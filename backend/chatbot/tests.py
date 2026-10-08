import hashlib
import json
import os
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from agent.models import Lead
from crm.models import Task
from inquiries.models import Inquiry, RateBucket
from .models import AssistantConfiguration, ChatMessage, Conversation, DailyUsage, InquiryProcessing, OutreachDraft
from .provider import BudgetExceeded, ProviderUnavailable, complete
from .secrets import read_key, write_key
from .worker import process_inquiries


@override_settings(PROXY_SHARED_SECRET='a' * 64)
class ChatbotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sales = get_user_model().objects.create_user('salesai', password='Strong-test-937!')
        cls.sales.groups.add(Group.objects.get_or_create(name='sales')[0])
        cls.owner = get_user_model().objects.create_user('ownerai', password='Strong-test-937!')
        cls.owner.groups.add(Group.objects.get(name='sales'))
        cls.owner.user_permissions.add(*Permission.objects.filter(content_type__app_label='chatbot', codename__in=['change_assistantconfiguration', 'approve_outreachdraft']))
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(CHATBOT_SECRET_FILE=str(Path(self.directory.name) / 'groq.json'))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.config = AssistantConfiguration.load()
        self.config.enabled = True
        self.config.enabled_at = timezone.now() - timedelta(minutes=1)
        self.config.save()
        write_key('test-key-' + 'x' * 30)
    def post(self, data, **extra):
        return self.client.post(reverse('public-chat'), data=json.dumps(data), content_type='application/json', HTTP_X_SONUTECH_PROXY_SECRET='a' * 64, HTTP_X_SONUTECH_CLIENT_IP='203.0.113.4', **extra)
    def token(self):
        response = self.post({'action': 'start'})
        self.assertEqual(response.status_code, 200)
        return response.json()['token']
    def contact(self, token, **overrides):
        data = {'action': 'contact', 'token': token, 'contact_id': str(uuid.uuid4()), 'name': 'Camille', 'email': 'camille@example.com', 'phone': '', 'company': 'ACME', 'message': 'Projet de site internet', 'consent': True}
        data.update(overrides)
        return self.post(data)
    def test_public_relay_auth_and_unavailable(self):
        self.assertEqual(self.client.post(reverse('public-chat'), '{}', content_type='application/json').status_code, 403)
        self.config.enabled = False
        self.config.save()
        response = self.post({'action': 'start'})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()['available'])
        self.assertFalse(Conversation.objects.exists())
    @patch('chatbot.service.provider.complete')
    def test_message_idempotency_expiry_and_no_data_leak(self, provider):
        provider.return_value = {'reply': 'Quel est votre projet ?', 'suggest_contact': True, 'unexpected': 'ignored'}
        token = self.token()
        data = {'action': 'message', 'token': token, 'message_id': str(uuid.uuid4()), 'message': 'Bonjour'}
        first = self.post(data)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.post(data).json(), first.json())
        self.assertEqual(provider.call_count, 1)
        data['message'] = 'Different'
        self.assertEqual(self.post(data).status_code, 409)
        self.assertNotIn('unexpected', first.json())
        self.assertEqual(self.post({**data, 'token': 'x' * 43}).status_code, 401)
        Conversation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post(data).status_code, 401)
    def test_contact_consent_dedup_and_no_human_overwrite(self):
        lead = Lead.objects.create(email='CAMILLE@example.com', name='Human name', stage='won', internal_notes='Private confidential note')
        token = self.token()
        self.assertEqual(self.contact(token, consent=False).status_code, 400)
        self.assertFalse(Inquiry.objects.exists())
        response = self.contact(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.contact(token).status_code, 200)
        self.assertEqual(self.contact(token, message='Changed').status_code, 409)
        self.assertEqual(Inquiry.objects.count(), 1)
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Lead.objects.count(), 1)
        lead.refresh_from_db()
        self.assertEqual((lead.name, lead.stage, lead.internal_notes), ('Human name', 'won', 'Private confidential note'))
        self.assertNotIn('lead', response.json())
        self.assertNotContains(response, 'Private confidential')
    def test_phone_only_reuses_normalized_phone(self):
        lead = Lead.objects.create(email=None, phone='07 75 78 78 25', name='Phone user')
        self.assertEqual(self.contact(self.token(), email='', phone='+33775787825').status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(Inquiry.objects.get().email, '')
        self.assertEqual(Inquiry.objects.get().inquiryimport.lead, lead)
    @patch('chatbot.provider.urllib.request.urlopen', side_effect=OSError('secret must not leak'))
    def test_provider_failure_charged_and_daily_cap(self, _):
        self.config.daily_limit = 1
        self.config.save()
        token = self.token()
        data = {'action': 'message', 'token': token, 'message_id': str(uuid.uuid4()), 'message': 'Bonjour'}
        response = self.post(data)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.content.decode())
        self.assertEqual(DailyUsage.objects.get().calls, 1)
        self.assertEqual(self.post(data).status_code, 429)
        self.assertEqual(DailyUsage.objects.get().calls, 1)
        self.assertFalse(ChatMessage.objects.exists())
    def test_ip_limit_and_input_bounds(self):
        token = self.token()
        self.assertEqual(self.post({'action': 'message', 'token': token, 'message_id': str(uuid.uuid4()), 'message': 'x' * 2001}).status_code, 400)
        RateBucket.objects.update(count=30)
        self.assertEqual(self.post({'action': 'start'}).status_code, 429)
    def test_key_permissions_masking_file_mode_and_csrf(self):
        self.client.force_login(self.sales)
        url = reverse('chatbot:assistant_settings')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'api_key': 'y' * 30}).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'test-key-')
        self.assertEqual(os.stat(Path(self.directory.name) / 'groq.json').st_mode & 0o777, 0o600)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(url, {'action': 'save'}).status_code, 403)
        response = self.client.post(url, {'action': 'save', 'enabled': 'on', 'daily_limit': 'bad', 'api_key': 'must-not-render-' + 'z' * 30})
        self.assertNotContains(response, 'must-not-render-')
    @patch('chatbot.views.send_mail', return_value=1)
    def test_email_only_explicit_owner_approval_no_repeat(self, mail):
        lead = Lead.objects.create(name='Recipient', email='recipient@example.com')
        draft = OutreachDraft.objects.create(lead=lead, subject='Draft', body='Hello', analysis='Need')
        url = reverse('chatbot:draft_detail', args=[draft.pk])
        self.client.force_login(self.sales)
        self.assertEqual(self.client.post(url, {'action': 'send', 'subject': 'Reviewed', 'body': 'Approved'}).status_code, 403)
        self.client.force_login(self.owner)
        self.client.get(url)
        self.client.post(url, {'action': 'save', 'subject': 'Reviewed', 'body': 'Approved'})
        self.assertFalse(mail.called)
        with override_settings(EMAIL_HOST='', DEFAULT_FROM_EMAIL=''):
            self.client.post(url, {'action': 'send', 'subject': 'Reviewed', 'body': 'Approved'})
        self.assertFalse(mail.called)
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.com', DEFAULT_FROM_EMAIL='owner@example.com'):
            self.client.post(url, {'action': 'send', 'subject': 'Reviewed', 'body': 'Approved'})
            self.client.post(url, {'action': 'send', 'subject': 'Reviewed', 'body': 'Approved'})
        self.assertEqual(mail.call_count, 1)
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'sent')
        self.assertEqual(draft.recipient_email, lead.email)
    @patch('chatbot.views.send_mail', side_effect=OSError('private smtp error'))
    def test_uncertain_mail_failure_not_retried(self, mail):
        lead = Lead.objects.create(name='Recipient', email='recipient@example.com')
        draft = OutreachDraft.objects.create(lead=lead, subject='Draft', body='Hello', analysis='Need')
        self.client.force_login(self.owner)
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.com', DEFAULT_FROM_EMAIL='owner@example.com'):
            for _ in range(2):
                self.client.post(reverse('chatbot:draft_detail', args=[draft.pk]), {'action': 'send', 'subject': 'Draft', 'body': 'Hello'})
        self.assertEqual(mail.call_count, 1)
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'failed')
        self.assertNotIn('private', draft.last_error)
    def inquiry(self, **kwargs):
        data = {'name': 'Website lead', 'email': 'fresh@example.com', 'message': 'Build a website', 'kind': 'contact', 'source': 'website', 'idempotency_key': uuid.uuid4(), 'payload_hash': 'hash'}
        data.update(kwargs)
        return Inquiry.objects.create(**data)
    @patch('chatbot.views.send_mail')
    @patch('chatbot.service.provider.complete', return_value={'analysis': 'Website needed', 'subject': 'Votre projet', 'body': 'Bonjour, parlons de votre besoin.', 'extra': 'ignored'})
    def test_worker_new_only_draft_only_idempotent(self, provider, mail):
        old = self.inquiry(email='old@example.com')
        Inquiry.objects.filter(pk=old.pk).update(created_at=self.config.enabled_at - timedelta(seconds=1))
        fresh = self.inquiry()
        self.assertEqual(process_inquiries(), 1)
        self.assertEqual(process_inquiries(), 0)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(OutreachDraft.objects.get().status, 'pending')
        self.assertEqual(provider.call_count, 1)
        self.assertFalse(mail.called)
        self.assertIsNotNone(InquiryProcessing.objects.get(inquiry=fresh).completed_at)
        self.config.enabled = False
        self.config.save()
        self.inquiry(email='disabled@example.com')
        self.assertEqual(process_inquiries(), 0)
    @patch('chatbot.service.provider.complete', side_effect=ProviderUnavailable('Service indisponible.'))
    def test_worker_retry_limit(self, provider):
        inquiry = self.inquiry()
        for _ in range(5):
            process_inquiries()
        self.assertEqual(provider.call_count, 3)
        self.assertEqual(InquiryProcessing.objects.get(inquiry=inquiry).attempts, 3)
        self.assertEqual(Task.objects.count(), 1)

    @patch('chatbot.service.provider.complete')
    def test_worker_budget_exhaustion_preserves_retries(self, provider):
        inquiry = self.inquiry()
        provider.side_effect = BudgetExceeded('Limite quotidienne atteinte.')
        for _ in range(5):
            self.assertEqual(process_inquiries(), 0)
        processing = InquiryProcessing.objects.get(inquiry=inquiry)
        self.assertEqual(processing.attempts, 0)
        self.assertIsNone(processing.completed_at)
        self.assertEqual(Task.objects.count(), 1)
        provider.side_effect = None
        provider.return_value = {'analysis': 'Website needed', 'subject': 'Votre projet', 'body': 'Bonjour, parlons de votre besoin.'}
        self.assertEqual(process_inquiries(), 1)
        processing.refresh_from_db()
        self.assertEqual(processing.attempts, 1)
        self.assertIsNotNone(processing.completed_at)
        self.assertEqual(OutreachDraft.objects.count(), 1)

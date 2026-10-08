import hashlib
import uuid
from datetime import timedelta
from io import StringIO
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from agent.models import Lead
from inquiries.models import Inquiry
from .models import Appointment, SetupToken, Task


class CRMTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('bootstrap_roles', stdout=StringIO())
        cls.sales = get_user_model().objects.create_user('salesperson', password='Safe-password-942!')
        cls.sales.groups.add(Group.objects.get(name='sales'))
        cls.editor = get_user_model().objects.create_user('editor', password='Safe-password-942!')
        cls.editor.groups.add(Group.objects.get(name='content_editor'))
        cls.lead = Lead.objects.create(name='Test client', email='CLIENT@example.com')
    def setUp(self):
        self.client.force_login(self.sales)
    def test_access_and_headers(self):
        self.client.logout()
        response = self.client.get(reverse('crm:prospect_list'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertIn('noindex', response['X-Robots-Tag'])
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse('crm:prospect_list')).status_code, 403)
        self.assertEqual(self.client.post(reverse('crm:prospect_create'), {'name': 'Bad', 'phone': '123'}).status_code, 403)
    def test_create_phone_only_and_case_insensitive_duplicate(self):
        for name in ['One', 'Two']:
            self.assertEqual(self.client.post(reverse('crm:prospect_create'), {'name': name, 'phone': '0775787825', 'stage': 'contacted'}).status_code, 302)
        self.assertEqual(Lead.objects.filter(email__isnull=True).count(), 2)
        response = self.client.post(reverse('crm:prospect_create'), {'name': 'Duplicate', 'email': 'client@example.com', 'stage': 'to_qualify'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Un prospect utilise déjà cet email.')
    def test_edit_and_search(self):
        self.client.post(reverse('crm:prospect_edit', args=[self.lead.pk]), {'name': 'Updated', 'email': self.lead.email, 'stage': 'won'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'won')
        response = self.client.get(reverse('crm:prospect_list'), {'q': 'Updated', 'stage': 'won'})
        self.assertEqual(list(response.context['page_obj']), [self.lead])
    def test_inquiry_import_idempotent_and_case_insensitive(self):
        inquiry = Inquiry.objects.create(idempotency_key=uuid.uuid4(), payload_hash='x', name='Client', email='client@example.com', message='A project', kind='contact')
        url = reverse('crm:inquiry_import', args=[inquiry.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(inquiry.inquiryimport.lead_id, self.lead.pk)
        detail = self.client.get(reverse('crm:prospect_detail', args=[self.lead.pk]))
        self.assertIn(inquiry, detail.context['inquiries'])
    def test_appointments_validation_timezone_and_status(self):
        data = {'title': 'Appel', 'lead': str(self.lead.pk), 'start': '2026-10-12T10:00', 'end': '2026-10-12T09:00', 'status': 'scheduled'}
        self.assertEqual(self.client.post(reverse('crm:appointment_create'), data).status_code, 200)
        self.assertFalse(Appointment.objects.exists())
        data['end'] = '2026-10-12T11:00'
        self.assertEqual(self.client.post(reverse('crm:appointment_create'), data).status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.start.hour, 8)
        data['status'] = 'done'
        self.client.post(reverse('crm:appointment_edit', args=[appointment.pk]), data)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'done')
    def test_task_and_notes(self):
        self.client.post(reverse('crm:task_create'), {'title': 'Rappeler', 'due_date': '2026-10-12', 'lead': str(self.lead.pk)})
        task = Task.objects.get()
        url = reverse('crm:task_toggle', args=[task.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        task.refresh_from_db()
        self.assertTrue(task.done)
        self.client.post(reverse('crm:note_create', args=[self.lead.pk]), {'body': '<script>alert(1)</script>'})
        response = self.client.get(reverse('crm:prospect_detail', args=[self.lead.pk]))
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.lead.notes.get().author, self.sales)
    def test_csrf_and_get_logout(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.sales)
        self.assertEqual(client.post(reverse('crm:prospect_create'), {'name': 'No CSRF'}).status_code, 403)
        self.assertEqual(client.post(reverse('crm:activate'), {'token': 'invalid'}).status_code, 403)
        self.assertEqual(client.post(reverse('crm:login'), {'username': 'salesperson'}).status_code, 403)
        self.assertEqual(client.get(reverse('crm:logout')).status_code, 405)
    def test_login(self):
        self.client.logout()
        response = self.client.post(reverse('crm:login'), {'username': 'salesperson', 'password': 'Safe-password-942!'})
        self.assertRedirects(response, reverse('crm:prospect_list'))
    def test_setup_expiry_replay_and_password_preservation(self):
        output = StringIO()
        call_command('create_crm_access', 'new@example.com', base_url='https://sonutech.fr', stdout=output)
        raw = output.getvalue().strip().split('#')[-1]
        token = SetupToken.objects.get(token_hash=hashlib.sha256(raw.encode()).hexdigest())
        self.assertFalse(token.user.has_usable_password())
        self.client.logout()
        data = {'token': raw, 'new_password1': 'short', 'new_password2': 'short'}
        self.assertEqual(self.client.post(reverse('crm:activate'), data).status_code, 200)
        token.refresh_from_db()
        self.assertIsNone(token.used_at)
        data.update(new_password1='Brand-new-strong-973!', new_password2='Brand-new-strong-973!')
        self.assertEqual(self.client.post(reverse('crm:activate'), data).status_code, 302)
        self.client.logout()
        response = self.client.post(reverse('crm:activate'), data)
        self.assertContains(response, 'Ce lien est invalide, expiré ou déjà utilisé.')
        user = get_user_model().objects.get(email='new@example.com')
        password = user.password
        call_command('create_crm_access', 'new@example.com', stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.password, password)
        call_command('create_crm_access', 'expired@example.com', stdout=output)
        expired = SetupToken.objects.get(user__email='expired@example.com')
        expired.expires_at = timezone.now() - timedelta(seconds=1)
        expired.save()
        raw_expired = output.getvalue().strip().split('#')[-1]
        data['token'] = raw_expired
        self.assertContains(self.client.post(reverse('crm:activate'), data), 'Ce lien est invalide, expiré ou déjà utilisé.')

    @override_settings(LOGIN_RATE_LIMIT=1)
    def test_login_throttling_and_invalid_prefill(self):
        self.assertEqual(self.client.get(reverse('crm:appointment_create'), {'lead': 'not-a-uuid'}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(reverse('crm:login'), {'username': 'bad', 'password': 'bad'}).status_code, 200)
        self.assertEqual(self.client.post(reverse('crm:login'), {'username': 'bad', 'password': 'bad'}).status_code, 429)

    def test_task_edit(self):
        task = Task.objects.create(title='Original', lead=self.lead)
        self.assertEqual(self.client.post(reverse('crm:task_edit', args=[task.pk]), {'title': 'Updated', 'due_date': '2026-11-01'}).status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Updated')
        self.assertEqual(str(task.due_date), '2026-11-01')

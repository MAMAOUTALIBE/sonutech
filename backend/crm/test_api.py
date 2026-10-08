import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import AuditLog
from agent.models import Lead
from chatbot.models import OutreachDraft
from inquiries.models import Inquiry
from .models import Client, Document, Invoice, Opportunity, Project, Quote, Task


class CRMProAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sales = get_user_model().objects.create_user('salespro', password='Very-strong-Test-832!')
        cls.manager = get_user_model().objects.create_user('managerpro', password='Very-strong-Test-832!')
        cls.viewer = get_user_model().objects.create_user('viewerpro', password='Very-strong-Test-832!')
        for user, role in [(cls.sales, 'sales'), (cls.manager, 'manager'), (cls.viewer, 'viewer')]:
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        cls.lead = Lead.objects.create(name='Existing prospect', email='prospect@example.com', internal_notes='Preserved')
        cls.customer = Client.objects.create(name='Customer', email='client@example.com')
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.sales)
    def url(self, resource, pk=None):
        return f'/api/v1/crm/{resource}/' + (f'{pk}/' if pk is not None else '')
    def test_auth_roles_and_no_cache(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url('bootstrap')).status_code, 403)
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.url('bootstrap'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertIn('noindex', response['X-Robots-Tag'])
        self.assertFalse(response.data['user']['can_write'])
        self.assertEqual(self.client.post(self.url('clients'), {'name': 'Forbidden'}, format='json').status_code, 403)
        self.assertEqual(self.client.get(self.url('users')).status_code, 403)
        csrf = APIClient(enforce_csrf_checks=True)
        csrf.force_login(self.sales)
        self.assertEqual(csrf.post(self.url('clients'), {'name': 'Missing CSRF'}, format='json').status_code, 403)
    def test_prospect_crud_dedup_filter_conversion(self):
        response = self.client.post(self.url('prospects'), {'name': 'Phone prospect', 'phone': '0775787825', 'stage': 'contacted', 'tags': ['À rappeler']}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertEqual(self.client.patch(self.url('prospects', pk), {'stage': 'qualified'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(self.url('prospects'), {'q': 'Phone', 'stage': 'qualified'}).data['count'], 1)
        self.assertEqual(self.client.get(self.url('prospects'), {'stage': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post(self.url('prospects'), {'name': 'Duplicate', 'email': 'PROSPECT@example.com'}, format='json').status_code, 400)
        converted = self.client.post(self.url('prospects', pk) + 'convert/')
        self.assertEqual(converted.status_code, 201)
        self.assertEqual(self.client.post(self.url('prospects', pk) + 'convert/').data['id'], converted.data['id'])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.internal_notes, 'Preserved')
    def test_clients_opportunities_projects_tasks_crud(self):
        created = self.client.post(self.url('opportunities'), {'title': 'ERP project', 'client': self.customer.pk, 'amount': '1200.50', 'probability': 40, 'service': 'digitalisation'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        opportunity = created.data['id']
        self.assertEqual(self.client.patch(self.url('opportunities', opportunity), {'stage': 'negotiation'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.url('opportunities', opportunity), {'probability': 101}, format='json').status_code, 400)
        project_data = {'name': 'ERP delivery', 'client': self.customer.pk, 'opportunity': opportunity, 'budget': '1200.50', 'cost': '100', 'progress': 30, 'start_date': '2026-10-10', 'due_date': '2026-10-20'}
        project = self.client.post(self.url('projects'), project_data, format='json')
        self.assertEqual(project.status_code, 201, project.data)
        self.assertEqual(self.client.patch(self.url('projects', project.data['id']), {'progress': 101}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url('projects', project.data['id']), {'due_date': '2026-01-01'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.url('clients', self.customer.pk)).status_code, 400)
        task = self.client.post(self.url('tasks'), {'title': 'Follow up', 'lead': str(self.lead.pk), 'priority': 'high'}, format='json')
        self.assertEqual(task.status_code, 201)
        self.assertEqual(self.client.patch(self.url('tasks', task.data['id']), {'done': True}, format='json').status_code, 200)
        self.assertEqual(self.client.get(self.url('tasks'), {'done': 'banana'}).status_code, 400)
        self.assertEqual(self.client.get(self.url('bootstrap')).data['dashboard']['services'], [{'name': 'Digitalisation', 'value': 1}])
    def financial(self):
        return {'client': self.customer.pk, 'issue_date': '2026-10-08', 'due_date': '2026-11-08', 'items': [{'description': 'Consulting', 'quantity': '3', 'unit_price': '0.10', 'tax_rate': '20'}, {'description': 'Service', 'quantity': '1.5', 'unit_price': '19.99', 'tax_rate': '5.5'}]}
    def test_financial_decimal_numbering_immutability(self):
        data = self.financial()
        data.update(total_ttc='0.01', number='HACKED')
        first = self.client.post(self.url('invoices'), data, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['total_ht'], '30.29')
        self.assertEqual(first.data['total_tax'], '1.71')
        self.assertEqual(first.data['total_ttc'], '32.00')
        self.assertEqual(first.data['number'], 'FAC-2026-00001')
        second = self.client.post(self.url('invoices'), self.financial(), format='json')
        self.assertEqual(second.data['number'], 'FAC-2026-00002')
        pk = first.data['id']
        self.assertEqual(self.client.patch(self.url('invoices', pk), {'status': 'issued'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.url('invoices', pk), {'items': self.financial()['items']}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url('invoices', pk), {'status': 'draft'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.url('invoices', pk)).status_code, 400)
        self.assertEqual(self.client.patch(self.url('invoices', pk), {'status': 'paid'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(self.url('bootstrap')).data['kpis']['revenue'], '30.29')
    def test_financial_invalid_relations_and_lines(self):
        other = Client.objects.create(name='Other')
        project = Project.objects.create(name='Other project', client=other)
        self.assertEqual(self.client.post(self.url('quotes'), {**self.financial(), 'project': project.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url('quotes'), {**self.financial(), 'items': []}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url('quotes'), {**self.financial(), 'items': [{'description': 'Bad', 'quantity': -1, 'unit_price': 1}]}, format='json').status_code, 400)
        quote = self.client.post(self.url('quotes'), self.financial(), format='json')
        self.assertEqual(quote.status_code, 201)
        self.assertEqual(self.client.delete(self.url('quotes', quote.data['id'])).status_code, 204)
    def test_appointments_dates_and_partial_update(self):
        data = {'title': 'Meeting', 'start': '2026-10-12T10:00:00+02:00', 'end': '2026-10-12T11:00:00+02:00', 'lead': str(self.lead.pk)}
        appointment = self.client.post(self.url('appointments'), data, format='json')
        self.assertEqual(appointment.status_code, 201, appointment.data)
        self.assertEqual(self.client.get(self.url('appointments'), {'date_from': '2026-10-12', 'date_to': '2026-10-18'}).data['count'], 1)
        self.assertEqual(self.client.get(self.url('appointments'), {'date_from': '2026-10-19', 'date_to': '2026-10-25'}).data['count'], 0)
        self.assertEqual(self.client.get(self.url('appointments'), {'date_from': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.patch(self.url('appointments', appointment.data['id']), {'end': '2026-10-12T09:00:00+02:00'}, format='json').status_code, 400)
    def test_private_document_upload_download_and_type_validation(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(CRM_DOCUMENT_ROOT=directory):
            # FileField storage callable resolves when models load; isolate its instance.
            with patch.object(Document._meta.get_field('file').storage, 'location', directory):
                response = self.client.post(self.url('documents'), {'title': 'Private contract', 'file': SimpleUploadedFile('contract.pdf', b'%PDF-1.4\nPrivate data'), 'client': self.customer.pk}, format='multipart')
                self.assertEqual(response.status_code, 201, response.data)
                self.assertNotIn('file', response.data)
                self.assertNotIn(directory, str(response.data))
                download = self.client.get(response.data['download_url'])
                self.assertEqual(download.status_code, 200)
                self.assertIn('attachment', download['Content-Disposition'])
                self.assertEqual(download['Cache-Control'], 'no-store')
                self.assertEqual(b''.join(download.streaming_content), b'%PDF-1.4\nPrivate data')
                self.client.force_authenticate(None)
                self.assertEqual(self.client.get(response.data['download_url']).status_code, 403)
                self.client.force_authenticate(self.sales)
                bad = self.client.post(self.url('documents'), {'title': 'Fake', 'file': SimpleUploadedFile('fake.pdf', b'<html>bad</html>')}, format='multipart')
                self.assertEqual(bad.status_code, 400)
    def test_manager_users_and_self_protection(self):
        self.assertEqual(self.client.get(self.url('users')).status_code, 403)
        self.client.force_authenticate(self.manager)
        data = {'username': 'newviewer', 'email': 'viewer@example.com', 'role': 'viewer', 'password': 'Another-Strong-pass-842!'}
        response = self.client.post(self.url('users'), data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        self.assertEqual(response.data['role'], 'viewer')
        self.assertTrue(get_user_model().objects.get(pk=response.data['id']).check_password(data['password']))
        self.assertEqual(self.client.patch(self.url('users', self.manager.pk), {'role': 'viewer'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url('users', self.manager.pk), {'is_active': False}, format='json').status_code, 400)
        self.assertNotIn('password', AuditLog.objects.filter(resource='auth.user').first().changed_fields)
        self.assertEqual(self.client.patch(self.url('settings'), {'company_name': 'SONUTECH PRO'}, format='json').status_code, 200)
    @patch('crm.api.send_mail')
    def test_email_pending_only_no_fake_send(self, send):
        email = self.client.post(self.url('emails'), {'lead': str(self.lead.pk), 'subject': 'Hello', 'body': 'Draft message', 'status': 'sent'}, format='json')
        self.assertEqual(email.status_code, 201, email.data)
        self.assertEqual(email.data['status'], 'pending')
        self.assertEqual(email.data['lead_email'], self.lead.email)
        self.assertEqual(email.data['recipient_email'], '')
        url = self.url('emails', email.data['id'])
        self.assertEqual(self.client.post(url + 'send/').status_code, 403)
        self.sales.user_permissions.add(Permission.objects.get(codename='approve_outreachdraft'))
        self.client.force_authenticate(get_user_model().objects.get(pk=self.sales.pk))
        with override_settings(EMAIL_HOST=''):
            self.assertEqual(self.client.post(url + 'send/').status_code, 400)
        self.assertFalse(send.called)
        self.assertEqual(self.client.post(url + 'reject/').status_code, 200)
        self.assertEqual(self.client.patch(url, {'body': 'Changed'}, format='json').status_code, 400)
    def test_inquiry_import_preserves_public_requests(self):
        inquiry = Inquiry.objects.create(idempotency_key=uuid.uuid4(), payload_hash='x', kind='contact', name='Website visitor', email='new@example.com', message='Website request')
        self.assertEqual(self.client.get(self.url('inquiries')).data['count'], 1)
        first = self.client.post(self.url('inquiries', inquiry.pk) + 'import/')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.client.post(self.url('inquiries', inquiry.pk) + 'import/').data['id'], first.data['id'])
        self.assertEqual(self.client.get(self.url('inquiries')).data['count'], 0)

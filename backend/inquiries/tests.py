import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from content.models import Service, Course
from accounts.models import AuditLog
from .models import Inquiry, RateBucket
from .notifications import notify_inquiry

def payload(**extra):
    return {'kind': 'contact', 'name': 'Camille Martin', 'email': 'camille@example.com', 'domain': 'informatique', 'message': 'Je souhaite échanger sur mon projet de site.', 'idempotency_key': str(uuid.uuid4()), **extra}

@override_settings(INQUIRY_RATE_LIMIT=100)
class InquiryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Service.objects.create(slug='informatique', title='Informatique', description='Web', published=True)
        Course.objects.create(slug='ia', title='IA', description='IA', category='IA', duration='À définir', modality='À définir', published=True)
    def setUp(self):
        self.client = APIClient()
    def test_persistence_and_idempotency(self):
        data = payload()
        with patch('inquiries.views.notify_inquiry') as notification, self.captureOnCommitCallbacks(execute=True):
            first = self.client.post('/api/v1/public/inquiries/', data, format='json')
            second = self.client.post('/api/v1/public/inquiries/', data, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data, second.data)
        self.assertEqual(Inquiry.objects.count(), 1)
        notification.assert_called_once()
        self.assertEqual(self.client.get('/api/v1/public/inquiries/').status_code, 405)
        self.assertEqual(self.client.get(f'/api/v1/public/inquiries/{first.data["id"]}/').status_code, 404)
    def test_conflicting_idempotency_key(self):
        data = payload()
        self.client.post('/api/v1/public/inquiries/', data, format='json')
        self.assertEqual(self.client.post('/api/v1/public/inquiries/', {**data, 'message': 'Un autre projet à étudier.'}, format='json').status_code, 409)
    def test_validation_and_honeypot(self):
        for changes in [{'email': 'invalid'}, {'message': 'court'}, {'website': 'bot'}, {'domain': 'unknown'}, {'kind': 'quote'}, {'kind': 'training'}, {'kind': 'contact', 'course': 'ia'}]:
            self.assertEqual(self.client.post('/api/v1/public/inquiries/', payload(**changes), format='json').status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)
    def test_unpublished_service_and_course_rejected(self):
        Service.objects.filter(slug='informatique').update(published=False)
        self.assertEqual(self.client.post('/api/v1/public/inquiries/', payload(), format='json').status_code, 400)
        Service.objects.filter(slug='informatique').update(published=True)
        Course.objects.filter(slug='ia').update(published=False)
        self.assertEqual(self.client.post('/api/v1/public/inquiries/', payload(kind='training', course='ia'), format='json').status_code, 400)
        self.assertEqual(Inquiry.objects.count(), 0)
    def test_training_and_quote(self):
        for changes in [{'kind': 'quote', 'project_type': 'Site web'}, {'kind': 'training', 'course': 'ia'}]:
            self.assertEqual(self.client.post('/api/v1/public/inquiries/', payload(**changes), format='json').status_code, 201)
        self.assertEqual(Inquiry.objects.get(kind='training').course.slug, 'ia')
    @override_settings(INQUIRY_RATE_LIMIT=2)
    def test_shared_database_rate_limit(self):
        self.assertEqual(self.client.post('/api/v1/public/inquiries/', payload(), format='json').status_code, 201)
        other_client = APIClient()
        self.assertEqual(other_client.post('/api/v1/public/inquiries/', payload(), format='json').status_code, 201)
        self.assertEqual(other_client.post('/api/v1/public/inquiries/', payload(), format='json').status_code, 429)
        self.assertEqual(Inquiry.objects.count(), 2)
    @override_settings(INQUIRY_RATE_LIMIT=1, PROXY_SHARED_SECRET='test-relay-secret-at-least-32-characters')
    def test_only_authenticated_relay_can_supply_client_ip(self):
        secret = 'test-relay-secret-at-least-32-characters'
        path = '/api/v1/public/inquiries/'
        self.assertEqual(self.client.post(path, payload(), format='json', HTTP_X_FORWARDED_FOR='192.0.2.1').status_code, 201)
        self.assertEqual(self.client.post(path, payload(), format='json', HTTP_X_SONUTECH_CLIENT_IP='192.0.2.2', HTTP_X_SONUTECH_PROXY_SECRET='wrong').status_code, 429)
        for ip in ['192.0.2.10', '192.0.2.11']:
            self.assertEqual(self.client.post(path, payload(), format='json', HTTP_X_SONUTECH_CLIENT_IP=ip, HTTP_X_SONUTECH_PROXY_SECRET=secret).status_code, 201)
        self.assertEqual(self.client.post(path, payload(), format='json', HTTP_X_SONUTECH_CLIENT_IP='192.0.2.10', HTTP_X_SONUTECH_PROXY_SECRET=secret).status_code, 429)
        self.assertEqual(self.client.post(path, payload(), format='json', HTTP_X_SONUTECH_CLIENT_IP='not-an-ip', HTTP_X_SONUTECH_PROXY_SECRET=secret).status_code, 429)
    @override_settings(EMAIL_HOST='smtp.example.com', DEFAULT_FROM_EMAIL='site@example.com', INQUIRY_NOTIFICATION_EMAIL='team@example.com')
    def test_smtp_failure_preserves_submission_then_retry(self):
        with patch('inquiries.notifications.send_mail', side_effect=OSError('SMTP unreachable')), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/v1/public/inquiries/', payload(), format='json')
        self.assertEqual(response.status_code, 201)
        item = Inquiry.objects.get()
        self.assertEqual(item.notification_status, 'failed')
        with patch('inquiries.notifications.send_mail', return_value=1) as mail:
            call_command('retry_notifications')
            call_command('retry_notifications')
        self.assertEqual(mail.call_count, 1)
        item.refresh_from_db()
        self.assertEqual(item.notification_status, 'sent')
        self.assertEqual(item.notification_attempts, 2)

class ManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('bootstrap_roles')
        cls.service = Service.objects.create(slug='informatique', title='Informatique', description='Web', published=True)
        cls.item = Inquiry.objects.create(idempotency_key=uuid.uuid4(), payload_hash='test', kind='contact', name='=1+1', email='a@example.com', message='Projet numérique', domain=cls.service)
        cls.users = {}
        for role in ['content_editor', 'sales', 'manager']:
            user = get_user_model().objects.create_user(username=role, password='Long test password 123!')
            user.groups.add(Group.objects.get(name=role))
            cls.users[role] = user
    def setUp(self):
        self.client = APIClient()
    def test_private_endpoints_require_auth(self):
        for path in ['inquiries', 'services', 'settings', 'users', 'groups', 'audit-logs', 'images']:
            self.assertEqual(self.client.get(f'/api/v1/manage/{path}/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/manage/inquiries/export/').status_code, 403)
    def test_editor_cannot_access_commercial_data(self):
        self.client.force_authenticate(self.users['content_editor'])
        self.assertEqual(self.client.get('/api/v1/manage/inquiries/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/manage/inquiries/export/').status_code, 403)
        response = self.client.patch(f'/api/v1/manage/services/{self.service.pk}/', {'title': 'Nouveau titre'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuditLog.objects.get().changed_fields, ['title'])
        self.assertEqual(self.client.get('/api/v1/manage/users/').status_code, 403)
    def test_sales_permissions_status_and_safe_csv(self):
        self.client.force_authenticate(self.users['sales'])
        self.assertEqual(self.client.patch(f'/api/v1/manage/services/{self.service.pk}/', {'title': 'No'}, format='json').status_code, 403)
        response = self.client.patch(f'/api/v1/manage/inquiries/{self.item.pk}/', {'status': 'in_progress', 'internal_notes': 'Appeler la semaine prochaine.'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/manage/inquiries/?status=in_progress&search=example').data['count'], 1)
        csv = self.client.get('/api/v1/manage/inquiries/export/')
        self.assertEqual(csv.status_code, 200)
        self.assertIn("'=1+1", csv.content.decode())
        self.assertNotIn('Appeler la semaine', csv.content.decode())
        self.assertEqual(self.client.get('/api/v1/manage/audit-logs/').status_code, 403)
    def test_manager_cannot_escalate_to_superuser(self):
        self.client.force_authenticate(self.users['manager'])
        self.assertEqual(self.client.get('/api/v1/manage/audit-logs/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/manage/users/').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/manage/groups/', {'name': 'admin'}, format='json').status_code, 403)
    def test_session_csrf_login_and_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        data = {'username': 'content_editor', 'password': 'Long test password 123!'}
        self.assertEqual(client.post('/api/v1/auth/login/', data, format='json').status_code, 403)
        token = client.get('/api/v1/auth/csrf/').data['csrfToken']
        response = client.post('/api/v1/auth/login/', data, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get('/api/v1/auth/me/').status_code, 200)
        self.assertEqual(client.patch(f'/api/v1/manage/services/{self.service.pk}/', {'title': 'Sans CSRF'}, format='json').status_code, 403)
        self.assertEqual(client.patch(f'/api/v1/manage/services/{self.service.pk}/', {'title': 'Avec CSRF'}, format='json', HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code, 200)

@override_settings(INQUIRY_RATE_LIMIT=100)
class ConcurrencyTests(TransactionTestCase):
    def test_simultaneous_submissions_create_one_record(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL concurrency test')
        Service.objects.create(slug='informatique', title='Informatique', description='Web', published=True)
        data = payload()
        def submit():
            close_old_connections()
            try:
                return APIClient().post('/api/v1/public/inquiries/', data, format='json').status_code
            finally:
                connection.close()
        with patch('inquiries.views.notify_inquiry'), ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: submit(), range(4)))
        self.assertEqual(sorted(statuses), [200, 200, 200, 201])
        self.assertEqual(Inquiry.objects.count(), 1)

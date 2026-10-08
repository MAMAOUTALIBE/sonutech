"""Independent regression coverage for private management and media safety."""
from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import AuditLog
from content.models import ImageAsset

class PrivateManagementRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('bootstrap_roles')
        cls.admin = get_user_model().objects.create_superuser(username='root-test', password='Only test password 4832!')
        cls.editor = get_user_model().objects.create_user(username='editor-test')
        cls.editor.groups.add(Group.objects.get(name='content_editor'))

    def test_user_password_is_hashed_hidden_and_audit_contains_only_field_names(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        secret = 'Test password must never be logged 72849!'
        result = client.post('/api/v1/manage/users/', {'username': 'new-test-user', 'password': secret}, format='json')
        self.assertEqual(result.status_code, 201)
        self.assertNotIn('password', result.data)
        self.assertTrue(get_user_model().objects.get(username='new-test-user').check_password(secret))
        log = AuditLog.objects.get()
        self.assertIn('password', log.changed_fields)
        self.assertNotIn(secret, str(log.__dict__))
        self.assertEqual(result['Cache-Control'], 'no-store')

    def test_inactive_and_no_role_users_cannot_read_private_resources(self):
        for username, active in [('inactive-test', False), ('unassigned-test', True)]:
            user = get_user_model().objects.create_user(username=username, is_active=active)
            client = APIClient()
            client.force_authenticate(user)
            for resource in ['inquiries', 'services', 'images', 'audit-logs', 'users', 'groups']:
                self.assertEqual(client.get(f'/api/v1/manage/{resource}/').status_code, 403)

    def test_upload_api_requires_permission_and_stores_reencoded_jpeg(self):
        def upload():
            out=BytesIO()
            Image.new('RGB', (40,30), 'green').save(out, 'PNG')
            return SimpleUploadedFile('untrusted-name.png', out.getvalue(), content_type='image/png')
        client=APIClient()
        self.assertEqual(client.post('/api/v1/manage/images/', {'file':upload(),'alt':'Illustration'},format='multipart').status_code,403)
        client.force_authenticate(self.editor)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response=client.post('/api/v1/manage/images/', {'file':upload(),'alt':'Illustration'},format='multipart')
            self.assertEqual(response.status_code,201)
            asset=ImageAsset.objects.get()
            self.assertTrue(asset.file.name.endswith('.jpg'))
            self.assertNotIn('untrusted-name',asset.file.name)
            with Image.open(asset.file.path) as img:
                self.assertEqual(img.format,'JPEG')
                self.assertEqual(img.size,(40,30))
            self.assertEqual(AuditLog.objects.get().action,'create')

    def test_csrf_logout_invalidates_session_and_bad_origin_not_allowed(self):
        client=APIClient(enforce_csrf_checks=True)
        token=client.get('/api/v1/auth/csrf/').data['csrfToken']
        response=client.post('/api/v1/auth/login/', {'username':'root-test','password':'Only test password 4832!'},format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post('/api/v1/auth/logout/').status_code,403)
        self.assertEqual(client.post('/api/v1/auth/logout/',HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code,204)
        self.assertEqual(client.get('/api/v1/auth/me/').status_code,403)
        cors=client.get('/api/v1/public/services/',HTTP_ORIGIN='https://untrusted.example')
        self.assertNotIn('Access-Control-Allow-Origin',cors)

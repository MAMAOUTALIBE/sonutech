from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import Service, Slide, Sector, Course, SiteSettings
from .serializers import ImageSerializer

class ContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_content')
        call_command('bootstrap_roles')
    def setUp(self):
        self.client = APIClient()
    def test_seed_endpoints_and_details(self):
        for resource, model, count in [('services', Service, 6), ('slides', Slide, 5), ('sectors', Sector, 3), ('courses', Course, 4)]:
            response = self.client.get(f'/api/v1/public/{resource}/')
            self.assertEqual(response.status_code, 200)
            self.assertIsInstance(response.data, list)
            self.assertEqual(len(response.data), count)
            self.assertEqual(self.client.get(f'/api/v1/public/{resource}/{model.objects.first().slug}/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/public/settings/').data['site_name'], 'SONUTECH')
    def test_unpublished_never_exposed(self):
        for resource, model in [('services', Service), ('slides', Slide), ('sectors', Sector), ('courses', Course)]:
            item = model.objects.first()
            item.published = False
            item.save()
            self.assertEqual(self.client.get(f'/api/v1/public/{resource}/{item.slug}/').status_code, 404)
            self.assertNotIn(item.slug, [row['slug'] for row in self.client.get(f'/api/v1/public/{resource}/').data])
    def test_seed_preserves_edits(self):
        item = Service.objects.first()
        item.title = 'Édition conservée'
        item.save()
        call_command('seed_content')
        item.refresh_from_db()
        self.assertEqual(item.title, 'Édition conservée')
        self.assertEqual(Service.objects.count(), 6)
    def test_private_edit_immediately_visible_and_html_rejected(self):
        user = get_user_model().objects.create_user(username='editor')
        user.groups.add(Group.objects.get(name='content_editor'))
        self.client.force_authenticate(user)
        item = Service.objects.first()
        for data in [{'body': '<script>alert(1)</script>'}, {'benefits': ['<b>unsafe</b>']}, {'image': 'javascript:alert(1)'}, {'image': '/images/picture.webp', 'image_alt': ''}]:
            self.assertEqual(self.client.patch(f'/api/v1/manage/services/{item.pk}/', data, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/manage/services/{item.pk}/', {'description': 'Description modifiée via API.'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(f'/api/v1/public/services/{item.slug}/').data['description'], 'Description modifiée via API.')
    def test_course_category_filter(self):
        self.assertEqual(len(self.client.get('/api/v1/public/courses/?category=CRM').data), 1)
    def test_upload_rejects_svg_and_reencodes_image(self):
        serializer = ImageSerializer(data={'alt': 'Image', 'file': SimpleUploadedFile('test.svg', b'<svg onload="alert(1)"/>', content_type='image/svg+xml')})
        self.assertFalse(serializer.is_valid())
        buffer = BytesIO()
        Image.new('RGB', (32, 32), 'blue').save(buffer, 'PNG')
        serializer = ImageSerializer(data={'alt': 'Image', 'file': SimpleUploadedFile('test.png', buffer.getvalue(), content_type='image/png')})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.validated_data['file'].name.endswith('.jpg'))
    def test_editor_can_create_and_delete_content_but_public_cannot_write(self):
        data = {'title': 'Service de test', 'slug': 'test-service', 'description': 'Contenu de test', 'published': False}
        self.assertEqual(self.client.post('/api/v1/public/services/', data, format='json').status_code, 405)
        user = get_user_model().objects.create_user(username='writer')
        user.groups.add(Group.objects.get(name='content_editor'))
        self.client.force_authenticate(user)
        response = self.client.post('/api/v1/manage/services/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get('/api/v1/public/services/test-service/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/v1/manage/services/{response.data["id"]}/').status_code, 204)
    def test_settings_editorial_fields_and_nested_validation(self):
        user = get_user_model().objects.create_user(username='settings-editor')
        user.groups.add(Group.objects.get(name='content_editor'))
        self.client.force_authenticate(user)
        data = {'about_title': 'Une approche adaptée', 'about_description': 'Description publique', 'about_body': ['Un accompagnement pratique.'], 'about_values': [{'title': 'Écoute', 'description': 'Comprendre votre besoin.'}], 'method_steps': [{'title': 'Découverte', 'description': 'Échanger avec votre équipe.'}], 'hero_note': 'Construisons votre projet.'}
        self.assertEqual(self.client.patch('/api/v1/manage/settings/1/', data, format='json').status_code, 200)
        published = self.client.get('/api/v1/public/settings/').data
        for key, value in data.items():
            self.assertEqual(published[key], value)
        for invalid in [
            {'about_body': ['<script>alert(1)</script>']},
            {'about_values': [{'title': '<b>HTML</b>', 'description': 'Description'}]},
            {'method_steps': [{'title': 'Titre', 'description': '<img src=x>'}]},
            {'method_steps': [{'title': 'Titre', 'description': 'Texte'}] * 11},
            {'method_steps': [{'title': 'Sans description'}]},
            {'about_values': {'title': 'Mauvais type'}},
        ]:
            self.assertEqual(self.client.patch('/api/v1/manage/settings/1/', invalid, format='json').status_code, 400)
        call_command('seed_content')
        self.assertEqual(self.client.get('/api/v1/public/settings/').data['about_title'], data['about_title'])
    def test_remote_images_are_rejected_for_managed_content(self):
        user = get_user_model().objects.create_user(username='image-editor')
        user.groups.add(Group.objects.get(name='content_editor'))
        self.client.force_authenticate(user)
        item = Service.objects.first()
        for path in ['https://example.com/image.jpg', '/images/../../secret', '/media/image.jpg?redirect=other']:
            self.assertEqual(self.client.patch(f'/api/v1/manage/services/{item.pk}/', {'image': path, 'image_alt': 'Description'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/manage/services/{item.pk}/', {'image': '/media/images/picture.jpg', 'image_alt': 'Description'}, format='json').status_code, 200)

import uuid
from io import BytesIO
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
from django.core.files.base import ContentFile
from rest_framework import serializers
from .models import Service, Slide, Sector, Course, SiteSettings, ImageAsset

class PlainContentSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        for key, value in attrs.items():
            if isinstance(value, str) and ('<' in value or '>' in value):
                raise serializers.ValidationError({key: 'Utilisez du texte simple, sans HTML.'})
            if key in ['needs', 'prestations', 'benefits', 'objectives', 'audience', 'prerequisites', 'program', 'about_body']:
                if not isinstance(value, list) or len(value) > 100 or any(not isinstance(v, str) or len(v) > 2000 or '<' in v or '>' in v for v in value):
                    raise serializers.ValidationError({key: 'Une liste de textes simples est attendue.'})
            if key.endswith('_href') and value and (not value.startswith('/') or value.startswith('//') or '\\' in value):
                raise serializers.ValidationError({key: 'Un chemin interne est attendu.'})
            if key == 'image' and value and not (value.startswith(('/media/', '/images/')) and '\\' not in value and '..' not in value and '?' not in value and '#' not in value):
                raise serializers.ValidationError({key: 'Chemin d’image gérée attendu : /images/ ou /media/.'})
        image = attrs.get('image', getattr(self.instance, 'image', ''))
        alt = attrs.get('image_alt', getattr(self.instance, 'image_alt', ''))
        if image and not alt:
            raise serializers.ValidationError({'image_alt': 'Décrivez cette image.'})
        return attrs

class ServiceSerializer(PlainContentSerializer):
    class Meta:
        model = Service
        fields = '__all__'
class SlideSerializer(PlainContentSerializer):
    class Meta:
        model = Slide
        fields = '__all__'
class SectorSerializer(PlainContentSerializer):
    class Meta:
        model = Sector
        fields = '__all__'
class CourseSerializer(PlainContentSerializer):
    class Meta:
        model = Course
        fields = '__all__'
class SettingsSerializer(PlainContentSerializer):
    class Meta:
        model = SiteSettings
        fields = '__all__'
    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field in ['about_values', 'method_steps']:
            if field not in attrs:
                continue
            value = attrs[field]
            if not isinstance(value, list) or len(value) > 10:
                raise serializers.ValidationError({field: 'Une liste de 10 éléments maximum est attendue.'})
            for item in value:
                if not isinstance(item, dict) or set(item) != {'title', 'description'}:
                    raise serializers.ValidationError({field: 'Chaque élément contient un titre et une description.'})
                for key, limit in [('title', 180), ('description', 2000)]:
                    text = item[key]
                    if not isinstance(text, str) or not text.strip() or len(text) > limit or '<' in text or '>' in text:
                        raise serializers.ValidationError({field: 'Utilisez des titres et descriptions en texte simple.'})
        return attrs
    def validate_social_links(self, value):
        if not isinstance(value, dict) or len(value) > 12 or any(not isinstance(v, str) or urlparse(v).scheme != 'https' for v in value.values()):
            raise serializers.ValidationError('Renseignez un objet de liens HTTPS.')
        return value

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageAsset
        fields = ['id', 'file', 'alt', 'created_at']
    def validate_file(self, file):
        if file.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Image limitée à 5 Mo.')
        try:
            img = Image.open(file)
            if img.format not in ('JPEG', 'PNG', 'WEBP') or img.width * img.height > 20_000_000:
                raise serializers.ValidationError('JPEG, PNG ou WebP, maximum 20 mégapixels.')
            img.load()
            out = BytesIO()
            img.convert('RGB').save(out, format='JPEG', quality=90)
            return ContentFile(out.getvalue(), name=f'{uuid.uuid4()}.jpg')
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise serializers.ValidationError('Image invalide.')

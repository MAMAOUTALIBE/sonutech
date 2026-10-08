from rest_framework import serializers
from content.models import Service, Course
from .models import Inquiry

class SubmissionSerializer(serializers.ModelSerializer):
    domain = serializers.SlugRelatedField(slug_field='slug', queryset=Service.objects.filter(published=True), required=True)
    course = serializers.SlugRelatedField(slug_field='slug', queryset=Course.objects.filter(published=True), required=False, allow_null=True)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    idempotency_key = serializers.UUIDField()
    class Meta:
        model = Inquiry
        fields = ['kind', 'name', 'company', 'email', 'phone', 'domain', 'message', 'project_type', 'budget', 'deadline', 'course', 'website', 'idempotency_key']
    def validate(self, attrs):
        if attrs.pop('website', ''):
            raise serializers.ValidationError({'website': 'La demande n’a pas pu être validée.'})
        if len(attrs.get('message', '').strip()) < 10:
            raise serializers.ValidationError({'message': 'Précisez votre besoin en au moins 10 caractères.'})
        if attrs.get('kind') == 'training' and not attrs.get('course'):
            raise serializers.ValidationError({'course': 'Sélectionnez une formation.'})
        if attrs.get('kind') != 'training' and attrs.get('course'):
            raise serializers.ValidationError({'course': 'Réservé aux demandes de formation.'})
        if attrs.get('kind') == 'quote' and not attrs.get('project_type', '').strip():
            raise serializers.ValidationError({'project_type': 'Précisez le type de projet.'})
        return attrs

class InquiryManagementSerializer(serializers.ModelSerializer):
    domain = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    course = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    class Meta:
        model = Inquiry
        exclude = ['payload_hash', 'idempotency_key']
        read_only_fields = [f.name for f in Inquiry._meta.fields if f.name not in ['status', 'internal_notes']]

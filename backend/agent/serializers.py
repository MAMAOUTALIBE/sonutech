from rest_framework import serializers
from .models import Lead, InquiryTriage, EmailDraft

class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = [f.name for f in Lead._meta.fields if f.name not in ['name', 'company', 'phone', 'stage', 'internal_notes']]

class TriageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InquiryTriage
        exclude = ['locked_at', 'failure_alerted']

class DraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailDraft
        exclude = ['approval_token_hash']
        read_only_fields = [f.name for f in EmailDraft._meta.fields if f.name not in ['subject', 'body']]

class DecisionSerializer(serializers.Serializer):
    subject = serializers.CharField(required=False, max_length=200)
    body = serializers.CharField(required=False, max_length=6000)

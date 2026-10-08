import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class AssistantConfiguration(models.Model):
    enabled = models.BooleanField('Activer le chatbot du site', default=False)
    daily_limit = models.PositiveIntegerField('Appels IA maximum par jour', default=100)
    rules = models.TextField('Consignes commerciales complémentaires', blank=True, max_length=6000)
    updated_at = models.DateTimeField(auto_now=True)
    enabled_at = models.DateTimeField(null=True, blank=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_success = models.BooleanField(default=False)
    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class DailyUsage(models.Model):
    day = models.DateField(unique=True)
    calls = models.PositiveIntegerField(default=0)


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    turns = models.PositiveSmallIntegerField(default=0)
    history = models.JSONField(default=list)
    lead = models.ForeignKey('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL)
    captured_at = models.DateTimeField(null=True, blank=True)
    capture_hash = models.CharField(max_length=64, blank=True)
    contact_id = models.UUIDField(null=True, blank=True)


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    message_id = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    reply = models.TextField()
    suggest_contact = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['conversation', 'message_id'], name='chat_message_idempotency')]


class OutreachDraft(models.Model):
    lead = models.ForeignKey('agent.Lead', on_delete=models.CASCADE, related_name='outreach_drafts')
    subject = models.CharField('Objet', max_length=200)
    body = models.TextField('Message', max_length=6000)
    analysis = models.TextField('Analyse du besoin', max_length=4000)
    status = models.CharField(max_length=12, default='pending', db_index=True, choices=[('pending', 'À valider'), ('sending', 'Envoi en cours'), ('sent', 'Envoyé'), ('rejected', 'Refusé'), ('failed', 'Envoi à vérifier')])
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_email = models.EmailField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    last_error = models.CharField(max_length=250, blank=True)
    class Meta:
        ordering = ['-created_at']
        permissions = [('approve_outreachdraft', 'Can approve and send an AI commercial draft')]


class InquiryProcessing(models.Model):
    inquiry = models.OneToOneField('inquiries.Inquiry', on_delete=models.CASCADE)
    draft = models.ForeignKey(OutreachDraft, null=True, blank=True, on_delete=models.SET_NULL)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=250, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

import uuid
from django.conf import settings
from django.db import models

TEMPERATURES = [('hot', 'Chaud'), ('warm', 'Tiède'), ('cold', 'Froid')]

class Lead(models.Model):
    # Shared prospect record for the CRM and inbound assistants.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=180, blank=True)
    source = models.CharField(max_length=30, blank=True, default='manual', choices=[('manual', 'Manuel'), ('website', 'Site web'), ('chatbot', 'Chatbot'), ('referral', 'Recommandation'), ('other', 'Autre')])
    tags = models.JSONField(default=list, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='crm_leads')
    phone = models.CharField(max_length=40, blank=True)
    stage = models.CharField(max_length=20, default='to_qualify', db_index=True, choices=[('to_qualify', 'À qualifier'), ('contacted', 'Contacté'), ('qualified', 'Qualifié'), ('proposal', 'Proposition envoyée'), ('won', 'Gagné'), ('not_retained', 'Non retenu')])
    temperature = models.CharField(max_length=10, blank=True, choices=TEMPERATURES)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    summary = models.TextField(blank=True)
    needs = models.JSONField(default=list)
    next_step = models.CharField(max_length=300, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-updated_at']

class InquiryTriage(models.Model):
    inquiry = models.OneToOneField('inquiries.Inquiry', primary_key=True, on_delete=models.CASCADE, related_name='triage')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='triages')
    state = models.CharField(max_length=12, default='pending', db_index=True, choices=[('pending', 'En attente'), ('processing', 'En cours'), ('done', 'Traitée'), ('failed', 'Échec')])
    attempts = models.PositiveIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)
    failure_alerted = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    spam_reason = models.CharField(max_length=300, blank=True)
    temperature = models.CharField(max_length=10, blank=True, choices=TEMPERATURES)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    summary = models.TextField(blank=True)
    needs = models.JSONField(default=list)
    next_step = models.CharField(max_length=300, blank=True)
    quote_outline = models.TextField(blank=True)
    escalated = models.BooleanField(default=False)
    escalation_reason = models.CharField(max_length=300, blank=True)
    model = models.CharField(max_length=60, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']

class EmailDraft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.ForeignKey('inquiries.Inquiry', on_delete=models.CASCADE, related_name='agent_drafts')
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name='drafts')
    # 0 is the first reply, 1..n the follow-ups.
    sequence = models.PositiveSmallIntegerField(default=0)
    subject = models.CharField(max_length=200)
    body = models.TextField(max_length=6000)
    status = models.CharField(max_length=20, db_index=True, choices=[('scheduled', 'Programmé'), ('pending_approval', 'À valider'), ('approved', 'Validé, envoi en cours'), ('sent', 'Envoyé'), ('rejected', 'Refusé'), ('cancelled', 'Annulé')])
    due_at = models.DateTimeField(db_index=True)
    approval_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    approval_expires_at = models.DateTimeField(null=True, blank=True)
    approval_requested_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    decided_via = models.CharField(max_length=12, blank=True, choices=[('auto', 'Automatique'), ('email_link', 'Lien de validation'), ('api', 'API de gestion')])
    decided_at = models.DateTimeField(null=True, blank=True)
    send_attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['due_at']
        constraints = [models.UniqueConstraint(fields=['inquiry', 'sequence'], name='unique_draft_sequence')]

class AgentState(models.Model):
    last_digest_on = models.DateField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)
    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

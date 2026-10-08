import uuid
from django.db import models

class Inquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.UUIDField(unique=True)
    payload_hash = models.CharField(max_length=64, editable=False)
    kind = models.CharField(max_length=15, choices=[('contact', 'Contact'), ('quote', 'Devis'), ('training', 'Formation')])
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=180, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    domain = models.ForeignKey('content.Service', null=True, blank=True, on_delete=models.SET_NULL)
    course = models.ForeignKey('content.Course', null=True, blank=True, on_delete=models.SET_NULL)
    message = models.TextField(max_length=10000)
    project_type = models.CharField(max_length=180, blank=True)
    budget = models.CharField(max_length=100, blank=True)
    deadline = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=50, default='website')
    status = models.CharField(max_length=20, default='new', choices=[('new', 'Nouvelle'), ('in_progress', 'En cours'), ('processed', 'Traitée'), ('archived', 'Archivée')], db_index=True)
    internal_notes = models.TextField(blank=True)
    notification_status = models.CharField(max_length=12, default='pending', choices=[('pending', 'En attente'), ('sent', 'Envoyée'), ('failed', 'Échec')])
    notification_attempts = models.PositiveIntegerField(default=0)
    notification_attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        permissions = [('export_inquiry', 'Can export inquiries'), ('retry_inquiry', 'Can retry inquiry notifications')]

class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)

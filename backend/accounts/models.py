from django.conf import settings
from django.db import models

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30)
    resource = models.CharField(max_length=100)
    object_id = models.CharField(max_length=80)
    changed_fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

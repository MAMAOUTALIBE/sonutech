import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import Inquiry
logger = logging.getLogger(__name__)

def notify_inquiry(pk):
    # Serialize retries and initial sends across all workers. SMTP delivery is at-least-once.
    with transaction.atomic():
        item = Inquiry.objects.select_for_update().get(pk=pk)
        if item.notification_status == 'sent':
            return True
        item.notification_attempts += 1
        item.notification_attempted_at = timezone.now()
        try:
            if not settings.INQUIRY_NOTIFICATION_EMAIL or not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST:
                raise ValueError('SMTP not configured')
            sent = send_mail('SONUTECH — Nouvelle demande', f'Une demande {item.kind} a été enregistrée.\nRéférence : {item.pk}\nConsultez l’API de gestion sécurisée pour la traiter.', settings.DEFAULT_FROM_EMAIL, [settings.INQUIRY_NOTIFICATION_EMAIL], fail_silently=False)
            if sent != 1:
                raise RuntimeError('Notification not accepted')
            item.notification_status = 'sent'
        except Exception:
            item.notification_status = 'failed'
            logger.warning('Inquiry notification failed id=%s', item.pk)
        item.save(update_fields=['notification_status', 'notification_attempts', 'notification_attempted_at'])
        return item.notification_status == 'sent'

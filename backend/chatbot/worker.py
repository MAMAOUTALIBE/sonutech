from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from agent.models import InquiryTriage
from crm.models import InquiryImport, Task
from inquiries.models import Inquiry
from .models import AssistantConfiguration, InquiryProcessing
from .provider import BudgetExceeded, ProviderUnavailable
from .secrets import read_key
from .service import find_or_create_lead, generate_draft


def process_inquiries(limit=10):
    """Qualify only new requests after explicit enablement. Never sends email."""
    config = AssistantConfiguration.load()
    if not config.enabled or not config.enabled_at or not read_key():
        return 0
    since = max(config.enabled_at, timezone.now() - timedelta(days=3))
    ids = list(Inquiry.objects.filter(created_at__gte=since, source__in=['website', 'chatbot']).exclude(status='archived').filter(Q(inquiryprocessing__isnull=True) | Q(inquiryprocessing__completed_at__isnull=True, inquiryprocessing__attempts__lt=3)).order_by('created_at').values_list('pk', flat=True)[:limit])
    completed = 0
    for pk in ids:
        with transaction.atomic():
            AssistantConfiguration.objects.select_for_update().get(pk=config.pk)
            inquiry = Inquiry.objects.select_for_update(skip_locked=True).filter(pk=pk).first()
            if inquiry is None:
                continue
            # Check again so disabling the assistant stops a running pass.
            if not AssistantConfiguration.load().enabled:
                break
            processing, _ = InquiryProcessing.objects.get_or_create(inquiry=inquiry)
            if processing.completed_at or processing.attempts >= 3:
                continue
            imported = InquiryImport.objects.filter(inquiry=inquiry).first()
            lead = imported.lead if imported else find_or_create_lead({'name': inquiry.name, 'email': inquiry.email, 'phone': inquiry.phone, 'company': inquiry.company})
            if imported is None:
                InquiryImport.objects.create(inquiry=inquiry, lead=lead)
                Task.objects.create(lead=lead, title=f'Revoir la demande de {inquiry.name[:150]}', due_date=timezone.localdate() + timedelta(days=1))
            InquiryTriage.objects.get_or_create(inquiry=inquiry, defaults={'lead': lead, 'state': 'done', 'processed_at': timezone.now(), 'summary': 'Demande prise en charge par l’assistant CRM, brouillon soumis à validation.'})
            lead = type(lead).objects.select_for_update().get(pk=lead.pk)
            processing.attempts += 1
            try:
                draft = lead.outreach_drafts.filter(status='pending').first() or generate_draft(lead)
            except BudgetExceeded as exc:
                # A daily quota is temporary, not a service failure. Keep the
                # request eligible when tomorrow’s budget becomes available.
                processing.attempts -= 1
                processing.last_error = str(exc)[:250]
                processing.save(update_fields=['attempts', 'last_error'])
                break
            except ProviderUnavailable as exc:
                processing.last_error = str(exc)[:250]
                processing.save(update_fields=['attempts', 'last_error'])
                # Avoid consuming the full budget retrying unavailable service.
                break
            processing.draft = draft
            processing.completed_at = timezone.now()
            processing.last_error = ''
            processing.save(update_fields=['attempts', 'draft', 'completed_at', 'last_error'])
            if inquiry.status == 'new':
                inquiry.status = 'in_progress'
                inquiry.save(update_fields=['status', 'updated_at'])
            completed += 1
    return completed

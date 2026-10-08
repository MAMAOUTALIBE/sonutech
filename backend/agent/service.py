import hashlib
import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone
from accounts.models import AuditLog
from inquiries.models import Inquiry
from . import llm
from .models import Lead, InquiryTriage, EmailDraft, AgentState

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=10)
STALE_LOCK = timedelta(minutes=15)
MAX_SEND_ATTEMPTS = 5
CLOSED_INQUIRY = ('processed', 'archived')

class DecisionError(Exception):
    pass

def audit(action, obj, fields=(), actor=None):
    AuditLog.objects.create(actor=actor, action=action, resource=obj._meta.label, object_id=str(obj.pk), changed_fields=sorted(fields))

def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

def owner_email():
    return settings.AGENT_OWNER_EMAIL or settings.INQUIRY_NOTIFICATION_EMAIL

def mail_ready():
    if not settings.DEFAULT_FROM_EMAIL or not owner_email():
        return False
    return settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend' or bool(settings.EMAIL_HOST)

def send(subject, body, to, reply_to=None):
    try:
        return EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to, reply_to=reply_to).send(fail_silently=False) == 1
    except Exception:
        logger.warning('Agent email not accepted by the mail server')
        return False

def notify_owner(subject, body):
    return mail_ready() and send(f'SONUTECH — {subject}', body, [owner_email()])

def draft_label(draft):
    return 'Réponse' if draft.sequence == 0 else f'Relance {draft.sequence}'

# Analysis

def history_for(inquiry):
    previous = Inquiry.objects.filter(email__iexact=inquiry.email).exclude(pk=inquiry.pk).order_by('-created_at')[:5]
    return [{'date': f'{p.created_at:%d/%m/%Y}', 'type': p.get_kind_display(), 'statut': p.get_status_display()} for p in previous]

def claim_inquiries(limit=5):
    now = timezone.now()
    fresh = Inquiry.objects.filter(status='new', triage__isnull=True, created_at__gte=now - timedelta(days=settings.AGENT_MAX_AGE_DAYS)).order_by('created_at').values_list('pk', flat=True)[:limit]
    for pk in fresh:
        InquiryTriage.objects.get_or_create(inquiry_id=pk)
    InquiryTriage.objects.filter(state='processing', locked_at__lt=now - STALE_LOCK, attempts__gte=MAX_ATTEMPTS).update(state='failed', last_error='Traitement interrompu.')
    claimed = []
    with transaction.atomic():
        due = InquiryTriage.objects.select_for_update(skip_locked=True).filter(
            Q(state='pending') | Q(state__in=['failed', 'processing'], attempts__lt=MAX_ATTEMPTS, locked_at__lt=now - RETRY_DELAY)
        ).exclude(state='processing', locked_at__gte=now - STALE_LOCK).order_by('created_at')[:limit]
        for triage in due:
            triage.state, triage.locked_at, triage.attempts = 'processing', now, triage.attempts + 1
            triage.save(update_fields=['state', 'locked_at', 'attempts'])
            claimed.append(triage.pk)
    return claimed

def process_triage(pk):
    triage = InquiryTriage.objects.select_related('inquiry__domain', 'inquiry__course').get(pk=pk)
    try:
        result = llm.analyze_inquiry(triage.inquiry, history_for(triage.inquiry))
        apply_analysis(triage, result)
    except Exception as exc:
        if not isinstance(exc, llm.AgentLLMError):
            logger.exception('Agent processing error inquiry=%s', pk)
        triage.state, triage.last_error = 'failed', (str(exc) if isinstance(exc, llm.AgentLLMError) else 'Erreur interne de l’assistant.')[:200]
        triage.save(update_fields=['state', 'last_error'])
        audit('agent_failed', triage)
        logger.warning('Agent analysis failed inquiry=%s attempt=%s', pk, triage.attempts)
        return False
    return True

@transaction.atomic
def apply_analysis(triage, result):
    a, inquiry, now = result.analysis, triage.inquiry, timezone.now()
    triage.is_spam, triage.spam_reason = a.is_spam, a.spam_reason[:300]
    triage.temperature, triage.score = a.temperature, max(0, min(100, a.score))
    triage.summary, triage.needs, triage.next_step = a.summary, [n[:200] for n in a.needs[:10]], a.next_step[:300]
    triage.quote_outline = a.quote_outline if inquiry.kind == 'quote' else ''
    triage.escalated, triage.escalation_reason = a.escalate and not a.is_spam, a.escalation_reason[:300]
    triage.model, triage.input_tokens, triage.output_tokens = result.model[:60], result.input_tokens, result.output_tokens
    triage.state, triage.processed_at, triage.last_error = 'done', now, ''
    if a.is_spam:
        triage.save()
        audit('agent_spam', triage)
        return
    lead, created = Lead.objects.select_for_update().get_or_create(email=inquiry.email.strip().lower(), defaults={'name': inquiry.name, 'company': inquiry.company, 'phone': inquiry.phone})
    lead.company, lead.phone = lead.company or inquiry.company, lead.phone or inquiry.phone
    lead.temperature, lead.score, lead.summary, lead.needs, lead.next_step = triage.temperature, triage.score, triage.summary, triage.needs, triage.next_step
    lead.save()
    triage.lead = lead
    triage.save()
    # The recipient is always the address typed in the form: the model never chooses it.
    emails = [(0, a.reply, now)] + [(i, text, now + timedelta(days=days)) for i, (days, text) in enumerate(zip(settings.AGENT_FOLLOWUP_DAYS, a.followups), start=1)]
    for sequence, text, due in emails:
        EmailDraft.objects.create(inquiry=inquiry, lead=lead, sequence=sequence, subject=text.subject.strip()[:200] or 'Votre demande à SONUTECH', body=text.body.strip()[:6000], status='scheduled', due_at=due)
    audit('agent_triage', triage, ['lead', 'temperature', 'score', 'escalated'] + (['lead_created'] if created else []))

# Sending policy

def can_auto_send(draft):
    triage = InquiryTriage.objects.filter(pk=draft.inquiry_id).first()
    if settings.AGENT_MODE == 'draft' or not triage or triage.escalated or triage.is_spam or not mail_ready():
        return False
    if settings.AGENT_MODE == 'semi' and draft.inquiry.kind == 'quote':
        return False
    recent = EmailDraft.objects.filter(decided_via='auto', decided_at__gte=timezone.now() - timedelta(hours=1)).count()
    return recent < settings.AGENT_MAX_AUTO_SENDS_PER_HOUR

def release_due_drafts(limit=20):
    now, released = timezone.now(), []
    with transaction.atomic():
        for draft in EmailDraft.objects.select_for_update(skip_locked=True).filter(status='scheduled', due_at__lte=now).order_by('due_at')[:limit]:
            if draft.sequence > 0:
                previous = EmailDraft.objects.filter(inquiry_id=draft.inquiry_id, sequence=draft.sequence - 1).first()
                if previous and previous.status not in ('sent', 'rejected', 'cancelled'):
                    continue
                stop = not previous or previous.status != 'sent' or (draft.lead and draft.lead.stage != 'to_qualify')
            else:
                stop = False
            if stop or draft.inquiry.status in CLOSED_INQUIRY:
                draft.status = 'cancelled'
                draft.save(update_fields=['status', 'updated_at'])
                audit('agent_cancel', draft)
                continue
            if can_auto_send(draft):
                draft.status, draft.decided_via, draft.decided_at = 'approved', 'auto', now
                audit('agent_auto_approve', draft)
            else:
                draft.status = 'pending_approval'
            draft.save()
            released.append(draft.pk)
    for pk in released:
        deliver(pk)
    return len(released)

# Approval

def approval_url(token):
    return settings.AGENT_PUBLIC_BASE_URL + reverse('agent-approval', args=[token])

def request_approval(draft):
    token, now = secrets.token_urlsafe(32), timezone.now()
    expires = now + timedelta(hours=settings.AGENT_APPROVAL_TTL_HOURS)
    inquiry, triage = draft.inquiry, InquiryTriage.objects.filter(pk=draft.inquiry_id).first()
    urgent = bool(triage and triage.escalated)
    lines = [
        f'Demande : {inquiry.get_kind_display()}' + (f' · {inquiry.domain.title}' if inquiry.domain else ''),
        f'Prospect : {inquiry.name}' + (f' ({inquiry.company})' if inquiry.company else ''),
    ]
    if triage and triage.temperature:
        lines.append(f'Intérêt estimé : {triage.get_temperature_display()} ({triage.score}/100)')
    if urgent:
        lines.append(f'Alerte : {triage.escalation_reason}')
    lines += ['', f'Consulter, modifier puis envoyer ou refuser : {approval_url(token)}', f'Ce lien personnel expire le {timezone.localtime(expires):%d/%m/%Y à %H:%M}. Ne le transférez pas.']
    subject = f'{"[PRIORITAIRE] " if urgent else ""}{draft_label(draft)} à valider — {inquiry.name}'
    if not notify_owner(subject, '\n'.join(lines)):
        return False
    draft.approval_token_hash, draft.approval_expires_at, draft.approval_requested_at = hash_token(token), expires, now
    draft.save(update_fields=['approval_token_hash', 'approval_expires_at', 'approval_requested_at', 'updated_at'])
    audit('agent_request_approval', draft)
    return True

def request_pending_approvals(limit=20):
    if not mail_ready():
        return 0
    with transaction.atomic():
        drafts = EmailDraft.objects.select_for_update(skip_locked=True).filter(status='pending_approval', approval_requested_at__isnull=True).order_by('due_at')[:limit]
        return sum(request_approval(d) for d in drafts)

def decide(draft, action, subject=None, body=None, via='email_link', user=None):
    # The caller holds a row lock on draft.
    if draft.status != 'pending_approval':
        raise DecisionError('Ce message a déjà été traité.')
    fields = ['status']
    if action == 'send':
        if subject and subject != draft.subject:
            draft.subject = subject
            fields.append('subject')
        if body and body != draft.body:
            draft.body = body
            fields.append('body')
        draft.status = 'approved'
    else:
        draft.status = 'rejected'
        EmailDraft.objects.filter(inquiry_id=draft.inquiry_id, sequence__gt=draft.sequence, status__in=['scheduled', 'pending_approval']).update(status='cancelled', approval_token_hash='', updated_at=timezone.now())
    draft.decided_via, draft.decided_by, draft.decided_at, draft.approval_token_hash = via, user, timezone.now(), ''
    draft.save()
    audit('agent_approve' if action == 'send' else 'agent_reject', draft, fields, actor=user)

# Delivery

def deliver(pk):
    with transaction.atomic():
        draft = EmailDraft.objects.select_for_update().select_related('inquiry').get(pk=pk)
        if draft.status != 'approved' or not mail_ready():
            return False
        draft.send_attempts += 1
        inquiry = draft.inquiry
        if not send(draft.subject, f'{draft.body.rstrip()}\n\n{settings.AGENT_SIGNATURE}', [inquiry.email], reply_to=[owner_email()]):
            draft.save(update_fields=['send_attempts', 'updated_at'])
            return False
        now = timezone.now()
        draft.status, draft.sent_at = 'sent', now
        draft.save(update_fields=['status', 'sent_at', 'send_attempts', 'updated_at'])
        Inquiry.objects.filter(pk=inquiry.pk, status='new').update(status='in_progress', updated_at=now)
        # Later follow-ups keep their configured gap from the email that actually left, even if it was approved late.
        delays = [0] + settings.AGENT_FOLLOWUP_DAYS
        for i in range(draft.sequence + 1, len(delays)):
            EmailDraft.objects.filter(inquiry_id=inquiry.pk, sequence=i, status='scheduled').update(due_at=now + timedelta(days=delays[i] - delays[draft.sequence]))
        audit('agent_send', draft)
    return True

def deliver_approved(limit=20):
    ids = list(EmailDraft.objects.filter(status='approved', send_attempts__lt=MAX_SEND_ATTEMPTS).values_list('pk', flat=True)[:limit])
    return sum(deliver(pk) for pk in ids)

# Owner reporting

def alert_failures():
    alerted = 0
    for triage in InquiryTriage.objects.select_related('inquiry').filter(state='failed', attempts__gte=MAX_ATTEMPTS, failure_alerted=False):
        inquiry = triage.inquiry
        if notify_owner(f'Demande à traiter vous-même — {inquiry.name}', f'L’assistant n’a pas pu analyser la demande de {inquiry.name} ({inquiry.get_kind_display()}, reçue le {timezone.localtime(inquiry.created_at):%d/%m/%Y à %H:%M}).\nRaison : {triage.last_error}\nRéférence : {inquiry.pk}\n\nLa demande est bien enregistrée. Consultez-la via l’API de gestion.'):
            InquiryTriage.objects.filter(pk=triage.pk).update(failure_alerted=True)
            alerted += 1
    return alerted

def digest_body(since):
    triages = InquiryTriage.objects.filter(processed_at__gte=since, state='done')
    counts = {t: triages.filter(is_spam=False, temperature=t).count() for t in ['hot', 'warm', 'cold']}
    spam = triages.filter(is_spam=True).count()
    sent = EmailDraft.objects.filter(sent_at__gte=since)
    pending = EmailDraft.objects.filter(status='pending_approval').select_related('inquiry').order_by('due_at')
    failed = InquiryTriage.objects.filter(state='failed', attempts__gte=MAX_ATTEMPTS, inquiry__status='new').select_related('inquiry')
    stuck = EmailDraft.objects.filter(status='approved', send_attempts__gte=MAX_SEND_ATTEMPTS).select_related('inquiry')
    tokens = triages.aggregate(i=Sum('input_tokens'), o=Sum('output_tokens'))
    if not (triages.exists() or sent.exists() or pending.exists() or failed.exists() or stuck.exists()):
        return None
    lines = [
        f'Demandes analysées en 24 h : {triages.count()} (chaudes {counts["hot"]}, tièdes {counts["warm"]}, froides {counts["cold"]}, spam {spam})',
        f'Emails envoyés en 24 h : {sent.count()}, dont {sent.filter(decided_via="auto").count()} automatiquement',
        f'Consommation IA : {tokens["i"] or 0} jetons en entrée, {tokens["o"] or 0} en sortie',
    ]
    sections = [
        ('En attente de votre validation (lien reçu par email)', [f'{d.inquiry.name} — {d.inquiry.get_kind_display()} — {draft_label(d)}' for d in pending]),
        ('Demandes à traiter vous-même', [f'{t.inquiry.name} — {t.inquiry.get_kind_display()} — {t.last_error}' for t in failed]),
        ('Envois en échec après plusieurs tentatives', [f'{d.inquiry.name} — {draft_label(d)}' for d in stuck]),
    ]
    for title, items in sections:
        if items:
            lines += ['', f'{title} :'] + [f'- {item}' for item in items[:30]]
    return '\n'.join(lines)

def send_digest_if_due():
    local = timezone.localtime()
    state = AgentState.load()
    if local.hour < settings.AGENT_DIGEST_HOUR or state.last_digest_on == local.date() or not mail_ready():
        return False
    body = digest_body(timezone.now() - timedelta(hours=24))
    if body and not notify_owner('Résumé quotidien de l’assistant', body):
        return False
    state.last_digest_on = local.date()
    state.save()
    return bool(body)

def run_pass():
    stats = {'analysées': 0}
    for pk in claim_inquiries():
        try:
            stats['analysées'] += process_triage(pk)
        except Exception:
            logger.exception('Agent processing error inquiry=%s', pk)
    steps = [('préparées', release_due_drafts), ('validations demandées', request_pending_approvals), ('envoyées', deliver_approved), ('alertes', alert_failures), ('résumé', send_digest_if_due)]
    for name, step in steps:
        try:
            stats[name] = int(step())
        except Exception:
            logger.exception('Agent step failed: %s', name)
    state = AgentState.load()
    state.heartbeat_at = timezone.now()
    state.save()
    return stats

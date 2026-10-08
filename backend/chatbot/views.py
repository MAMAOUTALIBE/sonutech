from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST
from agent.models import Lead
from crm.views import audit, page, private
from .forms import ChatbotSettingsForm, DraftForm
from .models import AssistantConfiguration, DailyUsage, OutreachDraft
from .provider import MODEL, ProviderUnavailable, complete
from .secrets import read_key, write_key
from .service import CHAT_SCHEMA, generate_draft


def smtp_ready():
    return bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL and settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend')


@sensitive_post_parameters('api_key')
@private
@require_http_methods(['GET', 'POST'])
def assistant_settings(request):
    if not request.user.has_perm('chatbot.change_assistantconfiguration'):
        return HttpResponseForbidden('Seul le responsable peut configurer cet assistant.')
    config = AssistantConfiguration.load()
    was_enabled = config.enabled
    form = ChatbotSettingsForm(instance=config, data=request.POST if request.method == 'POST' and request.POST.get('action', 'save') == 'save' else None)
    if request.method == 'POST':
        if request.POST.get('action') == 'test':
            try:
                result = complete([{'role': 'system', 'content': 'Réponds au format JSON demandé.'}, {'role': 'user', 'content': 'Test de connexion : réponds bonjour, suggest_contact=false.'}], CHAT_SCHEMA)
                config.last_test_success = isinstance(result.get('reply'), str) and isinstance(result.get('suggest_contact'), bool)
                if config.last_test_success:
                    messages.success(request, 'Connexion Groq vérifiée avec succès.')
                else:
                    messages.error(request, 'Le service IA a renvoyé une réponse invalide.')
            except ProviderUnavailable as exc:
                config.last_test_success = False
                messages.error(request, str(exc))
            config.last_test_at = timezone.now()
            config.save(update_fields=['last_test_at', 'last_test_success'])
            audit(request, config, 'ai_test', ['last_test_success'])
            return redirect('chatbot:assistant_settings')
        if form.is_valid():
            new_key = form.cleaned_data.get('api_key')
            if new_key:
                try:
                    write_key(new_key)
                except OSError:
                    form.add_error('api_key', 'Impossible d’enregistrer la clé. Contactez le responsable technique.')
                else:
                    config.last_test_success = False
            if not form.errors:
                if config.enabled and not was_enabled:
                    config.enabled_at = timezone.now()
                form.save()
                audit(request, config, 'ai_configure', [field for field in form.changed_data if field != 'api_key'] + (['key_updated'] if new_key else []))
                messages.success(request, 'Paramètres enregistrés. Aucun email ne part sans votre validation.')
                return redirect('chatbot:assistant_settings')
    usage = DailyUsage.objects.filter(day=timezone.localdate()).first()
    return render(request, 'crm/assistant.html', {'form': form, 'configured': bool(read_key()), 'model': MODEL, 'usage_today': usage.calls if usage else 0, 'last_test_success': config.last_test_success, 'configuration': config, 'active_nav': 'prospects'})


@private
@require_http_methods(['GET'])
def draft_list(request):
    selected = request.GET.get('filter', 'pending')
    drafts = OutreachDraft.objects.select_related('lead')
    if selected != 'all':
        drafts = drafts.filter(status=selected)
    return render(request, 'crm/drafts.html', {'page_obj': page(request, drafts), 'filter': selected, 'smtp_ready': smtp_ready(), 'can_approve': request.user.has_perm('chatbot.approve_outreachdraft'), 'active_nav': 'prospects'})


@private
@require_POST
def lead_generate(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    # Reuse the pending draft: a double click must not create multiple offers.
    with transaction.atomic():
        config = AssistantConfiguration.load()
        AssistantConfiguration.objects.select_for_update().get(pk=config.pk)
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        draft = lead.outreach_drafts.filter(status='pending').first()
        if draft is None:
            try:
                draft = generate_draft(lead)
            except ProviderUnavailable as exc:
                messages.error(request, str(exc))
                return redirect('crm:prospect_detail', pk=lead.pk)
            audit(request, draft, 'ai_draft', ['subject', 'body', 'analysis'])
    return redirect('chatbot:draft_detail', pk=draft.pk)


@private
@require_http_methods(['GET', 'POST'])
def draft_detail(request, pk):
    draft = get_object_or_404(OutreachDraft.objects.select_related('lead'), pk=pk)
    form = DraftForm(instance=draft, data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'send' and not request.user.has_perm('chatbot.approve_outreachdraft'):
            return HttpResponseForbidden('Seul le responsable peut valider l’envoi.')
        if action not in ['save', 'send', 'reject']:
            form.add_error(None, 'Action invalide.')
        else:
            with transaction.atomic():
                draft = OutreachDraft.objects.select_for_update().select_related('lead').get(pk=pk)
                form = DraftForm(instance=draft, data=request.POST)
                if draft.status != 'pending':
                    form.add_error(None, 'Ce brouillon a déjà été traité. Un envoi incertain doit être vérifié manuellement.')
                elif action == 'reject':
                    draft.status = 'rejected'
                    draft.decided_by = request.user
                    draft.save(update_fields=['status', 'decided_by'])
                    audit(request, draft, 'ai_reject', ['status'])
                    messages.success(request, 'Brouillon refusé. Aucun email envoyé.')
                    return redirect('chatbot:draft_list')
                elif form.is_valid():
                    if action == 'send' and (not smtp_ready() or not draft.lead.email):
                        form.add_error(None, 'Envoi impossible : configurez la messagerie et vérifiez l’email du prospect.')
                    else:
                        draft = form.save()
                        if action == 'save':
                            audit(request, draft, 'ai_edit', form.changed_data)
                            messages.success(request, 'Brouillon enregistré, en attente de votre validation.')
                            return redirect('chatbot:draft_detail', pk=pk)
                        draft.status = 'sending'
                        draft.decided_by = request.user
                        draft.recipient_email = draft.lead.email
                        draft.save(update_fields=['status', 'decided_by', 'recipient_email'])
                        audit(request, draft, 'ai_approve', ['status', 'recipient_email'])
            if action == 'send' and draft.status == 'sending' and not form.errors:
                try:
                    sent = send_mail(draft.subject, draft.body, settings.DEFAULT_FROM_EMAIL, [draft.recipient_email], fail_silently=False)
                    if sent != 1:
                        raise OSError('Unconfirmed delivery')
                except Exception:
                    # SMTP can fail after accepting a message. Never auto-retry.
                    OutreachDraft.objects.filter(pk=pk, status='sending').update(status='failed', last_error='Résultat de l’envoi incertain. Vérifiez la messagerie avant toute autre action.')
                    messages.error(request, 'L’envoi n’a pas été confirmé. Vérifiez votre messagerie ; aucun nouvel essai automatique ne sera effectué.')
                else:
                    OutreachDraft.objects.filter(pk=pk, status='sending').update(status='sent', sent_at=timezone.now(), last_error='')
                    messages.success(request, 'Email envoyé après votre validation.')
                return redirect('chatbot:draft_detail', pk=pk)
    return render(request, 'crm/draft_detail.html', {'form': form, 'draft': draft, 'smtp_ready': smtp_ready(), 'can_approve': request.user.has_perm('chatbot.approve_outreachdraft'), 'active_nav': 'prospects'})

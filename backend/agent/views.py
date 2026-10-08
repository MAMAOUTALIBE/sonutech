from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import ActionModelPermission
from content.views import AuditedManagement
from . import service
from .models import Lead, InquiryTriage, EmailDraft
from .serializers import LeadSerializer, TriageSerializer, DraftSerializer, DecisionSerializer

def page(request, context, status=200):
    response = render(request, 'agent/approval.html', {'signature': settings.AGENT_SIGNATURE, **context}, status=status)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response

# The unguessable single-use token in the URL is the credential: no session cookie is involved, so CSRF does not apply.
@csrf_exempt
@require_http_methods(['GET', 'POST'])
def approval(request, token):
    token_hash = service.hash_token(token)
    draft = EmailDraft.objects.select_related('inquiry__domain', 'inquiry__course').filter(approval_token_hash=token_hash, status='pending_approval').first()
    if not draft:
        return page(request, {'state': 'invalid'}, status=404)
    if draft.approval_expires_at and draft.approval_expires_at < timezone.now():
        return page(request, {'state': 'expired'}, status=410)
    context = {'state': 'form', 'inquiry': draft.inquiry, 'triage': InquiryTriage.objects.filter(pk=draft.inquiry_id).first(), 'label': service.draft_label(draft), 'subject': draft.subject, 'body': draft.body}
    if request.method == 'GET':
        return page(request, context)
    choice = request.POST.get('action')
    subject, body = request.POST.get('subject', '').strip(), request.POST.get('body', '').replace('\r\n', '\n').strip()
    if choice not in ('send', 'reject'):
        return page(request, {**context, 'error': 'Action inconnue.'}, status=400)
    if choice == 'send' and not (0 < len(subject) <= 200 and 0 < len(body) <= 6000):
        return page(request, {**context, 'subject': subject[:200], 'body': body[:6000], 'error': 'L’objet (200 caractères maximum) et le message (6 000 caractères maximum) sont obligatoires.'}, status=400)
    with transaction.atomic():
        locked = EmailDraft.objects.select_for_update().get(pk=draft.pk)
        if locked.approval_token_hash != token_hash:
            return page(request, {'state': 'invalid'}, status=404)
        service.decide(locked, choice, subject, body, via='email_link')
    sent = choice == 'send' and service.deliver(draft.pk)
    return page(request, {'state': 'done', 'action': choice, 'sent': sent, 'inquiry': draft.inquiry})

class ManageLeads(AuditedManagement):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    http_method_names = ['get', 'patch', 'put', 'head', 'options']
    def get_queryset(self):
        qs = super().get_queryset()
        for field in ['stage', 'temperature']:
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        search = self.request.query_params.get('search', '')[:200]
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(company__icontains=search))
        return qs

class ManageTriages(viewsets.ReadOnlyModelViewSet):
    queryset = InquiryTriage.objects.all()
    serializer_class = TriageSerializer
    permission_classes = [ActionModelPermission]
    def get_queryset(self):
        qs = super().get_queryset()
        for field in ['state', 'temperature']:
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        if self.request.query_params.get('escalated') in ('true', 'false'):
            qs = qs.filter(escalated=self.request.query_params['escalated'] == 'true')
        return qs

class ManageDrafts(AuditedManagement):
    queryset = EmailDraft.objects.all()
    serializer_class = DraftSerializer
    http_method_names = ['get', 'patch', 'put', 'post', 'head', 'options']
    def get_queryset(self):
        qs = super().get_queryset()
        for field in ['status', 'inquiry']:
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        return qs
    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Les brouillons sont rédigés par l’assistant.'}, status=405)
    def perform_update(self, serializer):
        if serializer.instance.status not in ('scheduled', 'pending_approval'):
            raise serializers.ValidationError({'status': 'Ce message ne peut plus être modifié.'})
        super().perform_update(serializer)
    def decide(self, request, choice):
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        pk = self.get_object().pk
        with transaction.atomic():
            draft = EmailDraft.objects.select_for_update().get(pk=pk)
            try:
                service.decide(draft, choice, data.validated_data.get('subject'), data.validated_data.get('body'), via='api', user=request.user)
            except service.DecisionError as exc:
                return Response({'detail': str(exc)}, status=409)
        sent = choice == 'send' and service.deliver(pk)
        return Response({'status': 'sent' if sent else draft.status})
    @extend_schema(request=DecisionSerializer, responses=inline_serializer(name='DraftDecision', fields={'status': serializers.CharField()}))
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self.decide(request, 'send')
    @extend_schema(request=None, responses=inline_serializer(name='DraftRejection', fields={'status': serializers.CharField()}))
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self.decide(request, 'reject')

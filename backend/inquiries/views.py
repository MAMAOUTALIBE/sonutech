import csv
import hashlib
import io
import json
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Q
from rest_framework import mixins, viewsets, serializers
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiTypes
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from content.views import AuditedManagement
from .models import Inquiry
from .serializers import SubmissionSerializer, InquiryManagementSerializer
from .throttles import DatabaseThrottle
from .notifications import notify_inquiry

class SubmitInquiry(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = SubmissionSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [DatabaseThrottle]
    @extend_schema(responses={201: inline_serializer(name='SubmissionReceipt', fields={'id': serializers.UUIDField(), 'status': serializers.CharField()}), 200: inline_serializer(name='DuplicateReceipt', fields={'id': serializers.UUIDField(), 'status': serializers.CharField()})})
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        key = values.pop('idempotency_key')
        # Canonicalize defaults so omitted optional strings and empty strings are equivalent.
        canonical = {name: values.get(name, None if name in ['domain', 'course'] else '') for name in ['kind', 'name', 'company', 'email', 'phone', 'domain', 'message', 'project_type', 'budget', 'deadline', 'course']}
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, default=lambda x: str(x.pk), ensure_ascii=False).encode()).hexdigest()
        with transaction.atomic():
            item, created = Inquiry.objects.get_or_create(idempotency_key=key, defaults={**values, 'payload_hash': fingerprint})
            if item.payload_hash != fingerprint:
                return Response({'detail': 'Cette clé a déjà été utilisée pour une autre demande.'}, status=409)
            if created:
                transaction.on_commit(lambda: notify_inquiry(item.pk))
        return Response({'id': str(item.pk), 'status': 'received'}, status=201 if created else 200)

class ManageInquiries(AuditedManagement):
    queryset = Inquiry.objects.select_related('domain', 'course').all()
    serializer_class = InquiryManagementSerializer
    http_method_names = ['get', 'patch', 'put', 'post', 'head', 'options']
    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Utilisez le formulaire public pour déposer une demande.'}, status=405)
    def get_queryset(self):
        qs = super().get_queryset()
        for field in ['status', 'kind']:
            if self.request.query_params.get(field):
                qs = qs.filter(**{field: self.request.query_params[field]})
        if self.request.query_params.get('domain'):
            qs = qs.filter(domain__slug=self.request.query_params['domain'])
        search = self.request.query_params.get('search', '')[:200]
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(company__icontains=search) | Q(message__icontains=search))
        return qs
    @extend_schema(responses={(200, 'text/csv'): OpenApiTypes.BINARY})
    @action(detail=False, methods=['get'])
    def export(self, request):
        def safe(value):
            s = str(value or '')
            return "'" + s if s.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) or s.startswith(('\t','\r','\n')) else s
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'nom', 'entreprise', 'email', 'téléphone', 'domaine', 'statut', 'création'])
        for item in self.get_queryset().iterator():
            writer.writerow([safe(v) for v in [item.pk, item.kind, item.name, item.company, item.email, item.phone, item.domain.slug if item.domain else '', item.status, item.created_at.isoformat()]])
        from accounts.models import AuditLog
        AuditLog.objects.create(actor=request.user, action='export', resource='inquiries.Inquiry', object_id='filtered')
        response = HttpResponse('\ufeff' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="demandes-sonutech.csv"'
        response['Cache-Control'] = 'no-store'
        return response
    @extend_schema(request=None, responses=inline_serializer(name='NotificationResult', fields={'notification_status': serializers.CharField()}))
    @action(detail=True, methods=['post'], url_path='retry-notification')
    def retry_notification(self, request, pk=None):
        item = self.get_object()
        ok = notify_inquiry(item.pk)
        self.audit(item, 'retry_notification')
        return Response({'notification_status': 'sent' if ok else 'failed'})

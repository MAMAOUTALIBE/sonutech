from decimal import Decimal
from datetime import date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.utils.decorators import method_decorator
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import AuditLog
from agent.models import Lead
from chatbot.forms import ChatbotSettingsForm
from chatbot.models import AssistantConfiguration, DailyUsage, OutreachDraft
from chatbot.provider import MODEL
from chatbot.provider import ProviderUnavailable, complete
from chatbot.secrets import read_key, write_key
from chatbot.service import CHAT_SCHEMA, generate_draft
from chatbot.views import smtp_ready
from content.models import Service
from inquiries.models import Inquiry
from .api_serializers import AppointmentSerializer, ClientSerializer, DocumentSerializer, EmailSerializer, InvoiceSerializer, LeadSerializer, OpportunitySerializer, ProjectSerializer, QuoteSerializer, SettingsSerializer, TaskSerializer, UserSerializer
from .models import InquiryImport, SERVICE_CATEGORIES, Appointment, Client, CRMSettings, Document, Invoice, Opportunity, Project, Quote, Task


def manager(user):
    return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name='manager').exists())


def member(user):
    return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name__in=['viewer', 'sales', 'manager']).exists())


def writer(user):
    return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name__in=['sales', 'manager']).exists())


class CRMAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return member(request.user) and (request.method in permissions.SAFE_METHODS or writer(request.user))


class ManagerAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return manager(request.user)


class AssistantAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return member(request.user) and request.user.has_perm('chatbot.change_assistantconfiguration')


class CRMPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def audit(request, obj, action_name, fields=()):
    AuditLog.objects.create(actor=request.user, action=action_name, resource=obj._meta.label_lower, object_id=str(obj.pk), changed_fields=sorted(field for field in fields if field not in ['password', 'api_key']))


class Resource(viewsets.ModelViewSet):
    permission_classes = [CRMAccess]
    pagination_class = CRMPagination
    search_fields = []
    filter_fields = []
    def get_queryset(self):
        queryset = self.queryset.all()
        q = self.request.query_params.get('q', '').strip()
        if len(q) > 200:
            raise serializers.ValidationError({'q': 'Recherche limitée à 200 caractères.'})
        if q and self.search_fields:
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{field + '__icontains': q})
            queryset = queryset.filter(condition)
        for field in self.filter_fields:
            value = self.request.query_params.get(field)
            if value not in [None, '']:
                model_field = queryset.model._meta.get_field(field)
                try:
                    if model_field.get_internal_type() == 'BooleanField':
                        if value not in ['true', 'false', '1', '0']:
                            raise ValueError()
                        value = value in ['true', '1']
                    elif model_field.is_relation:
                        value = model_field.target_field.to_python(value)
                    elif model_field.choices and value not in dict(model_field.choices):
                        raise ValueError()
                    else:
                        value = model_field.to_python(value)
                except (DjangoValidationError, ValueError, TypeError):
                    raise serializers.ValidationError({field: 'Filtre invalide.'}) from None
                queryset = queryset.filter(**{field: value})
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            queryset = queryset.select_for_update(of=('self',))
        return queryset
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        audit(self.request, obj, 'crm_create', serializer.validated_data.keys())
    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        audit(self.request, obj, 'crm_update', serializer.validated_data.keys())
    @transaction.atomic
    def perform_destroy(self, instance):
        if isinstance(instance, (Quote, Invoice)) and instance.status != 'draft':
            raise serializers.ValidationError('Seuls les documents financiers en brouillon peuvent être supprimés.')
        if isinstance(instance, OutreachDraft) and instance.status != 'pending':
            raise serializers.ValidationError('Un email déjà traité ne peut pas être supprimé.')
        try:
            audit(self.request, instance, 'crm_delete')
            document_file = instance.file if isinstance(instance, Document) else None
            instance.delete()
            if document_file:
                transaction.on_commit(lambda: document_file.delete(save=False))
        except ProtectedError:
            raise serializers.ValidationError('Cet élément est utilisé par un autre dossier. Retirez les liens ou archivez-le.') from None


class Prospects(Resource):
    queryset = Lead.objects.select_related('owner')
    serializer_class = LeadSerializer
    search_fields = ['name', 'company', 'email', 'phone']
    filter_fields = ['stage', 'source', 'owner']
    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        with transaction.atomic():
            lead = Lead.objects.select_for_update().get(pk=self.get_object().pk)
            client, created = Client.objects.get_or_create(lead=lead, defaults={'name': lead.name, 'company': lead.company, 'email': lead.email or '', 'phone': lead.phone})
            if created:
                audit(request, client, 'crm_convert', ['lead'])
        return Response(ClientSerializer(client).data, status=201 if created else 200)
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        lead = self.get_object()
        with transaction.atomic():
            config = AssistantConfiguration.load()
            AssistantConfiguration.objects.select_for_update().get(pk=config.pk)
            lead = Lead.objects.select_for_update().get(pk=lead.pk)
            draft = lead.outreach_drafts.filter(status='pending').first()
            if not draft:
                try:
                    draft = generate_draft(lead)
                except ProviderUnavailable as exc:
                    return Response({'detail': str(exc)}, status=503)
                audit(request, draft, 'ai_draft', ['subject', 'body'])
        return Response(EmailSerializer(draft).data, status=201)


class Clients(Resource):
    queryset = Client.objects.select_related('lead')
    serializer_class = ClientSerializer
    search_fields = ['name', 'company', 'email', 'phone']
    filter_fields = ['status']


class Opportunities(Resource):
    queryset = Opportunity.objects.select_related('lead', 'client', 'owner')
    serializer_class = OpportunitySerializer
    search_fields = ['title', 'lead__name', 'client__name']
    filter_fields = ['stage', 'lead', 'client', 'owner', 'service']


class Projects(Resource):
    queryset = Project.objects.select_related('client', 'opportunity')
    serializer_class = ProjectSerializer
    search_fields = ['name', 'client__name', 'description']
    filter_fields = ['status', 'client', 'service']


class Quotes(Resource):
    queryset = Quote.objects.select_related('client', 'project')
    serializer_class = QuoteSerializer
    search_fields = ['number', 'client__name']
    filter_fields = ['status', 'client', 'project']


class Invoices(Resource):
    queryset = Invoice.objects.select_related('client', 'project')
    serializer_class = InvoiceSerializer
    search_fields = ['number', 'client__name']
    filter_fields = ['status', 'client', 'project']


class Appointments(Resource):
    queryset = Appointment.objects.select_related('lead')
    serializer_class = AppointmentSerializer
    search_fields = ['title', 'location', 'lead__name']
    filter_fields = ['status', 'lead']
    def get_queryset(self):
        queryset = super().get_queryset()
        bounds = {}
        for key in ['date_from', 'date_to']:
            value = self.request.query_params.get(key)
            if value:
                try:
                    bounds[key] = date.fromisoformat(value)
                except ValueError:
                    raise serializers.ValidationError({key: 'Indiquez une date au format AAAA-MM-JJ.'}) from None
        if bounds.get('date_from') and bounds.get('date_to') and bounds['date_from'] > bounds['date_to']:
            raise serializers.ValidationError({'date_to': 'La fin doit être après le début.'})
        if 'date_from' in bounds:
            queryset = queryset.filter(end__date__gte=bounds['date_from'])
        if 'date_to' in bounds:
            queryset = queryset.filter(start__date__lte=bounds['date_to'])
        return queryset


class Tasks(Resource):
    queryset = Task.objects.select_related('lead', 'owner')
    serializer_class = TaskSerializer
    search_fields = ['title', 'lead__name']
    filter_fields = ['done', 'priority', 'lead', 'owner']


class Documents(Resource):
    queryset = Document.objects.select_related('client', 'project', 'lead')
    serializer_class = DocumentSerializer
    search_fields = ['title', 'original_name']
    filter_fields = ['category', 'client', 'project', 'lead']
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document = self.get_object()
        try:
            stream = document.file.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'Fichier indisponible.'}, status=404)
        response = FileResponse(stream, as_attachment=True, filename=document.original_name)
        response['Content-Type'] = 'application/octet-stream'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = 'no-store'
        return response


class Emails(Resource):
    queryset = OutreachDraft.objects.select_related('lead')
    serializer_class = EmailSerializer
    search_fields = ['subject', 'lead__name', 'body']
    filter_fields = ['status', 'lead']
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        with transaction.atomic():
            draft = OutreachDraft.objects.select_for_update().get(pk=self.get_object().pk)
            if draft.status != 'pending':
                return Response({'detail': 'Ce brouillon a déjà été traité.'}, status=409)
            draft.status, draft.decided_by = 'rejected', request.user
            draft.save(update_fields=['status', 'decided_by'])
            audit(request, draft, 'ai_reject', ['status'])
        return Response(self.get_serializer(draft).data)
    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        if not request.user.has_perm('chatbot.approve_outreachdraft'):
            return Response({'detail': 'Seul le responsable autorisé peut valider l’envoi.'}, status=403)
        with transaction.atomic():
            draft = OutreachDraft.objects.select_for_update().get(pk=self.get_object().pk)
            if draft.status != 'pending':
                return Response({'detail': 'Cet email a déjà été traité. Aucun nouvel envoi.'}, status=409)
            if not smtp_ready() or not draft.lead.email:
                return Response({'detail': 'Configurez la messagerie et vérifiez l’email du prospect avant l’envoi.'}, status=400)
            draft.status, draft.decided_by, draft.recipient_email = 'sending', request.user, draft.lead.email
            draft.save(update_fields=['status', 'decided_by', 'recipient_email'])
            audit(request, draft, 'ai_approve', ['status', 'recipient_email'])
        try:
            if send_mail(draft.subject, draft.body, settings.DEFAULT_FROM_EMAIL, [draft.recipient_email], fail_silently=False) != 1:
                raise OSError()
        except Exception:
            OutreachDraft.objects.filter(pk=draft.pk).update(status='failed', last_error='Envoi non confirmé. Vérifiez la messagerie avant toute autre action.')
            return Response({'detail': 'Envoi non confirmé ; aucun nouvel essai automatique.'}, status=502)
        OutreachDraft.objects.filter(pk=draft.pk).update(status='sent', sent_at=timezone.now())
        draft.refresh_from_db()
        return Response(self.get_serializer(draft).data)


class Users(Resource):
    permission_classes = [ManagerAccess]
    queryset = get_user_model().objects.all().order_by('username')
    serializer_class = UserSerializer
    search_fields = ['username', 'email', 'first_name', 'last_name']
    http_method_names = ['get', 'post', 'patch', 'put', 'head', 'options']


class SettingsView(APIView):
    permission_classes = [ManagerAccess]
    def get(self, request):
        return Response(SettingsSerializer(CRMSettings.objects.get_or_create(pk=1)[0]).data)
    @transaction.atomic
    def patch(self, request):
        serializer = SettingsSerializer(CRMSettings.objects.get_or_create(pk=1)[0], data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit(request, obj, 'crm_settings', serializer.validated_data.keys())
        return Response(serializer.data)


@method_decorator(sensitive_post_parameters('api_key'), name='dispatch')
class AssistantView(APIView):
    permission_classes = [AssistantAccess]
    def get(self, request):
        config = AssistantConfiguration.load()
        usage = DailyUsage.objects.filter(day=timezone.localdate()).first()
        return Response({'enabled': config.enabled, 'daily_limit': config.daily_limit, 'rules': config.rules, 'configured': bool(read_key()), 'model': MODEL, 'usage_today': usage.calls if usage else 0, 'last_test_success': config.last_test_success, 'smtp_ready': smtp_ready()})
    @sensitive_variables()
    def patch(self, request):
        config = AssistantConfiguration.load()
        enabled_before = config.enabled
        values = {'enabled': config.enabled, 'daily_limit': config.daily_limit, 'rules': config.rules, **request.data}
        form = ChatbotSettingsForm(values, instance=config)
        if not form.is_valid():
            return Response({'errors': dict(form.errors)}, status=400)
        key = form.cleaned_data.get('api_key')
        if key:
            try:
                write_key(key)
            except OSError:
                return Response({'detail': 'La clé ne peut pas être enregistrée.'}, status=503)
            config.last_test_success = False
        if config.enabled and not enabled_before:
            config.enabled_at = timezone.now()
        form.save()
        audit(request, config, 'ai_configure', ['settings'] + (['key_updated'] if key else []))
        return self.get(request)


class AssistantTest(APIView):
    permission_classes = [AssistantAccess]
    def post(self, request):
        config = AssistantConfiguration.load()
        try:
            result = complete([{'role': 'user', 'content': 'Test : réponds bonjour dans reply, suggest_contact=false.'}], CHAT_SCHEMA)
            success = isinstance(result.get('reply'), str) and isinstance(result.get('suggest_contact'), bool)
        except ProviderUnavailable:
            success = False
        config.last_test_at, config.last_test_success = timezone.now(), success
        config.save(update_fields=['last_test_at', 'last_test_success'])
        audit(request, config, 'ai_test', ['last_test_success'])
        return Response({'success': success, 'detail': 'Connexion Groq vérifiée.' if success else 'Connexion indisponible. Vérifiez la clé et le quota.'}, status=200 if success else 503)


class Bootstrap(APIView):
    permission_classes = [CRMAccess]
    def get(self, request):
        user = request.user
        choices = {}
        for resource, model in [('prospects', Lead), ('clients', Client), ('opportunities', Opportunity), ('projects', Project), ('quotes', Quote), ('invoices', Invoice), ('appointments', Appointment), ('tasks', Task), ('documents', Document), ('emails', OutreachDraft)]:
            for field in model._meta.fields:
                if field.choices:
                    choices[f'{resource}.{field.name}'] = [{'value': value, 'label': label} for value, label in field.choices]
        pipeline = []
        for value, label in Opportunity._meta.get_field('stage').choices:
            subset = Opportunity.objects.filter(stage=value)
            pipeline.append({'stage': value, 'label': label, 'count': subset.count(), 'amount': str(subset.aggregate(value=Sum('amount'))['value'] or Decimal('0'))})
        total_leads = Lead.objects.count()
        won = Lead.objects.filter(stage='won').count()
        kpis = {'prospects': total_leads, 'clients': Client.objects.count(), 'opportunities': Opportunity.objects.exclude(stage__in=['won', 'lost']).count(), 'projects': Project.objects.filter(status='in_progress').count(), 'revenue': str(Invoice.objects.filter(status='paid').aggregate(value=Sum('total_ht'))['value'] or Decimal('0')), 'pipeline_amount': str(Opportunity.objects.exclude(stage__in=['won', 'lost']).aggregate(value=Sum('amount'))['value'] or Decimal('0')), 'conversion_rate': round(won * 100 / total_leads, 1) if total_leads else 0, 'tasks_due': Task.objects.filter(done=False, due_date__lte=timezone.localdate()).count()}
        def options(queryset, label):
            return [{'id': str(obj.pk) if isinstance(obj, Lead) else obj.pk, 'label': label(obj)} for obj in queryset[:500]]
        lookups = {'leads': options(Lead.objects.all(), lambda x: x.name), 'clients': options(Client.objects.all(), lambda x: x.name), 'projects': options(Project.objects.all(), lambda x: x.name), 'opportunities': options(Opportunity.objects.all(), lambda x: x.title), 'users': options(get_user_model().objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(groups__name__in=['sales', 'manager'])).distinct(), lambda x: x.get_full_name() or x.username)}
        services = list(Opportunity.objects.values('service').annotate(value=Count('pk')).order_by('-value'))
        return Response({'user': {'id': user.pk, 'username': user.username, 'name': user.get_full_name() or user.username, 'roles': list(user.groups.values_list('name', flat=True)), 'permissions': sorted(user.get_all_permissions()), 'can_write': writer(user), 'can_manage': manager(user), 'can_approve': user.has_perm('chatbot.approve_outreachdraft'), 'can_configure_ai': user.has_perm('chatbot.change_assistantconfiguration')}, 'metadata': choices, 'kpis': kpis, 'dashboard': {'pipeline': pipeline, 'services': [{'name': dict(SERVICE_CATEGORIES).get(item['service'], item['service']), 'value': item['value']} for item in services], 'recent_projects': ProjectSerializer(Project.objects.select_related('client', 'opportunity')[:5], many=True).data}, 'lookups': lookups})


class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = ['id', 'name', 'company', 'email', 'phone', 'message', 'kind', 'source', 'status', 'created_at']
        read_only_fields = fields


class Inquiries(Resource):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer
    search_fields = ['name', 'company', 'email', 'message']
    filter_fields = ['status']
    http_method_names = ['get', 'post', 'head', 'options']
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('pending', 'true') == 'true' and self.action == 'list':
            queryset = queryset.filter(inquiryimport__isnull=True, triage__lead__isnull=True).exclude(status='archived')
        return queryset
    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Utilisez le formulaire public pour les nouvelles demandes.'}, status=405)
    @action(detail=True, methods=['post'], url_path='import')
    def import_inquiry(self, request, pk=None):
        with transaction.atomic():
            configuration = AssistantConfiguration.load()
            AssistantConfiguration.objects.select_for_update().get(pk=configuration.pk)
            inquiry = Inquiry.objects.select_for_update().get(pk=self.get_object().pk)
            imported = InquiryImport.objects.filter(inquiry=inquiry).first()
            if imported:
                lead = imported.lead
            else:
                from chatbot.service import find_or_create_lead
                lead = find_or_create_lead({'name': inquiry.name, 'company': inquiry.company, 'email': inquiry.email, 'phone': inquiry.phone})
                InquiryImport.objects.create(inquiry=inquiry, lead=lead)
                inquiry.status = 'in_progress'
                inquiry.save(update_fields=['status', 'updated_at'])
                audit(request, lead, 'crm_import', ['inquiry'])
        return Response(LeadSerializer(lead).data)

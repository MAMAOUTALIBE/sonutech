from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from agent.models import Lead
from chatbot.models import OutreachDraft
from .models import Appointment, Client, CRMSettings, Document, Invoice, Note, NumberSequence, Opportunity, Project, Quote, Task


class RelatedLabels(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field in ['lead', 'client', 'project', 'owner', 'opportunity']:
            if hasattr(instance, field):
                obj = getattr(instance, field)
                data[field + '_name'] = (getattr(obj, 'name', None) or getattr(obj, 'title', None) or obj.get_full_name() or obj.username) if obj else ''
        for field in ['status', 'stage', 'priority', 'source']:
            method = getattr(instance, f'get_{field}_display', None)
            if method:
                data[field + '_label'] = method()
        return data
    def validate(self, attrs):
        client = attrs.get('client', getattr(self.instance, 'client', None))
        project = attrs.get('project', getattr(self.instance, 'project', None))
        if project and client and project.client_id != client.pk:
            raise serializers.ValidationError({'project': 'Ce projet appartient à un autre client.'})
        owner = attrs.get('owner')
        if owner and (not owner.is_active or not (owner.is_superuser or owner.groups.filter(name__in=['sales', 'manager']).exists())):
            raise serializers.ValidationError({'owner': 'Choisissez un membre actif de l’équipe commerciale.'})
        return attrs


class LeadSerializer(RelatedLabels):
    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ['score', 'summary', 'needs', 'temperature', 'created_at', 'updated_at']
    def validate_tags(self, value):
        if not isinstance(value, list) or len(value) > 20 or any(not isinstance(tag, str) or len(tag) > 40 for tag in value):
            raise serializers.ValidationError('Indiquez au maximum 20 étiquettes de 40 caractères.')
        return value
    def validate_email(self, value):
        value = (value or '').strip().lower() or None
        if value and Lead.objects.filter(email__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('Cet email appartient déjà à un prospect.')
        return value
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get('email', getattr(self.instance, 'email', None)) and not attrs.get('phone', getattr(self.instance, 'phone', '')):
            raise serializers.ValidationError('Un email ou un téléphone est nécessaire.')
        return attrs


class ClientSerializer(RelatedLabels):
    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['created_at']


class OpportunitySerializer(RelatedLabels):
    class Meta:
        model = Opportunity
        fields = '__all__'
        read_only_fields = ['created_at']
        extra_kwargs = {'amount': {'min_value': Decimal('0')}, 'probability': {'min_value': 0, 'max_value': 100}}
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get('lead', getattr(self.instance, 'lead', None)) and not attrs.get('client', getattr(self.instance, 'client', None)):
            raise serializers.ValidationError('Rattachez l’opportunité à un prospect ou un client.')
        return attrs


class ProjectSerializer(RelatedLabels):
    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['created_at']
        extra_kwargs = {'budget': {'min_value': Decimal('0')}, 'cost': {'min_value': Decimal('0')}, 'progress': {'min_value': 0, 'max_value': 100}}
    def validate(self, attrs):
        attrs = super().validate(attrs)
        start, end = attrs.get('start_date', getattr(self.instance, 'start_date', None)), attrs.get('due_date', getattr(self.instance, 'due_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'due_date': 'La fin doit être après le début.'})
        client = attrs.get('client', getattr(self.instance, 'client', None))
        opportunity = attrs.get('opportunity', getattr(self.instance, 'opportunity', None))
        if opportunity and opportunity.client_id and client and opportunity.client_id != client.pk:
            raise serializers.ValidationError({'opportunity': 'Cette opportunité appartient à un autre client.'})
        return attrs


class LineSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=500)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), default=Decimal('20'))


class FinancialSerializer(RelatedLabels):
    items = LineSerializer(many=True)
    def validate_items(self, items):
        if not 1 <= len(items) <= 100:
            raise serializers.ValidationError('Indiquez entre 1 et 100 lignes.')
        return items
    def validate(self, attrs):
        attrs = super().validate(attrs)
        issue, due = attrs.get('issue_date', getattr(self.instance, 'issue_date', None)), attrs.get('due_date', getattr(self.instance, 'due_date', None))
        if issue and due and due < issue:
            raise serializers.ValidationError({'due_date': 'L’échéance ne peut pas précéder la date d’émission.'})
        if self.instance and isinstance(self.instance, Invoice) and self.instance.status != 'draft':
            if any(field not in ['status', 'notes'] for field in attrs):
                raise serializers.ValidationError('Les montants et le client d’une facture émise ne sont plus modifiables.')
            if attrs.get('status') == 'draft':
                raise serializers.ValidationError({'status': 'Une facture émise ne peut pas redevenir brouillon.'})
        if 'items' in attrs:
            ht = tax = Decimal('0.00')
            normalized = []
            for item in attrs['items']:
                line_ht = (item['quantity'] * item['unit_price']).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                line_tax = (line_ht * item['tax_rate'] / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                ht += line_ht
                tax += line_tax
                normalized.append({key: str(value) if isinstance(value, Decimal) else value for key, value in item.items()})
            if ht + tax >= Decimal('1000000000000'):
                raise serializers.ValidationError({'items': 'Le total dépasse le montant autorisé.'})
            attrs.update(items=normalized, total_ht=ht, total_tax=tax, total_ttc=ht + tax)
        return attrs
    @transaction.atomic
    def create(self, validated_data):
        prefix = 'DEV' if self.Meta.model is Quote else 'FAC'
        year = validated_data['issue_date'].year
        sequence, _ = NumberSequence.objects.get_or_create(key=f'{prefix}-{year}')
        sequence = NumberSequence.objects.select_for_update().get(pk=sequence.pk)
        sequence.value += 1
        sequence.save(update_fields=['value'])
        validated_data['number'] = f'{prefix}-{year}-{sequence.value:05d}'
        return super().create(validated_data)


class QuoteSerializer(FinancialSerializer):
    class Meta:
        model = Quote
        fields = '__all__'
        read_only_fields = ['number', 'total_ht', 'total_tax', 'total_ttc', 'created_at']


class InvoiceSerializer(FinancialSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['number', 'total_ht', 'total_tax', 'total_ttc', 'created_at']


class AppointmentSerializer(RelatedLabels):
    class Meta:
        model = Appointment
        fields = '__all__'
    def validate(self, attrs):
        attrs = super().validate(attrs)
        start, end = attrs.get('start', getattr(self.instance, 'start', None)), attrs.get('end', getattr(self.instance, 'end', None))
        if start and end and end <= start:
            raise serializers.ValidationError({'end': 'La fin doit être après le début.'})
        return attrs


class TaskSerializer(RelatedLabels):
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_at']


class DocumentSerializer(RelatedLabels):
    file = serializers.FileField(write_only=True, required=True)
    download_url = serializers.SerializerMethodField()
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['original_name', 'size', 'uploaded_by', 'created_at']
    def get_download_url(self, obj):
        return f'/api/v1/crm/documents/{obj.pk}/download/'
    def validate_file(self, value):
        suffix = Path(value.name).suffix.lower()
        if suffix not in ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.csv', '.docx', '.xlsx']:
            raise serializers.ValidationError('Formats acceptés : PDF, images PNG/JPG, TXT, CSV, DOCX et XLSX.')
        if value.size > 5 * 1024 * 1024 or value.size == 0:
            raise serializers.ValidationError('Le fichier doit contenir entre 1 octet et 5 Mo.')
        header = value.read(16)
        value.seek(0)
        signatures = {'.pdf': b'%PDF-', '.png': b'\x89PNG\r\n\x1a\n', '.jpg': b'\xff\xd8\xff', '.jpeg': b'\xff\xd8\xff', '.docx': b'PK', '.xlsx': b'PK'}
        if suffix in signatures and not header.startswith(signatures[suffix]):
            raise serializers.ValidationError('Le contenu ne correspond pas au format du fichier.')
        return value
    def create(self, validated_data):
        file = validated_data['file']
        validated_data.update(original_name=Path(file.name).name[:255], size=file.size, uploaded_by=self.context['request'].user)
        return super().create(validated_data)
    def update(self, instance, validated_data):
        if 'file' in validated_data:
            file = validated_data['file']
            validated_data.update(original_name=Path(file.name).name[:255], size=file.size)
        return super().update(instance, validated_data)


class EmailSerializer(RelatedLabels):
    lead_email = serializers.EmailField(source='lead.email', read_only=True, allow_null=True)
    review_url = serializers.SerializerMethodField()
    class Meta:
        model = OutreachDraft
        fields = '__all__'
        read_only_fields = ['analysis', 'status', 'created_at', 'sent_at', 'decided_by', 'recipient_email', 'last_error']
    def get_review_url(self, obj):
        return f'/crm/brouillons/{obj.pk}/'
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status != 'pending':
            raise serializers.ValidationError('Seuls les brouillons en attente sont modifiables.')
        if '\n' in attrs.get('subject', '') or '\r' in attrs.get('subject', ''):
            raise serializers.ValidationError({'subject': 'L’objet doit tenir sur une ligne.'})
        return attrs


class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMSettings
        fields = '__all__'
        read_only_fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=['viewer', 'sales', 'manager'], default='sales')
    password = serializers.CharField(write_only=True, required=False, max_length=1000)
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'role', 'password']
    def to_representation(self, instance):
        data = super().to_representation(instance)
        names = set(instance.groups.values_list('name', flat=True))
        data['role'] = 'manager' if instance.is_superuser or 'manager' in names else 'sales' if 'sales' in names else 'viewer'
        return data
    def validate(self, attrs):
        if self.instance and self.instance.is_superuser:
            raise serializers.ValidationError('Les comptes superadministrateurs se gèrent hors du CRM.')
        if self.instance and self.instance.pk == self.context['request'].user.pk:
            if attrs.get('is_active') is False or attrs.get('role', 'manager') != 'manager':
                raise serializers.ValidationError('Vous ne pouvez pas retirer votre propre accès responsable.')
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Mot de passe initial requis.'})
        if attrs.get('password'):
            try:
                validate_password(attrs['password'], self.instance or get_user_model()(username=attrs.get('username', ''), email=attrs.get('email', '')))
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'password': exc.messages}) from None
        return attrs
    def save_user(self, user, data):
        role = data.pop('role', None)
        password = data.pop('password', None)
        for key, value in data.items():
            setattr(user, key, value)
        if password:
            user.set_password(password)
        user.save()
        if role:
            user.groups.remove(*Group.objects.filter(name__in=['viewer', 'sales', 'manager']))
            user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user
    def create(self, validated_data):
        return self.save_user(get_user_model()(), validated_data)
    def update(self, instance, validated_data):
        return self.save_user(instance, validated_data)

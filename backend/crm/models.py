from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Appointment(models.Model):
    lead = models.ForeignKey('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL, related_name='appointments')
    title = models.CharField('Objet', max_length=180)
    start = models.DateTimeField('Début')
    end = models.DateTimeField('Fin')
    location = models.CharField('Lieu ou lien visio', max_length=300, blank=True)
    notes = models.TextField('Notes', blank=True)
    status = models.CharField('Statut', max_length=12, default='scheduled', choices=[('scheduled', 'Prévu'), ('done', 'Terminé'), ('cancelled', 'Annulé')])
    class Meta:
        ordering = ['start', 'pk']
        constraints = [models.CheckConstraint(condition=Q(end__gt=F('start')), name='crm_appointment_end_after_start')]


class Task(models.Model):
    lead = models.ForeignKey('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    title = models.CharField('À faire', max_length=240)
    due_date = models.DateField('Échéance', null=True, blank=True)
    done = models.BooleanField(default=False)
    priority = models.CharField(max_length=10, default='normal', choices=[('low', 'Basse'), ('normal', 'Normale'), ('high', 'Haute')])
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='crm_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['done', F('due_date').asc(nulls_last=True), '-created_at']


class Note(models.Model):
    lead = models.ForeignKey('agent.Lead', on_delete=models.CASCADE, related_name='notes')
    body = models.TextField('Votre note', max_length=10000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']


class SetupToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class InquiryImport(models.Model):
    inquiry = models.OneToOneField('inquiries.Inquiry', on_delete=models.CASCADE)
    lead = models.ForeignKey('agent.Lead', on_delete=models.CASCADE)


class Client(models.Model):
    lead = models.OneToOneField('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL, related_name='client')
    name = models.CharField(max_length=150)
    company = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=15, default='active', choices=[('active', 'Actif'), ('inactive', 'Inactif')])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['name', 'pk']


SERVICE_CATEGORIES = [('conseil', 'Conseil'), ('digitalisation', 'Digitalisation'), ('ia', 'Intelligence artificielle'), ('formation', 'Formation'), ('energie', 'Énergie'), ('autre', 'Autre')]


class Opportunity(models.Model):
    service = models.CharField(max_length=20, default='autre', choices=SERVICE_CATEGORIES)
    title = models.CharField(max_length=180)
    lead = models.ForeignKey('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT)
    stage = models.CharField(max_length=20, default='new', choices=[('new', 'Nouveau'), ('qualified', 'Qualifié'), ('proposal', 'Proposition'), ('negotiation', 'Négociation'), ('won', 'Gagné'), ('lost', 'Perdu')])
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    probability = models.PositiveSmallIntegerField(default=20)
    expected_close = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name='crm_opportunity_amount_positive'), models.CheckConstraint(condition=Q(probability__lte=100), name='crm_opportunity_probability_range')]


class Project(models.Model):
    service = models.CharField(max_length=20, default='autre', choices=SERVICE_CATEGORIES)
    progress = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=180)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, default='planned', choices=[('planned', 'À démarrer'), ('in_progress', 'En cours'), ('on_hold', 'En pause'), ('completed', 'Terminé')])
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=Q(budget__gte=0, cost__gte=0), name='crm_project_nonnegative_amounts'), models.CheckConstraint(condition=Q(progress__lte=100), name='crm_project_progress_range')]


class FinancialDocument(models.Model):
    number = models.CharField(max_length=30, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.PROTECT)
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    items = models.JSONField(default=list)
    total_ht = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_ttc = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        abstract = True
        ordering = ['-created_at']


class Quote(FinancialDocument):
    status = models.CharField(max_length=15, default='draft', choices=[('draft', 'Brouillon'), ('sent', 'Envoyé'), ('accepted', 'Accepté'), ('rejected', 'Refusé')])


class Invoice(FinancialDocument):
    status = models.CharField(max_length=15, default='draft', choices=[('draft', 'Brouillon'), ('issued', 'Émise'), ('paid', 'Payée'), ('overdue', 'En retard'), ('cancelled', 'Annulée')])


class NumberSequence(models.Model):
    key = models.CharField(max_length=20, unique=True)
    value = models.PositiveIntegerField(default=0)


def private_document_storage():
    from django.core.files.storage import FileSystemStorage
    return FileSystemStorage(location=settings.CRM_DOCUMENT_ROOT, base_url=None)


def private_document_path(instance, filename):
    import uuid
    from pathlib import Path
    return str(uuid.uuid4()) + Path(filename).suffix.lower()


class Document(models.Model):
    title = models.CharField(max_length=180)
    file = models.FileField(storage=private_document_storage, upload_to=private_document_path)
    original_name = models.CharField(max_length=255, blank=True)
    size = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=20, default='other', choices=[('contract', 'Contrat'), ('quote', 'Devis'), ('invoice', 'Facture'), ('brief', 'Brief'), ('other', 'Autre')])
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL)
    lead = models.ForeignKey('agent.Lead', null=True, blank=True, on_delete=models.SET_NULL)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']


class CRMSettings(models.Model):
    company_name = models.CharField(max_length=180, default='SONUTECH')
    email = models.EmailField(blank=True, default='sonutech@sonutech.fr')
    phone = models.CharField(max_length=40, blank=True, default='07 75 78 78 25')
    address = models.TextField(blank=True)
    siret = models.CharField(max_length=20, blank=True)
    vat_number = models.CharField(max_length=30, blank=True)
    currency = models.CharField(max_length=3, default='EUR', choices=[('EUR', 'EUR')])

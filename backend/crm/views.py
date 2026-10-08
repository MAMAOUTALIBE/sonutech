import hashlib
from functools import wraps
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, Http404
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from accounts.models import AuditLog
from agent.models import Lead
from inquiries.models import Inquiry
from inquiries.throttles import LoginThrottle
from .forms import ActivationForm, AppointmentForm, LeadForm, NoteForm, TaskForm
from .models import Appointment, InquiryImport, Note, SetupToken, Task


def allowed(user):
    return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name__in=['sales', 'manager']).exists())


def private(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('crm:login')
        if not allowed(request.user):
            return HttpResponseForbidden('Accès réservé à l’équipe commerciale.')
        return view(request, *args, **kwargs)
    return wrapper


def audit(request, obj, action, fields=()):
    AuditLog.objects.create(actor=request.user, action=action, resource=obj._meta.label_lower, object_id=str(obj.pk), changed_fields=list(fields))


def page(request, queryset):
    return Paginator(queryset, 25).get_page(request.GET.get('page'))


@require_http_methods(['GET', 'POST'])
def login_view(request):
    def login_allowed(user):
        return user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name__in=['sales', 'manager', 'viewer']).exists())
    if login_allowed(request.user):
        return redirect('crm:prospect_list')
    form = AuthenticationForm(request, data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if not LoginThrottle().allow_request(request, None):
            form.add_error(None, 'Trop de tentatives. Réessayez plus tard.')
            return render(request, 'crm/login.html', {'form': form}, status=429)
        if form.is_valid():
            if login_allowed(form.get_user()):
                login(request, form.get_user())
                return redirect('crm:prospect_list')
            form.add_error(None, 'Ce compte ne dispose pas de l’accès commercial.')
    return render(request, 'crm/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('crm:login')


@require_http_methods(['GET', 'POST'])
def activate(request):
    form = ActivationForm(get_user_model()(), data=request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        raw = request.POST.get('token', '')
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        with transaction.atomic():
            token = SetupToken.objects.select_for_update().filter(token_hash=token_hash, used_at__isnull=True, expires_at__gt=timezone.now()).first()
            user = get_user_model().objects.select_for_update().get(pk=token.user_id) if token else None
            if not token or not user or not allowed(user) or user.has_usable_password():
                form.is_valid()
                form.add_error(None, 'Ce lien est invalide, expiré ou déjà utilisé.')
            else:
                form = ActivationForm(user, data=request.POST)
                if form.is_valid():
                    form.save()
                    token.used_at = timezone.now()
                    token.save(update_fields=['used_at'])
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    audit(request, user, 'crm_activate', ['password'])
                    return redirect('crm:prospect_list')
    return render(request, 'crm/activation.html', {'form': form})


@private
@require_http_methods(['GET'])
def dashboard(request):
    return redirect('crm:prospect_list')


@private
@require_http_methods(['GET'])
def prospect_list(request):
    q = request.GET.get('q', '').strip()[:200]
    stage = request.GET.get('stage', '')
    leads = Lead.objects.all()
    if q:
        leads = leads.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
    if stage:
        leads = leads.filter(stage=stage)
    incoming = Inquiry.objects.filter(inquiryimport__isnull=True, triage__lead__isnull=True).exclude(status='archived')
    return render(request, 'crm/prospects.html', {'active_nav': 'prospects', 'page_obj': page(request, leads), 'q': q, 'stage': stage, 'stages': Lead._meta.get_field('stage').choices, 'new_inquiries': incoming[:20], 'counts': {'total': Lead.objects.count(), 'active': Lead.objects.exclude(stage__in=['won', 'not_retained']).count(), 'won': Lead.objects.filter(stage='won').count(), 'new_inquiries': incoming.count()}})


@private
@require_http_methods(['GET'])
def prospect_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    inquiries = Inquiry.objects.filter(Q(inquiryimport__lead=lead) | Q(triage__lead=lead) | (Q(email__iexact=lead.email) if lead.email else Q(pk__in=[]))).distinct()
    return render(request, 'crm/prospect_detail.html', {'active_nav': 'prospects', 'lead': lead, 'inquiries': inquiries, 'appointments': lead.appointments.all(), 'tasks': lead.tasks.all(), 'notes': lead.notes.select_related('author'), 'note_form': NoteForm()})


def edit_form(request, form_class, title, nav, back_url, instance=None):
    initial = {}
    if request.GET.get('lead'):
        try:
            initial['lead'] = get_object_or_404(Lead, pk=request.GET['lead']).pk
        except ValidationError as exc:
            raise Http404('Prospect introuvable.') from exc
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request, obj, 'crm_update' if instance else 'crm_create', form.changed_data)
        messages.success(request, 'Enregistré.')
        return redirect('crm:prospect_detail', pk=obj.pk) if isinstance(obj, Lead) else redirect(back_url)
    return render(request, 'crm/form.html', {'form': form, 'title': title, 'active_nav': nav, 'back_url': back_url, 'submit_label': 'Enregistrer'})


@private
@require_http_methods(['GET', 'POST'])
def prospect_create(request):
    return edit_form(request, LeadForm, 'Nouveau prospect', 'prospects', reverse('crm:prospect_list'))


@private
@require_http_methods(['GET', 'POST'])
def prospect_edit(request, pk):
    return edit_form(request, LeadForm, 'Modifier le prospect', 'prospects', reverse('crm:prospect_detail', args=[pk]), get_object_or_404(Lead, pk=pk))


@private
@require_POST
def inquiry_import(request, pk):
    with transaction.atomic():
        inquiry = get_object_or_404(Inquiry.objects.select_for_update(), pk=pk)
        imported = InquiryImport.objects.filter(inquiry=inquiry).first()
        if imported:
            return redirect('crm:prospect_detail', pk=imported.lead_id)
        email = inquiry.email.strip().lower()
        lead = Lead.objects.filter(email__iexact=email).first()
        if lead is None:
            lead, _ = Lead.objects.get_or_create(email=email, defaults={'name': inquiry.name, 'company': inquiry.company, 'phone': inquiry.phone})
        InquiryImport.objects.create(inquiry=inquiry, lead=lead)
        inquiry.status = 'in_progress'
        inquiry.save(update_fields=['status', 'updated_at'])
        audit(request, lead, 'crm_import', ['inquiry'])
    messages.success(request, 'Demande ajoutée aux prospects.')
    return redirect('crm:prospect_detail', pk=lead.pk)


@private
@require_POST
def note_create(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            note = form.save(commit=False)
            note.lead, note.author = lead, request.user
            note.save()
            Lead.objects.filter(pk=lead.pk).update(updated_at=timezone.now())
            audit(request, note, 'crm_create', ['body'])
        messages.success(request, 'Note ajoutée.')
    else:
        messages.error(request, 'La note doit contenir entre 1 et 10 000 caractères.')
    return redirect('crm:prospect_detail', pk=pk)


@private
@require_http_methods(['GET'])
def appointment_list(request):
    items = Appointment.objects.select_related('lead')
    selected = request.GET.get('filter', 'upcoming')
    if selected == 'upcoming':
        items = items.filter(end__gte=timezone.now(), status='scheduled')
    elif selected == 'past':
        items = items.filter(end__lt=timezone.now()).order_by('-start')
    return render(request, 'crm/appointments.html', {'active_nav': 'appointments', 'page_obj': page(request, items), 'filter': selected})


@private
@require_http_methods(['GET', 'POST'])
def appointment_create(request):
    return edit_form(request, AppointmentForm, 'Nouveau rendez-vous', 'appointments', reverse('crm:appointment_list'))


@private
@require_http_methods(['GET', 'POST'])
def appointment_edit(request, pk):
    return edit_form(request, AppointmentForm, 'Modifier le rendez-vous', 'appointments', reverse('crm:appointment_list'), get_object_or_404(Appointment, pk=pk))


@private
@require_http_methods(['GET'])
def task_list(request):
    items = Task.objects.select_related('lead')
    selected = request.GET.get('filter', 'open')
    if selected in ['open', 'done']:
        items = items.filter(done=selected == 'done')
    return render(request, 'crm/tasks.html', {'active_nav': 'tasks', 'page_obj': page(request, items), 'filter': selected, 'today': timezone.localdate()})


@private
@require_http_methods(['GET', 'POST'])
def task_create(request):
    return edit_form(request, TaskForm, 'Nouvelle action', 'tasks', reverse('crm:task_list'))


@private
@require_POST
def task_toggle(request, pk):
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        task.done = not task.done
        task.save(update_fields=['done'])
        audit(request, task, 'crm_update', ['done'])
    return redirect('crm:task_list')


@private
@require_http_methods(['GET', 'POST'])
def task_edit(request, pk):
    return edit_form(request, TaskForm, 'Modifier l’action', 'tasks', reverse('crm:task_list'), get_object_or_404(Task, pk=pk))

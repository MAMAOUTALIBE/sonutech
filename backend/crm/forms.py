from django import forms
from django.contrib.auth.forms import SetPasswordForm
from agent.models import Lead
from .models import Appointment, Task, Note


class LeadChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name} — {obj.company}' if obj.company else obj.name


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['name', 'company', 'email', 'phone', 'stage', 'next_step', 'internal_notes']
        labels = {'name': 'Nom', 'company': 'Entreprise', 'email': 'Email', 'phone': 'Téléphone', 'stage': 'Étape', 'next_step': 'Prochaine action', 'internal_notes': 'Notes internes'}
        widgets = {'internal_notes': forms.Textarea(attrs={'rows': 4})}
    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and Lead.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Un prospect utilise déjà cet email.')
        return email or None
    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('email') and not cleaned.get('phone'):
            raise forms.ValidationError('Indiquez au moins un email ou un téléphone.')
        return cleaned


class AppointmentForm(forms.ModelForm):
    lead = LeadChoiceField(queryset=Lead.objects.order_by('name'), required=False, label='Prospect')
    class Meta:
        model = Appointment
        fields = ['title', 'lead', 'start', 'end', 'location', 'status', 'notes']
        widgets = {'start': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}), 'end': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}), 'notes': forms.Textarea(attrs={'rows': 3})}
    def clean(self):
        cleaned = super().clean()
        if cleaned.get('start') and cleaned.get('end') and cleaned['end'] <= cleaned['start']:
            self.add_error('end', 'La fin doit être après le début.')
        return cleaned


class TaskForm(forms.ModelForm):
    lead = LeadChoiceField(queryset=Lead.objects.order_by('name'), required=False, label='Prospect')
    class Meta:
        model = Task
        fields = ['title', 'lead', 'due_date']
        widgets = {'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})}


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['body']
        widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Échange téléphonique, besoin, prochaine étape…'})}


class ActivationForm(SetPasswordForm):
    token = forms.CharField(widget=forms.HiddenInput, max_length=128)

from django import forms
from .models import AssistantConfiguration, OutreachDraft


class ChatbotSettingsForm(forms.ModelForm):
    api_key = forms.CharField(label='Nouvelle clé API Groq', required=False, min_length=20, max_length=512, strip=True, widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}), help_text='Laissez vide pour conserver la clé enregistrée. Elle ne sera jamais affichée.')
    class Meta:
        model = AssistantConfiguration
        fields = ['enabled', 'daily_limit', 'rules']
        widgets = {'rules': forms.Textarea(attrs={'rows': 5})}
    def clean_daily_limit(self):
        value = self.cleaned_data['daily_limit']
        if not 1 <= value <= 1000:
            raise forms.ValidationError('Choisissez entre 1 et 1 000 appels par jour.')
        return value
    def clean_api_key(self):
        value = self.cleaned_data.get('api_key', '')
        if any(c.isspace() for c in value):
            raise forms.ValidationError('La clé ne doit pas contenir d’espace.')
        return value


class DraftForm(forms.ModelForm):
    class Meta:
        model = OutreachDraft
        fields = ['subject', 'body']
        widgets = {'body': forms.Textarea(attrs={'rows': 14})}
    def clean_subject(self):
        value = self.cleaned_data['subject']
        if '\n' in value or '\r' in value:
            raise forms.ValidationError('L’objet doit tenir sur une ligne.')
        return value

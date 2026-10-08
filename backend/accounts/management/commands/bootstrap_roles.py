from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
class Command(BaseCommand):
    help = 'Create least-privilege CRM roles; users administration remains superuser-only.'
    def handle(self, *args, **kwargs):
        editor, _ = Group.objects.get_or_create(name='content_editor')
        editor.permissions.set(Permission.objects.filter(content_type__app_label='content'))
        sales, _ = Group.objects.get_or_create(name='sales')
        sales.permissions.set(Permission.objects.filter(content_type__app_label='inquiries', codename__in=['view_inquiry', 'change_inquiry', 'export_inquiry', 'retry_inquiry']) | Permission.objects.filter(content_type__app_label='agent', codename__in=['view_lead', 'add_lead', 'change_lead', 'view_inquirytriage', 'view_emaildraft', 'change_emaildraft']) | Permission.objects.filter(content_type__app_label='crm', codename__in=['view_appointment', 'add_appointment', 'change_appointment', 'view_task', 'add_task', 'change_task', 'view_note', 'add_note']))
        viewer, _ = Group.objects.get_or_create(name='viewer')
        viewer.permissions.set(Permission.objects.filter(content_type__app_label__in=['crm', 'agent'], codename__startswith='view_'))
        manager, _ = Group.objects.get_or_create(name='manager')
        manager.permissions.set(Permission.objects.filter(pk__in=list(editor.permissions.values_list('pk', flat=True)) + list(sales.permissions.values_list('pk', flat=True)) + list(Permission.objects.filter(codename='view_auditlog').values_list('pk', flat=True))))
        self.stdout.write('Roles configured: content_editor, sales, manager.')

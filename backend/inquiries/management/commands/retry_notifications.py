from django.core.management.base import BaseCommand
from inquiries.models import Inquiry
from inquiries.notifications import notify_inquiry
class Command(BaseCommand):
    help = 'Retry pending/failed notifications without duplicating submissions.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
    def handle(self, *args, **options):
        ids = list(Inquiry.objects.exclude(notification_status='sent').order_by('created_at').values_list('pk', flat=True)[:max(0, options['limit'])])
        sent = sum(notify_inquiry(pk) for pk in ids)
        self.stdout.write(f'{sent}/{len(ids)} notifications sent.')

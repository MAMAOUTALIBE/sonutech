from django.core.management.base import BaseCommand
from django.utils import timezone
from inquiries.models import RateBucket
class Command(BaseCommand):
    help = 'Remove expired anonymous rate-limit counters (run daily).'
    def handle(self, *args, **options):
        count, _ = RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'{count} expired counters deleted.')

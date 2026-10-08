import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from chatbot.worker import process_inquiries


class Command(BaseCommand):
    help = 'Prepare draft-only CRM analyses for fresh incoming requests. Never sends email.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--interval', type=int, default=60)
    def handle(self, *args, **options):
        if options['interval'] < 10:
            raise CommandError('Interval must be at least 10 seconds.')
        while True:
            close_old_connections()
            try:
                count = process_inquiries()
                if count:
                    self.stdout.write(f'{count} demande(s) préparée(s), en attente de validation humaine.')
            except Exception:
                # No traceback or provider payload in worker logs.
                self.stderr.write('Traitement indisponible ; nouvel essai au prochain passage.')
                if options['once']:
                    raise CommandError('Le traitement a échoué.') from None
            if options['once']:
                return
            time.sleep(options['interval'])

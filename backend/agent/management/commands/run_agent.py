import signal
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from agent.llm import credentials_configured
from agent.service import run_pass, mail_ready

class Command(BaseCommand):
    help = 'Assistant IA : analyse les nouvelles demandes, prépare les réponses, gère validations, relances et résumé quotidien.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Un seul passage, pour une tâche planifiée (cron).')
        parser.add_argument('--interval', type=int, default=30, help='Secondes entre deux passages.')
    def handle(self, *args, **options):
        stopping = []
        previous = {sig: signal.signal(sig, lambda *_: stopping.append(True)) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            self.loop(stopping, options)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    def loop(self, stopping, options):
        if not settings.AGENT_ENABLED:
            self.stdout.write('Assistant désactivé (AGENT_ENABLED=0).')
        else:
            self.stdout.write(f'Assistant actif, mode {settings.AGENT_MODE}, modèle {settings.AGENT_MODEL}.')
            if not credentials_configured():
                self.stdout.write('ANTHROPIC_API_KEY absente : les demandes resteront en échec jusqu’à sa configuration.')
            if not mail_ready():
                self.stdout.write('Emails non configurés : les brouillons restent consultables via l’API de gestion.')
        while not stopping:
            close_old_connections()
            if settings.AGENT_ENABLED:
                stats = run_pass()
                if any(stats.values()):
                    self.stdout.write(' · '.join(f'{name} {count}' for name, count in stats.items() if count))
            if options['once']:
                break
            for _ in range(max(1, options['interval'])):
                if stopping:
                    break
                time.sleep(1)

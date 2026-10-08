import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from crm.models import SetupToken


class Command(BaseCommand):
    help = 'Create a commercial account and a single-use 24-hour password setup link; sends no email.'
    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('--base-url', default=settings.AGENT_PUBLIC_BASE_URL)
    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError('Invalid email.') from exc
        if len(email) > 150:
            raise CommandError('Email too long for username.')
        call_command('bootstrap_roles', stdout=self.stdout)
        with transaction.atomic():
            users = get_user_model().objects.select_for_update().filter(email__iexact=email)
            if users.count() > 1:
                raise CommandError('Multiple accounts have this email; choose an unambiguous account first.')
            user = users.first()
            if user is None:
                if get_user_model().objects.filter(username__iexact=email).exists():
                    raise CommandError('Username already exists with another email.')
                user = get_user_model().objects.create_user(username=email, email=email, password=None)
            if not user.is_active:
                raise CommandError('Account inactive; enable it deliberately before provisioning access.')
            user.groups.add(Group.objects.get(name='sales'))
            if user.has_usable_password():
                self.stdout.write(f'Existing password preserved. Sign in as {user.username} at {options["base_url"].rstrip("/")}/crm/connexion/')
                return
            SetupToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            token = secrets.token_urlsafe(32)
            SetupToken.objects.create(user=user, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now() + timedelta(hours=24))
        self.stdout.write(f'{options["base_url"].rstrip("/")}/crm/activer/#{token}')

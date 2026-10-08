import hashlib
import ipaddress
import secrets
import time
from datetime import datetime, timezone
from django.conf import settings
from django.db import transaction
from rest_framework.throttling import BaseThrottle
from .models import RateBucket

class DatabaseThrottle(BaseThrottle):
    scope = 'inquiry'
    period = 3600
    def allow_request(self, request, view):
        ident = request.META.get('REMOTE_ADDR', '')
        # Only the server-side relay knows this secret. Its ingress must overwrite
        # the original client IP header; ordinary forwarded headers are ignored.
        expected = settings.PROXY_SHARED_SECRET
        supplied = request.META.get('HTTP_X_SONUTECH_PROXY_SECRET', '')
        if self.scope == 'inquiry' and expected and secrets.compare_digest(expected.encode(), supplied.encode()):
            try:
                ident = str(ipaddress.ip_address(request.META.get('HTTP_X_SONUTECH_CLIENT_IP', '')))
            except ValueError:
                pass
        window = int(time.time()) // self.period
        key = hashlib.sha256(f'{settings.SECRET_KEY}:{self.scope}:{ident}:{window}'.encode()).hexdigest()
        self.remaining_wait = (window + 1) * self.period - time.time()
        limit = settings.LOGIN_RATE_LIMIT if self.scope == 'login' else settings.INQUIRY_RATE_LIMIT
        with transaction.atomic():
            bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires_at': datetime.fromtimestamp((window + 1) * self.period, timezone.utc)})
            bucket = RateBucket.objects.select_for_update().get(pk=bucket.pk)
            if bucket.count >= limit:
                return False
            bucket.count += 1
            bucket.save(update_fields=['count'])
        return True
    def wait(self):
        return self.remaining_wait
class LoginThrottle(DatabaseThrottle):
    scope = 'login'

import hashlib
import ipaddress
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from inquiries.models import RateBucket
from .models import AssistantConfiguration, ChatMessage, Conversation
from .provider import BudgetExceeded, ProviderUnavailable
from .secrets import read_key
from . import service


def error(detail, status=400):
    return JsonResponse({'available': False, 'detail': detail, 'contact_url': '/contact'}, status=status)


def limited(ip):
    window = int(time.time()) // 3600
    key = hashlib.sha256(f'{settings.SECRET_KEY}:chat:{ip}:{window}'.encode()).hexdigest()
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires_at': datetime.fromtimestamp((window + 1) * 3600, dt_timezone.utc)})
        bucket = RateBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.count >= 30:
            return True
        bucket.count += 1
        bucket.save(update_fields=['count'])
    return False


def contact_data(data):
    if data.get('consent') is not True:
        raise ValueError('Votre accord est nécessaire pour être recontacté.')
    cleaned = {}
    for field, maximum in [('name', 150), ('email', 254), ('phone', 40), ('company', 180), ('message', 2000)]:
        value = data.get(field, '')
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError('Vérifiez les coordonnées renseignées.')
        cleaned[field] = value.strip()
    if not cleaned['name'] or not cleaned['message'] or not (cleaned['email'] or cleaned['phone']):
        raise ValueError('Indiquez votre nom, votre besoin et au moins un email ou un téléphone.')
    if cleaned['email']:
        try:
            validate_email(cleaned['email'])
        except ValidationError:
            raise ValueError('Indiquez un email valide.') from None
    if cleaned['phone'] and (sum(c.isdigit() for c in cleaned['phone']) < 6 or any(c not in '+()- .0123456789' for c in cleaned['phone'])):
        raise ValueError('Indiquez un téléphone valide.')
    try:
        uuid.UUID(str(data.get('contact_id', '')))
    except ValueError:
        raise ValueError('Identifiant de demande invalide.') from None
    return cleaned


@csrf_exempt
@require_POST
def chat(request):
    expected = settings.PROXY_SHARED_SECRET
    supplied = request.headers.get('X-Sonutech-Proxy-Secret', '')
    if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
        return error('Accès refusé.', 403)
    try:
        ip = str(ipaddress.ip_address(request.headers.get('X-Sonutech-Client-IP', '')))
    except ValueError:
        return error('Adresse de connexion invalide.', 403)
    if len(request.body) > 16000:
        return error('Demande trop volumineuse.', 413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return error('Demande invalide.')
    if limited(ip):
        return error('Trop de messages. Réessayez plus tard ou utilisez le formulaire de contact.', 429)
    action = data.get('action')
    if action == 'start':
        if not AssistantConfiguration.load().enabled or not read_key():
            return error('L’assistant IA est indisponible. Notre équipe reste joignable via le formulaire de contact.', 503)
        raw = secrets.token_urlsafe(32)
        Conversation.objects.create(token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=timezone.now() + timedelta(hours=24))
        return JsonResponse({'available': True, 'token': raw, 'reply': 'Bonjour ! Je suis l’assistant IA de SONUTECH. Quel projet souhaitez-vous réaliser ?'})
    if action not in ['message', 'contact']:
        return error('Action invalide.')
    raw = data.get('token', '')
    if not isinstance(raw, str) or not 20 <= len(raw) <= 128:
        return error('Session invalide ou expirée.', 401)
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().filter(token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at__gt=timezone.now()).first()
        if not conversation:
            return error('Session invalide ou expirée.', 401)
        if action == 'contact':
            try:
                cleaned = contact_data(data)
            except ValueError as exc:
                return error(str(exc))
            capture_hash = hashlib.sha256(json.dumps(cleaned, sort_keys=True).encode()).hexdigest()
            if conversation.captured_at and conversation.capture_hash != capture_hash:
                return error('Une demande différente a déjà été enregistrée pour cette conversation. Utilisez le formulaire de contact pour la compléter.', 409)
            service.capture(conversation, cleaned, data['contact_id'], capture_hash)
            return JsonResponse({'captured': True, 'detail': 'Votre demande est enregistrée. L’équipe SONUTECH pourra vous recontacter.'})
        message = data.get('message', '')
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            return error('Le message doit contenir entre 1 et 2 000 caractères.')
        try:
            message_id = uuid.UUID(str(data.get('message_id', '')))
        except ValueError:
            return error('Identifiant de message invalide.')
        payload_hash = hashlib.sha256(message.encode()).hexdigest()
        previous = ChatMessage.objects.filter(conversation=conversation, message_id=message_id).first()
        if previous:
            if previous.payload_hash != payload_hash:
                return error('Cet identifiant correspond à un autre message.', 409)
            return JsonResponse({'available': True, 'reply': previous.reply, 'suggest_contact': previous.suggest_contact})
        if conversation.turns >= 30:
            return error('La conversation a atteint sa limite. Notre équipe peut poursuivre par le formulaire de contact.', 429)
        try:
            result = service.reply(conversation.history, message)
        except BudgetExceeded as exc:
            return error(str(exc), 429)
        except ProviderUnavailable:
            return error('L’assistant IA est momentanément indisponible. Contactez directement notre équipe.', 503)
        ChatMessage.objects.create(conversation=conversation, message_id=message_id, payload_hash=payload_hash, **result)
        conversation.history = [*conversation.history, {'role': 'user', 'content': message}, {'role': 'assistant', 'content': result['reply']}][-12:]
        conversation.turns += 1
        conversation.save(update_fields=['history', 'turns'])
        return JsonResponse({'available': True, **result})

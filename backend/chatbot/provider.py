from django.views.decorators.debug import sensitive_variables
import json
import urllib.error
import urllib.request
from django.db import transaction
from django.utils import timezone
from .models import AssistantConfiguration, DailyUsage
from .secrets import read_key

MODEL = 'openai/gpt-oss-120b'


class ProviderUnavailable(Exception):
    pass


class BudgetExceeded(ProviderUnavailable):
    pass


def reserve_call():
    # Row locks serialize the global budget, including calls that fail upstream.
    with transaction.atomic():
        configuration = AssistantConfiguration.load()
        configuration = AssistantConfiguration.objects.select_for_update().get(pk=configuration.pk)
        usage, _ = DailyUsage.objects.get_or_create(day=timezone.localdate())
        usage = DailyUsage.objects.select_for_update().get(pk=usage.pk)
        if usage.calls >= configuration.daily_limit:
            raise BudgetExceeded('Limite quotidienne atteinte. Réessayez demain.')
        usage.calls += 1
        usage.save(update_fields=['calls'])


@sensitive_variables()
def complete(messages, schema, name='sonutech_response'):
    key = read_key()
    if not key:
        raise ProviderUnavailable('Assistant non configuré.')
    reserve_call()
    payload = {'model': MODEL, 'messages': messages, 'max_completion_tokens': 2500, 'reasoning_effort': 'low', 'response_format': {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}}}
    request = urllib.request.Request('https://api.groq.com/openai/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(1000000))
        choice = data['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Incomplete result')
        result = json.loads(choice['message']['content'])
        if not isinstance(result, dict):
            raise ValueError('Invalid result')
        return result
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError):
        # Never expose provider responses: they can contain credentials or prompts.
        raise ProviderUnavailable('Le service IA est momentanément indisponible.') from None

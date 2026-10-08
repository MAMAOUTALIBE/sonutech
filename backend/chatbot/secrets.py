from django.views.decorators.debug import sensitive_variables
"""Provider credentials live outside the database, static tree and application logs."""
import json
import os
import stat
import tempfile
from pathlib import Path
from django.conf import settings


def read_key():
    path = Path(settings.CHATBOT_SECRET_FILE)
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            return ''
        data = json.loads(path.read_text())
        key = data.get('api_key', '')
        return key if isinstance(key, str) and 20 <= len(key) <= 512 and not any(c.isspace() for c in key) else ''
    except (OSError, ValueError, TypeError):
        return ''


@sensitive_variables()
def write_key(key):
    path = Path(settings.CHATBOT_SECRET_FILE)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.groq-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'api_key': key}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

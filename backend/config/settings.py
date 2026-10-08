import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY is required. Generate a random secret before starting.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,backend,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'corsheaders', 'rest_framework', 'drf_spectacular', 'content', 'inquiries', 'accounts', 'agent', 'crm', 'chatbot']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'config.middleware.PrivateNoStoreMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': dj_database_url.config(default='postgresql://sonutech@db:5432/sonutech', conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [{'NAME': f'django.contrib.auth.password_validation.{name}'} for name in ['UserAttributeSimilarityValidator', 'MinimumLengthValidator', 'CommonPasswordValidator', 'NumericPasswordValidator']]
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
CORS_ALLOWED_ORIGINS = [s for s in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if s]
CSRF_TRUSTED_ORIGINS = [s for s in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000').split(',') if s]
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '0') == '1'
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
X_FRAME_OPTIONS = 'DENY'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'], 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 25, 'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema', 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer']}
SPECTACULAR_SETTINGS = {'TITLE': 'SONUTECH API', 'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False}
# Development only: django.core.mail.backends.console.EmailBackend prints emails in the logs.
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('SMTP_HOST', '')
EMAIL_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_HOST_USER = os.getenv('SMTP_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('SMTP_USE_TLS', '1') == '1'
EMAIL_USE_SSL = os.getenv('SMTP_USE_SSL', '0') == '1'
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '')
INQUIRY_NOTIFICATION_EMAIL = os.getenv('INQUIRY_NOTIFICATION_EMAIL', '')
INQUIRY_RATE_LIMIT = int(os.getenv('INQUIRY_RATE_LIMIT', '10'))
LOGIN_RATE_LIMIT = 10

# Shared only with the server-side frontend relay; never expose in NEXT_PUBLIC_* vars.
PROXY_SHARED_SECRET = os.getenv('PROXY_SHARED_SECRET', '')
if PROXY_SHARED_SECRET and len(PROXY_SHARED_SECRET) < 32:
    raise ImproperlyConfigured('PROXY_SHARED_SECRET must contain at least 32 characters.')

# AI assistant (agent app). ANTHROPIC_API_KEY is read by the SDK from the environment only.
AGENT_ENABLED = os.getenv('AGENT_ENABLED', '0') == '1'
AGENT_MODE = os.getenv('AGENT_MODE', 'draft')
if AGENT_MODE not in ('draft', 'semi', 'auto'):
    raise ImproperlyConfigured('AGENT_MODE must be draft, semi or auto.')
AGENT_MODEL = os.getenv('AGENT_MODEL', 'claude-opus-5-5')
AGENT_EFFORT = os.getenv('AGENT_EFFORT', 'medium')
AGENT_OWNER_EMAIL = os.getenv('AGENT_OWNER_EMAIL', '')
AGENT_SIGNATURE = os.getenv('AGENT_SIGNATURE', 'L’équipe SONUTECH')
AGENT_PUBLIC_BASE_URL = os.getenv('AGENT_PUBLIC_BASE_URL', 'http://localhost:8000').rstrip('/')
AGENT_FOLLOWUP_DAYS = [int(d) for d in os.getenv('AGENT_FOLLOWUP_DAYS', '3,7').split(',') if d.strip()]
AGENT_APPROVAL_TTL_HOURS = int(os.getenv('AGENT_APPROVAL_TTL_HOURS', '168'))
AGENT_MAX_AUTO_SENDS_PER_HOUR = int(os.getenv('AGENT_MAX_AUTO_SENDS_PER_HOUR', '20'))
AGENT_MAX_AGE_DAYS = int(os.getenv('AGENT_MAX_AGE_DAYS', '3'))
AGENT_DIGEST_HOUR = int(os.getenv('AGENT_DIGEST_HOUR', '8'))

# Groq credentials are stored in a private mounted file, never in database fields.
CHATBOT_SECRET_FILE = os.getenv('CHATBOT_SECRET_FILE', str(BASE_DIR.parent / '.local' / 'groq.json'))

CRM_DOCUMENT_ROOT = os.getenv('CRM_DOCUMENT_ROOT', str(BASE_DIR.parent / '.local' / 'documents'))

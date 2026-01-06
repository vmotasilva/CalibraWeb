import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/


# SECURITY WARNING: keep the secret key used in production secret!
# Read SECRET_KEY from environment in all environments. For local dev you may
# set SECRET_KEY in a .env file; but on production the variable must be provided.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Fallback for development/testing only
    # In production, SECRET_KEY MUST be set via environment
    if DEBUG or os.environ.get("ALLOW_INSECURE_SECRET_KEY", "false").lower() == "true":
        SECRET_KEY = "django-insecure-dev-key-do-not-use-in-production-change-this-asap"
    else:
        # Try to generate a temporary key for container initialization
        try:
            from django.core.management.utils import get_random_secret_key
            SECRET_KEY = get_random_secret_key()
            print(f"⚠️  Generated temporary SECRET_KEY: {SECRET_KEY}")
            print("⚠️  Set SECRET_KEY environment variable in production!")
        except:
            raise ImproperlyConfigured("SECRET_KEY is required. Set it in the environment (see .env.example)")

# SECURITY WARNING: don't run with debug turned on in production!
# Default is False (safer). In dev set DEBUG='True' in the environment.
DEBUG = os.environ.get("DEBUG", "False") == "True"

# Configure ALLOWED_HOSTS via environment variable (comma-separated), default to localhost for development.
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,0.0.0.0").split(",")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

# Ensure ALLOWED_HOSTS is not empty
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]


# Configuração necessária para o formulário de login funcionar no Railway (HTTPS)
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "https://*.railway.app"
).split(",")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Novos módulos modulares (ATIVADOS - Phase 9 modularization)
    "core.apps.CoreConfig",
    "organization.apps.OrganizationConfig",
    "rh.apps.RhConfig",
    "metrologia.apps.MetrologiaConfig",
    "procedures.apps.ProceduresConfig",  # Unificação de training + procurements
    "documents.apps.DocumentsConfig",
    "shared.apps.SharedConfig",
    "fornecedores.apps.FornecedoresConfig",
    # Módulo legado (compatibilidade - mantém 3 cross-app models: SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob)
    "qms",
    # Aplicações de terceiros
    "widget_tweaks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise para arquivos estáticos
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "shared.middleware.ModuleAccessMiddleware",  # Controle de acesso por módulo
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "shared" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Configuração padrão (Local)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Configuração de Produção (Railway)
import logging
logger = logging.getLogger(__name__)

def _build_db_from_pg_env() -> str | None:
    """Build a PostgreSQL URL from Railway-style PG* env vars if present.
    Expected vars: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    Returns a DSN string or None if insufficient info.
    """
    pg_host = os.environ.get("PGHOST")
    pg_port = os.environ.get("PGPORT", "5432")
    pg_user = os.environ.get("PGUSER")
    pg_pass = os.environ.get("PGPASSWORD")
    pg_db = os.environ.get("PGDATABASE")
    
    logger.info(f"DB ENV CHECK: PGHOST={pg_host}, PGPORT={pg_port}, PGUSER={pg_user}, PGDATABASE={pg_db}, has_pass={bool(pg_pass)}")
    
    if all([pg_host, pg_user, pg_db]):
        # Password may be optional in some setups
        if pg_pass:
            dsn = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
            logger.info(f"Built DSN from PG* vars: postgresql://{pg_user}:***@{pg_host}:{pg_port}/{pg_db}")
            return dsn
        dsn = f"postgresql://{pg_user}@{pg_host}:{pg_port}/{pg_db}"
        logger.info(f"Built DSN from PG* vars (no pass): {dsn}")
        return dsn
    logger.warning("Insufficient PG* environment variables to build database URL")
    return None

# Prefer an explicit DATABASE_URL; fall back to common alt names and PG* vars
database_url = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("RAILWAY_DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("POSTGRESQL_URL")
)

logger.info(f"DATABASE_URL present: {bool(database_url)}")
if database_url:
    # Mask password for logging
    safe_url = database_url.split('@')[0].split(':')[0] + ':***@' + database_url.split('@')[1] if '@' in database_url else database_url
    logger.info(f"DATABASE_URL value (masked): {safe_url}")

if database_url:
    # Guard against placeholder URLs like ...@host:port/db
    malformed_placeholder = "@host:" in database_url or database_url.endswith("@host")
    if malformed_placeholder:
        logger.warning(f"Detected malformed DATABASE_URL with placeholder 'host', attempting to build from PG* vars")
        built = _build_db_from_pg_env()
        if built:
            database_url = built
            logger.info("Successfully replaced malformed URL with PG* vars")
        else:
            logger.error("Failed to build URL from PG* vars, will use malformed URL (will likely fail)")
    DATABASES["default"] = dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)
else:
    logger.info("No DATABASE_URL found, attempting to build from PG* vars")
    built = _build_db_from_pg_env()
    if built:
        DATABASES["default"] = dj_database_url.parse(built, conn_max_age=600, ssl_require=True)
        logger.info("Successfully configured database from PG* vars")
    else:
        logger.warning("No database configuration found, using default SQLite")

# Cole o seu link GIGANTE do Railway entre as aspas abaixo para forçar manualmente, se necessário:
# DATABASES['default'] = dj_database_url.parse("postgresql://<user>:<pass>@<host>:<port>/<db>", conn_max_age=600, ssl_require=True)


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"  # Você pode mudar para 'pt-br' se quiser

TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
# Celery / Redis configuration (optional; defaults if not provided)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Onde o Django vai reunir os arquivos estáticos no deploy
STATIC_ROOT = BASE_DIR / "staticfiles"

# Diretórios onde Django procura por arquivos estáticos em desenvolvimento
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Media (user-uploaded files)
# Em desenvolvimento, os arquivos serão servidos via `django.views.static.serve`.
# Em produção (Railway/Gunicorn), recomenda-se usar um storage externo (ex.: S3)
# ou montar um volume persistente e servir via NGINX. WhiteNoise não serve MEDIA.
MEDIA_URL = "/media/"


# Armazenamento de mídia: sempre usar FileSystemStorage
if os.environ.get('PERSIST_MEDIA_PATH'):
    MEDIA_ROOT = Path(os.environ.get('PERSIST_MEDIA_PATH'))
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    logger = __import__('logging').getLogger(__name__)
    logger.info(f"✅ Usando volume persistente em: {MEDIA_ROOT}")
else:
    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    logger = __import__('logging').getLogger(__name__)
    if not DEBUG:
        logger.warning("⚠️ AVISO: Usando armazenamento local em produção. Arquivos podem ser perdidos!")
        logger.warning("Configure PERSIST_MEDIA_PATH para produção.")

# Algoritmo de compressão e cache do WhiteNoise
# Use manifest storage only in production; in development, use regular storage
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Form data limits - Increased to handle bulk operations with many records
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000  # Default is 1000, increased for bulk deletion with many items

# Configurações de Login e Redirecionamento
LOGIN_URL = "login"  # Avisa que sua URL se chama apenas 'login' e não 'accounts/login'
LOGIN_REDIRECT_URL = "/"  # Redireciona para dashboard após login bem-sucedido
LOGOUT_REDIRECT_URL = "login"  # Para onde vai depois de sair

# --- Production security settings ---
if not DEBUG:
    # Protect cookies — useful on HTTPS deploys
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    # Railway já gerencia SSL/HTTPS no proxy, então não precisamos forçar redirect aqui
    SECURE_SSL_REDIRECT = False
    X_FRAME_OPTIONS = "DENY"
else:
    # Development settings - allow iframes for PDF preview
    X_FRAME_OPTIONS = "SAMEORIGIN"

# ==============================================================================
# EMAIL CONFIGURATION - Fase 5: Export and Scheduled Reports
# ==============================================================================
# Configure email backend for sending reports and alerts
# Default: console backend for development (logs emails instead of sending)
# Options: smtp.EmailBackend (Gmail), sendgrid, AWS SES, etc

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", 
    "django.core.mail.backends.console.EmailBackend"  # Development default
)

# Gmail SMTP Configuration (if using EMAIL_BACKEND with smtp)
# Requires: Gmail account with App Password (not regular password)
# How to get App Password: https://myaccount.google.com/apppasswords
if "smtp" in EMAIL_BACKEND:
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        import warnings
        warnings.warn(
            "Email credentials not configured. "
            "Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in environment variables. "
            "Emails will not be sent."
        )

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@calibraweb.com")

# Email recipients for Phase 5 tasks (comma-separated)
REPORT_EMAIL_TO = [
    email.strip() 
    for email in os.getenv("REPORT_EMAIL_TO", "admin@calibraweb.com").split(",")
    if email.strip()
]

ALERT_EMAIL_TO = [
    email.strip() 
    for email in os.getenv("ALERT_EMAIL_TO", "admin@calibraweb.com").split(",")
    if email.strip()
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}

# ============================================================================
# CACHE CONFIGURATION - Fase 6 Task #3
# ============================================================================

from config.cache_settings import CACHES, SESSION_ENGINE

# Redis cache backends (multiple caches for different purposes)
CACHES = CACHES

# Use Redis for sessions (faster than database)
SESSION_ENGINE = SESSION_ENGINE

import os
from urllib.parse import urlparse
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/


# SECURITY WARNING: don't run with debug turned on in production!
# Default is False (safer). In dev set DEBUG='True' in the environment.

DJANGO_ENV = os.environ.get("DJANGO_ENV", "").strip().lower()


def _is_platform_runtime() -> bool:
    # Best-effort detection: prevents accidental local/dev behavior in hosted envs.
    return any(
        os.environ.get(key)
        for key in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_STATIC_URL",
            "RENDER",
            "RENDER_SERVICE_ID",
            "DYNO",
        )
    )


IS_LOCAL_ENV = DJANGO_ENV in {"local", "dev", "development"}
if not IS_LOCAL_ENV and not _is_platform_runtime():
    # Convenience fallback for true local runs when DJANGO_ENV isn't set.
    IS_LOCAL_ENV = any(
        h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1")
        for h in ("localhost", "127.0.0.1")
    )

DEBUG = (os.environ.get("DEBUG", "False") == "True") or IS_LOCAL_ENV

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

# Configure ALLOWED_HOSTS via environment variable (comma-separated), default to localhost for development.
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,0.0.0.0").split(",")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

# Ensure ALLOWED_HOSTS is not empty
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]


# Configuração necessária para o formulário de login funcionar no Railway (HTTPS) e em desenvolvimento
csrf_origins = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", 
    "https://*.railway.app,https://*.up.railway.app,http://localhost:8000,http://127.0.0.1:8000,http://localhost:18000,http://127.0.0.1:18000"
).split(",")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins if origin.strip()]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Autenticação em duas etapas (2FA)
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "two_factor.plugins.phonenumber",
    
    # Novos módulos modulares (ATIVADOS - Phase 9 modularization)
    "core.apps.CoreConfig",
    "organization.apps.OrganizationConfig",
    "rh.apps.RhConfig",
    "metrologia.apps.MetrologiaConfig",
    "procedures.apps.ProceduresConfig",  # Unificação de training + procurements
    "documents.apps.DocumentsConfig",
    "shared.apps.SharedConfig",
    "fornecedores.apps.FornecedoresConfig",
    "acoes.apps.AcoesConfig",  # Ações Corretivas/Preventivas
    "auditoria.apps.AuditoriaConfig",
    "insumos.apps.InsumosConfig",
    # Módulo legado (compatibilidade - mantém 3 cross-app models: SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob)
    "qms",
    "training",  # Adicionado para compatibilidade com dashboard de gráficos
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
    "django_otp.middleware.OTPMiddleware",  # Middleware para 2FA
    "django.contrib.messages.middleware.MessageMiddleware",
    "shared.middleware.TwoFactorRequiredMiddleware",  # Força ativação do 2FA (após messages)
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
                "shared.context_processors.nav_notifications",
                "shared.context_processors.template_variants",
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


def _is_railway_runtime() -> bool:
    """Best-effort detection of Railway runtime."""
    return any(
        os.environ.get(key)
        for key in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_STATIC_URL",
        )
    )


def _is_railway_internal_db_url(url: str) -> bool:
    """True when DATABASE_URL points to Railway internal network host."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    hostname = hostname.lower()
    return hostname.endswith(".railway.internal") or hostname == "railway.internal"

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

# If a Railway-internal hostname leaks into local env, it will break local DNS.
# In that case, fall back to SQLite unless explicitly forced.
allow_internal = os.environ.get("ALLOW_RAILWAY_INTERNAL_DB", "").lower() in ("1", "true", "yes")
if database_url and _is_railway_internal_db_url(database_url) and not _is_railway_runtime() and not allow_internal:
    logger.warning(
        "Detected Railway-internal DATABASE_URL outside Railway runtime; "
        "ignoring it and falling back to SQLite. "
        "Set ALLOW_RAILWAY_INTERNAL_DB=true to force." 
    )
    database_url = None

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

# Celery / Redis configuration - Build URL robustly
def _build_redis_url():
    """Build Redis URL from Railway environment variables or fallback to defaults."""
    
    # First try: Direct REDIS_URL (Railway provides this)
    redis_url = os.getenv("REDIS_URL")
    if redis_url and "${" not in redis_url and "%24%7B" not in redis_url:
        return redis_url
    
    # Second try: Build from individual components (Railway Railway Redis)
    redis_host = os.getenv("REDIS_HOST", "")
    redis_port = os.getenv("REDIS_PORT", "")
    redis_password = os.getenv("REDIS_PASSWORD", "")
    
    if redis_host and redis_port:
        try:
            redis_port = int(redis_port)  # Ensure it's a number
            if redis_password:
                return f"redis://default:{redis_password}@{redis_host}:{redis_port}/0"
            else:
                return f"redis://{redis_host}:{redis_port}/0"
        except (ValueError, TypeError):
            pass  # Fall through to default
    
    # Third try: CELERY_BROKER_URL (if explicitly set)
    celery_broker = os.getenv("CELERY_BROKER_URL")
    if celery_broker and "${" not in celery_broker and "%24%7B" not in celery_broker:
        return celery_broker
    
    # Default: Local Redis
    return "redis://localhost:6379/0"

CELERY_BROKER_URL = _build_redis_url()
# Also build result backend from scratch (ignore broken CELERY_RESULT_BACKEND env var)
CELERY_RESULT_BACKEND = _build_redis_url()

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"

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
    logger = __import__('logging').getLogger(__name__)

    # Auto-detect common production mount points used by Railway and containers.
    # If one is available, prefer it even when PERSIST_MEDIA_PATH is not explicitly set.
    candidate_media_roots = [Path("/data/media"), Path("/app/media")]
    detected_media_root = next(
        (
            candidate
            for candidate in candidate_media_roots
            if candidate.exists() or candidate.parent.exists()
        ),
        None,
    )

    if (not DEBUG) and detected_media_root:
        try:
            detected_media_root.mkdir(parents=True, exist_ok=True)
            MEDIA_ROOT = detected_media_root
            DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
            logger.info(f"✅ Usando volume persistente (auto-detectado) em: {MEDIA_ROOT}")
        except Exception:
            MEDIA_ROOT = BASE_DIR / "media"
            MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
            DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
            logger.warning("⚠️ AVISO: Usando armazenamento local em produção. Arquivos podem ser perdidos!")
            logger.warning("Configure PERSIST_MEDIA_PATH para produção.")
    else:
        MEDIA_ROOT = BASE_DIR / "media"
        MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
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
LOGIN_URL = "two_factor:login"  # Redireciona para login com 2FA
LOGIN_REDIRECT_URL = "/"  # Redireciona para dashboard após login bem-sucedido
LOGOUT_REDIRECT_URL = "two_factor:login"  # Para onde vai depois de sair

# Configurações do Two-Factor Authentication (2FA)
TWO_FACTOR_PATCH_ADMIN = True  # Adiciona 2FA ao admin
TWO_FACTOR_CALL_GATEWAY = None  # Desabilita chamadas telefônicas (usar apenas TOTP/SMS)
TWO_FACTOR_SMS_GATEWAY = None  # Configurar gateway SMS se necessário
TWO_FACTOR_TOTP_DIGITS = 6  # Número de dígitos do código TOTP
TWO_FACTOR_LOGIN_TIMEOUT = 600  # Timeout em segundos (10 minutos)

# --- Security settings ---
# Detectar se está em ambiente local (localhost/127.0.0.1)
IS_LOCAL = any(host in ALLOWED_HOSTS for host in ['localhost', '127.0.0.1', '0.0.0.0', 'testserver'])

if not DEBUG and not IS_LOCAL:
    # Production security settings (HTTPS only)
    # Assume TLS terminates at the platform proxy (Railway/Render) and trust forwarded proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in ("1", "true", "yes")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    X_FRAME_OPTIONS = "DENY"
else:
    # Development/Local settings - allow HTTP
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = False  # Allow JavaScript access in development
    SESSION_COOKIE_SAMESITE = 'Lax'  # Lax for development to allow cross-origin
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access in development
    CSRF_COOKIE_SAMESITE = 'Lax'  # Lax for development to allow form submissions
    X_FRAME_OPTIONS = "SAMEORIGIN"  # allow iframes for PDF preview

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

from config.cache_settings import CACHES

# Redis cache backends (multiple caches for different purposes)
CACHES = CACHES

# ============================================================================
# SESSION CONFIGURATION
# ============================================================================

# In DEBUG mode: Always use database sessions (no Redis dependency)
# In production: Use database sessions for reliability
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_CACHE_ALIAS = 'default'

# Store CSRF token in session instead of cookie for better security and compatibility
CSRF_USE_SESSIONS = True

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
    raise ImproperlyConfigured("SECRET_KEY is required. Set it in the environment (see .env.example)")

# SECURITY WARNING: don't run with debug turned on in production!
# Default is False (safer). In dev set DEBUG='True' in the environment.
DEBUG = os.environ.get("DEBUG", "False") == "True"

# Configure ALLOWED_HOSTS via environment variable (comma-separated), default empty list.
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]

# In development you may explicitly set DEBUG=True and still require SECRET_KEY above.
# No implicit insecure fallbacks are provided anymore.
if not ALLOWED_HOSTS and not DEBUG:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set (comma-separated) in production.")
if DEBUG and not ALLOWED_HOSTS:
    # Development convenience: allow localhost
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


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
    "qms",
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
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
# Se o Railway injetar a variável DATABASE_URL, o Django troca para PostgreSQL automaticamente
if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config(conn_max_age=600, ssl_require=True)

    # Cole o seu link GIGANTE do Railway entre as aspas abaixo:
# DATABASES['default'] = dj_database_url.parse("postgresql://postgres:nArNnTKgOHhWttgLSJrnruMjJtaeSrZI@interchange.proxy.rlwy.net:54683/railway", conn_max_age=600, ssl_require=True)


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

# Algoritmo de compressão e cache do WhiteNoise
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configurações de Login e Redirecionamento
LOGIN_URL = "login"  # Avisa que sua URL se chama apenas 'login' e não 'accounts/login'
LOGIN_REDIRECT_URL = (
    "home"  # Para onde vai depois de logar (vi que você tem uma url chamada 'home')
)
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

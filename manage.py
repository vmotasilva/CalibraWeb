#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_local_env() -> bool:
    env = os.environ.get("DJANGO_ENV", "").strip().lower()
    return env in {"local", "dev", "development"}


def _is_platform_runtime() -> bool:
    # Best-effort detection: prevents accidental local behavior in hosted envs.
    return any(
        os.environ.get(key)
        for key in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT",
            "RENDER",
            "RENDER_SERVICE_ID",
            "DYNO",
        )
    )


def main():
    """Run administrative tasks."""
    env_path = os.path.join(BASE_DIR, ".env")
    env_local_path = os.path.join(BASE_DIR, ".env.local")

    # Only load file-based env in explicit local dev.
    # In hosted runtimes (Railway/Render/etc), configuration must come from env vars.
    if _is_local_env() and not _is_platform_runtime():
        if os.path.exists(env_path):
            load_dotenv(env_path)
        if os.path.exists(env_local_path):
            load_dotenv(env_local_path, override=True)

    default_settings = "config.settings_local" if _is_local_env() else "config.settings"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)

    # Local dev safety: don't require Redis/Celery broker to be running.
    # Set FORCE_REDIS=true if you explicitly want to use Redis locally.
    if default_settings == "config.settings_local":
        force_redis = os.environ.get("FORCE_REDIS", "").lower() in ("1", "true", "yes")
        if not force_redis:
            os.environ["CELERY_BROKER_URL"] = "memory://"
            os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

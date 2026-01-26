Security cleanup recommendations
=================================

I found sensitive artifacts currently present or likely to be present in this repository (e.g. committed virtual environments, database files, certificate PDFs, or hard-coded secrets). To avoid accidentally exposing secrets and personal data, follow these steps.

Quick actions you can run locally (recommended):

1) Add `.gitignore` (already added in this repo) to stop checking in local env, DB and generated files.

2) Remove files from the index (keeps them locally but removes in git history):

   # Windows PowerShell
   git rm --cached -r venv
   git rm --cached db.sqlite3
   git rm --cached -r certificados
   git commit -m "chore: remove sensitive files from git index and add .gitignore"

3) Rewrite git history to purge sensitive files from all commits (optional but strongly recommended):

   - Using BFG Repo Cleaner (easier):
     - Install BFG (https://rtyley.github.io/bfg-repo-cleaner/)
     - Example: bfg --delete-folders '{venv,certificados}' --delete-files db.sqlite3 --no-blob-protection
     - Then follow with: git reflog expire --expire=now --all && git gc --prune=now --aggressive

   - Using git filter-repo (recommended over git-filter-branch):
     - pip install git-filter-repo
     - Example: git filter-repo --invert-paths --paths venv --paths db.sqlite3 --paths certificados

4) Rotate secrets / credentials after purge:
   - If SECRET_KEY, admin passwords, API keys or other secrets were committed earlier, rotate them in your services immediately.

6) How to generate a new Django SECRET_KEY locally
   - You can use the provided helper script:

     ```powershell
     python scripts/generate_secret_key.py > .env
     ```

     Then set the environment variable in your deployment environment (Railway / Heroku / CI secrets) using the value from the generated file.

7) Reset admin/passwords (recommended)
   - If you had an exposed admin user (e.g. `admin` with a weak password), rotate/reset that user immediately.
   - Example using Django management command to set a new password (interactive):

     ```powershell
     python manage.py changepassword <admin_username>
     ```

   - Or set a new password via an environment-driven script (careful to avoid writing secrets into git).

5) Keep sensitive files out of repo going forward — use artifact storage or secure object storage (S3), or `django-storages` for uploaded files.

If you want, I can perform safe removals of files here in the repo (git rm and commit), and add a history-cleaning script — tell me to proceed and I will continue with the next steps in the plan.

---

Production Deployment & Environment Variables
=============================================

Essential variables (store in Railway / container secrets, never commit actual values):

SECRET_KEY  Django secret (generate with: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`)
DEBUG       Should be `False` in production
ALLOWED_HOSTS Comma separated domains (no wildcards in prod)
DATABASE_URL Postgres connection string (Railway/Cloud provider)
REDIS_URL   Redis URL for Celery broker & result backend (e.g. Upstash/Railway Redis)
CELERY_BROKER_URL  Usually same as REDIS_URL
CELERY_RESULT_BACKEND Same as REDIS_URL (or use database/AMQP if preferred)
TIME_ZONE   e.g. `America/Sao_Paulo`
CSRF_TRUSTED_ORIGINS e.g. `https://your.domain.com`

Quick deploy (Railway Nixpacks already configured via `railway.toml`):
1. Set secrets (above) in Railway project settings
2. Push code (`git push origin main`)
3. Railway build runs startCommand: migrations + collectstatic + gunicorn
4. (Optional) Add additional services for Celery worker & beat using Procfile entries (web / worker / beat)

Docker (alternative deploy path):
```bash
docker build -t calibraweb:prod .
docker run -d --env-file .env -p 8000:8000 calibraweb:prod
```

Celery processes (if using Redis):
```bash
celery -A config.celery.app worker -l info --concurrency=4
celery -A config.celery.app beat -l info
```

Gunicorn manual run (without Docker):
```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Security checklist (supplement):
- Rotate SECRET_KEY if ever leaked
- Enforce HTTPS at platform/CDN level
- Restrict admin access (IP allowlist / VPN if possible)
- Monitor `/healthz` endpoint and set alerts
- Keep dependencies patched (monthly scan)

Refer to `.env.example` for a minimal template.

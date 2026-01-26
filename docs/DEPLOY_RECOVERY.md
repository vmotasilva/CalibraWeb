CalibraWeb — Recovery and quick restore guide
=============================================

If your deployed site is down, follow these steps to bring it back. This document assumes you can run commands on your hosting environment (Railway/Heroku/SSH container), or use the provider console.

1) Check the provider logs
   - Railway / Heroku / other: open the web dashboard and inspect recent logs (errors are usually printed, like missing SECRET_KEY or DB connection problems).

2) Common causes & quick fixes
   - Missing SECRET_KEY (this repo now requires SECRET_KEY for production): set SECRET_KEY in your environment variables.
     - Example (Railway / Heroku env var): set SECRET_KEY to a secure value (use `scripts/generate_secret_key.py` locally to generate).

   - No database or DB misconfigured:
     - If you use PostgreSQL (DATABASE_URL), verify env var DATABASE_URL is present and has correct credentials.
     - If using sqlite (not recommended for production), the file `db.sqlite3` may have been removed from repo history — you'll need to recreate DB with migrations or restore backups.

3) Quick restore commands (run in deploy console or SSH into container)


   # Quick diagnostic (safe read-only checks)
   python scripts/bootstrap_deploy.py --diagnose

   # Run all migrations (or use --apply to migrate + optionally create admin)
   python manage.py migrate

   # Optionally run the helper to auto-apply migrations and create admin non-interactively
   ADMIN_USERNAME=admin ADMIN_EMAIL=you@example.com ADMIN_PASSWORD='S3cure!' python scripts/bootstrap_deploy.py --apply

   # Or run interactively
   python manage.py createsuperuser

4) If you removed SQLite from repository history and you relied on it in production
   - If you have a database backup, restore the file into the container, then run migrations.
   - If you don't have backups: run migrations to create a fresh schema and whichever data importers you have.

5) After restore: rotate secrets
   - Always rotate SECRET_KEY and any credentials which were exposed prior to the purge.

6) Monitoring + health-check
   - A /healthz endpoint has been added to the app; configure your host to probe it and auto-restart on failures.
   - Consider adding process managers (systemd / supervisor) or platform health checks (Railway/Heroku) to auto-restart.

7) If you'd like, I can help remote: check logs, set env vars, run migrations or create admin — you'll need to provide host/console access or do these steps in your provider console and I can give exact commands.

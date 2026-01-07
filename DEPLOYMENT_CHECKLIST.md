# CALIBRAWEB - DEPLOYMENT CHECKLIST
## Production Deployment Guide

**Last Updated**: December 8, 2025  
**Application**: CalibraWeb - Calibration & Quality Management System  
**Framework**: Django 5.2 with SQLite (dev) / PostgreSQL (production)

---

## PRE-DEPLOYMENT VERIFICATION ✅

### Code & Configuration
- [ ] All code committed to git
- [ ] No uncommitted changes (`git status` returns clean)
- [ ] Latest code pulled from main/production branch
- [ ] All tests passing locally
- [ ] `python manage.py check` returns 0 issues
- [ ] `python manage.py check --deploy` returns acceptable warnings only

### Static Files
- [ ] Run `python manage.py collectstatic --noinput`
- [ ] Verify `staticfiles/` directory exists with 505+ files
- [ ] Verify `staticfiles/staticfiles.json` manifest created
- [ ] Test admin interface styling loads correctly

### Database
- [ ] Backup current production database (if upgrading)
- [ ] Run `python manage.py makemigrations` (should return "No changes")
- [ ] Review pending migrations with `python manage.py migrate --plan`
- [ ] Test migrations on local database first

### Security
- [ ] Run `python security_audit.py`
- [ ] All critical checks pass
- [ ] Review warnings and address if needed
- [ ] Verify no hardcoded secrets in codebase
- [ ] Check `.env` is in `.gitignore`

### Testing
- [ ] Run `python test_production_env.py`
- [ ] All 10 tests pass
- [ ] Run full test suite: `python manage.py test`
- [ ] At least 31+ tests passing, 5 expected errors acceptable

---

## ENVIRONMENT SETUP

### Required Environment Variables

For production deployment, set these environment variables:

```env
# CRITICAL - MUST BE SET
SECRET_KEY=<generate-new-secure-50-char-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# DATABASE (choose one approach)
DATABASE_URL=postgres://user:password@hostname:5432/calibraweb
# OR
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=calibraweb
# DB_USER=postgres
# DB_PASSWORD=password
# DB_HOST=localhost
# DB_PORT=5432

# CACHE (optional but recommended)
REDIS_URL=redis://:password@hostname:6379/0

# CELERY (if using background tasks)
CELERY_BROKER_URL=redis://:password@hostname:6379/0
CELERY_RESULT_BACKEND=redis://:password@hostname:6379/0

# EMAIL CONFIGURATION
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# SECURITY
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
TIME_ZONE=America/Sao_Paulo

# OPTIONAL
SENTRY_DSN=<sentry-project-dsn>
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_STORAGE_BUCKET_NAME=<bucket>
```

### How to Set Environment Variables

**Option 1: Railway (Recommended)**
1. Go to Railway dashboard
2. Select your project
3. Go to Variables
4. Add each variable from the list above
5. Deploy automatically triggers

**Option 2: .env File (Traditional VPS)**
1. Create `.env` file in project root
2. Copy template from `.env.example`
3. Fill in production values
4. Never commit to git (already in .gitignore)
5. Application loads on startup

**Option 3: Docker/Container**
1. Set environment variables in container runtime
2. Or mount `.env` as secret volume
3. Ensure secrets are not in Dockerfile

**Option 4: CI/CD Pipeline**
1. Set secrets in GitHub/GitLab settings
2. Pipeline injects at deployment time
3. Never logged or visible in CI logs

---

## GENERATING SECURE SECRET_KEY

Run this command locally (NOT in production):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Output example:
```
fj_2@e-$&9@!x#%^q$%^&*()_+|}{":?><,./;'[]=-0987654321
```

Copy this output to production environment as `SECRET_KEY`.

---

## STEP-BY-STEP DEPLOYMENT

### 1. Prepare Repository (Before Deployment)
```bash
# Clone or pull latest code
git clone https://github.com/vmotasilva/CalibraWeb.git
cd CalibraWeb

# Verify you're on correct branch
git branch -v
# Should show: * phase-9-full-modularization (or main after merge)

# Pull latest changes
git pull origin main
```

### 2. Set Up Python Environment
```bash
# Create virtual environment (if not exists)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

### 3. Set Environment Variables

See "Environment Setup" section above for your deployment platform.

### 4. Verify Application Configuration
```bash
# Check basic configuration
python manage.py check

# Check production-specific configuration
python manage.py check --deploy

# Run security audit
python security_audit.py

# Run production environment test
python test_production_env.py
```

### 5. Prepare Database

**First Time Deployment:**
```bash
# Create database (if using PostgreSQL)
createdb calibraweb
# Or use PostgreSQL admin interface

# Apply migrations
python manage.py migrate

# Create superuser for admin
python manage.py createsuperuser
```

**Upgrading Existing Installation:**
```bash
# Backup current database BEFORE proceeding
# (Platform-specific, see below)

# Apply migrations
python manage.py migrate

# Verify database
python manage.py dbshell
# Type: \dt  (PostgreSQL) to see all tables
# Or use similar command for your database
```

**Database Backup Procedures:**

Railway PostgreSQL backup:
```bash
# Automatic backups enabled in Railway
# Manual backup:
pg_dump postgres://user:pass@host:5432/db > backup.sql
```

Render PostgreSQL backup:
```bash
# Use Render dashboard backup feature
# Or use pg_dump command
```

### 6. Collect Static Files
```bash
# Collect all static files
python manage.py collectstatic --noinput

# Verify collection
ls -la staticfiles/
# Should show: 505+ files
```

### 7. Run Test Suite
```bash
# Run all tests
python manage.py test

# Or specific test suites
python manage.py test core rh organization metrologia procurements training qms

# Expected result: 31+ tests passing, max 5 failures (expected)
```

### 8. Start Application

**Option A: Gunicorn (Recommended for Production)**
```bash
# Install gunicorn
pip install gunicorn

# Run application
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class sync \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -
```

**Option B: Django Development Server (Testing Only)**
```bash
python manage.py runserver 0.0.0.0:8000
```

**Option C: Railway Deployment**
```bash
# Uses Procfile automatically:
# web: gunicorn config.wsgi
# Just deploy and Railway runs it
```

**Option D: Docker**
```bash
# Build image
docker build -t calibraweb:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -e SECRET_KEY=<your-key> \
  -e DEBUG=False \
  -e DATABASE_URL=postgres://... \
  calibraweb:latest
```

### 9. Verify Deployment
```bash
# Check application is running
curl http://localhost:8000/admin/

# Check static files are served
curl http://localhost:8000/static/admin/css/base.css

# Verify admin login
# Go to http://localhost:8000/admin/
# Login with superuser credentials
```

### 10. Set Up Monitoring & Logs

**Option A: Application Logs**
```bash
# View application logs (varies by platform)
# Railway: View in dashboard
# VPS: Check /var/log/django.log (if configured)
```

**Option B: Error Tracking (Optional)**
```bash
# If using Sentry:
# 1. Create account at sentry.io
# 2. Create new project for Django
# 3. Copy DSN to SENTRY_DSN environment variable
# 4. Application automatically sends errors

# Test error tracking:
# curl http://localhost:8000/admin/trigger-error/  (if implemented)
```

**Option C: Uptime Monitoring**
```bash
# Use external monitoring service (Uptime Robot, etc)
# Configure to check: http://yourdomain.com/admin/
# Alert if status code != 200
```

---

## DATABASE MIGRATION PROCEDURE

### Safe Migration Process

1. **Before Migration:**
   ```bash
   # Backup database
   pg_dump postgres://connection-string > backup_$(date +%Y%m%d_%H%M%S).sql
   
   # Verify backup created
   ls -la backup_*.sql
   ```

2. **Test Migration Locally:**
   ```bash
   # Restore backup to local database
   psql -U postgres -d test_db < backup.sql
   
   # Run migrations
   python manage.py migrate --database=test_db
   
   # Verify success
   python manage.py check --database=test_db
   ```

3. **In Production:**
   ```bash
   # Stop application (optional, Django handles migrations safely)
   
   # Run migrations
   python manage.py migrate
   
   # Restart application
   ```

4. **Verify Success:**
   ```bash
   # Check application still works
   curl http://yourdomain.com/admin/
   
   # Check application logs for errors
   tail -f /var/log/django.log
   ```

### Rollback Procedure (If Needed)

```bash
# If migration fails, restore from backup
psql -U postgres -d calibraweb < backup_YYYYMMDD_HHMMSS.sql

# OR use Django reverse migration (if available)
python manage.py migrate <app> <previous_migration_number>
```

---

## POST-DEPLOYMENT VERIFICATION ✅

After deployment, verify everything is working:

### Immediate Checks (First 5 minutes)
- [ ] Application loads at yourdomain.com
- [ ] Admin interface accessible at yourdomain.com/admin/
- [ ] Can log in with credentials
- [ ] No 500 errors in logs
- [ ] Static files (CSS/JS) loading correctly

### Functional Tests (First Hour)
- [ ] Navigate admin dashboard
- [ ] Check all 27 models listed in admin
- [ ] Create test record in each app
- [ ] Verify cross-app relationships
- [ ] Test filtering and searching
- [ ] Verify forms work correctly

### Performance Tests (First Day)
- [ ] Response times reasonable (< 500ms for page load)
- [ ] Admin loads quickly
- [ ] No database query timeouts
- [ ] No memory leaks (check process memory)
- [ ] Static files served efficiently

### Security Verification (First Day)
- [ ] HTTPS enabled and working
- [ ] SSL certificate valid
- [ ] Security headers present (check with curl)
- [ ] Login form CSRF token present
- [ ] No debug information in error pages

---

## TROUBLESHOOTING DEPLOYMENT

### Issue: Database Connection Error
**Symptoms**: "psycopg2.OperationalError: could not connect to server"

**Solutions:**
```bash
# 1. Verify DATABASE_URL is set correctly
echo $DATABASE_URL

# 2. Test database connection
python manage.py dbshell

# 3. Check PostgreSQL service is running
pg_isready -h localhost -p 5432

# 4. Verify credentials in DATABASE_URL
# Format: postgres://user:password@host:port/dbname
```

### Issue: Static Files Not Loading
**Symptoms**: Admin CSS/images missing, browser shows 404s

**Solutions:**
```bash
# 1. Verify collectstatic was run
ls -la staticfiles/ | wc -l  # Should show 505+ files

# 2. Verify STATIC_ROOT is correct
python -c "from django.conf import settings; print(settings.STATIC_ROOT)"

# 3. Check STATIC_URL configuration
python -c "from django.conf import settings; print(settings.STATIC_URL)"

# 4. Restart application and clear browser cache
```

### Issue: Admin Login Not Working
**Symptoms**: Login form submits but returns to login page

**Solutions:**
```bash
# 1. Verify superuser exists
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(is_superuser=True).count()
# Should return > 0

# 2. If not, create superuser
python manage.py createsuperuser

# 3. Verify CSRF settings
# CSRF_TRUSTED_ORIGINS should include yourdomain.com
python -c "from django.conf import settings; print(settings.CSRF_TRUSTED_ORIGINS)"
```

### Issue: High Memory Usage
**Symptoms**: Application becomes slow, memory keeps growing

**Solutions:**
```bash
# 1. Check for database N+1 queries
# Use Django Debug Toolbar (dev) or django-silk

# 2. Enable query caching
# Set up Redis: REDIS_URL in environment

# 3. Optimize database queries
# See Phase 12: Performance Optimization

# 4. Restart application periodically
# Set up daily restart in cron/supervisor
```

### Issue: Secret Key Error on Startup
**Symptoms**: "ImproperlyConfigured: SECRET_KEY is required"

**Solutions:**
```bash
# 1. Verify SECRET_KEY is set in environment
echo $SECRET_KEY

# 2. If using .env file, verify it exists
ls -la .env

# 3. If using environment variables, verify they're loaded
env | grep SECRET_KEY

# 4. If using Railway, check Variables section
# Redeploy after adding SECRET_KEY
```

### Issue: Migrations Fail to Apply
**Symptoms**: "django.db.utils.OperationalError: relation does not exist"

**Solutions:**
```bash
# 1. Check migration status
python manage.py showmigrations

# 2. Run specific migration with verbosity
python manage.py migrate qms --verbosity 2

# 3. If table exists but Django doesn't know:
# Mark migration as applied without running
python manage.py migrate qms 0031 --fake

# 4. Last resort: drop and recreate database
# (WARNING: Deletes all data!)
dropdb calibraweb
createdb calibraweb
python manage.py migrate
```

---

## SCHEDULED MAINTENANCE

### Daily
- [ ] Monitor error logs
- [ ] Verify application is responsive
- [ ] Check database backups completed

### Weekly
- [ ] Review security logs
- [ ] Check for new Django security releases
- [ ] Verify backup integrity (test restore)

### Monthly
- [ ] Update dependencies
- [ ] Run security audit again
- [ ] Review application performance
- [ ] Clean up old logs

### Quarterly
- [ ] Full security audit
- [ ] Load testing
- [ ] Database optimization
- [ ] Review and update documentation

---

## ROLLBACK PROCEDURE

If deployment fails and you need to revert:

### Option 1: Database Rollback Only
```bash
# Stop application
# Restore database from backup
psql -U postgres -d calibraweb < backup_YYYYMMDD.sql
# Restart application with previous version
# Application continues with old code but new database
```

### Option 2: Complete Rollback
```bash
# Stop application
# Revert git to previous commit
git revert HEAD

# Or checkout specific commit
git checkout <commit-hash>

# Restore database from backup
psql -U postgres -d calibraweb < backup_YYYYMMDD.sql

# Restart application
```

### Option 3: Blue-Green Deployment
```bash
# Keep two production environments
# Current (Blue) and New (Green)
# Deploy to Green first
# Test Green thoroughly
# Switch traffic to Green
# If issues, switch back to Blue
```

---

## ROLLBACK SAFETY CHECKLIST

Before rolling back:
- [ ] Note exact deployment time
- [ ] Note which migrations were new
- [ ] Verify backup file intact
- [ ] Have previous version code available
- [ ] Notify team of rollback plan

After rolling back:
- [ ] Verify application works
- [ ] Check database integrity
- [ ] Review error logs
- [ ] Document what went wrong
- [ ] Plan fix for next deployment attempt

---

## MONITORING & ALERTS

### Recommended Monitoring Setup

1. **Uptime Monitoring**: Uptime Robot
   - Check: http://yourdomain.com/admin/ every 5 minutes
   - Alert if down > 5 minutes

2. **Error Tracking**: Sentry
   - Capture all 500 errors
   - Alert on new error types
   - Integrate with Slack

3. **Performance Monitoring**: New Relic or DataDog
   - Monitor response times
   - Database query performance
   - Memory and CPU usage

4. **Log Aggregation**: Papertrail or LogRocket
   - Centralize all application logs
   - Easy searching and filtering
   - Archive for audit trail

5. **Database Monitoring**: Platform-specific
   - Railway: Built-in monitoring
   - Render: Built-in monitoring
   - VPS: Configure PostgreSQL monitoring

---

## DEPLOYMENT SUCCESS CRITERIA ✅

Deployment is successful when:

- ✅ Application loads without 500 errors
- ✅ Admin interface accessible and functional
- ✅ All 27 models visible in admin
- ✅ Can create/edit/delete records
- ✅ Static files loading (admin styled correctly)
- ✅ No console errors in browser
- ✅ Response times < 500ms for normal operations
- ✅ Database backups running automatically
- ✅ Error logging configured
- ✅ Monitoring/alerts active

---

## SUPPORT & ESCALATION

### If Deployment Fails

1. **Immediate**: Stop applying changes, verify no data loss
2. **Investigation**: Check logs, identify root cause
3. **Mitigation**: If critical, rollback to previous version
4. **Fix**: Address issue in development environment
5. **Testing**: Run all tests before re-deploying
6. **Re-deploy**: Follow deployment checklist again

### Emergency Contact Procedures

In case of emergency:
1. Contact DevOps team (if available)
2. Check application status page
3. Review error logs and recent changes
4. Document issue for post-incident review
5. Communicate status to users

---

## DEPLOYMENT SIGN-OFF

After successful deployment:

```
Deployment Date: _______________
Deployed By: _______________
Deployment Checklist: ✅ All items verified
Production Tests: ✅ All passing
Security Audit: ✅ No critical issues
Monitoring: ✅ Configured and alerting

Approved For Production: _______________
Signature: _______________
```

---

**Last Updated**: December 8, 2025  
**Next Review**: [After Phase 12 completion]  
**Emergency Contact**: [Contact information here]

---

*For questions or issues with deployment, refer to:*
- *PHASE_11_COMPLETION_SUMMARY.md - Detailed Phase 11 completion*
- *TROUBLESHOOTING.md - Common issues and solutions*
- *PROJECT_PROGRESS_REPORT.md - Overall project status*

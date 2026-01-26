# Phase 11: Static Files & Production Deployment

## Overview
After completing Phase 10 (views and admin configuration), Phase 11 focuses on preparing the application for production deployment.

## Current Status
- ✅ Phase 9 (Modularization): Complete - All 27 models distributed across 8 apps
- ✅ Phase 10 (Views & Admin): Complete - All admin interfaces configured, views validated
- ⏳ Phase 11 (Production): Ready to begin

## Phase 11 Tasks

### Task 1: Static Files Collection (30-45 min)

**Objective**: Prepare static files for production serving

**What to do**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Verify static files were collected
ls -la staticfiles/
```

**Check**:
- [ ] CSS files in place
- [ ] JavaScript files in place
- [ ] Admin static files (CSS, JS, images)
- [ ] No 404 errors when viewing admin

**Expected Result**:
- staticfiles/ directory populated
- All admin CSS/JS properly collected
- Admin interface styling intact

### Task 2: Production Settings Validation (45 min)

**Objective**: Ensure production configuration is correct

**Files to check**:
```
config/settings.py
config/settings_production.py (if exists)
.env or environment variables
```

**Validate**:
- [ ] DEBUG = False (production)
- [ ] ALLOWED_HOSTS configured properly
- [ ] Database credentials set via environment variables
- [ ] SECRET_KEY set via environment variables
- [ ] STATIC_URL and STATIC_ROOT configured
- [ ] MEDIA_URL and MEDIA_ROOT configured
- [ ] EMAIL settings configured
- [ ] LOGGING configured

**Security Checks**:
- [ ] No hardcoded secrets in settings.py
- [ ] Use environment variables for sensitive data
- [ ] CSRF_TRUSTED_ORIGINS configured
- [ ] SECURE_SSL_REDIRECT considered
- [ ] SESSION_COOKIE_SECURE = True (if using HTTPS)
- [ ] SECURE_HSTS_SECONDS configured

**Commands**:
```bash
# Test production settings
python manage.py check --deploy
```

### Task 3: Database Migration (30 min)

**Objective**: Prepare database for deployment

**Tasks**:
```bash
# Create a backup of current database (important!)
cp db.sqlite3 db.sqlite3.backup

# Show pending migrations
python manage.py showmigrations

# Create migration for any schema changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

**Verify**:
- [ ] All 11 migrations applied
- [ ] No migration conflicts
- [ ] Database is current with models
- [ ] Backup created successfully

**For PostgreSQL (production)**:
```bash
# Create PostgreSQL user and database
createuser calibra_user
createdb -O calibra_user calibra_db

# Run migrations on production database
python manage.py migrate --database=production
```

### Task 4: Environment Setup (30 min)

**Objective**: Configure environment variables for production

**Create .env file**:
```bash
# Django Settings
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=False
SECRET_KEY=<very-long-random-string>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=calibra_db
DATABASE_USER=calibra_user
DATABASE_PASSWORD=<secure-password>
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=<app-password>

# AWS S3 (if using for static/media files)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_STORAGE_BUCKET_NAME=<your-bucket>

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

**Protection**:
- [ ] .env file in .gitignore
- [ ] No secrets in git repository
- [ ] Environment variables loaded in settings.py

### Task 5: Testing in Production Mode (45 min)

**Objective**: Verify application works in production configuration

**Local Testing**:
```bash
# Set production settings
export DJANGO_SETTINGS_MODULE=config.settings

# Run with DEBUG=False
export DEBUG=False

# Run tests
python manage.py test --keepdb

# Check admin interface
python manage.py runserver
# Visit http://localhost:8000/admin/
```

**Tests to Verify**:
- [ ] All 27 models load in admin
- [ ] CSS/JS styling correct
- [ ] No static file 404 errors
- [ ] Forms work correctly
- [ ] Cross-app relationships display
- [ ] Search functionality works
- [ ] Filters work properly

**Performance Check**:
```bash
# Check slow queries
python manage.py debugsqlshell

# Test database performance
python manage.py test --debug-mode
```

### Task 6: Security Audit (1 hour)

**Objective**: Verify application is secure for production

**Commands**:
```bash
# Django security check
python manage.py check --deploy

# Check for common vulnerabilities
# Review settings.py against checklist
```

**Security Checklist**:
- [ ] DEBUG = False
- [ ] SECRET_KEY is strong and random
- [ ] Database password is secure
- [ ] No SQL injection vulnerabilities
- [ ] CSRF protection enabled
- [ ] XSS protection enabled
- [ ] Clickjacking protection enabled
- [ ] Content Security Policy considered
- [ ] HTTPS configured (production)
- [ ] SSL certificate valid
- [ ] Password hashing uses bcrypt or similar
- [ ] Admin interface protected
- [ ] API endpoints (if any) authenticated

### Task 7: Load Testing (Optional, 1-2 hours)

**Objective**: Ensure application can handle production load

**Tools**:
- Apache JMeter
- Locust
- wrk

**Test Scenarios**:
```python
# Simulate 100 concurrent users
# Each user makes 10 requests
# Measure response times
# Check for memory leaks
# Monitor database connections
```

**Expected Performance**:
- Average response time < 200ms
- 95th percentile < 500ms
- No memory growth over time
- Database connections stable

### Task 8: Documentation (30 min)

**Create deployment documentation**:
- [ ] Deployment checklist
- [ ] Environment variable guide
- [ ] Database backup procedure
- [ ] Recovery procedure
- [ ] Monitoring setup
- [ ] Log file locations
- [ ] Maintenance tasks

---

## Success Criteria for Phase 11

✅ Static files collected and serving correctly  
✅ Production settings validated (check --deploy passes)  
✅ Database migrations applied  
✅ Environment variables configured  
✅ All tests passing in production mode  
✅ Security audit passed  
✅ Admin interface fully functional  
✅ No static file errors or 404s  
✅ Documentation complete  

---

## Phase 11 Estimated Timeline

| Task | Estimate | Status |
|------|----------|--------|
| Static Files Collection | 30-45m | ⏳ Not started |
| Production Settings | 45m | ⏳ Not started |
| Database Migration | 30m | ⏳ Not started |
| Environment Setup | 30m | ⏳ Not started |
| Production Testing | 45m | ⏳ Not started |
| Security Audit | 1h | ⏳ Not started |
| Load Testing (Optional) | 1-2h | ⏳ Not started |
| Documentation | 30m | ⏳ Not started |
| **Total** | **5-8h** | |

---

## Getting Started with Phase 11

**First Steps**:

1. Check current production settings:
```bash
cat config/settings.py
```

2. Run deployment check:
```bash
python manage.py check --deploy
```

3. Collect static files:
```bash
python manage.py collectstatic --noinput
```

4. Test in production mode:
```bash
DEBUG=False python manage.py runserver
```

5. Check admin interface:
```bash
# Visit http://localhost:8000/admin/
```

---

## Deployment Checklist

Before deploying to production:

### Pre-Deployment
- [ ] All tests passing
- [ ] Django check --deploy passes
- [ ] Static files collected
- [ ] .env file created with all variables
- [ ] Database backup created
- [ ] Git repository clean
- [ ] No uncommitted changes

### Deployment
- [ ] Code pushed to production branch
- [ ] Environment variables set
- [ ] Database migrations applied
- [ ] Static files uploaded to CDN/S3 (if applicable)
- [ ] Application restarted
- [ ] Health check passing
- [ ] Admin interface accessible
- [ ] Monitoring enabled

### Post-Deployment
- [ ] Monitor error logs
- [ ] Check application performance
- [ ] Verify database backups
- [ ] Check static file delivery
- [ ] Monitor system resources
- [ ] Test all critical features

---

## Common Issues & Solutions

### Issue: Static files not loading
**Solution**: 
- Check STATIC_URL and STATIC_ROOT in settings
- Run collectstatic again
- Check web server configuration
- Verify file permissions

### Issue: Database connection error
**Solution**:
- Check DATABASE_* environment variables
- Test database credentials
- Verify database is running
- Check network connectivity

### Issue: SECRET_KEY not set
**Solution**:
- Generate new SECRET_KEY
- Set via environment variable
- Update .env file
- Restart application

### Issue: Admin interface CSS missing
**Solution**:
- Run collectstatic
- Check STATIC_ROOT directory
- Verify web server serving static files
- Check browser cache

---

## References

- Django Deployment Checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Django Security: https://docs.djangoproject.com/en/5.2/topics/security/
- Production Deployment: https://docs.djangoproject.com/en/5.2/howto/deployment/

---

**Ready to begin Phase 11 when you are!**

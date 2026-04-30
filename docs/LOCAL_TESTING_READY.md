# LOCAL TESTING - STEP BY STEP GUIDE

## Status: ✓ Server Running

Django development server is now running on **http://127.0.0.1:8000/**

---

## Admin Login Credentials

```
URL:      http://127.0.0.1:8000/admin/
Username: admin
Password: admin123
Email:    admin@calibra.com.br
```

---

## What You Can Test Now

### 1. Admin Dashboard
- Login with credentials above
- Manage users, collaborators, instruments
- View calibration history
- Manage training modules

### 2. Application Features
- Create new calibration records
- Import procedures
- Manage collaborators
- View hierarchy/sectors
- Check training assignments

### 3. Cache System
- Monitor cache performance in dashboard
- Test cache invalidation
- Verify cache warming
- Check multi-level caching

### 4. Database
- SQLite is default for local development
- All models are accessible
- Migrations already applied

---

## Running Tests Locally

### Run All Tests

```bash
python manage.py test qms --settings=config.settings_test -v 2
```

### Run Single Test

```bash
python manage.py test qms.tests.CeleryTasksTest.test_ping_task
```

### Expected Output

```
test_ping_task (qms.tests.CeleryTasksTest) ... ok
Ran 1 test in 0.XXs
OK
```

---

## Troubleshooting

### Server doesn't respond?
```bash
# Check if port 8000 is in use:
Get-NetTCPConnection -LocalPort 8000

# Use different port:
python manage.py runserver 8001
```

### Can't login?
```bash
# Reset password:
python manage.py shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.get(username='admin')
>>> u.set_password('admin123')
>>> u.save()
>>> exit()
```

### Database issues?
```bash
python manage.py migrate
python manage.py check
```

---

## Next Steps

1. ✓ Open http://127.0.0.1:8000/admin/
2. ✓ Login with admin/admin123
3. ✓ Explore application
4. ✓ Run tests with command above
5. ✓ Monitor cache dashboard
6. → When ready: Move to Staging (see STAGING_ACTION_PLAN.md)

---

## Development Environment

**Framework:** Django 5.0.14
**Database:** SQLite (default for local)
**Cache:** In-memory (LocalMemCache)
**Task Queue:** Celery 5.4.0 (eager mode)
**Redis:** Mock server on localhost:6379

**All dependencies installed and verified.**

---

Created: December 10, 2025
Status: Ready for testing

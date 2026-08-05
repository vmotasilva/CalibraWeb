# Local Testing Credentials

## Django Admin Access

**Superuser Account:**

- **Username:** admin
- **Password:** admin123
- **Email:** admin@calibra.com.br

## How to Start Local Server

### Option 1: Default Settings (SQLite + Mock Redis)

```bash
cd c:\CalibraWeb
python manage.py runserver
```

Expected output:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Option 2: Local Development Settings (In-Memory Cache)

```bash
cd c:\CalibraWeb
python manage.py runserver --settings=config.settings_local
```

Benefits:

- No Redis dependency needed
- Faster startup
- Perfect for development and testing

## Access Django Admin

1. Start the server (Option 1 or 2 above)
2. Open browser: http://127.0.0.1:8000/admin/
3. Login with credentials above
4. Test features:
   - User management
   - Calibration records
   - Training modules
   - Procedure import
   - Multi-level cache dashboard

---

## Run Tests Locally

### Option A: With In-Memory Cache (Recommended)

```bash
python manage.py test qms --settings=config.settings_test -v 2
```

**Expected Result:**
```
test_ping_task (qms.tests.CeleryTasksTest) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.XXs

OK
```

### Option B: With Redis

```bash
# Start mock Redis first (in another terminal)
python mock_redis_server.py

# Then run tests
python manage.py test qms --settings=config.settings.py -v 2
```

---

## Database Management

### Check Database Status

```bash
python manage.py dbshell
```

### Run Migrations

```bash
python manage.py migrate
```

### Create Test Data

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.create_superuser('testuser', 'test@test.com', 'testpass123')
>>> exit()
```

---

## Troubleshooting

### Issue: "No database configuration found"
**Solution:** This is normal for SQLite. Django auto-creates it. Just run migrations:
```bash
python manage.py migrate
```

### Issue: Redis connection error
**Solution:** Use local development settings:
```bash
python manage.py runserver --settings=config.settings_local
```

### Issue: Port 8000 already in use
**Solution:** Use different port:
```bash
python manage.py runserver 8001
```

---

## Testing Checklist

- [ ] Django admin login works
- [ ] Create new calibration record
- [ ] Create new training module
- [ ] Import procedures
- [ ] Check cache invalidation
- [ ] Monitor cache dashboard
- [ ] Run test suite (all tests pass)
- [ ] Database migrations applied
- [ ] Static files working
- [ ] Media files accessible

---

## Performance Testing

### Local Cache Performance

```bash
python manage.py runserver --settings=config.settings_local
# Access http://127.0.0.1:8000/cache-dashboard/
# Monitor cache hits/misses in real-time
```

### Celery Task Testing

```bash
# Terminal 1: Django server
python manage.py runserver --settings=config.settings_local

# Terminal 2: Celery worker (eager mode - synchronous)
python manage.py celery worker --loglevel=info

# Terminal 3: Test tasks
python manage.py shell
>>> from qms.tasks import warm_cache
>>> result = warm_cache()
>>> print(result)
```

---

## Environment Variables

Current settings in `.env.local`:

```env
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CACHE_BACKEND=locmem
```

To override, edit `.env.local` and reload Django.

---

## Next Steps

1. ✓ Start Django server
2. ✓ Login to admin (admin/admin123)
3. ✓ Create test data
4. ✓ Run test suite
5. → Monitor cache dashboard
6. → Validate all features working
7. → Ready for staging deployment (Opção 2)

---

**Created:** December 10, 2025
**Status:** Ready for local testing
**Git:** Committed and ready

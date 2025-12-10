# LOCAL TESTING CREDENTIALS

## Superuser Account (for Django Admin & Testing)

```
Username: admin
Email: admin@calibraweb.local
Password: TestPass123456!@#
```

## How to Use These Credentials

### 1. **Django Admin Panel**
   - Start Django server: `python manage.py runserver`
   - Open: http://127.0.0.1:8000/admin/
   - Login with credentials above
   - Create/manage users, permissions, settings

### 2. **Cache Dashboard**
   - Start: `python manage.py cache_dashboard --live --interval 2`
   - Open: http://127.0.0.1:8000/dashboard/
   - Monitor cache metrics in real-time
   - View hit/miss ratios, memory usage

### 3. **API Testing**
   - Use credentials with your API client
   - Example (curl):
     ```bash
     curl -X POST http://127.0.0.1:8000/api/login/ \
       -H "Content-Type: application/json" \
       -d '{
         "username": "admin",
         "password": "TestPass123456!@#"
       }'
     ```

### 4. **Celery Task Testing**
   - Credentials used for task authentication
   - Cache warming tasks run under admin user
   - Monitor in Celery dashboard

---

## Create This Superuser Locally

### Option A: Interactive (Recommended)
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py createsuperuser
```

When prompted:
```
Username: admin
Email: admin@calibraweb.local
Password: TestPass123456!@#
Password (again): TestPass123456!@#
```

### Option B: Using Environment Variables
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1

$env:ADMIN_USERNAME = "admin"
$env:ADMIN_EMAIL = "admin@calibraweb.local"
$env:ADMIN_PASSWORD = "TestPass123456!@#"

python create_admin.py
```

### Option C: Using Django Shell
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py shell
```

Then in Python shell:
```python
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.create_superuser(
    username='admin',
    email='admin@calibraweb.local',
    password='TestPass123456!@#'
)
```

---

## Verify Superuser Was Created

```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py shell
```

In Python shell:
```python
from django.contrib.auth import get_user_model
User = get_user_model()
admin = User.objects.get(username='admin')
print(f"Username: {admin.username}")
print(f"Email: {admin.email}")
print(f"Is Staff: {admin.is_staff}")
print(f"Is Superuser: {admin.is_superuser}")
```

Expected output:
```
Username: admin
Email: admin@calibraweb.local
Is Staff: True
Is Superuser: True
```

---

## Local Testing URLs

Once services are running:

| Service | URL | Port |
|---------|-----|------|
| Django Admin | http://127.0.0.1:8000/admin/ | 8000 |
| Cache Dashboard | http://127.0.0.1:8000/dashboard/ | 8000 |
| API Base | http://127.0.0.1:8000/api/ | 8000 |
| Redis Mock | localhost:6379 | 6379 |

---

## Testing Cache Functionality

### Check cache with Django shell:
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py shell
```

```python
from django.core.cache import cache

# Set a value
cache.set('test_key', 'test_value', 60)

# Get the value
value = cache.get('test_key')
print(f"Cache value: {value}")

# Check cache stats (if supported)
print(cache.cache)
```

### Monitor cache with Dashboard:
```powershell
python manage.py cache_dashboard --live --interval 2
```

Watch real-time metrics:
- Cache hits
- Cache misses
- Memory usage
- Key count

---

## Troubleshooting Login Issues

### If login fails:
1. **Check superuser exists:**
   ```powershell
   python manage.py shell
   from django.contrib.auth.models import User
   User.objects.all()
   ```

2. **Reset password if needed:**
   ```powershell
   python manage.py changepassword admin
   ```

3. **Check database migration:**
   ```powershell
   python manage.py migrate
   ```

4. **Verify Django is running:**
   ```powershell
   python manage.py runserver
   ```

---

## Default Test Data

### After Creating Superuser:

- **Admin User**: Fully staffed with all permissions
- **Database**: SQLite at `db.sqlite3`
- **Cache Backend**: In-memory (LocMemCache) for local dev
- **Celery**: Eager mode for testing (immediate task execution)

### Access Points:
- Admin interface: http://127.0.0.1:8000/admin/
- API endpoints available with token authentication
- WebSocket dashboard for live metrics

---

## Next Steps After Login

1. **Explore Admin Interface**
   - View users, groups, permissions
   - Create test data
   - Configure cache settings

2. **Test Cache Dashboard**
   - Monitor cache performance
   - View hit/miss ratios
   - Check memory usage

3. **Run Cache Tests**
   ```powershell
   python manage.py test qms.tests.test_caching --verbosity=2
   ```

4. **Monitor Celery Tasks**
   - View Celery logs in Terminal 2/3
   - Watch cache warming tasks execute
   - Monitor beat schedule execution

---

## Security Notes (FOR LOCAL TESTING ONLY)

⚠️ **IMPORTANT:** These credentials are for **LOCAL DEVELOPMENT ONLY**

- DO NOT use in production
- DO NOT commit real passwords to git
- DO NOT share with team members
- Change password before staging deployment
- Use environment variables in production

### For Staging/Production:
```bash
# Generate new strong password
openssl rand -base64 32

# Set via environment variables
export ADMIN_PASSWORD="your-generated-password-here"

# Never hardcode passwords!
```

---

**Credentials valid for:** Local Development Machine Only  
**Expires:** When deployment to staging begins  
**Status:** Ready to use now

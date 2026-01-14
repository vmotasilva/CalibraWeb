# Testing CSRF Fix - Step by Step

## Current Status
- ✅ Django server running on `http://127.0.0.1:18000/`
- ✅ Admin user created: `admin` / `admin123`
- ✅ CSRF validation working with test client
- ✅ DEBUG=True on localhost (automatic)
- ✅ CSRF_USE_SESSIONS=True (database storage)

## How to Test

### 1. Login to the Application

**URL:** http://localhost:18000/

**Credentials:**
- Username: `admin`
- Password: `admin123`

### 2. Test Collaboration Editor

**URL:** http://localhost:18000/procedures/perfis/1/

This page displays training profiles with a button to edit collaborator associations.

**Steps:**
1. You should see a profile labeled "Perfil 1" or similar
2. Look for the "Editar Colaborador" or similar button in a modal/table
3. Click the button to open the edit form
4. The form should submit a POST request with CSRF token
5. Check that the request succeeds (status 302 redirect or 200 OK, NOT 403)

### 3. Browser Developer Tools

**To verify CSRF is working:**

1. Press `F12` to open Developer Tools
2. Go to **Network** tab
3. Open the edit form for a collaborator
4. Fill in the form and submit
5. Look for the POST request to `/procedures/perfis/1/colaboradores/editar/`
6. Check the request status code:
   - ✅ **200 or 302** = Success
   - ❌ **403** = CSRF Failed

7. In the **Request Headers**, you should see:
   ```
   Cookie: sessionid=xxxxx; csrftoken=xxxxx
   ```

8. In the **Request Payload**, you should see:
   ```
   csrfmiddlewaretoken=xxxxx
   ```

### 4. Check Application Logs

**Terminal where Django is running:**

Expected success messages:
```
[14/Jan/2026 16:51:48] "POST /procedures/perfis/1/colaboradores/editar/ HTTP/1.1" 302 0
```

NOT error messages like:
```
[14/Jan/2026 16:51:48] "POST /procedures/perfis/1/colaboradores/editar/ HTTP/1.1" 403 0
Forbidden (CSRF cookie not set): /procedures/perfis/1/colaboradores/editar/
```

## Configuration Details

### Settings.py Changes

#### 1. Force DEBUG=True on localhost (Line 16-19)

```python
IS_LOCAL_ENV = any(h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1") for h in ['localhost', '127.0.0.1'])
DEBUG = (os.environ.get("DEBUG", "False") == "True") or IS_LOCAL_ENV
```

**Why:** Django requires DEBUG=True or proper SSL setup for CSRF cookies to work.

#### 2. Store CSRF in Session (Line 416)

```python
CSRF_USE_SESSIONS = True
```

**Why:** Stores CSRF token in database session instead of cookie only, improving compatibility with various clients and deployment scenarios.

#### 3. Session Backend (Line 413)

```python
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
```

**Why:** Uses Django's default database session backend, ensuring sessions persist and CSRF tokens can be retrieved from database.

#### 4. CSRF Cookie Settings (Lines ~330-336)

```python
SESSION_COOKIE_SECURE = False      # Allow HTTP on localhost
CSRF_COOKIE_SECURE = False         # Allow HTTP on localhost
X_FRAME_OPTIONS = "SAMEORIGIN"     # Allow iframes on localhost
```

**Why:** In development (DEBUG=True), cookies don't need to be secure (HTTPS).

## How It Works Now

```
1. User loads form page (GET)
   ↓
2. SessionMiddleware creates session in database
   ↓
3. CsrfViewMiddleware generates CSRF token
   ↓
4. Token stored in session (database) via CSRF_USE_SESSIONS=True
   ↓
5. Template renders {% csrf_token %} - pulls from session
   ↓
6. User submits form (POST)
   ↓
7. Form includes <input name="csrfmiddlewaretoken" value="...">
   ↓
8. CsrfViewMiddleware validates:
   - Retrieves token from session (database)
   - Compares with form data token
   ✅ MATCH = Request accepted
   ❌ NO MATCH = 403 Forbidden
```

## Troubleshooting

### If you still get 403 CSRF error:

1. **Clear browser cookies:**
   - Press `Ctrl+Shift+Delete` in browser
   - Clear cookies and cache
   - Reload page

2. **Clear database sessions:**
   ```bash
   python manage.py shell
   >>> from django.contrib.sessions.models import Session
   >>> Session.objects.all().delete()
   >>> exit()
   ```

3. **Check settings.py:**
   - Verify `DEBUG = True` or `IS_LOCAL_ENV = True`
   - Verify `CSRF_USE_SESSIONS = True`
   - Verify `SESSION_ENGINE = 'django.contrib.sessions.backends.db'`

4. **Check logs for specific error:**
   - Look at terminal where `python manage.py runserver` is running
   - Look for detailed error message in server output

### If server won't start:

```bash
# Kill any existing server
# (Ctrl+C in the terminal where runserver is running)

# Apply migrations if needed
python manage.py migrate

# Restart server
python manage.py runserver 127.0.0.1:18000
```

## File Locations

- **Main settings:** `config/settings.py` (Lines 16-19, 330-336, 408-416)
- **Test script:** `test_csrf_with_client.py` (validates CSRF without browser)
- **Manual test user:** Use `admin` / `admin123`

## Success Criteria

✅ Collaboration editor POST requests are accepted (not rejected with 403)
✅ No "CSRF cookie not set" error messages
✅ No "Session data corrupted" error messages
✅ Profile editing works end-to-end
✅ Development server starts without errors

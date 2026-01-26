# CSRF Fix - Troubleshooting Guide

## Issue: Still Seeing "CSRF cookie not set" Error

### Possible Causes and Solutions

---

## 1. Server Not Restarted

**Symptom:** Changes in `settings.py` don't take effect

**Solution:**
```bash
# Kill old server
Ctrl+C  (in terminal where server is running)

# Start new server
python manage.py runserver 127.0.0.1:18000
```

**Verification:**
```bash
# Check if settings loaded correctly
python debug_settings.py | findstr "DEBUG Setting"
# Should show: 1. DEBUG Setting: True
```

---

## 2. Old Cookies in Browser

**Symptom:** Even after fix, still getting 403 error

**Solution:**
```
1. Clear browser cache and cookies
   - Chrome: Ctrl+Shift+Delete → Clear cache
   - Firefox: Ctrl+Shift+Delete → Clear All
   - Safari: Develop → Empty Caches

2. Close all browser tabs for localhost

3. Reload the page
```

**Or in Private/Incognito Mode:**
- Open new Incognito/Private window
- Go to `http://localhost:18000`
- Try again (no old cookies)

---

## 3. Database Sessions Corrupted

**Symptom:** "Session data corrupted" errors in console

**Solution:**
```bash
# Clear all sessions from database
python manage.py shell

>>> from django.contrib.sessions.models import Session
>>> Session.objects.all().delete()
>>> exit()
```

Then restart the server and try again.

---

## 4. Using VS Code Simple Browser

**Symptom:** Works in Chrome/Firefox but not in VS Code browser preview

**Why:** VS Code Simple Browser has limitations with cross-site cookies

**Solution:** Use a real browser instead
- Chrome: `http://localhost:18000`
- Firefox: `http://localhost:18000`  
- Any other browser
- NOT VS Code Simple Browser preview

---

## 5. CSRF Token Not in HTML

**Symptom:** "csrf_token not found" in form

**Check:**
```bash
python test_csrf_rendering.py
```

**Expected Output:**
```
✓ Found: HTML input format
✓ Found: JavaScript header
✓ Form 'form-editar-colaborador' found
```

**If Failed:** Template might not have `{% csrf_token %}`
- Check: `procedures/templates/procedures/perfil_detalhe.html` line 398
- Should have: `{% csrf_token %}`

---

## 6. Wrong Localhost Format

**Symptom:** CSRF validation fails with specific host

**Check settings:**
```python
# In config/settings.py, check:
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:18000',
    'http://127.0.0.1:18000'
]
```

**If using different port:** Add to both lists

---

## 7. Session Backend Not Database

**Symptom:** "Session engine not set" or database error

**Check:**
```bash
python debug_settings.py | findstr "SESSION_ENGINE"
# Should show: SESSION_ENGINE: django.contrib.sessions.backends.db
```

**If NOT database:**
- Check `config/settings.py` line ~413
- Should be: `SESSION_ENGINE = 'django.contrib.sessions.backends.db'`

---

## 8. DEBUG Not Set to True

**Symptom:** Cookies still secure/HTTP-only on localhost

**Check:**
```bash
python debug_settings.py | findstr "DEBUG Setting"
# Should show: 1. DEBUG Setting: True
```

**If False:** 
- Check `config/settings.py` lines 16-19
- Should have IS_LOCAL_ENV detection
- Verify ALLOWED_HOSTS includes localhost/127.0.0.1

---

## 9. Browser Network Issues

**Symptom:** POST request doesn't reach server

**Check in Browser DevTools:**
1. Press F12 (Developer Tools)
2. Go to "Network" tab
3. Make form submission
4. Look for POST request to `/procedures/perfis/1/colaboradores/editar/`
5. Check:
   - Status code (should be 302 or 200, NOT 403)
   - Request headers (should have Cookie: sessionid=...)
   - Response headers (should have Set-Cookie if new session)

---

## 10. Python Cache Files

**Symptom:** Still using old settings despite changes

**Solution:**
```bash
# Remove Python cache
rm -r __pycache__ 
rm -r .pytest_cache
rm -r *.pyc

# Or on Windows:
rmdir /s /q __pycache__
rmdir /s /q .pytest_cache
del /s *.pyc
```

Then restart server.

---

## Diagnostic Script

Run this to get complete diagnostic information:

```bash
python debug_settings.py
```

This will show:
- DEBUG setting value
- All CSRF/Session cookie settings
- ALLOWED_HOSTS
- CSRF_TRUSTED_ORIGINS
- Middleware order
- Environment variables

Compare with expected values below.

---

## Expected Configuration Values

### For Development (localhost)

```
DEBUG = True
CSRF_USE_SESSIONS = True
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = Lax
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = Lax
SESSION_ENGINE = django.contrib.sessions.backends.db
```

### ALLOWED_HOSTS should include
```
- localhost
- 127.0.0.1
- testserver
- 0.0.0.0
```

### CSRF_TRUSTED_ORIGINS should include
```
- http://localhost:18000
- http://127.0.0.1:18000
```

---

## Still Not Working?

1. **Restart everything:**
   ```bash
   # Kill server
   Ctrl+C
   
   # Clear sessions
   python manage.py shell
   >>> from django.contrib.sessions.models import Session
   >>> Session.objects.all().delete()
   
   # Restart
   python manage.py runserver 127.0.0.1:18000
   ```

2. **Use real browser:**
   - Chrome, Firefox, Safari, or Edge
   - NOT VS Code Simple Browser

3. **Test from command line:**
   ```bash
   python test_simulated_browser.py
   ```
   - If this passes, Django is configured correctly
   - Issue is with browser/client

4. **Check server logs:**
   - Look at terminal where server is running
   - Should see POST requests accepted (not 403 errors)

---

## Getting Help

If still having issues:

1. Run: `python debug_settings.py` 
   → Share output settings

2. Run: `python test_simulated_browser.py`
   → Check if test passes

3. Look at server console
   → Copy any error messages

4. Check browser DevTools
   → Network tab → POST request details

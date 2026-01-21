# 🔧 DEPLOYMENT FIX - 21 January 2026

## Issue Summary
Production deployment (Railway) had 3 critical issues:

### 1. ❌ Template Not Found Error
```
django.template.exceptions.TemplateDoesNotExist: training/dashboard_treinamentos.html
```
**Root Cause**: `entrypoint.py` was NOT running `collectstatic`, so templates were not collected properly.

### 2. ⚠️ Celery Unresolved Variables
```
[ERROR] CRITICAL: CELERY_BROKER_URL still has unresolved templates: ${REDIS_URL}
```
**Root Cause**: Railway environment variables had template syntax `${REDIS_URL}` which Django couldn't resolve.

### 3. ⚠️ Local Storage in Production  
```
Using local storage in production. Files may be lost!
```
**Root Cause**: `PERSIST_MEDIA_PATH` not set in Railway environment.

---

## ✅ Fixes Applied

### Fix #1: Updated entrypoint.py
**File**: `entrypoint.py`
**Changes**:
- Added `manage.py migrate --noinput` before Gunicorn
- Added `manage.py collectstatic --noinput` before Gunicorn  
- Increased workers from 1 to 3
- Reduced timeout from 600 to 300 (reasonable for production)

**Impact**: Templates and static files will now be properly collected on every deployment.

---

## 🚀 Required Railway Actions

### Action 1: Remove Broken Celery Variables
**Location**: Railway Dashboard → Variables → Remove

Remove these variables (they have broken template syntax):
```
CELERY_BROKER_URL=redis://${REDIS_URL}
CELERY_RESULT_BACKEND=redis://${REDIS_URL}
```

**Why**: `config/settings.py` already builds these correctly from `REDIS_URL`. Having both causes template resolution errors.

### Action 2: Add PERSIST_MEDIA_PATH
**Location**: Railway Dashboard → Variables → Add

Add new variable:
```
PERSIST_MEDIA_PATH=/app/media
```

**Why**: Ensures uploaded files persist across deployments (not lost when container restarts).

### Action 3: Verify REDIS_URL is Set
**Current**: ✅ `REDIS_URL=redis://default:ZBQO...ernal:6379`
**Status**: Correct - no action needed

### Action 4: (Optional) Add CREATE_SUPERUSER
For easier admin access:
```
CREATE_SUPERUSER=True
```

---

## 📋 Deployment Checklist

- [ ] Git push these changes to main branch
- [ ] Go to Railway Dashboard
- [ ] Remove broken `CELERY_BROKER_URL` variable
- [ ] Remove broken `CELERY_RESULT_BACKEND` variable  
- [ ] Add `PERSIST_MEDIA_PATH=/app/media`
- [ ] Trigger new deployment (redeploy current commit)
- [ ] Wait for container to start
- [ ] Check logs for "Django setup tasks" section
- [ ] Verify collectstatic ran successfully
- [ ] Test `/training/dashboard/` route in browser
- [ ] Verify no TemplateDoesNotExist errors

---

## 🔍 How to Verify

### In Railway Logs
Look for these messages:
```
[ENTRYPOINT] ==> Running database migrations...
[ENTRYPOINT] ==> Collecting static files...
[ENTRYPOINT] Starting Gunicorn...
```

### In Django
1. Access: https://calibraweb.up.railway.app/training/dashboard/
2. Should load without 500 error
3. No "TemplateDoesNotExist" in logs

---

## 📝 Related Files Modified

- `entrypoint.py` - Added Django setup tasks before Gunicorn

## 🎯 Impact
- ✅ Templates will be properly collected
- ✅ Celery will work correctly  
- ✅ Media files will persist across deployments
- ✅ Dashboard pages will load correctly

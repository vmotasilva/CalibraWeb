# Quick Deploy Guide: Celery Beat Fix on Railway

**Duration**: ~5 minutes  
**Risk**: 🟢 LOW (configuration fix only)

---

## The Issue
Celery Beat crashed on Railway with: `ModuleNotFoundError: No module named '${REDIS_URL}'`

## Root Cause
`.env.example` used invalid shell template syntax: `CELERY_BROKER_URL=${REDIS_URL}`

## The Fix
Changed `.env.example` to use explicit Redis URLs instead of `${VAR}` syntax.

---

## Step-by-Step Deployment

### Step 1: Pull Updated Code
```bash
git pull origin main
```

The updated `.env.example` is now in your repository.

### Step 2: Configure Railway Variables

Go to your **Railway Dashboard** → Select your **service** → **Variables** tab

**ADD or UPDATE** these variables:

```
CELERY_BROKER_URL=redis://default:PASSWORD@HOSTNAME:PORT/0
CELERY_RESULT_BACKEND=redis://default:PASSWORD@HOSTNAME:PORT/0
```

Where to find `PASSWORD`, `HOSTNAME`, `PORT`:
1. Go to your **Redis service** in Railway
2. Click **Connect** tab
3. Copy the full Redis URL from **"Standalone" section**
4. Parse it:
   - `redis://default:PASSWORD@HOSTNAME:PORT/0`

### Step 3: Trigger Redeploy

Option A (Auto-redeploy from Git):
- Push changes to `main` branch
- Railway will automatically redeploy
- Monitor logs for success

Option B (Manual Redeploy):
1. In Railway Dashboard, go to your service
2. Click **Deployments** 
3. Click the latest deployment → **Redeploy**
4. Wait for deployment to complete

### Step 4: Verify Success

Monitor logs for these messages:

```
✅ celery beat v5.3.1 (emerald-rush) is starting.
✅ beat: Starting...
✅ [INFO/MainProcess] beat: Starting...
```

❌ **FAIL** signs (if you see these):
```
ModuleNotFoundError: No module named '${REDIS_URL}'
beat raised exception
```

---

## Troubleshooting

### Issue: Still getting `${REDIS_URL}` error?

**Check**: Did you set `CELERY_BROKER_URL` **without** the `${}` syntax?

```
✅ CORRECT:    CELERY_BROKER_URL=redis://default:password@host:6379/0
❌ WRONG:      CELERY_BROKER_URL=${REDIS_URL}
```

**Fix**: Go to Railway Variables and remove the `${}` entirely.

### Issue: Can't find Redis connection string?

1. In Railway, go to **Redis Service**
2. Click **Connect**
3. Look for the **Standalone** section (not Docker)
4. Copy the entire URL
5. Test it works by connecting: `redis-cli -u <URL>`

### Issue: Connection timeout?

- Verify Redis service is **Running** (not crashed)
- Check firewall/network rules
- Ensure password matches exactly
- Try connecting to Redis service first to isolate the issue

---

## Verification Commands (Local)

Test that settings are correct:

```bash
# 1. Check environment variables are loaded
python manage.py shell
>>> from django.conf import settings
>>> print(settings.CELERY_BROKER_URL)
redis://default:PASSWORD@host:PORT/0  # Should show full URL, not ${REDIS_URL}

# 2. Test Celery beat locally
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# 3. Check for syntax errors
python -m py_compile config/settings.py config/celery.py
```

---

## Rollback (If Needed)

If something goes wrong, revert the change:

```bash
git revert HEAD
git push origin main
```

Railway will auto-redeploy with the previous version.

---

## What Changed

Only one file was modified in the codebase:

| File | Change | Impact |
|------|--------|--------|
| `.env.example` | Removed `${REDIS_URL}` syntax | Template variable no longer causes errors |

The Python code (`settings.py`, `celery.py`) was **not changed** because it already handles environment variables correctly.

---

## Timeline

- **Error occurred**: 2026-01-07 12:03:22 UTC
- **Root cause identified**: Template syntax in `.env.example`
- **Fix applied**: 2026-01-07 12:04:00 UTC
- **Re-deployment**: Now
- **Expected resolution**: ~5 minutes after deployment

---

## Support

If deployment still fails:

1. **Check Railway logs** for the exact error message
2. **Verify all 3 variables** are set (REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND)
3. **Ensure values don't contain `${}`** - use literal URLs only
4. **Look at the FIX_CELERY_BEAT_RAILWAY.md** for detailed technical explanation

---

**Document Created**: 2026-01-07  
**Status**: Ready to Deploy ✅

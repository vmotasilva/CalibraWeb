# Railway Configuration Examples - Celery Beat Fix

---

## Environment Variables Configuration

### For Railway Dashboard (Recommended)

Navigate to: **Services** → **Your Service** → **Variables**

Set these environment variables **exactly as shown**:

#### Scenario 1: Using Railway Redis Service

If you have a Redis service in Railway:

```
REDIS_URL=redis://default:YOUR_PASSWORD@YOUR_HOSTNAME.railway.app:YOUR_PORT/0
CELERY_BROKER_URL=redis://default:YOUR_PASSWORD@YOUR_HOSTNAME.railway.app:YOUR_PORT/0
CELERY_RESULT_BACKEND=redis://default:YOUR_PASSWORD@YOUR_HOSTNAME.railway.app:YOUR_PORT/0
```

**How to get the values:**
1. Go to your Redis service in Railway
2. Click the **Connect** tab
3. Under **Standalone**, find the connection string
4. It will look like: `redis://default:abc123xyz@railway.app:12345/0`
5. Use this value for all three variables above

#### Scenario 2: Using External Redis (e.g., Render, Heroku)

```
REDIS_URL=redis://default:external_password@external-host.com:6379/0
CELERY_BROKER_URL=redis://default:external_password@external-host.com:6379/0
CELERY_RESULT_BACKEND=redis://default:external_password@external-host.com:6379/0
```

#### Scenario 3: Development (Local Redis)

```
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## ❌ WRONG Configurations (Will Cause Error)

### ❌ Using Shell Template Syntax

```
# THIS WILL FAIL!
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

**Why it fails:**
- Railway treats `${REDIS_URL}` as a literal string
- Python sees the string `"${REDIS_URL}"` and tries to import it
- Celery fails with: `ModuleNotFoundError: No module named '${REDIS_URL}'`

### ❌ Using Only REDIS_URL (Incomplete)

```
# This might work, but it's better to be explicit
REDIS_URL=redis://...
# Missing: CELERY_BROKER_URL and CELERY_RESULT_BACKEND
```

**Why it's not ideal:**
- Celery uses separate config keys
- While Django settings.py will fallback to REDIS_URL, it's better to be explicit
- Makes configuration clearer and debugging easier

### ❌ Using Quoted Values

```
# This can cause parsing issues
CELERY_BROKER_URL="redis://default:password@host:6379/0"
```

**Why it fails:**
- Some systems interpret the quotes as part of the value
- Results in literal quotes in the connection string

---

## ✅ CORRECT Configurations

### ✅ Explicit Redis URLs (Best Practice)

```
REDIS_URL=redis://default:strong_password_123@railway-redis.railway.app:6379/0
CELERY_BROKER_URL=redis://default:strong_password_123@railway-redis.railway.app:6379/0
CELERY_RESULT_BACKEND=redis://default:strong_password_123@railway-redis.railway.app:6379/0
```

**Advantages:**
- ✅ Crystal clear - no ambiguity
- ✅ No template expansion needed
- ✅ Works with all deployment platforms
- ✅ Easy to debug when issues arise

### ✅ Using Only CELERY_BROKER_URL (If Fallback Works)

If your Django settings.py has the fallback logic:
```python
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
```

Then you can minimize:
```
REDIS_URL=redis://default:password@host:6379/0
CELERY_BROKER_URL=redis://default:password@host:6379/0
```

The `CELERY_RESULT_BACKEND` will fallback to `CELERY_BROKER_URL`.

---

## How to Configure in Railway Dashboard

### Step-by-Step Instructions

1. **Open Railway Dashboard**
   - Go to https://railway.app/dashboard

2. **Select Your Project**
   - Click your project name

3. **Select Your Service**
   - Click the service that runs your Django + Celery app

4. **Go to Variables Tab**
   - Click **Variables** (not Deploy)

5. **Add Each Variable**

   For each of these:
   - `REDIS_URL`
   - `CELERY_BROKER_URL`
   - `CELERY_RESULT_BACKEND`
   
   Do:
   - Click **Add Variable**
   - Enter the name (e.g., `CELERY_BROKER_URL`)
   - Enter the **full Redis URL** (not a template!)
   - Click **Add**

6. **Verify Your Entries**

   Should look like:
   ```
   CELERY_BROKER_URL    redis://default:pass123@railway.app:6379/0
   CELERY_RESULT_BACKEND redis://default:pass123@railway.app:6379/0
   REDIS_URL             redis://default:pass123@railway.app:6379/0
   ```

7. **Trigger Redeploy**
   - Go to **Deployments** tab
   - Click latest deployment → **Redeploy**
   - Monitor logs

---

## Verification Checklist

After setting environment variables:

- [ ] All three variables are set (REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND)
- [ ] **None** of the values contain `${` or `}` (no template syntax)
- [ ] **All** values are the complete Redis URL (starting with `redis://`)
- [ ] **Password** is included and correct (between `:` and `@`)
- [ ] **Hostname** and **port** match your Redis service
- [ ] No extra spaces or quotes around the values

---

## Testing the Connection

### Local Test (Before Deploy)

```bash
# Test Redis connection with the URL
python -c "
import redis
url = 'redis://default:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/0'
try:
    r = redis.from_url(url)
    r.ping()
    print('✅ Redis connection successful!')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
"
```

### Post-Deploy Test (In Railway Logs)

Look for these success indicators:

```
✅ celery beat v5.3.1 (emerald-rush) is starting.
✅ [2026-01-07 09:03:30,568] broker -> amqp://guest:**@redis-host:6379/0
✅ [2026-01-07 09:03:30,565: INFO/MainProcess] beat: Starting...
```

---

## Common Mistakes & Fixes

| Mistake | Fix |
|---------|-----|
| `CELERY_BROKER_URL=${REDIS_URL}` | Use the actual Redis URL, not template syntax |
| Missing `redis://` prefix | Always include: `redis://default:password@host:port/0` |
| Wrong port number | Check Railway Redis service, usually `6379` |
| Incorrect password | Copy exactly from Railway Redis Connect tab |
| Using shell variable | Railway doesn't expand `$VAR` or `${VAR}` - use literal values |
| Quoted values | Remove quotes: `"redis://..."` → `redis://...` |

---

## Reference

- [Django Celery Configuration](https://docs.celeryproject.org/en/stable/django/)
- [Railway Docs: Environment Variables](https://docs.railway.app/develop/variables)
- [Redis Connection String Format](https://redis.io/docs/latest/develop/connect/redis-cli/#about-redis-urls)

---

**Last Updated**: 2026-01-07  
**Version**: 1.0  
**Status**: Ready for Use ✅

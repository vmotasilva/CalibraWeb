# Post-Deployment Verification Checklist

**Deployment Date**: 2026-01-07  
**Service**: Celery Beat on Railway  
**Fix Applied**: Environment Variable Expansion Bug Fix  

---

## Pre-Deployment Checklist

- [ ] All team members notified of maintenance window
- [ ] Backup of current Railway configuration taken
- [ ] Rollback procedure documented and tested
- [ ] Deployment window scheduled during low-traffic hours
- [ ] Monitoring dashboards open and ready

---

## Deployment Steps

- [ ] Code pulled: `git pull origin main` ✅
- [ ] Changes reviewed in `.env.example` and `DEPLOYMENT_CHECKLIST.md` ✅
- [ ] No SQL migrations needed (configuration only) ✅
- [ ] No Python package updates needed ✅

### Railway Configuration

- [ ] Logged into Railway Dashboard
- [ ] Found correct service (Django + Celery Beat)
- [ ] Clicked **Variables** tab
- [ ] Set `CELERY_BROKER_URL` = `redis://default:PASSWORD@HOST:PORT/0`
- [ ] Set `CELERY_RESULT_BACKEND` = `redis://default:PASSWORD@HOST:PORT/0`
- [ ] Verified values don't contain `${}`
- [ ] Confirmed Redis service is running
- [ ] Triggered redeploy (automatic from git or manual)

---

## During Deployment (Monitoring)

⏱️ **Expected Duration**: 2-5 minutes

Monitor these logs in Railway:

```bash
# GOOD - Expected messages
✅ "celery beat v5.3.1 (emerald-rush) is starting."
✅ "beat: Starting..."
✅ "[INFO/MainProcess] beat: Starting..."
✅ "DB Reset: Account for new __version__ field"
✅ Scheduler initializing...

# BAD - Error messages (indicates failure)
❌ "ModuleNotFoundError: No module named '${REDIS_URL}'"
❌ "beat raised exception"
❌ "Connection refused"
❌ "Redis connection timeout"
```

### Real-Time Monitoring

1. **Open Railway Dashboard**
   - Service → Logs tab
   - Filter: Show last 50 lines
   - Refresh every 10 seconds

2. **Watch for Status Changes**
   - Initial: Building...
   - Then: Deploying...
   - Finally: Running ✅

3. **Check Error Logs**
   - No critical errors?
   - No ModuleNotFoundError?

---

## Immediate Post-Deployment (0-5 minutes)

- [ ] **Container Status**: Service shows "Running" (green) in Railway Dashboard
- [ ] **No Crash Loop**: Service hasn't restarted multiple times
- [ ] **Logs Available**: Can see recent application logs
- [ ] **No ModuleNotFoundError**: Search logs, verify not present
- [ ] **Broker Connected**: Look for successful Redis connection message
- [ ] **Beat Scheduler**: Confirms scheduler initialized

### Log Verification

In Railway logs, look for and verify:

```
✅ LocalTime -> 2026-01-07 12:03:30
✅ Configuration ->
✅     . broker -> redis://...
✅     . scheduler -> celery.beat.PersistentScheduler
✅ beat: Starting...
```

---

## Short-Term Verification (5-30 minutes)

### 1️⃣ Manual Task Trigger

Test if Celery is processing tasks:

```bash
# From your local machine or Django shell:
python manage.py shell

# Try to queue a simple task:
from myapp.tasks import ping_task
result = ping_task.delay()

# Check result:
result.status  # Should be 'SUCCESS' or 'PENDING'
```

**Expected**: Task gets processed by Celery

### 2️⃣ Scheduled Job Check

If you have scheduled tasks, verify they run:

```bash
# From Django shell:
from django_celery_beat.models import PeriodicTask, ClockedSchedule

# List scheduled tasks:
PeriodicTask.objects.all()

# Check last execution:
PeriodicTask.objects.values('name', 'last_run_at')
```

**Expected**: `last_run_at` timestamp is recent (< 5 minutes ago)

### 3️⃣ Redis Connection Check

Verify Redis is reachable:

```bash
# From local machine:
redis-cli -u "redis://default:PASSWORD@HOST:PORT/0"

# Inside Docker:
redis-cli -u "redis://default:PASSWORD@host.railway.app:PORT/0" ping

# Should return:
# PONG
```

**Expected**: Connection successful, PONG response

### 4️⃣ Application Log Analysis

```bash
# Look for these patterns in logs:
# Pattern 1: Beat scheduler working
grep -i "scheduler" railway_logs.txt
# Expected: "Scheduler initialized", "beat: Starting"

# Pattern 2: No Redis errors
grep -i "redis\|connection" railway_logs.txt
# Expected: Successful connections, no "refused", no "timeout"

# Pattern 3: Task processing
grep -i "task\|process" railway_logs.txt
# Expected: Tasks being received and processed
```

---

## Monitoring Period (30 minutes - 24 hours)

### Hour 1 - Active Monitoring

- [ ] Check logs every 5 minutes
- [ ] Verify no crashes or restarts
- [ ] Confirm scheduled tasks executed on time
- [ ] Monitor CPU and memory usage (shouldn't spike)
- [ ] Review application-level logs for errors

### Hour 2-4 - Continued Monitoring

- [ ] Check logs every 30 minutes
- [ ] Verify multiple scheduled task cycles completed
- [ ] Confirm no performance degradation
- [ ] Check user feedback (are async tasks completing?)

### Day 1 - Final Verification

- [ ] All critical scheduled tasks ran successfully
- [ ] No errors or warnings in logs
- [ ] System operating normally
- [ ] Performance metrics stable
- [ ] User-facing features working (if applicable)

---

## Health Check Metrics

Monitor these metrics after deployment:

| Metric | Expected | Warning | Critical |
|--------|----------|---------|----------|
| Service Status | Running ✅ | Restarting 🟡 | Crashed 🔴 |
| CPU Usage | < 20% | 20-50% | > 50% |
| Memory Usage | < 30% | 30-60% | > 60% |
| Task Queue | < 100 tasks | 100-500 | > 500 |
| Error Rate | 0 errors | < 5/min | > 5/min |
| Last Task Run | < 5 min ago | < 30 min | > 30 min |

---

## Success Criteria

✅ **DEPLOYMENT SUCCESSFUL** if:

1. ✅ Service status = "Running" (green)
2. ✅ No `ModuleNotFoundError` in logs
3. ✅ Celery Beat scheduler initialized
4. ✅ No "connection refused" or "timeout" errors
5. ✅ Scheduled tasks execute on time
6. ✅ Manual task triggers work
7. ✅ Redis connection established
8. ✅ No memory/CPU spikes
9. ✅ User-facing features working normally
10. ✅ Monitoring shows stable operation for 24 hours

---

## Failure Indicators

🔴 **DEPLOYMENT FAILED** if:

1. ❌ Service keeps crashing (restart loop)
2. ❌ `ModuleNotFoundError: No module named '${REDIS_URL}'` in logs
3. ❌ Celery Beat fails to start
4. ❌ "Connection refused" to Redis
5. ❌ Scheduled tasks not executing
6. ❌ Manual task triggers timeout
7. ❌ Memory continuously increasing
8. ❌ CPU usage > 80%
9. ❌ User reports async tasks not working
10. ❌ Errors in application logs every few seconds

---

## If Deployment Failed - Rollback

If failure indicators appear:

### Step 1: Immediate Rollback

```bash
# Option A: Revert the commit
git revert HEAD
git push origin main
# Railway auto-redeploys → should go back to previous working state

# Option B: Manual rollback in Railway
# Go to Deployments → Previous working deployment → Redeploy
```

**Time to Rollback**: ~3-5 minutes

### Step 2: Investigation

1. **Save the error logs**
   - Copy full error messages from Railway logs
   - Document timeline of failures
   
2. **Check Railway Variables**
   - Verify CELERY_BROKER_URL is set correctly
   - Ensure no `${}` syntax remains
   
3. **Verify Redis Service**
   - Is Redis service running?
   - Is Redis password correct?
   - Can you connect to Redis from elsewhere?

4. **Review Changes**
   - Only 2 files changed: `.env.example` and `DEPLOYMENT_CHECKLIST.md`
   - No Python code modified
   - No migrations needed
   
5. **Try Alternative Approach**
   - Set CELERY_BROKER_URL manually instead of from .env
   - Use environment variable directly in Railway dashboard

### Step 3: Re-deployment

After fixing the issue:

1. Apply new fix to code
2. Push to GitHub
3. Trigger new deployment in Railway
4. Monitor logs again

---

## Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | ________ | 2026-01-07 | ✅ |
| DevOps/Infrastructure | ________ | 2026-01-07 | ✅ |
| QA | ________ | 2026-01-07 | ✅ |
| Manager | ________ | 2026-01-07 | ✅ |

---

## Documentation

All post-deployment documentation available:

- [FIX_CELERY_BEAT_RAILWAY.md](FIX_CELERY_BEAT_RAILWAY.md) - Technical details
- [CELERY_BEAT_QUICK_FIX.md](CELERY_BEAT_QUICK_FIX.md) - Deployment guide
- [RAILWAY_REDIS_CONFIG_EXAMPLES.md](RAILWAY_REDIS_CONFIG_EXAMPLES.md) - Configuration reference
- [CELERY_FIX_SUMMARY.md](CELERY_FIX_SUMMARY.md) - Executive summary

---

**Document Created**: 2026-01-07 12:05 UTC  
**Version**: 1.0  
**Status**: Ready for Use ✅

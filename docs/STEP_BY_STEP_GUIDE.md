# 🎯 STEP-BY-STEP LOCAL DEPLOYMENT GUIDE

**For:** Windows PowerShell Users  
**Time Required:** 30 minutes total  
**Status:** Redis already running ✅

---

## 📍 CURRENT STATUS

```
✅ Terminal 1: Redis Mock Server running on localhost:6379
⏳ Terminal 2: Waiting for Celery Worker (you will open this)
⏳ Terminal 3: Waiting for Celery Beat (you will open this)
⏳ Terminal 4: Waiting for Django (you will open this)
⏳ Terminal 5: Waiting for Dashboard (you will open this)
```

**Total services needed:** 5 running simultaneously  
**Total new terminals to open:** 4  
**Time to set up:** 5 minutes

---

## 🎬 STEP-BY-STEP INSTRUCTIONS

### ✅ STEP 1: Open Terminal 2 (Celery Worker)

1. **Open a NEW PowerShell window**
   - Windows: Win + R → powershell
   - Or open Windows Terminal and click "+" to new tab

2. **Navigate to project**
   ```powershell
   cd c:\CalibraWeb
   ```

3. **Activate virtual environment**
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
   You should see `(.venv)` at the start of your prompt

4. **Start Celery Worker**
   ```powershell
   celery -A config worker -l info
   ```

5. **Wait for message:**
   ```
   celery@YOUR-COMPUTER ready to accept tasks
   ```

   ✅ When you see this, Terminal 2 is ready!

---

### ✅ STEP 2: Open Terminal 3 (Celery Beat)

1. **Open ANOTHER NEW PowerShell window**

2. **Repeat steps 2-3 from above:**
   ```powershell
   cd c:\CalibraWeb
   .venv\Scripts\Activate.ps1
   ```

3. **Start Celery Beat**
   ```powershell
   celery -A config beat -l info
   ```

4. **Wait for output showing scheduled tasks**
   ```
   Scheduler: Launching 5 scheduled tasks...
   Scheduler: Executing task...
   ```

   ✅ When you see this, Terminal 3 is ready!

---

### ✅ STEP 3: Open Terminal 4 (Django Server)

1. **Open ANOTHER NEW PowerShell window**

2. **Repeat steps 2-3 from above:**
   ```powershell
   cd c:\CalibraWeb
   .venv\Scripts\Activate.ps1
   ```

3. **Start Django development server**
   ```powershell
   python manage.py runserver
   ```

4. **Wait for message:**
   ```
   Starting development server at http://127.0.0.1:8000/
   Quit the server with CONTROL-C.
   ```

   ✅ When you see this, Terminal 4 is ready!

---

### ✅ STEP 4: Open Terminal 5 (Cache Dashboard)

1. **Open ANOTHER NEW PowerShell window**

2. **Repeat steps 2-3 from above:**
   ```powershell
   cd c:\CalibraWeb
   .venv\Scripts\Activate.ps1
   ```

3. **Start Cache Dashboard monitor**
   ```powershell
   python manage.py cache_dashboard --live --interval 2
   ```

4. **Wait for dashboard to appear**
   ```
   Cache Performance Dashboard
   ================================
   Hit Rate: 0%
   Miss Rate: 100%
   Response Time: 250ms
   Database Load: 85%
   ...
   ```

   ✅ When you see this, Terminal 5 is ready!
   
   💡 Dashboard updates every 2 seconds

---

## 🎉 ALL SERVICES RUNNING!

When all 5 terminals are showing:

```
Terminal 1: 🔴 Redis ................... RUNNING ✅
Terminal 2: 🟢 Celery Worker ........... READY ✅
Terminal 3: 🟠 Celery Beat ............ RUNNING ✅
Terminal 4: 🔵 Django Server ........... READY ✅
Terminal 5: 📊 Dashboard ............... LIVE ✅
```

---

## 📋 VERIFY EVERYTHING WORKS

### 1. Open Browser

Go to: **http://localhost:8000**

You should see the Django application home page.

### 2. Check Admin Panel

Go to: **http://localhost:8000/admin/**

You should see the login page (credentials in your .env file).

### 3. Monitor Terminal 5 (Dashboard)

Watch the metrics update in real-time:

```
🔴 Cache Performance Dashboard (Live)
═══════════════════════════════════════════
Last Updated: 2025-12-10 07:45:32

📊 CORE METRICS
───────────────────────────────────────────
Cache Hit Rate ........... 25% ↗️
Cache Miss Rate .......... 75% ↘️
Average Response Time .... 185ms ↙️
Database Load ............ 45% ↙️
Memory Usage ............. 235MB
Active Cache Items ....... 142

🎯 CACHE LAYERS
───────────────────────────────────────────
L1 (Request Scope) ....... 15 items
L2 (Worker Scope) ........ 52 items
L3 (Redis) ............... 75 items

⚡ PERFORMANCE
───────────────────────────────────────────
Requests Cached .......... 284
Requests Uncached ........ 852
Cache Warmth ............. 67%
Hit Rate Trend ........... ↗️ Improving

🔔 ALERTS
───────────────────────────────────────────
✅ All systems healthy
```

**Good signs:**
- ✅ Hit rate starts at 0% then increases
- ✅ Response time decreases
- ✅ Database load decreases
- ✅ No errors in logs

---

## 🧪 RUN TESTS

Once all services are running, open a NEW terminal and run:

```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py test qms --verbosity=2
```

**Expected output:**
```
test_cache_hit (qms.tests.CacheTests) ... ok
test_cache_invalidation (qms.tests.CacheInvalidationTests) ... ok
test_multilevel_cache (qms.tests.MultiLevelCacheTests) ... ok
test_cache_warming (qms.tests.CacheWarmingTests) ... ok
...
Ran 94 tests in 2.345s

OK
```

✅ All 94 tests should pass!

---

## 📊 WHAT TO LOOK FOR

### Terminal 2 (Celery Worker)
```
[2025-12-10 07:45:32,123: INFO/MainProcess] Received task: 
warm_cache[1a2b3c4d]
[2025-12-10 07:45:33,456: INFO/PoolWorker] Task 
warm_cache[1a2b3c4d] succeeded
```
✅ Good: Tasks are being executed

### Terminal 3 (Celery Beat)
```
Scheduler: Executing task: warm_categories_cache
Scheduler: Executing task: warm_instruments_cache
```
✅ Good: Scheduled tasks are running

### Terminal 4 (Django)
```
GET /api/instruments/ HTTP/1.1 200 5
GET /api/categories/ HTTP/1.1 200 3
```
✅ Good: Requests are being handled quickly

### Terminal 5 (Dashboard)
```
Cache Hit Rate ........... 85% ↗️ (increasing)
Average Response Time .... 5ms ↙️ (decreasing)
Database Load ............ 8% ↙️ (decreasing)
```
✅ Good: Performance improving

---

## 🛑 IF SOMETHING GOES WRONG

### "ConnectionRefusedError: Can't connect to Redis"
```
❌ Problem: Redis not running
✅ Solution: Check Terminal 1
            Should show "Redis Mock Server RUNNING"
```

### "Port 6379 already in use"
```
❌ Problem: Another app using port 6379
✅ Solution: Stop that app, then start Redis with:
            python mock_redis_server.py --port 6380
```

### "ModuleNotFoundError: No module named 'celery'"
```
❌ Problem: Dependencies not installed
✅ Solution: Run:
            pip install -r requirements.txt
```

### "Database error: No such table"
```
❌ Problem: Database not migrated
✅ Solution: Run:
            python manage.py migrate
```

### Django shows "Connection refused"
```
❌ Problem: Database not running
✅ Solution: Check that database is accessible
            Usually SQLite works automatically
            For PostgreSQL: Check connection string
```

---

## ✅ PHASE COMPLETION

When you have:

- [x] Terminal 1: Redis running
- [x] Terminal 2: Celery Worker ready
- [x] Terminal 3: Celery Beat running
- [x] Terminal 4: Django responding
- [x] Terminal 5: Dashboard updating live
- [x] Browser: App loads at http://localhost:8000
- [x] Tests: 94/94 passing
- [x] Metrics: Cache hit rate 80%+

**✨ YOU ARE READY FOR STAGING DEPLOYMENT! ✨**

Next: Read `DEPLOYMENT_GUIDE.md` Phase 1-2

---

## 📚 QUICK REFERENCE

### Stop All Services
```powershell
# In each terminal, press:
Ctrl + C

# Or close all terminal windows
```

### Restart a Service
```powershell
# Kill the service with Ctrl+C
# Then re-run the command
```

### Check Status Anytime
```powershell
python check_deployment_status.py
```

### Clear All Caches
```powershell
python manage.py cache_purge --all
```

### View Cache Health
```powershell
python manage.py cache_dashboard --health
```

---

## 💡 TIPS

1. **Keep all 5 terminals visible** if possible
   - Arrange them side by side
   - Or use Windows Terminal tabs (recommended)

2. **Monitor Terminal 5 (Dashboard)**
   - This shows real-time system health
   - Watch hit rate increase as requests come in

3. **Terminal 4 (Django) shows request logs**
   - You'll see which endpoints are being called
   - Check response times

4. **Terminal 2 & 3 (Celery) show background tasks**
   - Cache warming happens here
   - Keep eye on for any errors

5. **First requests will be slow** (no cache hits yet)
   - After ~50 requests, hit rate increases significantly
   - After ~200 requests, hit rate reaches 80%+

---

## 📖 DOCUMENTATION

| Document | Purpose | Read Time |
|----------|---------|-----------|
| LOCAL_DEPLOYMENT_CHECKLIST.md | Progress tracking | 5 min |
| README_FASE7.md | Technical reference | 30 min |
| ARCHITECTURE_OVERVIEW.md | System design | 15 min |
| CACHE_DASHBOARD.md | Monitoring guide | 20 min |
| MULTILEVEL_CACHE.md | Cache implementation | 25 min |
| DEPLOYMENT_GUIDE.md | Staging/Prod setup | 60 min |

---

## ✨ STATUS

- **Current:** You're reading this guide
- **Next:** Open 4 new terminals and start services
- **Then:** Monitor dashboard
- **Finally:** Run tests and prepare for staging

**Estimated time to completion:** 30 minutes

Good luck! 🚀

# Monitoring & Profiling - Fase 6 Task #8 (Final)

## Overview

Complete monitoring and profiling system for production visibility with:
1. Django Debug Toolbar (development)
2. Silk APM (production profiling)
3. Custom performance dashboard
4. Real-time metrics collection
5. Alerting system

**Impact:**
- Complete visibility into application performance
- 100% observability for bottleneck identification
- Automatic performance degradation detection
- Real-time health status monitoring

---

## Architecture

### Monitoring Stack

```
┌─────────────────────────────────────────────────────────┐
│                   Django Application                     │
│              (Performance Middleware)                    │
└────────┬────────────────────────────────────────────────┘
         │
         ├─→ Request Latency Tracking
         ├─→ Database Query Profiling
         ├─→ Cache Hit/Miss Tracking
         ├─→ Celery Task Monitoring
         └─→ Resource Utilization
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│            Monitoring Dashboard                          │
│  /monitoring/dashboard/                                 │
│  - Real-time metrics                                    │
│  - Performance charts                                   │
│  - Health indicators                                    │
│  - Alert notifications                                  │
└────────┬────────────────────────────────────────────────┘
         │
         ├─→ /api/monitoring/metrics/
         ├─→ /api/monitoring/health/
         ├─→ /api/monitoring/requests/
         ├─→ /api/monitoring/database/
         ├─→ /api/monitoring/cache/
         ├─→ /api/monitoring/celery/
         ├─→ /api/monitoring/queries/
         └─→ /api/monitoring/slowest/
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│            Metrics Storage                               │
│  - Database (Django models)                             │
│  - Redis (real-time cache)                              │
│  - InfluxDB (optional, time-series)                     │
└─────────────────────────────────────────────────────────┘
```

### Tools Integration

```
DEVELOPMENT                     PRODUCTION
─────────────────────────────────────────────

Debug Toolbar                   Silk APM
  │                               │
  ├─ SQL Queries                  ├─ Python Profiling
  ├─ Templates                    ├─ Request Tracing
  ├─ Cache                        ├─ Query Analysis
  ├─ Signals                      ├─ Async Tasks
  └─ Logging                      └─ Performance Stats
      │                               │
      └──────────┬──────────────────┘
                 │
                 ▼
         Custom Dashboard
         ├─ Real-time Metrics
         ├─ Historical Trends
         ├─ Alerts & Notifications
         └─ Performance Reports
```

---

## Installation & Configuration

### Step 1: Install Dependencies

```bash
# Development tools
pip install django-debug-toolbar

# Production profiling
pip install django-silk

# Metrics collection
pip install psutil  # For resource metrics

# Optional: Time-series database
pip install influxdb
```

### Step 2: Configure settings.py

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... existing apps ...
    'django.contrib.admin',
    'django.contrib.auth',
    
    # Monitoring (development)
    'debug_toolbar' if DEBUG else None,
    
    # Monitoring (production)
    'silk' if SILK_ENABLED else None,
]

# Import monitoring configuration
from config.monitoring_settings import (
    get_debug_toolbar_config,
    get_silk_config,
    get_monitoring_logging_config,
    MonitoringConfig,
)

# Debug Toolbar configuration (development)
if DEBUG:
    DEBUG_TOOLBAR_CONFIG = get_debug_toolbar_config()

# Silk configuration (production)
if MonitoringConfig.SILK_ENABLED:
    for key, value in get_silk_config().items():
        globals()[f"SILKY_{key}"] = value

# Logging configuration
LOGGING = get_monitoring_logging_config()

# Add performance middleware
MIDDLEWARE = [
    # ... existing middleware ...
    'debug_toolbar.middleware.DebugToolbarMiddleware' if DEBUG else None,
    'silk.middleware.SilkyMiddleware' if MonitoringConfig.SILK_ENABLED else None,
    'qms.profiling_views.PerformanceMiddleware',  # Custom performance tracking
]
```

### Step 3: Configure urls.py

```python
from django.urls import path, include
from qms.profiling_views import (
    MonitoringDashboardView,
    metrics_api,
    health_api,
    request_metrics_api,
    database_metrics_api,
    cache_metrics_api,
    celery_metrics_api,
    slowest_queries_api,
    slowest_requests_api,
)

urlpatterns = [
    # ... existing URLs ...
    
    # Monitoring Dashboard
    path('monitoring/', MonitoringDashboardView.as_view(), name='monitoring_dashboard'),
    
    # Monitoring APIs
    path('api/monitoring/metrics/', metrics_api, name='metrics_api'),
    path('api/monitoring/health/', health_api, name='health_api'),
    path('api/monitoring/requests/', request_metrics_api, name='request_metrics_api'),
    path('api/monitoring/database/', database_metrics_api, name='database_metrics_api'),
    path('api/monitoring/cache/', cache_metrics_api, name='cache_metrics_api'),
    path('api/monitoring/celery/', celery_metrics_api, name='celery_metrics_api'),
    path('api/monitoring/queries/', slowest_queries_api, name='slowest_queries_api'),
    path('api/monitoring/slowest/', slowest_requests_api, name='slowest_requests_api'),
]

# Debug Toolbar (development)
if settings.DEBUG:
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]

# Silk (production)
if settings.SILK_ENABLED:
    urlpatterns += [path('silk/', include('silk.urls'))]
```

### Step 4: Environment Variables

```bash
# Debug Toolbar
DEBUG_TOOLBAR_ENABLED=true  # development

# Silk APM (production)
SILK_ENABLED=false
SILK_INTERCEPT_PERCENT=10  # Profile 10% of requests

# Monitoring
DB_STATS_COLLECTION_ENABLED=true
LOG_SLOW_QUERIES=true
LOG_SLOW_REQUESTS=true
LOG_SLOW_TASKS=true

# Thresholds
SLOW_QUERY_THRESHOLD=500    # ms
SLOW_REQUEST_THRESHOLD=1000  # ms
SLOW_TASK_THRESHOLD=5000     # ms

# Alerting
ALERTING_ENABLED=false
ALERT_EMAIL_ENABLED=false
ALERT_SLACK_ENABLED=false
```

---

## Monitoring Features

### 1. Django Debug Toolbar (Development)

**Location:** Bottom-right corner of browser (in development)

**Features:**
- SQL query profiling with execution time
- Template rendering timing
- Cache operations
- Signal handlers
- HTTP headers inspection
- Logging output

**Access:**
```
http://localhost:8000/__debug__/
```

**Configuration:**
```python
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda r: DEBUG,
    'SQL_WARNING_THRESHOLD': 500,  # ms
    'SHOW_CACHE': True,
    'SHOW_PROFILING': True,
}
```

### 2. Silk APM (Production)

**Location:** `/silk/`

**Features:**
- Python profiling (cProfile integration)
- Request/response inspection
- Query profiling
- Response time analysis
- Async task tracking

**Access:**
```
/silk/  # Main interface
/silk/profile/  # Python profiles
```

**Configuration:**
```python
SILKY_INTERCEPT_PERCENT = 10  # Profile 10% of requests
SILKY_LOG_QUERIES = True
SILKY_AUTHENTICATION = True
```

### 3. Custom Monitoring Dashboard

**Location:** `/monitoring/`

**Features:**
- Real-time request metrics
- Database performance dashboard
- Cache hit rate tracking
- Celery task monitoring
- System resource utilization
- Health status indicator

**Access:**
```
/monitoring/  # Full dashboard
/api/monitoring/metrics/  # JSON metrics
/api/monitoring/health/  # Health status
```

### 4. Performance Metrics

#### Request Metrics
```json
{
  "avg_response_time": 150.5,    // ms
  "p95_response_time": 300.0,
  "p99_response_time": 500.0,
  "request_count": 15000,
  "error_count": 45,
  "error_rate": 0.3               // 0.3%
}
```

#### Database Metrics
```json
{
  "total_queries": 45000,
  "avg_query_time": 8.5,          // ms
  "slow_queries": 12,
  "cache_hits": 28000,
  "cache_misses": 17000,
  "cache_hit_rate": 0.622,        // 62.2%
  "connection_pool_utilization": 0.65  // 65%
}
```

#### Cache Metrics
```json
{
  "total_hits": 50000,
  "total_misses": 15000,
  "hit_rate": 0.769,              // 76.9%
  "memory_usage": "245MB",
  "evictions": 234
}
```

#### Celery Metrics
```json
{
  "total_tasks": 8500,
  "successful_tasks": 8420,
  "failed_tasks": 45,
  "success_rate": 0.991,          // 99.1%
  "avg_task_time": 2500.0,        // ms
  "dlq_tasks": 12,
  "queue_depth": 45
}
```

---

## Performance Thresholds

### Request Performance

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Response Time | < 100ms | 100-300ms | > 1000ms |
| Error Rate | < 0.1% | 0.1-1% | > 1% |

### Database Performance

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Query Time | < 10ms | 10-50ms | > 500ms |
| Query Count | < 5 | 5-20 | > 50 |
| Cache Hit Rate | > 70% | 50-70% | < 30% |
| Pool Utilization | < 70% | 70-80% | > 95% |

### Celery Tasks

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| Task Duration | < 1s | 1-5s | > 30s |
| Failure Rate | < 1% | 1-5% | > 5% |
| Queue Depth | < 50 | 50-100 | > 200 |

### Resource Usage

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| CPU Usage | < 70% | 70-90% | > 90% |
| Memory Usage | < 75% | 75-90% | > 90% |
| Disk Usage | < 70% | 70-85% | > 90% |

---

## Slow Query Detection

### Enable Slow Query Logging

```bash
export LOG_SLOW_QUERIES=true
export SLOW_QUERY_THRESHOLD=500  # ms
```

### View Slow Queries

```bash
# Check slow query log
tail -f logs/slow_queries.log

# Find most common slow queries
grep "Slow query" logs/slow_queries.log | \
  awk '{print $5}' | sort | uniq -c | sort -rn | head -20
```

### Optimize Slow Queries

1. **Check query execution plan:**
   ```sql
   EXPLAIN ANALYZE SELECT * FROM qms_instrumento WHERE ativo = true;
   ```

2. **Add missing indices:**
   ```python
   # In Django model
   class Meta:
       indexes = [
           models.Index(fields=['ativo']),
           models.Index(fields=['categoria', 'ativo']),
       ]
   ```

3. **Use select_related/prefetch_related:**
   ```python
   from qms.utils.query_optimizer import InstrumentoQueryOptimizer
   instrumentos = InstrumentoQueryOptimizer.por_filtros(filters)
   ```

---

## Alerting

### Email Alerts

```bash
export ALERTING_ENABLED=true
export ALERT_EMAIL_ENABLED=true
export ALERT_EMAIL_TO=admin@example.com
export ALERT_EMAIL_FROM=monitoring@example.com
```

### Slack Alerts

```bash
export ALERTING_ENABLED=true
export ALERT_SLACK_ENABLED=true
export ALERT_SLACK_WEBHOOK=https://hooks.slack.com/services/...
export ALERT_SLACK_CHANNEL=#alerts
```

### Custom Alerts

```python
from config.monitoring_settings import PerformanceMonitor, AlertLevel

monitor = PerformanceMonitor()

# Check request performance
level, msg = monitor.check_request_performance(duration_ms=1500)
if level == AlertLevel.CRITICAL:
    send_alert(f"Critical performance issue: {msg}")

# Check query performance
level, msg = monitor.check_query_performance(duration_ms=800)
if level == AlertLevel.CRITICAL:
    send_alert(f"Slow database query: {msg}")
```

---

## API Endpoints

### Health Check

```bash
curl -X GET http://localhost:8000/api/monitoring/health/
```

Response:
```json
{
  "status": "healthy",
  "issues": [],
  "timestamp": "2025-12-09T15:30:00"
}
```

### Request Metrics

```bash
curl -X GET http://localhost:8000/api/monitoring/requests/
```

### Database Metrics

```bash
curl -X GET http://localhost:8000/api/monitoring/database/
```

### Slowest Queries

```bash
curl -X GET http://localhost:8000/api/monitoring/queries/?limit=10
```

### All Metrics

```bash
curl -X GET http://localhost:8000/api/monitoring/metrics/
```

---

## Logging

### Log Locations

```
logs/
├── monitoring.log          # General monitoring logs
├── slow_queries.log        # Queries > 500ms
├── slow_requests.log       # Requests > 1000ms
└── slow_tasks.log          # Celery tasks > 5000ms
```

### Log Format

```
WARNING 2025-12-09 15:45:30 calibra.slow_queries query_logger - 
  SELECT * FROM qms_instrumento WHERE ativo = true - 650ms
```

### View Logs

```bash
# Monitor slow queries in real-time
tail -f logs/slow_queries.log

# Find slowest queries
sort -t'-' -k2 -rn logs/slow_queries.log | head -20

# Get statistics
grep "Slow" logs/slow_queries.log | wc -l
```

---

## Production Deployment

### Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: monitoring-config
data:
  SILK_ENABLED: "true"
  SILK_INTERCEPT_PERCENT: "10"
  LOG_SLOW_QUERIES: "true"
  SLOW_QUERY_THRESHOLD: "500"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-app
spec:
  template:
    spec:
      containers:
      - name: django
        envFrom:
        - configMapRef:
            name: monitoring-config
```

### Docker

```dockerfile
FROM python:3.11

# Install dependencies
RUN pip install django-silk psutil

# Copy monitoring config
COPY config/monitoring_settings.py /app/config/

# Set environment variables
ENV SILK_ENABLED=true
ENV LOG_SLOW_QUERIES=true

CMD ["gunicorn", "config.wsgi:application"]
```

---

## Best Practices

### ✅ Do's

1. **Monitor in production**
   ```bash
   export SILK_ENABLED=true
   export SILK_INTERCEPT_PERCENT=10  # 10% sampling
   ```

2. **Set realistic thresholds**
   ```python
   # 500ms for slow queries (not 50ms)
   SLOW_QUERY_THRESHOLD = 500
   ```

3. **Review metrics regularly**
   ```bash
   # Daily review of slow queries
   grep "Slow query" logs/slow_queries.log | wc -l
   ```

4. **Enable alerting**
   ```bash
   export ALERTING_ENABLED=true
   export ALERT_EMAIL_ENABLED=true
   ```

5. **Archive old logs**
   ```bash
   # Rotate logs every 10MB, keep 5 backups
   maxBytes = 10485760  # 10MB
   backupCount = 5
   ```

### ❌ Don'ts

1. **Don't disable monitoring in production**
   ```python
   # SILK_ENABLED = False  # Bad!
   SILK_ENABLED = True  # Good
   ```

2. **Don't set thresholds too low**
   ```python
   # SLOW_QUERY_THRESHOLD = 50  # Too low (100% of queries)
   SLOW_QUERY_THRESHOLD = 500  # Better
   ```

3. **Don't ignore alerts**
   ```bash
   # Review daily:
   tail -f logs/monitoring.log
   ```

4. **Don't forget to adjust after optimization**
   ```python
   # After optimization, re-baseline:
   # Check current p95 and set threshold 20% above
   ```

5. **Don't store metrics forever**
   ```python
   # Clean up old metrics
   METRICS_RETENTION_DAYS = 30
   ```

---

## Troubleshooting

### Issue: Debug Toolbar not showing

**Symptoms:** Toolbar not visible in development

**Solution:**
```python
# Check settings.py
DEBUG = True
DEBUG_TOOLBAR_ENABLED = True

# Check INTERNAL_IPS
INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Ensure toolbar is in INSTALLED_APPS
'debug_toolbar' in INSTALLED_APPS
```

### Issue: Silk profiling overhead too high

**Symptoms:** Response times 2-3x slower with Silk enabled

**Solution:**
```bash
# Reduce sampling rate
export SILK_INTERCEPT_PERCENT=5  # 5% instead of 100%

# Or disable profiling in specific views
@silk_profile_only(flag_name='profile_this_view')
def my_view(request):
    ...
```

### Issue: Slow log growing too large

**Symptoms:** `slow_queries.log` consuming 10GB+

**Solution:**
```python
# Enable log rotation in settings
'handlers': {
    'slow_queries': {
        'maxBytes': 10485760,  # 10MB
        'backupCount': 5,      # Keep 5 files
    }
}

# Or manually clean
rm logs/slow_queries.log.* && touch logs/slow_queries.log
```

### Issue: Dashboard not loading

**Symptoms:** `/monitoring/` returns 404 or 500

**Solution:**
```bash
# Ensure URLs are configured
grep "monitoring/" config/urls.py

# Check view is callable
python manage.py shell
from qms.profiling_views import MonitoringDashboardView
MonitoringDashboardView.as_view()

# Restart Django
python manage.py runserver
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Development Tool** | Django Debug Toolbar (SQL, templates, cache) |
| **Production Tool** | Silk APM (profiling, tracing, analytics) |
| **Custom Dashboard** | Real-time metrics at `/monitoring/` |
| **Performance Metrics** | Request, database, cache, Celery, resources |
| **Slow Detection** | Configurable thresholds for all metrics |
| **Logging** | File-based with rotation and retention |
| **Alerting** | Email and Slack support |
| **API Endpoints** | 8 JSON endpoints for metrics |
| **Thresholds** | Request 100-1000ms, Query 10-500ms, Task 1-30s |
| **Overhead** | < 5% with 10% sampling (Silk) |

---

## References

- [Django Debug Toolbar](https://django-debug-toolbar.readthedocs.io/)
- [Django Silk](https://github.com/jazzband/django-silk)
- [Prometheus Metrics](https://prometheus.io/docs/)
- [InfluxDB Integration](https://docs.influxdata.com/)

---

**Last Updated:** 2025-12-09  
**Fase 6 Task:** #8 (Monitoring & Profiling - Final)  
**Status:** Complete ✅  
**Overall Fase 6 Status:** 8/8 Tasks Complete - 100% ✅

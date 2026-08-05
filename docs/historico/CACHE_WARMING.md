# Cache Warming System

## Overview

The cache warming system proactively fills the cache with frequently accessed data, reducing cache misses and improving user experience.

**Key Features:**
- ✅ Access pattern analysis (hotness scoring)
- ✅ Predictive warming based on patterns
- ✅ Time-of-day based warming
- ✅ User-specific data warming
- ✅ Off-peak bulk warming
- ✅ Automatic Celery scheduling
- ✅ Warming effectiveness monitoring

**Architecture:**

```
Cache Access Patterns
    ↓
AccessPatternAnalyzer
    ├─ Record: key, user, timestamp
    ├─ Identify: Hot (85%+ hit), Warm (20-84%), Cold (<20%)
    ├─ Detect: Peak hours, off-peak hours
    └─ Calculate: Hotness score
    ↓
CacheWarmer
    ├─ Warm Hot Items (top 20)
    ├─ Warm Peak Hour Items (predictions)
    ├─ Warm Off-Peak Models (bulk)
    └─ Warm User-Specific Data
    ↓
Celery Beat Scheduler
    ├─ Every hour: Warm hot items
    ├─ Every 15 min: Warm peak hour items
    ├─ Daily 2 AM: Warm all models
    └─ Every 6 hours: Warm active user data
    ↓
Higher Cache Hit Rate ✓
```

---

## Components

### 1. AccessPattern

Tracks access statistics for individual cache keys.

**Attributes:**
- `key`: Cache key
- `access_count`: Total accesses
- `unique_users`: Set of accessing users
- `timestamps`: Recent access times
- `score`: Calculated popularity score

**Methods:**

```python
pattern = AccessPattern("instrument_5")
pattern.record_access(user_id=123)
pattern.record_access(user_id=456)

if pattern.is_hot(threshold=50.0):
    print(f"Hot! Score: {pattern.score}")

# Score calculation:
# - Base: access_count * 1.0
# - Users: unique_users * 10.0
# - Recency: recent_accesses * 5.0
```

**Score Tiers:**

| Category | Score | TTL | Warm? |
|----------|-------|-----|-------|
| **Hot** | 50+ | 1h | Yes, hourly |
| **Warm** | 20-49 | 10m | Sometimes |
| **Cold** | <20 | 1m | No |

### 2. AccessPatternAnalyzer

Analyzes access patterns across all cache keys.

**Usage:**

```python
from qms.cache_warming import access_analyzer

# Record an access
access_analyzer.record_access(
    key="instrument_5",
    model_name="Instrument",
    user_id=123
)

# Get hot keys
hot_keys = access_analyzer.get_hot_keys(limit=20, threshold=50.0)
# Returns: ['instrument_5', 'instrument_12', ...]

# Get model popularity
popularity = access_analyzer.get_model_popularity("Instrument")
# Returns: {'instrument_5': 125.5, 'instrument_12': 98.3, ...}

# Get peak hours (highest traffic)
peak = access_analyzer.get_peak_hours(top_n=3)
# Returns: [10, 14, 18]  (10 AM, 2 PM, 6 PM)

# Get off-peak hours (best for warming)
off_peak = access_analyzer.get_off_peak_hours(top_n=3)
# Returns: [2, 3, 4]  (2-4 AM)

# Get statistics
stats = access_analyzer.get_stats()
# {
#   'total_patterns': 1250,
#   'hot_keys': 45,
#   'warm_keys': 203,
#   'avg_score': 38.2,
#   'max_score': 487.1,
#   'peak_hours': [10, 14, 18],
#   'off_peak_hours': [2, 3, 4]
# }

# Reset patterns (periodically)
access_analyzer.reset()
```

### 3. CacheWarmer

Warms cache with frequently accessed data.

**Warming Methods:**

```python
from qms.cache_warming import cache_warmer
from config.multilevel_cache import multi_level_cache

# 1. Warm hot items (most accessed)
count = cache_warmer.warm_hot_items(multi_level_cache, top_n=20)
print(f"Warmed {count} hot items")

# 2. Warm by time pattern (items popular at current hour)
count = cache_warmer.warm_by_time_pattern(multi_level_cache)

# 3. Warm entire model
count = cache_warmer.warm_model_data(
    "Instrument",
    multi_level_cache,
    limit=100  # Top 100 instances
)

# 4. Warm user-specific data
count = cache_warmer.warm_user_data(user_id=123, cache_mgr=multi_level_cache)

# 5. Register custom warming function
def warm_instruments(instance_ids):
    """Custom warming for instruments."""
    from qms.models import Instrument
    instruments = Instrument.objects.filter(id__in=instance_ids)
    return [i.__dict__ for i in instruments]

cache_warmer.register_warmer("Instrument", warm_instruments)
```

**Expected Warming Times:**

```
Operation            Items     Time      Frequency
─────────────────────────────────────────────────
Warm hot items       20-50     100ms     Every hour
Warm peak hour       50-100    500ms     Every 15 min
Warm off-peak        1000s     10s       Daily 2 AM
Warm active users    500-1000  2s        Every 6 hours
```

### 4. Warming Strategies

Pluggable strategies for different warming scenarios.

```python
from qms.cache_warming import (
    HotItemsWarmingStrategy,
    TimeBasedWarmingStrategy,
    ModelBasedWarmingStrategy,
    CompositeWarmingStrategy
)

# Strategy 1: Warm hot items only
hot_strategy = HotItemsWarmingStrategy(limit=20)

# Strategy 2: Warm items popular at current time
time_strategy = TimeBasedWarmingStrategy()

# Strategy 3: Warm entire models
model_strategy = ModelBasedWarmingStrategy("Instrument", limit=100)

# Strategy 4: Combine multiple strategies
composite = CompositeWarmingStrategy([
    hot_strategy,
    time_strategy,
    model_strategy,
])

# Execute
count = composite.warm(multi_level_cache, access_analyzer)
```

---

## Integration

### 1. Record Cache Accesses

**In API Views:**

```python
from rest_framework import viewsets
from rest_framework.response import Response
from qms.cache_warming import record_cache_access
from config.cache_managers import ModelInstanceCache

class InstrumentViewSet(viewsets.ViewSet):
    cache_mgr = ModelInstanceCache()
    
    def retrieve(self, request, pk=None):
        # Record access for warming
        record_cache_access(
            key=f"instrument_{pk}",
            model_name="Instrument",
            user_id=request.user.id if request.user else None
        )
        
        # Get cached or database data
        data = self.cache_mgr.get(f"instrument_{pk}")
        if not data:
            from qms.models import Instrument
            inst = Instrument.objects.get(pk=pk)
            data = InstrumentSerializer(inst).data
            self.cache_mgr.set(f"instrument_{pk}", data, ttl=3600)
        
        return Response(data)
```

**In Admin/Dashboard:**

```python
from qms.cache_warming import record_api_access

def instrument_list(request):
    """Track dashboard access."""
    record_api_access(request, "instrument_list")
    
    # Get instruments (warmed by previous accesses)
    instruments = Instrument.objects.all()
    return render(request, 'instruments.html', {'instruments': instruments})
```

### 2. Schedule Warming Tasks

**In `config/celery.py`:**

```python
from celery import Celery
from celery.schedules import crontab
from qms.cache_warming_tasks import get_warming_beat_schedule

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Add warming schedules
app.conf.beat_schedule.update(get_warming_beat_schedule())

# Optional: Create cache_warming and cache_monitoring queues
app.conf.task_queues = (
    Queue('default'),
    Queue('cache_warming', routing_key='cache.warming'),
    Queue('cache_monitoring', routing_key='cache.monitoring'),
    Queue('cache_optimization', routing_key='cache.optimization'),
)
```

### 3. Monitor Effectiveness

**Celery Tasks:**

```python
# These run automatically when scheduled:
# - warm_hot_items: Every hour
# - warm_peak_hour_items: Every 15 minutes
# - warm_off_peak_items: Daily 2 AM
# - warm_active_user_data: Every 6 hours
# - analyze_access_patterns: Every hour
# - monitor_warming_effectiveness: Every 30 minutes
# - optimize_cache_ttls: Daily 1 AM
# - reset_access_patterns: Daily 1:30 AM
```

**Manual Monitoring:**

```python
from qms.cache_warming_tasks import (
    analyze_access_patterns,
    monitor_warming_effectiveness,
)

# Trigger immediately (for testing)
result = analyze_access_patterns.delay()
print(result.get())

# Check effectiveness
result = monitor_warming_effectiveness.delay()
print(result.get())
# Output:
# {
#   'status': 'success',
#   'combined_hit_rate': 0.87,  # 87%
#   'l1': 0.35, 'l2': 0.52, 'l3': 0.78
# }
```

---

## Best Practices

### 1. Record All Accesses

✅ **Good:**
```python
# Record API access
record_cache_access(f"instrument_{pk}", "Instrument", user.id)

# Record admin access
record_api_access(request, "instrument_admin", pk)
```

❌ **Bad:**
```python
# Forgot to record - no warming data
data = get_instrument(pk)
```

### 2. Let Warming Run

✅ **Good:**
```python
# Let Celery Beat run scheduled warming
# - Automatically warms hot items hourly
# - Predictively warms peak hour items
# - Off-peak warming at 2 AM
```

❌ **Bad:**
```python
# Manual warming (error-prone)
# warm_cache()  # When to call? Overhead?
```

### 3. Monitor Effectiveness

✅ **Good:**
```python
# Dashboard shows:
# - Cache hit rate: 87%
# - Hot keys: 45 (warmed)
# - Peak hours: 10 AM, 2 PM, 6 PM
# - Off-peak hours: 2-4 AM
```

❌ **Bad:**
```python
# No monitoring - assume it works
# May have degraded hit rate without notice
```

### 4. Optimize Based on Data

✅ **Good:**
```python
# Analyze patterns daily
# Adjust TTL for hot/warm/cold keys
# Adjust warming times based on peak hours
# Reset patterns weekly to capture trends
```

❌ **Bad:**
```python
# Static configuration
# Same warming regardless of traffic patterns
```

---

## Performance Metrics

### Expected Improvement

**Before Warming:**
- Cache hit rate: 60-70% (without prediction)
- Peak hour hit rate: 40-50% (requests outpace warming)
- Off-peak hit rate: 85%+ (cache stable)

**After Warming:**
- Cache hit rate: 85-92% (predictive warming)
- Peak hour hit rate: 75-85% (pre-warmed)
- Off-peak hit rate: 95%+ (complete)

**Improvement: +10-25% hit rate increase**

### Overhead

```
Warming Operation        Latency    CPU    Memory
────────────────────────────────────────────────
Record access            <1ms       0.1%   1KB
Analyze patterns         100ms      2%     10MB
Warm 20 hot items        100ms      5%     20MB
Warm 100 warm items      500ms      10%    50MB
Warm 1000 off-peak       10s        15%    200MB
```

**Net Benefit:**
- Small overhead during warming
- Large improvement in hit rate
- Offset by reduced database queries

---

## Troubleshooting

### Issue: Hot Keys Not Detected

**Symptoms:**
- `hot_keys` list is empty
- `access_analyzer.get_stats()` shows 0 patterns

**Diagnosis:**
```bash
# Check if accesses are being recorded
python manage.py shell
>>> from qms.cache_warming import access_analyzer
>>> access_analyzer.get_stats()
```

**Solutions:**

1. **Check if recording calls exist:**
   ```python
   # Grep for record_cache_access calls
   grep -r "record_cache_access" --include="*.py"
   ```

2. **Add recording to views:**
   ```python
   # In your API views
   from qms.cache_warming import record_cache_access
   
   @api_view(['GET'])
   def get_instrument(request, pk):
       record_cache_access(f"instrument_{pk}", "Instrument", request.user.id)
       # ...
   ```

3. **Generate test traffic:**
   ```bash
   # Simulate accesses
   python manage.py shell
   >>> from qms.cache_warming import access_analyzer
   >>> for i in range(100):
   ...     access_analyzer.record_access(f"instrument_{i % 5}", "Instrument", i % 10)
   >>> access_analyzer.get_stats()
   ```

### Issue: Warming Not Running

**Symptoms:**
- Cache hit rate not improving
- Celery tasks not executing

**Diagnosis:**
```bash
# Check Celery Beat status
celery -A config inspect active

# Check scheduled tasks
celery -A config inspect scheduled

# Check queue status
celery -A config inspect active_queues
```

**Solutions:**

1. **Verify Celery Beat is running:**
   ```bash
   celery -A config beat
   ```

2. **Verify schedule is registered:**
   ```python
   # In celery.py
   from qms.cache_warming_tasks import get_warming_beat_schedule
   app.conf.beat_schedule.update(get_warming_beat_schedule())
   ```

3. **Check task logs:**
   ```bash
   # Monitor Celery worker
   celery -A config worker -l info
   ```

### Issue: High Memory Usage During Warming

**Symptoms:**
- Memory spikes during off-peak warming
- Server becomes slow at 2 AM

**Solutions:**

1. **Reduce warming batch sizes:**
   ```python
   # In cache_warming_tasks.py
   limit=50  # Was 100, now warm fewer items
   ```

2. **Spread warming over time:**
   ```python
   # Warm in smaller chunks
   for batch in chunks(items, size=10):
       warm_model_data("Instrument", multi_level_cache, limit=10)
       time.sleep(1)  # Space them out
   ```

3. **Monitor memory:**
   ```bash
   # Track memory during warming
   watch -n 1 'free -h | grep Mem'
   ```

### Issue: Warming Not Improving Hit Rate

**Symptoms:**
- Run warming, but hit rate stays same
- `monitor_warming_effectiveness` shows no improvement

**Diagnosis:**
```python
# Check if cache is persisting warmed data
stats = multi_level_cache.get_stats()
if stats['L3']['size'] < 100:  # Should be warming items
    print("Cache not persisting warmed data")
```

**Solutions:**

1. **Verify cache configuration:**
   ```python
   # Check Redis is accessible
   from config.multilevel_cache import multi_level_cache
   multi_level_cache.set("test", "value", ttl=3600)
   assert multi_level_cache.get("test") == "value"
   ```

2. **Check warming is actually running:**
   ```bash
   # Check logs for warming tasks
   tail -f celery_worker.log | grep "warm_"
   ```

3. **Increase warming frequency:**
   ```python
   # Warm more often during peak hours
   # In get_warming_beat_schedule():
   'cache-warm-peak-hour': {
       'schedule': crontab(minute='*/5'),  # Every 5 min (was 15)
   },
   ```

---

## Configuration

### Warming Thresholds

```python
# In qms/cache_warming.py
class AccessPattern:
    def is_hot(self, threshold: float = 50.0) -> bool:  # Adjust this
        return self.score >= threshold
    
    def is_warm(self, threshold: float = 20.0) -> bool:  # And this
        return threshold <= self.score < 50.0
```

### Warming Limits

```python
# In cache_warming_tasks.py
def warm_hot_items(self, limit: int = 20):  # Adjust top N
    # ...

def warm_off_peak_items(self):
    limit=50  # Adjust per-model limit
```

### Schedule Times

```python
# In cache_warming_tasks.py > get_warming_beat_schedule()
'cache-warm-off-peak': {
    'schedule': crontab(hour=2, minute=0),  # Change from 2 AM
},
```

---

## API Reference

```python
# AccessPatternAnalyzer
from qms.cache_warming import access_analyzer

access_analyzer.record_access(key, model_name, user_id)
access_analyzer.get_hot_keys(limit, threshold)  # → List[str]
access_analyzer.get_warm_keys(limit, threshold)  # → List[str]
access_analyzer.get_model_popularity(model_name)  # → Dict
access_analyzer.get_peak_hours(top_n)  # → List[int]
access_analyzer.get_off_peak_hours(top_n)  # → List[int]
access_analyzer.get_stats()  # → Dict
access_analyzer.reset()

# CacheWarmer
from qms.cache_warming import cache_warmer

cache_warmer.warm_hot_items(cache_mgr, top_n)  # → int
cache_warmer.warm_by_time_pattern(cache_mgr, current_hour)  # → int
cache_warmer.warm_model_data(model_name, cache_mgr, limit)  # → int
cache_warmer.warm_user_data(user_id, cache_mgr)  # → int
cache_warmer.register_warmer(model_name, warming_func)

# Monitoring Functions
from qms.cache_warming import record_cache_access, record_api_access

record_cache_access(key, model_name, user_id)
record_api_access(request, view_name, model_id)

# Celery Tasks
from qms.cache_warming_tasks import (
    warm_hot_items,
    warm_peak_hour_items,
    warm_off_peak_items,
    warm_active_user_data,
    analyze_access_patterns,
    monitor_warming_effectiveness,
    optimize_cache_ttls,
)

task_result = warm_hot_items.delay(limit=20)
task_result.get()  # Get result
```

---

## Summary

The cache warming system provides:

1. **Access Pattern Analysis** via AccessPatternAnalyzer
2. **Predictive Warming** based on patterns and time
3. **Automatic Scheduling** via Celery Beat
4. **Multiple Strategies** for different scenarios
5. **Effectiveness Monitoring** and optimization
6. **Easy Integration** with Django views and APIs

**Result:** +10-25% improvement in cache hit rates through intelligent, automated warming.

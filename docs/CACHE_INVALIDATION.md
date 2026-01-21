# Cache Invalidation System

## Overview

The intelligent cache invalidation system ensures that cached data remains consistent with the database while minimizing unnecessary cache clears. It combines automatic signal-based invalidation with smart TTL management for optimal performance.

**Key Features:**
- ✅ Automatic signal-based invalidation (post_save, post_delete)
- ✅ Cascading invalidation through model relationships
- ✅ Smart TTL management based on access patterns
- ✅ Batch invalidation for bulk operations
- ✅ Conditional invalidation by field
- ✅ Manual purge commands
- ✅ Monitoring and statistics

**Architecture Diagram:**

```
User Action
    ↓
Django Signal (post_save/post_delete)
    ↓
CacheDependencyTracker
    ├─ Check registered dependencies
    ├─ Invoke callbacks
    └─ Cascade through relationships
         ├─ Parent models (ForeignKey)
         ├─ Child models (Reverse relations)
         └─ M2M relationships
    ↓
MultiLevelCache
    ├─ L1 (Request): Clear by key
    ├─ L2 (Worker): Clear by pattern
    └─ L3 (Redis): Invalidate pattern
    ↓
SmartTTLManager
    └─ Record invalidation event
    └─ Adjust TTL for future caches
    ↓
Consistent Cache State ✓
```

---

## Components

### 1. CacheDependencyTracker

Tracks relationships between models and coordinates cascading invalidation.

**Purpose:**
- Register model dependencies
- Track which caches depend on which models
- Coordinate callbacks on model changes

**Key Methods:**

```python
from config.cache_invalidation import dependency_tracker

# Register a dependency
dependency_tracker.add_dependency(
    source=Category,           # When Category changes
    dependent=Instrument,      # Invalidate Instrument cache
    cascade=True               # Cascade through relationships
)

# Add custom callback
def on_category_change(instance):
    # Custom logic when category changes
    notify_dashboard(f"Category {instance.id} changed")

dependency_tracker.add_callback(Category, on_category_change)

# Get affected models
affected = dependency_tracker.get_affected_models(Category)
# Returns: {Instrument, Procedure, ...}

# Manually invalidate
count = dependency_tracker.invalidate_for_model(Instrument, instance)
# Returns: 3 (number of affected caches)
```

### 2. CascadingInvalidator

Automatically invalidates related model caches when a model changes.

**How It Works:**

```
User saves Instrument
    ↓
CascadingInvalidator.cascade_invalidate(instrument)
    ├─ Level 0: instrument_* (direct)
    ├─ Level 1: 
    │   ├─ categoria_* (parent via FK)
    │   ├─ calibracao_* (children)
    │   └─ manutencao_* (children)
    └─ Level 2:
        └─ Further relationships...
    ↓
All related caches cleared
```

**Usage:**

```python
from config.cache_invalidation import CascadingInvalidator
from qms.models import Instrument

instance = Instrument.objects.get(pk=1)

# Cascade invalidate with default depth (2)
count = CascadingInvalidator.cascade_invalidate(instance)
print(f"Cleared {count} cache entries")

# Custom depth
count = CascadingInvalidator.cascade_invalidate(instance, depth=3)

# Returns: 15 (all related caches)
```

**Invalidation Depth:**
- **Depth 0:** Only direct cache (instrument_1)
- **Depth 1:** + Parent models (categoria_5)
- **Depth 2:** + Child models (calibracao_*, manutencao_*)
- **Depth 3:** + Grandchild and M2M (default: 2)

### 3. SmartTTLManager

Dynamically adjusts cache TTL based on access patterns.

**How It Works:**

```
Cache Key: instrument_5

1. Record Access
   smart_ttl.record_access("instrument_5")
   → Access count: 1

2. Monitor Pattern
   - If accessed 5+ times per hour → HOT
   - If accessed 1-5 times per hour → WARM
   - If accessed rarely → COLD

3. Assign TTL
   - HOT:  1 hour   (frequently accessed, worth keeping)
   - WARM: 10 min   (occasional access)
   - COLD: 1 min    (rarely used, expire quickly)

4. On Invalidation
   smart_ttl.record_invalidation("instrument_5")
   → If invalidated often, reduce TTL next time
```

**Usage:**

```python
from config.cache_invalidation import smart_ttl
from config.multilevel_cache import multi_level_cache

# Get recommended TTL for key
ttl = smart_ttl.get_optimal_ttl("instrument_5")
# Returns: 3600 (1 hour for hot key)

# Cache with smart TTL
from config.cache_managers import ModelInstanceCache

cache_mgr = ModelInstanceCache()
cache_mgr.set(
    "instrument_5",
    instrument_data,
    ttl=ttl  # Use smart TTL
)

# Get statistics
stats = smart_ttl.get_stats()
# {
#   "total_keys": 42,
#   "total_accesses": 1250,
#   "hot_keys": ["instrument_5", "instrument_12", ...],
#   "warm_keys": [...],
#   "cold_keys": [...]
# }

# Reset statistics
smart_ttl.reset_stats()
```

**TTL Thresholds:**

| Category | Access Freq | TTL | Use Case |
|----------|-------------|-----|----------|
| **Hot** | 5+ /hour | 1h (3600s) | Frequently accessed instruments |
| **Warm** | 1-5 /hour | 10m (600s) | Occasionally accessed data |
| **Cold** | <1 /hour | 1m (60s) | Rarely accessed, expire quickly |

### 4. BatchInvalidator

Efficiently invalidate multiple patterns in one operation.

**Usage:**

```python
from config.cache_invalidation import BatchInvalidator

batch = BatchInvalidator()

# Add multiple patterns
batch.add_patterns([
    "instrument_*",
    "query_instrument*",
    "agg_instrument*",
])

# Execute batch (more efficient than individual calls)
count = batch.execute()
print(f"Cleared {count} entries")

# Clear for next batch
batch.clear()
```

### 5. register_model_cache_invalidation()

Automatically register signal handlers for any model.

**Usage:**

```python
from config.cache_invalidation import register_model_cache_invalidation
from qms.models import Instrument

# Simple registration
register_model_cache_invalidation(Instrument)

# Advanced: with custom patterns and invalidator
register_model_cache_invalidation(
    model=Instrument,
    cache_key_pattern="instrument_{id}_*",  # Custom pattern
    related_models=[Category, CalibrationHistory],  # Cascade to these
    custom_invalidator=my_custom_func,  # Custom logic
)
```

---

## Signal-Based Invalidation

### Automatic Setup

The easiest way is to register signals in your Django app's `ready()` method:

**In `qms/apps.py`:**

```python
from django.apps import AppConfig

class QmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'qms'
    verbose_name = 'QMS - Sistema de Gestão'

    def ready(self):
        # Initialize cache invalidation
        from qms.cache_signals import initialize_cache_invalidation
        initialize_cache_invalidation()
```

### What Gets Invalidated

When a model is saved or deleted:

```python
from qms.models import Instrument, Category

# Create new Instrument
instrument = Instrument.objects.create(
    numero="INS-001",
    categoria=category,
    ...
)

# Automatically invalidated:
# ✓ instrument_* (direct cache)
# ✓ query_instrument_* (query results)
# ✓ agg_instrument_* (aggregates)
# ✓ categoria_X_* (parent category cache)
# ✓ user_X_* (user-specific views)
```

### Custom Invalidation Callbacks

Register custom functions to run when models change:

```python
from qms.cache_signals import dependency_tracker
from qms.models import Category

def on_category_change(category_instance):
    """Called when any Category is saved or deleted."""
    # Notify connected clients
    send_notification(
        "category_updated",
        category_id=category_instance.id
    )
    
    # Clear related dashboard cache
    multi_level_cache.invalidate_pattern("dashboard_*")

# Register callback
dependency_tracker.add_callback(Category, on_category_change)
```

---

## Conditional Invalidation

Only invalidate cache if specific fields change.

**Usage:**

```python
from config.cache_invalidation import should_invalidate_cache
from qms.models import Instrument

class InstrumentSerializer(ModelSerializer):
    def update(self, instance, validated_data):
        changed_fields = set(validated_data.keys())
        
        # Only invalidate if important fields changed
        important_fields = {'numero', 'categoria', 'descricao'}
        
        if should_invalidate_cache(instance, changed_fields, important_fields):
            # Invalidate cache
            multi_level_cache.delete(f"instrument_{instance.id}")
        
        return super().update(instance, validated_data)
```

**Example: Track Update Notifications**

```python
# Only notify if status changed
if 'status' in changed_fields:
    notify_stakeholders(f"Instrument status changed to {instance.status}")

# Only clear aggregates if numeric data changed
numeric_fields = {'valor', 'incerteza', 'tolerancia'}
if numeric_fields & changed_fields:
    multi_level_cache.invalidate_pattern("agg_*")
```

---

## Manual Cache Purging

### Management Command

```bash
# Clear entire cache
python manage.py cache_purge --all

# Clear by pattern
python manage.py cache_purge --pattern instrument_*

# Clear for specific URL
python manage.py cache_purge --url /api/instruments/

# Clear for specific model
python manage.py cache_purge --model Instrument

# Clear recent changes (last hour)
python manage.py cache_purge --since 1h

# Show statistics
python manage.py cache_purge --stats

# Show smart TTL recommendations
python manage.py cache_purge --ttl

# Reset all cache and statistics
python manage.py cache_purge --reset-all

# JSON output (for automation)
python manage.py cache_purge --stats --json
```

### Programmatic Purging

```python
from config.multilevel_cache import multi_level_cache
from config.cache_invalidation import smart_ttl

# Clear entire cache
multi_level_cache.clear()

# Clear by pattern
count = multi_level_cache.invalidate_pattern("instrument_*")
print(f"Cleared {count} entries")

# Delete specific key
multi_level_cache.delete("instrument_5")

# Reset TTL statistics
smart_ttl.reset_stats()
```

---

## Performance Metrics

### Expected Performance

| Scenario | Latency | Cache Hit Rate |
|----------|---------|----------------|
| **Without Caching** | 50-500ms | 0% |
| **HTTP Cache Only** | 1-2ms | 85-95% |
| **Multi-Level Only** | 0-10ms | 85-95% |
| **Full Stack** | 0-2ms | 95%+ |

### Invalidation Overhead

```
Invalidation Event Breakdown:

1. Django Signal (post_save)       ~0.5ms
2. CacheDependencyTracker lookup   ~0.3ms
3. CascadingInvalidator            ~1.0ms
4. MultiLevelCache invalidate      ~0.2ms
                                  --------
Total Invalidation Overhead:       ~2.0ms

Per-request hit: 0.5-1ms
Per-request miss + invalidation: 50-500ms + 2ms

Net benefit: 50-500x faster with caching
```

### Disk/Memory Usage

```
L1 (Request-scoped):  ~1-5 MB/request
L2 (Worker):          ~100-500 MB (configurable)
L3 (Redis):           ~1-10 GB (depends on dataset)

Total: 1-10 GB for typical installation
```

---

## Best Practices

### 1. Use Automatic Invalidation

✅ **Good:**
```python
# Signals automatically invalidate
instrument.save()  # Cache cleared automatically
```

❌ **Bad:**
```python
# Manual invalidation - easy to forget
instrument.save()
# Forgot to invalidate cache!
```

### 2. Leverage Cascading

✅ **Good:**
```python
# One change invalidates related caches
category.save()
# Also clears: instrument_*, procedimento_*, etc.
```

❌ **Bad:**
```python
# Manually invalidate each related model
category.save()
multi_level_cache.invalidate_pattern("instrument_*")
multi_level_cache.invalidate_pattern("procedimento_*")
# Easy to miss relationships
```

### 3. Use Smart TTL

✅ **Good:**
```python
# TTL automatically adjusts
ttl = smart_ttl.get_optimal_ttl("instrument_5")
cache.set("instrument_5", data, ttl=ttl)
```

❌ **Bad:**
```python
# Fixed TTL for everything
cache.set("instrument_5", data, ttl=3600)  # 1h always
# Hot data expires too soon, cold data expires too late
```

### 4. Batch Operations

✅ **Good:**
```python
# Batch invalidation (single operation)
batch = BatchInvalidator()
batch.add_patterns(["instrument_*", "query_*", "agg_*"])
batch.execute()
```

❌ **Bad:**
```python
# Individual invalidations (multiple operations)
multi_level_cache.invalidate_pattern("instrument_*")
multi_level_cache.invalidate_pattern("query_*")
multi_level_cache.invalidate_pattern("agg_*")
```

### 5. Monitor and Adjust

✅ **Good:**
```python
# Check cache efficiency regularly
stats = multi_level_cache.get_stats()
if stats['L2']['hit_rate'] < 0.40:
    # Increase L2 max_size
    
if stats['L3']['hit_rate'] < 0.70:
    # Reduce TTL values
```

❌ **Bad:**
```python
# "Set and forget" - no monitoring
# Cache slowly degrades without notice
```

---

## Troubleshooting

### Issue: Cache Hit Rate Too Low

**Symptoms:**
- L1: < 30% hit rate
- L2: < 40% hit rate
- L3: < 70% hit rate

**Diagnosis:**
```bash
python manage.py cache_purge --stats
```

**Solutions:**

1. **For L1 (Request-scoped):**
   ```python
   # Check if queries are in same request
   # If separate requests, that's normal (expect 20-30%)
   
   # If same request, use prefetch_related()
   instruments = Instrument.objects.prefetch_related('categoria').all()
   ```

2. **For L2 (Worker-scoped):**
   ```python
   # Increase LRU max_size
   # In config/multilevel_cache.py:
   worker_cache = WorkerCache(max_size=2000)  # Was 1000
   ```

3. **For L3 (Redis):**
   ```python
   # Reduce TTL values
   ttl_hot = 1800   # 30min (was 1h)
   ttl_warm = 300   # 5min (was 10m)
   ttl_cold = 30    # 30sec (was 1min)
   
   # But careful - too low TTL = more database hits
   ```

### Issue: Stale Cache Data

**Symptoms:**
- User sees old data after saving
- Different users see different data

**Diagnosis:**
```bash
# Check if signals are registered
python manage.py shell
>>> from qms.models import Instrument
>>> from django.db.models.signals import post_save
>>> from django.dispatch import receiver
>>> post_save.receivers  # Should show registered handlers
```

**Solutions:**

1. **Ensure signals are initialized:**
   ```python
   # In qms/apps.py ready() method:
   from qms.cache_signals import initialize_cache_invalidation
   initialize_cache_invalidation()
   ```

2. **Verify Redis connection:**
   ```bash
   redis-cli ping  # Should return PONG
   redis-cli info  # Check memory and stats
   ```

3. **Manual purge as temporary fix:**
   ```bash
   python manage.py cache_purge --all
   ```

### Issue: Cache Invalidation Too Aggressive

**Symptoms:**
- Too many cache clears
- Database hit rate high despite caching

**Diagnosis:**
```python
# Monitor smart TTL
stats = smart_ttl.get_stats()
print(stats['total_invalidations'])  # Should be low
```

**Solutions:**

1. **Use conditional invalidation:**
   ```python
   # Only invalidate if important fields changed
   if should_invalidate_cache(instance, changed_fields, important_fields):
       multi_level_cache.invalidate_pattern("instrument_*")
   ```

2. **Reduce cascading depth:**
   ```python
   # Only cascade 1 level instead of 2
   CascadingInvalidator.cascade_invalidate(instance, depth=1)
   ```

3. **Disable unnecessary cascades:**
   ```python
   dependency_tracker.add_dependency(
       source=MinorModel,
       dependent=MajorModel,
       cascade=False  # Don't cascade this relationship
   )
   ```

### Issue: Memory Usage Too High

**Symptoms:**
- Redis memory growing
- L2 worker memory high

**Solutions:**

1. **Reduce L2 max_size:**
   ```python
   # In config/multilevel_cache.py
   worker_cache = WorkerCache(max_size=500)  # Was 1000
   ```

2. **Reduce Redis TTL:**
   ```python
   ttl_hot = 1800   # 30min (was 1h)
   ttl_warm = 300   # 5min (was 10m)
   ```

3. **Monitor and clean up:**
   ```bash
   python manage.py cache_purge --stats
   # If stale data, manually purge
   python manage.py cache_purge --since 1h
   ```

---

## Integration Examples

### Example 1: API Endpoint with Cache Invalidation

```python
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from config.multilevel_cache import multi_level_cache
from config.cache_managers import ModelInstanceCache
from qms.models import Instrument

class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = '__all__'

class InstrumentViewSet(viewsets.ModelViewSet):
    queryset = Instrument.objects.all()
    serializer_class = InstrumentSerializer
    cache_mgr = ModelInstanceCache()
    
    def retrieve(self, request, pk=None):
        # Try cache first
        cached = self.cache_mgr.get(f"instrument_{pk}")
        if cached:
            return Response(cached)
        
        # Database query
        instrument = self.get_object()
        data = InstrumentSerializer(instrument).data
        
        # Cache with smart TTL
        ttl = smart_ttl.get_optimal_ttl(f"instrument_{pk}")
        self.cache_mgr.set(f"instrument_{pk}", data, ttl=ttl)
        
        return Response(data)
    
    def perform_update(self, serializer):
        serializer.save()
        # Signal automatically invalidates cache
        # No manual cache.delete() needed!
```

### Example 2: Background Task with Cache Warmup

```python
from celery import shared_task
from config.cache_invalidation import smart_ttl
from config.cache_managers import QueryResultCache
from qms.models import Instrument

@shared_task
def warmup_hot_instruments():
    """Pre-cache frequently accessed instruments."""
    cache_mgr = QueryResultCache()
    
    # Get hot instruments from TTL statistics
    hot_keys = smart_ttl.get_stats().get('hot_keys', [])
    
    for key in hot_keys:
        if key.startswith('instrument_'):
            inst_id = key.split('_')[1]
            
            # Prefetch from database
            instrument = Instrument.objects.get(pk=inst_id)
            
            # Cache with hot TTL
            ttl = smart_ttl.get_optimal_ttl(key)
            cache_mgr.set(key, instrument, ttl=ttl)
    
    logger.info(f"Warmed {len(hot_keys)} hot instruments")
```

### Example 3: Dashboard with Cache Monitoring

```python
from django.shortcuts import render
from config.multilevel_cache import multi_level_cache
from config.cache_invalidation import smart_ttl

def cache_dashboard(request):
    """Display cache statistics and health."""
    cache_stats = multi_level_cache.get_stats()
    ttl_stats = smart_ttl.get_stats()
    
    context = {
        'cache_stats': cache_stats,
        'ttl_stats': ttl_stats,
        'l1_hit_rate': cache_stats['L1']['hit_rate'],
        'l2_hit_rate': cache_stats['L2']['hit_rate'],
        'l3_hit_rate': cache_stats['L3']['hit_rate'],
        'combined_hit_rate': (
            cache_stats['L1']['hit_rate'] * 0.3 +
            cache_stats['L2']['hit_rate'] * 0.4 +
            cache_stats['L3']['hit_rate'] * 0.3
        ),
        'hot_keys': ttl_stats['hot_keys'][:10],
    }
    
    return render(request, 'cache_dashboard.html', context)
```

---

## Advanced Configuration

### Custom Invalidation Strategy

```python
from config.cache_invalidation import CacheDependencyTracker

# Create custom tracker
tracker = CacheDependencyTracker()

# Define complex dependencies
tracker.add_dependency(Category, Instrument, cascade=True)
tracker.add_dependency(Instrument, CalibrationHistory, cascade=True)

# Custom callback with business logic
def invalidate_reports(category):
    """Invalidate all reports using this category."""
    multi_level_cache.invalidate_pattern(f"report_category_{category.id}_*")
    multi_level_cache.invalidate_pattern("dashboard_summary")

tracker.add_callback(Category, invalidate_reports)

# Use custom tracker
count = tracker.invalidate_for_model(Category, category_instance)
```

### Custom TTL Profiles

```python
from config.cache_invalidation import SmartTTLManager

# Create custom TTL manager with different thresholds
class CustomTTLManager(SmartTTLManager):
    ttl_hot = 7200      # 2 hours (more aggressive caching)
    ttl_warm = 1800     # 30 minutes
    ttl_cold = 300      # 5 minutes
    
    access_threshold_hot = 10   # 10+ accesses = hot
    access_threshold_warm = 3   # 3-10 accesses = warm

custom_ttl = CustomTTLManager()
```

---

## Monitoring Checklist

- [ ] Cache hit rates > 80% (combined)
- [ ] L1 hit rate > 30% (request-scoped)
- [ ] L2 hit rate > 40% (worker-scoped)
- [ ] L3 hit rate > 70% (Redis)
- [ ] Invalidation events < 100/minute
- [ ] Average invalidation latency < 5ms
- [ ] Redis memory < 10 GB
- [ ] Worker memory < 1 GB
- [ ] Hot keys properly identified
- [ ] Smart TTL capturing patterns

---

## API Reference

```python
# CacheDependencyTracker
from config.cache_invalidation import dependency_tracker

dependency_tracker.add_dependency(source, dependent, cascade=True)
dependency_tracker.add_callback(model, callback_func)
dependency_tracker.get_affected_models(model)  # → Set[Model]
dependency_tracker.invalidate_for_model(model, instance)  # → int
dependency_tracker.clear_all()

# CascadingInvalidator
from config.cache_invalidation import CascadingInvalidator

CascadingInvalidator.cascade_invalidate(instance, depth=2)  # → int

# SmartTTLManager
from config.cache_invalidation import smart_ttl

smart_ttl.record_access(key)
smart_ttl.record_invalidation(key)
smart_ttl.get_optimal_ttl(key)  # → int (seconds)
smart_ttl.get_stats()  # → Dict
smart_ttl.reset_stats()

# BatchInvalidator
from config.cache_invalidation import BatchInvalidator

batch = BatchInvalidator()
batch.add_pattern(pattern)
batch.add_patterns([patterns...])
batch.execute()  # → int
batch.clear()

# Registration
from config.cache_invalidation import register_model_cache_invalidation

register_model_cache_invalidation(
    model,
    cache_key_pattern=None,
    related_models=None,
    custom_invalidator=None
)

# Conditional invalidation
from config.cache_invalidation import should_invalidate_cache

should_invalidate_cache(instance, changed_fields, important_fields)  # → bool
```

---

## Summary

The cache invalidation system provides:

1. **Automatic Invalidation** via Django signals
2. **Intelligent Cascading** through model relationships
3. **Smart TTL** that adapts to access patterns
4. **Batch Operations** for efficiency
5. **Manual Control** via management commands
6. **Full Monitoring** with statistics and recommendations

**Result:** 95%+ cache consistency with minimal overhead.

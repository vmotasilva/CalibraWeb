"""
Cache Invalidation System
=========================

Intelligent cache invalidation with:
1. Signal-based invalidation (automatic on model changes)
2. Cascading invalidation (for related objects)
3. Pattern-based invalidation (glob patterns)
4. Smart TTL management (based on access patterns)

Features:
- Automatic invalidation on model save/delete
- Cascading through foreign keys
- Pattern matching for bulk operations
- Dependency tracking
- Performance logging

Author: Caching Team
Date: 2025-12
"""

import logging
from typing import Type, Set, List, Dict, Callable, Optional
from weakref import WeakSet

from django.db.models import Model, ForeignKey, ManyToManyField, signals
from django.dispatch import receiver
from django.db.models.fields.related import ForeignObjectRel

from config.multilevel_cache import multi_level_cache
from config.cache_managers import (
    ModelInstanceCache,
    query_cache,
    aggregate_cache,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# CACHE DEPENDENCY TRACKER
# ════════════════════════════════════════════════════════════════

class CacheDependencyTracker:
    """
    Track cache dependencies between models.
    
    Manages relationships for cascading invalidation:
    - Parent-child relationships
    - Many-to-many dependencies
    - Reverse relationships
    
    Example:
        tracker = CacheDependencyTracker()
        
        # When Instrument changes, also invalidate Category cache
        tracker.add_dependency(Instrument, Category)
        
        # Invalidating Instrument will cascade to Category
        tracker.invalidate(Instrument, id=1)
    """

    def __init__(self):
        """Initialize dependency tracker."""
        # Model → Set of dependent models
        self.dependencies: Dict[Type[Model], Set[Type[Model]]] = {}
        
        # Invalidation callbacks
        self.callbacks: Dict[Type[Model], List[Callable]] = {}

    def add_dependency(
        self,
        source: Type[Model],
        dependent: Type[Model],
        cascade: bool = True
    ) -> None:
        """
        Register a cache dependency.
        
        Args:
            source: Model that, when changed, affects dependent
            dependent: Model whose cache should be invalidated
            cascade: Whether to cascade invalidation
            
        Example:
            tracker.add_dependency(Instrument, Category)
            # Invalidating Instrument → also invalidate Category
        """
        if source not in self.dependencies:
            self.dependencies[source] = set()
        
        self.dependencies[source].add(dependent)
        logger.debug(f"Registered dependency: {source.__name__} → {dependent.__name__}")

    def add_callback(
        self,
        model: Type[Model],
        callback: Callable
    ) -> None:
        """
        Register custom invalidation callback.
        
        Args:
            model: Model to watch
            callback: Function to call when model changes
                     Signature: (model_class, instance) -> None
        """
        if model not in self.callbacks:
            self.callbacks[model] = []
        
        self.callbacks[model].append(callback)
        logger.debug(f"Registered callback for {model.__name__}")

    def get_affected_models(self, model: Type[Model]) -> Set[Type[Model]]:
        """
        Get all models affected by changes to given model.
        
        Args:
            model: Source model
            
        Returns:
            Set of affected model classes
        """
        affected = {model}
        
        # Direct dependencies
        if model in self.dependencies:
            affected.update(self.dependencies[model])
        
        return affected

    def invalidate_for_model(
        self,
        model: Type[Model],
        instance: Optional[Model] = None,
        **kwargs
    ) -> int:
        """
        Invalidate cache for model and dependents.
        
        Args:
            model: Model class
            instance: Model instance (optional)
            **kwargs: Lookup parameters (id, pk, etc)
            
        Returns:
            Number of cache keys invalidated
        """
        count = 0
        affected_models = self.get_affected_models(model)

        for affected in affected_models:
            # Run custom callbacks
            if affected in self.callbacks:
                for callback in self.callbacks[affected]:
                    try:
                        callback(affected, instance)
                        count += 1
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

        return count

    def clear_all(self) -> None:
        """Clear all dependency registrations."""
        self.dependencies.clear()
        self.callbacks.clear()
        logger.debug("Dependency tracker cleared")


# ════════════════════════════════════════════════════════════════
# GLOBAL DEPENDENCY TRACKER
# ════════════════════════════════════════════════════════════════

cache_dependency_tracker = CacheDependencyTracker()


# ════════════════════════════════════════════════════════════════
# CACHE INVALIDATION SIGNALS
# ════════════════════════════════════════════════════════════════

def register_model_cache_invalidation(
    model: Type[Model],
    cache_key_pattern: str = None,
    related_models: List[Type[Model]] = None,
    custom_invalidator: Callable = None,
) -> None:
    """
    Register automatic cache invalidation for a model.
    
    Automatically clears cache when model instances change.
    
    Args:
        model: Django model class
        cache_key_pattern: Pattern for cache keys (e.g., 'instrument_*')
                          Auto-generated if None
        related_models: Models to also invalidate
        custom_invalidator: Custom function to invalidate cache
                           Signature: (instance) -> None
    
    Example:
        from qms.models import Instrument
        
        register_model_cache_invalidation(
            Instrument,
            cache_key_pattern='instrument_*',
            related_models=[Category],
            custom_invalidator=lambda inst: cache.delete(f'summary_{inst.id}')
        )
    """
    model_name = model.__name__.lower()
    pattern = cache_key_pattern or f"{model_name}_*"

    @receiver(signals.post_save, sender=model, dispatch_uid=f"cache_invalidate_{model_name}_save")
    def invalidate_on_save(sender, instance, created, **kwargs):
        """Invalidate cache when model is saved."""
        operation = "created" if created else "updated"
        logger.info(f"Invalidating cache for {model_name} (id={instance.pk}, {operation})")

        # Invalidate specific instance
        multi_level_cache.delete(f"{model_name}_{instance.pk}")

        # Invalidate pattern (lists, queries)
        multi_level_cache.invalidate_pattern(pattern)

        # Invalidate aggregates
        multi_level_cache.invalidate_pattern(f"agg_{model_name}*")

        # Run custom invalidator
        if custom_invalidator:
            try:
                custom_invalidator(instance)
            except Exception as e:
                logger.error(f"Custom invalidator error: {e}")

        # Invalidate related models
        if related_models:
            for related in related_models:
                related_name = related.__name__.lower()
                multi_level_cache.invalidate_pattern(f"{related_name}_*")
                logger.debug(f"Cascaded invalidation to {related_name}")

    @receiver(signals.post_delete, sender=model, dispatch_uid=f"cache_invalidate_{model_name}_delete")
    def invalidate_on_delete(sender, instance, **kwargs):
        """Invalidate cache when model is deleted."""
        logger.info(f"Invalidating cache for deleted {model_name} (id={instance.pk})")

        # Invalidate specific instance
        multi_level_cache.delete(f"{model_name}_{instance.pk}")

        # Invalidate all lists/queries
        multi_level_cache.invalidate_pattern(pattern)

        # Invalidate aggregates
        multi_level_cache.invalidate_pattern(f"agg_{model_name}*")

        # Invalidate related models
        if related_models:
            for related in related_models:
                related_name = related.__name__.lower()
                multi_level_cache.invalidate_pattern(f"{related_name}_*")


# ════════════════════════════════════════════════════════════════
# CASCADING INVALIDATION
# ════════════════════════════════════════════════════════════════

class CascadingInvalidator:
    """
    Handle cascading cache invalidation through relationships.
    
    When a model instance changes, invalidate:
    1. Direct instance cache
    2. List/query caches (patterns)
    3. Parent objects (foreign keys)
    4. Child objects (reverse relations)
    5. Many-to-many related objects
    
    Example:
        invalidator = CascadingInvalidator()
        
        # Invalidate Instrument and cascade to Category, Procedures, etc
        invalidator.cascade_invalidate(instrument_instance)
    """

    @staticmethod
    def cascade_invalidate(instance: Model, depth: int = 2) -> int:
        """
        Cascade invalidation through model relationships.
        
        Args:
            instance: Model instance that changed
            depth: How deep to cascade (default: 2 levels)
            
        Returns:
            Number of cache keys invalidated
        """
        model = type(instance)
        model_name = model.__name__.lower()
        invalidated_count = 0

        # 1. Invalidate instance itself
        multi_level_cache.delete(f"{model_name}_{instance.pk}")
        invalidated_count += 1
        logger.debug(f"Invalidated {model_name} instance: {instance.pk}")

        # 2. Invalidate query results
        invalidated_count += multi_level_cache.invalidate_pattern(f"query_{model_name}*")

        # 3. Invalidate aggregates
        invalidated_count += multi_level_cache.invalidate_pattern(f"agg_{model_name}*")

        if depth <= 0:
            return invalidated_count

        # 4. Invalidate parent objects (foreign keys)
        for field in model._meta.get_fields():
            if isinstance(field, ForeignKey):
                try:
                    parent = getattr(instance, field.name)
                    if parent:
                        parent_name = parent.__class__.__name__.lower()
                        multi_level_cache.delete(f"{parent_name}_{parent.pk}")
                        invalidated_count += 1
                        logger.debug(f"Cascaded to parent {parent_name}: {parent.pk}")
                except Exception as e:
                    logger.debug(f"Cascade to parent failed: {e}")

        # 5. Invalidate related child objects
        for relation in model._meta.related_objects:
            try:
                related_name = relation.related_model.__name__.lower()
                invalidated_count += multi_level_cache.invalidate_pattern(
                    f"{related_name}_{instance.pk}_*"
                )
            except Exception as e:
                logger.debug(f"Cascade to children failed: {e}")

        # 6. Invalidate many-to-many
        for field in model._meta.many_to_many:
            try:
                related_name = field.remote_field.model.__name__.lower()
                invalidated_count += multi_level_cache.invalidate_pattern(f"{related_name}_*")
            except Exception as e:
                logger.debug(f"Cascade to M2M failed: {e}")

        return invalidated_count


# ════════════════════════════════════════════════════════════════
# SMART TTL MANAGEMENT
# ════════════════════════════════════════════════════════════════

class SmartTTLManager:
    """
    Manage cache TTL based on access patterns.
    
    Adjusts TTL dynamically:
    - Frequently accessed data: longer TTL
    - Rarely accessed data: shorter TTL
    - Recently invalidated: shorter TTL
    - Stable data: longer TTL
    
    Example:
        ttl_mgr = SmartTTLManager()
        
        # Get optimal TTL for data
        ttl = ttl_mgr.get_optimal_ttl('user_1')
        # Returns: 3600 (1 hour) for frequently accessed
        #        or  300 (5 min) for rarely accessed
    """

    def __init__(self):
        """Initialize smart TTL manager."""
        # Track access counts and invalidation patterns
        self.access_counts: Dict[str, int] = {}
        self.invalidation_counts: Dict[str, int] = {}
        
        # Base TTL values
        self.ttl_hot = 3600  # 1 hour for frequently accessed
        self.ttl_warm = 600  # 10 minutes for moderate access
        self.ttl_cold = 60   # 1 minute for rarely accessed

    def record_access(self, key: str) -> None:
        """Record that a key was accessed."""
        self.access_counts[key] = self.access_counts.get(key, 0) + 1

    def record_invalidation(self, key: str) -> None:
        """Record that a key was invalidated."""
        self.invalidation_counts[key] = self.invalidation_counts.get(key, 0) + 1

    def get_optimal_ttl(self, key: str, default_ttl: int = 600) -> int:
        """
        Calculate optimal TTL for a key.
        
        Args:
            key: Cache key
            default_ttl: Default TTL if no data
            
        Returns:
            Recommended TTL in seconds
        """
        access_count = self.access_counts.get(key, 0)
        invalidation_count = self.invalidation_counts.get(key, 0)

        # Too many invalidations → short TTL
        if invalidation_count > 100:
            return self.ttl_cold

        # High access count → long TTL
        if access_count > 1000:
            return self.ttl_hot
        
        # Moderate access → medium TTL
        if access_count > 100:
            return self.ttl_warm
        
        # Low access → short TTL
        return self.ttl_cold

    def get_stats(self) -> Dict[str, any]:
        """Get TTL management statistics."""
        return {
            'tracked_keys': len(self.access_counts),
            'total_accesses': sum(self.access_counts.values()),
            'total_invalidations': sum(self.invalidation_counts.values()),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.access_counts.clear()
        self.invalidation_counts.clear()


# ════════════════════════════════════════════════════════════════
# GLOBAL SMART TTL INSTANCE
# ════════════════════════════════════════════════════════════════

smart_ttl = SmartTTLManager()


# ════════════════════════════════════════════════════════════════
# BATCH INVALIDATION
# ════════════════════════════════════════════════════════════════

class BatchInvalidator:
    """
    Invalidate cache in batches for efficiency.
    
    Useful for:
    - Bulk updates
    - Scheduled invalidation
    - Maintenance operations
    
    Example:
        invalidator = BatchInvalidator()
        
        # Invalidate multiple patterns
        invalidator.add_pattern('user_*')
        invalidator.add_pattern('instrument_*')
        invalidator.add_pattern('category_*')
        
        # Execute all at once
        count = invalidator.execute()
        print(f"Invalidated {count} keys")
    """

    def __init__(self):
        """Initialize batch invalidator."""
        self.patterns: List[str] = []

    def add_pattern(self, pattern: str) -> None:
        """Add pattern to invalidation batch."""
        if pattern not in self.patterns:
            self.patterns.append(pattern)

    def add_patterns(self, patterns: List[str]) -> None:
        """Add multiple patterns."""
        for pattern in patterns:
            self.add_pattern(pattern)

    def execute(self) -> int:
        """
        Execute batch invalidation.
        
        Returns:
            Total number of keys invalidated
        """
        total = 0
        
        logger.info(f"Executing batch invalidation ({len(self.patterns)} patterns)")
        
        for pattern in self.patterns:
            count = multi_level_cache.invalidate_pattern(pattern)
            total += count
            logger.debug(f"Invalidated pattern {pattern}: {count} keys")

        self.patterns.clear()
        logger.info(f"Batch invalidation complete: {total} keys")
        
        return total

    def clear(self) -> None:
        """Clear pending patterns without executing."""
        self.patterns.clear()


# ════════════════════════════════════════════════════════════════
# CONDITIONAL INVALIDATION
# ════════════════════════════════════════════════════════════════

def should_invalidate_cache(
    instance: Model,
    changed_fields: Set[str],
    important_fields: Set[str],
) -> bool:
    """
    Determine if cache should be invalidated based on changed fields.
    
    Only invalidate if important fields changed (not timestamp fields, etc).
    
    Args:
        instance: Model instance
        changed_fields: Fields that changed
        important_fields: Fields that matter for caching
        
    Returns:
        True if cache should be invalidated
        
    Example:
        # Only invalidate if name or price changed, not updated_at
        should_invalidate = should_invalidate_cache(
            product,
            changed_fields={'name', 'price', 'updated_at'},
            important_fields={'name', 'price', 'category'}
        )
    """
    # If no important fields changed, don't invalidate
    important_changed = changed_fields & important_fields
    
    return len(important_changed) > 0


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════
#
# from qms.models import Instrument, Category
# from config.cache_invalidation import (
#     register_model_cache_invalidation,
#     CascadingInvalidator,
#     smart_ttl
# )
#
# # 1. Register automatic invalidation
# register_model_cache_invalidation(
#     Instrument,
#     cache_key_pattern='instrument_*',
#     related_models=[Category]
# )
#
# # 2. Cascade invalidate on save
# @receiver(post_save, sender=Instrument)
# def invalidate_instrument(sender, instance, **kwargs):
#     CascadingInvalidator.cascade_invalidate(instance)
#
# # 3. Use smart TTL
# ttl = smart_ttl.get_optimal_ttl('instrument_1')
#
# ════════════════════════════════════════════════════════════════

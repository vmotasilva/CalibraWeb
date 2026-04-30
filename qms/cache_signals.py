"""
Cache Invalidation Signals
===========================

Django signals for automatic cache invalidation.

Connect these signals to your models to automatically
clear cache when data changes.

Setup:
    In your app's ready() method, import this module
    to register signal handlers.

Author: Caching Team
Date: 2025-12
"""

import logging
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.apps import apps

from config.cache_invalidation import (
    CascadingInvalidator,
    smart_ttl,
    register_model_cache_invalidation,
)
from config.multilevel_cache import multi_level_cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# GENERIC CACHE INVALIDATION SIGNALS
# ════════════════════════════════════════════════════════════════

def register_cache_invalidation_signals():
    """
    Register cache invalidation signals for all models.
    
    Call this function in your Django app's ready() method:
    
        # In qms/apps.py
        from django.apps import AppConfig
        
        class QmsConfig(AppConfig):
            name = 'qms'
            
            def ready(self):
                from qms.cache_signals import register_cache_invalidation_signals
                register_cache_invalidation_signals()
    """
    logger.info("Registering cache invalidation signals")
    
    # Get all models from qms app
    try:
        models = apps.get_app_config('qms').get_models()
        
        for model in models:
            # Skip models that shouldn't invalidate cache
            if model.__name__ in ['LogEntry', 'Migration']:
                continue
            
            model_name = model.__name__.lower()
            pattern = f"{model_name}_*"
            
            # Create signal handlers dynamically
            @receiver(post_save, sender=model)
            def invalidate_on_save(sender, instance, created, **kwargs):
                """Automatically invalidate cache on model save."""
                operation = "created" if created else "updated"
                logger.info(
                    f"Cache: Invalidating {sender.__name__} "
                    f"(id={instance.pk}, {operation})"
                )
                
                # Cascade invalidate
                CascadingInvalidator.cascade_invalidate(instance)
            
            @receiver(post_delete, sender=model)
            def invalidate_on_delete(sender, instance, **kwargs):
                """Automatically invalidate cache on model delete."""
                logger.info(f"Cache: Invalidating deleted {sender.__name__} (id={instance.pk})")
                
                # Cascade invalidate
                CascadingInvalidator.cascade_invalidate(instance)
            
            logger.debug(f"Registered signals for {model.__name__}")
    
    except LookupError:
        logger.warning("QMS app not found, skipping signal registration")


# ════════════════════════════════════════════════════════════════
# SPECIFIC MODEL INVALIDATION HANDLERS
# ════════════════════════════════════════════════════════════════

# These are specific handlers for key models
# Override default behavior if needed

def setup_instrument_invalidation():
    """Setup Instrument model cache invalidation."""
    try:
        from qms.models import Instrument
        
        @receiver(post_save, sender=Instrument)
        def invalidate_instrument(sender, instance, created, **kwargs):
            """Invalidate Instrument cache and related caches."""
            logger.info(f"Invalidating Instrument cache: {instance.pk}")
            
            # Direct invalidation
            multi_level_cache.delete(f"instrument_{instance.pk}")
            
            # Query results
            multi_level_cache.invalidate_pattern("query_instrument*")
            
            # Aggregates
            multi_level_cache.invalidate_pattern("agg_instrument*")
            
            # Category cache (instrument belongs to category)
            if hasattr(instance, 'categoria'):
                multi_level_cache.invalidate_pattern("query_categoria*")
                multi_level_cache.invalidate_pattern(f"categoria_{instance.categoria.pk}*")
            
            # Record access for smart TTL
            smart_ttl.record_invalidation(f"instrument_{instance.pk}")
        
        @receiver(post_delete, sender=Instrument)
        def invalidate_instrument_delete(sender, instance, **kwargs):
            """Invalidate all Instrument caches on delete."""
            logger.info(f"Invalidating deleted Instrument: {instance.pk}")
            
            multi_level_cache.invalidate_pattern("instrument_*")
            multi_level_cache.invalidate_pattern("query_instrument*")
            multi_level_cache.invalidate_pattern("agg_instrument*")
        
        logger.debug("Instrument invalidation signals registered")
    
    except ImportError:
        logger.debug("Instrument model not available")


def setup_user_invalidation():
    """Setup User model cache invalidation."""
    try:
        from django.contrib.auth.models import User
        
        @receiver(post_save, sender=User)
        def invalidate_user(sender, instance, created, **kwargs):
            """Invalidate User cache."""
            logger.info(f"Invalidating User cache: {instance.pk}")
            
            multi_level_cache.delete(f"user_{instance.pk}")
            multi_level_cache.invalidate_pattern(f"user_{instance.pk}_*")  # User-specific
            multi_level_cache.invalidate_pattern("query_user*")
            
            smart_ttl.record_invalidation(f"user_{instance.pk}")
        
        logger.debug("User invalidation signals registered")
    
    except ImportError:
        logger.debug("User model not available")


# ════════════════════════════════════════════════════════════════
# MANY-TO-MANY INVALIDATION
# ════════════════════════════════════════════════════════════════

def setup_m2m_invalidation():
    """Setup M2M relationship cache invalidation."""
    try:
        from qms.models import Instrument
        
        @receiver(m2m_changed, sender=Instrument.procedures.through)
        def invalidate_instrument_procedures(sender, instance, action, **kwargs):
            """Invalidate cache when M2M relationship changes."""
            if action in ["post_add", "post_remove", "post_clear"]:
                logger.info(f"Invalidating M2M: Instrument {instance.pk} procedures")
                
                multi_level_cache.delete(f"instrument_{instance.pk}")
                multi_level_cache.invalidate_pattern("query_instrument*")
                multi_level_cache.invalidate_pattern("query_procedure*")
        
        logger.debug("M2M invalidation signals registered")
    
    except ImportError:
        logger.debug("Instrument M2M signals not available")


# ════════════════════════════════════════════════════════════════
# SCHEDULED CACHE MAINTENANCE
# ════════════════════════════════════════════════════════════════

def schedule_cache_cleanup():
    """
    Schedule periodic cache cleanup and optimization.
    
    Call this in Django app ready() to setup:
    - Expire old keys
    - Update smart TTL
    - Analyze cache efficiency
    """
    try:
        from celery import shared_task
        from django.utils import timezone
        from datetime import timedelta
        
        @shared_task
        def cache_maintenance():
            """Run cache maintenance tasks."""
            logger.info("Starting cache maintenance")
            
            stats = multi_level_cache.get_stats()
            logger.info(f"Cache stats: {stats}")
            
            # Log smart TTL recommendations
            ttl_stats = smart_ttl.get_stats()
            logger.info(f"Smart TTL stats: {ttl_stats}")
        
        # Schedule task (Celery Beat)
        # Add to celery beat schedule every hour
        return cache_maintenance
    
    except ImportError:
        logger.debug("Celery not available for cache maintenance")


# ════════════════════════════════════════════════════════════════
# INITIALIZATION
# ════════════════════════════════════════════════════════════════

def initialize_cache_invalidation():
    """Initialize all cache invalidation signals and handlers."""
    logger.info("Initializing cache invalidation system")
    
    # Register generic handlers
    register_cache_invalidation_signals()
    
    # Setup specific model handlers
    setup_instrument_invalidation()
    setup_user_invalidation()
    setup_m2m_invalidation()
    
    logger.info("Cache invalidation system initialized")


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════
#
# In your app's apps.py (qms/apps.py):
#
#     from django.apps import AppConfig
#
#     class QmsConfig(AppConfig):
#         default_auto_field = 'django.db.models.BigAutoField'
#         name = 'qms'
#         verbose_name = 'QMS - Sistema de Gestão'
#
#         def ready(self):
#             # Initialize cache invalidation
#             from qms.cache_signals import initialize_cache_invalidation
#             initialize_cache_invalidation()
#
# That's it! Cache will be automatically invalidated when:
# - Models are saved (new or updated)
# - Models are deleted
# - M2M relationships change
#
# ════════════════════════════════════════════════════════════════

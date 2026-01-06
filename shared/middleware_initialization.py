"""
Lazy initialization middleware - runs one-time setup tasks on first request
"""
import logging
import os
from django.utils.decorators import sync_only_middleware
from django.core.management import call_command

logger = logging.getLogger(__name__)

# Flag to track if initialization has run
_INITIALIZED = False


@sync_only_middleware
def lazy_initialization_middleware(get_response):
    """
    Middleware that runs initialization tasks on the first request.
    This allows the container to start quickly and avoid blocking startup.
    """
    global _INITIALIZED
    
    def middleware(request):
        global _INITIALIZED
        
        if not _INITIALIZED:
            _INITIALIZED = True
            logger.info("=== LAZY INITIALIZATION RUNNING ===")
            
            try:
                # Run migrations
                logger.info("Running migrations...")
                call_command('migrate', '--noinput')
                logger.info("✓ Migrations completed")
            except Exception as e:
                logger.warning(f"Migration error (non-fatal): {e}")
            
            try:
                # Collect static files
                logger.info("Collecting static files...")
                call_command('collectstatic', '--noinput', '--clear')
                logger.info("✓ Static files collected")
            except Exception as e:
                logger.warning(f"Collectstatic error (non-fatal): {e}")
            
            try:
                # Ensure superuser exists
                logger.info("Ensuring superuser exists...")
                call_command('ensure_superuser')
                logger.info("✓ Superuser check completed")
            except Exception as e:
                logger.warning(f"Superuser error (non-fatal): {e}")
            
            logger.info("=== LAZY INITIALIZATION COMPLETED ===")
        
        response = get_response(request)
        return response
    
    return middleware

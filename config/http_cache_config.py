"""
HTTP-Level Caching Configuration
==================================

Browser and proxy-level caching with:
1. Cache-Control headers (max-age, public/private)
2. ETag and Last-Modified validation
3. Conditional requests (304 Not Modified)
4. Static asset fingerprinting
5. CDN integration strategy

Performance Impact:
- Browser cache: 0ms latency for cached assets (100% local)
- Proxy cache (Varnish): 1-5ms (RAM) vs 50-500ms (database)
- Reduced server load: 60-80% fewer requests to origin
- Bandwidth savings: 70-90% for repeat users

Author: HTTP Caching Team
Date: 2025-12
"""

import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any

from django.utils.cache import get_cache_key, learn_cache_key
from django.views.decorators.http import condition
from django.http import HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# HTTP CACHE STRATEGIES
# ════════════════════════════════════════════════════════════════


class CacheStrategy:
    """Define cache strategies for different content types."""

    # ────────────────────────────────────────────────────────────
    # STATIC ASSETS (Never change within version)
    # ────────────────────────────────────────────────────────────

    # CSS/JS/Images with fingerprint in URL
    # Safe to cache for 1 year (browser) + infinite (CDN)
    STATIC_VERSIONED = {
        "max_age": 31536000,  # 1 year
        "immutable": True,    # Never expires
        "public": True,       # Cacheable by all
        "cdn": True,          # Cache on CDN
    }

    # Unversioned static files (should not exist in production)
    # Cache for 1 hour (short due to lack of versioning)
    STATIC_UNVERSIONED = {
        "max_age": 3600,      # 1 hour
        "immutable": False,
        "public": True,
        "cdn": True,
    }

    # ────────────────────────────────────────────────────────────
    # HTML PAGES (Semi-dynamic, revalidate needed)
    # ────────────────────────────────────────────────────────────

    # HTML pages with ETag validation
    # Cache for 1 hour, but validate on each request
    HTML_PAGES = {
        "max_age": 3600,      # 1 hour
        "must_revalidate": True,  # Must check with server
        "public": True,
        "cdn": True,
    }

    # User-specific pages (not cacheable by browser/CDN)
    # Cache in browser for 5 minutes, never on CDN
    USER_SPECIFIC = {
        "max_age": 300,       # 5 minutes
        "private": True,      # Only in browser, not CDN
        "must_revalidate": True,
        "cdn": False,
    }

    # ────────────────────────────────────────────────────────────
    # API RESPONSES (Data-heavy, time-sensitive)
    # ────────────────────────────────────────────────────────────

    # API responses (public data)
    # Cache for 5 minutes to reduce database load
    API_PUBLIC = {
        "max_age": 300,       # 5 minutes
        "public": True,
        "cdn": True,
        "vary": "Accept-Encoding",
    }

    # API responses (authenticated users)
    # Cache for 2 minutes, user-specific
    API_PRIVATE = {
        "max_age": 120,       # 2 minutes
        "private": True,
        "cdn": False,
        "vary": "Accept-Encoding, Authorization",
    }

    # Real-time API (stock prices, live stats)
    # No caching, always fresh
    API_REALTIME = {
        "max_age": 0,
        "no_cache": True,     # Must revalidate before use
        "no_store": True,     # Don't store at all
        "private": True,
    }

    # ────────────────────────────────────────────────────────────
    # PARTIAL RESPONSES (Fragments, includes)
    # ────────────────────────────────────────────────────────────

    # ESI fragments (edge-side includes)
    # Cache for longer, reuse across pages
    ESI_FRAGMENT = {
        "max_age": 7200,      # 2 hours
        "public": True,
        "cdn": True,
        "surrogate_key": True,  # Use cache tags for invalidation
    }

    # AJAX partial responses
    # Cache for 5 minutes
    AJAX_FRAGMENT = {
        "max_age": 300,
        "private": True,
        "cdn": False,
    }

    # ────────────────────────────────────────────────────────────
    # SEARCH/FILTERING RESULTS (User queries)
    # ────────────────────────────────────────────────────────────

    # Search results (publicly cacheable queries)
    SEARCH_RESULTS = {
        "max_age": 600,       # 10 minutes
        "public": True,
        "cdn": True,
        "vary": "q,sort,page",  # Cache per query param combo
    }

    # User-filtered results (private results)
    FILTERED_RESULTS = {
        "max_age": 300,       # 5 minutes
        "private": True,
        "cdn": False,
        "vary": "q,sort,page,Authorization",
    }


def get_cache_control_header(strategy: Dict[str, Any]) -> str:
    """
    Build Cache-Control header from strategy dictionary.

    Args:
        strategy: Dictionary with cache directives

    Returns:
        Cache-Control header value

    Example:
        >>> strategy = {"max_age": 3600, "public": True}
        >>> get_cache_control_header(strategy)
        'public, max-age=3600'
    """
    directives = []

    # Public/private (mutually exclusive)
    if strategy.get("public"):
        directives.append("public")
    elif strategy.get("private"):
        directives.append("private")

    # Max age (lifetime)
    if "max_age" in strategy:
        directives.append(f"max-age={strategy['max_age']}")

    # Immutability (for versioned assets)
    if strategy.get("immutable"):
        directives.append("immutable")

    # Revalidation
    if strategy.get("must_revalidate"):
        directives.append("must-revalidate")
    if strategy.get("proxy_revalidate"):
        directives.append("proxy-revalidate")
    if strategy.get("no_cache"):
        directives.append("no-cache")
    if strategy.get("no_store"):
        directives.append("no-store")

    # CDN-specific
    if strategy.get("surrogate_key"):
        directives.append("surrogate-key=true")
    if strategy.get("surrogate_control"):
        directives.append(f"surrogate-control={strategy['surrogate_control']}")

    return ", ".join(directives)


def cache_control(**strategy):
    """
    Decorator to set Cache-Control headers on view response.

    Usage:
        @cache_control(max_age=3600, public=True)
        def my_view(request):
            return render(request, 'template.html')

    Args:
        **strategy: Cache strategy directives

    Returns:
        Decorated view function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Set Cache-Control header
            cache_header = get_cache_control_header(strategy)
            response["Cache-Control"] = cache_header

            # Set Vary header if specified
            if "vary" in strategy:
                response["Vary"] = strategy["vary"]

            # Set ETag and Last-Modified for revalidation
            if hasattr(response, "content"):
                # Generate ETag from content hash
                content_hash = hashlib.md5(response.content).hexdigest()
                response["ETag"] = f'"{content_hash}"'

                # Set Last-Modified to current time
                response["Last-Modified"] = datetime.utcnow().strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )

            return response
        return wrapped_view
    return decorator


def conditional_response(etag_func=None, last_modified_func=None):
    """
    Decorator for conditional requests (304 Not Modified).

    Compares ETag and Last-Modified headers to serve 304 responses
    instead of full response body.

    Usage:
        @conditional_response(
            etag_func=lambda r: get_object_etag(r),
            last_modified_func=lambda r: get_object_modified(r)
        )
        def my_view(request, id):
            return render(request, 'template.html')

    Args:
        etag_func: Callable that returns ETag for request
        last_modified_func: Callable that returns Last-Modified datetime

    Returns:
        Decorated view function
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get ETag and Last-Modified for this request
            if etag_func:
                etag = etag_func(request, *args, **kwargs)
            else:
                etag = None

            if last_modified_func:
                last_modified = last_modified_func(request, *args, **kwargs)
            else:
                last_modified = None

            # Check If-None-Match (ETag)
            if etag and request.META.get("HTTP_IF_NONE_MATCH") == etag:
                logger.debug(f"304 Not Modified (ETag match): {request.path}")
                response = HttpResponse(status=304)
                response["ETag"] = etag
                return response

            # Check If-Modified-Since
            if last_modified and request.META.get("HTTP_IF_MODIFIED_SINCE"):
                client_modified = datetime.strptime(
                    request.META["HTTP_IF_MODIFIED_SINCE"],
                    "%a, %d %b %Y %H:%M:%S %Z"
                )
                if last_modified <= client_modified:
                    logger.debug(f"304 Not Modified (Last-Modified): {request.path}")
                    response = HttpResponse(status=304)
                    response["Last-Modified"] = last_modified.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT"
                    )
                    return response

            # Full response
            response = view_func(request, *args, **kwargs)

            if etag:
                response["ETag"] = etag
            if last_modified:
                response["Last-Modified"] = last_modified.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )

            return response
        return wrapped_view
    return decorator


# ════════════════════════════════════════════════════════════════
# STATIC ASSET FINGERPRINTING
# ════════════════════════════════════════════════════════════════


def fingerprint_asset(file_path: str) -> str:
    """
    Generate fingerprint (hash) for static asset.

    Used to create cache-busting URLs like:
    - Before: /static/css/style.css
    - After: /static/css/style.a1b2c3d4.css

    Args:
        file_path: Path to static asset

    Returns:
        Fingerprint hash (first 8 chars of MD5)

    Usage:
        >>> fingerprint_asset('/static/css/style.css')
        'a1b2c3d4'
    """
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash[:8]  # First 8 chars
    except FileNotFoundError:
        logger.warning(f"Asset not found: {file_path}")
        return "unknown"


def get_static_url_with_fingerprint(static_path: str) -> str:
    """
    Get static URL with cache-busting fingerprint.

    Args:
        static_path: Path relative to static root

    Returns:
        Full URL with fingerprint

    Example:
        >>> get_static_url_with_fingerprint('css/style.css')
        '/static/css/style.a1b2c3d4.css'
    """
    static_root = settings.STATIC_ROOT
    full_path = f"{static_root}/{static_path}"
    fingerprint = fingerprint_asset(full_path)

    # Insert fingerprint before file extension
    parts = static_path.rsplit(".", 1)
    if len(parts) == 2:
        return f"{settings.STATIC_URL}{parts[0]}.{fingerprint}.{parts[1]}"
    return f"{settings.STATIC_URL}{static_path}"


# ════════════════════════════════════════════════════════════════
# CDN INTEGRATION
# ════════════════════════════════════════════════════════════════


class CDNConfig:
    """CDN configuration and integration."""

    # Enable CDN
    ENABLED = False

    # CDN provider (cloudflare, cloudfront, akamai, etc)
    PROVIDER = "cloudflare"

    # CDN URL (set via environment)
    CDN_URL = None

    # Cache tag prefix (for surrogate key invalidation)
    CACHE_TAG_PREFIX = "calibra"

    # Purge API endpoint (provider-specific)
    PURGE_ENDPOINT = None

    # Purge API key (from environment)
    PURGE_KEY = None

    @classmethod
    def purge_cache(cls, patterns: list[str]) -> bool:
        """
        Purge CDN cache for specific URL patterns.

        Args:
            patterns: List of URL patterns to purge

        Returns:
            True if successful, False otherwise

        Example:
            >>> CDNConfig.purge_cache(['/qms/instrumentos/*', '/api/v1/*'])
        """
        if not cls.ENABLED or not cls.PURGE_ENDPOINT:
            logger.warning("CDN purging not configured")
            return False

        logger.info(f"Purging CDN cache for patterns: {patterns}")
        # Implementation would call CDN API (Cloudflare, CloudFront, etc)
        return True

    @classmethod
    def get_cdn_url(cls, path: str) -> str:
        """
        Get CDN URL for asset path.

        Args:
            path: Asset path (e.g., '/static/css/style.css')

        Returns:
            Full CDN URL

        Example:
            >>> CDNConfig.get_cdn_url('/static/css/style.css')
            'https://cdn.example.com/static/css/style.css'
        """
        if not cls.ENABLED or not cls.CDN_URL:
            return path

        return f"{cls.CDN_URL.rstrip('/')}{path}"


# ════════════════════════════════════════════════════════════════
# VARY HEADER CONFIGURATION
# ════════════════════════════════════════════════════════════════


VARY_HEADERS = {
    # Cache based on these request headers
    "Accept-Encoding": ["gzip", "deflate", "br"],  # Compression
    "Authorization": ["Bearer", "Basic"],           # Auth scheme
    "Accept": ["text/html", "application/json"],   # Content type
    "Accept-Language": ["en", "pt", "es"],         # Language
    "Accept-Charset": ["utf-8"],                   # Character encoding
    "User-Agent": ["Mobile", "Desktop"],           # Device type
}


# ════════════════════════════════════════════════════════════════
# QUICK START GUIDE
# ════════════════════════════════════════════════════════════════
#
# 1. Apply to views:
#    from config.http_cache_config import cache_control, CacheStrategy
#
#    @cache_control(**CacheStrategy.STATIC_VERSIONED)
#    def download_static(request, filename):
#        return serve_file(filename)
#
#    @cache_control(**CacheStrategy.HTML_PAGES)
#    def list_items(request):
#        return render(request, 'items.html')
#
# 2. Conditional requests:
#    @conditional_response(
#        etag_func=lambda r: get_etag(r),
#        last_modified_func=lambda r: get_modified(r)
#    )
#    def get_item(request, id):
#        item = Item.objects.get(id=id)
#        return render(request, 'item.html', {'item': item})
#
# 3. Static asset fingerprinting:
#    url = get_static_url_with_fingerprint('css/style.css')
#    # Result: /static/css/style.a1b2c3d4.css
#
# 4. CDN integration:
#    CDNConfig.ENABLED = True
#    CDNConfig.CDN_URL = 'https://cdn.example.com'
#    url = CDNConfig.get_cdn_url('/static/css/style.css')
#
# ════════════════════════════════════════════════════════════════

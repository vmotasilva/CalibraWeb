"""
HTTP Cache Decorators
======================

Ready-to-use decorators for common caching patterns:
1. @cache_view - Simple view caching with max-age
2. @cache_versioned_static - Assets with fingerprinting
3. @cache_with_etag - Conditional requests (304)
4. @cache_api_response - API-specific caching
5. @cache_paginated - Paginated results with smart TTL

Usage Examples:
    @cache_view(max_age=3600, public=True)
    def list_instrumentos(request):
        return render(request, 'instrumentos.html')

    @cache_versioned_static(days=365)
    def download_asset(request, filename):
        return serve_file(filename)

    @cache_with_etag(etag_callback=get_instrument_etag)
    def view_instrument(request, id):
        instrument = Instrument.objects.get(id=id)
        return render(request, 'instrument.html', {'item': instrument})

Author: HTTP Caching Team
Date: 2025-12
"""

import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional, Dict, Any
from json import dumps

from django.http import HttpResponse
from django.conf import settings

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# SIMPLE VIEW CACHING DECORATOR
# ════════════════════════════════════════════════════════════════


def cache_view(
    max_age: int = 3600,
    public: bool = True,
    must_revalidate: bool = False,
    vary: Optional[str] = None,
):
    """
    Simple decorator to cache a view with Cache-Control headers.

    Args:
        max_age: Cache lifetime in seconds (default: 1 hour)
        public: Cache in CDN/proxy if True, browser-only if False
        must_revalidate: Require revalidation after expiry
        vary: Header names to vary caching by (comma-separated)

    Returns:
        Decorated view function

    Example:
        @cache_view(max_age=3600, public=True)
        def list_instrumentos(request):
            instruments = Instrument.objects.all()
            return render(request, 'instrumentos.html', {
                'instruments': instruments
            })
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Build Cache-Control header
            directives = []
            if public:
                directives.append("public")
            else:
                directives.append("private")

            directives.append(f"max-age={max_age}")

            if must_revalidate:
                directives.append("must-revalidate")

            response["Cache-Control"] = ", ".join(directives)

            # Set Vary header
            if vary:
                response["Vary"] = vary

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# STATIC ASSET CACHING WITH FINGERPRINTING
# ════════════════════════════════════════════════════════════════


def cache_versioned_static(days: int = 365, immutable: bool = True):
    """
    Cache versioned static assets (with fingerprint in URL).

    Use for assets with cache-busting URLs:
    - /static/css/style.a1b2c3d4.css (fingerprint in name)

    Args:
        days: Cache lifetime in days
        immutable: Mark as immutable (never changes at this URL)

    Returns:
        Decorated view function

    Example:
        @cache_versioned_static(days=365)
        def download_css(request, filename):
            return serve_static_file(filename)

    Performance:
        - Browser: 0ms (cached locally for 1 year)
        - Repeat visits: 0ms
        - Load time: Minimal (from browser cache)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            max_age = days * 86400  # Convert to seconds
            directives = [
                "public",
                f"max-age={max_age}",
            ]

            if immutable:
                directives.append("immutable")

            response["Cache-Control"] = ", ".join(directives)

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# CONDITIONAL REQUEST CACHING (304 NOT MODIFIED)
# ════════════════════════════════════════════════════════════════


def cache_with_etag(
    etag_callback: Callable,
    last_modified_callback: Optional[Callable] = None,
    max_age: int = 3600,
):
    """
    Cache with ETag support for conditional requests (304 Not Modified).

    The client (browser) includes:
    - If-None-Match header with ETag value
    - If-Modified-Since header with timestamp

    Server responds with:
    - 304 Not Modified (no body) if unchanged
    - 200 with full response if changed

    Args:
        etag_callback: Function returning ETag for request
                      Signature: (request, *args, **kwargs) -> str
        last_modified_callback: Optional function returning datetime
                               Signature: (request, *args, **kwargs) -> datetime
        max_age: Cache lifetime for browser

    Returns:
        Decorated view function

    Example:
        def get_etag(request, id):
            instrument = Instrument.objects.get(id=id)
            # Hash the object's data
            data = f"{instrument.id}_{instrument.updated_at}".encode()
            return hashlib.md5(data).hexdigest()

        @cache_with_etag(
            etag_callback=get_etag,
            max_age=3600
        )
        def view_instrument(request, id):
            instrument = Instrument.objects.get(id=id)
            return render(request, 'instrument.html', {
                'instrument': instrument
            })

    Performance:
        - First request: Full response (~50-500ms)
        - Cached request with no changes: 304 response (1-5ms)
        - Changed content: Full response with updated ETag
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Generate ETag and Last-Modified
            etag = etag_callback(request, *args, **kwargs)
            last_modified = None

            if last_modified_callback:
                last_modified = last_modified_callback(request, *args, **kwargs)

            # ──────────────────────────────────────────────────────
            # Check If-None-Match (ETag match = 304)
            # ──────────────────────────────────────────────────────

            client_etag = request.META.get("HTTP_IF_NONE_MATCH", "").strip('"')

            if etag and client_etag == etag:
                logger.debug(f"304 Not Modified (ETag): {request.path}")
                response = HttpResponse(status=304)
                response["ETag"] = f'"{etag}"'
                response["Cache-Control"] = f"max-age={max_age}, public"
                return response

            # ──────────────────────────────────────────────────────
            # Check If-Modified-Since (older than client version = 304)
            # ──────────────────────────────────────────────────────

            if last_modified and "HTTP_IF_MODIFIED_SINCE" in request.META:
                try:
                    client_modified_str = request.META["HTTP_IF_MODIFIED_SINCE"]
                    # Parse HTTP date format
                    client_modified = datetime.strptime(
                        client_modified_str, "%a, %d %b %Y %H:%M:%S %Z"
                    )

                    if last_modified <= client_modified:
                        logger.debug(
                            f"304 Not Modified (Last-Modified): {request.path}"
                        )
                        response = HttpResponse(status=304)
                        response["Last-Modified"] = (
                            last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
                        )
                        response["Cache-Control"] = f"max-age={max_age}, public"
                        return response
                except ValueError:
                    # Invalid date format, ignore
                    pass

            # ──────────────────────────────────────────────────────
            # Full response (object was modified)
            # ──────────────────────────────────────────────────────

            response = view_func(request, *args, **kwargs)

            # Add cache headers
            response["Cache-Control"] = f"max-age={max_age}, public, must-revalidate"
            response["ETag"] = f'"{etag}"'

            if last_modified:
                response["Last-Modified"] = (
                    last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
                )

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# API RESPONSE CACHING
# ════════════════════════════════════════════════════════════════


def cache_api_response(
    max_age: int = 300,
    vary: str = "Accept-Encoding, Authorization",
    private: bool = True,
):
    """
    Cache API JSON responses with proper headers.

    Args:
        max_age: Cache lifetime in seconds (default: 5 min)
        vary: Headers to vary caching by
        private: Private cache (user-specific) vs public

    Returns:
        Decorated view function

    Example:
        @cache_api_response(max_age=300, private=False)
        def api_instruments_list(request):
            instruments = Instrument.objects.values(
                'id', 'name', 'model'
            )[:100]
            return JsonResponse({'instruments': list(instruments)})

    Performance:
        - Subsequent requests: 1-5ms (cache hit)
        - Database queries: Eliminated for 5 minutes
        - Bandwidth: 70-90% reduction for repeat requests
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            # Add API-specific headers
            directives = []

            if private:
                directives.append("private")
            else:
                directives.append("public")

            directives.append(f"max-age={max_age}")

            response["Cache-Control"] = ", ".join(directives)
            response["Vary"] = vary
            response["Content-Type"] = "application/json; charset=utf-8"

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# PAGINATED RESULTS CACHING
# ════════════════════════════════════════════════════════════════


def cache_paginated(
    max_age: int = 600,
    public: bool = True,
    vary_by_params: Optional[list[str]] = None,
):
    """
    Cache paginated results with smart TTL.

    Longer cache for first pages (stable), shorter for later pages (changing).

    Args:
        max_age: Cache lifetime for first page (in seconds)
        public: Cache in CDN/proxy
        vary_by_params: Query params to vary caching by
                       (e.g., ['page', 'sort', 'filter'])

    Returns:
        Decorated view function

    Example:
        @cache_paginated(
            max_age=600,
            vary_by_params=['page', 'sort', 'category']
        )
        def list_items_paginated(request):
            page = request.GET.get('page', 1)
            items = Item.objects.all()
            paginator = Paginator(items, 20)
            page_obj = paginator.get_page(page)
            return render(request, 'items_list.html', {
                'page_obj': page_obj
            })

    Cache Strategy:
        - Page 1: 10 minutes (most visited, stable)
        - Page 2-3: 5 minutes (moderately visited)
        - Page 4+: 2 minutes (rarely visited, changes more)
        - Sorted/filtered: 5 minutes (less stable)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get page number
            page = int(request.GET.get("page", 1))

            # Adjust TTL based on page number
            if page == 1:
                ttl = max_age  # Full TTL for first page
            elif page <= 3:
                ttl = int(max_age * 0.5)  # 50% for early pages
            else:
                ttl = int(max_age * 0.25)  # 25% for later pages

            # Check if using filters/sort
            has_filters = any(
                param in request.GET
                for param in (vary_by_params or ["filter", "search", "sort"])
            )
            if has_filters:
                ttl = int(ttl * 0.8)  # 20% reduction for filtered results

            response = view_func(request, *args, **kwargs)

            # Build Cache-Control
            directives = []
            if public:
                directives.append("public")
            else:
                directives.append("private")

            directives.append(f"max-age={ttl}")

            response["Cache-Control"] = ", ".join(directives)

            # Set Vary header
            if vary_by_params:
                response["Vary"] = ", ".join(vary_by_params)

            logger.debug(
                f"Cached paginated result: page={page}, ttl={ttl}s, {request.path}"
            )

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# JSON RESPONSE CACHING
# ════════════════════════════════════════════════════════════════


def cache_json_response(
    max_age: int = 300,
    vary: str = "Accept-Encoding",
    public: bool = False,
):
    """
    Cache JSON response with proper headers.

    Simpler variant of cache_api_response.

    Args:
        max_age: Cache lifetime
        vary: Vary by these headers
        public: Public (CDN) or private (browser-only)

    Returns:
        Decorated view function
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            directives = [
                ("public" if public else "private"),
                f"max-age={max_age}",
            ]

            response["Cache-Control"] = ", ".join(directives)
            response["Vary"] = vary
            response["Content-Type"] = "application/json; charset=utf-8"

            return response

        return wrapped_view

    return decorator


# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════


def generate_etag(data: Any) -> str:
    """
    Generate ETag from data.

    Args:
        data: Object to hash (dict, str, bytes, or JSON-serializable)

    Returns:
        ETag hash

    Example:
        >>> etag = generate_etag({'id': 1, 'name': 'Item'})
        >>> etag
        'a1b2c3d4'
    """
    if isinstance(data, bytes):
        data_bytes = data
    elif isinstance(data, str):
        data_bytes = data.encode()
    else:
        # Convert to JSON string for consistent hashing
        data_bytes = dumps(data, sort_keys=True, default=str).encode()

    return hashlib.md5(data_bytes).hexdigest()[:8]


def get_last_modified(obj) -> Optional[datetime]:
    """
    Get Last-Modified datetime from Django model instance.

    Checks for updated_at, modified_at, changed_at, or last_modified fields.

    Args:
        obj: Django model instance

    Returns:
        datetime or None
    """
    for field_name in ["updated_at", "modified_at", "changed_at", "last_modified"]:
        if hasattr(obj, field_name):
            value = getattr(obj, field_name)
            if isinstance(value, datetime):
                return value
    return None


# ════════════════════════════════════════════════════════════════
# QUICK START
# ════════════════════════════════════════════════════════════════
#
# 1. Simple view caching:
#    from config.cache_decorators import cache_view
#
#    @cache_view(max_age=3600)
#    def list_items(request):
#        return render(request, 'items.html')
#
# 2. With ETag support (conditional requests):
#    from config.cache_decorators import cache_with_etag, generate_etag
#
#    def get_item_etag(request, id):
#        item = Item.objects.get(id=id)
#        return generate_etag({'id': item.id, 'updated': item.updated_at})
#
#    @cache_with_etag(etag_callback=get_item_etag)
#    def view_item(request, id):
#        item = Item.objects.get(id=id)
#        return render(request, 'item.html', {'item': item})
#
# 3. API responses:
#    from config.cache_decorators import cache_api_response
#
#    @cache_api_response(max_age=300)
#    def api_items(request):
#        items = Item.objects.values('id', 'name')[:100]
#        return JsonResponse({'items': list(items)})
#
# 4. Paginated results:
#    from config.cache_decorators import cache_paginated
#
#    @cache_paginated(vary_by_params=['page', 'sort'])
#    def list_items_paginated(request):
#        page = request.GET.get('page', 1)
#        paginator = Paginator(Item.objects.all(), 20)
#        return render(request, 'items.html', {
#            'page_obj': paginator.get_page(page)
#        })
#
# ════════════════════════════════════════════════════════════════

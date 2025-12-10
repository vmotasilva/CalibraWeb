"""
Pagination utilities for efficient data handling with support for cursor-based
and offset-based pagination patterns.

This module provides pagination classes integrated with caching for better performance
when handling large datasets.

Example:
    Cursor-based pagination:
    >>> paginator = CursorPaginator(page_size=50)
    >>> page = paginator.paginate_queryset(queryset, request)
    >>> serialized = MySerializer(page, many=True)
    >>> response = paginator.get_paginated_response(serialized.data)

    Offset-based pagination:
    >>> paginator = OffsetPaginator(page_size=100)
    >>> page = paginator.paginate_queryset(queryset, request)
"""

import base64
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlencode

from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.http import QueryDict
from django.db.models import QuerySet, Model

from qms.cache_utils import CacheManager
from config.cache_settings import CACHE_KEY_PATTERNS, CACHE_TIMEOUTS


class PaginationMetadata:
    """Container for pagination metadata."""
    
    def __init__(
        self,
        total_items: int,
        total_pages: int,
        current_page: int,
        page_size: int,
        has_next: bool = False,
        has_previous: bool = False,
        next_page: Optional[int] = None,
        previous_page: Optional[int] = None,
    ):
        self.total_items = total_items
        self.total_pages = total_pages
        self.current_page = current_page
        self.page_size = page_size
        self.has_next = has_next
        self.has_previous = has_previous
        self.next_page = next_page
        self.previous_page = previous_page
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON responses."""
        return {
            'total_items': self.total_items,
            'total_pages': self.total_pages,
            'current_page': self.current_page,
            'page_size': self.page_size,
            'has_next': self.has_next,
            'has_previous': self.has_previous,
            'next_page': self.next_page,
            'previous_page': self.previous_page,
        }


class CursorPaginator:
    """
    Cursor-based pagination for efficient handling of large datasets.
    
    Ideal for:
    - Continuous scrolling/infinite scroll
    - Large datasets where offset becomes slow
    - Real-time data with frequent changes
    
    Pros:
    - O(1) performance regardless of dataset size
    - Consistent results with concurrent changes
    - No COUNT(*) required
    
    Cons:
    - Cannot jump to arbitrary page
    - Requires unique ordering field
    """
    
    def __init__(
        self,
        page_size: int = 50,
        ordering_field: str = 'id',
        use_cache: bool = True,
    ):
        self.page_size = page_size
        self.ordering_field = ordering_field
        self.use_cache = use_cache
        self.queryset: Optional[QuerySet] = None
        self.cursor: Optional[str] = None
    
    def encode_cursor(self, value: Any) -> str:
        """Encode cursor value to base64 string."""
        cursor_bytes = str(value).encode('utf-8')
        return base64.b64encode(cursor_bytes).decode('utf-8')
    
    def decode_cursor(self, cursor: str) -> Any:
        """Decode cursor from base64 string."""
        try:
            cursor_bytes = base64.b64decode(cursor.encode('utf-8'))
            return cursor_bytes.decode('utf-8')
        except Exception:
            return None
    
    def paginate_queryset(
        self,
        queryset: QuerySet,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Model], Optional[str], Optional[str]]:
        """
        Paginate queryset using cursor-based approach.
        
        Args:
            queryset: Django QuerySet to paginate
            cursor: Encoded cursor for continuation
        
        Returns:
            Tuple of (page_items, next_cursor, previous_cursor)
        """
        self.queryset = queryset.order_by(self.ordering_field)
        
        # Decode cursor if provided
        if cursor:
            decoded_cursor = self.decode_cursor(cursor)
            if decoded_cursor:
                # Fetch one extra item to check for next page
                items = list(
                    self.queryset.filter(**{f'{self.ordering_field}__gt': decoded_cursor})
                    [:self.page_size + 1]
                )
            else:
                items = list(self.queryset[:self.page_size + 1])
        else:
            items = list(self.queryset[:self.page_size + 1])
        
        # Check if there's a next page
        has_next = len(items) > self.page_size
        if has_next:
            items = items[:self.page_size]
        
        # Generate cursors
        next_cursor = None
        if items and has_next:
            last_item = items[-1]
            next_cursor = self.encode_cursor(getattr(last_item, self.ordering_field))
        
        previous_cursor = cursor
        
        return items, next_cursor, previous_cursor
    
    def get_paginated_response(
        self,
        data: List[Dict],
        next_cursor: Optional[str] = None,
        previous_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format paginated response with metadata."""
        return {
            'results': data,
            'pagination': {
                'next_cursor': next_cursor,
                'previous_cursor': previous_cursor,
                'page_size': self.page_size,
            },
        }


class OffsetPaginator:
    """
    Offset-based pagination for standard page navigation.
    
    Ideal for:
    - Page-based navigation UI
    - Smaller datasets (< 100k items)
    - SEO-friendly URLs with page numbers
    
    Pros:
    - Natural page-based navigation
    - Can jump to any page
    - Familiar UI pattern
    
    Cons:
    - O(n) performance due to OFFSET
    - Inconsistent results with concurrent changes
    - COUNT(*) required
    
    Performance Note:
    For better performance with large offsets, use CursorPaginator or
    implement keyset pagination with WHERE clauses.
    """
    
    def __init__(
        self,
        page_size: int = 100,
        use_cache: bool = True,
        cache_count: bool = True,
    ):
        self.page_size = page_size
        self.use_cache = use_cache
        self.cache_count = cache_count
    
    def get_cached_count(
        self,
        queryset: QuerySet,
        cache_key: str,
    ) -> int:
        """Get cached count or compute and cache it."""
        if not self.cache_count:
            return queryset.count()
        
        # Try to get from cache
        cache = CacheManager.get_cache_instance('queries')
        cached_count = cache.get(cache_key)
        
        if cached_count is not None:
            return cached_count
        
        # Compute and cache for 5 minutes
        count = queryset.count()
        cache.set(cache_key, count, CACHE_TIMEOUTS['queryset_count'])
        
        return count
    
    def paginate_queryset(
        self,
        queryset: QuerySet,
        page: int = 1,
        cache_key: Optional[str] = None,
    ) -> Tuple[List[Model], PaginationMetadata]:
        """
        Paginate queryset using offset-based approach.
        
        Args:
            queryset: Django QuerySet to paginate
            page: Page number (1-indexed)
            cache_key: Optional cache key for count query
        
        Returns:
            Tuple of (page_items, pagination_metadata)
        """
        try:
            page = int(page)
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1
        
        # Get total count
        if cache_key:
            total_items = self.get_cached_count(queryset, cache_key)
        else:
            total_items = queryset.count()
        
        # Calculate pagination info
        total_pages = (total_items + self.page_size - 1) // self.page_size
        offset = (page - 1) * self.page_size
        
        # Clamp page to valid range
        if page > total_pages and total_pages > 0:
            page = total_pages
            offset = (page - 1) * self.page_size
        
        # Get page items
        items = list(queryset[offset:offset + self.page_size])
        
        # Build metadata
        metadata = PaginationMetadata(
            total_items=total_items,
            total_pages=total_pages,
            current_page=page,
            page_size=self.page_size,
            has_next=page < total_pages,
            has_previous=page > 1,
            next_page=page + 1 if page < total_pages else None,
            previous_page=page - 1 if page > 1 else None,
        )
        
        return items, metadata
    
    def get_paginated_response(
        self,
        data: List[Dict],
        metadata: PaginationMetadata,
    ) -> Dict[str, Any]:
        """Format paginated response with metadata."""
        return {
            'results': data,
            'pagination': metadata.to_dict(),
        }


class PageNumberPaginator:
    """
    Traditional Django paginator wrapper with caching integration.
    
    Simplifies usage of Django's built-in Paginator with cache support.
    """
    
    def __init__(
        self,
        page_size: int = 50,
        use_cache: bool = True,
    ):
        self.page_size = page_size
        self.use_cache = use_cache
    
    def paginate_queryset(
        self,
        queryset: QuerySet,
        page: int = 1,
    ) -> Tuple[Page, int]:
        """
        Paginate queryset using Django's Paginator.
        
        Args:
            queryset: Django QuerySet to paginate
            page: Page number
        
        Returns:
            Tuple of (page_object, total_pages)
        """
        paginator = Paginator(queryset, self.page_size)
        
        try:
            page_obj = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        
        return page_obj, paginator.num_pages
    
    def get_paginated_response(
        self,
        data: List[Dict],
        page_obj: Page,
    ) -> Dict[str, Any]:
        """Format paginated response."""
        return {
            'results': data,
            'pagination': {
                'count': page_obj.paginator.count,
                'total_pages': page_obj.paginator.num_pages,
                'current_page': page_obj.number,
                'page_size': self.page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            },
        }


class PaginationHelper:
    """Helper utilities for pagination across the application."""
    
    @staticmethod
    def get_paginator_for_queryset(
        queryset: QuerySet,
        pagination_type: str = 'offset',
        **kwargs,
    ):
        """
        Factory method to get appropriate paginator for queryset.
        
        Args:
            queryset: Django QuerySet
            pagination_type: 'offset', 'cursor', or 'page'
            **kwargs: Additional arguments for paginator
        
        Returns:
            Appropriate paginator instance
        """
        if pagination_type == 'cursor':
            return CursorPaginator(**kwargs)
        elif pagination_type == 'page':
            return PageNumberPaginator(**kwargs)
        else:  # offset
            return OffsetPaginator(**kwargs)
    
    @staticmethod
    def get_page_from_request(request, page_param: str = 'page') -> int:
        """Extract page number from request parameters."""
        try:
            return int(request.GET.get(page_param, 1))
        except (ValueError, TypeError):
            return 1
    
    @staticmethod
    def get_cursor_from_request(request, cursor_param: str = 'cursor') -> Optional[str]:
        """Extract cursor from request parameters."""
        return request.GET.get(cursor_param)
    
    @staticmethod
    def build_pagination_url(
        base_url: str,
        page: Optional[int] = None,
        cursor: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Build pagination URL with parameters."""
        params = {}
        
        if page is not None:
            params['page'] = page
        
        if cursor is not None:
            params['cursor'] = cursor
        
        params.update(kwargs)
        
        if params:
            return f"{base_url}?{urlencode(params)}"
        return base_url


def paginate_queryset(
    queryset: QuerySet,
    page_size: int = 50,
    pagination_type: str = 'offset',
    page: int = 1,
    cursor: Optional[str] = None,
    cache_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function for quick pagination.
    
    Example:
        result = paginate_queryset(
            Instrumento.objects.all(),
            page_size=100,
            pagination_type='offset',
            page=1,
            cache_key='instrumentos_count'
        )
        # result = {
        #     'items': [...],
        #     'metadata': {...},
        #     'next_cursor': None,
        #     'previous_cursor': None
        # }
    """
    if pagination_type == 'cursor':
        paginator = CursorPaginator(page_size=page_size)
        items, next_cursor, previous_cursor = paginator.paginate_queryset(
            queryset,
            cursor=cursor,
        )
        return {
            'items': items,
            'next_cursor': next_cursor,
            'previous_cursor': previous_cursor,
            'page_size': page_size,
        }
    else:  # offset
        paginator = OffsetPaginator(page_size=page_size)
        items, metadata = paginator.paginate_queryset(
            queryset,
            page=page,
            cache_key=cache_key,
        )
        return {
            'items': items,
            'metadata': metadata.to_dict(),
            'page_size': page_size,
        }

"""
Pagination performance benchmarks and tests.

Tests cursor-based, offset-based, and traditional pagination
against various dataset sizes.

Run with:
    python manage.py test qms.tests_pagination
    python manage.py benchmark_pagination
"""

import time
import random
from django.test import TestCase, TransactionTestCase
from django.db.models import QuerySet
from metrologia.models import Instrumento, CategoriaInstrumento
from organization.models import Setor
from qms.pagination import (
    CursorPaginator,
    OffsetPaginator,
    PageNumberPaginator,
    paginate_queryset,
)


class PaginationBaseTest(TransactionTestCase):
    """Base test class with test data setup."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.setup_test_data()
    
    @staticmethod
    def setup_test_data(num_items=500):
        """Create test data for pagination tests."""
        # Create test categories
        categoria = CategoriaInstrumento.objects.create(
            nome='Test Categoria',
            descricao='Category for testing'
        )
        
        # Create test setor
        setor = Setor.objects.create(
            nome='Test Setor',
            sigla='TS'
        )
        
        # Create test instruments
        for i in range(num_items):
            Instrumento.objects.create(
                tag=f'INST-{i:05d}',
                descricao=f'Test Instrument {i}',
                categoria=categoria,
                setor=setor,
                ativo=i % 10 != 0,  # 90% active
            )


class CursorPaginatorTest(PaginationBaseTest):
    """Test cursor-based pagination."""
    
    def setUp(self):
        self.paginator = CursorPaginator(page_size=50)
        self.queryset = Instrumento.objects.all().order_by('id')
    
    def test_cursor_pagination_first_page(self):
        """Test cursor pagination for first page."""
        items, next_cursor, prev_cursor = self.paginator.paginate_queryset(
            self.queryset
        )
        
        self.assertEqual(len(items), 50)
        self.assertIsNotNone(next_cursor)
        self.assertIsNone(prev_cursor)
        self.assertEqual(items[0].tag, 'INST-00000')
    
    def test_cursor_pagination_next_page(self):
        """Test cursor pagination for next page."""
        # Get first page to get cursor
        items1, next_cursor, _ = self.paginator.paginate_queryset(
            self.queryset
        )
        
        # Get next page
        items2, next_cursor2, prev_cursor = self.paginator.paginate_queryset(
            self.queryset,
            cursor=next_cursor
        )
        
        self.assertEqual(len(items2), 50)
        self.assertIsNotNone(next_cursor2)
        self.assertIsNotNone(prev_cursor)
        self.assertNotEqual(items2[0].id, items1[0].id)
    
    def test_cursor_pagination_consistency(self):
        """Test that cursor pagination is consistent across multiple calls."""
        items1, cursor1, _ = self.paginator.paginate_queryset(
            self.queryset
        )
        items2, cursor2, _ = self.paginator.paginate_queryset(
            self.queryset
        )
        
        # Should get same items
        self.assertEqual([i.id for i in items1], [i.id for i in items2])
    
    def test_cursor_encode_decode(self):
        """Test cursor encoding and decoding."""
        value = 'test-123-value'
        encoded = self.paginator.encode_cursor(value)
        decoded = self.paginator.decode_cursor(encoded)
        
        self.assertEqual(value, decoded)
    
    def test_invalid_cursor(self):
        """Test handling of invalid cursor."""
        items, _, _ = self.paginator.paginate_queryset(
            self.queryset,
            cursor='invalid-cursor-value'
        )
        
        # Should still return items (from start)
        self.assertEqual(len(items), 50)


class OffsetPaginatorTest(PaginationBaseTest):
    """Test offset-based pagination."""
    
    def setUp(self):
        self.paginator = OffsetPaginator(page_size=50, cache_count=False)
        self.queryset = Instrumento.objects.all().order_by('id')
    
    def test_offset_pagination_first_page(self):
        """Test offset pagination for first page."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=1
        )
        
        self.assertEqual(len(items), 50)
        self.assertEqual(metadata.current_page, 1)
        self.assertTrue(metadata.has_next)
        self.assertFalse(metadata.has_previous)
    
    def test_offset_pagination_middle_page(self):
        """Test offset pagination for middle page."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=5
        )
        
        self.assertEqual(len(items), 50)
        self.assertEqual(metadata.current_page, 5)
        self.assertTrue(metadata.has_next)
        self.assertTrue(metadata.has_previous)
        self.assertEqual(metadata.next_page, 6)
        self.assertEqual(metadata.previous_page, 4)
    
    def test_offset_pagination_last_page(self):
        """Test offset pagination for last page."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=10  # Should be last page for 500 items with page_size=50
        )
        
        self.assertEqual(metadata.current_page, 10)
        self.assertFalse(metadata.has_next)
        self.assertTrue(metadata.has_previous)
    
    def test_offset_pagination_beyond_last_page(self):
        """Test offset pagination beyond last page."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=100
        )
        
        # Should clamp to last page
        self.assertEqual(metadata.current_page, 10)
        self.assertFalse(metadata.has_next)
    
    def test_offset_pagination_metadata(self):
        """Test pagination metadata."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=1
        )
        
        self.assertEqual(metadata.total_items, 500)
        self.assertEqual(metadata.total_pages, 10)
        self.assertEqual(metadata.page_size, 50)
    
    def test_metadata_to_dict(self):
        """Test conversion of metadata to dict."""
        items, metadata = self.paginator.paginate_queryset(
            self.queryset,
            page=1
        )
        
        data = metadata.to_dict()
        
        self.assertIn('total_items', data)
        self.assertIn('total_pages', data)
        self.assertIn('current_page', data)
        self.assertEqual(data['total_items'], 500)


class PageNumberPaginatorTest(PaginationBaseTest):
    """Test Django's traditional page number paginator."""
    
    def setUp(self):
        self.paginator = PageNumberPaginator(page_size=50)
        self.queryset = Instrumento.objects.all().order_by('id')
    
    def test_page_number_pagination(self):
        """Test page number pagination."""
        page_obj, total_pages = self.paginator.paginate_queryset(
            self.queryset,
            page=1
        )
        
        self.assertEqual(len(page_obj.object_list), 50)
        self.assertEqual(total_pages, 10)
    
    def test_page_number_invalid_page(self):
        """Test page number pagination with invalid page."""
        page_obj, _ = self.paginator.paginate_queryset(
            self.queryset,
            page='invalid'
        )
        
        self.assertEqual(page_obj.number, 1)
    
    def test_page_number_response_format(self):
        """Test page number response format."""
        page_obj, _ = self.paginator.paginate_queryset(
            self.queryset,
            page=1
        )
        
        response = self.paginator.get_paginated_response(
            [{'id': i.id, 'tag': i.tag} for i in page_obj],
            page_obj
        )
        
        self.assertIn('results', response)
        self.assertIn('pagination', response)
        self.assertEqual(response['pagination']['current_page'], 1)


class PaginationHelperTest(PaginationBaseTest):
    """Test pagination helper utilities."""
    
    def test_get_paginator_for_queryset_offset(self):
        """Test getting offset paginator."""
        queryset = Instrumento.objects.all()
        paginator = PaginationHelper.get_paginator_for_queryset(
            queryset,
            pagination_type='offset'
        )
        
        self.assertIsInstance(paginator, OffsetPaginator)
    
    def test_get_paginator_for_queryset_cursor(self):
        """Test getting cursor paginator."""
        queryset = Instrumento.objects.all()
        paginator = PaginationHelper.get_paginator_for_queryset(
            queryset,
            pagination_type='cursor'
        )
        
        self.assertIsInstance(paginator, CursorPaginator)


class PaginationPerformanceTest(TransactionTestCase):
    """Performance comparison tests."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        PaginationBaseTest.setup_test_data(num_items=2000)
    
    def test_cursor_pagination_performance(self):
        """Benchmark cursor pagination."""
        queryset = Instrumento.objects.all().order_by('id')
        paginator = CursorPaginator(page_size=100)
        
        start = time.time()
        for i in range(10):
            items, next_cursor, _ = paginator.paginate_queryset(queryset)
            if not next_cursor:
                break
        elapsed = time.time() - start
        
        print(f"\nCursor Pagination (10 pages): {elapsed:.4f}s")
        self.assertLess(elapsed, 1.0)  # Should be fast
    
    def test_offset_pagination_performance(self):
        """Benchmark offset pagination."""
        queryset = Instrumento.objects.all().order_by('id')
        paginator = OffsetPaginator(page_size=100, cache_count=False)
        
        start = time.time()
        for i in range(1, 11):
            items, metadata = paginator.paginate_queryset(queryset, page=i)
        elapsed = time.time() - start
        
        print(f"Offset Pagination (10 pages): {elapsed:.4f}s")
        self.assertLess(elapsed, 1.0)
    
    def test_page_number_pagination_performance(self):
        """Benchmark page number pagination."""
        queryset = Instrumento.objects.all().order_by('id')
        paginator = PageNumberPaginator(page_size=100)
        
        start = time.time()
        for i in range(1, 11):
            page_obj, _ = paginator.paginate_queryset(queryset, page=i)
        elapsed = time.time() - start
        
        print(f"Page Number Pagination (10 pages): {elapsed:.4f}s")
        self.assertLess(elapsed, 1.0)


# Convenience test runner
if __name__ == '__main__':
    import django
    django.setup()
    
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True, keepdb=False)
    failures = test_runner.run_tests(['qms.tests_pagination'])

"""
Management command: multilevel_cache_monitor

Monitor multi-level cache performance and statistics.

Features:
1. L1 cache (request-scoped) stats
2. L2 cache (worker-scoped) stats and LRU info
3. L3 cache (distributed/Redis) stats
4. Combined hit rate and efficiency
5. Performance recommendations

Usage:
    python manage.py multilevel_cache_monitor --all
    python manage.py multilevel_cache_monitor --l1
    python manage.py multilevel_cache_monitor --l2
    python manage.py multilevel_cache_monitor --l3
    python manage.py multilevel_cache_monitor --analyze
    python manage.py multilevel_cache_monitor --reset

Author: Caching Team
Date: 2025-12
"""

import logging
import json
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.conf import settings

from config.multilevel_cache import multi_level_cache

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Multi-level cache monitoring command."""

    help = "Monitor multi-level caching statistics"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--l1",
            action="store_true",
            help="Show L1 (request) cache stats"
        )
        parser.add_argument(
            "--l2",
            action="store_true",
            help="Show L2 (worker) cache stats"
        )
        parser.add_argument(
            "--l3",
            action="store_true",
            help="Show L3 (distributed) cache stats"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all cache levels"
        )
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Analyze cache performance and recommendations"
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset cache statistics"
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON"
        )

    def handle(self, *args, **options):
        """Execute command."""
        if not any([options["l1"], options["l2"], options["l3"], 
                   options["all"], options["analyze"], options["reset"]]):
            options["all"] = True

        try:
            if options["reset"]:
                self.reset_stats()
            
            if options["all"]:
                self.show_all_stats(options["json"])
            else:
                if options["l1"]:
                    self.show_l1_stats(options["json"])
                if options["l2"]:
                    self.show_l2_stats(options["json"])
                if options["l3"]:
                    self.show_l3_stats(options["json"])
            
            if options["analyze"]:
                self.analyze_performance()

        except Exception as e:
            self.stderr.write(f"Error: {e}")

    def show_all_stats(self, as_json=False):
        """Show stats for all cache levels."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*70))
        self.stdout.write(self.style.HTTP_SUCCESS("MULTI-LEVEL CACHE STATISTICS"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*70 + "\n"))

        stats = multi_level_cache.get_stats()

        # Overall summary
        self.stdout.write(self.style.HTTP_INFO("OVERALL SUMMARY"))
        self.stdout.write(f"Total Requests:        {stats['total_requests']:,}")
        self.stdout.write(f"Cache Hit Rate:        {stats['cache_hit_rate_percent']}%")
        self.stdout.write(f"Database Queries:      {stats['db_queries']:,}\n")

        # L1 Stats
        self.show_l1_stats(as_json=False)

        # L2 Stats
        self.show_l2_stats(as_json=False)

        # L3 Stats
        self.show_l3_stats(as_json=False)

        if as_json:
            self.stdout.write("\n" + json.dumps(stats, indent=2))

    def show_l1_stats(self, as_json=False):
        """Show L1 (request-scoped) cache stats."""
        self.stdout.write(self.style.HTTP_INFO("\nL1 CACHE (Request-Scoped)"))
        self.stdout.write("-" * 70)

        stats = multi_level_cache.get_stats()
        l1_stats = stats.get('l1_stats', {})

        self.stdout.write(f"Size:                  {l1_stats.get('size', 0)} items")
        self.stdout.write(f"Keys:                  {l1_stats.get('keys', [])}")
        self.stdout.write("Lifetime:              Duration of single HTTP request")
        self.stdout.write("Purpose:               Prevent duplicate queries within request\n")

        if as_json:
            self.stdout.write(json.dumps(l1_stats, indent=2))

    def show_l2_stats(self, as_json=False):
        """Show L2 (worker-scoped) cache stats."""
        self.stdout.write(self.style.HTTP_INFO("\nL2 CACHE (Worker-Scoped LRU)"))
        self.stdout.write("-" * 70)

        stats = multi_level_cache.get_stats()
        l2_stats = stats.get('l2_stats', {})

        size = l2_stats.get('size', 0)
        max_size = l2_stats.get('max_size', 1000)
        hits = l2_stats.get('hits', 0)
        misses = l2_stats.get('misses', 0)
        hit_rate = l2_stats.get('hit_rate_percent', 0)

        utilization = (size / max_size * 100) if max_size > 0 else 0

        self.stdout.write(f"Size:                  {size:,} / {max_size:,} items")
        self.stdout.write(f"Utilization:           {utilization:.1f}%")
        self.stdout.write(f"Hits:                  {hits:,}")
        self.stdout.write(f"Misses:                {misses:,}")
        self.stdout.write(f"Hit Rate:              {hit_rate}%")
        self.stdout.write("Lifetime:              Process lifetime")
        self.stdout.write("Eviction:              LRU (Least Recently Used)\n")

        # Recommendations
        if hit_rate < 50:
            self.stdout.write(self.style.WARNING(
                f"⚠ Low L2 hit rate ({hit_rate}%). "
                "Consider increasing cache TTL or max_size."
            ))
        if utilization > 80:
            self.stdout.write(self.style.WARNING(
                f"⚠ High utilization ({utilization:.1f}%). "
                "Consider increasing max_size."
            ))

        self.stdout.write("")

        if as_json:
            self.stdout.write(json.dumps(l2_stats, indent=2))

    def show_l3_stats(self, as_json=False):
        """Show L3 (distributed/Redis) cache stats."""
        self.stdout.write(self.style.HTTP_INFO("\nL3 CACHE (Distributed/Redis)"))
        self.stdout.write("-" * 70)

        stats = multi_level_cache.get_stats()
        l3_stats = stats.get('l3_stats', {})

        size = l3_stats.get('size', 0)
        memory = l3_stats.get('memory_used', 'N/A')
        expired = l3_stats.get('keys_expired', 0)
        evicted = l3_stats.get('keys_evicted', 0)

        self.stdout.write(f"Keys:                  {size:,}")
        self.stdout.write(f"Memory Used:           {memory}")
        self.stdout.write(f"Keys Expired:          {expired:,}")
        self.stdout.write(f"Keys Evicted:          {evicted:,}")
        self.stdout.write("Lifetime:              Configurable per key")
        self.stdout.write("Scope:                 Across all workers\n")

        if evicted > 1000:
            self.stdout.write(self.style.WARNING(
                f"⚠ High eviction rate ({evicted:,}). "
                "Redis memory may be insufficient."
            ))

        if as_json:
            self.stdout.write(json.dumps(l3_stats, indent=2))

    def analyze_performance(self):
        """Analyze cache performance and provide recommendations."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*70))
        self.stdout.write(self.style.HTTP_SUCCESS("CACHE PERFORMANCE ANALYSIS"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*70 + "\n"))

        stats = multi_level_cache.get_stats()

        # Calculate breakdown
        l1_hits = stats.get('l1_hits', 0)
        l2_hits = stats.get('l2_hits', 0)
        l3_hits = stats.get('l3_hits', 0)
        db_queries = stats.get('db_queries', 0)
        total = stats.get('total_requests', 1)

        hit_rate = stats.get('cache_hit_rate_percent', 0)

        # Display breakdown
        self.stdout.write("REQUEST BREAKDOWN:")
        self.stdout.write(f"  L1 (Request Cache):    {l1_hits:6,} ({l1_hits/total*100:5.1f}%) - 0ms")
        self.stdout.write(f"  L2 (Worker Cache):     {l2_hits:6,} ({l2_hits/total*100:5.1f}%) - <1ms")
        self.stdout.write(f"  L3 (Redis Cache):      {l3_hits:6,} ({l3_hits/total*100:5.1f}%) - 5-10ms")
        self.stdout.write(f"  Database Queries:      {db_queries:6,} ({db_queries/total*100:5.1f}%) - 50-500ms")
        self.stdout.write(f"  TOTAL:                 {total:6,} (100.0%)\n")

        # Performance score
        self.stdout.write("PERFORMANCE SCORE:")

        if hit_rate >= 90:
            self.stdout.write(self.style.SUCCESS(f"  ✓ EXCELLENT ({hit_rate}% hit rate)"))
        elif hit_rate >= 80:
            self.stdout.write(self.style.SUCCESS(f"  ✓ GOOD ({hit_rate}% hit rate)"))
        elif hit_rate >= 70:
            self.stdout.write(self.style.WARNING(f"  ⚠ FAIR ({hit_rate}% hit rate)"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ POOR ({hit_rate}% hit rate)"))

        # Recommendations
        self.stdout.write("\nRECOMMENDATIONS:")

        if hit_rate < 70:
            self.stdout.write("  1. Increase cache TTL values")
            self.stdout.write("  2. Review cache invalidation strategy")
            self.stdout.write("  3. Check cache key coverage")

        if stats.get('l2_stats', {}).get('hit_rate_percent', 0) < 50:
            self.stdout.write("  - L2 (worker) cache hit rate is low")
            self.stdout.write("    → Increase worker cache max_size")
            self.stdout.write("    → Review data locality")

        if db_queries > total * 0.3:
            self.stdout.write("  - Database query rate is high (>30%)")
            self.stdout.write("    → Add caching for popular queries")
            self.stdout.write("    → Implement cache warming")

        self.stdout.write("")

    def reset_stats(self):
        """Reset cache statistics."""
        multi_level_cache.stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'l3_hits': 0,
            'db_queries': 0,
        }
        self.stdout.write(self.style.SUCCESS("✓ Cache statistics reset"))

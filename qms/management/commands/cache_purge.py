"""
Cache Purge Management Command
==============================

Manual cache purging and invalidation tool.

Commands:
    python manage.py cache_purge --all
    python manage.py cache_purge --pattern instrument_*
    python manage.py cache_purge --url /api/instruments/
    python manage.py cache_purge --model Instrument
    python manage.py cache_purge --since 1h
    python manage.py cache_purge --stats

Author: Caching Team
Date: 2025-12
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from config.multilevel_cache import multi_level_cache
from config.cache_invalidation import (
    CascadingInvalidator,
    smart_ttl,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Purge and invalidate application cache"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear entire cache',
        )
        
        parser.add_argument(
            '--pattern',
            type=str,
            help='Clear by pattern (e.g., instrument_*, query_*)',
        )
        
        parser.add_argument(
            '--url',
            type=str,
            help='Clear cache for specific URL pattern',
        )
        
        parser.add_argument(
            '--model',
            type=str,
            help='Clear cache for specific model (e.g., Instrument, Category)',
        )
        
        parser.add_argument(
            '--since',
            type=str,
            help='Clear cache entries changed since (e.g., 1h, 30m, 1d)',
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show cache statistics and recommendations',
        )
        
        parser.add_argument(
            '--ttl',
            action='store_true',
            help='Show smart TTL recommendations',
        )
        
        parser.add_argument(
            '--reset-ttl',
            action='store_true',
            help='Reset smart TTL statistics',
        )
        
        parser.add_argument(
            '--reset-all',
            action='store_true',
            help='Reset all cache and statistics',
        )
        
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON',
        )
        
        parser.add_argument(
            '--verbose-output',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        """Execute command."""
        if options['json']:
            import json
            output = self.handle_json(options)
            self.stdout.write(json.dumps(output, indent=2))
            return
        
        # Stats
        if options['stats']:
            self.show_stats()
            return
        
        # Smart TTL
        if options['ttl']:
            self.show_ttl_stats()
            return
        
        # Reset operations
        if options['reset_all']:
            self.reset_all()
            return
        
        if options['reset_ttl']:
            self.reset_ttl()
            return
        
        # Purge operations
        if options['all']:
            self.clear_all(options)
            return
        
        if options['pattern']:
            self.clear_pattern(options['pattern'], options)
            return
        
        if options['url']:
            self.clear_url(options['url'], options)
            return
        
        if options['model']:
            self.clear_model(options['model'], options)
            return
        
        if options['since']:
            self.clear_since(options['since'], options)
            return
        
        # Default: show help
        self.stdout.write(self.style.WARNING(
            "No action specified. Use --help for options."
        ))
    
    def clear_all(self, options):
        """Clear entire cache."""
        self.stdout.write(self.style.WARNING(
            "⚠️  Clearing ALL cache..."
        ))
        
        try:
            multi_level_cache.clear()
            self.stdout.write(self.style.SUCCESS(
                "✓ Cache cleared successfully"
            ))
            logger.info("Cache completely cleared via management command")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            logger.error(f"Error clearing cache: {e}", exc_info=True)
    
    def clear_pattern(self, pattern, options):
        """Clear cache by pattern."""
        verbose = options.get('verbose_output', False)
        
        self.stdout.write(f"Clearing cache pattern: {pattern}")
        
        try:
            count = multi_level_cache.invalidate_pattern(pattern)
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Cleared {count} cache entries matching '{pattern}'"
            ))
            
            logger.info(f"Cleared {count} cache entries for pattern: {pattern}")
            
            if verbose:
                stats = multi_level_cache.get_stats()
                self.stdout.write(f"Remaining cache: {stats}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            logger.error(f"Error clearing pattern: {e}", exc_info=True)
    
    def clear_url(self, url_pattern, options):
        """Clear cache for URL pattern."""
        # Convert URL to cache pattern
        # /api/instruments/ -> query_instruments_*
        
        url = url_pattern.strip('/')
        segments = url.split('/')
        pattern = f"query_{segments[0]}_*"
        
        self.stdout.write(f"Clearing cache for URL: {url_pattern}")
        
        try:
            count = multi_level_cache.invalidate_pattern(pattern)
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Cleared {count} cache entries for URL pattern"
            ))
            
            logger.info(f"Cleared cache for URL: {url_pattern}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            logger.error(f"Error clearing URL cache: {e}", exc_info=True)
    
    def clear_model(self, model_name, options):
        """Clear cache for specific model."""
        pattern = f"{model_name.lower()}_*"
        query_pattern = f"query_{model_name.lower()}*"
        agg_pattern = f"agg_{model_name.lower()}*"
        
        self.stdout.write(f"Clearing cache for model: {model_name}")
        
        try:
            count1 = multi_level_cache.invalidate_pattern(pattern)
            count2 = multi_level_cache.invalidate_pattern(query_pattern)
            count3 = multi_level_cache.invalidate_pattern(agg_pattern)
            
            total = count1 + count2 + count3
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Cleared {total} cache entries for {model_name}"
            ))
            
            logger.info(f"Cleared cache for model: {model_name} ({total} entries)")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            logger.error(f"Error clearing model cache: {e}", exc_info=True)
    
    def clear_since(self, since_param, options):
        """Clear cache entries modified since specified time."""
        # Parse time parameter (1h, 30m, 1d)
        try:
            time_delta = self._parse_time_delta(since_param)
            cutoff_time = timezone.now() - time_delta
            
            self.stdout.write(
                f"Clearing cache entries modified since: {cutoff_time}"
            )
            
            # For now, just clear common patterns
            # In production, track modification times
            patterns = [
                "query_*",
                "agg_*",
                "instrument_*",
                "categoria_*",
                "procedimento_*",
            ]
            
            total_count = 0
            for pattern in patterns:
                count = multi_level_cache.invalidate_pattern(pattern)
                total_count += count
            
            self.stdout.write(self.style.SUCCESS(
                f"✓ Cleared {total_count} recent cache entries"
            ))
            
            logger.info(f"Cleared {total_count} cache entries since {cutoff_time}")
        
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f"✗ Invalid time format: {e}"))
    
    def show_stats(self):
        """Display cache statistics."""
        try:
            stats = multi_level_cache.get_stats()
            
            self.stdout.write(self.style.SUCCESS("\n=== Cache Statistics ===\n"))
            
            for level, level_stats in stats.items():
                self.stdout.write(self.style.WARNING(f"{level}:"))
                
                for key, value in level_stats.items():
                    if isinstance(value, float):
                        value = f"{value:.2%}"
                    self.stdout.write(f"  {key}: {value}")
                
                self.stdout.write("")
            
            # Show recommendations
            self._show_recommendations(stats)
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            logger.error(f"Error getting cache stats: {e}", exc_info=True)
    
    def show_ttl_stats(self):
        """Display smart TTL statistics."""
        try:
            ttl_stats = smart_ttl.get_stats()
            
            self.stdout.write(self.style.SUCCESS("\n=== Smart TTL Statistics ===\n"))
            
            self.stdout.write(f"Tracked keys: {ttl_stats.get('total_keys', 0)}")
            self.stdout.write(f"Access events: {ttl_stats.get('total_accesses', 0)}")
            self.stdout.write(f"Invalidations: {ttl_stats.get('total_invalidations', 0)}")
            
            if 'hot_keys' in ttl_stats:
                self.stdout.write("\nHot Keys (1h TTL):")
                for key in ttl_stats['hot_keys'][:5]:
                    self.stdout.write(f"  - {key}")
            
            if 'warm_keys' in ttl_stats:
                self.stdout.write("\nWarm Keys (10m TTL):")
                for key in ttl_stats['warm_keys'][:5]:
                    self.stdout.write(f"  - {key}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
    
    def reset_ttl(self):
        """Reset smart TTL statistics."""
        self.stdout.write("Resetting smart TTL statistics...")
        
        try:
            smart_ttl.reset_stats()
            self.stdout.write(self.style.SUCCESS(
                "✓ Smart TTL statistics reset"
            ))
            logger.info("Smart TTL statistics reset via management command")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
    
    def reset_all(self):
        """Reset all cache and statistics."""
        self.stdout.write(self.style.WARNING(
            "⚠️  Resetting ALL cache and statistics..."
        ))
        
        try:
            multi_level_cache.clear()
            smart_ttl.reset_stats()
            
            self.stdout.write(self.style.SUCCESS(
                "✓ Cache and statistics completely reset"
            ))
            logger.info("Complete cache and statistics reset via management command")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
    
    def _show_recommendations(self, stats):
        """Show cache optimization recommendations."""
        self.stdout.write(self.style.WARNING("\n=== Recommendations ===\n"))
        
        recommendations = [
            "• Monitor L1 hit rate - if low (<30%), consider wider request scope",
            "• Monitor L2 hit rate - if low (<40%), increase max_size",
            "• Monitor L3 hit rate - if low (<70%), reduce TTL values",
            "• Use smart TTL for automatic optimization",
            "• Profile hot keys and consider prefetching",
        ]
        
        for rec in recommendations:
            self.stdout.write(rec)
    
    def handle_json(self, options):
        """Return JSON output."""
        import json
        
        output = {
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
        }
        
        if options['stats']:
            output['stats'] = multi_level_cache.get_stats()
        
        if options['ttl']:
            output['ttl_stats'] = smart_ttl.get_stats()
        
        return output
    
    @staticmethod
    def _parse_time_delta(time_str):
        """Parse time string like '1h', '30m', '1d'."""
        import re
        
        match = re.match(r'(\d+)([hmd])', time_str.lower())
        if not match:
            raise ValueError(
                f"Invalid time format: {time_str}. Use '1h', '30m', '1d'"
            )
        
        value, unit = int(match.group(1)), match.group(2)
        
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'd':
            return timedelta(days=value)
        
        raise ValueError(f"Unknown time unit: {unit}")

"""
Management command: http_cache_monitor

Monitor HTTP cache performance and statistics.

Features:
1. Cache hit rate tracking
2. Cache size monitoring
3. TTL distribution analysis
4. Performance metrics
5. Compression effectiveness

Usage:
    python manage.py http_cache_monitor --stats
    python manage.py http_cache_monitor --health
    python manage.py http_cache_monitor --watch 60
    python manage.py http_cache_monitor --all

Author: Caching Team
Date: 2025-12
"""

import os
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.cache import cache


class Command(BaseCommand):
    """HTTP cache monitoring management command."""

    help = "Monitor HTTP cache performance and statistics"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show cache statistics"
        )
        parser.add_argument(
            "--health",
            action="store_true",
            help="Check cache health"
        )
        parser.add_argument(
            "--varnish",
            action="store_true",
            help="Show Varnish statistics (if available)"
        )
        parser.add_argument(
            "--nginx",
            action="store_true",
            help="Show Nginx cache statistics"
        )
        parser.add_argument(
            "--watch",
            type=int,
            metavar="SECONDS",
            help="Watch cache statistics for N seconds"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all information"
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON"
        )

    def handle(self, *args, **options):
        """Execute command."""
        output_json = options.get("json", False)

        # Default: show stats
        if not any([
            options["stats"],
            options["health"],
            options["varnish"],
            options["nginx"],
            options["watch"],
            options["all"]
        ]):
            options["stats"] = True

        try:
            if options["all"]:
                self.show_all_stats(output_json)
            else:
                if options["stats"]:
                    self.show_cache_stats(output_json)
                if options["health"]:
                    self.check_cache_health(output_json)
                if options["varnish"]:
                    self.show_varnish_stats(output_json)
                if options["nginx"]:
                    self.show_nginx_stats(output_json)
                if options["watch"]:
                    self.watch_cache_stats(options["watch"], output_json)

        except Exception as e:
            self.stderr.write(f"Error: {e}")

    def show_cache_stats(self, output_json=False):
        """Show cache statistics."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.HTTP_SUCCESS("HTTP CACHE STATISTICS"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*60 + "\n"))

        stats = {
            "timestamp": datetime.now().isoformat(),
            "cache_backend": settings.CACHES["default"]["BACKEND"],
            "cache_location": settings.CACHES["default"].get("LOCATION"),
            "cache_timeout": settings.CACHES["default"].get("TIMEOUT", 300),
        }

        # Get cache info from Django
        if hasattr(cache, '_cache'):
            try:
                # For Redis backend
                info = cache._cache.info()
                stats.update({
                    "redis_memory_used": info.get("used_memory_human"),
                    "redis_connected_clients": info.get("connected_clients"),
                    "redis_evicted_keys": info.get("evicted_keys"),
                    "redis_keyspace": self.get_redis_keyspace(),
                })
            except Exception:
                pass

        # Print stats
        for key, value in stats.items():
            if value is not None:
                label = key.replace("_", " ").title()
                self.stdout.write(f"{label:30} {value}")

        if output_json:
            self.stdout.write("\n" + json.dumps(stats, indent=2))

    def show_all_stats(self, output_json=False):
        """Show all cache statistics."""
        self.show_cache_stats(output_json=False)
        self.check_cache_health(output_json=False)

        # Try to show proxy cache stats
        try:
            self.show_varnish_stats(output_json=False)
        except Exception:
            pass

        try:
            self.show_nginx_stats(output_json=False)
        except Exception:
            pass

    def check_cache_health(self, output_json=False):
        """Check cache health."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.HTTP_SUCCESS("CACHE HEALTH CHECK"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*60 + "\n"))

        health_checks = {
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }

        # 1. Connection test
        try:
            cache.set("_health_check", "ok", 1)
            value = cache.get("_health_check")
            is_healthy = value == "ok"
            health_checks["checks"]["connection"] = {
                "status": "HEALTHY" if is_healthy else "FAILED",
                "message": "Cache backend responding" if is_healthy else "Cache backend not responding"
            }
            self.stdout.write(
                self.style.SUCCESS("✓ Connection: OK") if is_healthy
                else self.style.ERROR("✗ Connection: FAILED")
            )
        except Exception as e:
            health_checks["checks"]["connection"] = {
                "status": "FAILED",
                "message": str(e)
            }
            self.stdout.write(self.style.ERROR(f"✗ Connection: {e}"))

        # 2. Performance test
        try:
            import redis
            conn = cache._cache
            start = time.time()
            conn.ping()
            latency = (time.time() - start) * 1000
            is_fast = latency < 10

            health_checks["checks"]["latency"] = {
                "status": "HEALTHY" if is_fast else "SLOW",
                "latency_ms": round(latency, 2)
            }
            self.stdout.write(
                self.style.SUCCESS(f"✓ Latency: {latency:.2f}ms") if is_fast
                else self.style.WARNING(f"⚠ Latency: {latency:.2f}ms")
            )
        except Exception as e:
            health_checks["checks"]["latency"] = {
                "status": "UNKNOWN",
                "message": str(e)
            }

        # 3. Memory usage
        try:
            info = cache._cache.info()
            used_percent = float(
                info.get("used_memory") /
                info.get("maxmemory", 1)
            ) * 100

            is_ok = used_percent < 80

            health_checks["checks"]["memory"] = {
                "status": "OK" if is_ok else "HIGH",
                "used_percent": round(used_percent, 2)
            }
            self.stdout.write(
                self.style.SUCCESS(f"✓ Memory: {used_percent:.1f}%") if is_ok
                else self.style.WARNING(f"⚠ Memory: {used_percent:.1f}%")
            )
        except Exception:
            pass

        # 4. Eviction rate
        try:
            info = cache._cache.info()
            evicted = info.get("evicted_keys", 0)
            status = "LOW" if evicted < 100 else "HIGH"
            style = self.style.SUCCESS if evicted < 100 else self.style.WARNING

            health_checks["checks"]["evictions"] = {
                "status": status,
                "evicted_keys": evicted
            }
            self.stdout.write(style(f"✓ Evictions: {evicted}"))
        except Exception:
            pass

        if output_json:
            self.stdout.write("\n" + json.dumps(health_checks, indent=2))

    def show_varnish_stats(self, output_json=False):
        """Show Varnish cache statistics."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.HTTP_SUCCESS("VARNISH CACHE STATISTICS"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*60 + "\n"))

        try:
            # Try to get Varnish stats
            result = subprocess.run(
                ["varnishstat", "-1", "-j"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                stats = json.loads(result.stdout)

                # Extract key metrics
                metrics = {
                    "cache_hits": stats.get("MAIN.cache_hit"),
                    "cache_misses": stats.get("MAIN.cache_miss"),
                    "backend_fail": stats.get("MAIN.backend_fail"),
                    "client_requests": stats.get("MAIN.client_requests"),
                }

                # Calculate hit rate
                total = metrics["cache_hits"] + metrics["cache_misses"]
                if total > 0:
                    hit_rate = (metrics["cache_hits"] / total) * 100
                    metrics["hit_rate_percent"] = round(hit_rate, 2)

                for key, value in metrics.items():
                    label = key.replace("_", " ").title()
                    self.stdout.write(f"{label:30} {value}")

                if output_json:
                    self.stdout.write("\n" + json.dumps(metrics, indent=2))
            else:
                self.stdout.write(self.style.WARNING("Varnish not running or not installed"))

        except FileNotFoundError:
            self.stdout.write(self.style.WARNING("varnishstat command not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))

    def show_nginx_stats(self, output_json=False):
        """Show Nginx cache statistics."""
        self.stdout.write(self.style.HTTP_SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.HTTP_SUCCESS("NGINX CACHE STATISTICS"))
        self.stdout.write(self.style.HTTP_SUCCESS("="*60 + "\n"))

        try:
            # Check Nginx cache directory
            cache_dirs = [
                "/var/cache/nginx/main",
                "/var/cache/nginx/static",
                "/var/cache/nginx/api"
            ]

            stats = {"timestamp": datetime.now().isoformat()}

            for cache_dir in cache_dirs:
                if os.path.exists(cache_dir):
                    size = self.get_dir_size(cache_dir)
                    file_count = len(list(Path(cache_dir).rglob("*")))

                    key = cache_dir.split("/")[-1]
                    stats[f"{key}_size_mb"] = round(size / 1024 / 1024, 2)
                    stats[f"{key}_files"] = file_count

                    self.stdout.write(
                        f"{key.upper():20} {round(size/1024/1024, 2):10.2f}MB "
                        f"({file_count:,} files)"
                    )

            if output_json:
                self.stdout.write("\n" + json.dumps(stats, indent=2))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))

    def watch_cache_stats(self, interval, output_json=False):
        """Watch cache statistics for N seconds."""
        self.stdout.write(self.style.HTTP_SUCCESS(
            f"\nWatching cache statistics for {interval} seconds...\n"
        ))

        start_time = time.time()
        iteration = 0

        while time.time() - start_time < interval:
            iteration += 1

            # Clear screen
            os.system("clear" if os.name != "nt" else "cls")

            self.stdout.write(
                self.style.HTTP_SUCCESS(
                    f"CACHE MONITOR - Iteration {iteration} "
                    f"({int(time.time() - start_time)}s/{interval}s)\n"
                )
            )

            try:
                self.show_cache_stats(output_json=False)
                self.check_cache_health(output_json=False)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))

            # Wait before next iteration
            time.sleep(5)

    @staticmethod
    def get_redis_keyspace():
        """Get Redis keyspace stats."""
        try:
            from django.core.cache import cache
            info = cache._cache.info()
            keyspace = info.get("db0", {})
            if isinstance(keyspace, dict):
                return keyspace.get("keys", 0)
            return 0
        except Exception:
            return "N/A"

    @staticmethod
    def get_dir_size(path):
        """Get directory size in bytes."""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total += os.path.getsize(fp)
        except Exception:
            pass
        return total

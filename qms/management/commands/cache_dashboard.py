"""
Cache Dashboard Management Command
==================================

Display real-time cache metrics and monitoring.

Usage:
    python manage.py cache_dashboard
    python manage.py cache_dashboard --live
    python manage.py cache_dashboard --stats
    python manage.py cache_dashboard --performance
    python manage.py cache_dashboard --alerts

Author: Caching Team
Date: 2025-12
"""

import logging
import time
import os
from django.core.management.base import BaseCommand
from django.utils import timezone

from qms.cache_dashboard import (
    DashboardDataProvider,
    metrics_collector,
    alert_manager,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Display cache dashboard and real-time monitoring"
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--live',
            action='store_true',
            help='Live dashboard with continuous updates (every 5 seconds)',
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show detailed cache statistics',
        )
        
        parser.add_argument(
            '--performance',
            action='store_true',
            help='Show performance summary',
        )
        
        parser.add_argument(
            '--alerts',
            action='store_true',
            help='Show current alerts',
        )
        
        parser.add_argument(
            '--health',
            action='store_true',
            help='Show cache health status',
        )
        
        parser.add_argument(
            '--trends',
            action='store_true',
            help='Show trend analysis (last hour)',
        )
        
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON',
        )
        
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Update interval in seconds (for --live, default: 5)',
        )
        
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear screen between updates (for --live)',
        )
    
    def handle(self, *args, **options):
        """Execute command."""
        provider = DashboardDataProvider()
        
        if options['json']:
            self.output_json(provider)
            return
        
        if options['live']:
            self.live_dashboard(provider, options)
            return
        
        if options['stats']:
            self.show_stats(provider)
            return
        
        if options['performance']:
            self.show_performance(provider)
            return
        
        if options['alerts']:
            self.show_alerts()
            return
        
        if options['health']:
            self.show_health(provider)
            return
        
        if options['trends']:
            self.show_trends(provider)
            return
        
        # Default: show dashboard
        self.show_dashboard(provider)
    
    def show_dashboard(self, provider: DashboardDataProvider):
        """Show complete cache dashboard."""
        self.stdout.write(self.style.SUCCESS("\n╔════════════════════════════════════════════════════╗"))
        self.stdout.write(self.style.SUCCESS("║         CACHE DASHBOARD & MONITORING              ║"))
        self.stdout.write(self.style.SUCCESS("╚════════════════════════════════════════════════════╝\n"))
        
        # Performance summary
        perf = provider.get_performance_summary()
        
        self.stdout.write(self.style.WARNING("📊 PERFORMANCE SUMMARY"))
        self.stdout.write(f"  Combined Hit Rate:    {perf['cache_hit_rate']:.1f}%")
        self.stdout.write(f"  L1 Efficiency:        {perf['l1_efficiency']:.1f}%")
        self.stdout.write(f"  L2 Efficiency:        {perf['l2_efficiency']:.1f}%")
        self.stdout.write(f"  L3 Efficiency:        {perf['l3_efficiency']:.1f}%")
        self.stdout.write(f"  Memory Usage:         {perf['memory_used_gb']:.1f} GB")
        self.stdout.write(f"  Items Cached:         {perf['items_cached']}")
        self.stdout.write(f"  Trend:                {perf['hourly_trend'].upper()}\n")
        
        # Cache health
        health = provider._get_cache_health()
        self.stdout.write(self.style.WARNING("🏥 CACHE HEALTH"))
        self.stdout.write(f"  Status:     {health['status']}")
        self.stdout.write(f"  Hit Rate:   {health['hit_rate']:.1%}")
        self.stdout.write(f"  Advice:     {health['recommendation']}\n")
        
        # Access patterns
        patterns = provider._get_access_patterns()
        self.stdout.write(self.style.WARNING("🔍 ACCESS PATTERNS"))
        self.stdout.write(f"  Total Tracked Keys:   {patterns['total_keys']}")
        self.stdout.write(f"  Hot Keys:             {patterns['hot_keys_count']}")
        self.stdout.write(f"  Warm Keys:            {patterns['warm_keys_count']}")
        self.stdout.write(f"  Peak Hours:           {patterns['peak_hours']}")
        self.stdout.write(f"  Off-Peak Hours:       {patterns['off_peak_hours']}\n")
        
        # Hot keys
        self.stdout.write(self.style.WARNING("🔥 TOP HOT KEYS (Most Accessed)"))
        hot_keys = provider._get_hot_keys(limit=5)
        
        if hot_keys:
            for i, key_info in enumerate(hot_keys, 1):
                self.stdout.write(
                    f"  {i}. {key_info['key']:<30} "
                    f"(Score: {key_info['score']:.1f}, "
                    f"Accesses: {key_info['accesses']}, "
                    f"Users: {key_info['users']})"
                )
        else:
            self.stdout.write("  (No data yet)")
        
        self.stdout.write("")
        
        # Alerts
        alerts = alert_manager.get_alerts()
        if alerts:
            self.stdout.write(self.style.ERROR("⚠️  ALERTS"))
            for alert in alerts[-3:]:
                severity_color = {
                    'critical': self.style.ERROR,
                    'warning': self.style.WARNING,
                    'info': self.style.SUCCESS,
                }.get(alert['severity'], self.style.SUCCESS)
                
                self.stdout.write(
                    severity_color(
                        f"  [{alert['severity'].upper()}] {alert['message']}"
                    )
                )
            self.stdout.write("")
        
        # Timestamp
        self.stdout.write(
            self.style.WARNING(
                f"Last updated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
    
    def live_dashboard(self, provider: DashboardDataProvider, options):
        """Show live dashboard with continuous updates."""
        interval = options['interval']
        clear = options['clear']
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting live dashboard (updating every {interval}s, press Ctrl+C to exit)\n"
            )
        )
        
        try:
            while True:
                if clear and os.system('clear') == 0:
                    pass  # Unix/Linux
                elif clear:
                    os.system('cls')  # Windows
                
                self.show_dashboard(provider)
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.stdout.write("\n\nDashboard closed.")
    
    def show_stats(self, provider: DashboardDataProvider):
        """Show detailed statistics."""
        data = provider.get_dashboard_data()
        
        self.stdout.write(self.style.SUCCESS("\n=== Detailed Cache Statistics ===\n"))
        
        # L1 Stats
        self.stdout.write(self.style.WARNING("L1 Cache (Request-Scoped):"))
        l1 = data['current_metrics']['l1']
        for key, value in l1.items():
            self.stdout.write(f"  {key}: {value}")
        
        # L2 Stats
        self.stdout.write(self.style.WARNING("\nL2 Cache (Worker-Scoped):"))
        l2 = data['current_metrics']['l2']
        for key, value in l2.items():
            self.stdout.write(f"  {key}: {value}")
        
        # L3 Stats
        self.stdout.write(self.style.WARNING("\nL3 Cache (Distributed/Redis):"))
        l3 = data['current_metrics']['l3']
        for key, value in l3.items():
            self.stdout.write(f"  {key}: {value}")
        
        # System Stats
        self.stdout.write(self.style.WARNING("\nSystem Statistics:"))
        system = data['current_metrics']['system']
        for key, value in system.items():
            if isinstance(value, float):
                self.stdout.write(f"  {key}: {value:.3f}")
            else:
                self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write("")
    
    def show_performance(self, provider: DashboardDataProvider):
        """Show performance summary."""
        self.stdout.write(self.style.SUCCESS("\n=== Performance Summary ===\n"))
        
        perf = provider.get_performance_summary()
        hourly = metrics_collector.get_averages(60)
        daily = metrics_collector.get_averages(1440)
        
        self.stdout.write("Current Performance:")
        for key, value in perf.items():
            self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write("\nHourly Averages:")
        for key, value in hourly.items():
            if isinstance(value, float):
                self.stdout.write(f"  {key}: {value:.3f}")
            else:
                self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write("\nDaily Averages:")
        for key, value in daily.items():
            if isinstance(value, float):
                self.stdout.write(f"  {key}: {value:.3f}")
            else:
                self.stdout.write(f"  {key}: {value}")
        
        self.stdout.write("")
    
    def show_health(self, provider: DashboardDataProvider):
        """Show cache health."""
        self.stdout.write(self.style.SUCCESS("\n=== Cache Health ===\n"))
        
        health = provider._get_cache_health()
        
        self.stdout.write(f"Status: {health['status']}")
        self.stdout.write(f"Health Level: {health['health'].upper()}")
        self.stdout.write(f"Hit Rate: {health['hit_rate']:.1%}")
        self.stdout.write(f"\nRecommendation: {health['recommendation']}")
        self.stdout.write("")
    
    def show_trends(self, provider: DashboardDataProvider):
        """Show trend analysis."""
        self.stdout.write(self.style.SUCCESS("\n=== Trend Analysis (Last Hour) ===\n"))
        
        trends = metrics_collector.get_trends(60)
        
        self.stdout.write(f"Trend: {trends['trend'].upper()}")
        self.stdout.write(f"Change: {trends['change']:+.1%}")
        self.stdout.write(f"First Half Avg: {trends['first_half_avg']:.1%}")
        self.stdout.write(f"Second Half Avg: {trends['second_half_avg']:.1%}")
        self.stdout.write("")
    
    def show_alerts(self):
        """Show current alerts."""
        self.stdout.write(self.style.SUCCESS("\n=== Cache Alerts ===\n"))
        
        critical = alert_manager.get_alerts('critical')
        warnings = alert_manager.get_alerts('warning')
        info = alert_manager.get_alerts('info')
        
        if critical:
            self.stdout.write(self.style.ERROR("🔴 CRITICAL:"))
            for alert in critical[-5:]:
                self.stdout.write(f"  • {alert['message']}")
        
        if warnings:
            self.stdout.write(self.style.WARNING("🟡 WARNINGS:"))
            for alert in warnings[-5:]:
                self.stdout.write(f"  • {alert['message']}")
        
        if info:
            self.stdout.write(self.style.SUCCESS("ℹ️  INFO:"))
            for alert in info[-3:]:
                self.stdout.write(f"  • {alert['message']}")
        
        if not (critical or warnings or info):
            self.stdout.write(self.style.SUCCESS("✓ No alerts"))
        
        self.stdout.write("")
    
    def output_json(self, provider: DashboardDataProvider):
        """Output dashboard data as JSON."""
        import json
        data = provider.get_dashboard_data()
        self.stdout.write(json.dumps(data, indent=2, default=str))

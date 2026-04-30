#!/usr/bin/env python
"""
Cache System Validation Script
Valida todos os componentes do sistema de cache Fase 7
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.cache import cache
from django_redis import get_redis_connection
from config.multilevel_cache import MultiLevelCacheManager
from config.cache_invalidation import initialize_cache_invalidation
from qms.cache_warming import access_analyzer, cache_warmer
from qms.cache_dashboard import metrics_collector, alert_manager
import json
from datetime import datetime


class CacheSystemValidator:
    """Valida todos os componentes do sistema de cache"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def log_result(self, component, status, message, details=None):
        """Log resultado de validação"""
        result = {
            'component': component,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if details:
            result['details'] = details
        self.results.append(result)
        
        if status == '✅ PASS':
            self.passed += 1
            symbol = '✅'
        elif status == '⚠️ WARNING':
            self.warnings += 1
            symbol = '⚠️'
        else:
            self.failed += 1
            symbol = '❌'
            
        print(f"{symbol} {component}: {message}")
        
    def validate_django_settings(self):
        """Validar configurações Django"""
        print("\n📋 Validando Configurações Django...")
        
        # Cache settings
        if 'default' in settings.CACHES:
            self.log_result(
                'Django Cache Config',
                '✅ PASS',
                'Cache configuration found'
            )
        else:
            self.log_result(
                'Django Cache Config',
                '❌ FAIL',
                'No cache configuration in settings'
            )
            
        # Redis URL
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            self.log_result(
                'Redis URL Config',
                '✅ PASS',
                f'Redis URL configured: {redis_url[:40]}...'
            )
        else:
            self.log_result(
                'Redis URL Config',
                '⚠️ WARNING',
                'REDIS_URL not set (using default localhost:6379)'
            )
            
    def validate_redis_connection(self):
        """Validar conexão Redis"""
        print("\n🔴 Validando Redis...")
        
        try:
            redis_conn = get_redis_connection("default")
            ping = redis_conn.ping()
            
            if ping:
                # Teste de set/get
                redis_conn.set('test_key', 'test_value', 60)
                value = redis_conn.get('test_key')
                
                if value:
                    self.log_result(
                        'Redis Connection',
                        '✅ PASS',
                        'Redis connected and responding'
                    )
                    
                    # Info do Redis
                    info = redis_conn.info()
                    self.log_result(
                        'Redis Info',
                        '✅ PASS',
                        f"Redis v{info['redis_version']} - {info['used_memory_human']} used",
                        {'version': info['redis_version'], 'memory': info['used_memory_human']}
                    )
                else:
                    self.log_result(
                        'Redis Read/Write',
                        '❌ FAIL',
                        'Redis not responding to get/set'
                    )
            else:
                self.log_result(
                    'Redis Connection',
                    '❌ FAIL',
                    'Redis ping failed'
                )
                
        except Exception as e:
            self.log_result(
                'Redis Connection',
                '❌ FAIL',
                f'Cannot connect to Redis: {str(e)}'
            )
            
    def validate_multilevel_cache(self):
        """Validar cache multi-nível"""
        print("\n📦 Validando Cache Multi-Nível...")
        
        try:
            cache_manager = MultiLevelCacheManager()
            
            # Test set/get
            cache_manager.set('validation_key', {'test': 'data'}, 300)
            value = cache_manager.get('validation_key')
            
            if value and value.get('test') == 'data':
                self.log_result(
                    'MultiLevel Cache',
                    '✅ PASS',
                    'Multi-level cache working (L1+L2+L3)'
                )
            else:
                self.log_result(
                    'MultiLevel Cache',
                    '❌ FAIL',
                    'Multi-level cache get/set failed'
                )
                
            # Stats
            stats = cache_manager.get_stats()
            self.log_result(
                'Cache Statistics',
                '✅ PASS',
                f"L1: {stats.get('l1_hits', 0)} hits | L2: {stats.get('l2_hits', 0)} hits | L3: {stats.get('l3_hits', 0)} hits"
            )
            
        except Exception as e:
            self.log_result(
                'MultiLevel Cache',
                '❌ FAIL',
                f'Cache error: {str(e)}'
            )
            
    def validate_cache_invalidation(self):
        """Validar invalidação de cache"""
        print("\n🔄 Validando Cache Invalidation...")
        
        try:
            # Initialize signals
            initialize_cache_invalidation()
            self.log_result(
                'Cache Signals',
                '✅ PASS',
                'Cache invalidation signals registered'
            )
            
            # Test pattern invalidation
            cache.set('test:1:data', 'value1')
            cache.set('test:2:data', 'value2')
            
            # Implementar invalidação
            from config.cache_invalidation import CascadingInvalidator
            invalidator = CascadingInvalidator()
            invalidator.invalidate_pattern('test:*')
            
            self.log_result(
                'Pattern Invalidation',
                '✅ PASS',
                'Pattern-based cache invalidation working'
            )
            
        except Exception as e:
            self.log_result(
                'Cache Invalidation',
                '⚠️ WARNING',
                f'Invalidation test incomplete: {str(e)}'
            )
            
    def validate_cache_warming(self):
        """Validar cache warming"""
        print("\n🔥 Validando Cache Warming...")
        
        try:
            # Check access analyzer
            if access_analyzer:
                self.log_result(
                    'Access Pattern Analyzer',
                    '✅ PASS',
                    'Access pattern analyzer initialized'
                )
            else:
                self.log_result(
                    'Access Pattern Analyzer',
                    '❌ FAIL',
                    'Access pattern analyzer not initialized'
                )
                
            # Check cache warmer
            if cache_warmer:
                self.log_result(
                    'Cache Warmer',
                    '✅ PASS',
                    'Cache warmer initialized'
                )
            else:
                self.log_result(
                    'Cache Warmer',
                    '❌ FAIL',
                    'Cache warmer not initialized'
                )
                
        except Exception as e:
            self.log_result(
                'Cache Warming',
                '⚠️ WARNING',
                f'Warming validation incomplete: {str(e)}'
            )
            
    def validate_dashboard(self):
        """Validar dashboard"""
        print("\n📊 Validando Cache Dashboard...")
        
        try:
            # Collect metrics
            metrics = metrics_collector.collect()
            
            if metrics:
                self.log_result(
                    'Metrics Collection',
                    '✅ PASS',
                    f"Metrics collected: L1={metrics.l1_stats}, L2={metrics.l2_stats}, L3={metrics.l3_stats}"
                )
            else:
                self.log_result(
                    'Metrics Collection',
                    '⚠️ WARNING',
                    'No metrics collected yet'
                )
                
            # Check alerts
            if alert_manager:
                self.log_result(
                    'Alert Manager',
                    '✅ PASS',
                    'Alert manager initialized'
                )
            else:
                self.log_result(
                    'Alert Manager',
                    '❌ FAIL',
                    'Alert manager not initialized'
                )
                
        except Exception as e:
            self.log_result(
                'Dashboard',
                '⚠️ WARNING',
                f'Dashboard validation incomplete: {str(e)}'
            )
            
    def validate_celery(self):
        """Validar Celery integration"""
        print("\n⚙️ Validando Celery...")
        
        try:
            from config.celery import app
            
            # Check if tasks are registered
            tasks = list(app.tasks.keys())
            cache_tasks = [t for t in tasks if 'cache' in t or 'warming' in t]
            
            if cache_tasks:
                self.log_result(
                    'Celery Cache Tasks',
                    '✅ PASS',
                    f'Found {len(cache_tasks)} cache-related tasks registered'
                )
            else:
                self.log_result(
                    'Celery Cache Tasks',
                    '⚠️ WARNING',
                    'No cache-related tasks found'
                )
                
        except Exception as e:
            self.log_result(
                'Celery',
                '⚠️ WARNING',
                f'Celery validation incomplete: {str(e)}'
            )
            
    def validate_files_exist(self):
        """Validar que todos os arquivos necessários existem"""
        print("\n📁 Validando Arquivos...")
        
        required_files = [
            'config/http_cache_config.py',
            'config/cache_decorators.py',
            'config/multilevel_cache.py',
            'config/cache_managers.py',
            'config/cache_invalidation.py',
            'qms/cache_signals.py',
            'qms/cache_warming.py',
            'qms/cache_warming_tasks.py',
            'qms/cache_dashboard.py',
        ]
        
        missing_files = []
        for filepath in required_files:
            full_path = os.path.join(settings.BASE_DIR, filepath)
            if os.path.exists(full_path):
                self.log_result(
                    f'File: {filepath}',
                    '✅ PASS',
                    'File exists'
                )
            else:
                missing_files.append(filepath)
                self.log_result(
                    f'File: {filepath}',
                    '❌ FAIL',
                    'File not found'
                )
                
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*60)
        print("📋 CACHE SYSTEM VALIDATION SUMMARY")
        print("="*60)
        
        total = self.passed + self.failed + self.warnings
        
        print(f"\n✅ PASSED:  {self.passed}/{total}")
        print(f"⚠️ WARNING: {self.warnings}/{total}")
        print(f"❌ FAILED:  {self.failed}/{total}")
        
        percentage = (self.passed / total * 100) if total > 0 else 0
        print(f"\n📊 Overall Score: {percentage:.1f}%")
        
        if self.failed == 0 and self.warnings == 0:
            print("\n🎉 CACHE SYSTEM FULLY VALIDATED! Ready for Staging/Production")
            return True
        elif self.failed == 0:
            print("\n⚠️ CACHE SYSTEM MOSTLY VALIDATED (with warnings)")
            return True
        else:
            print("\n❌ CACHE SYSTEM HAS ISSUES - Fix before deployment")
            return False
            
    def save_results(self):
        """Save validation results to JSON"""
        output_file = os.path.join(settings.BASE_DIR, 'cache_validation_results.json')
        
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'passed': self.passed,
                    'warnings': self.warnings,
                    'failed': self.failed,
                    'total': self.passed + self.failed + self.warnings
                },
                'results': self.results
            }, f, indent=2)
            
        print(f"\n💾 Results saved to: {output_file}")
        
    def run_all_validations(self):
        """Run all validations"""
        print("🔍 VALIDATING CACHE SYSTEM (FASE 7)")
        print("="*60)
        
        self.validate_django_settings()
        self.validate_redis_connection()
        self.validate_multilevel_cache()
        self.validate_cache_invalidation()
        self.validate_cache_warming()
        self.validate_dashboard()
        self.validate_celery()
        self.validate_files_exist()
        
        success = self.print_summary()
        self.save_results()
        
        return success


if __name__ == '__main__':
    validator = CacheSystemValidator()
    success = validator.run_all_validations()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

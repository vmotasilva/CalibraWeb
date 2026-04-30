"""
Django management command for frontend optimization.

Usage:
    python manage.py optimize_static --minify-css
    python manage.py optimize_static --minify-js
    python manage.py optimize_static --optimize-images
    python manage.py optimize_static --gzip
    python manage.py optimize_static --service-worker
    python manage.py optimize_static --all
"""

import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from qms.static_optimizer import StaticOptimizer


class Command(BaseCommand):
    help = 'Optimize frontend assets (CSS, JS, images, compression)'
    
    def add_arguments(self, parser):
        """Define command arguments."""
        parser.add_argument(
            '--minify-css',
            action='store_true',
            help='Minify CSS files'
        )
        parser.add_argument(
            '--minify-js',
            action='store_true',
            help='Minify JavaScript files'
        )
        parser.add_argument(
            '--optimize-images',
            action='store_true',
            help='Optimize images (resize, compress)'
        )
        parser.add_argument(
            '--gzip',
            action='store_true',
            help='Gzip compress static files'
        )
        parser.add_argument(
            '--service-worker',
            action='store_true',
            help='Generate service worker'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimizations'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='dist/',
            help='Output directory for optimized files (default: dist/)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        """Execute command."""
        # Determine what to run
        run_all = options['all']
        minify_css = options['minify_css'] or run_all
        minify_js = options['minify_js'] or run_all
        optimize_images = options['optimize_images'] or run_all
        gzip = options['gzip'] or run_all
        service_worker = options['service_worker'] or run_all
        
        # If nothing selected, show help
        if not any([minify_css, minify_js, optimize_images, gzip, service_worker]):
            self.stdout.write(
                self.style.ERROR(
                    'Please specify at least one optimization type or use --all'
                )
            )
            return
        
        optimizer = StaticOptimizer(settings.STATIC_ROOT)
        dry_run = options['dry_run']
        output_dir = options['output']
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('FRONTEND OPTIMIZATION TASK'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be made'))
        
        try:
            # CSS Minification
            if minify_css:
                self._minify_css(optimizer, output_dir, dry_run)
            
            # JavaScript Minification
            if minify_js:
                self._minify_javascript(optimizer, output_dir, dry_run)
            
            # Image Optimization
            if optimize_images:
                self._optimize_images(optimizer, output_dir, dry_run)
            
            # Gzip Compression
            if gzip:
                self._gzip_files(optimizer, output_dir, dry_run)
            
            # Service Worker Generation
            if service_worker:
                self._generate_service_worker(optimizer, output_dir, dry_run)
            
            self.stdout.write(self.style.SUCCESS('\n✅ Frontend optimization completed!'))
            self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        except Exception as e:
            raise CommandError(f'Optimization failed: {str(e)}')
    
    def _minify_css(self, optimizer, output_dir, dry_run):
        """Minify CSS files."""
        self.stdout.write('\n📦 Minifying CSS files...')
        
        css_count = 0
        total_original = 0
        total_minified = 0
        
        static_root = optimizer.static_root
        for root, dirs, files in os.walk(static_root):
            for file in files:
                if file.endswith('.css'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r') as f:
                            css_content = f.read()
                        
                        original_size = len(css_content.encode())
                        minified = optimizer.minify_css(css_content)
                        minified_size = len(minified.encode())
                        
                        if not dry_run:
                            with open(file_path, 'w') as f:
                                f.write(minified)
                        
                        css_count += 1
                        total_original += original_size
                        total_minified += minified_size
                        
                        saved = original_size - minified_size
                        ratio = (minified_size / original_size * 100) if original_size > 0 else 0
                        
                        self.stdout.write(f"  ✓ {file} ({ratio:.1f}%, saved {saved/1024:.1f}KB)")
                    
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Error: {file} - {e}"))
        
        if css_count > 0:
            total_saved = total_original - total_minified
            ratio = (total_minified / total_original * 100) if total_original > 0 else 0
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  Minified {css_count} CSS files"
                    f" | Total: {ratio:.1f}% | Saved: {total_saved/1024:.1f}KB"
                )
            )
    
    def _minify_javascript(self, optimizer, output_dir, dry_run):
        """Minify JavaScript files."""
        self.stdout.write('\n📦 Minifying JavaScript files...')
        
        js_count = 0
        total_original = 0
        total_minified = 0
        
        static_root = optimizer.static_root
        for root, dirs, files in os.walk(static_root):
            for file in files:
                if file.endswith('.js') and not file.endswith('.min.js'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r') as f:
                            js_content = f.read()
                        
                        original_size = len(js_content.encode())
                        minified = optimizer.minify_javascript(js_content)
                        minified_size = len(minified.encode())
                        
                        if not dry_run:
                            with open(file_path, 'w') as f:
                                f.write(minified)
                        
                        js_count += 1
                        total_original += original_size
                        total_minified += minified_size
                        
                        saved = original_size - minified_size
                        ratio = (minified_size / original_size * 100) if original_size > 0 else 0
                        
                        self.stdout.write(f"  ✓ {file} ({ratio:.1f}%, saved {saved/1024:.1f}KB)")
                    
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Error: {file} - {e}"))
        
        if js_count > 0:
            total_saved = total_original - total_minified
            ratio = (total_minified / total_original * 100) if total_original > 0 else 0
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  Minified {js_count} JavaScript files"
                    f" | Total: {ratio:.1f}% | Saved: {total_saved/1024:.1f}KB"
                )
            )
    
    def _optimize_images(self, optimizer, output_dir, dry_run):
        """Optimize images."""
        self.stdout.write('\n🖼️  Optimizing images...')
        
        try:
            from PIL import Image
        except ImportError:
            self.stdout.write(
                self.style.WARNING('  ⚠ Pillow not installed. Install with: pip install Pillow')
            )
            return
        
        # Find images directory
        images_dir = os.path.join(optimizer.static_root, 'images')
        if not os.path.exists(images_dir):
            self.stdout.write(f"  ⚠ Images directory not found: {images_dir}")
            return
        
        if not dry_run:
            stats = optimizer.optimize_image_directory(images_dir)
            optimizer.print_optimization_report(stats)
        else:
            self.stdout.write("  [DRY RUN] Would optimize images in " + images_dir)
    
    def _gzip_files(self, optimizer, output_dir, dry_run):
        """Gzip compress files."""
        self.stdout.write('\n🗜️  Compressing files with gzip...')
        
        if not dry_run:
            stats = optimizer.gzip_directory(optimizer.static_root)
            optimizer.print_optimization_report(stats)
        else:
            self.stdout.write(f"  [DRY RUN] Would gzip compress files in {optimizer.static_root}")
    
    def _generate_service_worker(self, optimizer, output_dir, dry_run):
        """Generate service worker."""
        self.stdout.write('\n⚙️  Generating service worker...')
        
        sw_path = os.path.join(output_dir, 'service-worker.js')
        
        if not dry_run:
            optimizer.generate_service_worker(sw_path)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Service worker generated at {sw_path}"))
        else:
            self.stdout.write(f"  [DRY RUN] Would generate service worker at {sw_path}")

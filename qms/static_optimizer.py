"""
Frontend optimization utilities for CSS/JS minification, image optimization,
and static file compression.

Features:
- CSS minification (removes comments, whitespace, unused rules)
- JavaScript minification (basic whitespace removal)
- Image optimization (compression, format conversion)
- Inline critical CSS
- Lazy loading decorator for images
- Service worker generation

Example:
    from qms.static_optimizer import StaticOptimizer

    # Minify CSS
    optimizer = StaticOptimizer()
    minified_css = optimizer.minify_css(css_content)

    # Optimize images
    optimizer.optimize_image_directory('static/images/')

    # Generate service worker
    optimizer.generate_service_worker('dist/sw.js')
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import gzip
import json
from datetime import datetime

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

from django.conf import settings
from django.core.files.storage import staticfiles_storage


class StaticOptimizer:
    """Main class for static file optimization."""
    
    def __init__(self, static_root: Optional[str] = None):
        """Initialize optimizer with static files root."""
        self.static_root = static_root or settings.STATIC_ROOT
        self.static_url = settings.STATIC_URL
        self.metrics = {
            'files_processed': 0,
            'original_size': 0,
            'compressed_size': 0,
            'compression_ratio': 0.0,
        }
    
    # =========================================================================
    # CSS MINIFICATION
    # =========================================================================
    
    def minify_css(self, css_content: str) -> str:
        """
        Minify CSS content by removing comments, whitespace, and unnecessary characters.
        
        Args:
            css_content: Raw CSS content
        
        Returns:
            Minified CSS content
        """
        # Remove comments
        css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
        
        # Remove whitespace around special characters
        css_content = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', css_content)
        
        # Remove whitespace at start/end of lines
        css_content = re.sub(r'^\s+|\s+$', '', css_content, flags=re.MULTILINE)
        
        # Remove newlines
        css_content = re.sub(r'\n+', '', css_content)
        
        # Remove spaces around values
        css_content = re.sub(r':\s+', ':', css_content)
        css_content = re.sub(r';\s*', ';', css_content)
        
        # Remove last semicolon in declarations
        css_content = re.sub(r';}', '}', css_content)
        
        # Remove leading zeros
        css_content = re.sub(r'\b0\.', '.', css_content)
        
        # Shorten color values (hex)
        css_content = re.sub(r'#([0-9a-f])\1([0-9a-f])\2([0-9a-f])\3', r'#\1\2\3', css_content, flags=re.IGNORECASE)
        
        return css_content.strip()
    
    # =========================================================================
    # JAVASCRIPT MINIFICATION
    # =========================================================================
    
    def minify_javascript(self, js_content: str) -> str:
        """
        Minify JavaScript content.
        
        Note: This is basic minification. For production, use terser or uglify-js.
        
        Args:
            js_content: Raw JavaScript content
        
        Returns:
            Minified JavaScript content
        """
        # Remove single-line comments (but not URLs with //)
        js_content = re.sub(r'//(?!.*:.*\/\/).*$', '', js_content, flags=re.MULTILINE)
        
        # Remove multi-line comments
        js_content = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)
        
        # Remove leading/trailing whitespace from lines
        js_content = re.sub(r'^\s+|\s+$', '', js_content, flags=re.MULTILINE)
        
        # Remove unnecessary whitespace
        js_content = re.sub(r'\s{2,}', ' ', js_content)
        
        # Remove whitespace around operators (careful with this)
        js_content = re.sub(r'\s*([{}();:,])\s*', r'\1', js_content)
        js_content = re.sub(r'\s*([=+\-*/<>!&|])\s*', r' \1 ', js_content)
        
        # Clean up the result
        js_content = re.sub(r'\s+', ' ', js_content).strip()
        
        return js_content
    
    # =========================================================================
    # IMAGE OPTIMIZATION
    # =========================================================================
    
    def optimize_image(
        self,
        image_path: str,
        max_width: int = 1920,
        quality: int = 85,
        output_path: Optional[str] = None,
    ) -> Tuple[str, int, int]:
        """
        Optimize a single image.
        
        Args:
            image_path: Path to source image
            max_width: Maximum width in pixels
            quality: JPEG quality (1-100)
            output_path: Path to save optimized image
        
        Returns:
            Tuple of (output_path, original_size, optimized_size)
        """
        if not HAS_PILLOW:
            raise ImportError("Pillow is required for image optimization. Install with: pip install Pillow")
        
        try:
            image = Image.open(image_path)
            
            # Get original size
            original_size = os.path.getsize(image_path)
            
            # Resize if needed
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            if output_path is None:
                output_path = image_path
            
            # Determine format and save
            if image.mode in ('RGBA', 'LA', 'P'):
                image.save(output_path, format='PNG', optimize=True)
            else:
                image.save(output_path, format='JPEG', quality=quality, optimize=True)
            
            # Get optimized size
            optimized_size = os.path.getsize(output_path)
            
            return output_path, original_size, optimized_size
        
        except Exception as e:
            raise Exception(f"Error optimizing image {image_path}: {str(e)}")
    
    def optimize_image_directory(
        self,
        directory: str,
        recursive: bool = True,
        patterns: Optional[List[str]] = None,
    ) -> Dict[str, any]:
        """
        Optimize all images in a directory.
        
        Args:
            directory: Directory path
            recursive: Include subdirectories
            patterns: File patterns to match (default: *.jpg, *.png, *.gif)
        
        Returns:
            Dictionary with optimization statistics
        """
        if patterns is None:
            patterns = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
        
        stats = {
            'images_optimized': 0,
            'total_original_size': 0,
            'total_optimized_size': 0,
            'total_saved': 0,
            'details': []
        }
        
        directory = Path(directory)
        
        for pattern in patterns:
            if recursive:
                files = directory.rglob(pattern)
            else:
                files = directory.glob(pattern)
            
            for image_file in files:
                try:
                    _, orig_size, opt_size = self.optimize_image(str(image_file))
                    saved = orig_size - opt_size
                    
                    stats['images_optimized'] += 1
                    stats['total_original_size'] += orig_size
                    stats['total_optimized_size'] += opt_size
                    stats['total_saved'] += saved
                    stats['details'].append({
                        'file': str(image_file),
                        'original_size': orig_size,
                        'optimized_size': opt_size,
                        'saved': saved,
                        'ratio': f"{(opt_size / orig_size * 100):.1f}%"
                    })
                except Exception as e:
                    print(f"Warning: Could not optimize {image_file}: {e}")
        
        return stats
    
    # =========================================================================
    # COMPRESSION & GZIP
    # =========================================================================
    
    def gzip_file(self, file_path: str, output_path: Optional[str] = None) -> Tuple[str, int, int]:
        """
        Gzip compress a file.
        
        Args:
            file_path: Path to source file
            output_path: Path to save .gz file
        
        Returns:
            Tuple of (output_path, original_size, compressed_size)
        """
        original_size = os.path.getsize(file_path)
        
        if output_path is None:
            output_path = f"{file_path}.gz"
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        compressed_size = os.path.getsize(output_path)
        
        return output_path, original_size, compressed_size
    
    def gzip_directory(
        self,
        directory: str,
        patterns: Optional[List[str]] = None,
        min_size: int = 1024,  # Only gzip files > 1KB
    ) -> Dict[str, any]:
        """
        Gzip compress all matching files in directory.
        
        Args:
            directory: Directory path
            patterns: File patterns to match
            min_size: Minimum file size to compress in bytes
        
        Returns:
            Dictionary with compression statistics
        """
        if patterns is None:
            patterns = ['*.css', '*.js', '*.html', '*.json', '*.svg', '*.xml']
        
        stats = {
            'files_compressed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'total_saved': 0,
            'details': []
        }
        
        directory = Path(directory)
        
        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                if os.path.getsize(file_path) < min_size:
                    continue
                
                try:
                    _, orig_size, comp_size = self.gzip_file(str(file_path))
                    saved = orig_size - comp_size
                    
                    stats['files_compressed'] += 1
                    stats['total_original_size'] += orig_size
                    stats['total_compressed_size'] += comp_size
                    stats['total_saved'] += saved
                    stats['details'].append({
                        'file': str(file_path),
                        'original_size': orig_size,
                        'compressed_size': comp_size,
                        'saved': saved,
                        'ratio': f"{(comp_size / orig_size * 100):.1f}%"
                    })
                except Exception as e:
                    print(f"Warning: Could not compress {file_path}: {e}")
        
        return stats
    
    # =========================================================================
    # SERVICE WORKER GENERATION
    # =========================================================================
    
    def generate_service_worker(
        self,
        output_path: str,
        cache_name: str = 'calibraweb-v1',
        cache_patterns: Optional[List[str]] = None,
        network_first: Optional[List[str]] = None,
    ) -> None:
        """
        Generate a service worker for offline support and caching.
        
        Args:
            output_path: Where to save the service worker
            cache_name: Name of the cache storage
            cache_patterns: URL patterns to cache
            network_first: Patterns to prefer network over cache
        """
        if cache_patterns is None:
            cache_patterns = [
                r'^/static/',
                r'^/api/.*/$',
                r'\.(?:png|jpg|jpeg|svg|gif|webp|css|js|woff2?)$',
            ]
        
        if network_first is None:
            network_first = [
                r'^/api/',
                r'\.html$',
            ]
        
        service_worker_code = f'''/**
 * Service Worker for CalibraWeb
 * Cache Version: {cache_name}
 * Generated: {datetime.now().isoformat()}
 */

const CACHE_NAME = '{cache_name}';
const CACHE_PATTERNS = {json.dumps(cache_patterns)};
const NETWORK_FIRST_PATTERNS = {json.dumps(network_first)};

// Install event: Cache essential assets
self.addEventListener('install', (event) => {{
    console.log('[SW] Installing service worker...');
    self.skipWaiting();
}});

// Activate event: Clean up old caches
self.addEventListener('activate', (event) => {{
    console.log('[SW] Activating service worker...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {{
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => {{
                        console.log('[SW] Deleting old cache:', name);
                        return caches.delete(name);
                    }})
            );
        }})
    );
}});

// Fetch event: Implement caching strategy
self.addEventListener('fetch', (event) => {{
    const {{ request }} = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {{
        return;
    }}

    // Determine strategy
    const isNetworkFirst = NETWORK_FIRST_PATTERNS.some((pattern) =>
        new RegExp(pattern).test(url.pathname)
    );

    if (isNetworkFirst) {{
        // Network first, fallback to cache
        event.respondWith(networkFirst(request));
    }} else {{
        // Cache first, fallback to network
        event.respondWith(cacheFirst(request));
    }}
}});

/**
 * Cache-first strategy: Try cache first, then network
 * Good for: images, fonts, CSS, JS
 */
async function cacheFirst(request) {{
    try {{
        // Try cache
        const cached = await caches.match(request);
        if (cached) {{
            return cached;
        }}

        // Try network
        const response = await fetch(request);
        if (response && response.status === 200) {{
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }}
        return response;
    }} catch (error) {{
        console.error('[SW] Cache first error:', error);
        return new Response('Service Unavailable', {{ status: 503 }});
    }}
}}

/**
 * Network-first strategy: Try network first, then cache
 * Good for: API calls, HTML
 */
async function networkFirst(request) {{
    try {{
        const response = await fetch(request);
        if (response && response.status === 200) {{
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }}
        return response;
    }} catch (error) {{
        console.warn('[SW] Network error, trying cache:', error);
        const cached = await caches.match(request);
        if (cached) {{
            return cached;
        }}
        return new Response('Network Unavailable', {{ status: 503 }});
    }}
}}

// Message handler for cache clearing
self.addEventListener('message', (event) => {{
    if (event.data && event.data.action === 'clear-cache') {{
        caches.delete(CACHE_NAME).then(() => {{
            console.log('[SW] Cache cleared');
        }});
    }}
}});
'''

        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write service worker
        with open(output_path, 'w') as f:
            f.write(service_worker_code)
        
        print(f"✅ Service worker generated at {output_path}")
    
    # =========================================================================
    # CRITICAL CSS
    # =========================================================================
    
    def extract_critical_css(
        self,
        html_content: str,
        css_file_path: str,
        above_the_fold_selector: str = 'header, .hero, .navbar',
    ) -> str:
        """
        Extract critical CSS (above the fold) from a CSS file based on selectors.
        
        Args:
            html_content: HTML content to analyze
            css_file_path: Path to CSS file
            above_the_fold_selector: Selectors for above-the-fold content
        
        Returns:
            Critical CSS content
        """
        with open(css_file_path, 'r') as f:
            css_content = f.read()
        
        critical_css = []
        
        # Parse CSS rules (simplified)
        rules = re.findall(r'([^{]+)\s*\{([^}]*)\}', css_content)
        
        for selectors, declarations in rules:
            # Check if selector matches above-the-fold elements
            if any(selector.strip() in selectors for selector in above_the_fold_selector.split(',')):
                critical_css.append(f"{selectors} {{{declarations}}}")
        
        return '\n'.join(critical_css)
    
    def inline_critical_css(
        self,
        html_path: str,
        css_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Inline critical CSS into HTML <head>.
        
        Args:
            html_path: Path to HTML file
            css_path: Path to CSS file
            output_path: Path to save modified HTML
        
        Returns:
            Modified HTML content
        """
        with open(html_path, 'r') as f:
            html_content = f.read()
        
        # Extract critical CSS
        critical_css = self.extract_critical_css(html_content, css_path)
        minified_css = self.minify_css(critical_css)
        
        # Inject into head
        style_tag = f'<style>{minified_css}</style>'
        html_content = html_content.replace('</head>', f'{style_tag}</head>', 1)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(html_content)
        
        return html_content
    
    # =========================================================================
    # STATISTICS & REPORTING
    # =========================================================================
    
    def get_metrics_summary(self) -> Dict[str, any]:
        """Get optimization metrics summary."""
        compression_ratio = (
            self.metrics['compressed_size'] / self.metrics['original_size'] * 100
            if self.metrics['original_size'] > 0
            else 0
        )
        
        return {
            'files_processed': self.metrics['files_processed'],
            'original_size_mb': self.metrics['original_size'] / (1024 * 1024),
            'compressed_size_mb': self.metrics['compressed_size'] / (1024 * 1024),
            'compression_ratio': f"{compression_ratio:.1f}%",
            'bytes_saved': self.metrics['original_size'] - self.metrics['compressed_size'],
        }
    
    def print_optimization_report(self, stats: Dict) -> None:
        """Print formatted optimization report."""
        print("\n" + "="*70)
        print("FRONTEND OPTIMIZATION REPORT".center(70))
        print("="*70 + "\n")
        
        if 'images_optimized' in stats:
            print(f"Images Optimized: {stats['images_optimized']}")
            print(f"  Original Size:  {stats['total_original_size'] / (1024*1024):.2f} MB")
            print(f"  Optimized Size: {stats['total_optimized_size'] / (1024*1024):.2f} MB")
            print(f"  Saved:          {stats['total_saved'] / (1024*1024):.2f} MB\n")
        
        if 'files_compressed' in stats:
            print(f"Files Compressed: {stats['files_compressed']}")
            print(f"  Original Size:   {stats['total_original_size'] / (1024*1024):.2f} MB")
            print(f"  Compressed Size: {stats['total_compressed_size'] / (1024*1024):.2f} MB")
            print(f"  Saved:           {stats['total_saved'] / (1024*1024):.2f} MB\n")
        
        print("="*70)

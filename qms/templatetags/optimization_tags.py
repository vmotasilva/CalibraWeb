"""
Template tags for frontend optimization features.

Includes lazy loading, critical CSS, and resource hints.

Usage:
    {% load optimization_tags %}
    {% lazy_image image_url alt_text %}
    {% responsive_image image_url sizes %}
    {% link_preload path %}
    {% link_prefetch path %}
"""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from urllib.parse import quote

register = template.Library()


@register.inclusion_tag('qms/partials/lazy_image.html')
def lazy_image(src, alt='Image', classes='', width=None, height=None, placeholder=None):
    """
    Render a lazy-loaded image using Intersection Observer API.
    
    Usage:
        {% lazy_image '/path/to/image.jpg' 'Alt text' classes='img-fluid' %}
    """
    # Generate placeholder if not provided
    if placeholder is None:
        # Use a lightweight SVG placeholder
        placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3C/svg%3E'
    
    return {
        'src': src,
        'alt': alt,
        'classes': classes,
        'width': width,
        'height': height,
        'placeholder': placeholder,
    }


@register.simple_tag
def responsive_image(src, alt='Image', sizes=None, classes=''):
    """
    Render a responsive image with srcset.
    
    Usage:
        {% responsive_image '/path/to/image.jpg' 'Alt text' sizes='100vw' %}
    """
    if sizes is None:
        sizes = '(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw'
    
    # Generate srcset (simple version - assumes image optimizer naming convention)
    base, ext = src.rsplit('.', 1)
    srcset = f'{src} 1x, {base}-2x.{ext} 2x'
    
    return format_html(
        '<img src="{}" alt="{}" srcset="{}" sizes="{}" class="{}" loading="lazy">',
        src,
        alt,
        srcset,
        sizes,
        classes,
    )


@register.simple_tag
def link_preload(href, as_type='script', crossorigin=False):
    """
    Generate a preload link for critical resources.
    
    Usage:
        {% link_preload '/static/css/critical.css' as_type='style' %}
        {% link_preload '/static/fonts/roboto.woff2' as_type='font' %}
    """
    crossorigin_attr = ' crossorigin' if crossorigin or as_type == 'font' else ''
    
    return format_html(
        '<link rel="preload" href="{}" as="{}"{}/>',
        href,
        as_type,
        mark_safe(crossorigin_attr)
    )


@register.simple_tag
def link_prefetch(href):
    """
    Generate a prefetch link for resources needed on next page.
    
    Usage:
        {% link_prefetch '/static/js/next-page.js' %}
    """
    return format_html(
        '<link rel="prefetch" href="{}"/>',
        href
    )


@register.simple_tag
def link_dns_prefetch(href):
    """
    Generate a DNS-prefetch link for external domains.
    
    Usage:
        {% link_dns_prefetch 'https://api.example.com' %}
    """
    return format_html(
        '<link rel="dns-prefetch" href="{}"/>',
        href
    )


@register.simple_tag
def critical_css_inline(css_content):
    """
    Inline critical CSS in head.
    
    Usage:
        {% critical_css_inline css_content %}
    """
    return format_html(
        '<style>{}</style>',
        mark_safe(css_content)
    )


@register.simple_tag
def defer_script(src):
    """
    Render a deferred script tag.
    
    Usage:
        {% defer_script '/static/js/app.js' %}
    """
    return format_html(
        '<script src="{}" defer></script>',
        src
    )


@register.simple_tag
def async_script(src):
    """
    Render an async script tag.
    
    Usage:
        {% async_script '/static/js/analytics.js' %}
    """
    return format_html(
        '<script src="{}" async></script>',
        src
    )


@register.filter
def lazy_srcset(value):
    """
    Convert image src to lazy-loading compatible format.
    
    Usage:
        {{ image_url|lazy_srcset }}
    """
    # This would be used with data-srcset in templates
    return value


@register.simple_tag
def service_worker_register(sw_path='/static/js/service-worker.js'):
    """
    Generate script to register service worker.
    
    Usage:
        {% service_worker_register %}
    """
    script = f"""
    <script>
        if ('serviceWorker' in navigator) {{
            window.addEventListener('load', () => {{
                navigator.serviceWorker.register('{sw_path}')
                    .then((registration) => {{
                        console.log('Service Worker registered:', registration);
                    }})
                    .catch((error) => {{
                        console.warn('Service Worker registration failed:', error);
                    }});
            }});
        }}
    </script>
    """
    return mark_safe(script)


@register.inclusion_tag('qms/partials/performance_monitoring.html')
def performance_monitoring():
    """
    Include performance monitoring script.
    
    Tracks Core Web Vitals (LCP, FID, CLS).
    """
    return {}


@register.simple_tag
def web_font_preload(font_family, font_url, font_format='woff2'):
    """
    Generate preload link for web fonts.
    
    Usage:
        {% web_font_preload 'Roboto' '/static/fonts/roboto.woff2' %}
    """
    return format_html(
        '<link rel="preload" href="{}" as="font" type="font/{}" crossorigin/>',
        font_url,
        font_format
    )


@register.simple_tag
def video_lazy_load(src, poster=None, width=None, height=None, classes=''):
    """
    Render a lazy-loaded video.
    
    Usage:
        {% video_lazy_load '/video.mp4' poster='/poster.jpg' %}
    """
    attributes = ['loading="lazy"']
    
    if width:
        attributes.append(f'width="{width}"')
    if height:
        attributes.append(f'height="{height}"')
    if classes:
        attributes.append(f'class="{classes}"')
    
    poster_attr = f' poster="{poster}"' if poster else ''
    
    return format_html(
        '<video {}{}><source src="{}" type="video/mp4"></video>',
        mark_safe(' '.join(attributes)),
        mark_safe(poster_attr),
        src
    )

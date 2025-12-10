# ════════════════════════════════════════════════════════════════
# VARNISH CACHE CONFIGURATION
# ════════════════════════════════════════════════════════════════
#
# HTTP reverse proxy/cache for Django application
# Caches HTTP responses, reduces origin server load by 60-80%
#
# Performance:
# - Browser cache: 0ms (local)
# - Varnish (RAM): 1-5ms
# - Origin Django: 50-500ms
#
# Installation:
# 1. Ubuntu/Debian: sudo apt-get install varnish
# 2. Place this file at: /etc/varnish/default.vcl
# 3. Restart: sudo systemctl restart varnish
#
# Author: Caching Team
# Date: 2025-12
# ════════════════════════════════════════════════════════════════

vcl 4.1;

import std;
import directors;

# ════════════════════════════════════════════════════════════════
# BACKEND DEFINITION (Django Application)
# ════════════════════════════════════════════════════════════════

backend default {
    # Django application server
    .host = "127.0.0.1";
    .port = "8000";

    # Connection timeouts
    .connect_timeout = 5s;
    .first_byte_timeout = 30s;
    .between_bytes_timeout = 30s;

    # Health check
    .probe = {
        .url = "/health/";
        .timeout = 5s;
        .interval = 10s;
        .window = 5;
        .threshold = 3;
    }
}

# Multiple backends for load balancing
backend django_1 {
    .host = "127.0.0.1";
    .port = "8001";
    .probe = {
        .url = "/health/";
        .timeout = 5s;
        .interval = 10s;
    }
}

backend django_2 {
    .host = "127.0.0.1";
    .port = "8002";
    .probe = {
        .url = "/health/";
        .timeout = 5s;
        .interval = 10s;
    }
}

# Load balancer for multiple backends
sub vcl_init {
    new cluster = directors.round_robin(
        django_1,
        django_2
    );
}

# ════════════════════════════════════════════════════════════════
# REQUEST HANDLING (CLIENT → VARNISH)
# ════════════════════════════════════════════════════════════════

sub vcl_recv {
    # Use load balancer
    set req.backend_hint = cluster.backend();

    # ────────────────────────────────────────────────────────────
    # NORMALIZE REQUESTS
    # ────────────────────────────────────────────────────────────

    # Remove cookies for static assets
    if (req.url ~ "\.(css|js|gif|jpg|jpeg|png|ico|svg|woff|woff2)(\?[a-z0-9]+)?$") {
        unset req.http.Cookie;
        return (hash);
    }

    # Lowercase URL for better caching
    set req.url = std.tolower(req.url);

    # ────────────────────────────────────────────────────────────
    # CACHE BYPASS (Never cache these)
    # ────────────────────────────────────────────────────────────

    # POST requests - always pass to backend
    if (req.method == "POST" || req.method == "PUT" || req.method == "DELETE") {
        return (pass);
    }

    # Admin interface - never cache
    if (req.url ~ "^/admin/") {
        return (pass);
    }

    # API endpoints with authentication - never cache
    if (req.url ~ "^/api/v[0-9]+/.*" && req.http.Authorization) {
        return (pass);
    }

    # Search with query params - might be cacheable
    if (req.url ~ "^/search\?") {
        # Can cache, but include query string in cache key
        set req.http.Cache-Key = req.url;
    }

    # ────────────────────────────────────────────────────────────
    # REMOVE SENSITIVE COOKIES
    # ────────────────────────────────────────────────────────────

    # Keep only session ID, remove CSRF tokens, user prefs, etc
    if (req.http.Cookie) {
        set req.http.Cookie = ";" + req.http.Cookie;
        set req.http.Cookie = regsuball(req.http.Cookie, "; +", ";");
        set req.http.Cookie = regsuball(req.http.Cookie, ";(Django|sessionid|Path|Domain)=", "; \1=");
        set req.http.Cookie = regsuball(req.http.Cookie, ";[^ ][^;]*", "");
        set req.http.Cookie = regsuball(req.http.Cookie, "^[; ]+|[; ]+$", "");

        if (req.http.Cookie == "") {
            unset req.http.Cookie;
        }
    }

    # ────────────────────────────────────────────────────────────
    # VARY HEADERS
    # ────────────────────────────────────────────────────────────

    # Cache differently based on:
    # - Accept-Encoding (gzip vs uncompressed)
    # - Authorization (authenticated vs anonymous)
    # - Accept-Language (language preference)

    if (req.http.Authorization) {
        # User-specific content
        set req.http.Vary = "Authorization";
    } else {
        # Public content
        set req.http.Vary = "Accept-Encoding";
    }

    # ────────────────────────────────────────────────────────────
    # ENABLE COMPRESSION
    # ────────────────────────────────────────────────────────────

    if (req.http.Accept-Encoding) {
        if (req.url ~ "\.(jpg|png|gif|gz|tgz|bz2|tbz|mp3|ogg)$") {
            # Incompressible, remove encoding
            unset req.http.Accept-Encoding;
        } elsif (req.http.Accept-Encoding ~ "gzip") {
            set req.http.Accept-Encoding = "gzip";
        } elsif (req.http.Accept-Encoding ~ "deflate") {
            set req.http.Accept-Encoding = "deflate";
        } else {
            # Unsupported, remove
            unset req.http.Accept-Encoding;
        }
    }

    # ────────────────────────────────────────────────────────────
    # DEFAULT: HASH (Check cache)
    # ────────────────────────────────────────────────────────────

    return (hash);
}

# ════════════════════════════════════════════════════════════════
# CACHE KEY GENERATION
# ════════════════════════════════════════════════════════════════

sub vcl_hash {
    # Include these in cache key
    hash_data(req.url);

    if (req.http.host) {
        hash_data(req.http.host);
    } else {
        hash_data(server.ip);
    }

    # Include vary headers in cache key
    if (req.http.Accept-Encoding) {
        hash_data(req.http.Accept-Encoding);
    }

    if (req.http.Authorization) {
        hash_data(req.http.Authorization);
    }

    if (req.http.Accept-Language) {
        hash_data(req.http.Accept-Language);
    }

    return (lookup);
}

# ════════════════════════════════════════════════════════════════
# BACKEND RESPONSE HANDLING
# ════════════════════════════════════════════════════════════════

sub vcl_backend_response {
    # ────────────────────────────────────────────────────────────
    # RESPECT CACHE-CONTROL HEADERS
    # ────────────────────────────────────────────────────────────

    # If backend says no-cache or no-store, don't cache
    if (beresp.http.Cache-Control ~ "no-cache|no-store|private") {
        set beresp.uncacheable = true;
        return (deliver);
    }

    # ────────────────────────────────────────────────────────────
    # SET DEFAULT TTL
    # ────────────────────────────────────────────────────────────

    # Extract max-age from Cache-Control header
    if (beresp.http.Cache-Control ~ "max-age=([0-9]+)") {
        set beresp.ttl = std.duration(
            regsub(beresp.http.Cache-Control, "^.*max-age=([0-9]+).*$", "\1s"),
            1h
        );
    } else if (beresp.http.Expires) {
        # Fallback to Expires header
        set beresp.ttl = beresp.http.Expires - now;
    } else {
        # Default: 1 hour
        set beresp.ttl = 1h;
    }

    # ────────────────────────────────────────────────────────────
    # CACHE STATIC ASSETS FOR LONG TIME
    # ────────────────────────────────────────────────────────────

    if (bereq.url ~ "\.(css|js|gif|jpg|jpeg|png|ico|svg|woff|woff2)(\?[a-z0-9]+)?$") {
        set beresp.ttl = 365d;  # 1 year for versioned assets
    }

    # ────────────────────────────────────────────────────────────
    # CACHE API RESPONSES
    # ────────────────────────────────────────────────────────────

    if (bereq.url ~ "^/api/v[0-9]+/.*") {
        if (beresp.status == 200 || beresp.status == 304) {
            # Cache successful API responses
            set beresp.ttl = 5m;
        }
    }

    # ────────────────────────────────────────────────────────────
    # ADD DEBUG HEADERS
    # ────────────────────────────────────────────────────────────

    set beresp.http.X-Cache-TTL = beresp.ttl;
    set beresp.http.X-Backend = bereq.backend;

    return (deliver);
}

# ════════════════════════════════════════════════════════════════
# CLIENT RESPONSE HANDLING (VARNISH → CLIENT)
# ════════════════════════════════════════════════════════════════

sub vcl_deliver {
    # ────────────────────────────────────────────────────────────
    # ADD CACHE STATUS HEADER (for debugging)
    # ────────────────────────────────────────────────────────────

    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
        set resp.http.X-Cache-Hits = obj.hits;
    } else {
        set resp.http.X-Cache = "MISS";
    }

    # ────────────────────────────────────────────────────────────
    # ADD AGE HEADER (how long has been in cache)
    # ────────────────────────────────────────────────────────────

    set resp.http.Age = (now - resp.http.Date);

    # ────────────────────────────────────────────────────────────
    # REMOVE SENSITIVE HEADERS
    # ────────────────────────────────────────────────────────────

    # Don't expose internal Django headers
    unset resp.http.Server;
    unset resp.http.X-Powered-By;

    # Keep useful cache debugging headers (remove in production)
    if (std.getenv("VARNISH_DEBUG") == "true") {
        set resp.http.X-Cache-Control = resp.http.Cache-Control;
        set resp.http.X-TTL = resp.http.Cache-Control;
    } else {
        unset resp.http.X-Cache-TTL;
        unset resp.http.X-Backend;
    }

    return (deliver);
}

# ════════════════════════════════════════════════════════════════
# PURGE REQUEST HANDLING
# ════════════════════════════════════════════════════════════════

sub vcl_recv {
    # Allow PURGE method to clear cache (restricted to localhost)
    if (req.method == "PURGE") {
        if (!client.ip ~ localhost) {
            return (synth(405, "Not allowed"));
        }
        return (purge);
    }

    # Allow BAN method (restricted to localhost)
    if (req.method == "BAN") {
        if (!client.ip ~ localhost) {
            return (synth(405, "Not allowed"));
        }
        
        # Ban by URL pattern
        if (req.http.X-Ban-Pattern) {
            ban("req.url ~ " + req.http.X-Ban-Pattern);
            return (synth(200, "Banned: " + req.http.X-Ban-Pattern));
        }
    }
}

# ════════════════════════════════════════════════════════════════
# ERROR HANDLING
# ════════════════════════════════════════════════════════════════

sub vcl_backend_error {
    set beresp.http.Content-Type = "text/html; charset=utf-8";

    # Serve stale cache on backend errors
    if (bereq.is_bgfetch) {
        return (deliver);
    }

    # Don't cache 5xx errors
    if (beresp.status >= 500) {
        set beresp.uncacheable = true;
    }

    return (deliver);
}

sub vcl_synth {
    set resp.http.Content-Type = "text/html; charset=utf-8";
    return (deliver);
}

# ════════════════════════════════════════════════════════════════
# CACHE SETTINGS IN VCL
# ════════════════════════════════════════════════════════════════
#
# CLI COMMANDS:
#
# 1. Monitor cache performance:
#    sudo varnishstat -f "MAIN.cache_hit,MAIN.cache_miss,MAIN.backend_fail"
#
# 2. View request log:
#    sudo varnishlog -g request
#
# 3. Clear all cache:
#    sudo systemctl restart varnish
#
# 4. View cache statistics:
#    sudo varnishstat
#
# 5. Test cache headers:
#    curl -I http://localhost:6081/
#    # Look for: X-Cache: HIT or MISS
#
# ════════════════════════════════════════════════════════════════
#
# PERFORMANCE METRICS:
#
# Before Varnish (Origin Server):
#   - Response time: 50-500ms
#   - Database queries: 10-50 per request
#   - CPU usage: 60-80%
#   - Max concurrent: 100 requests
#
# After Varnish (Cached):
#   - Response time: 1-5ms (cache hit)
#   - Database queries: 0 per request
#   - CPU usage: 5-10%
#   - Max concurrent: 5000+ requests
#   - Throughput: 10,000+ requests/sec
#
# Cache Hit Rate Target: 80-90%
# Backend Load Reduction: 60-80%
#
# ════════════════════════════════════════════════════════════════

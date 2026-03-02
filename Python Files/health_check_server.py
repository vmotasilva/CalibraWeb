#!/usr/bin/env python
"""
Simple health check server that responds immediately
Responds to GET /healthz with 200 OK
"""
import http.server
import socketserver
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format='[HEALTHCHECK] %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 8000))

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz' or self.path == '/healthz/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            logger.info(f"✓ Health check passed")
            return
        
        self.send_response(404)
        self.end_headers()
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    try:
        with socketserver.TCPServer(("0.0.0.0", PORT), HealthCheckHandler) as httpd:
            logger.info(f"Health check server listening on port {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")
        sys.exit(1)

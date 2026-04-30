#!/usr/bin/env python
"""
Mock Redis Server for Development/Testing
Allows local development without Redis installation
"""

import socket
import threading
import time
from collections import defaultdict
import json
import sys

class MockRedisServer:
    """Simple Redis-compatible server for development"""
    
    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port
        self.data = {}
        self.server = None
        self.running = False
        
    def start(self):
        """Start the mock Redis server"""
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server.bind((self.host, self.port))
            self.server.listen(5)
            self.running = True
            
            print(f"\n{'='*60}")
            print(f"🔴 MOCK REDIS SERVER")
            print(f"{'='*60}")
            print(f"Host: {self.host}")
            print(f"Port: {self.port}")
            print(f"Status: ✅ RUNNING")
            print(f"\n⚠️  WARNING: This is a development mock server")
            print(f"   - Data NOT persisted between restarts")
            print(f"   - Single-threaded (no production use)")
            print(f"   - For development/testing only")
            print(f"\n💡 For production, use real Redis:")
            print(f"   - Docker: docker run -d -p 6379:6379 redis:latest")
            print(f"   - Cloud: AWS ElastiCache, Redis Cloud, etc.")
            print(f"\nPress Ctrl+C to stop")
            print(f"{'='*60}\n")
            
            while self.running:
                try:
                    client, addr = self.server.accept()
                    thread = threading.Thread(target=self.handle_client, args=(client, addr))
                    thread.daemon = True
                    thread.start()
                except KeyboardInterrupt:
                    self.stop()
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
                        
        except OSError as e:
            print(f"❌ ERROR: Could not bind to {self.host}:{self.port}")
            print(f"   Reason: {e}")
            print(f"\n   Solutions:")
            print(f"   1. Check if Redis is already running on port {self.port}")
            print(f"   2. Check if another application is using this port")
            print(f"   3. Try a different port: python mock_redis_server.py --port 6380")
            sys.exit(1)
    
    def handle_client(self, client, addr):
        """Handle client connections"""
        try:
            while self.running:
                # Read command
                data = client.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                
                # Parse RESP protocol (simplified)
                response = self.process_command(data)
                client.send(response.encode('utf-8'))
                
        except Exception as e:
            pass
        finally:
            client.close()
    
    def process_command(self, data):
        """Process Redis commands (simplified RESP protocol)"""
        try:
            # Handle PING
            if data.upper() == 'PING':
                return '+PONG\r\n'
            
            # Handle GET command
            if data.upper().startswith('GET '):
                key = data[4:].strip()
                value = self.data.get(key)
                if value is None:
                    return '$-1\r\n'  # Nil
                return f'${len(value)}\r\n{value}\r\n'
            
            # Handle SET command
            if data.upper().startswith('SET '):
                parts = data[4:].split(' ', 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ''
                self.data[key] = value
                return '+OK\r\n'
            
            # Handle DEL command
            if data.upper().startswith('DEL '):
                key = data[4:].strip()
                if key in self.data:
                    del self.data[key]
                    return ':1\r\n'
                return ':0\r\n'
            
            # Handle FLUSHALL command
            if data.upper() == 'FLUSHALL':
                self.data.clear()
                return '+OK\r\n'
            
            # Handle KEYS command (simplified)
            if data.upper().startswith('KEYS '):
                pattern = data[5:].strip()
                if pattern == '*':
                    keys = list(self.data.keys())
                    response = f'*{len(keys)}\r\n'
                    for key in keys:
                        response += f'${len(key)}\r\n{key}\r\n'
                    return response
                return '*0\r\n'
            
            # Handle EXPIRE command
            if data.upper().startswith('EXPIRE '):
                # Simplified: just return OK
                return ':1\r\n'
            
            # Handle EXISTS command
            if data.upper().startswith('EXISTS '):
                key = data[7:].strip()
                return ':1\r\n' if key in self.data else ':0\r\n'
            
            # Handle INCR command
            if data.upper().startswith('INCR '):
                key = data[5:].strip()
                current = int(self.data.get(key, 0))
                self.data[key] = str(current + 1)
                return f':{current + 1}\r\n'
            
            # Unknown command
            return '-ERR unknown command\r\n'
            
        except Exception as e:
            return f'-ERR {str(e)}\r\n'
    
    def stop(self):
        """Stop the server"""
        print("\n\n{'='*60}")
        print("🛑 Mock Redis Server stopping...")
        print(f"{'='*60}\n")
        self.running = False
        if self.server:
            self.server.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Mock Redis Server for Development')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=6379, help='Port to bind to')
    
    args = parser.parse_args()
    
    server = MockRedisServer(args.host, args.port)
    server.start()


if __name__ == '__main__':
    main()

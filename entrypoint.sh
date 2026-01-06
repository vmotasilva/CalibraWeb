#!/bin/bash
export PYTHONUNBUFFERED=1
PORT=${PORT:-8000}

echo "[STARTUP] Starting health check server on port $PORT..."
exec python health_check_server.py

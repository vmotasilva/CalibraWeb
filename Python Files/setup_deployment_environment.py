#!/usr/bin/env python
"""
Environment Configuration Script
Configura variáveis de ambiente para Staging/Produção
"""

import os
import json
from pathlib import Path


class EnvironmentConfigurator:
    """Configura ambiente para deployment"""
    
    ENVIRONMENTS = {
        'development': {
            'DEBUG': True,
            'SECURE_SSL_REDIRECT': False,
            'SESSION_COOKIE_SECURE': False,
            'CSRF_COOKIE_SECURE': False,
            'ALLOWED_HOSTS': ['localhost', '127.0.0.1'],
            'CACHE_ENABLE_L3': False,  # Redis optional in dev
            'LOG_LEVEL': 'DEBUG',
        },
        'staging': {
            'DEBUG': False,
            'SECURE_SSL_REDIRECT': True,
            'SESSION_COOKIE_SECURE': True,
            'CSRF_COOKIE_SECURE': True,
            'ALLOWED_HOSTS': ['staging.example.com', '*.staging.example.com'],
            'CACHE_ENABLE_L3': True,  # Redis required
            'LOG_LEVEL': 'INFO',
            'CACHE_DEFAULT_TIMEOUT': 3600,
            'L2_CACHE_MAX_SIZE': 1000,
        },
        'production': {
            'DEBUG': False,
            'SECURE_SSL_REDIRECT': True,
            'SESSION_COOKIE_SECURE': True,
            'CSRF_COOKIE_SECURE': True,
            'ALLOWED_HOSTS': ['api.example.com', '*.example.com'],
            'CACHE_ENABLE_L3': True,  # Redis required
            'LOG_LEVEL': 'WARNING',
            'CACHE_DEFAULT_TIMEOUT': 7200,
            'L2_CACHE_MAX_SIZE': 2000,
        },
    }
    
    @staticmethod
    def generate_env_file(environment: str, output_path: str = '.env'):
        """Generate .env file for environment"""
        
        if environment not in EnvironmentConfigurator.ENVIRONMENTS:
            raise ValueError(f"Unknown environment: {environment}")
        
        config = EnvironmentConfigurator.ENVIRONMENTS[environment]
        
        env_content = f"""# CalibraWeb Environment Configuration
# Environment: {environment.upper()}
# Generated automatically - modify as needed

# Django Settings
DEBUG={config['DEBUG']}
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS={','.join(config['ALLOWED_HOSTS'])}

# Security
SECURE_SSL_REDIRECT={config['SECURE_SSL_REDIRECT']}
SESSION_COOKIE_SECURE={config['SESSION_COOKIE_SECURE']}
CSRF_COOKIE_SECURE={config['CSRF_COOKIE_SECURE']}

# Database Configuration
DB_ENGINE=django.db.backends.postgresql
DB_HOST=localhost
DB_NAME=calibra_db
DB_USER=calibra_user
DB_PASSWORD=change-me
DB_PORT=5432

# Redis Configuration (CRITICAL for Fase 7)
REDIS_URL=redis://localhost:6379/1
CACHE_ENABLE_L3={config['CACHE_ENABLE_L3']}
CACHE_DEFAULT_TIMEOUT={config.get('CACHE_DEFAULT_TIMEOUT', 300)}
L2_CACHE_MAX_SIZE={config.get('L2_CACHE_MAX_SIZE', 1000)}

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_ACCEPT_CONTENT=json
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_TIMEZONE=America/Sao_Paulo

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True

# Logging
LOG_LEVEL={config['LOG_LEVEL']}
LOG_FILE=/var/log/calibra/application.log

# Cache Monitoring
CACHE_ALERT_EMAIL=admin@example.com
CACHE_ALERT_SLACK_WEBHOOK=https://hooks.slack.com/...

# AWS/Cloud Configuration (optional)
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_STORAGE_BUCKET_NAME=
# AWS_S3_REGION_NAME=us-east-1

# Sentry Configuration (optional)
# SENTRY_DSN=https://...@sentry.io/...

# DataDog Configuration (optional)
# DATADOG_API_KEY=
# DATADOG_APP_KEY=
"""
        
        with open(output_path, 'w') as f:
            f.write(env_content)
            
        print(f"✅ Generated .env file for {environment} at {output_path}")
        
    @staticmethod
    def generate_docker_compose(environment: str):
        """Generate docker-compose.yml for environment"""
        
        is_prod = environment == 'production'
        redis_persistence = "yes" if is_prod else "no"
        
        compose = f"""version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:14
    container_name: calibra-db-{environment}
    environment:
      POSTGRES_DB: calibra_db
      POSTGRES_USER: calibra_user
      POSTGRES_PASSWORD: ${{DB_PASSWORD}}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - calibra-network
    restart: always
    {'healthcheck:\n      test: ["CMD-SHELL", "pg_isready -U calibra_user"]\n      interval: 10s\n      timeout: 5s\n      retries: 5' if is_prod else ''}

  # Redis Cache (L3 Cache Layer)
  redis:
    image: redis:7-alpine
    container_name: calibra-redis-{environment}
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - calibra-network
    restart: always
    command: redis-server --appendonly {redis_persistence} --maxmemory 512mb --maxmemory-policy allkeys-lru
    {'healthcheck:\n      test: ["CMD", "redis-cli", "ping"]\n      interval: 10s\n      timeout: 5s\n      retries: 5' if is_prod else ''}

  # Django Application
  web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: calibra-web-{environment}
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
    environment:
      - DEBUG=False
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
    networks:
      - calibra-network
    restart: always

  # Celery Worker
  celery:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: calibra-celery-{environment}
    command: celery -A config worker -l info --concurrency=4
    environment:
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
    networks:
      - calibra-network
    restart: always

  # Celery Beat (Scheduler)
  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: calibra-beat-{environment}
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/1
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
    networks:
      - calibra-network
    restart: always

volumes:
  postgres-data:
  redis-data:
  static_volume:

networks:
  calibra-network:
    driver: bridge
"""
        
        filename = f"docker-compose.{environment}.yml"
        with open(filename, 'w') as f:
            f.write(compose)
            
        print(f"✅ Generated {filename}")
        
    @staticmethod
    def generate_nginx_config(environment: str):
        """Generate Nginx configuration"""
        
        if environment == 'production':
            ssl_config = """
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
"""
        else:
            ssl_config = "# SSL configuration for staging"
        
        nginx_config = f"""# Nginx Configuration for {environment}
# Include this in your main nginx.conf or use as standalone

upstream calibra_backend {{
    server 127.0.0.1:8000;
    keepalive 32;
}}

# Cache zones
proxy_cache_path /var/cache/nginx/calibra levels=1:2 keys_zone=calibra_cache:10m max_size=1g inactive=60m use_temp_path=off;
proxy_cache_path /var/cache/nginx/api levels=1:2 keys_zone=api_cache:5m max_size=500m inactive=30m use_temp_path=off;

server {{
    listen 80;
    server_name api.example.com;
    client_max_body_size 100M;

    # Include cache configuration (created in Fase 7)
    include /etc/nginx/conf.d/cache.conf;

{ssl_config}

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss;
    gzip_vary on;

    # Proxy settings
    location / {{
        proxy_pass http://calibra_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cache API responses
        proxy_cache api_cache;
        proxy_cache_valid 200 10m;
        proxy_cache_use_stale error timeout http_500 http_502 http_503 http_504;
        
        # Headers for cache
        add_header X-Cache-Status $upstream_cache_status;
    }}

    # Static files (never cache bust with versioning)
    location /static/ {{
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}

    # Health check
    location /health/ {{
        proxy_pass http://calibra_backend;
        access_log off;
    }}
}}
"""
        
        filename = f"nginx.{environment}.conf"
        with open(filename, 'w') as f:
            f.write(nginx_config)
            
        print(f"✅ Generated {filename}")
        
    @staticmethod
    def generate_systemd_services(environment: str):
        """Generate systemd service files"""
        
        services = {
            'calibra-web': f"""[Unit]
Description=CalibraWeb Django Application ({environment})
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=calibra
WorkingDirectory=/opt/calibra
Environment="PATH=/opt/calibra/.venv/bin"
ExecStart=/opt/calibra/.venv/bin/gunicorn \\
    config.wsgi:application \\
    --bind 0.0.0.0:8000 \\
    --workers 4 \\
    --timeout 120 \\
    --access-logfile /var/log/calibra/access.log \\
    --error-logfile /var/log/calibra/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""",
            'calibra-celery-worker': f"""[Unit]
Description=CalibraWeb Celery Worker ({environment})
After=network.target redis.service

[Service]
Type=forking
User=calibra
WorkingDirectory=/opt/calibra
Environment="PATH=/opt/calibra/.venv/bin"
ExecStart=/opt/calibra/.venv/bin/celery multi start \\
    worker \\
    -A config \\
    --pidfile=/var/run/calibra/celery-worker.pid \\
    --logfile=/var/log/calibra/celery-worker.log \\
    -l info \\
    --concurrency=4
ExecStop=/opt/calibra/.venv/bin/celery multi stopwait \\
    worker \\
    --pidfile=/var/run/calibra/celery-worker.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""",
            'calibra-celery-beat': f"""[Unit]
Description=CalibraWeb Celery Beat ({environment})
After=network.target redis.service

[Service]
Type=simple
User=calibra
WorkingDirectory=/opt/calibra
Environment="PATH=/opt/calibra/.venv/bin"
ExecStart=/opt/calibra/.venv/bin/celery -A config beat \\
    -l info \\
    --pidfile=/var/run/calibra/celery-beat.pid \\
    --logfile=/var/log/calibra/celery-beat.log \\
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        }
        
        for service_name, service_content in services.items():
            filename = f"{service_name}.service"
            with open(filename, 'w') as f:
                f.write(service_content)
            print(f"✅ Generated {filename}")


def main():
    """Main configuration wizard"""
    
    print("🔧 CalibraWeb Deployment Configuration")
    print("="*60)
    print("\nSelect environment:")
    print("1. Development")
    print("2. Staging")
    print("3. Production")
    
    choice = input("\nChoice (1-3): ").strip()
    
    env_map = {'1': 'development', '2': 'staging', '3': 'production'}
    environment = env_map.get(choice)
    
    if not environment:
        print("❌ Invalid choice")
        return
    
    print(f"\n📦 Configuring for {environment.upper()}...")
    
    try:
        # Generate configuration files
        EnvironmentConfigurator.generate_env_file(environment)
        EnvironmentConfigurator.generate_docker_compose(environment)
        EnvironmentConfigurator.generate_nginx_config(environment)
        EnvironmentConfigurator.generate_systemd_services(environment)
        
        print("\n✨ Configuration Complete!")
        print("\nNext steps:")
        print(f"1. Edit .env file with your specific values")
        print(f"2. Review docker-compose.{environment}.yml")
        print(f"3. Configure DNS/SSL certificates")
        print(f"4. Deploy with: docker-compose -f docker-compose.{environment}.yml up -d")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()

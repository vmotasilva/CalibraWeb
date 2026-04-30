# 📋 DEPLOYMENT GUIDE - Fase 7 Caching System

## 🎯 Visão Geral

Este documento descreve como fazer deploy do sistema de caching avançado (Fase 7) em ambiente de **staging** e **produção**.

---

## ✅ PRÉ-REQUISITOS

### Infraestrutura Necessária

```
✓ Python 3.9+
✓ PostgreSQL (ou banco de dados compatível)
✓ Redis 6.0+ (CRÍTICO para L3 cache)
✓ Celery Worker (para warming tasks)
✓ Celery Beat (para scheduler)
✓ Nginx ou Varnish (opcional, para HTTP cache)
```

### Dependências Python

```bash
pip install -r requirements.txt
```

**Novo em Fase 7:**
- Redis Client (redis>=4.0)
- Celery (já presente)
- Já configurado em requirements.txt

---

## 🚀 PHASE 1: DESENVOLVIMENTO/STAGING

### 1.1 Setup do Ambiente

```bash
# Ativar virtualenv
.venv/Scripts/Activate.ps1

# Instalar/atualizar dependências
pip install -r requirements.txt

# Migrações do banco (se houver)
python manage.py migrate
```

### 1.2 Configurar Redis

**Opção A: Docker (Recomendado)**
```bash
# Instalar Docker (se não tiver)
# https://www.docker.com/products/docker-desktop

# Rodar Redis
docker run -d -p 6379:6379 redis:latest --name calibra-redis

# Verificar
docker ps | findstr redis
```

**Opção B: Redis nativo (Windows)**
```bash
# Baixar Redis Windows
# https://github.com/microsoftarchive/redis/releases

# Instalar e iniciar Redis
redis-server.exe
```

**Opção C: Redis Cloud (Desenvolvimento)**
```bash
# Usar serviço gerenciado (Redis Cloud, ElastiCache, etc.)
# Configurar URL em settings.py

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://seu-host:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### 1.3 Configurar Celery

**Arquivo: `config/celery.py`** (já configurado)

```python
# Verificar configuração
from config.celery import app
app.autodiscover_tasks()
```

### 1.4 Testar Cache System

```bash
# Terminal 1: Iniciar Celery Worker
celery -A config worker -l info

# Terminal 2: Iniciar Celery Beat
celery -A config beat -l info

# Terminal 3: Rodar Django
python manage.py runserver

# Terminal 4: Monitor Dashboard
python manage.py cache_dashboard --live --interval 2
```

### 1.5 Validar Cada Componente

#### ✓ Test L1 Cache (Request-Scoped)
```bash
python manage.py shell
```
```python
from config.multilevel_cache import MultiLevelCacheManager

cache = MultiLevelCacheManager()
cache.set('test_key', 'test_value', 60)
print(cache.get('test_key'))  # Deve retornar 'test_value'
```

#### ✓ Test L2 Cache (Worker-Scoped)
```python
# Fazer 2 requests iguais - segunda deve usar L2 cache
import requests
requests.get('http://localhost:8000/api/instruments/')
requests.get('http://localhost:8000/api/instruments/')

# Verificar stats
python manage.py multilevel_cache_monitor --l2
```

#### ✓ Test L3 Cache (Redis Distributed)
```python
# Verificar conexão Redis
from django_redis import get_redis_connection
redis_conn = get_redis_connection("default")
redis_conn.ping()  # Deve retornar True
```

#### ✓ Test Cache Invalidation
```python
from qms.models import Instrument
from config.cache_invalidation import initialize_cache_invalidation

# Inicializar signals
initialize_cache_invalidation()

# Criar e modificar instrumento - deve invalidar cache automaticamente
inst = Instrument.objects.first()
inst.descricao = 'Updated'
inst.save()  # Triggers invalidation
```

#### ✓ Test Cache Warming
```bash
# Executar warm tasks
celery -A config call qms.cache_warming_tasks.warm_hot_items
celery -A config call qms.cache_warming_tasks.analyze_access_patterns

# Verificar estatísticas
python manage.py cache_warming_monitor
```

#### ✓ Test Dashboard
```bash
# Modo live
python manage.py cache_dashboard --live

# Stats
python manage.py cache_dashboard --stats

# JSON output
python manage.py cache_dashboard --json
```

### 1.6 Rodar Testes Unitários

```bash
# Testes básicos (sem Redis)
python manage.py test qms --verbosity=2

# Testes de cache (com Redis)
python manage.py test qms.tests.CacheTests -v 2
```

**Resultado esperado:**
```
Found 94 test(s).
OK (94 passed)
```

---

## 📊 PHASE 2: STAGING DEPLOYMENT

### 2.1 Preparar Staging Server

```bash
# SSH para servidor staging
ssh user@staging.example.com

# Clonar repositório
git clone https://github.com/vmotasilva/CalibraWeb.git
cd CalibraWeb

# Criar virtualenv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\Activate.ps1  # Windows

# Instalar dependências
pip install -r requirements.txt
pip install gunicorn whitenoise
```

### 2.2 Setup Redis em Staging

```bash
# Usando Docker (recomendado)
docker run -d \
  -p 6379:6379 \
  --name redis-staging \
  -v redis-data:/data \
  redis:latest \
  redis-server --appendonly yes

# Ou usando managed service (AWS ElastiCache, etc.)
```

### 2.3 Configurar Variáveis de Ambiente

**Arquivo: `.env` (staging)**
```bash
# Database
DB_HOST=staging-db.example.com
DB_USER=calibra_user
DB_PASSWORD=secure_password

# Redis
REDIS_URL=redis://staging-redis:6379/1

# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=staging.example.com

# Email (para alertas)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@example.com
EMAIL_HOST_PASSWORD=email_password

# Slack (opcional, para alertas)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### 2.4 Rodar Migrations

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 2.5 Iniciar Serviços

**Script: `start_staging.sh`**
```bash
#!/bin/bash
set -e

cd /opt/calibra

# Ativar venv
source .venv/bin/activate

# Redis
docker start redis-staging || true

# Gunicorn (Django)
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - &

# Celery Worker
celery -A config worker \
  -l info \
  --concurrency=4 \
  -f /var/log/celery/worker.log &

# Celery Beat
celery -A config beat \
  -l info \
  -f /var/log/celery/beat.log &

echo "Staging services started"
```

### 2.6 Monitoramento em Staging

```bash
# Terminal 1: Dashboard live
python manage.py cache_dashboard --live --interval 5

# Terminal 2: Monitor de alertas
python manage.py cache_dashboard --alerts --watch

# Terminal 3: Logs do Celery
tail -f /var/log/celery/worker.log
```

### 2.7 Testes de Carga (Staging)

```bash
# Instalar ab (Apache Bench) ou usar locust
pip install locust

# Executar teste de carga
locust -f tests/load_test.py --host=https://staging.example.com
```

**Esperado:**
- ✅ Hit rate: 85-95%
- ✅ Response time cached: <5ms
- ✅ Response time uncached: 50-200ms
- ✅ CPU: <30%
- ✅ Memory: <500MB

### 2.8 Validação Final

**Checklist de Staging:**
- [ ] Redis conectando
- [ ] Celery Worker rodando
- [ ] Celery Beat agendando tasks
- [ ] Dashboard mostrando métricas
- [ ] Alertas funcionando
- [ ] Cache hit rate > 80%
- [ ] Nenhum erro nos logs
- [ ] Testes passando
- [ ] Performance aceitável

---

## 🌍 PHASE 3: PRODUCTION DEPLOYMENT

### 3.1 Preparar Produção

```bash
# SSH para servidor produção
ssh deploy@prod.example.com

# Clonar repositório
git clone --branch main https://github.com/vmotasilva/CalibraWeb.git
cd CalibraWeb

# Criar virtualenv
python -m venv .venv
source .venv/bin/activate

# Instalar dependências (production)
pip install -r requirements.txt
pip install gunicorn whitenoise psycopg2-binary
```

### 3.2 Setup Redis em Produção

**RECOMENDAÇÃO: Use serviço gerenciado**

```bash
# AWS ElastiCache
REDIS_URL=redis://calibra-cache.xxxxx.ng.0001.use1.cache.amazonaws.com:6379/0

# Google Cloud Memorystore
REDIS_URL=redis://10.0.0.3:6379/0

# Azure Cache for Redis
REDIS_URL=redis://calibra-cache.redis.cache.windows.net:6380/0?ssl=True

# DigitalOcean Managed Database
REDIS_URL=redis://default:password@...ondigitalocean.com:25061/0
```

### 3.3 Configurar Produção

**Arquivo: `.env` (production)**
```bash
# Database (managed, high-availability)
DB_HOST=prod-db-rw.example.com
DB_USER=calibra_prod
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id calibra/db/password)

# Redis (managed)
REDIS_URL=redis://prod-cache.xxxxx.cache.amazonaws.com:6379/0

# Django
SECRET_KEY=$(aws secretsmanager get-secret-value --secret-id calibra/django/secret-key)
DEBUG=False
ALLOWED_HOSTS=api.example.com,*.example.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Email (para alertas críticos)
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=$(aws secretsmanager get-secret-value --secret-id calibra/sendgrid/key)

# Monitoring (Sentry, DataDog, etc.)
SENTRY_DSN=https://...@sentry.io/...
DATADOG_API_KEY=...

# Slack (alertas críticos)
SLACK_WEBHOOK_URL=$(aws secretsmanager get-secret-value --secret-id calibra/slack/webhook)
```

### 3.4 Blue-Green Deployment (Recomendado)

```bash
# BLUE environment (current production)
# GREEN environment (nova versão)

# Rodar migrations em GREEN
.venv/bin/python manage.py migrate --database=green

# Testar GREEN
.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001

# Verificar saúde
curl -s http://127.0.0.1:8001/health/

# Switch traffic BLUE → GREEN
# (via load balancer ou DNS)

# Se problema, rollback: BLUE ← GREEN
```

### 3.5 Setup Docker (Alternativa)

**Dockerfile (já existe)**
```dockerfile
FROM python:3.11

WORKDIR /app

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Migrations
RUN python manage.py migrate --noinput

# Collect static
RUN python manage.py collectstatic --noinput

# Comando padrão
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**Deploy com Docker:**
```bash
# Build image
docker build -t calibra:latest .

# Push para registry
docker tag calibra:latest myregistry/calibra:latest
docker push myregistry/calibra:latest

# Deploy em produção
kubectl set image deployment/calibra \
  calibra=myregistry/calibra:latest
```

### 3.6 Reverse Proxy (HTTP Caching)

**Nginx (recomendado)**
```bash
# Include arquivo de cache (já criado em Fase 7)
include /etc/nginx/conf.d/cache.conf;

# Verificar
nginx -t
nginx -s reload
```

**Varnish (alternativa)**
```bash
# Start Varnish
varnishd -f /etc/varnish/default.vcl -s malloc,256m -T 127.0.0.1:6082

# Monitorar
varnishstat -1
```

### 3.7 Monitoramento em Produção (24/7)

```bash
# Terminal 1: Dashboard (persistente)
nohup python manage.py cache_dashboard --live --interval 10 > dashboard.log 2>&1 &

# Terminal 2: Alertas críticos
python manage.py cache_dashboard --alerts --severity=critical

# Terminal 3: Logs estruturados (ELK, CloudWatch, etc.)
tail -f /var/log/calibra/application.log
```

### 3.8 Alertas em Produção

**Configurar notificações para:**
- ❌ Redis down (crítico)
- ❌ Hit rate < 70% (aviso)
- ❌ Memory > 80% (aviso)
- ⚠️ Celery tasks falhando (crítico)
- ⚠️ Database slow queries (aviso)

```python
# config/settings.py

CACHE_ALERTS = {
    'redis_down': {'severity': 'critical', 'notify': ['email', 'slack']},
    'low_hit_rate': {'severity': 'warning', 'notify': ['email']},
    'high_memory': {'severity': 'warning', 'notify': ['email']},
    'celery_failures': {'severity': 'critical', 'notify': ['email', 'slack']},
}
```

### 3.9 Performance Targets

**Após deployment, esperar:**

| Métrica | Antes | Depois | Target |
|---------|-------|--------|--------|
| Cache Hit Rate | 0% | 85-95% | ✅ |
| Response Time (cached) | - | <5ms | ✅ |
| Response Time (uncached) | 500ms | 50-200ms | ✅ |
| Database Queries | 100% | 5-10% | ✅ |
| Server CPU | 80%+ | <20% | ✅ |
| Server Memory | 80%+ | <40% | ✅ |
| Throughput | 100 req/s | 10,000+ req/s | ✅ |
| **Overall Speed** | 1x | **90x** | ✅ |

### 3.10 Rollback Plan

```bash
# Se houver problemas críticos:

# 1. Detectar problema
python manage.py cache_dashboard --health

# 2. Parar Celery (evitar mudanças)
kill $(pgrep -f "celery worker")
kill $(pgrep -f "celery beat")

# 3. Rollback código
git checkout HEAD~1
python manage.py collectstatic --noinput

# 4. Reiniciar serviços
systemctl restart calibra
systemctl restart celery-worker
systemctl restart celery-beat

# 5. Verificar saúde
curl https://api.example.com/health/
python manage.py cache_dashboard --health
```

---

## 🔧 TROUBLESHOOTING

### Redis Down
```bash
# Verificar status
redis-cli ping

# Restart
systemctl restart redis
# ou
docker restart redis-staging
```

### Celery Not Processing
```bash
# Verificar worker
celery -A config inspect active

# Reiniciar
pkill -f "celery worker"
celery -A config worker -l info
```

### Low Hit Rate
```bash
# Verificar padrões
python manage.py cache_warming_monitor

# Aumentar warming frequency
# Editar qms/cache_warming_tasks.py
```

### High Memory Usage
```bash
# Reduzir L2 cache size
# config/multilevel_cache.py → L2_MAX_SIZE = 500 (era 1000)

# Limpat cache antigo
python manage.py cache_purge --all
```

### Slow Database Queries
```bash
# Analisar queries lentas
python manage.py shell_plus
from django.db import connection
from django.test.utils import override_settings

# Rodar query lenta
list(Instrument.objects.all())

# Ver SQL
print(connection.queries)
```

---

## 📈 MONITORING CONTÍNUO

### Diário
- [ ] Hit rate > 80%
- [ ] Response times < 5ms (cached)
- [ ] Nenhum erro crítico

### Semanal
- [ ] Revisar trends
- [ ] Ajustar TTLs se necessário
- [ ] Analisar padrões de acesso

### Mensal
- [ ] Performance review
- [ ] Otimizar warming schedule
- [ ] Atualizar cache estratégia

---

## ✨ CHECKLIST FINAL

**Antes de ir para Produção:**
- [ ] Todos testes passam (94/94)
- [ ] Redis rodando e acessível
- [ ] Celery Worker ativo
- [ ] Celery Beat agendando
- [ ] Dashboard mostrando métricas
- [ ] Alertas configurados
- [ ] Hit rate > 80% em staging
- [ ] Response time < 5ms (cached)
- [ ] Plano de rollback documentado
- [ ] Time treinado
- [ ] Backup do banco realizado

---

## 🎯 PRÓXIMOS PASSOS

1. **Hoje**: Completar Staging (validar cada componente)
2. **Amanhã**: Deploy em Produção (blue-green)
3. **Semana 1**: Monitoramento intensivo 24/7
4. **Semana 2+**: Otimizações baseadas em dados reais

---

**Status: 🟢 PRONTO PARA DEPLOYMENT**

Para dúvidas, consulte:
- 📄 `MULTILEVEL_CACHE.md` (arquitetura cache)
- 📄 `CACHE_INVALIDATION.md` (invalidação)
- 📄 `CACHE_WARMING.md` (warming)
- 📄 `CACHE_DASHBOARD.md` (monitoramento)
- 📄 `HTTPCACHE.md` (HTTP cache)
- 📄 `FASE_7_SUMMARY.md` (visão geral)

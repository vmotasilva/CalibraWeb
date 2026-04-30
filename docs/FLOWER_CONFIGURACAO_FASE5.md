## Flower Configuration Guide - Fase 5

**Status:** ✅ CONFIGURADO

**Data:** 9 de Dezembro de 2025

---

## 📊 O que é Flower?

Flower é um **dashboard web em tempo real** para monitorar e gerenciar tarefas Celery. Permite visualizar:

- ✅ Tasks em execução, pendentes e concluídas
- ✅ Workers online/offline
- ✅ Histórico de execução
- ✅ Performance metrics
- ✅ Alertas de falhas
- ✅ Gerenciamento de filas
- ✅ API REST para automação

---

## 🚀 Instalação

### 1. Instalar Flower
```bash
pip install flower==2.0.1
```

Ou via requirements.txt (já adicionado):
```bash
pip install -r requirements.txt
```

### 2. Verificar Instalação
```bash
celery --version
flower --version
```

---

## 🔧 Configuração

### Arquivo: `config/flower_config.py`

Criado com as seguintes configurações:

```python
# Porta padrão
port = 5555

# Autenticação (via env)
FLOWER_USERNAME = seu_usuario
FLOWER_PASSWORD = sua_senha

# Logging
FLOWER_LOG_LEVEL = info

# Database
FLOWER_DB = flower.db (SQLite)

# Broker
CELERY_BROKER_URL = redis://...

# Segurança
show_task_args = false (não mostrar dados sensíveis)
hide_task_args = true

# Performance
max_tasks = 10000
worker_offline_threshold = 60s
```

---

## 🎯 Como Usar

### Desenvolvimento Local

#### Terminal 1: Django
```bash
python manage.py runserver 0.0.0.0:8000
```

#### Terminal 2: Celery Worker
```bash
celery -A config worker -l info
```

#### Terminal 3: Celery Beat
```bash
celery -A config beat -l info
```

#### Terminal 4: Flower
```bash
# Opção A: Com script
bash start-flower.sh

# Opção B: Direto
celery -A config flower --port=5555

# Opção C: Com configuração customizada
celery -A config flower --config=config.flower_config
```

Acesse: **http://localhost:5555**

---

## 📱 Interface do Flower

### Home/Dashboard
```
┌──────────────────────────────────────────────┐
│                   FLOWER                      │
├──────────────────────────────────────────────┤
│                                               │
│  📊 STATS                                     │
│  ├─ Workers: 1 online                        │
│  ├─ Tasks: 42 total, 2 running, 5 pending    │
│  └─ Success Rate: 98.5%                      │
│                                               │
│  📈 BROKER CAPACITY                          │
│  ├─ Redis: 127.0.0.1:6379                   │
│  └─ Connections: 5/10                        │
│                                               │
│  🔄 RECENT TASKS                             │
│  ├─ [SUCCESS] export_instrumentos (2.3s)    │
│  ├─ [SUCCESS] send_daily_report (1.5s)      │
│  └─ [PENDING] cleanup_old_exports            │
│                                               │
└──────────────────────────────────────────────┘
```

### Páginas Principais

#### 1. **Workers** (`/workers`)
```
├─ celery@hostname
│  ├─ Status: Online
│  ├─ Concurrency: 4
│  ├─ Pool: prefork
│  ├─ Uptime: 2 days 3 hours
│  ├─ Tasks: 127 processed
│  └─ Queues: default, exports, emails
```

#### 2. **Tasks** (`/tasks`)
```
├─ export_instrumentos
│  ├─ Received: 0
│  ├─ Started: 23
│  ├─ Succeeded: 23
│  ├─ Failed: 0
│  ├─ Retried: 0
│  └─ Success Rate: 100%
│
├─ send_daily_report
│  ├─ Received: 7
│  ├─ Started: 7
│  ├─ Succeeded: 6
│  ├─ Failed: 1 (retry scheduled)
│  └─ Success Rate: 85.7%
```

#### 3. **Real-time** (`/monitor`)
- Atualização ao vivo (WebSocket)
- Task queue status
- Worker load

#### 4. **Task Details** (`/task/<task_id>`)
```
Task: export_instrumentos
Status: SUCCESS
Runtime: 2.34 seconds
Returned: File saved to /exports/instrumentos_2025-12-09.xlsx
Args: (20, ['Excel'])
```

#### 5. **API** (`/api/*`)
- REST endpoints para programação
- Exemplo: `GET /api/tasks?limit=10`

---

## 🔐 Segurança

### 1. Autenticação Básica

Definir variáveis de ambiente:
```bash
export FLOWER_USERNAME=admin
export FLOWER_PASSWORD=seu_senha_forte
```

Flower pedirá login antes de acessar o dashboard.

### 2. SSL/TLS em Produção

```bash
# Gerar certificado auto-assinado
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# Usar em Flower
celery -A config flower \
    --certfile=cert.pem \
    --keyfile=key.pem
```

### 3. Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name flower.seu-dominio.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Limitar Acesso

```python
# Em config/flower_config.py
# Permitir apenas certos IPs
allowed_ips = ['127.0.0.1', '192.168.1.100']
```

---

## 📊 Monitoramento em Produção

### Railway Deployment

#### 1. Variáveis de Ambiente
```
FLOWER_PORT=5555
FLOWER_USERNAME=admin
FLOWER_PASSWORD=sua_senha
FLOWER_LOG_LEVEL=info
CELERY_BROKER_URL=redis://redis-url
```

#### 2. Procfile
```
web: bash start.sh
worker: bash start-worker.sh
beat: bash start-beat.sh
flower: celery -A config flower --port=${PORT:-5555}
```

#### 3. Acessar Flower
```
https://seu-railway-url.up.railway.app/flower
```

---

## 🔔 Alertas & Notificações

### Email Alerts (Opcional)

Ativar alertas de falha:
```bash
export FLOWER_EMAIL_ON_FAILURE=true
export FLOWER_ALERT_EMAIL=seu_email@example.com
```

Flower enviará email quando uma task falhar.

### Webhook Customizado

Para integração com Slack/Discord:

```python
# qms/tasks.py
from celery import current_task

@shared_task(bind=True)
def my_task(self):
    try:
        # ... código ...
        return "Sucesso"
    except Exception as e:
        # Enviar para Slack
        import requests
        requests.post('https://hooks.slack.com/...', json={
            'text': f'Task {self.name} falhou: {str(e)}'
        })
        raise
```

---

## 📈 Métricas Úteis

### Ver em Flower

1. **Task Success Rate**
   - Percentage de tasks que completaram com sucesso
   - Target: > 95%

2. **Average Task Duration**
   - Tempo médio de execução
   - Target: < 5 segundos para exports

3. **Queue Depth**
   - Quantas tasks estão aguardando
   - Target: < 100 (evitar backlog)

4. **Worker Load**
   - CPU/Memory por worker
   - Escalabilidade automática se > 80%

### API para Monitoração

```bash
# Tasks em fila
curl http://localhost:5555/api/tasks?status=PENDING

# Workers online
curl http://localhost:5555/api/workers

# Estatísticas
curl http://localhost:5555/api/stats

# Task específica
curl http://localhost:5555/api/tasks/task-uuid
```

---

## 🐛 Troubleshooting

### Problema: Flower não conecta ao Broker
```
Solution:
1. Verificar se Redis está rodando
2. Verificar CELERY_BROKER_URL
3. Verificar firewall/porta 6379
```

### Problema: Dashboard lento
```
Solution:
1. Reduzir FLOWER_MAX_TASKS (padrão 10000)
2. Limpar database: flower --purge
3. Aumentar worker processes
```

### Problema: Tasks não aparecem
```
Solution:
1. Verificar se worker está rodando
2. Verificar logs: celery -A config events
3. Verificar queue: celery -A config inspect active
```

### Problema: Autenticação não funciona
```
Solution:
1. Usar aspas nas variáveis:
   export FLOWER_PASSWORD="senha_com_espaço"
2. URL encode: senha@123 → senha%40123
3. Reiniciar Flower
```

---

## 🚀 Start/Stop Flower

### Local Development

```bash
# Iniciar
celery -A config flower

# Parar
# Ctrl + C

# Em background
celery -A config flower &

# Fechar background
kill %1
```

### Production (Systemd)

```bash
# Criar arquivo: /etc/systemd/system/flower.service
[Unit]
Description=Flower for Celery
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/calibraweb
ExecStart=/usr/local/bin/celery -A config flower --port=5555

[Install]
WantedBy=multi-user.target

# Habilitar e iniciar
sudo systemctl enable flower
sudo systemctl start flower

# Ver status
sudo systemctl status flower

# Logs
sudo journalctl -u flower -f
```

### Production (Docker)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5555
CMD ["celery", "-A", "config", "flower", "--port=5555"]
```

---

## 📚 Documentação Adicional

- **Flower Official:** https://flower.readthedocs.io/
- **Celery Tasks:** https://docs.celeryproject.io/
- **Task Monitoring:** https://docs.celeryproject.io/en/stable/userguide/monitoring/

---

## ✅ Próximos Passos

1. ✅ Instalar Flower (pip install flower)
2. ✅ Configurar config/flower_config.py
3. ✅ Atualizar Procfile
4. ✅ Testar localmente
5. 🟡 Deploy em Railway
6. 🟡 Configurar autenticação
7. 🟡 Configurar reverse proxy
8. 🟡 Setup alertas de email

---

## 🎯 Sumário

**Flower fornece:**
- ✅ Visualização em tempo real de tasks
- ✅ Monitoramento de workers
- ✅ Histórico de execução
- ✅ Alertas de falhas
- ✅ API REST
- ✅ Dashboard web responsivo
- ✅ Autenticação & segurança

**Instalação:**
- ✅ Adicionado ao requirements.txt
- ✅ Procfile configurado
- ✅ Script start-flower.sh criado
- ✅ Configuração avançada em config/flower_config.py

**Status:** ✅ **PRONTO PARA USAR**

---

*Data: 9 de Dezembro de 2025*  
*Status: ✅ CONFIGURADO*  
*Próximo: Deploy em Railway*

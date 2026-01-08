# Exemplo de Configuração de Variáveis no Railway

Este arquivo mostra EXATAMENTE como as variáveis devem estar configuradas.

## CENÁRIO: Você tem 3 serviços no Railway

```
Projeto: CalibraWeb
├── postgres-service (PostgreSQL)
├── redis-service (Redis)
├── web-app (CalibraWeb - Gunicorn)
└── celery-beat (Celery Beat - NOVO)
```

## PASSO 1: Obter URLs dos Serviços

### PostgreSQL

1. Clique em "postgres-service"
2. Vá para "Connect" tab
3. Procure por "DATABASE_URL" ou "PostgreSQL"
4. Você verá algo como:
   ```
   postgresql://postgres:NomMqAKjy2kNj5E@railway.railway.internal:5432/railway
   ```
5. **Copie EXATAMENTE** este valor

### Redis

1. Clique em "redis-service"
2. Vá para "Connect" tab
3. Procure por "REDIS_URL" ou "Redis"
4. Você verá algo como:
   ```
   redis://default:ZLl5Uz3K2xJ9qF4vB8nP@redis.railway.internal:6379
   ```
5. **Copie EXATAMENTE** este valor

## PASSO 2: Configurar Variáveis do Serviço WEB

1. Clique em "web-app"
2. Vá para "Variables" tab
3. Adicione as seguintes variáveis:

```
DJANGO_SETTINGS_MODULE
config.settings

SECRET_KEY
django-insecure-nA^@*KzX$9pL#mQ2vB^tR$%YuI&*oP(qW!eR@!tY!uI&*oP(

DEBUG
False

ALLOWED_HOSTS
*

DATABASE_URL
postgresql://postgres:NomMqAKjy2kNj5E@railway.railway.internal:5432/railway

REDIS_URL
redis://default:ZLl5Uz3K2xJ9qF4vB8nP@redis.railway.internal:6379

CELERY_BROKER_URL
redis://default:ZLl5Uz3K2xJ9qF4vB8nP@redis.railway.internal:6379

CELERY_RESULT_BACKEND
redis://default:ZLl5Uz3K2xJ9qF4vB8nP@redis.railway.internal:6379

CELERY_TIMEZONE
America/Sao_Paulo

CELERY_ENABLE_UTC
True
```

4. Clique em "Deploy"

## PASSO 3: Configurar Variáveis do Serviço CELERY-BEAT

1. Clique em "celery-beat"
2. Vá para "Settings" → "Dockerfile"
3. Mude para: `Dockerfile.beat`
4. Clique em "Variables" tab
5. **Copie TODAS as variáveis do web-app**
   - Selecione todas as linhas do web-app
   - Copie e cole no celery-beat
6. Clique em "Deploy"

## VERIFICAÇÃO

### No Serviço Web-App

Verifique os logs para ver:
```
[ENTRYPOINT] Starting Gunicorn...
[ENTRYPOINT] Gunicorn version: 23.0.0
```

Acesse: https://seu-site.railway.app/healthz

Deve retornar:
```json
{"status": "ok"}
```

### No Serviço Celery-Beat

Verifique os logs para ver:
```
[CELERY_BEAT_ENTRYPOINT] ✓ Celery version: 5.3.1
[CELERY_BEAT_ENTRYPOINT] ✓ Django version: 5.0.14
[CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...
beat: Scheduler: celery.beat.PersistentScheduler
beat: Entering tick loop.
```

## ⚠️ ARMADILHAS COMUNS

### ❌ ERRADO: Usando template variables

```
CELERY_BROKER_URL
${REDIS_URL}
```

Isto **NÃO FUNCIONA** no Railway!

### ✅ CORRETO: Copiando a URL completa

```
CELERY_BROKER_URL
redis://default:ZLl5Uz3K2xJ9qF4vB8nP@redis.railway.internal:6379
```

### ❌ ERRADO: Esquecendo de copiar variáveis

Se apenas o web-app tiver variáveis, o celery-beat falhará!

### ✅ CORRETO: Mesmo conjunto de variáveis

Ambos os serviços devem ter:
- DATABASE_URL
- REDIS_URL
- CELERY_BROKER_URL
- CELERY_RESULT_BACKEND
- SECRET_KEY
- etc.

## TROUBLESHOOTING

Se ver erro: `ModuleNotFoundError: No module named '${REDIS_URL}'`

**Causa**: A variável CELERY_BROKER_URL ou REDIS_URL contém o texto literal `${REDIS_URL}`

**Solução**:
1. Clique no serviço celery-beat
2. Vá para Variables
3. Clique em CELERY_BROKER_URL
4. Deleta completamente
5. Cole a URL COMPLETA do Redis que copiou lá atrás
6. Clique em "Redeploy"

## EXEMPLO DE URLs REAIS

```
DATABASE_URL: postgresql://postgres:senha123@railway.railway.internal:5432/mydb
REDIS_URL: redis://default:senhaRedis456@redis.railway.internal:6379
CELERY_BROKER_URL: redis://default:senhaRedis456@redis.railway.internal:6379
CELERY_RESULT_BACKEND: redis://default:senhaRedis456@redis.railway.internal:6379
```

Notem que:
- Todas começam com a URL completa (não templates)
- PostgreSQL e Redis têm hosts internos do Railway
- As senhas estão incluídas

## PRÓXIMOS PASSOS

1. ✅ Configure as variáveis acima
2. ✅ Faça deploy dos dois serviços
3. Verifique os logs
4. Teste acessando o Django admin
5. Veja as tarefas agendadas em `/admin/django_celery_beat/periodictask/`

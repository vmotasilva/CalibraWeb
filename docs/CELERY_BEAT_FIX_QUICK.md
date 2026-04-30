# Fix: Celery Beat Deployment no Railway - SOLUÇÃO RÁPIDA

**Data**: 2026-01-07  
**Status**: ✅ SOLUÇÃO IMPLEMENTADA  
**Severidade**: 🔴 CRÍTICA

---

## O Problema em 1 Frase

O Railway estava tentando rodar **Gunicorn** (servidor web) como um serviço de **Celery Beat** (scheduler), o que causava falha no healthcheck HTTP.

---

## A Solução em 3 Passos

### 1️⃣ Criar novo Dockerfile para Celery Beat

**Arquivo criado**: [Dockerfile.beat](Dockerfile.beat)

```dockerfile
# Cópia do Dockerfile padrão MAS:
# - Sem EXPOSE 8000
# - Sem healthcheck HTTP
# - CMD: python entrypoint-beat.py
```

### 2️⃣ Criar novo entrypoint para Celery Beat

**Arquivo criado**: [entrypoint-beat.py](entrypoint-beat.py)

```python
# Em vez de: gunicorn config.wsgi:application
# Executa: celery -A config beat
```

### 3️⃣ Configurar serviço separado no Railway

No dashboard do Railway:

1. Crie um novo serviço vazio
2. Conecte ao GitHub: `vmotasilva/CalibraWeb` / branch `main`
3. Settings → Dockerfile: mude para `Dockerfile.beat`
4. Variables: copie **todas** as variáveis do serviço web
5. Deploy!

---

## Arquivos Criados/Modificados

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| [Dockerfile.beat](Dockerfile.beat) | ✨ NOVO | Dockerfile específico para Celery Beat |
| [entrypoint-beat.py](entrypoint-beat.py) | ✨ NOVO | Script de inicialização do Celery Beat |
| [check_celery_beat_setup.py](check_celery_beat_setup.py) | ✨ NOVO | Script para verificar pré-requisitos |
| [CELERY_BEAT_RAILWAY_DEPLOYMENT.md](CELERY_BEAT_RAILWAY_DEPLOYMENT.md) | ✨ NOVO | Documentação detalhada |
| [railroad.yml](railroad.yml) | ✨ NOVO | Configuração do Railway (referência) |

---

## Arquitetura Recomendada

```
Railway Project
├── PostgreSQL (Database)
├── Redis (Message Broker)
├── CalibraWeb (Web App - porta 8000)
└── Celery Beat (Scheduler - porta nenhuma) ← NOVO
```

---

## Variáveis de Ambiente Necessárias

```env
# Para AMBOS os serviços (Web + Celery Beat)
DJANGO_SETTINGS_MODULE=config.settings
SECRET_KEY=[sua-chave-segura]
DEBUG=False
ALLOWED_HOSTS=*
DATABASE_URL=[copie do PostgreSQL]
REDIS_URL=[copie do Redis]
CELERY_BROKER_URL=[copie do Redis]
CELERY_RESULT_BACKEND=[copie do Redis]
CELERY_TIMEZONE=America/Sao_Paulo
```

**⚠️ IMPORTANTE**: Copie as URLs **completas** do Redis. NÃO use `${REDIS_URL}` ou templates!

---

## Checklist de Deploy

- [ ] Crie novo serviço "celery-beat" no Railway
- [ ] Conecte ao GitHub (vmotasilva/CalibraWeb)
- [ ] Mude Dockerfile para `Dockerfile.beat`
- [ ] Configure todas as variáveis de ambiente
- [ ] Verifique os logs para "Starting Celery Beat Scheduler..."
- [ ] Confirme "beat: Entering tick loop" nos logs
- [ ] Teste acessando http://seu-site/admin/django_celery_beat/

---

## Verificação Rápida de Logs

Procure por essas mensagens de sucesso:

```
[CELERY_BEAT_ENTRYPOINT] ✓ Celery version: 5.3.1
[CELERY_BEAT_ENTRYPOINT] ✓ Django version: 5.0.14
[CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...
beat: Scheduler: celery.beat.PersistentScheduler
beat: Entering tick loop.
```

Se ver `ModuleNotFoundError: No module named '${REDIS_URL}'`, revise a REDIS_URL.

---

## Próximas Melhorias (Futuro)

- [ ] Criar [Dockerfile.worker](Dockerfile.worker) para Celery Workers
- [ ] Implementar retry logic automática
- [ ] Monitorar com Flower (Celery Monitoring)
- [ ] Alertas de falha de tarefas
- [ ] Dashboard de execução de tarefas

---

## Documentação Completa

Ver: [CELERY_BEAT_RAILWAY_DEPLOYMENT.md](CELERY_BEAT_RAILWAY_DEPLOYMENT.md)

---

## Suporte

Dúvidas? Verifique:
1. [CELERY_BEAT_RAILWAY_DEPLOYMENT.md](CELERY_BEAT_RAILWAY_DEPLOYMENT.md) - Guia completo
2. [railroad.yml](railroad.yml) - Configuração detalhada
3. Logs do Railway → Clique no serviço celery-beat → "Logs"

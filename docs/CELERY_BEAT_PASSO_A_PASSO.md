# CELERY BEAT - PASSO A PASSO SIMPLIFICADO

## ❌ PROBLEMA
Railway tentava rodar Celery Beat com Gunicorn (web server)
- Healthcheck esperava HTTP → Celery Beat não responde HTTP
- 337+ falhas de healthcheck → serviço morreu

## ✅ SOLUÇÃO
Separar Celery Beat em **serviço próprio** com **Docker próprio**

---

## 🎯 OS ARQUIVOS

Já estão prontos:

```
Dockerfile.beat ........... Docker para Celery Beat (sem HTTP)
entrypoint-beat.py ....... Script que inicia Celery Beat
```

---

## 📍 PASSO 1: Railway Dashboard

```
1. Abra: https://railway.app
2. Clique: + Create
3. Escolha: GitHub
4. Repositório: vmotasilva/CalibraWeb
5. Clique: Deploy
6. Aguarde: ~5-7 minutos (deixe buildar)
```

---

## 📍 PASSO 2: Configurar Dockerfile

```
1. Novo serviço está pronto? ✓
2. Clique: Settings (aba superior)
3. Procure: Dockerfile
4. Mude de "Dockerfile" → "Dockerfile.beat"
5. Clique: Save
6. Aguarde: Railway rebuildar
```

---

## 📍 PASSO 3: Copiar URLs

**Seu web-app já está no Railway:**

```
1. Clique: Seu serviço web-app
2. Clique: Variables
3. Copie: SECRET_KEY
4. Guarde num arquivo temporário

1. Clique: PostgreSQL (banco)
2. Abra: Connect
3. Copie: Database URL (postgresql://...)
4. Guarde num arquivo temporário

1. Clique: Redis
2. Abra: Connect
3. Copie: Redis URL (redis://...)
4. Guarde num arquivo temporário
```

---

## 📍 PASSO 4: Colar Variáveis no Celery Beat

```
1. Volte para: Seu novo serviço (celery-beat)
2. Clique: Variables
3. Cole EXATAMENTE isto:
```

```
DJANGO_SETTINGS_MODULE = config.settings
DEBUG = False
SECRET_KEY = [COLE DO WEB-APP]
ALLOWED_HOSTS = *
DATABASE_URL = [COLE DO POSTGRESQL]
POSTGRES_URL = [COLE DO POSTGRESQL]
REDIS_URL = [COLE DO REDIS]
CELERY_BROKER_URL = [COLE DO REDIS]
CELERY_RESULT_BACKEND = [COLE DO REDIS]
CELERY_TIMEZONE = America/Sao_Paulo
CELERY_ENABLE_UTC = True
```

```
4. Clique: Save
5. Aguarde: 10-15 segundos reiniciar
```

⚠️ **IMPORTANTE**: Cole a URL COMPLETA do Redis, não variável!

---

## 📍 PASSO 5: Verificar

```
1. Clique: Logs (aba superior)
2. Procure por: "beat: Entering tick loop"
3. Se vir isso = PRONTO!
```

Logs normais parecem assim:
```
beat: Starting Celery Beat Scheduler...
beat: Entering tick loop
Scheduled 'relatorio-diario-vencidos' at 08:00:00
```

---

## ✅ PRONTO!

Se aparecer "Entering tick loop" nos logs = **Celery Beat funcionando!**

---

## ❌ ERRO?

| Erro | Causa | Solução |
|------|-------|---------|
| `beat: ERROR` | Variável faltando | Verifique as 11 variáveis |
| `ConnectionError - Redis` | REDIS_URL errada | Copie URL completa novamente |
| `Django database error` | DATABASE_URL errada | Copie PostgreSQL URL |
| `No such file: Dockerfile.beat` | Não trocou Dockerfile | Settings > Dockerfile > `Dockerfile.beat` |

---

## 📊 6 Tarefas que Rodarão

- **08:00 AM** → relatorio-diario-vencidos
- **09:00 AM domingo** → relatorio-semanal-estatisticas
- **A cada 4h** → alerta-critico-vencidos
- **A cada 25 min** → warm-instrumentos-cache
- **A cada 55 min** → warm-statistics-cache
- **A cada 55 min** → warm-categories-cache

---

## ⏱️ Tempo Total

- Setup: 5 min
- Deploy: 15 min
- Verificação: 5 min
- **TOTAL: ~20 min**

---

**É só isso! Sucesso!** 🚀

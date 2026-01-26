# ⚡ CELERY BEAT - DEPLOY EM 10 MINUTOS

## ✅ PRONTO!

Todos os arquivos necessários foram criados no seu projeto:
- ✓ Dockerfile.beat
- ✓ entrypoint-beat.py  
- ✓ Documentação completa

## 🚀 AGORA FAÇA NO RAILWAY

### PASSO 1: Abra https://railway.app

### PASSO 2: Clique em "+ Create"

### PASSO 3: Selecione "GitHub"

### PASSO 4: 
- Repositório: vmotasilva/CalibraWeb
- Branch: main
- Clique "Deploy"

### PASSO 5: Aguarde 5 minutos (o build vai rodar)

### PASSO 6: Quando terminar, clique em "Settings"

### PASSO 7: Vá para "Build" → "Dockerfile"

Mude de: Dockerfile  
Para: **Dockerfile.beat**

Clique "Save"

### PASSO 8: Vá para "Variables"

Copie e cole EXATAMENTE estas variáveis (11 no total):

```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=False
SECRET_KEY=[COPIE DO WEB-APP]
ALLOWED_HOSTS=*
DATABASE_URL=[COPIE DO POSTGRESQL]
POSTGRES_URL=[COPIE DO POSTGRESQL]
REDIS_URL=[COPIE DO REDIS]
CELERY_BROKER_URL=[COPIE DO REDIS]
CELERY_RESULT_BACKEND=[COPIE DO REDIS]
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=True
```

**⚠️ IMPORTANTE:**
- NÃO use `${REDIS_URL}` 
- Cole a URL COMPLETA do Redis
- Ex: redis://default:password@redis.railway.internal:6379

### PASSO 9: Clique "Save"

Railway fará novo deploy automaticamente.

## ✅ VERIFICAÇÃO (5 MINUTOS)

1. Vá para "Logs" do serviço celery-beat
2. Procure por: **"Starting Celery Beat Scheduler..."**
3. Procure por: **"beat: Entering tick loop"**

Se viu essas mensagens: ✅ **DEU CERTO!**

## 📍 ONDE COPIAR AS URLs

### PostgreSQL:
1. Clique no serviço "PostgreSQL"
2. Clique em "Connect"  
3. Procure por "DATABASE_URL" ou "PostgreSQL"
4. Copie a URL COMPLETA

Exemplo:
```
postgresql://postgres:SenhaAqui@railway.railway.internal:5432/railway
```

### Redis:
1. Clique no serviço "Redis"
2. Clique em "Connect"
3. Procure por "REDIS_URL" ou "Redis"
4. Copie a URL COMPLETA

Exemplo:
```
redis://default:SenhaAqui@redis.railway.internal:6379
```

### SECRET_KEY:
1. Clique no serviço "CalibraWeb" (web-app)
2. Clique em "Variables"
3. Copie o valor de "SECRET_KEY"

## 🎯 RESULTADO

Quando tudo estiver certo, você verá:

```
Serviço: celery-beat
Status: ✓ UP

Logs mostram:
> [CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...
> beat: Scheduler: celery.beat.PersistentScheduler
> beat: Entering tick loop ✓

Tarefas agendadas: 6 ✓
```

## 🆘 ERRO? 

### Se ver: "ModuleNotFoundError: No module named '${REDIS_URL}'"

❌ Você copiou `${REDIS_URL}` em vez da URL real

✅ Solução:
1. Vá para Variables
2. Clique em CELERY_BROKER_URL
3. Delete e cole a URL REAL
4. Salve e faça novo deploy

### Se ver: "ConnectionError connecting to Redis"

❌ REDIS_URL está incorreta ou Redis está offline

✅ Solução:
1. Confirme que Redis está UP (verde)
2. Copie a URL novamente do Redis
3. Cole em REDIS_URL, CELERY_BROKER_URL e CELERY_RESULT_BACKEND

---

## 📚 PRECISA DE AJUDA?

- Leia: README_CELERY_BEAT.md
- Ou: RAILWAY_STEP_BY_STEP.md
- Ou: RAILWAY_VARIABLES_EXAMPLE.md

---

**Tempo total: 10-15 minutos**  
**Dificuldade: Fácil (copiar e colar)**  
**Status: Pronto para deploy! ✓**

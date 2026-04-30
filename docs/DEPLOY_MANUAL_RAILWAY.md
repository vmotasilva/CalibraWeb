# 🚀 DEPLOY CELERY BEAT - RAILWAY (MANUAL)

> **Status**: Código pronto ✅ | Esperando você fazer os passos manuais no Railway

---

## ⚠️ IMPORTANTE - LEIA ANTES DE COMEÇAR

**Você PRECISA destes dados do seu Railway ANTES de começar:**

1. **PostgreSQL URL** - Do seu banco de dados existente
2. **Redis URL** - Do seu serviço Redis existente
3. **SECRET_KEY** - Do seu web-app atual

Se NÃO tiver essas URLs, abra seu Railway NOW e copie-as!

---

## 🎯 9 PASSOS SIMPLES (10-15 minutos)

### PASSO 1: Crie um novo Serviço no Railway
```
1. Vá para: https://railway.app/dashboard
2. Clique: + Create (no canto superior direito)
3. Escolha: GitHub
4. Selecione: vmotasilva/CalibraWeb
5. Clique: Deploy
```
⏱️ Aguarde 5-7 minutos o Docker build completar.

---

### PASSO 2: Configure o Dockerfile.beat
```
1. Novo serviço criado? ✓
2. Clique: Settings (aba na parte superior)
3. Procure: Root Directory (deixe vazio ou "/")
4. Procure: Dockerfile
5. Mude de "Dockerfile" para "Dockerfile.beat"
6. Clique: Save (canto inferior direito)
```
🔄 Railway vai fazer rebuild automático.

---

### PASSO 3: Copie seu SECRET_KEY
```
Abra seu serviço WEB-APP no Railway:
  1. Clique no nome do serviço (CalibraWeb web)
  2. Vá para: Variables
  3. Copie o valor de: SECRET_KEY
  4. Guarde em um arquivo temporário
```

---

### PASSO 4: Copie PostgreSQL URL
```
No seu Railway:
  1. Clique em: PostgreSQL (o banco de dados)
  2. Abra a aba: Connect
  3. Copie: Database URL (aquela começada com "postgresql://")
  4. Guarde em um arquivo temporário
```

---

### PASSO 5: Copie Redis URL
```
No seu Railway:
  1. Clique em: Redis
  2. Abra a aba: Connect
  3. Copie: Redis URL (aquela começada com "redis://")
  4. Guarde em um arquivo temporário
```

---

### PASSO 6: Volte ao Serviço Celery Beat
```
No seu Railway:
  1. Clique no novo serviço (celery-beat ou similar)
  2. Vá para: Variables
```

---

### PASSO 7: Cole as VARIÁVEIS (cópia exata!)

Cole EXATAMENTE assim (use copy-paste):

```
DJANGO_SETTINGS_MODULE = config.settings
DEBUG = False
SECRET_KEY = [COLE O QUE COPIOU DO WEB-APP]
ALLOWED_HOSTS = *
DATABASE_URL = [COLE A URL DO POSTGRESQL]
POSTGRES_URL = [COLE A URL DO POSTGRESQL]
REDIS_URL = [COLE A URL DO REDIS]
CELERY_BROKER_URL = [COLE A URL DO REDIS]
CELERY_RESULT_BACKEND = [COLE A URL DO REDIS]
CELERY_TIMEZONE = America/Sao_Paulo
CELERY_ENABLE_UTC = True
```

**⚠️ ATENÇÃO ESPECIAL:**
- Se a REDIS_URL viera assim: `redis://default:abc123@host:6379`
- NÃO mude para variável ${REDIS_URL}
- **COLE A URL INTEIRA** como está!

---

### PASSO 8: Salve as variáveis
```
1. Clique: Save (canto inferior direito)
2. Aguarde 10-15 segundos o serviço reiniciar
```

---

### PASSO 9: Verifique nos Logs
```
1. Vá para: Logs (aba na parte superior do serviço)
2. Procure por: "beat: Entering tick loop"
3. Se vir isso = ✅ FUNCIONANDO!
```

Logs normais parecem assim:
```
[2026-01-07 14:23:45] INFO - beat: Starting Celery Beat Scheduler...
[2026-01-07 14:23:46] INFO - beat: Entering tick loop
[2026-01-07 14:23:50] INFO - Scheduled 'relatorio-diario-vencidos' at 08:00:00
```

---

## ✅ PRONTO!

Se viu "Entering tick loop" nos logs → **Celery Beat está rodando!**

### Próximas tarefas agendadas:
- ⏰ **relatorio-diario-vencidos**: 08:00 AM (todo dia)
- ⏰ **relatorio-semanal-estatisticas**: 09:00 AM (domingo)
- ⏰ **alerta-critico-vencidos**: A cada 4 horas
- 🔄 **warm-instrumentos-cache**: A cada 25 minutos
- 🔄 **warm-statistics-cache**: A cada 55 minutos
- 🔄 **warm-categories-cache**: A cada 55 minutos

---

## ❌ Se der ERRO?

### Erro: "beat: ERROR/MainProcess"
```
Causa: Variáveis de ambiente faltando
Solução: Verifique se colou todas as 11 variáveis
```

### Erro: "ConnectionError - Redis"
```
Causa: REDIS_URL incorreta
Solução: Copie novamente a URL exata do Redis no Railway
```

### Erro: "Django database error"
```
Causa: DATABASE_URL incorreta
Solução: Copie novamente a URL exata do PostgreSQL
```

### Erro: "No such file: Dockerfile.beat"
```
Causa: Não trocou para Dockerfile.beat
Solução: Settings > Dockerfile > mude para "Dockerfile.beat"
```

---

## 📞 Precisa de ajuda?

Consulte:
- [README_CELERY_BEAT.md](README_CELERY_BEAT.md) - Visão geral do projeto
- [RAILWAY_STEP_BY_STEP.md](RAILWAY_STEP_BY_STEP.md) - Detalhes de cada passo
- [CELERY_BEAT_RAILWAY_DEPLOYMENT.md](CELERY_BEAT_RAILWAY_DEPLOYMENT.md) - Troubleshooting completo

---

**Você consegue!** 💪 É só 9 passos simples.

Boa sorte! 🚀

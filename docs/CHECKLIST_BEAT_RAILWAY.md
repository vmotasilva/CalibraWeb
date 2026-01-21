# ✅ CHECKLIST - Celery Beat Railway (Passo-a-Passo Completo)

## 1️⃣ Código foi atualizado ✅
- ✅ Push feito ao GitHub
- ✅ Railway está fazendo rebuild

## 2️⃣ Aguarde rebuild (~2-3 minutos)
- [ ] Vá para Railway Dashboard
- [ ] Seu projeto CalibraWeb
- [ ] Veja os serviços: `web`, `beat`, `worker`
- [ ] Todos devem estar `Building` ou `Online`

## 3️⃣ Abra o serviço `beat` (⚠️ NÃO web, NÃO worker)
- [ ] Clique em `beat`
- [ ] Vá para aba `Variables`

## 4️⃣ Copie variáveis do `web`
- [ ] Clique em `web` > `Variables`
- [ ] Copie `SECRET_KEY` (valor completo, é uma string longa)
- [ ] Copie `ALLOWED_HOSTS` (se existir)
- [ ] Volte para `beat` > `Variables`

## 5️⃣ Copie variáveis do `PostgreSQL`
- [ ] Clique em `PostgreSQL` > `Variables`
- [ ] Copie `DATABASE_URL` (é uma string tipo `postgresql://...`)
- [ ] Volte para `beat` > `Variables`

## 6️⃣ Copie variáveis do `Redis`
- [ ] Clique em `Redis` > `Variables`
- [ ] Procure por `REDIS_URL` (é uma string tipo `redis://...`)
  - **OU** procure por: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- [ ] Copie o que encontrar
- [ ] Volte para `beat` > `Variables`

## 7️⃣ Adicione as variáveis no `beat`

### Se você tem `REDIS_URL`:
```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
SECRET_KEY=<paste aqui>
ALLOWED_HOSTS=*.railway.app,localhost
DATABASE_URL=<paste aqui>
REDIS_URL=<paste aqui>
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

### Se você tem `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`:
```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
SECRET_KEY=<paste aqui>
ALLOWED_HOSTS=*.railway.app,localhost
DATABASE_URL=<paste aqui>
REDIS_HOST=<paste aqui>
REDIS_PORT=<paste aqui>
REDIS_PASSWORD=<paste aqui>
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

## 8️⃣ Salve as variáveis
- [ ] Clique em **Save** (botão no canto inferior direito)
- [ ] Railway fará redeploy automaticamente
- [ ] Aguarde ~1 minuto

## 9️⃣ Verifique os Logs
- [ ] Vá para aba **Logs** (no serviço `beat`)
- [ ] Aguarde ~30 segundos
- [ ] Procure por:
  - `✅ Django settings loaded for Celery`
  - `✅ Database OK`
  - `✅ Redis Connection OK`
  - `Entering tick loop`

## ✅ SUCESSO!
Se vir as mensagens de ✅ acima = **FUNCIONANDO!**

---

## 🆘 Se der erro

**Copie o log completo e verifique:**

### Erro: `Port could not be cast to integer value as '${REDIS_PORT}'`
- Solução: Adicione `REDIS_PORT` como número (ex: `6379`), não como variável

### Erro: `Connection refused`
- Solução: Verifique se Redis está `Running` em Railway > Overview

### Erro: `No module named 'postgresql'`
- Solução: DATABASE_URL está inválida ou PostgreSQL não está online

### Erro: `Connection timed out`
- Solução: Aguarde mais 5 minutos e redeploie manualmente

---

## 📞 Resumo

✅ **Código:**
- `config/settings.py` - Constrói URL do Redis robustamente
- `config/celery.py` - Debug completo
- `entrypoint-beat-debug.sh` - Validação antes de iniciar

**Você precisa:**
1. Esperar rebuild do Railway (2-3 min)
2. Adicionar 8 variáveis de ambiente no serviço `beat`
3. Clicar Save
4. Verificar Logs

Pronto! Celery Beat funcionará! 🚀

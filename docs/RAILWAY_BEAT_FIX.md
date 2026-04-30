# 🔧 Railway - Celery Beat Fix

## Problema
Celery Beat está falhando com:
```
ValueError: Port could not be cast to integer value as '${REDIS_PORT}'
```

**Causa**: O serviço `beat` **NÃO TEM** as variáveis de ambiente configuradas.

---

## ✅ Solução (5 minutos)

### 1. Vá para Railway Dashboard
- Acesse: https://railway.app/dashboard
- Selecione seu projeto **CalibraWeb**

### 2. Clique no serviço **beat**
- Você verá 3 serviços: `web`, `beat`, `worker`
- Clique em **beat**

### 3. Vá para a aba **Variables**
- No topo, vejo várias abas: Overview, Deployments, **Variables**, Logs...
- Clique em **Variables**

### 4. Copie as variáveis do serviço **web**

**Clique em `web`** e em **Variables**, copie essas:
- `SECRET_KEY` = [valor que já existe no web]
- `DEBUG` = `false`
- `DJANGO_SETTINGS_MODULE` = `config.settings`

**Clique em PostgreSQL** (ou seu database) e copie:
- `DATABASE_URL` = [URL de conexão]

**Clique em Redis** e copie:
- `REDIS_URL` = [URL com redis://...]

### 5. Cole todas no serviço **beat**

Volte para o serviço **beat** > **Variables** e adicione:

```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
SECRET_KEY=<copie do web>
DATABASE_URL=<copie do PostgreSQL>
REDIS_URL=<copie do Redis>
CELERY_BROKER_URL=<mesmo valor de REDIS_URL>
CELERY_RESULT_BACKEND=<mesmo valor de REDIS_URL>
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

### 6. Clique **Save**
- Railway fará redeploy automaticamente

---

## ✅ Verificação

Vá para **Logs** do serviço `beat`:

Deve aparecer:
```
celery beat v5.3.1 (emerald-rush) is starting.
```

Depois (aguarde ~30 segundos):
```
[INFO] beat: Starting...
[INFO] Scheduler: Scheduler started
[INFO] Entering tick loop
```

Se aparecer isso = **FUNCIONANDO! ✅**

---

## 🔴 Se ainda der erro

Se mesmo depois disso ainda der erro, delete a aba **Beat Logs** e veja o log novamente. Pode ser que:

1. **Aguarde mais 5 minutos** - Railway às vezes demora para propagar variáveis
2. **Force redeploy**:
   - Vá em **Deployments**
   - Clique nos 3 pontinhos `...` do último deployment
   - Clique **Redeploy**

3. **Verifique se Redis está online**:
   - Clique em **Redis** > **Overview**
   - Deve mostrar "Running"

---

## 📋 Checklist Final

- [ ] Abri o serviço **beat** (não web, não worker)
- [ ] Cliquei em **Variables**
- [ ] Copiei `SECRET_KEY` do web
- [ ] Copiei `DATABASE_URL` do PostgreSQL
- [ ] Copiei `REDIS_URL` do Redis
- [ ] Adicionei `CELERY_BROKER_URL` = mesmo que REDIS_URL
- [ ] Cliquei **Save**
- [ ] Aguardei 1 minuto
- [ ] Verifiquei **Logs** do beat
- [ ] Vejo "Entering tick loop" ✅

---

## 📞 Resumo das mudanças no código

Também atualizei `config/celery.py` para ser mais robusto e detectar variáveis não expandidas.

Se ainda der problema, envie o log completo do beat para debug.

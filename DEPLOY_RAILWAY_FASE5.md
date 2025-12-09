# 🚀 DEPLOY FASE 5 NO RAILWAY

## 📋 Guia Passo a Passo

Este guia mostra como deployar o sistema de Fase 5 (Exports + Scheduled Reports) no Railway.

---

## 🎯 Pré-requisitos

- [x] Código Fase 5 commitado
- [x] Testes passando localmente
- [x] Railway account criada
- [x] Redis configurado no Railway
- [x] Email backend escolhido

---

## 📝 PASSO 1: Preparar Procfile

Editar ou criar `Procfile` na raiz do projeto:

```procfile
# Web server
web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 60

# Celery worker
worker: celery -A config worker -l info --concurrency=4 --time-limit=3600 --soft-time-limit=3000

# Celery beat (scheduler)
beat: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Ou mantendo simples:**
```procfile
web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn config.wsgi
worker: celery -A config worker -l info
beat: celery -A config beat -l info
```

---

## 🔑 PASSO 2: Configurar Variáveis de Ambiente

No painel do Railway, adicione as variáveis:

```
# Django
SECRET_KEY=sua-chave-secreta
DEBUG=False
ALLOWED_HOSTS=seu-app.railway.app,www.seu-app.railway.app

# Email (Gmail recomendado)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-app-password-16-chars

# Email recipients
DEFAULT_FROM_EMAIL=seu-email@gmail.com
REPORT_EMAIL_TO=gestor@empresa.com,supervisor@empresa.com
ALERT_EMAIL_TO=supervisor@empresa.com

# Celery (Redis já no Railway)
CELERY_BROKER_URL=$REDIS_PRIVATE_URL  # ou $REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_PRIVATE_URL

# Database
DATABASE_URL=$DATABASE_PRIVATE_URL  # ou seu PostgreSQL URL

# CSRF
CSRF_TRUSTED_ORIGINS=https://seu-app.railway.app
```

---

## 🐳 PASSO 3: Dockerfile (Opcional, mais controle)

Se quiser mais controle, criar `Dockerfile`:

```dockerfile
FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

---

## 🚢 PASSO 4: Deploy no Railway

### Opção A: Via Web UI

1. **Conectar repositório**
   - Railway → New Project → Deploy from GitHub
   - Selecionar seu repo `CalibraWeb`

2. **Configurar variáveis**
   - Ir para projeto → Variables
   - Adicionar todas as variáveis acima

3. **Configurar Procfile**
   - Railway detecta Procfile automaticamente
   - Se não detectar, ver Deployment Settings

4. **Deploy**
   - Push para main: `git push`
   - Railway faz deploy automático

### Opção B: Via CLI Railway

```bash
# Login
railway login

# Link projeto
railway link

# Configurar variáveis
railway variables set EMAIL_HOST_USER=seu-email@gmail.com
railway variables set EMAIL_HOST_PASSWORD=app-password
railway variables set REPORT_EMAIL_TO=gestor@empresa.com

# Deploy
git push  # Dispara deploy automático

# Ver logs
railway logs
```

---

## 📊 PASSO 5: Configurar Serviços Railway

### Redis (Message Broker)

1. **Criar Redis**
   ```bash
   railway service create
   # Selecionar: Redis
   ```

2. **Obter URL**
   ```bash
   railway variables | grep REDIS
   # Usar: REDIS_PRIVATE_URL ou REDIS_URL
   ```

3. **Adicionar ao Procfile ou variáveis**
   ```
   CELERY_BROKER_URL=$REDIS_PRIVATE_URL
   ```

### PostgreSQL (Database)

Já deve estar configurado, mas verificar:

```bash
railway variables | grep DATABASE
```

---

## ✅ PASSO 6: Verificar Deploy

### Logs Web
```bash
railway logs --service web
# Deve mostrar:
# "Uvicorn running on 0.0.0.0:8000"
```

### Logs Worker
```bash
railway logs --service worker
# Deve mostrar:
# "celery@hostname ready"
```

### Logs Beat
```bash
railway logs --service beat
# Deve mostrar:
# "celery beat running"
```

### Acessar Aplicação
```
https://seu-app.railway.app
```

---

## 🧪 PASSO 7: Testar Funcionalidades

### Teste 1: Exportação Manual

```bash
# Via Railway CLI
railway run python manage.py shell
>>> from qms.models import Instrumento
>>> from metrologia.exportadores import ExportadorInstrumentos
>>> queryset = Instrumento.objects.all()[:10]
>>> exp = ExportadorInstrumentos(queryset)
>>> # Apenas teste se criou obj
>>> print("✅ Export OK")
```

### Teste 2: Tarefa Manual

```bash
railway run celery -A config call qms.tasks.gerar_relatorio_diario_vencidos
```

Verificar nos logs se executou.

### Teste 3: Email

```bash
railway run python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Teste do Fase 5', 'from@gmail.com', ['seu-email@gmail.com'])
# Verificar inbox
```

### Teste 4: Verificar Agendamento

```bash
railway logs --service beat
# Procure por: "Sending due task"
```

---

## 🔍 MONITORAMENTO

### Flower (Dashboard do Celery)

1. **Instalar Flower**
   ```
   pip install flower
   # Adicionar ao requirements.txt
   ```

2. **Criar serviço no Railway**
   ```procfile
   # Adicionar ao Procfile
   flower: celery -A config flower --port=5555
   ```

3. **Acessar**
   ```
   https://seu-app-flower.railway.app
   ```

4. **Ver Tasks**
   - Active Tasks
   - Task History
   - Worker Status

### Railway Dashboard

1. **Monitorar CPU/Memória**
   - Railway → Seu Projeto → Metrics

2. **Ver Logs em Tempo Real**
   - Railway → Seu Projeto → Logs

3. **Alertas (Upgrade Pro)**
   - Railway → Settings → Alerts

---

## 🆘 TROUBLESHOOTING

### "Worker não inicia"

```
Module celery not found
```

**Solução:**
```bash
# Verificar requirements.txt
pip install celery

# Adicionar ao requirements.txt
echo "celery>=5.3.0" >> requirements.txt

# Commit e push
git add requirements.txt
git commit -m "Add celery to requirements"
git push
```

### "Redis connection refused"

```
Error: Couldn't connect to Redis
```

**Verificar:**
1. Redis foi criado no Railway?
2. URL está correta em CELERY_BROKER_URL?
3. Verificar em Railway Dashboard → Variables

**Solução:**
```bash
railway variables list | grep REDIS
# Copiar URL exata
railway variables set CELERY_BROKER_URL=$(railway variables get REDIS_PRIVATE_URL)
```

### "Database connection error"

**Solução:**
```bash
railway run python manage.py migrate
# Se ainda não rodar, pode ser timeout
```

### "Email não envia"

**Checklist:**
1. EMAIL_BACKEND está correto?
2. EMAIL_HOST_USER e EMAIL_HOST_PASSWORD corretos?
3. Se Gmail: usar App Password, não senha normal?
4. Verificar firewall (porta 587)?

**Teste:**
```bash
railway run python manage.py shell
>>> from django.core.mail import send_mail
>>> result = send_mail('Test', 'Body', 'from@gmail.com', ['to@example.com'])
>>> print(f"Emails enviados: {result}")
```

### "Beat não agenda tasks"

**Verificar logs:**
```bash
railway logs --service beat | tail -50
```

Procure por:
- `Scheduler: Starting`
- `Sending due task`

Se não houver:
```bash
railway run celery -A config inspect scheduled
# Deve listar as tarefas agendadas
```

---

## 📈 ESCALABILIDADE

### Para Alta Carga

**Aumentar workers:**
```procfile
worker: celery -A config worker -l info --concurrency=8
```

**Adicionar múltiplos workers:**
```procfile
worker1: celery -A config worker -Q default,reports --concurrency=4
worker2: celery -A config worker -Q alerts --concurrency=2
```

**Aumentar recursos Railway:**
- Railway Dashboard → Seu Projeto → Plugins
- Aumentar CPU/RAM do dyno

---

## 📅 MANUTENÇÃO

### Limpeza Periódica

```bash
# Limpar tasks antigas
railway run celery -A config purge

# Limpar cache Redis
railway run python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### Backup de Dados

```bash
# Exportar dados
railway run python manage.py dumpdata > backup.json

# Importar se necessário
railway run python manage.py loaddata backup.json
```

### Update de Código

```bash
# Fazer mudanças locais
git add .
git commit -m "feat: Melhorias Fase 5"
git push

# Railway faz deploy automático
# Monitorar com: railway logs
```

---

## 🎉 PRÓXIMAS ETAPAS

1. ✅ Deploy em staging primeiro
2. ✅ Testar todas funcionalidades
3. ✅ Monitorar por 24h
4. ✅ Setup alertas (email se algo falhar)
5. ✅ Documentar URLs e credenciais
6. ✅ Treinamento do time

---

## 📞 REFERÊNCIAS

- **Railway Docs**: https://docs.railway.app
- **Celery Guide**: https://docs.celeryproject.org/
- **Django on Railway**: https://docs.railway.app/guides/django
- **Procfile**: https://devcenter.heroku.com/articles/procfile

---

**Status: Pronto para deploy! 🚀**

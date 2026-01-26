# 🔧 CONFIGURAÇÃO DE PRODUÇÃO - CELERY, REDIS E EMAIL

## 📋 Resumo

Para colocar a Fase 5 em produção (tasks agendadas, exports e emails), você precisa de:

1. **Email Backend** - Para enviar relatórios e alertas
2. **Redis** - Message broker para Celery
3. **Celery Worker** - Processa tasks
4. **Celery Beat** - Agenda tasks automáticas

---

## 📧 1. CONFIGURAÇÃO DE EMAIL

### Opção A: Gmail (Recomendado para começar)

**Passo 1:** Ativar autenticação em 2 fatores
- Acesse: https://myaccount.google.com/security
- Ative "Verificação em duas etapas"

**Passo 2:** Gerar App Password
- Acesse: https://myaccount.google.com/apppasswords
- Selecione: "Mail" e "Windows Computer"
- Copie a senha gerada (16 caracteres)

**Passo 3:** Configurar em `.env`
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Senha de 16 chars
DEFAULT_FROM_EMAIL=seu-email@gmail.com
REPORT_EMAIL_TO=gestor@empresa.com
ALERT_EMAIL_TO=supervisor@empresa.com
```

**Teste:**
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@gmail.com', ['to@example.com'])
```

### Opção B: SendGrid

1. Criar conta em https://sendgrid.com
2. Gerar API Key
3. Instalar: `pip install sendgrid-backend`
4. Configurar:
```bash
EMAIL_BACKEND=sendgrid_backend.SendgridBackend
SENDGRID_API_KEY=seu-api-key
DEFAULT_FROM_EMAIL=noreply@empresa.com
```

### Opção C: AWS SES

1. Verificar domínio em AWS SES
2. Criar credenciais IAM
3. Instalar: `pip install django-ses`
4. Configurar:
```bash
EMAIL_BACKEND=django_ses.SESBackend
AWS_SES_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=sua-key
AWS_SECRET_ACCESS_KEY=sua-secret
```

---

## 🔴 2. CONFIGURAÇÃO DE REDIS

### Railway (Recomendado para Deploy)

**Passo 1:** Criar serviço Redis no Railway
```bash
# Via CLI do Railway
railway service create
# Selecionar: Redis
```

**Passo 2:** Obter connection string
```bash
railway variables
# Procurar por: REDIS_URL ou REDIS_PRIVATE_URL
```

**Passo 3:** Adicionar ao `.env`
```bash
CELERY_BROKER_URL=redis://default:password@host:port/0
CELERY_RESULT_BACKEND=redis://default:password@host:port/0
```

### Local (Desenvolvimento)

**Passo 1:** Instalar Redis
- Windows: `choco install redis` ou usar WSL2
- Mac: `brew install redis`
- Linux: `apt-get install redis-server`

**Passo 2:** Iniciar Redis
```bash
redis-server
# Deve mostrar: "Ready to accept connections"
```

**Passo 3:** Configurar em `.env`
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**Teste:**
```bash
python manage.py shell
>>> import redis
>>> r = redis.Redis(host='localhost', port=6379, db=0)
>>> r.ping()  # Deve retornar True
```

---

## 🐍 3. CELERY WORKER

### Iniciar Worker Local

```bash
# Terminal 1: Ativar ambiente
source .venv/bin/activate  # ou .venv\Scripts\Activate.ps1 no Windows

# Terminal 1: Rodar worker
celery -A config worker -l info
```

Saída esperada:
```
 -------------- celery@hostname v5.3.1 (morning glory)
 --- ***** -----
 -- ******* ----
 - *** --- * ---
 - ** ---------- [config]
 - ** ---------- [queues]
     Concurrency: 4 (prefork)
     [2025-12-09 10:00:00,000: WARNING/MainProcess] celery@hostname ready.
```

### Em Produção (Railway/Render)

**Procfile:**
```
worker: celery -A config worker -l info
```

**Ou via comando customizado:**
```bash
celery -A config worker \
  --loglevel=info \
  --concurrency=4 \
  --time-limit=3600 \
  --soft-time-limit=3000
```

---

## ⏰ 4. CELERY BEAT (Task Scheduler)

### Iniciar Beat Local

```bash
# Terminal 2: (mantendo worker rodando)
celery -A config beat -l info
```

Saída esperada:
```
 celery beat v5.3.1 is running.
 ...
 [2025-12-09 10:00:00,000: INFO/MainProcess] Scheduler: Sending due task relatorio-diario-vencidos
```

### Em Produção (Railway/Render)

**Procfile:**
```
beat: celery -A config beat -l info
```

**Ou Systemd (Linux):**

Criar arquivo `/etc/systemd/system/calibraweb-beat.service`:
```ini
[Unit]
Description=Celery Beat for CalibraWeb
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/calibraweb
ExecStart=/var/www/calibraweb/.venv/bin/celery -A config beat -l info
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Ativar:
```bash
sudo systemctl enable calibraweb-beat
sudo systemctl start calibraweb-beat
sudo systemctl status calibraweb-beat
```

### Em Produção (Windows Service)

Usar `NSSM` (Non-Sucking Service Manager):
```bash
# Instalar NSSM
choco install nssm

# Criar serviço
nssm install CalibraWebBeat "C:\path\.venv\Scripts\celery.exe" "-A config beat -l info"

# Iniciar
nssm start CalibraWebBeat
```

---

## 🖥️ 5. MONITORAMENTO

### Flower (Web UI para Celery)

```bash
# Terminal 3: Instalar e rodar Flower
pip install flower
celery -A config flower
```

Acesse: http://localhost:5555

Mostra:
- Tasks em execução
- Histórico de tasks
- Workers ativos
- Pool de tarefas

---

## ✅ CHECKLIST DE PRODUÇÃO

### Antes de Deploy

- [ ] Redis configurado e testado
- [ ] Email backend configurado e testado
- [ ] Variáveis de ambiente no `.env`
- [ ] Testes Fase 5 passando: `python manage.py test qms.tests_fase5`
- [ ] Worker rodando localmente: `celery -A config worker -l info`
- [ ] Beat rodando localmente: `celery -A config beat -l info`
- [ ] Tarefa manual testada: `celery -A config call qms.tasks.gerar_relatorio_diario_vencidos`
- [ ] Email manual testado: `python manage.py shell`

### Deploy

- [ ] Push para Railway/Render
- [ ] Configurar variáveis de ambiente no painel
- [ ] Procfile com worker e beat
- [ ] Rodar migrações: `railway run python manage.py migrate`
- [ ] Verificar logs: `railway logs`
- [ ] Teste manual de email
- [ ] Monitorar com Flower

---

## 🐛 TROUBLESHOOTING

### Worker não inicia

```
Error: No module named 'config'
```
**Solução:** Verificar que está no diretório correto e ambiente virtual ativado

```bash
pwd  # Deve ser /path/to/CalibraWeb
source .venv/bin/activate
```

### "Couldn't connect to redis"

**Solução:** Verificar se Redis está rodando
```bash
redis-cli ping  # Deve retornar "PONG"
```

Se não está:
```bash
# Local
redis-server

# Railway: verificar CELERY_BROKER_URL em variáveis de ambiente
```

### Task não executa

```
Task received but not executing
```

**Verificar:**
1. Worker está rodando? `celery -A config worker -l info`
2. Beat está rodando? `celery -A config beat -l info`
3. Task está registrada? `celery -A config inspect registered`

### Email não envia

```
SMTPAuthenticationError
```

**Verificar:**
1. Credenciais corretas?
2. App Password (não senha normal)?
3. Email backend correto?

**Teste:**
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@gmail.com', ['to@example.com'])
```

---

## 📊 EXEMPLO: RAILWAY DEPLOY

### 1. Criar projeto Railway

```bash
railway link  # Conectar repositório
```

### 2. Configurar variáveis

```bash
railway variables set \
  EMAIL_HOST_USER=seu-email@gmail.com \
  EMAIL_HOST_PASSWORD=app-password \
  REPORT_EMAIL_TO=gestor@empresa.com \
  CELERY_BROKER_URL=redis://... \
  SECRET_KEY=sua-chave
```

### 3. Criar Procfile

```
web: python manage.py runserver 0.0.0.0:$PORT
worker: celery -A config worker -l info
beat: celery -A config beat -l info
```

### 4. Deploy

```bash
git push  # Push automático dispara deploy
railway logs  # Ver logs em tempo real
```

---

## 📞 REFERÊNCIAS

- **Celery**: https://docs.celeryproject.org/
- **Gmail App Password**: https://myaccount.google.com/apppasswords
- **Redis**: https://redis.io/docs/getting-started/
- **Railway**: https://railway.app/docs
- **Flower**: https://flower.readthedocs.io/

---

**Próximas etapas após setup:**
1. ✅ Testar exports via UI
2. ✅ Testar tasks manualmente
3. ✅ Ativar agendamento 24h
4. ✅ Monitorar com Flower

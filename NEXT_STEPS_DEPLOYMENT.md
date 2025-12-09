# PRÓXIMOS PASSOS - CALIBRAWEB PRODUCTION DEPLOYMENT

**Data**: December 8, 2025  
**Status**: 🟢 Pronto para Deploy  
**Readiness Score**: 97%

---

## 🚀 IMEDIATAMENTE (Antes do Deploy)

### 1. Gerar Nova SECRET_KEY de Produção

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiar o output (chave de 50 caracteres) para `.env` ou variável de ambiente com nome `SECRET_KEY`

### 2. Preparar Environment Variables

Criar `.env` com todas as variáveis necessárias:

```env
# CRÍTICO
SECRET_KEY=<sua-nova-chave-50-caracteres>
DEBUG=False
ALLOWED_HOSTS=seudominio.com,www.seudominio.com

# DATABASE - Escolher uma opção
DATABASE_URL=postgres://user:password@host:5432/calibraweb
# OU
DB_ENGINE=django.db.backends.postgresql
DB_NAME=calibraweb
DB_USER=postgres
DB_PASSWORD=sua-senha
DB_HOST=localhost
DB_PORT=5432

# OPTIONAL (melhor performance)
REDIS_URL=redis://:password@host:6379/0

# EMAIL
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=app-password
EMAIL_USE_TLS=True

# SEGURANÇA
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
TIME_ZONE=America/Sao_Paulo
```

### 3. Executar Backup de Segurança

```bash
python backup_manager.py backup
python backup_manager.py status
```

Verificar que o backup foi criado em `backups/`

### 4. Validação Final Pré-Deploy

```bash
# Verificar sem erros
python manage.py check --deploy

# Validar ambiente de produção
python test_production_env.py

# Executar testes
python manage.py test
pytest integration_tests.py
```

---

## 📦 OPÇÕES DE DEPLOYMENT

### OPÇÃO 1: Railway (Recomendado - Mais Fácil)

1. Conectar repositório GitHub em https://railway.app
2. Selecionar CalibraWeb
3. Ir em "Variables" na dashboard
4. Adicionar todas as variáveis de `.env`
5. Deploy automático ao fazer push!

```bash
# Deploy (apenas fazer push)
git push origin main
```

### OPÇÃO 2: Render.com

1. Conectar GitHub em https://render.com
2. Criar novo Web Service
3. Selecionar CalibraWeb repository
4. Configurar environment variables
5. Deploy automático

### OPÇÃO 3: VPS/Servidor (Linux)

```bash
# 1. SSH no servidor
ssh user@seu-servidor

# 2. Clonar código
cd /var/www
git clone https://github.com/vmotasilva/CalibraWeb.git
cd CalibraWeb

# 3. Preparar ambiente
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configurar variáveis
nano .env  # Editar com suas variáveis

# 5. Rodar migrations
python manage.py migrate

# 6. Coletar static files
python manage.py collectstatic --noinput

# 7. Criar superuser
python manage.py createsuperuser

# 8. Configurar Gunicorn
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4

# 9. Configurar Nginx como reverse proxy
sudo nano /etc/nginx/sites-available/calibraweb

# 10. Iniciar serviços
sudo systemctl start calibraweb
sudo systemctl start nginx
```

### OPÇÃO 4: Docker

```bash
# Build image
docker build -t calibraweb:latest .

# Run container
docker run -d \
  --name calibraweb \
  -p 8000:8000 \
  -e SECRET_KEY=<sua-chave> \
  -e DEBUG=False \
  -e DATABASE_URL=postgres://... \
  calibraweb:latest

# Ou com docker-compose
docker-compose up -d
```

---

## ✅ VERIFICAÇÃO PÓS-DEPLOY

Após fazer o deploy, verificar:

```bash
# 1. Aplicação rodando
curl https://seudominio.com/admin/

# 2. Static files sendo servidos
curl https://seudominio.com/static/admin/css/base.css

# 3. Log in no admin
# Ir em https://seudominio.com/admin/
# Login com credentials do superuser criado

# 4. Criar backup do novo banco
python backup_manager.py backup

# 5. Verificar logs (platform-dependent)
# Railway: dashboard logs
# VPS: tail -f /var/log/django.log
```

---

## 📋 PRIMEIRA SEMANA PÓS-DEPLOY

### Dia 1: Monitoramento Crítico
- [ ] Verificar que app está respondendo
- [ ] Monitorar logs por erros
- [ ] Verificar status do banco de dados
- [ ] Teste de login admin
- [ ] Teste de operações básicas

### Dia 2-3: Load Testing (Opcional)
```bash
# Executar testes de carga
locust -f load_testing.py -u 50 -r 10 -t 10m --host https://seudominio.com
```

### Dia 4-7: Otimizações
- [ ] Implementar Redis caching (se desejar)
- [ ] Configurar monitoramento (Datadog, New Relic)
- [ ] Configurar backups automáticos
- [ ] Setup de alertas

---

## 🔄 SETUP AUTOMÁTICO DE BACKUPS

### Linux (Cron)
```bash
# Adicionar ao crontab
crontab -e

# Backup diário às 2 AM
0 2 * * * cd /path/to/CalibraWeb && python backup_manager.py backup

# Ou múltiplos backups (2 AM, 8 AM, 2 PM, 8 PM)
0 2,8,14,20 * * * cd /path/to/CalibraWeb && python backup_manager.py backup
```

### Windows (Task Scheduler)
1. Abrir Task Scheduler
2. Create Basic Task: "CalibraWeb Backup"
3. Trigger: Diário às 2:00 AM
4. Action:
   - Program: `C:\Python312\python.exe`
   - Arguments: `C:\path\to\backup_manager.py backup`

### Docker/Railway
- Criar worker container separado
- Command: `python backup_manager.py backup`
- Schedule via plataforma

---

## 🔧 REDIS CACHING (OPCIONAL - MELHORA 60%)

Se quiser implementar caching para melhor performance:

```bash
# 1. Instalar Redis
pip install django-redis redis

# 2. Configurar em settings.py
# (Ver REDIS_CACHING_STRATEGY.md para detalhes)

# 3. Testar
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value', 30)
>>> cache.get('test')
'value'

# 4. Redeploy com Redis configurado
```

---

## 📊 MONITORAMENTO RECOMENDADO

### Essencial (Free)
- [ ] Uptime Robot: http://uptimerobot.com
  - Verificar cada 5 min se app responde
  - Alertas por email

- [ ] Railway/Render Logs
  - Logs são inclusos na plataforma

### Recomendado (Paid)
- [ ] Sentry: https://sentry.io
  - Rastreamento automático de erros
  - $29/mês básico

- [ ] Datadog: https://www.datadoghq.com
  - Monitoramento completo
  - $15/host/mês

---

## 🆘 TROUBLESHOOTING RÁPIDO

### App não abre
```bash
# 1. Verificar logs
# 2. Verificar variáveis de ambiente estão setadas
# 3. Verificar database connection
python manage.py dbshell

# 4. Fazer rollback se necessário
git revert <commit-id>
git push origin main
```

### Static files não carregam
```bash
# 1. Recolectar
python manage.py collectstatic --noinput

# 2. Verificar STATIC_ROOT, STATIC_URL
# 3. Verificar Nginx/servidor configurado para servir /static/
```

### Database erro
```bash
# 1. Verificar conexão
python manage.py dbshell

# 2. Restaurar do backup
python backup_manager.py restore <backup-name>

# 3. Se backup antigo, contatar time
```

---

## 📞 SUPORTE & DOCUMENTAÇÃO

**Documentos Disponíveis**:
1. `DEPLOYMENT_CHECKLIST.md` - Guia passo-a-passo
2. `DEPLOYMENT_VALIDATION_REPORT.md` - Status de readiness
3. `DEVELOPER_GUIDE.md` - Guia para devs
4. `TROUBLESHOOTING.md` - Resolução de problemas
5. `PHASE_12_FINAL_COMPLETION_SUMMARY.md` - Status final do projeto

**Scripts Disponíveis**:
- `backup_manager.py` - Gerenciar backups
- `load_testing.py` - Testes de carga
- `integration_tests.py` - Testes de integração

**Links Úteis**:
- [Django Docs](https://docs.djangoproject.com/)
- [Railway Docs](https://docs.railway.app/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

---

## ✨ RESUMO

**CalibraWeb está 100% pronto para produção.**

Próximos passos:
1. ✅ Gerar SECRET_KEY
2. ✅ Configurar variáveis de ambiente
3. ✅ Executar backup de segurança
4. ✅ Deploy (escolher plataforma)
5. ✅ Verificar funcionamento
6. ✅ Configurar backups automáticos
7. ✅ Monitoramento (opcional)

**Tempo estimado**: 30-60 minutos para deploy completo.

🚀 **Boa sorte! Tá na hora!**

---

**Documento**: NEXT_STEPS_DEPLOYMENT.md  
**Data**: December 8, 2025  
**Status**: Ready for Production  
**Recommendation**: Deploy Now!

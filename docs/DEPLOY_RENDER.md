# Deploy CalibraWeb no Render.com

## 🚀 Deploy Rápido (5 minutos)

### 1. Criar Conta Render
1. Acesse https://render.com
2. Cadastre-se (pode usar GitHub)

### 2. Conectar Repositório
1. No dashboard, clique **"New +"** → **"Blueprint"**
2. Conecte sua conta GitHub
3. Selecione o repositório **CalibraWeb**
4. Render detectará automaticamente o `render.yaml`

### 3. Confirmar Configuração
Render criará automaticamente:
- ✅ Web Service (Django app)
- ✅ PostgreSQL Database
- ✅ Redis (para Celery)

Variáveis de ambiente já estarão configuradas!

### 4. Aguardar Deploy
- Primeiro deploy leva ~5-10 minutos
- Render instala dependências, roda migrations, collectstatic
- Health check em `/healthz/` monitora status

### 5. Acessar Aplicação
Após deploy concluir, Render fornece URL:
```
https://calibraweb.onrender.com
```

## 🔧 Configuração Manual (se necessário)

### Variáveis de Ambiente Adicionais

No Render Dashboard → Service → Environment:

```bash
TIME_ZONE=America/Sao_Paulo
SECURE_HSTS_SECONDS=31536000
```

### Comandos Pós-Deploy

```bash
# Via Render Shell (Dashboard → Shell)
python manage.py createsuperuser
python manage.py rebuild_treinamentos
python manage.py cleanup_treinamentos
python manage.py sync_treinamentos
```

Ou crie um **Deploy Hook** para automatizar:

```yaml
# Adicionar ao render.yaml em web service:
buildCommand: |
  pip install -r requirements.txt && 
  python manage.py collectstatic --noinput && 
  python manage.py migrate --noinput
```

## 📊 Monitoramento

### Health Check
Render monitora automaticamente `/healthz/`

### Logs
```bash
# Via Dashboard: Logs tab
# Filtra por erro: Search "error" ou "exception"
```

### Métricas
- CPU, Memory, Request Rate disponíveis no Dashboard
- Alertas configuráveis (email/Slack)

## 🔄 Atualizações

```bash
# Local
git add .
git commit -m "Sua mensagem"
git push origin main
```

Render detecta push e redeploya automaticamente! 🎉

## 🆓 Limites Free Tier

- **Web Service:** 750 horas/mês (suficiente para 1 app 24/7)
- **PostgreSQL:** 90 dias free, depois $7/mês (1GB storage)
- **Redis:** 90 dias free, depois $10/mês
- **Sleep após 15min inatividade** (primeiro request demora ~30s)

### Evitar Sleep (opcional)
Use serviço como **UptimeRobot** ou **Cron-Job.org** para ping a cada 10 minutos:
```
https://calibraweb.onrender.com/healthz/
```

## 🐛 Troubleshooting

### Build Falha
```bash
# Verificar requirements.txt tem todas dependências
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update requirements"
git push
```

### Database Connection Error
- Verificar `DATABASE_URL` está injetada automaticamente
- Postgres leva ~2min para provisionar na primeira vez

### 502/503 Errors
- Check health endpoint: `curl https://calibraweb.onrender.com/healthz/`
- Verificar logs para traceback Django
- Confirmar migrations rodaram: Logs devem mostrar "Applying..."

### Static Files 404
```bash
# No render.yaml, confirme buildCommand tem:
python manage.py collectstatic --noinput
```

## 🔐 Backup Database

```bash
# Render fornece backups automáticos (paid plans)
# Export manual via Dashboard → Database → Backups
# Ou via pg_dump:
pg_dump $DATABASE_URL > backup.sql
```

## 📈 Upgrade para Paid

Benefícios:
- Sem sleep (always-on)
- Mais CPU/RAM
- Backups automáticos
- Priority support

Preços:
- Web Service: $7/mês (Starter)
- PostgreSQL: $7/mês (1GB) 
- Total: ~$14/mês para produção estável

## ✅ Checklist Deploy

- [ ] Repositório conectado ao Render
- [ ] render.yaml commitado
- [ ] Build completou sem erros
- [ ] Health check retorna 200 OK
- [ ] Superusuário criado
- [ ] Admin acessível (/admin/)
- [ ] Dados importados (procedimentos, colaboradores)
- [ ] Treinamentos sincronizados

## 🆘 Suporte

- Documentação: https://render.com/docs
- Community: https://community.render.com
- Status: https://status.render.com

---

**Vantagens Render vs Railway:**
✅ Mais estável (menos 502 errors)
✅ Health checks nativos
✅ Logs melhores
✅ PostgreSQL backups incluídos
✅ Suporte mais responsivo

**Desvantagens:**
⏰ Sleep após 15min (free tier)
💰 Paid plans necessários para always-on

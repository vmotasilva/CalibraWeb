# 🚀 DEPLOY EM PRODUÇÃO - GUIA COMPLETO

## ✅ Status Atual

```
✓ Código Committed: 3c51151
✓ Feature: Históricos de Calibração implementado
✓ Tests: Todos passando
✓ Django Check: Sem erros
✓ Repository: Sincronizado
```

## 🎯 Plataforma de Deploy

Este projeto está configurado para **Railway** (plataforma de deploy em nuvem).

### Por que Railway?
- ✅ Deployment automático ao fazer push
- ✅ Variáveis de ambiente gerenciadas
- ✅ Volumes persistentes para mídia
- ✅ Suporte a PostgreSQL
- ✅ Suporte a Redis
- ✅ Logs em tempo real
- ✅ SSL automático
- ✅ Domain automático

---

## 📋 PRÉ-REQUISITOS

Antes de fazer deploy, certifique-se de que tem:

1. **Conta Railway** (https://railway.app)
2. **GitHub conectado** ao Railway
3. **Variáveis de ambiente configuradas**
4. **PostgreSQL** provisionado
5. **Redis** provisionado
6. **Domínio personalizado** (opcional)

---

## 🔧 CONFIGURAÇÃO DE VARIÁVEIS

### 1. Acesse o Railway Dashboard
- Vá para https://railway.app
- Clique no seu projeto
- Vá em "Settings" → "Variables"

### 2. Adicione as Variáveis Essenciais

**DJANGO CORE:**
```
SECRET_KEY=<seu-secret-key-seguro>
DEBUG=False
ALLOWED_HOSTS=seu-dominio.railway.app,.railway.app
CSRF_TRUSTED_ORIGINS=https://seu-dominio.railway.app,https://*.railway.app
```

**DATABASE:**
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**REDIS:**
```
REDIS_URL=redis://default:password@host:port
CELERY_BROKER_URL=redis://default:password@host:port/0
CELERY_RESULT_BACKEND=redis://default:password@host:port/1
```

**EMAIL (Gmail/SMTP):**
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-app
DEFAULT_FROM_EMAIL=seu-email@gmail.com
```

**STORAGE (Opcional - AWS S3):**
```
USE_S3=True
AWS_ACCESS_KEY_ID=seu-access-key
AWS_SECRET_ACCESS_KEY=sua-secret-key
AWS_STORAGE_BUCKET_NAME=seu-bucket
AWS_S3_REGION_NAME=us-east-1
```

**ADMIN:**
```
ADMIN_USER=admin
ADMIN_PASSWORD=<senha-forte>
ADMIN_EMAIL=admin@empresa.com
```

---

## 🔐 Gerar SECRET_KEY Seguro

Executar localmente:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copie o resultado e cole em `SECRET_KEY` no Railway.

---

## 📊 ETAPAS DO DEPLOY

### Passo 1: Preparar o Código
```bash
cd c:\CalibraWeb

# Verificar status
git status

# Fazer commit (se houver mudanças)
git add -A
git commit -m "Production deployment - calibration history feature"

# Push para main
git push origin main
```

### Passo 2: Verificar Dockerfile
O Dockerfile está pronto em `c:\CalibraWeb\Dockerfile`:
- ✅ Multi-stage build
- ✅ Slim image (Python 3.12)
- ✅ Requirements otimizadas
- ✅ Gunicorn configurado
- ✅ Entrypoint com migrations

### Passo 3: Verificar railway.toml
O arquivo `railway.toml` está configurado:
```toml
[build]
builder = "dockerfile"

[deploy]
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5

[deploy.volumes]
media = "/data/media"
```

### Passo 4: Trigger Deploy no Railway

**Opção A - Push Automático (Recomendado)**
```bash
# Fazer push ativa o deploy automático
git push origin main
```

**Opção B - Manual no Dashboard**
1. Acesse https://railway.app
2. Clique no projeto
3. Clique em "Deploy" → "Redeploy"

### Passo 5: Monitorar Deploy
1. Vá para "Deployments"
2. Verifique o status do build
3. Acompanhe os logs em tempo real
4. Espere até ver "Successfully deployed"

### Passo 6: Executar Migrations
Após deployment bem-sucedido:
```bash
# Via SSH no Railway CLI:
railway shell -e production

# Dentro do shell:
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

---

## 🐛 TROUBLESHOOTING

### Build Failed
**Problema:** Build falha com erro de dependências
**Solução:**
```bash
# Atualizar requirements-prod.txt
pip install -r requirements.txt
pip freeze > requirements-prod.txt
git add requirements-prod.txt
git commit -m "Update production requirements"
git push origin main
```

### Database Connection Error
**Problema:** Cannot connect to PostgreSQL
**Solução:**
- Verificar `DATABASE_URL` no Railway
- Certificar que PostgreSQL service está running
- Checar firewall/security groups

### Static Files Not Loading
**Problema:** CSS/JS retorna 404
**Solução:**
```bash
# Executar no Railway shell:
python manage.py collectstatic --noinput --clear
```

### Redis Connection Error
**Problema:** Celery não consegue conectar ao Redis
**Solução:**
- Verificar `REDIS_URL` está correto
- Confirmar Redis service está running
- Testar conexão: `redis-cli -u $REDIS_URL`

---

## ✅ CHECKLIST POS-DEPLOYMENT

Após deploy bem-sucedido:

- [ ] Acesse a URL em produção
- [ ] Faça login com admin
- [ ] Teste o novo recurso "Históricos de Calibração"
- [ ] Clique no link Metrologia → Históricos de Calibração
- [ ] Teste os filtros
- [ ] Verifique as mensagens de erro no admin
- [ ] Teste upload de arquivos (se aplicável)
- [ ] Verifique logs do Celery
- [ ] Execute um teste de carga básico

---

## 📊 MONITORAR EM PRODUÇÃO

### Logs
```bash
# Via Railway CLI
railway logs

# Em tempo real
railway logs --follow
```

### Saúde da Aplicação
```bash
# Health check endpoint
curl https://seu-dominio.railway.app/health/
```

### Banco de Dados
```bash
# Conectar ao PostgreSQL
railway postgres shell

# Listar tabelas
\dt

# Verificar historicos de calibração
SELECT COUNT(*) FROM metrologia_historicocalibracao;
```

### Cache/Redis
```bash
# Testar conexão Redis
redis-cli -u $REDIS_URL ping
```

---

## 🔄 ATUALIZAÇÕES FUTURAS

Para fazer updates em produção:

```bash
# 1. Fazer mudanças locais
# 2. Testar localmente
# 3. Commit
git add -A
git commit -m "Update: descrição da mudança"

# 4. Push (ativa deploy automático)
git push origin main

# 5. Railway faz build e deploy automaticamente
# 6. Acompanhe em https://railway.app
```

---

## 🛡️ SEGURANÇA EM PRODUÇÃO

### Essencial
- [x] `DEBUG=False`
- [x] `SECRET_KEY` único e seguro
- [x] `ALLOWED_HOSTS` configurado
- [x] `CSRF_TRUSTED_ORIGINS` configurado
- [x] HTTPS habilitado (automático no Railway)
- [x] Senhas de admin fortes
- [x] Email de admin configurado

### Recomendado
- [x] Backup automático do banco de dados
- [x] Logs centralizados
- [x] Monitoramento de performance
- [x] Alertas para erros
- [x] Rate limiting
- [x] WAF (Web Application Firewall)

---

## 📞 SUPORTE

Para problemas:

1. Verifique a documentação do Railway
2. Leia os logs em tempo real
3. Teste localmente em ambiente similar
4. Verifique variáveis de ambiente
5. Reinicie os serviços

---

## 📈 PRÓXIMOS PASSOS POS-DEPLOY

Após confirmar que tudo está funcionando:

1. **Backup do Banco**
   - Configure backups automáticos
   - Teste restauração

2. **Monitoramento**
   - Configure alertas
   - Monitore performance

3. **Analytics**
   - Implemente rastreamento
   - Monitore uso de features

4. **Segurança**
   - Faça auditoria
   - Configure WAF

5. **Otimização**
   - Analise performance
   - Otimize queries lentas

---

**Status:** ✅ **PRONTO PARA DEPLOY**

**Data:** 09/01/2026 | **Versão:** 1.0

```
╔════════════════════════════════════════════════════════════╗
║  Seu código está pronto para produção!                      ║
║                                                             ║
║  Próximo passo: Push para Railway (automático) ou           ║
║  Execute manualmente deploy no dashboard do Railway         ║
╚════════════════════════════════════════════════════════════╝
```

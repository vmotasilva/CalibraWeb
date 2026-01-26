# Guia Rápido: Deploy no Railway

## 1. Configuração Inicial

### Criar Projeto no Railway
1. Acesse [railway.app](https://railway.app)
2. Clique em "New Project"
3. Escolha "Deploy from GitHub repo"
4. Selecione o repositório `CalibraWeb`

### Adicionar PostgreSQL
1. No projeto, clique em "+ New"
2. Escolha "Database" → "PostgreSQL"
3. Aguarde a criação (Railway automaticamente configura as variáveis PG*)

## 2. Configurar Variáveis de Ambiente

Vá no serviço **web** → aba **Variables** e adicione:

```bash
SECRET_KEY=<gere-uma-chave-secreta>
DEBUG=False
ALLOWED_HOSTS=<seu-dominio>.up.railway.app,.railway.app
CSRF_TRUSTED_ORIGINS=https://<seu-dominio>.up.railway.app,https://*.railway.app
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=<senha-forte>
TIME_ZONE=America/Sao_Paulo
```

### Gerar SECRET_KEY
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. Configurar Domínio

No serviço **web** → **Settings** → **Networking**:
- Clique em "Generate Domain"
- Railway criará algo como: `calibraweb.up.railway.app`
- Use esse domínio nas variáveis `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`

## 4. Deploy Automático

O Railway detecta automaticamente:
- `Dockerfile` para build
- `railway.toml` para configurações
- Push no GitHub dispara redeploy automático

## 5. Verificar Deploy

### Via Web
- **Health**: `https://<seu-dominio>.up.railway.app/healthz` → deve retornar 200
- **Admin**: `https://<seu-dominio>.up.railway.app/admin/` → login

### Via Railway Shell
Clique no serviço **web** → aba **Shell** ou clique nos 3 pontos → "Shell"

```bash
# Verificar conexão com banco
python manage.py check --database default

# Ver migrações aplicadas
python manage.py showmigrations

# Criar superuser (se não usou ensure_superuser)
python manage.py createsuperuser

# Coletar arquivos estáticos manualmente (se necessário)
python manage.py collectstatic --noinput
```

## 6. Logs e Debugging

- **Logs em tempo real**: Aba "Deployments" → clique no deploy → "View Logs"
- **Logs de runtime**: Aba "Observability" ou clique nos 3 pontos → "View Logs"

### Comandos úteis no Shell:
```bash
# Ver últimas 100 linhas de log
railway logs --lines 100

# Seguir logs em tempo real
railway logs --follow
```

## 7. Troubleshooting Comum

### Erro: "could not translate host name"
- ✅ **Resolvido**: O código agora usa variáveis PG* do Railway
- Verifique se o PostgreSQL está conectado ao serviço web

### Erro: "DisallowedHost"
- Adicione seu domínio em `ALLOWED_HOSTS`
- Exemplo: `calibraweb.up.railway.app`

### Erro: "Forbidden (403) CSRF"
- Adicione seu domínio em `CSRF_TRUSTED_ORIGINS`
- Exemplo: `https://calibraweb.up.railway.app`

### Healthcheck falhando
- Verifique se `/healthz` retorna 200
- Confirme `healthcheckPath` no `railway.toml` está correto
- Aguarde migrations completarem (pode levar 1-2 minutos no primeiro deploy)

### Static files não carregam
- Verifique logs: `collectstatic` deve rodar em `start.sh`
- Confirme `STATIC_ROOT` e `STATICFILES_STORAGE` em settings.py

## 8. Estrutura de Arquivos Importantes

```
CalibraWeb/
├── railway.toml          # Configurações Railway (builder, healthcheck)
├── Dockerfile            # Build da imagem
├── Procfile             # Processos (web, worker, beat)
├── start.sh             # Script de inicialização (migrations + collectstatic)
├── requirements.txt     # Dependências Python
└── config/
    └── settings.py      # Configurações Django
```

## 9. Comandos Railway CLI (opcional)

Instale: `npm i -g @railway/cli`

```bash
# Login
railway login

# Linkar projeto
railway link

# Ver variáveis
railway variables

# Abrir shell
railway shell

# Ver logs
railway logs

# Deploy manual
railway up
```

## 10. Próximos Passos

- [ ] Configurar domínio customizado (se necessário)
- [ ] Habilitar Celery worker/beat (se usar tarefas em background)
- [ ] Configurar Redis (se usar cache ou Celery)
- [ ] Configurar email SMTP (para recuperação de senha)
- [ ] Adicionar monitoring/alertas

## Recursos

- [Documentação Railway](https://docs.railway.app)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/settings.html)

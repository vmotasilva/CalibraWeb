# 🚀 INSTRUÇÕES PÓS-DEPLOYMENT - RAILWAY

## ✅ Implementação Concluída com Sucesso!

Sua aplicação foi enviada para o Railway e está em processo de deploy automático.

---

## ⏱️ TIMELINE DO DEPLOYMENT

### O que já foi feito:
- ✅ Código implementado e testado localmente
- ✅ Commits criados (3 commits)
- ✅ Push para GitHub realizado
- ✅ Railway detectou novos commits
- ✅ Build Docker iniciado

### O que está acontecendo agora:
- ⏳ Build Docker: Instalando dependências, compilando imagem
- ⏳ Deploy: Enviando nova versão
- ⏳ Migrations: Aplicando ao banco PostgreSQL
- ⏳ Startup: Iniciando serviços

### Tempo esperado: **5-10 minutos até estar 100% live**

---

## 🔍 MONITORAR DEPLOYMENT

### Método 1: Railway Dashboard (Recomendado)
```
1. Acesse: https://railway.app/dashboard
2. Faça login com GitHub
3. Selecione projeto: CalibraWeb
4. Clique em "Deployments"
5. Veja o build em tempo real
6. Quando ficar 🟢 GREEN = Pronto!
```

### Método 2: Railway CLI
```bash
# Terminal PowerShell
railway login
railway logs --follow

# Saída esperada:
# ==> Checking database connection...
# ==> Running database migrations...
# ==> Collecting static files...
# ==> Starting Gunicorn server...
# ✓ Health check passed
```

### Método 3: Verificar Status
```bash
# Quando o deploy terminar:
curl https://calibraweb.up.railway.app/healthz/

# Resposta esperada: 
# {"status": "ok", "timestamp": "..."}
```

---

## 🌐 TESTAR A APLICAÇÃO

### Quando o Deploy Terminar (5-10 min):

#### 1. Acessar a Aplicação
```
URL: https://calibraweb.up.railway.app/
Esperado: Página de login ou dashboard
Status: 200 OK
```

#### 2. Fazer Login
```
Admin URL: https://calibraweb.up.railway.app/admin/
Usuário: admin (ou conforme criado localmente)
```

#### 3. Testar Novo Feature
```
1. Ir para: /metrologia/categorias/
2. Clicar em uma categoria
3. Procurar pela tabela "Instrumentos Cadastrados"
4. Marcar checkboxes de instrumentos
5. Clicar botão "Mover para esta categoria"
6. Confirmar na dialog
7. Verificar se funcionou ✅
```

#### 4. Verificar API
```
URL: https://calibraweb.up.railway.app/api/metrologia/
Esperado: JSON com dados de metrologia
```

---

## 📊 O QUE FOI DEPLOYADO

### Feature Principal: Alteração em Massa de Categoria

```
Página: Detalhe de Categoria
Novo:   Checkboxes em tabela de instrumentos
Novo:   Botão "Selecionar Todos"
Novo:   Barra de ações em massa
Novo:   Botão "Mover para esta categoria"
Novo:   Confirmação com dialog
Novo:   Validação automática
Result: Instrumentos movidos com sucesso
```

### Commits Enviados:

1. **Feature**: `8d08436`
   - Adicionado `instrumento_bulk_change_category_view()`
   - Adicionada URL `/categorias/{id}/instrumento/alterar-categoria-em-massa/`
   - Modificado `categoria_detail.html` com checkboxes
   - Adicionado JavaScript para gestão de seleção

2. **Documentação**: `6fce1b5` + `f351855`
   - Status de deployment
   - Guia rápido
   - Checklists
   - Troubleshooting

---

## ⚠️ SE ALGO DER ERRADO

### Erro 404 - Página Não Encontrada
```
Causa: App ainda não iniciou
Solução: Aguardar mais 2-3 minutos
Verificar: Dashboard → Deployments → Status
```

### Erro 500 - Server Error
```
Causa: Possível erro nas migrations ou startup
Solução: Ver logs no Railway Dashboard
Comando: railway logs --follow
Procurar por: "ERROR", "exception", "traceback"
```

### Database Connection Failed
```
Causa: PostgreSQL não está acessível
Solução: Verificar DATABASE_URL no Railway
Dashboard → Environment variables → Editar
```

### Migration Failed
```
Causa: Schema incompatível
Solução: Via Railway Shell
  railway shell
  python manage.py migrate --noinput
```

### App Keeps Restarting
```
Causa: Erro no código ou configuração
Solução: 
  1. Ver logs completos
  2. Revisar error traceback
  3. Corrigir localmente
  4. Fazer novo push
  5. Novo deployment automático
```

---

## 🔧 EMERGENCY PROCEDURES

### Via Railway Shell

```bash
# Acessar console interativo
railway shell

# Verificar banco de dados
python manage.py dbshell

# Aplicar migrations manualmente
python manage.py migrate --noinput

# Criar superuser
python manage.py createsuperuser

# Testar import
python manage.py shell
>>> from metrologia.models import CategoriaInstrumento
>>> CategoriaInstrumento.objects.count()
```

### Restart Aplicação

```bash
# Via Railway CLI
railway restart

# Via Dashboard
1. Railway → Service → Restart button
```

### Ver Variáveis de Ambiente

```bash
railway variables

# Saída esperada:
# DATABASE_URL=postgresql://...
# SECRET_KEY=...
# DEBUG=false
# etc
```

---

## 📈 MONITORAMENTO PÓS-DEPLOY

### Checklist de Validação

Após o deployment estar 🟢 GREEN:

- [ ] App responde em https://calibraweb.up.railway.app/
- [ ] Admin panel acessível em /admin/
- [ ] Login funciona
- [ ] Categorias carregam em /metrologia/categorias/
- [ ] Novo feature: checkboxes aparecem
- [ ] Novo feature: botão "Mover" funciona
- [ ] API responde em /api/metrologia/
- [ ] Health check passa em /healthz/
- [ ] Nenhum erro 500 nos logs
- [ ] Database está conectado
- [ ] Redis cache funcionando

### Logs para Revisar

```
Sucesso esperado:
✓ "Checking database connection..."
✓ "Running database migrations..."
✓ "Collecting static files..."
✓ "Starting Gunicorn server..."
✓ "Listening at: http://0.0.0.0:8000"
✓ "Workers booted: 3"

Erros a evitar:
✗ "ERROR"
✗ "FATAL"
✗ "exception"
✗ "ConnectionRefused"
✗ "MigrationError"
```

---

## 🎯 PRÓXIMOS PASSOS RECOMENDADOS

### Imediato (0-5 min):
1. Monitorar logs no Dashboard
2. Aguardar build completar

### Curto Prazo (5-10 min):
1. Acessar aplicação
2. Testar novo feature
3. Validar funcionalidades críticas
4. Revisar erros nos logs

### Médio Prazo (30+ min):
1. Testes de carga (se aplicável)
2. Configurar monitoramento
3. Setup de alertas
4. Documentar runbooks
5. Treinar usuários

---

## 📞 RECURSOS ÚTEIS

### Links Importantes
```
Railway Dashboard:        https://railway.app/dashboard
GitHub Repo:             https://github.com/vmotasilva/CalibraWeb
Aplicação Produção:      https://calibraweb.up.railway.app/
Documentation:           https://docs.railway.app/
```

### Comandos Rápidos
```bash
# Railway CLI
railway login
railway logs --follow
railway shell
railway variables
railway restart

# PostgreSQL via shell
psql -U postgres
\dt metrologia_*
SELECT COUNT(*) FROM metrologia_categoriainstrumento;
```

### Tech Stack Produção
```
Python:         3.12
Django:         5.0.14
Database:       PostgreSQL 14+
Cache:          Redis
Task Queue:     Celery
WSGI Server:    Gunicorn (3 workers)
Platform:       Railway.app (Free tier)
Container:      Docker
```

---

## 🎓 DICAS IMPORTANTES

1. **Não deletar dados em produção** - Sempre fazer backup primeiro
2. **Sempre testar localmente** - Antes de fazer push
3. **Revisar logs regularmente** - Para detectar problemas cedo
4. **Manter documentação atualizada** - Para futuras manutenções
5. **Usar Railway CLI localmente** - Para troubleshooting rápido

---

## 🎉 CONCLUSÃO

Sua aplicação está em transição para produção!

**Status:** 🟡 Em Deployment  
**Próxima Etapa:** Aguardar 5-10 minutos  
**Resultado Esperado:** 🟢 Go Live  

**Parabéns pelo deploy bem-sucedido! 🚀**

---

*Instruções geradas em: 17 de Dezembro de 2025*  
*Plataforma: Railway.app*  
*Versão: 2025-12-17*

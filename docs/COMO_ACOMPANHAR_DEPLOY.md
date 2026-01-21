# 🎯 COMO ACOMPANHAR O DEPLOY EM PRODUÇÃO

## 📊 Estado Atual

```
✅ Código Pronto
✅ GitHub Sincronizado
✅ Commits: 3 (3c51151, 58099bd, c885166)
✅ Documentação Completa
⏳ Aguardando Deploy no Railway
```

---

## 🚀 PASSO A PASSO PARA DEPLOY

### PASSO 1: Acessar Railway Dashboard

1. Acesse: https://railway.app
2. Faça login com sua conta
3. Clique no projeto "CalibraWeb"

### PASSO 2: Configurar Variáveis de Ambiente

1. Vá em: **Settings** → **Variables**
2. Copie as variáveis do arquivo `.env.railway.example`:
   ```
   SECRET_KEY=<gere um novo>
   DEBUG=False
   ALLOWED_HOSTS=seu-dominio.up.railway.app,.railway.app
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://...
   CELERY_BROKER_URL=redis://...
   EMAIL_HOST=smtp.gmail.com
   EMAIL_HOST_USER=seu-email@gmail.com
   EMAIL_HOST_PASSWORD=app-password
   ```

3. Clique em "Save" para cada variável

### PASSO 3: Iniciar Deploy

**Opção A - Automático (Recomendado):**
```bash
cd c:\CalibraWeb
git push origin main
# Railway detecta automaticamente e inicia o build
```

**Opção B - Manual:**
1. No Railway Dashboard
2. Vá em: **Deployments**
3. Clique em: **Deploy latest commit** ou **Redeploy**
4. Selecione o commit `c885166` (mais recente)
5. Clique em **Deploy**

### PASSO 4: Acompanhar o Build

1. No Dashboard, vá em: **Deployments**
2. Você verá um novo deployment em andamento
3. Clique nele para ver o progresso em tempo real
4. Os logs aparecem em tempo real

**Etapas do Build:**
```
1. Building Docker image...     (2-3 min)
2. Pushing to registry...       (1 min)
3. Deploying...                 (1 min)
4. Running migrations...        (1 min)
5. Collecting static files...   (1 min)
6. Starting services...         (1 min)

Total esperado: 7-10 minutos
```

### PASSO 5: Verificar Build Bem-Sucedido

**Indicadores de Sucesso:**
- ✅ Status muda para "Success" (verde)
- ✅ Aplicação fica acessível na URL
- ✅ Logs não mostram erros

**Indicadores de Falha:**
- ❌ Status mostra "Failed" (vermelho)
- ❌ Erros nos logs
- ❌ URL não responde

### PASSO 6: Pós-Deploy (Se necessário)

Se o build passou mas há erro nos logs:

```bash
# Conectar ao Railway
railway shell -e production

# Dentro do container
python manage.py migrate
python manage.py createsuperuser  # Se não existir
python manage.py collectstatic --noinput --clear

# Sair
exit
```

### PASSO 7: Testar em Produção

1. Acesse: `https://seu-dominio.up.railway.app`
2. Faça login com admin
3. Vá em: **Metrologia** → **Históricos de Calibração**
4. Teste os filtros
5. Navegue as páginas
6. Verifique funcionamento completo

---

## 📈 MONITORAR O DEPLOYMENT

### Via Railway Dashboard

**Logs em Tempo Real:**
```
1. Vá em: Deployments → [Seu Deployment]
2. Veja os logs atualizando em tempo real
3. Procure por erros ou warnings
```

**Métricas:**
```
1. Vá em: Metrics
2. Veja CPU, Memória, Requisições
3. Monitore performance
```

**Variáveis:**
```
1. Vá em: Settings → Variables
2. Verifique se todas estão configuradas
3. Confira valores críticos
```

### Via Railway CLI

```bash
# Instalar (se não tiver)
npm install -g @railway/cli

# Fazer login
railway login

# Ver logs em tempo real
railway logs --follow

# Ver status
railway status

# Conectar ao container
railway shell

# Sair do shell
exit
```

### Health Check

```bash
# Verificar saúde da aplicação
curl https://seu-dominio.up.railway.app/health/

# Resposta esperada
{"status": "ok"}
```

---

## 🔍 TROUBLESHOOTING DURANTE DEPLOY

### Build Falha com Erro de Dependências

**Sintoma:** `Failed to install requirements`

**Solução:**
```bash
cd c:\CalibraWeb
pip install -r requirements-prod.txt
pip freeze > requirements-prod.txt
git add requirements-prod.txt
git commit -m "Fix: update production requirements"
git push origin main
# Railway vai retentar automaticamente
```

### Database Connection Error

**Sintoma:** `psycopg2.OperationalError`

**Verificar:**
1. Variável `DATABASE_URL` está correta?
2. PostgreSQL service está rodando?
3. Firewall permite a conexão?

**Solução:**
```bash
railway shell
python manage.py dbshell  # Testa conexão
\dt  # Lista tabelas
```

### Static Files Retorna 404

**Sintoma:** CSS/JS não carrega

**Solução:**
```bash
railway shell
python manage.py collectstatic --noinput --clear
exit
```

### Redis Connection Error

**Sintoma:** Celery não conecta

**Verificar:**
```bash
railway shell
redis-cli -u $REDIS_URL ping
# Resposta: PONG (se OK)
```

### Migrations Não Executam

**Sintoma:** Banco sem dados

**Solução:**
```bash
railway shell
python manage.py migrate
python manage.py createsuperuser
```

---

## ✅ CHECKLIST PÓS-DEPLOY

Após o deployment estar bem-sucedido:

- [ ] URL está acessível
- [ ] Página carrega em < 2s
- [ ] Login funciona
- [ ] Dashboard carrega
- [ ] Metrologia → Históricos de Calibração acessível
- [ ] Tabela de históricos mostra dados
- [ ] Filtros funcionam
- [ ] Paginação funciona
- [ ] Downloads de certificados funcionam
- [ ] Sem erros nos logs
- [ ] Email de contato funciona
- [ ] Celery worker rodando
- [ ] Redis conectado
- [ ] Database responsivo

---

## 📞 CONTATOS SUPORTE

### Railway Support
- **Site:** https://railway.app
- **Docs:** https://docs.railway.app
- **Status:** https://status.railway.app
- **Email:** support@railway.app

### Django Documentation
- **Docs:** https://docs.djangoproject.com
- **Forum:** https://forum.djangoproject.com

### PostgreSQL
- **Docs:** https://postgresql.org/docs

### Redis
- **Docs:** https://redis.io/documentation

---

## 🎯 PRÓXIMOS PASSOS APÓS DEPLOY

### Imediato
1. Notificar usuários sobre novo recurso
2. Providenciar treinamento básico
3. Monitorar feedback

### Curto Prazo (1 semana)
1. Coletar feedback de usuários
2. Analisar performance
3. Corrigir bugs encontrados

### Médio Prazo (1 mês)
1. Analisar uso da feature
2. Otimizar queries lentas
3. Implementar melhorias solicitadas

### Longo Prazo
1. Adicionar novos filtros
2. Implementar exportação para Excel
3. Adicionar gráficos de análise

---

## 📊 MONITORAMENTO CONTÍNUO

### Métricas a Acompanhar

```
1. Tempo de Resposta
   - Target: < 500ms
   - Alarme: > 2000ms

2. Taxa de Erro
   - Target: < 0.1%
   - Alarme: > 1%

3. Uso de CPU
   - Target: < 50%
   - Alarme: > 80%

4. Uso de Memória
   - Target: < 60%
   - Alarme: > 90%

5. Requisições/Minuto
   - Monitor: Picos de uso
```

### Configurar Alertas

No Railway Dashboard:
1. Vá em: **Settings** → **Alerts**
2. Configure alertas para:
   - High CPU usage
   - High memory usage
   - Deployment failures
   - Database issues

---

## 🎊 SUCESSO!

Quando você vir:

```
╔═══════════════════════════════════════════════════════╗
║  ✅ Deployment Successful                            ║
║  ✅ Application Running                              ║
║  ✅ URL Accessible                                   ║
║  ✅ Feature Visible                                  ║
║                                                      ║
║  Parabéns! Deploy em produção concluído!            ║
╚═══════════════════════════════════════════════════════╝
```

---

**Dúvidas?** Consulte os arquivos de documentação:
- `DEPLOY_PRODUCAO_GUIA_COMPLETO.md`
- `CHECKLIST_DEPLOY_PRODUCAO.md`
- `DEPLOYMENT_READY_RESUMO_EXECUTIVO.md`

**Data:** 09/01/2026 | **Status:** ✅ Pronto para Deploy

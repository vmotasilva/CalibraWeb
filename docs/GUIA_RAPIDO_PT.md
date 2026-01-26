# ⚡ GUIA RÁPIDO - DEPLOYMENT RAILWAY (PT-BR)

## 🚀 Você está aqui: DEPLOYMENT EM PROGRESSO

---

## ⏱️ O QUE FAZER AGORA (Próximos 10 minutos)

### 1️⃣ ACOMPANHAR O BUILD (Agora)

**Opção A: Dashboard (Fácil)**
1. Acesse: https://railway.app/dashboard
2. Selecione: Projeto "CalibraWeb"
3. Clique: Aba "Deployments"
4. Observe: Build Docker em tempo real
5. Quando ficar 🟢 GREEN = Pronto!

**Opção B: Terminal (Se tiver Railway CLI instalado)**
```bash
railway login
railway logs --follow
```

### 2️⃣ QUANDO DEPLOY TERMINAR (5-10 minutos)

Acesse sua aplicação em produção:
```
https://calibraweb.up.railway.app/
```

**Esperado:** Página de login ou dashboard  
**Status:** 200 OK  
**BD:** PostgreSQL (gerenciado pelo Railway)  

### 3️⃣ TESTAR NOVO FEATURE

1. Faça login em produção
2. Vá para: `/metrologia/categorias/`
3. Clique em qualquer categoria
4. Procure por: Tabela "Instrumentos Cadastrados"
5. Marque checkboxes de instrumentos
6. Clique: "Mover para esta categoria"
7. Confirme na dialog
8. ✅ Pronto! Feature funcionando!

---

## 📊 O QUE FOI ENTREGUE

✅ Feature: **Alteração em Massa de Categoria de Instrumentos**

Permite selecionar vários instrumentos e movê-los para a categoria de uma vez, em vez de um por um.

**Como funciona:**
- Checkboxes para cada instrumento
- "Selecionar Todos" para conveniência
- Barra de ações com contador
- Botão "Mover para esta categoria"
- Confirmação antes de executar
- Mensagem de sucesso

---

## 🔍 SE ALGO DER ERRADO

### Error 404 (Página não encontrada)
```
Causa:    App ainda não iniciou
Solução:  Aguarde 2-3 minutos extras
Verificar: Dashboard → Status deve ser 🟢 GREEN
```

### Error 500 (Server Error)
```
Causa:    Erro durante o startup
Solução:  Ver logs no Railway Dashboard
Procurar: Mensagens de erro, SQL exceptions
```

### Error "Cannot connect to database"
```
Causa:    PostgreSQL não está acessível
Solução:  Verificar DATABASE_URL está correto
Check:    Dashboard → Environment Variables
```

### App fica reiniciando infinitamente
```
Causa:    Erro no código ou startup script
Solução:  Ver logs completos
Action:   Possivelmente precisa corrigir e fazer novo push
```

---

## 🎓 URLS E ENDPOINTS

### Produção (após deploy)
```
App:        https://calibraweb.up.railway.app/
Admin:      https://calibraweb.up.railway.app/admin/
Categorias: https://calibraweb.up.railway.app/metrologia/categorias/
API:        https://calibraweb.up.railway.app/api/metrologia/
Health:     https://calibraweb.up.railway.app/healthz/
```

### Local (agora)
```
App:        http://127.0.0.1:8000/
Admin:      http://127.0.0.1:8000/admin/
Categorias: http://127.0.0.1:8000/metrologia/categorias/
API:        http://127.0.0.1:8000/api/metrologia/
```

---

## 📞 EMERGÊNCIA - SHELL DE PRODUÇÃO

Se precisar acessar a produção via terminal:

```bash
# Via Railway CLI
railway shell

# Você está dentro da shell de produção, pode fazer:
python manage.py migrate
python manage.py createsuperuser
python manage.py shell

# Ver variáveis de ambiente
railway variables

# Restart app
railway restart
```

---

## 📚 DOCUMENTAÇÃO COMPLETA

Se precisar de mais detalhes, leia:

1. **EXECUTIVE_SUMMARY_DEPLOYMENT.md** (Resumo técnico)
2. **POST_DEPLOYMENT_INSTRUCTIONS.md** (Troubleshooting)
3. **INDEX_DEPLOYMENT_17_12.md** (Índice de tudo)

---

## ✅ CHECKLIST FINAL

- [ ] Leu este guia
- [ ] Acompanhou o build no Dashboard
- [ ] Aplicação ficou 🟢 GREEN
- [ ] Acessou: https://calibraweb.up.railway.app/
- [ ] Fez login com sucesso
- [ ] Testou novo feature (checkboxes)
- [ ] Verificou se não há erros nos logs
- [ ] Comunicou go-live ao time

---

## 🎉 PARABÉNS!

Seu deployment está em progresso!

**Próxima etapa:** Aguarde 5-10 minutos e a aplicação estará 100% live.

**Dashboard para monitorar:**
👉 https://railway.app/dashboard

---

*Desenvolvido em: 17 de Dezembro de 2025*

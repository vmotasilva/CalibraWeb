# 🚀 DEPLOY RENDER - INSTRUÇÕES RÁPIDAS

## 📋 Pré-requisito: Git Push

```powershell
cd c:\CalibraWeb

# Verificar status
git status

# Se houver mudanças não commitadas:
git add .
git commit -m "feat: Alteração em massa de categoria de instrumentos"

# Fazer push para origin main
git push origin main
```

## ✨ Deploy Automático

Após o `git push origin main`:

1. **Acessar Dashboard Render:**
   - https://dashboard.render.com
   - Login com sua conta (GitHub)

2. **Monitorar Deploy:**
   - Selecionar o serviço **calibraweb**
   - Clicar em **"Deployments"**
   - Acompanhar o build em tempo real
   - Tempo estimado: **5-10 minutos**

3. **Verificar Status:**
   - Quando ficar **green** = Deploy concluído
   - URL: https://calibraweb.onrender.com

## 🌐 Acessar Produção

Quando deployment concluir:

- **Aplicação:** https://calibraweb.onrender.com
- **Admin:** https://calibraweb.onrender.com/admin/
- **Categorias:** https://calibraweb.onrender.com/metrologia/categorias/
- **Health:** https://calibraweb.onrender.com/healthz/

## ✅ Checklist Pós-Deploy

- [ ] Site carrega sem erro 404/500
- [ ] Login funciona
- [ ] Categorias carregam
- [ ] Faixas de medição aparecem
- [ ] **Novo:** Checkboxes para alterar categoria em massa funcionam
- [ ] API responde: `/api/metrologia/`

## 🔧 Se Algo der Errado

1. **Verificar Logs:**
   - Dashboard → Logs → Ir para Browser
   - Procurar por erro 500 ou traceback

2. **Troubleshooting Comum:**
   ```bash
   # Acessar shell de produção (no Render):
   python manage.py migrate  # Se migration falhou
   python manage.py collectstatic --noinput  # Ativos estáticos
   ```

3. **Contato com Suporte Render:**
   - Dashboard → Notifications → Support

---

## 📊 Resumo do Release

**Versão:** 2025-12-17  
**Feature Principal:** Alteração em Massa de Categoria de Instrumentos  
**Status:** ✅ Testado e Pronto

### O que foi adicionado:
- ✅ Checkboxes em tabela de instrumentos
- ✅ Botão "Selecionar Todos"
- ✅ Barra de ações em massa
- ✅ Botão "Mover para esta categoria"
- ✅ Validação de dados
- ✅ Confirmação antes de executar

### Tecnologias:
- Django 5.0.14
- PostgreSQL (prod) / SQLite (dev)
- Redis para cache
- Celery para tasks
- Bootstrap 5 UI

---

**Desenvolvido:** 17 de Dezembro de 2025  
**Repositório:** vmotasilva/CalibraWeb

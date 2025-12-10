# 🎉 OPÇÃO 1 - CREDENCIAIS E INÍCIO RÁPIDO

## ⚡ CREDENCIAIS PARA TESTE LOCAL

```
Username: admin
Password: TestPass123456!@#
Email:   admin@calibraweb.local
```

✅ **Superuser já criado e verificado**

---

## 🌐 ACESSAR AGORA

| Serviço | URL | Status |
|---------|-----|--------|
| Django Admin | http://127.0.0.1:8000/admin/ | ⏳ Após iniciar |
| Cache Dashboard | http://127.0.0.1:8000/dashboard/ | ⏳ Após iniciar |
| API Base | http://127.0.0.1:8000/api/ | ⏳ Após iniciar |

---

## 📖 GUIAS DISPONÍVEIS

### **COMECE AQUI:**
👉 **`OPCAO_1_PASSO_A_PASSO.md`**
- Guia visual de 5 passos
- Instruções copy-paste prontas
- Troubleshooting incluído
- 30 minutos para completar

### **REFERÊNCIA RÁPIDA:**
📄 **`LOCAL_TESTING_CREDENTIALS.md`**
- Como usar as credenciais
- 3 formas diferentes de criar admin
- URLs de acesso
- Testes de funcionalidade
- Notas de segurança

### **SCRIPT PRONTO:**
🔧 **`create_test_admin.py`**
- Execute se precisar recriar admin
- Comando: `python create_test_admin.py`

---

## ⚡ QUICK START (Copiar-Colar)

### Terminal 1: Já rodando ✅
```powershell
# Redis Mock Server (não fazer nada, já está rodando)
```

### Terminal 2: Celery Worker
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
celery -A config worker -l info
```

### Terminal 3: Celery Beat
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
celery -A config beat -l info
```

### Terminal 4: Django Server
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py runserver
```

### Terminal 5: Cache Dashboard
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py cache_dashboard --live --interval 2
```

---

## 🧪 TESTAR

Após iniciar todos os 5 serviços:

1. **Django Admin**
   - Abra: http://127.0.0.1:8000/admin/
   - Login: admin / TestPass123456!@#

2. **Cache Dashboard**
   - Abra: http://127.0.0.1:8000/dashboard/
   - Veja métricas em tempo real

3. **Testes**
   ```powershell
   python manage.py test qms --verbosity=2
   ```
   Esperado: 94 testes passando

---

## ✅ CHECKLIST

Antes de considerar pronto:

- [ ] Terminal 1: Redis rodando (com logs)
- [ ] Terminal 2: Celery Worker pronto ("ready to accept tasks")
- [ ] Terminal 3: Celery Beat agendando ("Launching tasks")
- [ ] Terminal 4: Django rodando (http://127.0.0.1:8000/)
- [ ] Terminal 5: Dashboard rodando (http://127.0.0.1:8000/dashboard/)
- [ ] Admin login funciona com credenciais
- [ ] Dashboard mostra gráficos/dados
- [ ] Testes passam (94/94)
- [ ] Sem erros em nenhum terminal
- [ ] Git status limpo

✅ **Se tudo acima está marcado, Opção 1 COMPLETA!**

---

## 📊 PRÓXIMA ETAPA

Quando satisfeito com testes locais:

1. **Parar serviços**: Ctrl+C em cada terminal
2. **Próximo**: Abrir `STAGING_ACTION_PLAN.md`
3. **Escolher**: Uma das 3 opções de deploy
4. **Deploy**: Para staging ou produção

---

## 📚 DOCUMENTAÇÃO COMPLETA DISPONÍVEL

- `OPCAO_1_PASSO_A_PASSO.md` ← **COMECE AQUI**
- `LOCAL_TESTING_CREDENTIALS.md` ← Referência
- `STAGING_ACTION_PLAN.md` ← Próxima etapa
- `DEPLOYMENT_GUIDE.md` ← Guia completo
- `ARCHITECTURE_OVERVIEW.md` ← Design do sistema
- `MULTILEVEL_CACHE.md` ← Cache técnico
- `CACHE_DASHBOARD.md` ← Monitoramento

---

## ⏱️ TEMPO TOTAL

| Fase | Tempo |
|------|-------|
| Setup (4 terminais) | 5 min |
| Testes/Exploração | 15 min |
| Dashboard/Validação | 10 min |
| **TOTAL** | **30 min** |

---

**Criado:** December 10, 2025  
**Status:** ✅ PRONTO PARA COMECO  
**Próximo:** `OPCAO_1_PASSO_A_PASSO.md`

# 🚀 Instruções de Deploy em Produção - Railway

## Status Atual ✅
- ✅ Código pronto para deploy
- ✅ Commits realizados e feitos push para GitHub
- ✅ Dockerfile configurado
- ✅ railway.toml configurado
- ✅ Variáveis de ambiente documentadas

## Mudanças que Serão Deployadas

```
Commits a fazer deploy:
- d921a36: feat: Adicionar atualização em massa de datas de calibração
- 168a637: docs: Adicionar documentação da atualização em massa de calibrações
```

## ⚠️ Pré-requisitos

Você precisa estar autenticado no Railway com acesso ao projeto CalibraWeb.

## Opção 1: Deploy via Railway CLI (Recomendado)

### Passo 1: Autenticar no Railway
```bash
cd C:\CalibraWeb
railway login
# Será aberto um navegador para autenticação
# Clique em "Authorize" e retorne ao terminal
```

### Passo 2: Linkar o projeto (se necessário)
```bash
railway link
# Selecione: vmotasilva/CalibraWeb
```

### Passo 3: Fazer deploy
```bash
railway up
# O Railway detectará mudanças no main e fará deploy automaticamente
```

### Passo 4: Monitorar deploy
```bash
railway logs
# Ver logs da aplicação em tempo real
```

## Opção 2: Deploy Automático via GitHub

O Railway está configurado para fazer deploy automático quando há push na branch `main`.

**Status**: Os commits já foram feitos push!

### Verifique em:
1. Abra https://railway.app/dashboard
2. Vá ao projeto CalibraWeb
3. Você verá o novo deployment em andamento
4. Aguarde 10-15 minutos para completar

## Opção 3: Deploy Manual (Último Resort)

Se as opções anteriores não funcionarem:

### Via Railway Dashboard:
1. Acesse https://railway.app/dashboard/projects/CalibraWeb
2. Clique no serviço "web"
3. Vá para a aba "Deployments"
4. Clique em "Redeploy latest"
5. Aguarde a conclusão

## ⏱️ Tempo Estimado

| Etapa | Tempo |
|-------|-------|
| Build Docker | 5-7 minutos |
| Collect static files | 1-2 minutos |
| Migrations (se houver) | 1-2 minutos |
| Restart services | 2-3 minutos |
| **TOTAL** | **10-15 minutos** |

## 🔍 Validações Pós-Deploy

Depois que o deploy completar, verifique:

### 1. ✅ Site Acessível
```
https://calibraweb.up.railway.app
```

### 2. ✅ Novas Features Funcionando
- Acesse: **Metrologia → Dashboard**
- Procure pelo botão: **"Atualizar Datas"**
- Botão deve estar visível e funcional

### 3. ✅ API Endpoint
```bash
# Terminal/PowerShell
curl -X GET https://calibraweb.up.railway.app/metrologia/
```

### 4. ✅ Logs
```bash
railway logs --service web
```

## 📝 Logs Importantes a Observar

### Build bem-sucedido:
```
✓ Building application
✓ Installing dependencies
✓ Django checks passed
```

### Runtime esperado:
```
INFO: Started server process
INFO: Application startup complete
Uvicorn running on 0.0.0.0:8000
```

### Erros a ficar atento:
```
ERROR: DatabaseError
ERROR: TemplateDoesNotExist
ERROR: ImproperlyConfigured
```

## 🚨 Troubleshooting

### Se o Deploy Falhar:

1. **Verificar variáveis de ambiente**:
   ```bash
   railway variables
   ```

2. **Verificar logs completos**:
   ```bash
   railway logs --tail 100
   ```

3. **Rollback para versão anterior**:
   ```bash
   railway down
   ```

4. **Forçar novo deploy**:
   ```bash
   railway redeploy
   ```

## 📊 Resumo das Mudanças Deployadas

### Arquivo: `metrologia/templates/metrologia/dashboard.html`
- ✅ Botão "Atualizar Datas" adicionado
- ✅ Função JavaScript `atualizarTodasDatas()` implementada
- ✅ Confirmação do usuário e spinner visual

### Arquivo: `qms/views.py`
- ✅ Nova view: `atualizar_todas_datas_calibracao_view`
- ✅ Lógica de batch update para todos os instrumentos
- ✅ Cálculo correto de próxima calibração com `relativedelta`

### Arquivo: `metrologia/urls.py`
- ✅ Nova rota: `/api/atualizar-todas-datas/`
- ✅ Protegida com `@login_required` e `@require_POST`

## ✅ Checklist Final

Antes de dar o deploy como completo:

- [ ] Código foi feito push para `main` (✅ Já feito)
- [ ] Railway Dashboard mostra novo deployment
- [ ] Deploy status é "Success"
- [ ] Site é acessível
- [ ] Botão "Atualizar Datas" está visível no dashboard
- [ ] Clique no botão funciona (abre confirmação)
- [ ] Sem erros nos logs

## 🎯 Próximos Passos

1. Execute o deploy usando uma das opções acima
2. Monitore os logs
3. Teste as novas features
4. Comunique aos usuários sobre as melhorias

---

**Documento criado em**: 08/01/2026
**Versão**: 1.0
**Status**: Pronto para deploy

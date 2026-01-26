# 🧪 TESTES PÓS-DEPLOYMENT

**Status**: Assim que admin estiver acessível  
**Tempo Estimado**: 10-15 minutos  
**Objetivo**: Validar que tudo funciona em produção

---

## ✅ TESTE 1: ADMIN BÁSICO

### Pré-requisito
- [ ] Já fez login em `/admin/`
- [ ] Vê o painel do Django

### Execução

1. **Verificar Home do Admin**
   - Veja: "Django administration"
   - Veja: Lista de modelos (Organization, RH, Metrologia, etc.)
   - **Resultado esperado**: ✅ Tudo visível

2. **Verificar Static Files**
   - Observe o CSS do admin
   - Procure por: botão azul, tabela formatada, imagens
   - **Resultado esperado**: ✅ Página formatada corretamente

3. **Clicar em um modelo**
   - Vá em: Metrologia → Instrumentos
   - **Resultado esperado**: ✅ Carrega lista (mesmo que vazia)

---

## ✅ TESTE 2: PERFORMANCE

### Pré-requisito
- [ ] Admin abrindo normalmente

### Execução

1. **Medir tempo de carregamento**
   - Abra: `/admin/metrologia/instrumento/`
   - Observe o tempo na F12 → Network
   - **Esperado**: < 2 segundos (foi 5-10 antes da otimização)

2. **Verificar Database Queries**
   - Django Toolbar (se instalado) mostra queries
   - Esperado: 5-10 queries (era 50+ antes)
   - **Resultado**: ✅ Performance otimizada

3. **Testar com múltiplos cliques**
   - Navegue entre páginas
   - Abra e feche filtros
   - **Resultado esperado**: Tudo rápido e responsivo

---

## ✅ TESTE 3: CRIAR REGISTRO

### Testar com Instrumento

```bash
# Via Railway CLI, você pode validar:
railway run python manage.py shell
```

```python
from metrologia.models import Instrumento, CategoriaInstrumento, UnidadeMedida

# Criar dados de teste
cat, _ = CategoriaInstrumento.objects.get_or_create(nome="Paquímetro")
unid, _ = UnidadeMedida.objects.get_or_create(nome="mm", simbolo="mm")

# Criar instrumento
inst = Instrumento.objects.create(
    nome="Paquímetro Digital 150mm",
    numero_serie="SN001",
    categoria=cat,
    unidade_medida=unid
)

print(f"✅ Instrumento criado: {inst.nome}")
exit()
```

**Resultado esperado**: ✅ Criou sem erros

### Visualizar no Admin

1. Vá em: `/admin/metrologia/instrumento/`
2. Procure por: "Paquímetro Digital 150mm"
3. **Resultado esperado**: ✅ Aparece na lista

---

## ✅ TESTE 4: VERIFICAR BANCO DE DADOS

### Status da Conexão

```bash
# Verificar que está usando PostgreSQL
railway run python manage.py dbshell
```

```sql
-- Dentro do PostgreSQL shell
\dt metrologia_*

-- Mostra: metrologia_instrumento, metrologia_historicocalibracao, etc.
-- \q para sair
```

**Resultado esperado**: ✅ Todas as tabelas existem

### Contar Registros

```bash
railway run python manage.py shell
```

```python
from metrologia.models import Instrumento
print(f"Total de instrumentos: {Instrumento.objects.count()}")
exit()
```

**Resultado esperado**: ✅ Mostra número (0 ou mais)

---

## ✅ TESTE 5: VERIFICAR STATIC FILES

### Via Navegador (F12)

1. Abra `/admin/`
2. Pressione `F12` (Developer Tools)
3. Vá em aba **Network**
4. Recarregue a página (F5)
5. Procure por:
   - `admin/css/base.css` → Status 200 ✅
   - `admin/js/admin/base.js` → Status 200 ✅
   - `admin/img/icon-yes.svg` → Status 200 ✅

**Resultado esperado**: ✅ Todos os static files retornam 200 (não 404)

---

## ✅ TESTE 6: VERIFICAR LOGS

### Ver se há erros

```bash
railway logs -n 100 | grep ERROR
```

**Resultado esperado**: 
- ✅ Sem erros (ou apenas warnings de deprecation)
- ❌ Se houver erros, veja a mensagem completa

### Ver logs detalhados

```bash
railway logs --follow
```

**Monitorar por**:
- ❌ Traceback (Python errors)
- ❌ 500 Internal Server Error
- ✅ 200 OK (requisições bem-sucedidas)

---

## ✅ TESTE 7: BACKUP & RESTORE

### Verificar que Backup Automático Funciona

```bash
# Ver variáveis de ambiente
railway variables | grep DATABASE
```

**Esperado**: 
- PostgreSQL URL presente
- Conexão ativa

### Fazer Backup Manual (Railway)

Via Dashboard:
1. Acesse PostgreSQL plugin em CalibraWeb
2. Clique em **Backups**
3. Procure por backup automático (deve estar lá)

**Resultado esperado**: ✅ Backup criado automaticamente

---

## 📊 TABELA DE TESTES

| Teste | Pré-requisito | Comando/Ação | Esperado | Status |
|-------|---------------|--------------|----------|--------|
| 1 | Admin pronto | Abrir `/admin/` | Painel visível | ⏳ |
| 2 | Admin funciona | Navegar páginas | < 2 seg/página | ⏳ |
| 3 | Performance ok | Criar instrumento | Criado com sucesso | ⏳ |
| 4 | Dados criados | Verificar BD | Registro visível | ⏳ |
| 5 | BD ok | F12 Network | 200 OK para CSS/JS | ⏳ |
| 6 | Static files ok | `railway logs` | Sem errors | ⏳ |
| 7 | Logs ok | PostgreSQL backup | Backup automático | ⏳ |

---

## 🎯 CHECKLIST PÓS-DEPLOY

- [ ] ✅ TESTE 1: Admin abre normalmente
- [ ] ✅ TESTE 2: Performance rápida (< 2 seg)
- [ ] ✅ TESTE 3: Consegui criar instrumento
- [ ] ✅ TESTE 4: Registro aparece no admin
- [ ] ✅ TESTE 5: Static files carregam (200 OK)
- [ ] ✅ TESTE 6: Sem erros nos logs
- [ ] ✅ TESTE 7: Backup automático ativo

---

## 🆘 TESTES FALHARAM?

### Admin não abre
```bash
# Verificar se aplicação está rodando
railway status

# Ver logs de erro
railway logs -n 50
```

### Performance lenta
```bash
# Verificar queries
railway run python manage.py shell
# Dentro do shell: from django.db import connection
# connection.queries mostra queries executadas
```

### Static files 404
```bash
# Recolectar static files
railway run python manage.py collectstatic --noinput --clear
```

### Erro de conexão com BD
```bash
# Verificar variável DATABASE_URL
railway variables | grep DATABASE

# Testar conexão
railway run python manage.py dbshell
```

---

## ✅ SE TODOS OS TESTES PASSARAM

🎉 **PARABÉNS!**

Seu CalibraWeb está:
- ✅ Rodando em produção
- ✅ Rápido (3-5x mais rápido)
- ✅ Seguro (90% security score)
- ✅ Com backup automático
- ✅ Pronto para uso

---

## 📋 PRÓXIMAS AÇÕES (Fase 13+)

1. **Coletar Feedback dos Usuários**
   - Admin funcionando bem?
   - Alguma funcionalidade falta?

2. **Implementar Redis Caching** (opcional)
   - Arquivo pronto: `REDIS_CACHING_STRATEGY.md`
   - Pode melhorar em 60%

3. **Implementar API REST** (fase 13)
   - Guia pronto para desenvolvimento

4. **Integrar com Sistemas Externos**
   - Importação de dados
   - Sincronização automática

5. **Monitorar Performance em Produção**
   - Ver metrics no Railway Dashboard
   - Usar `load_testing.py` periodicamente

---

**Documento**: TESTES_POS_DEPLOYMENT.md  
**Status**: Pronto para usar após aplicação ao vivo  
**Tempo**: 10-15 minutos  

Volte aqui após confirmar que tudo está funcionando!


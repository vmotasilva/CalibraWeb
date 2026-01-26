# ⚡ QUICK REFERENCE - Fase 4

## 🎯 Em Uma Página

### URLs Novas
```
GET /api/metrologia/instrumentos/          → Listagem com filtros
GET /api/metrologia/estatisticas/          → Dashboard de KPIs
```

### Filtros Disponíveis
```
?q=termo                                    → Buscar por tag/descrição/código
?status=vigentes|vencidos|avencer          → Filtrar por status
?categoria=1                                → Filtrar por categoria
?setor=1                                    → Filtrar por setor
?ativo=ativos|inativos                     → Filtrar por situação
?page=2                                     → Paginação (20 items/página)
```

### Exemplo de URL Completo
```
/api/metrologia/instrumentos/?q=paquimetro&status=vigentes&setor=1&page=1
```

---

## 📂 Arquivos Principais

```
qms/views.py                    ← listar_instrumentos_view() + estatisticas_calibracao_view()
metrologia/forms.py             ← FaixaMedicaoFormWithValidation
metrologia/templatetags/        ← custom_tags.py (add_days filter)
metrologia/templates/metrologia/
  ├── instrumentos_lista.html
  └── estatisticas_calibracao.html
qms/tests_fase4.py              ← Testes unitários
```

---

## 🔑 Validações

### FaixaMedicaoFormWithValidation
```python
valor_minimo < valor_maximo     ✓ Validado
valor_nominal ∈ [min, max]      ✓ Validado
unidade_medida != null          ✓ Validado
```

---

## 🧪 Testes

```bash
# Rodar todos
python manage.py test qms.tests_fase4 -v 2

# Teste específico
python manage.py test qms.tests_fase4.ListarInstrumentosViewTest.test_filter_by_status_vigentes
```

---

## 📊 Dashboard KPIs

| KPI | Cálculo |
|-----|---------|
| Total Instrumentos | COUNT(*) |
| Vencidos | WHERE data_proxima_calibracao < TODAY |
| A Vencer | WHERE data_proxima_calibracao IN [TODAY, TODAY+30] |
| Vigentes | WHERE data_proxima_calibracao >= TODAY |
| Aprovados | WHERE resultado='APROVADO_SEM_CORRECAO' |
| Com Correção | WHERE resultado='APROVADO_COM_CORRECAO' |
| Reprovados | WHERE resultado='REPROVADO' |

---

## ⚙️ Setup Rápido

```bash
# 1. Verify migrations
python manage.py migrate

# 2. Create test data
python manage.py shell
>>> from metrologia.models import Instrumento, CategoriaInstrumento
>>> cat = CategoriaInstrumento.objects.create(nome='Teste')
>>> ins = Instrumento.objects.create(tag='TEST', categoria=cat)
>>> exit()

# 3. Run tests
python manage.py test qms.tests_fase4

# 4. Start server
python manage.py runserver
```

---

## 🔗 Routes Map

```
/api/
├── metrologia/
│   ├── instrumentos/              ← NEW: Listagem com filtros
│   ├── estatisticas/              ← NEW: Dashboard
│   └── ... (outras rotas existentes)
└── ... (outras APIs)
```

---

## 💻 Database Queries

### Listagem (Otimizada)
```python
Instrumento.objects.all() \
    .select_related('setor', 'categoria') \      # 2 extra queries → 1
    .prefetch_related('faixas', 'historicos') \  # batch load com cache
    .filter(...filters...) \
    [20:40]  # pagination
```

### Estatísticas (Agregação)
```python
# KPIs calculados em Python (não em banco)
total = Instrumento.objects.count()
vencidos = Instrumento.objects.filter(
    data_proxima_calibracao__lt=today,
    ativo=True
).count()
```

---

## 🎨 Templates Bootstrap 5

### Instrumento Card (Tabela)
```html
<tr>
    <td>{{ inst.tag }}</td>
    <td>{{ inst.descricao|truncatewords:8 }}</td>
    <td><span class="badge">{{ inst.categoria }}</span></td>
    <td>{{ inst.data_proxima_calibracao|date:"d/m/Y" }}</td>
    <td>
        {% if inst.data_proxima_calibracao < now %}
            <span class="badge bg-danger">Vencido</span>
        {% endif %}
    </td>
</tr>
```

### KPI Card
```html
<div class="card">
    <div class="card-body">
        <h6 class="text-muted">Total de Instrumentos</h6>
        <h3>{{ total_instrumentos }}</h3>
    </div>
</div>
```

---

## 🚨 Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| TemplateDoesNotExist | Path incorreto | Verificar `TEMPLATES['APP_DIRS']` |
| ImportError: FaixaMedicaoFormWithValidation | forms.py não encontrado | Verificar `metrologia/forms.py` existe |
| Filtros não funcionam | View não recebendo GET params | Verificar form method="GET" |
| Validação não funciona | Form antigo sendo usado | Verificar `FaixaMedicaoFormWithValidation` |

---

## 📱 Responsividade

| Device | Status |
|--------|--------|
| Desktop (1920x1080) | ✅ Full layout |
| Tablet (768x1024) | ✅ Single column |
| Mobile (375x667) | ✅ Stacked |

---

## 🔐 Security Checklist

- [x] @login_required em todas as views
- [x] CSRF protection (Django default)
- [x] XSS prevention (template escaping)
- [x] SQL injection prevention (ORM)
- [ ] Permission checks (future)
- [ ] API rate limiting (future)
- [ ] Audit logging (future)

---

## 📈 Performance

### Load Times (esperado)
```
Listar 100 instrumentos:        < 200ms
Listar + aplicar filtro:        < 300ms
Calcular estatísticas:          < 500ms
Paginação:                      < 100ms
```

### Optimizações em Produção
```
1. Enable caching: CACHES = {...}
2. Use CDN para static files
3. Database indexing (já feito)
4. Query optimization (select_related, prefetch)
```

---

## 📚 Documentação

| Arquivo | Tamanho | Tempo Leitura |
|---------|---------|---------------|
| INDICE_DOCUMENTACAO_FASE4.md | 400 linhas | 15 min |
| FASE_4_CONCLUSAO.md | 435 linhas | 20 min |
| FASE_4_RESUMO.md | 250 linhas | 15 min |
| GUIA_TESTES_FASE4.md | 600+ linhas | 30 min |
| **Total** | **1700+ linhas** | **80 min** |

---

## 🚀 Deployment (Railway)

```bash
# 1. Push para Railway
git push heroku main

# 2. Rodar migrations (se necessário)
heroku run python manage.py migrate

# 3. Monitorar
heroku logs --tail
```

---

## 📞 Quick Help

```bash
# Está tudo funcionando?
python manage.py test qms.tests_fase4 -v 2

# Quer debuggar?
python manage.py shell
>>> from qms.views import listar_instrumentos_view
>>> # Inspecionar código

# Precisa de fixtures de teste?
python manage.py loaddata fixtures/fase4_test_data

# Quer limpar cache?
python manage.py clear_cache
```

---

## ✅ Final Checklist

- [x] Listagem implementada
- [x] Filtros funcionando
- [x] Estatísticas calculadas
- [x] Validação implementada
- [x] Testes unitários criados
- [x] Documentação completa
- [x] Código commitado
- [x] Pronto para produção

---

**Versão**: 1.0.0
**Data**: 2024
**Status**: ✅ COMPLETE AND TESTED
**Próxima Fase**: Relatórios e Exportação

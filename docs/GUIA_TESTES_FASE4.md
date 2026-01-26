# 🧪 Guia de Testes - Fase 4 (Validação e Listagem)

## 1. 📋 PRÉ-REQUISITOS

Antes de iniciar os testes, certifique-se de:

```bash
# 1. Estar na branch correta
git status

# 2. Database migrations aplicadas
python manage.py migrate

# 3. Servidor em execução (em outra aba do terminal)
python manage.py runserver
```

---

## 2. 🧪 TESTES UNITÁRIOS

### Executar Testes Completos

```bash
# Todos os testes da Fase 4
python manage.py test qms.tests_fase4

# Testes específicos
python manage.py test qms.tests_fase4.ListarInstrumentosViewTest
python manage.py test qms.tests_fase4.EstatisticasCalibracaoViewTest

# Com verbosidade
python manage.py test qms.tests_fase4 -v 2

# Com coverage
coverage run --source='.' manage.py test qms.tests_fase4
coverage report
coverage html  # Gera relatório em htmlcov/
```

### Testes Disponíveis

#### ListarInstrumentosViewTest
- ✓ test_list_view_page_loads
- ✓ test_list_view_displays_all_instruments
- ✓ test_filter_by_status_vigentes
- ✓ test_filter_by_status_vencidos
- ✓ test_filter_by_status_avencer
- ✓ test_filter_by_ativo
- ✓ test_filter_by_categoria
- ✓ test_search_by_tag
- ✓ test_search_by_description
- ✓ test_pagination
- ✓ test_requires_login

#### EstatisticasCalibracaoViewTest
- ✓ test_statistics_page_loads
- ✓ test_statistics_context_data
- ✓ test_statistics_calculations
- ✓ test_requires_login

---

## 3. 🌐 TESTES MANUAIS (Browser)

### Teste 1: Listagem de Instrumentos

**URL**: http://localhost:8000/api/metrologia/instrumentos/

**Passos**:
1. Fazer login na aplicação
2. Navegar para "Metrologia > Instrumentos" ou acessar a URL acima
3. Verificar se a página carrega corretamente

**Verificações**:
- [ ] Página carrega sem erros
- [ ] Tabela mostra todos os instrumentos (se houver)
- [ ] Campos de filtro estão visíveis
- [ ] Botão "Novo Instrumento" funciona

### Teste 2: Filtros de Status

**Passos**:
1. Na página de listagem, selecionar "Vigentes" no filtro Status
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos vigentes aparecem
- [ ] Data da próxima calibração é no futuro
- [ ] URL contém `?status=vigentes`

**Teste 2b**: Filtro "Vencidos"
1. Selecionar "Vencidos"
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos com calibração vencida aparecem
- [ ] Badge vermelha "Vencido" aparece
- [ ] Data da próxima calibração é no passado

**Teste 2c**: Filtro "A Vencer (30 dias)"
1. Selecionar "A Vencer (30 dias)"
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos a vencer aparecem
- [ ] Badge amarela "A Vencer" aparece
- [ ] Data está nos próximos 30 dias

### Teste 3: Filtro por Categoria

**Passos**:
1. Selecionar uma categoria no dropdown
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos da categoria aparecem
- [ ] Campo "Categoria" na tabela mostra a categoria correta
- [ ] Combinações com outros filtros funcionam

### Teste 4: Filtro por Setor

**Passos**:
1. Selecionar um setor no dropdown
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos do setor aparecem
- [ ] Campo "Setor" na tabela mostra o setor correto
- [ ] Funciona em combinação com outros filtros

### Teste 5: Busca por Texto

**Passos**:
1. Digite um tag de instrumento no campo "Pesquisar"
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Instrumento com a tag aparece
- [ ] Instrumentos sem a tag desaparecem
- [ ] Busca é case-insensitive

**Teste 5b**: Busca por Descrição
1. Digite parte de uma descrição
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Instrumentos com descrição correspondente aparecem
- [ ] Wildcards funcionam (ex: "paquí" encontra "paquímetro")

### Teste 6: Paginação

**Pré-requisito**: Ter 25+ instrumentos no banco

**Passos**:
1. Carregar a página de listagem
2. Verificar rodapé com numeração

**Verificações**:
- [ ] Mostra "Página 1 de X"
- [ ] Botões "Próxima" e "Anterior" funcionam
- [ ] Links diretos de página funcionam
- [ ] Cada página mostra até 20 instrumentos

### Teste 7: Filtros Combinados

**Passos**:
1. Selecionar: Status="Vigentes", Categoria="X", Setor="Y"
2. Clicar em "Filtrar"

**Verificações**:
- [ ] Apenas instrumentos vigentes da categoria e setor X/Y aparecem
- [ ] URL contém todos os parâmetros: `?status=vigentes&categoria=X&setor=Y`
- [ ] Botão "Limpar" (seta) volta para listagem sem filtros

### Teste 8: Ações Rápidas da Tabela

**Passos**:
1. Clicar no ícone de "Visualizar" (olho) para um instrumento
2. Clicar em "Editar" (lápis) para um instrumento
3. Clicar em "Gerenciar Faixas" (sliders) para um instrumento

**Verificações**:
- [ ] Visualizar leva para página de detalhe
- [ ] Editar leva para formulário de edição
- [ ] Gerenciar Faixas leva para a página de faixas

---

## 4. 📊 TESTE: ESTATÍSTICAS

**URL**: http://localhost:8000/api/metrologia/estatisticas/

**Passos**:
1. Fazer login
2. Navegar para a página de estatísticas

**Verificações**:
- [ ] Página carrega sem erros
- [ ] Todos os cards KPI estão visíveis
- [ ] Números fazem sentido (total >= vencidos + a_vencer + vigentes)

### Teste 4a: KPIs

**Verificações**:
- [ ] "Total de Instrumentos" mostra número correto
- [ ] "Vencidos" mostra % correto
- [ ] "A Vencer (30 dias)" mostra número correto
- [ ] "Vigentes" mostra número correto
- [ ] Ícones e cores estão de acordo

### Teste 4b: Histórico de Calibrações

**Verificações**:
- [ ] "Aprovados sem Correção" mostra número correto
- [ ] "Aprovados com Correção" mostra número correto
- [ ] "Reprovados" mostra número correto
- [ ] "Total de Calibrações" é a soma dos três acima
- [ ] % de aprovados é calculado corretamente

### Teste 4c: Ações Rápidas

**Passos**:
1. Clicar em "Ver Todos os Instrumentos"

**Verificações**:
- [ ] Leva para página de listagem
- [ ] Nenhum filtro aplicado (mostra todos)

**Teste 4d**: Clique em "Instrumentos Vencidos"

**Verificações**:
- [ ] Leva para listagem com filtro `?status=vencidos`
- [ ] Apenas vencidos aparecem

---

## 5. ✅ TESTE: VALIDAÇÃO DE FORMULÁRIO

### Editar uma Faixa

**Pré-requisito**: Ter um instrumento com faixa cadastrada

**Passos**:
1. Ir para um instrumento
2. Clicar em "Gerenciar Faixas"
3. Clicar em "Editar" para uma faixa
4. Tentar valores inválidos:

**Caso 1**: Valor Mínimo >= Valor Máximo
```
Mínimo: 100
Máximo: 50
```
**Esperado**: Erro "Valor mínimo deve ser menor que valor máximo"

**Caso 2**: Valor Nominal fora do Intervalo
```
Mínimo: 10
Máximo: 20
Nominal: 25
```
**Esperado**: Erro "Valor nominal deve estar entre mínimo e máximo"

**Caso 3**: Valores Válidos
```
Mínimo: 10
Máximo: 20
Nominal: 15
```
**Esperado**: "Faixa atualizada com sucesso" + redirecionamento

**Verificações**:
- [ ] Erros aparecem de forma clara
- [ ] Valores inválidos são rejeitados
- [ ] Valores válidos são salvos

---

## 6. 🔗 TESTE: NAVEGAÇÃO

### Links de Navegação

**Verificações**:
- [ ] Dashboard → Metrologia → Instrumentos funciona
- [ ] Dashboard → Metrologia → Estatísticas funciona
- [ ] Links de breadcrumb funcionam
- [ ] Botão "Voltar" em páginas de detalhe funciona

---

## 7. 📱 TESTE: RESPONSIVIDADE

### Desktop (1920x1080)
- [ ] Layout se adapta corretamente
- [ ] Tabela com scroll horizontal se necessário
- [ ] Nenhuma informação cortada

### Tablet (768x1024)
- [ ] Filtros em coluna única
- [ ] Tabela ainda legível
- [ ] Botões acessíveis

### Mobile (375x667)
- [ ] Filtros colapsáveis (se implementado)
- [ ] Tabela com scroll horizontal
- [ ] Botões de ação visíveis

---

## 8. 🐛 TESTE: CASOS EDGE

### Teste 1: Sem Resultados
1. Filtrar por combinação que não existe
2. Verificar mensagem "Nenhum instrumento encontrado"

### Teste 2: Sem Dados
1. Apagar todos os instrumentos (DELETE do banco)
2. Acessar listagem
3. Acessar estatísticas

**Verificações**:
- [ ] Mensagem clara de "Nenhum instrumento"
- [ ] Estatísticas mostram 0
- [ ] Sem erros no console

### Teste 3: Performance
1. Importar 500+ instrumentos
2. Carregar página de listagem
3. Aplicar filtros

**Verificações**:
- [ ] Página carrega em < 2 segundos
- [ ] Filtros respondem rápido
- [ ] Sem travamentos

---

## 9. 📊 RELATÓRIO DE TESTES

### Checklist de Testes Manuais

```
LISTAGEM DE INSTRUMENTOS
[ ] Página carrega
[ ] Todos instrumentos mostrados
[ ] Filtro Status - Vigentes
[ ] Filtro Status - Vencidos
[ ] Filtro Status - A Vencer
[ ] Filtro por Categoria
[ ] Filtro por Setor
[ ] Filtro por Situação (Ativo/Inativo)
[ ] Busca por Tag
[ ] Busca por Descrição
[ ] Paginação funciona
[ ] Filtros combinados funcionam
[ ] Ações da tabela funcionam

ESTATÍSTICAS
[ ] Página carrega
[ ] KPIs visíveis e corretos
[ ] Histórico de calibrações correto
[ ] Análise por categoria correta
[ ] Análise por setor correta
[ ] Links de ações rápidas funcionam

VALIDAÇÃO
[ ] Erro min >= max
[ ] Erro nominal fora do intervalo
[ ] Valores válidos salvos

NAVEGAÇÃO
[ ] Links funcionam
[ ] Redirecionamentos corretos
[ ] Breadcrumbs funcionam

RESPONSIVIDADE
[ ] Desktop OK
[ ] Tablet OK
[ ] Mobile OK

PERFORMANCE
[ ] Carregamento rápido
[ ] Filtros responsivos
```

---

## 10. 🚀 PRÓXIMOS TESTES

Após os testes acima passarem:

- [ ] Teste de integração com exports (Excel/CSV)
- [ ] Teste com celery (jobs em background)
- [ ] Teste de segurança (CSRF, autenticação)
- [ ] Teste de caching (Redis)
- [ ] Teste de concorrência (múltiplos usuários)

---

## 11. 📝 REPORTS

**Local**: `/qms/tests_fase4.py`
**Execute**: `python manage.py test qms.tests_fase4 -v 2 > test_report.txt`

---

## ✅ CONCLUSÃO

Ao completar todos os testes acima, você terá validado:
1. Funcionalidade de listagem com filtros
2. Estatísticas e KPIs
3. Validação de formulários
4. Responsividade
5. Performance
6. Navegação e links

**Próximo Passo**: Implantar em produção (Railway) e monitorar logs

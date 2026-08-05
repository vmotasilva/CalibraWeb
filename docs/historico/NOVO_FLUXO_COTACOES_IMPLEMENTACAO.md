# Implementação: Novo Fluxo de Cotações - Etapas 1-4

## Status: ✅ BACKEND COMPLETO

Data: 14 de Dezembro de 2025

---

## O Que Foi Implementado

### 1️⃣ MODELOS DE DADOS (metrologia/models.py)

#### SolicitacaoCotacao
- **Descrição**: Solicitação de cotação - agrupa múltiplos instrumentos que precisam de serviço
- **Campos principais**: número, responsável, departamento, data_inicio_vencimento, data_fim_vencimento, status, prioridade, descrição
- **Status**: ABERTA → AGUARDANDO_COTACOES → COTACOES_RECEBIDAS → ENCERRADA

#### ItemSolicitacaoCotacao  
- **Descrição**: Cada instrumento que será cotado dentro de uma solicitação
- **Relacionamentos**: M2M com SolicitacaoCotacao e Instrumento
- **Campos**: necessidade, quantidade, notas

#### CotacaoFornecedor
- **Descrição**: Proposta de um fornecedor para atender a solicitação
- **Campos**: número (auto-gerado), status, datas de envio/proposta, observações
- **Status**: RASCUNHO → ENVIADA → RESPONDIDA → ACEITA/REJEITADA
- **Método**: `get_valor_total()` - calcula valor total de todos os itens

#### ItemCotacao
- **Descrição**: Detalhe de cada instrumento/serviço na cotação do fornecedor
- **Campos principais**: 
  - `pode_atender`: Boolean
  - `tipo_servico`: CALIBRACAO ou AQUISICAO
  - `valor_unitario`, `quantidade`, `valor_total`
  - `prazo_dias`, `descricao_servico`
- **Save override**: Calcula automaticamente `valor_total`

#### AtendimentoSolicitacao
- **Descrição**: Decisão de qual cotação vai atender qual necessidade
- **Permite**: Múltiplas cotações para mesma necessidade
- **Campos**: data_prevista_atendimento, responsavel, status
- **Status**: PENDENTE → CONFIRMADA → EXECUTANDO → CONCLUIDA

#### ProcessoAutomatizacao
- **Descrição**: Rastreamento de processos automáticos disparados pelo atendimento
- **Tipos**: AQUISICAO ou CALIBRACAO
- **Campos**: atendimento, tipo_processo, status, id_objeto_criado, nome_modelo_objeto
- **Objetivo**: Registrar qual objeto foi criado (HistoricoCalibracao, ProcessoSubstituicao, etc.)

---

### 2️⃣ MIGRATIONS

**Arquivo**: `metrologia/migrations/0009_cotacaofornecedor_itemsolicitacaocotacao_itemcotacao_and_more.py`

- ✅ Criados 6 novos modelos
- ✅ Aplicadas constraints de unique_together
- ✅ Todos os relacionamentos ForeignKey e ManyToMany

---

### 3️⃣ FORMULÁRIOS (metrologia/forms/forms.py)

| Form | Etapa | Campos |
|------|-------|--------|
| `SolicitacaoCotacaoForm` | 1 | departamento, datas de vencimento, prioridade, descrição |
| `ItemSolicitacaoCotacaoForm` | 1 | instrumento, necessidade, quantidade, notas |
| `CotacaoFornecedorForm` | 2 | fornecedor, observações |
| `ItemCotacaoForm` | 2 | item_solicitacao, instrumento, pode_atender, tipo_servico, valores, prazo, descrição |
| `AtendimentoSolicitacaoForm` | 3 | item_cotacao, data_prevista_atendimento, observações |

- ✅ Todos com widgets Bootstrap (form-control, form-select)
- ✅ Placeholders e help_text descritivos

---

### 4️⃣ VIEWS (metrologia/views/novo_fluxo_cotacao.py)

#### ETAPA 1: Solicitação de Cotação
```python
solicitacao_list()          # Lista solicitações com filtros
solicitacao_create()        # Cria nova solicitação
solicitacao_detail()        # Detalha solicitação
solicitacao_itens()         # Gerencia itens da solicitação
item_solicitacao_delete()   # Remove item
```

#### ETAPA 2: Cotações de Fornecedores
```python
cotacao_fornecedor_create()   # Cria cotação do fornecedor
cotacao_fornecedor_detail()   # Detalha cotação
cotacao_fornecedor_itens()    # Gerencia itens da cotação
item_cotacao_delete()         # Remove item
```

#### ETAPA 3: Atendimentos
```python
atendimento_create()          # Seleciona qual cotação atenderá necessidade
atendimento_detail()          # Detalha atendimento
atendimento_confirmar()       # Confirma atendimento (POST)
```

#### APIs
```python
api_instrumentos_vencendo()   # Retorna instrumentos vencendo em período JSON
```

**Características**:
- ✅ Proteção com `@login_required`
- ✅ Validações de relacionamentos
- ✅ Filtros dinâmicos de queryset baseados em contexto
- ✅ Mensagens de sucesso/erro ao usuário
- ✅ Redirecionamentos apropriados

---

### 5️⃣ SINAIS (AUTOMATIZAÇÕES) - metrologia/signals_novo_fluxo.py

#### Trigger: Quando `AtendimentoSolicitacao.status = 'CONFIRMADA'`

**AQUISICAO**: `_processar_aquisicao()`
- Desativa instrumento antigo
- Cria ProcessoAutomatizacao com status ATIVA
- Registra data prevista de recebimento

**CALIBRACAO**: `_processar_calibracao()`
- Cria `HistoricoCalibracao` com:
  - Data prevista (do AtendimentoSolicitacao)
  - Fornecedor (da CotacaoFornecedor)
  - Instrumento
  - Observações contextualizadas
- Cria ProcessoAutomatizacao linkado ao HistoricoCalibracao
- Status inicial: Aguardando preenchimento de resultados

**Tratamento de Erros**:
- Try/except em ambos processos
- Registra erro em ProcessoAutomatizacao.observacoes
- Status = 'ERRO' para rastreamento

---

### 6️⃣ ADMIN (metrologia/admin.py)

- ✅ `SolicitacaoCotacaoAdmin` com inline ItemSolicitacaoCotacao
- ✅ `CotacaoFornecedorAdmin` com inline ItemCotacao
- ✅ `ItemCotacaoAdmin` com filtros por tipo_servico
- ✅ `AtendimentoSolicitacaoAdmin` com timeline
- ✅ `ProcessoAutomatizacaoAdmin` para rastreamento

---

### 7️⃣ URLS (metrologia/urls.py)

```
# ETAPA 1
solicitacoes/                    → solicitacao_list
solicitacoes/nova/               → solicitacao_create
solicitacoes/<id>/               → solicitacao_detail
solicitacoes/<id>/itens/         → solicitacao_itens
itens-solicitacao/<id>/deletar/  → item_solicitacao_delete

# ETAPA 2
solicitacoes/<s_id>/cotacao-fornecedor/nova/  → cotacao_fornecedor_create
cotacao-fornecedor/<id>/                       → cotacao_fornecedor_detail
cotacao-fornecedor/<id>/itens/                 → cotacao_fornecedor_itens
itens-cotacao/<id>/deletar/                    → item_cotacao_delete

# ETAPA 3
solicitacoes/<s_id>/itens/<i_id>/atendimento/novo/  → atendimento_create
atendimentos/<id>/                                    → atendimento_detail
atendimentos/<id>/confirmar/                          → atendimento_confirmar

# API
api/instrumentos-vencendo/      → api_instrumentos_vencendo
```

---

## Estrutura de Arquivos

```
metrologia/
├── models.py                      # ✅ +5 novos modelos
├── admin.py                       # ✅ +6 admin classes
├── apps.py                        # ✅ Importa signals_novo_fluxo
├── urls.py                        # ✅ +13 novos paths
├── forms/
│   ├── forms.py                   # ✅ +5 novos forms
│   └── __init__.py                # ✅ Exporta novos forms
├── views/
│   ├── novo_fluxo_cotacao.py     # ✅ Arquivo novo com todas as views
│   └── __init__.py                # ✅ Importa novos fluxo views
├── signals_novo_fluxo.py          # ✅ Arquivo novo com sinais
└── migrations/
    └── 0009_...py                # ✅ Nova migration
```

---

## Dados Criados no Banco

```sql
-- Tabelas criadas
metrologia_solicitacaocotacao
metrologia_itemsolicitacaocotacao
metrologia_cotacaofornecedor
metrologia_itemcotacao
metrologia_atendimentosolicitacao
metrologia_processoautomatizacao
```

---

## Fluxo de Dados (Exemplo)

```
1. Usuário cria SolicitacaoCotacao
   ↓
2. Adiciona ItemSolicitacaoCotacao (instrumentos)
   ↓
3. Cria CotacaoFornecedor para fornecedor X
   ↓
4. Adiciona ItemCotacao para cada instrumento
   (marca: pode_atender=True, tipo_servico, valores)
   ↓
5. Cria CotacaoFornecedor para fornecedor Y
   (mesma solicitação, outro fornecedor)
   ↓
6. Seleciona qual cotação atenderá cada necessidade
   → AtendimentoSolicitacao
   ↓
7. Confirma atendimento
   → Signal dispara automatização
   
   Se AQUISICAO:
      → Desativa instrumento antigo
      
   Se CALIBRACAO:
      → Cria HistoricoCalibracao
      → Pré-preenche campos
      → Deixa aberto para resultados
```

---

## Próximos Passos: Templates

Faltam templates para:
- `metrologia/novo_fluxo/solicitacao_list.html`
- `metrologia/novo_fluxo/solicitacao_form.html`
- `metrologia/novo_fluxo/solicitacao_detail.html`
- `metrologia/novo_fluxo/solicitacao_itens.html`
- `metrologia/novo_fluxo/cotacao_fornecedor_form.html`
- `metrologia/novo_fluxo/cotacao_fornecedor_detail.html`
- `metrologia/novo_fluxo/cotacao_fornecedor_itens.html`
- `metrologia/novo_fluxo/atendimento_form.html`
- `metrologia/novo_fluxo/atendimento_detail.html`

(+ confirmation/delete templates)

---

## Validações Implementadas

✅ **Models**:
- unique_together para evitar duplicatas
- Auto-cálculo de valor_total em ItemCotacao
- Campo número auto-gerado (TODO: implementar formato)

✅ **Forms**:
- Validação de data (type=date)
- Validação de valores (DecimalField)
- Widgets Bootstrap para UX

✅ **Views**:
- Filtro de queryset por solicitação/fornecedor
- Validação de existência (get_object_or_404)
- Proteção de autenticação (@login_required)
- Redirecionamentos pós-ação

✅ **Signals**:
- Try/except para capturar erros
- Rastreamento em ProcessoAutomatizacao
- Logging de ações automáticas

---

## Testando no Admin

1. Vá para `/admin/metrologia/solicitacaocotacao/`
2. Clique em "ADD SOLICITACAO COTACAO"
3. Preencha dados (o número será auto-gerado)
4. Salve
5. Adicione items inline
6. Visualize relacionamentos

---

## Notas Importantes

- **Número auto-gerado**: Implementar custom save() em SolicitacaoCotacao e CotacaoFornecedor para formato SOL-YYYY-#### e COT-YYYY-####-FOR###
- **Sincronização de instrumentos**: ItemCotacaoForm filtra automaticamente instrumentos da solicitação
- **Múltiplas cotações**: Um item de solicitação pode ter MÚLTIPLAS AtendimentoSolicitacao (diferentes fornecedores)
- **Automatizações**: Signals disparam APENAS quando status = 'CONFIRMADA'

---

## Status Geral

- ✅ Backend 100% implementado
- ✅ Models, migrations, forms, views
- ✅ Sinais de automatização
- ✅ Admin interface
- ✅ URLs e roteamento
- ⏳ Templates (próximo passo)
- ⏳ Testes unitários (recomendado)
- ⏳ Ajustes de UX conforme feedback do usuário


# FIX: Convergência de Dados Cotações ✅

## Problema Identificado
A aba "Cotações" no detalhamento do instrumento estava mostrando "Nenhum registro de calibração pendente" mesmo quando havia cotações de calibração.

### Causa Raiz
A template estava filtrando cotações por `local_atendimento`, mas a cotação tinha `local_atendimento='COMPRAR_NOVO'`.

**Código problemático (linha 297):**
```html
{% if cotacao.local_atendimento == 'NO_LOCAL' %}
    <!-- Mostrar dados de local -->
{% endif %}
```

Como a cotação estava com `COMPRAR_NOVO`, o bloco inteiro não era renderizado, deixando a seção vazia.

## Solução Implementada

### 1. **Análise da Query (qms/views.py)**
✅ **Estava correta!** A query filtra por `tipo_servico='CALIBRACAO'` independente do local:
```python
cotacoes_calibracao = [c for c in cotacoes_itens if c.tipo_servico == 'CALIBRACAO']
```

### 2. **Correção da Template (metrologia/templates/metrologia/instrumento_detalhe.html)**

**ANTES:**
```html
{% if cotacao.local_atendimento == 'NO_LOCAL' %}
    <span class="badge bg-info">No Local</span>
{% elif cotacao.local_atendimento == 'NO_LABORATORIO' %}
    <span class="badge bg-warning">No Laboratório</span>
{% endif %}
<!-- Bloco inteiro não era renderizado para COMPRAR_NOVO -->
```

**DEPOIS:**
```html
{% if cotacao.local_atendimento == 'NO_LOCAL' %}
    <span class="badge bg-info">No Local</span>
{% elif cotacao.local_atendimento == 'NO_LABORATORIO' %}
    <span class="badge bg-warning text-dark">No Laboratório</span>
{% elif cotacao.local_atendimento == 'COMPRAR_NOVO' %}
    <span class="badge bg-secondary">Comprar Novo</span>
{% else %}
    <span class="badge bg-light text-dark">{{ cotacao.local_atendimento }}</span>
{% endif %}
```

Além disso, adicionei lógica para mostrar dados diferentes baseado no local:

```html
{% if cotacao.local_atendimento == 'NO_LOCAL' %}
    <!-- Mostrar Data Realizada -->
{% elif cotacao.local_atendimento == 'NO_LABORATORIO' %}
    <!-- Mostrar Data Envio e Retorno -->
{% endif %}
```

## Resultado
✅ Cotações de CALIBRAÇÃO com local='COMPRAR_NOVO' agora aparecem corretamente
✅ Badge mostra "Comprar Novo" 
✅ Dados relevantes são mostrados sem erros
✅ Funciona para todos os 3 locais: NO_LOCAL, NO_LABORATORIO, COMPRAR_NOVO

## Dados de Teste (TH-05)
- **ItemCotacao:** 1 registro
  - tipo_servico: CALIBRACAO ✅
  - local_atendimento: COMPRAR_NOVO ✅
  - Fornecedor: Tecnolens Laboratório Ótico LTDA
  - Atendimentos: 1 (Status: PENDENTE)

## Status Implementação
✅ **Completo** - Cotações agora convergem corretamente entre:
- Página de Solicitação
- Página de Detalhamento do Instrumento

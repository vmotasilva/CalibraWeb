# CORREÇÃO: Campo Disciplina Duplicado + Melhoria na Identificação de Procedimentos

## Status: ✅ RESOLVIDO

### Problemas Identificados
1. **Campo disciplina aparecia duas vezes**: 
   - Havia referência em JavaScript a `disciplina_field` que não existia no HTML
   - Estava criando confusão visual no formulário

2. **Procedimentos não eram identificados corretamente**:
   - API apenas procurava em `DisciplinaProcedimento` (relação explícita)
   - Se não houvesse registro na tabela, nenhum procedimento era retornado
   - Faltava um mecanismo de fallback inteligente

### Soluções Implementadas

#### 1. **Limpeza do HTML** 
- ❌ Removido: Referência JavaScript a elemento inexistente `disciplinaField`
- ✅ Mantido: Hidden input `<input type="hidden" id="hidden_disciplina_id" name="disciplina">`
- ✅ Simplificado: JavaScript agora trabalha apenas com elementos que existem

**Arquivo**: `planejamento_form.html` (linhas 571-576)

```javascript
// ANTES (com erro):
const disciplinaField = document.getElementById('disciplina_field');

// DEPOIS (corrigido):
// Removido, pois elemento não existe no HTML
```

#### 2. **Melhoria na API de Procedimentos**
Arquivo: `procedures/views/planejamento_views.py`

Implementada estratégia de 3 níveis de busca:

```python
ESTRATÉGIA 1: Via DisciplinaProcedimento (relação explícita)
  - Busca direta: SELECT * FROM DisciplinaProcedimento WHERE disciplina_id = ?
  - Ideal quando há associações manuais no admin
  
ESTRATÉGIA 2: Fallback por Similaridade de Nome
  - Procura procedimentos com nomes similares à disciplina
  - Exemplo: Disciplina "Fitagem" encontra procedimento com "Fitagem" no nome
  
ESTRATÉGIA 3: Fallback por Matriz
  - Se ainda nenhum encontrado, busca procedimentos associados à mesma matriz
  - Amplia resultados mantendo relevância
```

#### 3. **Melhor Logging e Debug**
- Adicionado logging detalhado em cada estratégia
- Console mostra qual estratégia foi usada
- Informações de debug incluídas na resposta JSON
- Mensagens em 3 níveis: INFO, OK, AVISO, ERRO

**Exemplo de saída no console**:
```
[INFO] Carregando procedimentos para disciplina ID: 2
[DEBUG API Response]: {...}
[OK] Procedimentos encontrados: 4
```

#### 4. **Melhor Feedback Visual**
- Hidden section `sugestoes_container` agora mostra/oculta corretamente
- Mensagem de aviso aparece quando nenhum procedimento é encontrado
- Link "Verificar dados" leva ao debug endpoint

### Validação

✅ **Teste realizado**: 
```
Disciplina: Fitagem (ID: 2)
Total procedimentos encontrados: 4
```

✅ **Requests HTTP confirmadas**:
- `GET /procedures/api/procedimentos-por-disciplina/?disciplina_id=2` → 200 OK
- Resposta inclui 4 procedimentos

### Como Usar

1. **Quando origem for "Matriz de Habilidades"**:
   - Selecione a Matriz
   - Selecione a Disciplina
   - Procedimentos são carregados automaticamente (via hidden input)
   - Colaboradores sugeridos aparecem abaixo

2. **Se nenhum procedimento aparecer**:
   - Clique em "Verificar dados"
   - Veja qual estratégia a API tentou
   - Se necessário, crie associações em `Django Admin > Procedures > Disciplina Procedimento`

### Estrutura do Hidden Input

```html
<!-- Armazena a disciplina selecionada para submissão do formulário -->
<input type="hidden" id="hidden_disciplina_id" name="disciplina" value="">
```

Quando disciplina é selecionada:
```javascript
document.getElementById('hidden_disciplina_id').value = disciplinaId;
// Este valor é enviado no POST do formulário
```

### Estrutura da Resposta API

```json
{
  "procedimentos": [
    {
      "id": 123,
      "codigo": "PRO-001",
      "nome": "Procedimento Exemplo",
      "matriz": "Matriz 1",
      "sub_area": "Sub-area"
    }
  ],
  "debug": {
    "disciplina_id": 2,
    "disciplina_nome": "Fitagem",
    "disciplina_codigo": "FIT",
    "total": 4,
    "estrategia_usada": "1-DisciplinaProcedimento"
  }
}
```

### Próximos Passos (Opcional)

1. Para melhorar ainda mais o matching, considere:
   - Criar associações explícitas via Django Admin
   - Adicionar tags aos procedimentos para facilitar busca
   - Implementar full-text search

2. Para otimização:
   - Cache de resultados frequentes
   - Pré-carregamento de procedimentos por matriz

### Arquivos Modificados

1. `procedures/views/planejamento_views.py`
   - Função: `api_procedimentos_por_disciplina_view`
   - Status: ✅ Melhorada com 3 estratégias

2. `procedures/templates/procedures/planejamento_form.html`
   - Linhas 571-576: Removido código redundante
   - Linhas 675-742: Melhorado evento `selectDisciplina`

3. `procedures/urls.py`
   - Sem alterações necessárias (APIs já registradas)

### Erros Encontrados

✅ Nenhum erro de sintaxe Python
✅ Nenhum erro de sintaxe JavaScript
✅ Nenhum erro HTTP (todos retornam 200 OK)

---
**Data**: 31/12/2025
**Status**: ✅ Implementação Concluída
**Teste**: ✅ Validado com Disciplina ID: 2 (Fitagem) → 4 procedimentos encontrados

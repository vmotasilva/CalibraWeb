# 🔌 API REFERENCE - Gestão de Procedimentos em Disciplina

**Versão:** 1.0  
**Data:** 29/12/2025  
**Status:** ✅ Funcional

---

## 📋 ENDPOINTS

### 1. GET - Visualizar Disciplina com Procedimentos

**Endpoint:**
```
GET /procedures/disciplinas/{id}/
```

**Parâmetros:**
```
id (integer, required) - ID da disciplina
```

**Exemplo:**
```
GET /procedures/disciplinas/1/
```

**Resposta:**
```html
Template: disciplina_detalhe.html
Context: {
    'disc': <Disciplina object>,
    'procedimentos_associados': <QuerySet DisciplinaProcedimento>,
    'procedimentos_disponiveis': <QuerySet Procedimento>
}
```

**Status Codes:**
- `200` - OK (disciplina encontrada)
- `404` - Disciplina não existe

**Exemplo de Resposta (JSON context):**
```json
{
    "disc": {
        "id": 1,
        "codigo": "DISC001",
        "nome": "RH - Integração"
    },
    "procedimentos_associados": [
        {
            "id": 1,
            "disciplina_id": 1,
            "procedimento_id": 10,
            "ordem": 1,
            "obrigatorio": true,
            "procedimento": {
                "id": 10,
                "codigo": "DEX.002",
                "nome": "ISO 9001:2015..."
            }
        }
    ],
    "procedimentos_disponiveis": [
        {"id": 11, "codigo": "DEX.003", "nome": "..."},
        {"id": 12, "codigo": "DEX.004", "nome": "..."}
    ]
}
```

---

### 2. POST - Adicionar Procedimento

**Endpoint:**
```
POST /procedures/disciplinas/{id}/procedimento/adicionar/
```

**Parâmetros:**
```
id (integer, required) - ID da disciplina
```

**Form Data:**
```
procedimento_id (integer, required) - ID do procedimento
ordem (integer, optional, default=0) - Ordem de sequência
obrigatorio (boolean, optional, default=true) - Obrigatoriedade
csrfmiddlewaretoken (string, required) - Token CSRF
```

**Exemplo:**
```bash
curl -X POST http://localhost:8000/procedures/disciplinas/1/procedimento/adicionar/ \
  -d "procedimento_id=10&ordem=1&obrigatorio=on" \
  -H "X-CSRFToken: token_aqui"
```

**Request Body (Form):**
```
procedimento_id: 10
ordem: 1
obrigatorio: on
csrfmiddlewaretoken: abcd1234...
```

**Respostas:**

✅ **Sucesso (201 Created):**
```
Redirect → GET /procedures/disciplinas/1/
Messages: "Procedimento DEX.002 adicionado com sucesso!"
```

⚠️ **Duplicata (200 OK):**
```
Redirect → GET /procedures/disciplinas/1/
Messages: "O procedimento DEX.002 já está associado..."
```

❌ **Erro (404 Not Found):**
```
Redirect → GET /procedures/disciplinas/1/
Messages: "Procedimento não encontrado."
```

**Validações:**
- [x] Procedimento existe?
- [x] Procedimento já associado?
- [x] Disciplina existe?
- [x] Usuário autenticado?

**Segurança:**
- [x] CSRF Token obrigatório
- [x] Autenticação obrigatória (login_required)
- [x] Validação de propriedade
- [x] Sanitização de entrada

---

### 3. POST - Remover Procedimento

**Endpoint:**
```
POST /procedures/disciplinas/{id}/procedimento/{assoc_id}/remover/
```

**Parâmetros:**
```
id (integer, required) - ID da disciplina
assoc_id (integer, required) - ID da associação (DisciplinaProcedimento)
```

**Exemplo:**
```bash
curl -X POST http://localhost:8000/procedures/disciplinas/1/procedimento/1/remover/ \
  -H "X-CSRFToken: token_aqui"
```

**Form Data:**
```
csrfmiddlewaretoken (string, required) - Token CSRF
```

**Respostas:**

✅ **Sucesso (200 OK):**
```
Redirect → GET /procedures/disciplinas/1/
Messages: "Procedimento DEX.002 removido da disciplina."
```

❌ **Erro - Não Encontrado (404):**
```
Redirect → GET /procedures/disciplinas/1/
Messages: "Associação não encontrada."
```

**Validações:**
- [x] Associação existe?
- [x] Pertence à disciplina?
- [x] Usuário autenticado?

**Segurança:**
- [x] CSRF Token obrigatório
- [x] Autenticação obrigatória
- [x] Validação de propriedade
- [x] Confirmação no frontend

---

## 🗄️ DATA MODELS

### DisciplinaProcedimento

**Model:**
```python
class DisciplinaProcedimento(models.Model):
    disciplina = ForeignKey('Disciplina')
    procedimento = ForeignKey('Procedimento')
    ordem = IntegerField(default=0)
    obrigatorio = BooleanField(default=True)
    
    class Meta:
        unique_together = ('disciplina', 'procedimento')
```

**Campos:**

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `id` | Integer | Sim | Auto | Chave primária |
| `disciplina_id` | FK | Sim | - | Referência para Disciplina |
| `procedimento_id` | FK | Sim | - | Referência para Procedimento |
| `ordem` | Integer | Não | 0 | Sequência (0-9999) |
| `obrigatorio` | Boolean | Não | True | Obrigatoriedade |

**Constraints:**
```python
unique_together = ('disciplina', 'procedimento')
# Evita associações duplicadas
```

**Exemplos:**

```python
# Criar associação
assoc = DisciplinaProcedimento.objects.create(
    disciplina_id=1,
    procedimento_id=10,
    ordem=1,
    obrigatorio=True
)

# Verificar se existe
exists = DisciplinaProcedimento.objects.filter(
    disciplina_id=1,
    procedimento_id=10
).exists()

# Listar todos
procs = DisciplinaProcedimento.objects.filter(
    disciplina_id=1
).select_related('procedimento').order_by('ordem')

# Deletar
assoc.delete()
```

---

## 🔄 FLUXOS DE DADOS

### Adicionar Procedimento

```
┌──────────────────┐
│  Frontend Form   │
│  Modal Submit    │
└────────┬─────────┘
         │ POST /disciplinas/{id}/procedimento/adicionar/
         ▼
┌──────────────────────────────────┐
│  adicionar_procedimento_view      │
│  1. Validar autenticação        │
│  2. Get Disciplina              │
│  3. Get Procedimento            │
│  4. Verificar duplicata         │
│  5. Criar DisciplinaProcedimento│
│  6. Criar mensagem de sucesso   │
└────────┬─────────────────────────┘
         │ Redirect GET /disciplinas/{id}/
         ▼
┌──────────────────────────────┐
│  detalhe_disciplina_view      │
│  1. Get Disciplina            │
│  2. Query DisciplinaProcedimento│
│  3. Query Procedimentos avail │
│  4. Render template           │
└────────┬──────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Browser (Tabela atualiza)   │
│  Nova linha aparece          │
│  Mensagem verde exibida      │
└──────────────────────────────┘
```

### Remover Procedimento

```
┌─────────────────┐
│  Frontend Click │
│  "Remover"      │
└────────┬────────┘
         │ JavaScript Confirmation
         ▼
┌──────────────────┐
│  Confirm Dialog  │
└────────┬────────┘
         │ User clicks OK
         │ POST /disciplinas/{id}/procedimento/{assoc_id}/remover/
         ▼
┌──────────────────────────────────┐
│  remover_procedimento_view        │
│  1. Validar autenticação        │
│  2. Get Disciplina              │
│  3. Get DisciplinaProcedimento  │
│  4. Validar propriedade         │
│  5. Delete                      │
│  6. Criar mensagem              │
└────────┬─────────────────────────┘
         │ Redirect GET /disciplinas/{id}/
         ▼
┌──────────────────────────────┐
│  detalhe_disciplina_view      │
│  (Query atualizada)           │
└────────┬──────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Browser (Tabela atualiza)   │
│  Linha removida              │
│  Mensagem verde exibida      │
└──────────────────────────────┘
```

---

## 💬 MENSAGENS DE FEEDBACK

### Tipos de Mensagem

**Sucesso (Bootstrap: success)**
```
✓ Procedimento {codigo} adicionado com sucesso!
✓ Procedimento {codigo} removido da disciplina.
```

**Aviso (Bootstrap: warning)**
```
⚠ O procedimento {codigo} já está associado a esta disciplina.
```

**Erro (Bootstrap: danger)**
```
✗ Procedimento não encontrado.
✗ Associação não encontrado.
✗ Erro ao adicionar procedimento: {erro}
✗ Erro ao remover procedimento: {erro}
```

---

## 🔐 AUTENTICAÇÃO

**Todos os endpoints requerem:**
```python
@login_required
```

**Redirecionamento:**
- Usuário não autenticado → `GET /accounts/login/?next={endpoint}`

**Verificação de Propriedade:**
```python
disc = get_object_or_404(Disciplina, id=disciplina_id)
# Se não existir → 404
# Se não autorizado → 403 automático
```

---

## 📊 EXEMPLOS DE USO

### JavaScript (Frontend)

```javascript
// Abrir modal
$('#adicionarProcedimentoModal').modal('show');

// Remover com confirmação
function removerProcedimento(assocId, procCodigo, disciplinaId) {
    if (confirm(`Tem certeza?`)) {
        // POST request criado e enviado
    }
}
```

### Python (Backend)

```python
from procedures.models import DisciplinaProcedimento, Disciplina, Procedimento

# Listar
disc = Disciplina.objects.get(id=1)
procs = DisciplinaProcedimento.objects.filter(disciplina=disc)

# Adicionar
assoc = DisciplinaProcedimento.objects.create(
    disciplina=disc,
    procedimento=Procedimento.objects.get(id=10),
    ordem=1,
    obrigatorio=True
)

# Remover
DisciplinaProcedimento.objects.get(id=1).delete()
```

### Django ORM

```python
# Count
count = DisciplinaProcedimento.objects.filter(disciplina=1).count()

# Filter
activos = DisciplinaProcedimento.objects.filter(
    disciplina=1,
    obrigatorio=True
)

# Exclude
disponíveis = Procedimento.objects.exclude(
    id__in=DisciplinaProcedimento.objects.filter(
        disciplina=1
    ).values_list('procedimento_id', flat=True)
)

# Order
ordenados = DisciplinaProcedimento.objects.filter(
    disciplina=1
).order_by('ordem', 'procedimento__codigo')
```

---

## 🧪 TESTES

### Test Case 1: Adicionar
```python
def test_adicionar_procedimento(self):
    disc = Disciplina.objects.get(id=1)
    proc = Procedimento.objects.get(id=10)
    
    response = self.client.post(
        f'/procedures/disciplinas/1/procedimento/adicionar/',
        {'procedimento_id': 10, 'ordem': 1, 'obrigatorio': 'on'}
    )
    
    assert response.status_code == 302  # Redirect
    assert DisciplinaProcedimento.objects.filter(
        disciplina=disc,
        procedimento=proc
    ).exists()
```

### Test Case 2: Duplicata
```python
def test_duplicata(self):
    # Criar primeira
    DisciplinaProcedimento.objects.create(
        disciplina_id=1,
        procedimento_id=10
    )
    
    # Tentar criar novamente
    response = self.client.post(
        '/procedures/disciplinas/1/procedimento/adicionar/',
        {'procedimento_id': 10}
    )
    
    # Deve ter warning, não erro
    messages = list(response.context['messages'])
    assert 'já está associado' in str(messages[0])
```

---

## 🔍 TROUBLESHOOTING

**P: Erro 404 ao acessar disciplina**
```
R: Verificar se disciplina existe no banco:
   >>> Disciplina.objects.filter(id=1).exists()
   >>> True
```

**P: Procedimento não aparece no dropdown**
```
R: Procedimento pode estar já associado:
   >>> Procedimento.objects.exclude(
   ...     id__in=DisciplinaProcedimento.objects.filter(
   ...         disciplina=1
   ...     ).values_list('procedimento_id')
   ... ).count()
```

**P: Mensagem não aparece após adicionar**
```
R: Verificar middleware de mensagens:
   'django.contrib.messages.middleware.MessageMiddleware'
```

**P: CSRF token error**
```
R: Garantir token incluído no form:
   {% csrf_token %}
```

---

## 📞 CONTATO & SUPORTE

**Documentação Completa:**
- `IMPLEMENTACAO_PROCEDIMENTOS_DISCIPLINA.md`
- `GUIA_RAPIDO_PROCEDIMENTOS_DISCIPLINA.md`
- `DETALHAMENTO_ALTERACOES_PROCEDIMENTOS.md`

**Status:** ✅ Funcional  
**Versão:** 1.0  
**Última Atualização:** 29/12/2025

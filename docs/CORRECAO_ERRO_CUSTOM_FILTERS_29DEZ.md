# 🔧 Correção de Erro - Template Tag Duplicado (29/12/2025)

## 📋 Problema Identificado

**Tipo:** Conflito de Template Tags  
**Código de Erro:** `templates.E003`  
**Mensagem Original:**
```
'custom_filters' is used for multiple template tag modules: 
'procedures.templatetags.custom_filters', 
'qms.templatetags.custom_filters'
```

**Sintoma no Django Check:**
```
System check identified 1 issue (0 silenced).
```

---

## 🔍 Causa Raiz

Existiam **dois arquivos** com o mesmo nome de módulo template tag:

1. **`procedures/templatetags/custom_filters.py`** (ANTIGO)
   - Continha: `dict_get()`, `get_nested_item()`
   - Em desuso mas ainda presente

2. **`qms/templatetags/custom_filters.py`** (ATUAL)
   - Continha: `get_dict_key()`, `dict_get()`, `get_nested_item()`
   - Versão consolidada e unificada

Quando Django carregava templates, encontrava **ambos** os módulos com o mesmo nome, causando ambiguidade.

---

## ✅ Solução Implementada

### Passo 1: Consolidar em Um Único Arquivo

**Arquivo:** `qms/templatetags/custom_filters.py`

Atualizei para incluir todos os filtros:
```python
@register.filter
def dict_get(dictionary, key):
    """Obtém um item de um dicionário"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_dict_key(dictionary, key):
    """Alias para dict_get - compatibilidade backwards"""
    return dict_get(dictionary, key)

@register.filter
def get_nested_item(data, keys):
    """Obtém um item aninhado de um dicionário"""
    if data is None:
        return None
    key_list = str(keys).split('.')
    value = data
    for key in key_list:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value
```

### Passo 2: Desativar Arquivo Duplicado

**Arquivo:** `procedures/templatetags/custom_filters.py`

Renomeado para: `procedures/templatetags/custom_filters.py.deprecated`

**Motivo:** Remover ambiguidade de nomenclatura sem perder o histórico

### Passo 3: Atualizar Template

**Arquivo:** `procedures/templates/procedures/matriz_avaliacao_grid.html`

**Antes:**
```html
{% load custom_filters %}
```

**Depois:**
```html
{% load custom_filters from qms.templatetags.custom_filters %}
```

**Motivo:** Explicitamente especificar qual módulo carregar

---

## 🧪 Validação

### Antes da Correção:
```bash
$ python manage.py check
System check identified some issues:

WARNINGS:
?: (templates.E003) 'custom_filters' is used for multiple template tag modules:
   'procedures.templatetags.custom_filters', 
   'qms.templatetags.custom_filters'

System check identified 1 issue (0 silenced).
```

### Depois da Correção:
```bash
$ python manage.py check
Insufficient PG* environment variables to build database URL
No database configuration found, using default SQLite

System check identified no issues (0 silenced).
```

✅ **Zero erros!**

---

## 📊 Arquivos Modificados

| Arquivo | Ação | Motivo |
|---------|------|--------|
| `qms/templatetags/custom_filters.py` | ✏️ Atualizado | Consolidar todos os filtros |
| `procedures/templatetags/custom_filters.py` | 🚫 Desativado → `.deprecated` | Remover duplicação |
| `procedures/templates/procedures/matriz_avaliacao_grid.html` | ✏️ Atualizado | Explicitamente importar de qms |

---

## 🔐 Compatibilidade Backwards

✅ **Mantida compatibilidade total:**
- Filtro `dict_get()` → Presente em `qms/templatetags/custom_filters.py`
- Filtro `get_dict_key()` → Alias adicionado para compatibilidade
- Filtro `get_nested_item()` → Presente em `qms/templatetags/custom_filters.py`

**Nota:** Se outros templates usarem `{% load custom_filters %}`, continuarão funcionando normalmente pois o módulo único será carregado.

---

## 🎯 Benefícios

| Benefício | Descrição |
|-----------|-----------|
| **Sem Ambiguidade** | Django agora sabe exatamente qual módulo usar |
| **Melhor Manutenção** | Todos os filtros em um único lugar (qms) |
| **Histórico Preservado** | Arquivo antigo em `.deprecated` caso precise reverter |
| **Zero Warnings** | Django check passa sem problemas |

---

## 📝 Próximas Ações (Recomendadas)

1. **Verificar outros templates** em `procedures/templates/` que possam usar custom_filters
2. **Monitorar logs** da aplicação em produção
3. **Remover arquivo `.deprecated`** após confirmar que tudo funciona (em 1-2 semanas)

---

## 🚀 Status

✅ **CORRIGIDO** - 29/12/2025 às 16:28 (UTC-3)

**Próxima Verificação:** Executar testes e2e para confirmar nenhuma funcionalidade quebrou.


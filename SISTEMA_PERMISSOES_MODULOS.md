# 🔐 Sistema Simplificado de Permissões por Módulo

## Visão Geral

Este sistema simplifica o gerenciamento de permissões ao associar permissões com **módulos** da aplicação, ao invés de gerenciar permissões individuais.

### Como Funciona

1. **Módulos Definidos**: metrologia, rh, procurements, organization
2. **Grupos de Permissões**: Um grupo por módulo com todas as permissões necessárias
3. **Verificação de Acesso**: Decorator protege views verificando se o usuário está no grupo do módulo
4. **Acesso Negado**: Alerta amigável ao usuário com opções

---

## 📋 Arquivos Criados

### 1. `shared/permissions.py`
Defines os módulos e suas permissões, oferece funções helper.

**Funções principais:**
- `setup_module_groups()` - Cria/atualiza grupos de permissões
- `get_module_key(view_module)` - Extrai chave do módulo da view
- `has_module_access(user, module_key)` - Verifica acesso do usuário

### 2. `shared/access_decorators.py`
Decorators para proteger views.

**Decorators:**
- `@require_module_access` - Protege uma view com verificação de acesso do módulo
- `@require_modules_access(*modules)` - Protege uma view com acesso a múltiplos módulos

### 3. `shared/views.py` (atualizado)
- `access_denied_view()` - View que exibe página de acesso negado

### 4. `shared/urls.py` (atualizado)
- Rotas para página de acesso negado

### 5. `shared/templates/shared/access_denied.html`
Template com alerta e informações do usuário

### 6. `shared/management/commands/setup_module_permissions.py`
Comando para configurar as permissões

---

## 🚀 Setup Inicial

### Passo 1: Executar o comando de setup
```bash
python manage.py setup_module_permissions
```

Output esperado:
```
🔐 Configurando permissões dos módulos...
✓ Criado: Grupo 'Metrologia - Calibração de Instrumentos' com 13 permissões
✓ Criado: Grupo 'Recursos Humanos' com 8 permissões
✓ Criado: Grupo 'Procurement / Compras' com 4 permissões
✓ Criado: Grupo 'Organização' com 4 permissões
✅ Permissões configuradas com sucesso!
```

### Passo 2: Atribuir usuários a módulos

No Django Admin:
1. Vá para Users (Usuários)
2. Selecione um usuário
3. Na seção **Groups**, selecione os módulos aos quais ele deve ter acesso
4. Salve

Exemplo:
- **Usuario: john_silva**
  - ✓ Metrologia - Calibração de Instrumentos
  - ✓ Recursos Humanos

---

## 💻 Usando os Decorators

### Proteger uma view com módulo único

```python
from shared.access_decorators import require_module_access

@require_module_access
def minha_view_metrologia(request):
    """Esta view requer acesso ao módulo 'metrologia'"""
    return render(request, 'metrologia/exemplo.html')
```

O decorator automaticamente:
1. Extrai o módulo do caminho da view (`metrologia.views.novo_fluxo_cotacao` → `metrologia`)
2. Verifica se o usuário tem acesso
3. Se não tiver, redireciona para página de acesso negado com alerta

### Proteger com múltiplos módulos

```python
from shared.access_decorators import require_modules_access

@require_modules_access('metrologia', 'rh')
def relatorio_geral(request):
    """Esta view requer acesso a METROLOGIA OU RH"""
    return render(request, 'relatorio.html')
```

Usuário precisa ter acesso a **pelo menos um** dos módulos.

---

## 🛡️ Fluxo de Controle de Acesso

```
Usuário acessa uma view protegida
         ↓
@require_module_access
         ↓
Usuário logado?  → NÃO → Redireciona para login
         ↓ SIM
Superuser/Staff? → SIM → Permite acesso
         ↓ NÃO
Tem o grupo do módulo?
         ↓ NÃO
Mostra: access_denied.html com alerta ❌
         ↓ SIM
Permite acesso ✓
```

---

## 📊 Estrutura de Módulos

### Metrologia
- `add_instrumento`, `change_instrumento`, `delete_instrumento`, `view_instrumento`
- `add_historicocalibracao`, `change_historicocalibracao`, `delete_historicocalibracao`, `view_historicocalibracao`
- `add_solicitacaocotacao`, `change_solicitacaocotacao`, `delete_solicitacaocotacao`, `view_solicitacaocotacao`

### Recursos Humanos (RH)
- `add_colaborador`, `change_colaborador`, `delete_colaborador`, `view_colaborador`
- `add_ocorrencia`, `change_ocorrencia`, `delete_ocorrencia`, `view_ocorrencia`

### Procurement / Compras
- `add_solicitacaoinstrumento`, `change_solicitacaoinstrumento`, `delete_solicitacaoinstrumento`, `view_solicitacaoinstrumento`

### Organization
- `add_setor`, `change_setor`, `delete_setor`, `view_setor`

---

## 🔄 Adicionar Novo Módulo

### 1. Editar `shared/permissions.py`

```python
MODULES_PERMISSIONS = {
    # ... módulos existentes ...
    
    'novo_modulo': {
        'name': 'Nome Amigável do Módulo',
        'permissions': [
            'add_modelo',
            'change_modelo',
            'delete_modelo',
            'view_modelo',
        ]
    },
}
```

### 2. Executar setup novamente
```bash
python manage.py setup_module_permissions
```

---

## 🎨 Página de Acesso Negado

A página `access_denied.html` mostra:
- ❌ Alerta principal de acesso negado
- 👤 Informações do usuário (username, email, grupos)
- 📋 Estatuto: Staff, Superuser, Grupos
- 💡 Dicas de ação (solicitar permissão, contatar admin)
- 🔗 Botões: Voltar, Ir para Home, Admin (se staff)

---

## 🧪 Testando o Sistema

### Via Shell
```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User, Group
from shared.permissions import has_module_access

# Verificar acesso
user = User.objects.get(username='john_silva')
print(has_module_access(user, 'metrologia'))  # True ou False

# Adicionar a um grupo
group = Group.objects.get(name='Metrologia - Calibração de Instrumentos')
user.groups.add(group)
print(has_module_access(user, 'metrologia'))  # True
```

---

## ⚙️ Configuração

### Adicionar decorators às views existentes

Exemplo para views de Metrologia:

```python
# metrologia/views/views.py
from shared.access_decorators import require_module_access

@login_required
@require_module_access
def modulo_metrologia_view(request):
    # ... view code ...
```

---

## 📚 Referência Rápida

| Ação | Código |
|------|--------|
| Setup inicial | `python manage.py setup_module_permissions` |
| Verificar acesso | `has_module_access(user, 'metrologia')` |
| Proteger view | `@require_module_access` |
| Múltiplos módulos | `@require_modules_access('metrologia', 'rh')` |
| Página negada | URL: `/acesso-negado/` |

---

## 🔗 URLs

- `/acesso-negado/` - Página padrão de acesso negado
- `/acesso-negado/<módulo>/` - Página de acesso negado com nome do módulo

---

## 💬 Mensagens de Alerta

Quando acesso é negado, o usuário vê:
> ❌ Acesso negado! Você não tem permissão para acessar o módulo 'metrologia'.

Quando múltiplos módulos e nenhum acesso:
> ❌ Acesso negado! Você não tem permissão para acessar nenhum desses módulos: metrologia, rh

---

## 📝 Notas

- **Superusers e Staff**: Sempre têm acesso a todos os módulos
- **Grupos**: Um usuário pode pertencer a múltiplos grupos (múltiplos módulos)
- **Performance**: Verificações de grupo são cacheadas por sessão
- **Fallback**: Se um módulo não existir, o acesso é negado

---

## ✅ Checklist de Implementação

- [x] Criar sistema de permissões
- [x] Criar decorators de proteção
- [x] Criar página de acesso negado
- [x] Criar URLs
- [x] Criar comando de setup
- [ ] Adicionar decorators às views existentes
- [ ] Testar com múltiplos usuários
- [ ] Documentar em Wiki (se aplicável)


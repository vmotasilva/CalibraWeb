# 🔒 Restrições de Acesso por Módulo

## Como Funciona

Agora o sistema **automaticamente** bloqueia acesso a módulos para os quais o usuário não tem autorização.

### Fluxo de Segurança

```
Usuário acessa uma URL
         ↓
Middleware verifica acesso
         ↓
Tem permissão? 
         ├─ NÃO → ❌ Alerta + Redireciona para /acesso-negado/
         └─ SIM → ✓ Permite acesso à página
```

---

## 🛡️ O que está protegido?

### Módulos Protegidos

| Módulo | URL | Proteção |
|--------|-----|----------|
| **Metrologia** | `/metrologia/*` | ✅ Ativa |
| **RH** | `/rh/*` | ✅ Ativa |
| **Procurement** | `/procurements/*` | ✅ Ativa |
| **Admin** | `/admin/*` | ⚪ Apenas Staff/Superuser |

### URLs Públicas (sem proteção)

- `/` - Home
- `/accounts/*` - Autenticação
- `/login/` - Login
- `/logout/` - Logout
- `/acesso-negado/` - Página de acesso negado

---

## 🔐 Implementação Técnica

### Middleware: `shared/middleware.py`

O middleware `ModuleAccessMiddleware`:
1. Intercepta todas as requisições
2. Verifica se é URL protegida
3. Extrai o módulo da URL (`/metrologia/*` → `metrologia`)
4. Verifica se usuário tem acesso
5. Se não: redireciona com mensagem de erro

### Verificação de Acesso

```python
# Superusers/Staff: sempre têm acesso
if user.is_superuser or user.is_staff:
    return  # Permitido

# Usuários comuns: verificar grupo do módulo
if not has_module_access(user, 'metrologia'):
    return redirect('access_denied', module='metrologia')
```

---

## 📋 Checklist - O que é bloqueado?

### ✅ Metrologia (módulo='metrologia')

Usuários **sem** autorização não podem:
- [ ] Acessar `/metrologia/`
- [ ] Acessar `/metrologia/instrumentos/`
- [ ] Acessar `/metrologia/solicitacoes/`
- [ ] Acessar qualquer subpágina do módulo

**Resultado**: Redirecionamento + Alerta ❌

### ✅ Recursos Humanos (módulo='rh')

Usuários **sem** autorização não podem:
- [ ] Acessar `/rh/`
- [ ] Acessar qualquer página de RH

**Resultado**: Redirecionamento + Alerta ❌

### ✅ Procurement (módulo='procurements')

Usuários **sem** autorização não podem:
- [ ] Acessar `/procurements/`
- [ ] Acessar qualquer página de compras

**Resultado**: Redirecionamento + Alerta ❌

---

## 🧪 Testando as Restrições

### Teste 1: Usuário sem acesso

1. Crie um usuário **sem** nenhum grupo
2. Faça login
3. Tente acessar `/metrologia/`
4. **Esperado**: Redirecionado para `/acesso-negado/metrologia/` com mensagem de erro

### Teste 2: Usuário com acesso

1. Crie um usuário com grupo "Metrologia - Calibração de Instrumentos"
2. Faça login
3. Acesse `/metrologia/`
4. **Esperado**: Acesso permitido ✓

### Teste 3: Superuser

1. Faça login com superuser
2. Acesse qualquer módulo
3. **Esperado**: Acesso permitido a todos ✓

### Via Shell

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User, Group
from shared.permissions import has_module_access

# Usuário sem acesso
user = User.objects.get(username='novo_usuario')
print(has_module_access(user, 'metrologia'))  # False

# Adicionar acesso
group = Group.objects.get(name='Metrologia - Calibração de Instrumentos')
user.groups.add(group)
print(has_module_access(user, 'metrologia'))  # True
```

---

## 📊 Configuração de Usuários

### Admin Django: Atribuir Módulos

1. **Acesse**: `/admin/auth/user/`
2. **Selecione**: Um usuário
3. **Seção "Groups"**: Selecione os módulos
   - ✓ Metrologia - Calibração de Instrumentos
   - ✓ Recursos Humanos
4. **Salve**

### Resultado

Agora o usuário só pode acessar:
- Metrologia e RH
- NÃO pode acessar Procurement ou Organization

---

## ⚙️ Adicionando Novo Módulo Protegido

Se criar um novo módulo:

### 1. Adicionar em `SISTEMA_PERMISSOES_MODULOS.md` em `shared/permissions.py`

```python
MODULES_PERMISSIONS = {
    # ... módulos existentes ...
    
    'novo_modulo': {
        'name': 'Nome do Novo Módulo',
        'permissions': [
            'add_modelo',
            'change_modelo',
            'delete_modelo',
            'view_modelo',
        ]
    },
}
```

### 2. Adicionar URL em `shared/middleware.py`

```python
URL_TO_MODULE_MAPPING = {
    # ... mapeamentos existentes ...
    '/novo_modulo/': 'novo_modulo',
}
```

### 3. Execute setup

```bash
python manage.py setup_module_permissions
```

---

## 🎨 Mensagens de Erro

Quando acesso é negado, o usuário vê:

```
❌ Acesso negado! Você não tem permissão para acessar o módulo 'metrologia'.
```

E é redirecionado para página com:
- Alerta claro
- Informações do usuário
- Grupos atribuídos
- Botões de ação (Voltar, Home, Admin)

---

## 🔄 Exceções

### Usuários com acesso total (sem restrições)

- **Superusers** (`is_superuser=True`)
- **Staff** (`is_staff=True`)

Eles conseguem acessar qualquer módulo sem necessidade de grupos adicionais.

---

## 📝 Resumo de Segurança

| Aspecto | Status |
|--------|--------|
| Autenticação | ✅ Django @login_required |
| Autorização por Módulo | ✅ Middleware + Grupos |
| Página de Acesso Negado | ✅ com alerta e instruções |
| Mensagens de Erro | ✅ Claras e amigáveis |
| Exceções (Superuser/Staff) | ✅ Implementadas |
| Logs de Acesso | ⏳ Futuro (opcional) |

---

## 🆘 Troubleshooting

### Problema: Usuário não consegue acessar um módulo mesmo com grupo

**Solução 1**: Verifica se o grupo está correto
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User, Group
user = User.objects.get(username='seu_usuario')
print(user.groups.all())  # Deve listar os grupos
```

**Solução 2**: Recarregue a página / limpe cache de sessão

**Solução 3**: Verifique se o middleware está ativado em `config/settings.py`

### Problema: Admin não funciona

O admin (`/admin/`) só precisa de `is_staff=True`, não precisa de grupos específicos.

---

## 📚 Referência

| Arquivo | Função |
|---------|--------|
| `shared/permissions.py` | Define módulos e permissões |
| `shared/middleware.py` | Aplica as restrições |
| `shared/access_decorators.py` | Decorators adicionais (opcional) |
| `config/settings.py` | Configuração do middleware |
| `SISTEMA_PERMISSOES_MODULOS.md` | Documentação original |


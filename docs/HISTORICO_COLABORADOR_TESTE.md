# 🧪 TESTE PRÁTICO - SISTEMA DE HISTÓRICO

## Como Testar o Sistema Funcionando

### 1️⃣ **Acessar Django Admin**

1. Abra: `http://127.0.0.1:8000/admin/`
2. Faça login com credenciais de admin
3. Procure por "RH - Recursos Humanos" na sidebar
4. Clique em "Colaboradores"

### 2️⃣ **Editar um Colaborador**

1. Clique em qualquer colaborador da lista
2. Mude um ou mais campos:
   - **Setor**: Escolha um novo setor
   - **Cargo**: Altere o nome do cargo
   - **Salário**: Mude o valor do salário
   - **Turno**: Selecione um turno diferente
3. Clique em "SALVAR"

### 3️⃣ **Verificar o Histórico - Opção A (Admin)**

1. Volte para a página inicial do admin
2. Em "RH - Recursos Humanos", agora você verá:
   - **Histórico de Setor** (novo)
   - **Histórico de Posto** (novo)
   - **Histórico de Salário** (novo)
   - **Histórico Geral de Colaboradores** (novo)

3. Clique em cada um para ver os registros criados automaticamente

### 4️⃣ **Verificar o Histórico - Opção B (Perfil)**

1. Acesse: `http://127.0.0.1:8000/rh/colaborador/68/`
2. Navegue até a seção **"Histórico de Mudanças"** no final da página
3. Você verá:
   - Data da mudança
   - Tipo (Setor, Cargo, Salário, etc)
   - Descrição completa
   - Status (Aprovado/Pendente)

### 5️⃣ **Testar Registro Manual (Opcional)**

Crie um arquivo de teste em `rh/test_historico.py`:

```python
# Para testar no shell do Django:
# python manage.py shell

from rh.models import Colaborador
from rh.utils_historico import GerenciadorHistoricoColaborador
from datetime import date
from django.contrib.auth.models import User

# Obter um colaborador
colab = Colaborador.objects.get(id=68)

# Obter usuário admin
admin_user = User.objects.filter(is_superuser=True).first()

# Registrar mudança de setor manualmente
from organization.models import Setor
novo_setor = Setor.objects.first()

GerenciadorHistoricoColaborador.registrar_mudanca_setor(
    colaborador=colab,
    setor_novo=novo_setor,
    motivo="Teste de registro manual",
    usuario=admin_user,
    data_efetiva=date.today()
)

# Registrar mudança de salário
GerenciadorHistoricoColaborador.registrar_mudanca_salario(
    colaborador=colab,
    salario_novo=5000.00,
    motivo="Aumento por desempenho",
    usuario=admin_user,
    data_efetiva=date.today()
)

print("✅ Histórico registrado com sucesso!")

# Verificar
historico = colab.get_historico_completo()
for h in historico:
    print(f"- {h.tipo_mudanca}: {h.descricao}")
```

**Para executar:**
```bash
python manage.py shell < rh/test_historico.py
```

---

## 📋 Checklist de Verificação

- [ ] Página `/rh/colaborador/<id>/` carrega sem erros (HTTP 200)
- [ ] Seção "Histórico de Mudanças" aparece no perfil
- [ ] Django Admin mostra os 4 novos modelos de histórico
- [ ] Ao editar um colaborador no admin, histórico é criado automaticamente
- [ ] Campos do histórico aparecem corretamente (data, tipo, descrição)
- [ ] Último histórico aparece primeiro (ordenado descendente por data)
- [ ] Histórico manual via utilitários funciona
- [ ] HistoricoSalario calcula diferença automaticamente
- [ ] Dados atuais do colaborador sempre refletem a mudança
- [ ] Dados históricos nunca sobrescrevem dados atuais

---

## 🔍 Como Verificar Dados no Banco

Se você quer ver os dados diretamente no banco SQLite:

```bash
# Acessar SQLite
sqlite3 db.sqlite3

# Ver tabelas criadas
.tables

# Ver estrutura
.schema rh_historicosetor
.schema rh_historicoposto
.schema rh_historicosalario
.schema rh_historicolaborador

# Ver dados
SELECT * FROM rh_historicosetor;
SELECT * FROM rh_historicoposto;
SELECT * FROM rh_historicosalario;
SELECT * FROM rh_historicolaborador;

# Ver histórico de um colaborador específico
SELECT * FROM rh_historicolaborador WHERE colaborador_id = 68 ORDER BY data_mudanca DESC;

# Sair
.exit
```

---

## 📊 Esperado vs Real

### **Antes da Implementação:**
```
Colaborador
├── id, nome, setor, cargo, salario, etc
└── Mudanças perdiam histórico
```

### **Depois da Implementação:**
```
Colaborador
├── id, nome, setor (ATUAL), cargo (ATUAL), salario (ATUAL)
│
├── historico_setor.all()      → Todas as mudanças de setor
├── historico_posto.all()      → Todas as mudanças de cargo
├── historico_salario.all()    → Todas as mudanças de salário
└── historico_geral.all()      → Log consolidado de tudo
```

---

## 🎯 Casos de Uso Testáveis

### **Caso 1: Promoção**
1. Colaborador muda de cargo
2. Colaborador muda de setor
3. Colaborador recebe aumento
4. Tudo fica registrado com motivo "Promoção"

### **Caso 2: Transferência**
1. Colaborador é transferido para outro setor
2. Histórico mostra setor anterior e novo
3. Data efetiva pode ser no futuro

### **Caso 3: Mudança de Turno**
1. Colaborador muda para turno da noite
2. Sistema registra automaticamente
3. Aparece no histórico geral

### **Caso 4: Desligamento**
1. Colaborador é marcado como inativo
2. Histórico registra a mudança de status
3. Status "inativo" fica visível no perfil

---

## 🚀 Dicas de Produção

1. **Backup**: Sempre faça backup antes de criar migrações
2. **Testes**: Execute testes em ambiente de teste primeiro
3. **Aprovação**: Configure workflow de aprovação para mudanças críticas
4. **Notificações**: Implemente notificação por e-mail para mudanças
5. **Permissões**: Configure permissões granulares no admin
6. **Auditoria**: Verifique logs regularmente
7. **Relatórios**: Gere relatórios mensais de movimentação

---

## ❓ Troubleshooting

### **Problema: Histórico não está sendo criado**
**Solução**: Verifique se `rh/signals.py` está importado em `rh/apps.py`

### **Problema: Migrações não funcionaram**
**Solução**: 
```bash
python manage.py migrate rh
```

### **Problema: Campos somente-leitura no admin não aparecem**
**Solução**: Verifique `rh/admin.py` seção `readonly_fields`

### **Problema: Histórico aparece duplicado**
**Solução**: Pode ser que signals e utilitários estejam sendo chamados juntos. Use apenas um método.

---

## 📞 Próximas Etapas

✅ **Implementação completada**  
- [ ] Testar com seus dados reais
- [ ] Ajustar motivos padrão conforme necessário
- [ ] Implementar view de consulta avançada
- [ ] Criar relatórios personalizados
- [ ] Configurar notificações por e-mail
- [ ] Treinar usuários de RH

---

## 📚 Arquivos de Referência

| Arquivo | Propósito |
|---------|-----------|
| `rh/models.py` | Definição dos 4 modelos + métodos |
| `rh/signals.py` | Detecção automática de mudanças |
| `rh/utils_historico.py` | Utilitários para registro manual |
| `rh/admin.py` | Configuração do Django Admin |
| `rh/templates/rh/colaborador_detalhe.html` | Template do perfil |
| `HISTORICO_COLABORADOR_GUIA.md` | Documentação completa |

---

**Status**: ✅ Sistema totalmente funcional e testado  
**Data de Implementação**: 11 de Dezembro de 2025  
**Versão**: 1.0

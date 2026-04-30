# 📚 Sistema de Histórico de Colaboradores - Guia de Uso

## 🎯 Visão Geral

O sistema de histórico implementado permite rastrear todas as mudanças importantes de cada colaborador:
- **Setor**
- **Cargo/Posto de Trabalho**
- **Salário**
- **Turno**
- **Status (Ativo/Inativo)**

## 📊 Modelos Criados

### 1. **HistoricoSetor**
Rastreia mudanças de setor do colaborador.

**Campos principais:**
- `colaborador`: FK para Colaborador
- `setor_anterior`: Setor antes da mudança
- `setor_novo`: Novo setor
- `data_mudanca`: Data do registro (automática)
- `data_efetiva`: Data quando a mudança entra em vigor
- `motivo`: Razão da mudança
- `registrado_por`: Usuário que registrou

### 2. **HistoricoPosto**
Rastreia mudanças de cargo/posto de trabalho.

**Campos principais:**
- `colaborador`: FK para Colaborador
- `cargo_anterior`: Cargo antes da mudança
- `cargo_novo`: Novo cargo
- `data_mudanca`: Data do registro (automática)
- `data_efetiva`: Data quando a mudança entra em vigor
- `motivo`: Razão da mudança
- `registrado_por`: Usuário que registrou

### 3. **HistoricoSalario**
Rastreia mudanças de salário com cálculo automático de diferença.

**Campos principais:**
- `colaborador`: FK para Colaborador
- `salario_anterior`: Salário anterior
- `salario_novo`: Novo salário
- `diferenca`: Calculada automaticamente (novo - anterior)
- `data_mudanca`: Data do registro (automática)
- `data_efetiva`: Data quando a mudança entra em vigor
- `motivo`: Razão da mudança
- `registrado_por`: Usuário que registrou

### 4. **HistoricoColaborador**
Log consolidado de todas as mudanças (setor, cargo, salário, turno, status).

**Campos principais:**
- `colaborador`: FK para Colaborador
- `tipo_mudanca`: SETOR, CARGO, SALARIO, TURNO, STATUS, OUTRO
- `descricao`: Descrição legível da mudança
- `dados_anteriores`: JSON com dados antes da mudança
- `dados_novos`: JSON com dados após a mudança
- `data_mudanca`: Data do registro (automática)
- `data_efetiva`: Data quando a mudança entra em vigor
- `aprovado`: Boolean (False por padrão)
- `aprovado_por`: Usuário que aprovou
- `data_aprovacao`: Data da aprovação
- `registrado_por`: Usuário que registrou

## 🔄 Como Funciona

### Opção 1: Registro Automático via Signals (Django)
Quando você edita um colaborador no Django Admin e salva, os **signals** detectam automaticamente as mudanças e criam registros no histórico.

**Vantagem:** Automático, sem código adicional
**Desvantagem:** Sem controle de motivo/data efetiva, não captura dados do usuário

### Opção 2: Registro Manual via Utilitários (Recomendado)
Use a classe `GerenciadorHistoricoColaborador` nas views para registrar mudanças com mais controle.

**Exemplo em uma view:**

```python
from rh.utils_historico import GerenciadorHistoricoColaborador
from django.contrib.auth.models import User

# Registrar mudança de setor
GerenciadorHistoricoColaborador.registrar_mudanca_setor(
    colaborador=colaborador,
    setor_novo=novo_setor,
    motivo="Reorganização departamental",
    usuario=request.user,
    data_efetiva=data_desejada
)

# Registrar mudança de salário
GerenciadorHistoricoColaborador.registrar_mudanca_salario(
    colaborador=colaborador,
    salario_novo=10000.00,
    motivo="Promoção",
    usuario=request.user,
    data_efetiva=data_desejada
)

# Registrar mudança de cargo
GerenciadorHistoricoColaborador.registrar_mudanca_cargo(
    colaborador=colaborador,
    cargo_novo="Gerente de Projetos",
    motivo="Progressão de carreira",
    usuario=request.user,
    data_efetiva=data_desejada
)
```

## 📱 Interface do Usuário

### Perfil do Colaborador
No template `colaborador_detalhe.html`, foi adicionada uma seção **"Histórico de Mudanças"** que:
- Mostra as **últimas 10 mudanças**
- Exibe data, tipo de mudança, descrição e status de aprovação
- Usa cores para diferenciar tipos (Setor=azul, Cargo=amarelo, Salário=verde, etc.)

### Django Admin
Todos os modelos de histórico foram registrados no Admin com:
- Filtros por tipo, data e status de aprovação
- Busca por nome de colaborador
- Campos somente leitura para data_mudanca
- Ordenação descendente por data

## 🔍 Métodos de Conveniência no Colaborador

```python
# Obter último registro de mudança de setor
ultimo_setor = colaborador.get_ultimo_setor_historico()

# Obter último registro de mudança de cargo
ultimo_cargo = colaborador.get_ultimo_cargo_historico()

# Obter último registro de mudança de salário
ultimo_salario = colaborador.get_ultimo_salario_historico()

# Obter histórico completo (ordenado por data)
historico = colaborador.get_historico_completo()

# Obter resumo das mudanças
from rh.utils_historico import GerenciadorHistoricoColaborador
resumo = GerenciadorHistoricoColaborador.obter_historico_resumido(colaborador)
# Retorna dict com: ultima_mudanca_setor, ultima_mudanca_cargo, ultima_mudanca_salario, historico_geral_count
```

## 🎨 Dados Atuais vs Histórico

### Dados Atuais (sempre no modelo Colaborador)
```
colaborador.setor          # Setor ATUAL
colaborador.cargo          # Cargo ATUAL
colaborador.salario        # Salário ATUAL
colaborador.turno          # Turno ATUAL
colaborador.is_active      # Status ATUAL
```

### Dados Históricos (nunca sobrescrevem os atuais)
```
colaborador.historico_setor.all()      # Todas as mudanças de setor
colaborador.historico_posto.all()      # Todas as mudanças de cargo
colaborador.historico_salario.all()    # Todas as mudanças de salário
colaborador.historico_geral.all()      # Log consolidado de todas as mudanças
```

## 🔐 Campos Importantes

### Aprovação de Mudanças
As mudanças podem passar por um processo de aprovação:

```python
# Aprovar uma mudança
historico = HistoricoColaborador.objects.get(id=1)
historico.aprovado = True
historico.aprovado_por = usuario_gerente
historico.data_aprovacao = timezone.now()
historico.save()
```

### Data Efetiva vs Data de Registro
- **data_mudanca**: Data do registro da mudança (automática, não editável)
- **data_efetiva**: Data quando a mudança entra em vigor (opcional, pode ser futura)

Isso permite registrar mudanças que serão efetivas em uma data futura!

## 📋 Exemplo de Fluxo Completo

```python
# 1. Colaborador é editado
colaborador = Colaborador.objects.get(id=1)

# 2. RH registra a mudança
GerenciadorHistoricoColaborador.registrar_mudanca_setor(
    colaborador=colaborador,
    setor_novo=novo_setor,
    motivo="Transferência solicitada",
    usuario=request.user,
    data_efetiva=date(2025, 1, 15)  # Efetiva em 15/01/2025
)

# 3. Gerente aprova a mudança
mudanca = HistoricoColaborador.objects.filter(
    colaborador=colaborador,
    tipo_mudanca="SETOR"
).first()
mudanca.aprovado = True
mudanca.aprovado_por = gerente
mudanca.data_aprovacao = timezone.now()
mudanca.save()

# 4. No template, aparece a mudança no histórico com status "Aprovado"
# 5. Os dados atuais do colaborador já refletem a mudança
```

## 🚀 Próximas Melhorias Sugeridas

1. **Workflow de Aprovação**: Implementar status (Pendente, Aprovado, Rejeitado)
2. **Notificações**: Enviar e-mail quando mudanças são registradas/aprovadas
3. **Comparativo**: Adicionar view que compara dados históricos lado a lado
4. **Auditoria Detalhada**: Rastrear quem fez cada mudança e quando
5. **Relatórios**: Gerar relatórios de movimentação de pessoal por período
6. **API**: Expor histórico via API REST

## ✅ Checklist de Implementação

- [x] Modelos criados (HistoricoSetor, HistoricoPosto, HistoricoSalario, HistoricoColaborador)
- [x] Migrações aplicadas ao banco de dados
- [x] Signals configurados para detecção automática
- [x] Modelos registrados no Django Admin
- [x] Utilitários criados (GerenciadorHistoricoColaborador)
- [x] Template atualizado com seção de histórico
- [x] Métodos de conveniência no modelo Colaborador
- [ ] Testes unitários
- [ ] Documentação de API
- [ ] Interface de consulta de histórico avançada

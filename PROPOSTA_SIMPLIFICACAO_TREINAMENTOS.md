# Proposta: Simplificação da Arquitetura de Treinamentos

## 📋 Problema Identificado

A estrutura atual de treinamentos está **complexa e confusa**, misturando:
- Treinamentos planejados
- Treinamentos realizados
- Matrizes de habilidades
- Listas de presença
- Registros de treinamento

**Resultado**: Difícil de usar, manter e entender.

---

## ✨ Proposta: Arquitetura Simplificada

### 🎯 Conceito Central

**Separar completamente os fluxos de PLANEJADO e REALIZADO**, com comunicação manual e clara entre eles.

---

## 🏗️ Nova Arquitetura

### 1️⃣ **TREINAMENTOS PLANEJADOS** (Demanda/Necessidade)

**Propósito**: Registrar o que cada colaborador PRECISA fazer

**Modelo**: `DemandaTreinamento`

```python
class DemandaTreinamento(models.Model):
    """O que o colaborador precisa fazer"""
    colaborador = ForeignKey(Colaborador)
    procedimento = ForeignKey(Procedimento)
    
    # Status
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('AGENDADO', 'Agendado'),
        ('CONCLUIDO', 'Concluído'),
        ('DISPENSADO', 'Dispensado'),
    ]
    status = CharField(choices=STATUS_CHOICES, default='PENDENTE')
    
    # Informações de planejamento
    prioridade = CharField(choices=['ALTA', 'MEDIA', 'BAIXA'])
    prazo_limite = DateField(null=True)
    motivo = TextField()  # Por que precisa fazer
    criado_por = ForeignKey(User)
    criado_em = DateTimeField(auto_now_add=True)
    
    # Vinculação com realização (quando ocorrer)
    realizacao = ForeignKey('RealizacaoTreinamento', null=True, blank=True)
    data_conclusao = DateTimeField(null=True)
```

**Características**:
- ✅ Criado automaticamente ao associar colaborador a perfil
- ✅ Criado manualmente por gestor/RH
- ✅ Sempre vinculado a um procedimento específico
- ✅ Tem prazo e prioridade
- ✅ Pode ser dispensado (com justificativa)

---

### 2️⃣ **TREINAMENTOS REALIZADOS** (Execução/Histórico)

**Propósito**: Registrar o que REALMENTE aconteceu

**Modelo**: `RealizacaoTreinamento`

```python
class RealizacaoTreinamento(models.Model):
    """O que realmente aconteceu"""
    # Quem participou (flexível)
    colaborador = ForeignKey(Colaborador, null=True, blank=True)
    participante_externo = ForeignKey(ParticipanteExterno, null=True, blank=True)
    
    # O que foi feito
    TIPO_CHOICES = [
        ('PROCEDIMENTO', 'Treinamento em Procedimento'),
        ('CURSO', 'Curso/Capacitação Externa'),
        ('PALESTRA', 'Palestra/Workshop'),
        ('REUNIAO', 'Reunião Técnica'),
        ('ALINHAMENTO', 'Alinhamento Interno'),
    ]
    tipo = CharField(choices=TIPO_CHOICES)
    
    # Conteúdo (flexível)
    procedimento = ForeignKey(Procedimento, null=True, blank=True)
    titulo = CharField(max_length=200)
    descricao = TextField(null=True)
    
    # Execução
    data_realizacao = DateField()
    carga_horaria = DecimalField()
    instrutor = CharField(max_length=200)
    local = CharField(max_length=200, null=True)
    
    # Evidências
    lista_presenca = ForeignKey(ListaPresenca, null=True)
    certificado = FileField(null=True)
    
    # Avaliação (se necessário)
    necessita_avaliacao_eficacia = BooleanField(default=False)
    data_limite_avaliacao = DateField(null=True)
    avaliacao_eficacia_realizada = BooleanField(default=False)
    resultado_avaliacao = TextField(null=True)
    
    # Controle
    registrado_por = ForeignKey(User)
    registrado_em = DateTimeField(auto_now_add=True)
```

**Características**:
- ✅ Registra QUALQUER tipo de treinamento/evento
- ✅ Interno OU externo
- ✅ Com OU sem procedimento
- ✅ Flexível para cenários reais
- ✅ Não depende de ter sido planejado
- ✅ Pode ser vinculado a demanda depois

---

### 3️⃣ **LISTAS DE PRESENÇA** (Agrupamento)

**Propósito**: Agrupar várias realizações da mesma sessão

**Modelo**: `SessaoTreinamento` (renomear ListaPresenca)

```python
class SessaoTreinamento(models.Model):
    """Uma sessão de treinamento que aconteceu"""
    codigo = CharField(unique=True)  # ST2025-0001
    titulo = CharField(max_length=200)
    
    # Data e horário
    data = DateField()
    hora_inicio = TimeField(null=True)
    hora_fim = TimeField(null=True)
    carga_horaria = DecimalField(null=True)
    
    # Local e responsável
    local = CharField(max_length=200, null=True)
    instrutor = CharField(max_length=200)
    
    # Observações
    observacoes = TextField(null=True)
    
    # Controle
    criado_por = ForeignKey(User)
    criado_em = DateTimeField(auto_now_add=True)
    
    # Relacionamento reverso: sessao.realizacoes.all()
```

---

## 🔄 Fluxos de Trabalho

### Fluxo 1: Planejamento → Realização

```
1. Colaborador é associado a um perfil
   ↓
2. Sistema cria DemandaTreinamento automaticamente
   ↓
3. Gestor vê lista de pendências
   ↓
4. Agenda treinamento (status = AGENDADO)
   ↓
5. Realiza treinamento e registra RealizacaoTreinamento
   ↓
6. MANUALMENTE vincula realização à demanda
   ↓
7. DemandaTreinamento.status = CONCLUIDO
```

### Fluxo 2: Realização → Planejamento (Retroativo)

```
1. Treinamento acontece (sem planejamento prévio)
   ↓
2. Registra RealizacaoTreinamento
   ↓
3. Sistema sugere demandas pendentes correspondentes
   ↓
4. Usuário ESCOLHE vincular ou não
```

### Fluxo 3: Importação em Massa

```
1. Excel com realizações
   ↓
2. Sistema cria RealizacaoTreinamento para cada linha
   ↓
3. Opcionalmente agrupa em SessaoTreinamento
   ↓
4. DEPOIS usuário pode vincular a demandas pendentes
```

---

## 📊 Telas/Interfaces

### Dashboard Principal

```
┌─────────────────────────────────────────────┐
│         GESTÃO DE TREINAMENTOS              │
├─────────────────────────────────────────────┤
│                                             │
│  [📋 DEMANDAS]    [✅ REALIZAÇÕES]          │
│                                             │
│  Pendentes: 45    Hoje: 3                  │
│  Vencidas: 12     Mês: 87                  │
│  Agendadas: 23    Ano: 1.234               │
│                                             │
│  [Ver Demandas]   [Ver Realizações]        │
│                                             │
└─────────────────────────────────────────────┘
```

### Tela: Demandas Pendentes

**Filtros**: Colaborador, Procedimento, Prioridade, Prazo
**Ações**: 
- Agendar
- Dispensar
- Vincular a realização existente
- Exportar lista

**Colunas**:
- Colaborador
- Procedimento
- Prioridade
- Prazo
- Status
- Ações

### Tela: Realizações

**Filtros**: Data, Tipo, Instrutor, Colaborador
**Ações**:
- Novo registro
- Importar Excel
- Exportar relatório
- Vincular a demandas

**Colunas**:
- Data
- Tipo
- Título/Procedimento
- Participante
- Instrutor
- Vinculado a demanda?

---

## 💡 Vantagens da Nova Arquitetura

### 1. **Simplicidade**
- ✅ Conceitos claros: "o que preciso fazer" vs "o que fiz"
- ✅ Menos modelos
- ✅ Menos campos confusos

### 2. **Flexibilidade**
- ✅ Posso planejar sem realizar
- ✅ Posso realizar sem ter planejado
- ✅ Posso vincular depois

### 3. **Realidade**
- ✅ Nem tudo é planejado
- ✅ Nem tudo planejado é realizado
- ✅ Participantes externos são comuns

### 4. **Rastreabilidade**
- ✅ Histórico completo do que foi feito
- ✅ Evidências anexadas
- ✅ Vinculação clara entre demanda e realização

### 5. **Auditoria**
- ✅ "Quem precisa treinar?" → Demandas pendentes
- ✅ "Quem já treinou?" → Realizações por colaborador
- ✅ "Treinamento X foi feito?" → Realizações por procedimento

---

## 🔧 Migração da Estrutura Atual

### Etapa 1: Criar Novos Modelos
```python
# Criar DemandaTreinamento
# Criar RealizacaoTreinamento
# Renomear ListaPresenca → SessaoTreinamento
```

### Etapa 2: Migrar Dados Existentes

```python
# RegistroTreinamento atual vira:
# - Se tem data_treinamento → RealizacaoTreinamento
# - Se não tem data → DemandaTreinamento (pendente)
```

### Etapa 3: Atualizar Views e Templates

```python
# Separar em dois módulos:
# 1. views_demandas.py → PLANEJAMENTO
# 2. views_realizacoes.py → HISTÓRICO
```

### Etapa 4: Deprecar Modelo Antigo

```python
# Manter RegistroTreinamento por um tempo
# Mostrar aviso de migração
# Remover após confirmação
```

---

## 📝 Modelo de Dados Simplificado

```
PLANEJAMENTO (O que precisa fazer)
┌─────────────────────────────┐
│   DemandaTreinamento        │
├─────────────────────────────┤
│ - colaborador               │
│ - procedimento              │
│ - status (pendente/etc)     │
│ - prazo                     │
│ - prioridade                │
│ - realizacao (FK opcional)  │◄──┐
└─────────────────────────────┘   │
                                  │ Vinculação
REALIZAÇÃO (O que aconteceu)      │ Manual
┌─────────────────────────────┐   │
│   RealizacaoTreinamento     │───┘
├─────────────────────────────┤
│ - colaborador/externo       │
│ - tipo                      │
│ - procedimento (opcional)   │
│ - titulo                    │
│ - data_realizacao           │
│ - instrutor                 │
│ - evidencias                │
│ - sessao (FK opcional)      │───┐
└─────────────────────────────┘   │
                                  │ Agrupamento
SESSÃO (Agrupamento)              │
┌─────────────────────────────┐   │
│   SessaoTreinamento         │◄──┘
├─────────────────────────────┤
│ - codigo (ST2025-0001)      │
│ - titulo                    │
│ - data/hora                 │
│ - local                     │
│ - instrutor                 │
└─────────────────────────────┘
```

---

## 🚀 Próximos Passos

### Fase 1: Planejamento (1-2 dias)
1. ✅ Revisar e aprovar proposta
2. ✅ Definir prioridades de features
3. ✅ Criar backlog detalhado

### Fase 2: Implementação Base (3-5 dias)
1. Criar novos modelos
2. Criar migrations
3. Migrar dados existentes (script)
4. Testes de integridade

### Fase 3: Interfaces (5-7 dias)
1. Dashboard principal
2. CRUD de Demandas
3. CRUD de Realizações
4. Vinculação manual
5. Importação simplificada

### Fase 4: Features Avançadas (5-7 dias)
1. Relatórios
2. Notificações (prazos)
3. Sugestões automáticas de vinculação
4. Aprovações/workflows
5. Indicadores/métricas

### Fase 5: Transição (2-3 dias)
1. Documentação
2. Treinamento usuários
3. Monitoramento
4. Ajustes finais

**Total estimado**: 16-24 dias de desenvolvimento

---

## ❓ Perguntas para Decisão

### 1. Aprovação Geral
**Você concorda com essa separação clara entre PLANEJADO e REALIZADO?**
- [ ] Sim, faz sentido
- [ ] Não, prefiro manter junto
- [ ] Sim, mas com ajustes: _______________

### 2. Prioridade
**O que implementar primeiro?**
- [ ] Realizações (histórico/importação)
- [ ] Demandas (planejamento/pendências)
- [ ] Ambos em paralelo

### 3. Dados Existentes
**O que fazer com dados atuais?**
- [ ] Migrar tudo automaticamente
- [ ] Limpar e começar do zero
- [ ] Manter em paralelo (dual mode)

### 4. Timeline
**Urgência da implementação?**
- [ ] Urgente (começar agora)
- [ ] Normal (nas próximas semanas)
- [ ] Baixa (quando possível)

### 5. Escopo Inicial
**Versão mínima viável (MVP)?**
- [ ] Só CRUD básico
- [ ] CRUD + Importação
- [ ] CRUD + Importação + Vinculação
- [ ] Tudo

---

## 📞 Feedback Necessário

Por favor, responda:

1. **A proposta faz sentido para o seu processo real?**
2. **Algo importante está faltando?**
3. **Alguma parte está muito complexa/simples?**
4. **Prioridades: O que é mais urgente?**

---

**Data**: 28/12/2025  
**Status**: 🟡 Aguardando Aprovação  
**Próximo Passo**: Feedback e Decisão

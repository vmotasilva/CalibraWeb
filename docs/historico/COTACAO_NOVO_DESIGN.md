# Novo Design de Fluxo de Cotações

## Visão Geral do Processo

O fluxo será dividido em **4 etapas** bem definidas, permitindo uma gestão realista de cotações onde múltiplos fornecedores competem pelos mesmos itens e a decisão é feita posteriormente.

---

## 1. ETAPA 1: Abrir Cotação (Necessidades)

**Objetivo**: Definir QUAIS instrumentos precisam de serviço e QUANDO.

### Modelo: `SolicitacaoCotacao` (novo)
```python
class SolicitacaoCotacao(models.Model):
    # Identificação
    numero = CharField(unique=True)  # Auto-gerado: SOL-2025-001
    data_criacao = DateTimeField(auto_now_add=True)
    
    # Dados principais
    responsavel = ForeignKey(User)
    departamento = ForeignKey(Setor)
    
    # Período de atendimento
    data_inicio_vencimento = DateField()  # Ex: hoje
    data_fim_vencimento = DateField()      # Ex: hoje + 30 dias
    # Opção: período_vencimento = IntegerField(choices=[30, 60, 90]) dias
    
    # Status
    STATUS = [('ABERTA', 'Aberta'), ('AGUARDANDO_COTACOES', 'Aguardando'), ('ENCERRADA', 'Encerrada')]
    status = CharField(choices=STATUS)
    
    # Descrição
    descricao = TextField()  # Por que precisa? Contexto?
    prioridade = CharField(choices=[('BAIXA', 'Baixa'), ('MÉDIA', 'Média'), ('ALTA', 'Alta')])
    
    def __str__(self):
        return f"{self.numero} - {self.get_status_display()}"
```

### M2M: `ItemSolicitacaoCotacao` (novo)
```python
class ItemSolicitacaoCotacao(models.Model):
    solicitacao = ForeignKey(SolicitacaoCotacao, CASCADE)
    instrumento = ForeignKey(Instrumento)
    necessidade = CharField(max_length=500)  # Ex: "Calibração de precisão"
    quantidade = IntegerField(default=1)
    notas = TextField(blank=True)
    
    class Meta:
        unique_together = ('solicitacao', 'instrumento')
```

### Interface (Step 1)
- Modal com filtros de vencimento: "Próximos 30/60/90 dias"
- Seleção de instrumentos vencendo nesse período
- Para cada instrumento: campo de "necessidade" (descrição da demanda)
- Botões: "Criar Solicitação" | "Cancelar"

---

## 2. ETAPA 2: Seleção de Fornecedores e Cotações

**Objetivo**: Fornecedores ofertam o que conseguem fazer, com valores e especificações.

### Modelo: `CotacaoFornecedor` (novo - renomeia Cotacao atual)
```python
class CotacaoFornecedor(models.Model):
    # Ligação com a necessidade
    solicitacao = ForeignKey(SolicitacaoCotacao)
    fornecedor = ForeignKey(Fornecedor)
    
    # Identificação
    numero = CharField(unique=True)  # Auto-gerado: COT-2025-001-FOR001
    data_criacao = DateTimeField(auto_now_add=True)
    data_envio_para_fornecedor = DateTimeField(null=True, blank=True)
    data_proposta_recebida = DateTimeField(null=True, blank=True)
    
    # Status
    STATUS = [
        ('RASCUNHO', 'Rascunho'),
        ('ENVIADA', 'Enviada para Fornecedor'),
        ('RESPONDIDA', 'Proposta Respondida'),
        ('ACEITA', 'Aceita'),
        ('REJEITADA', 'Rejeitada'),
        ('CANCELADA', 'Cancelada'),
    ]
    status = CharField(choices=STATUS, default='RASCUNHO')
    
    # Observações gerais
    observacoes = TextField(blank=True)
    
    # Rastreamento
    criado_por = ForeignKey(User)
    atualizado_em = DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.numero} - {self.fornecedor.empresa}"
```

### M2M: `ItemCotacao` (novo - detalha cada instrumento/serviço)
```python
class ItemCotacao(models.Model):
    cotacao_fornecedor = ForeignKey(CotacaoFornecedor, CASCADE)
    item_solicitacao = ForeignKey(ItemSolicitacaoCotacao)
    # OU simplesmente:
    instrumento = ForeignKey(Instrumento)
    
    # O fornecedor vai atender?
    pode_atender = BooleanField(default=False)  # 2.2: Marcar quais instrumentos
    
    # Tipo de serviço (2.4)
    TIPO_SERVICO = [
        ('CALIBRACAO', 'Calibração de Instrumento Existente'),
        ('AQUISICAO', 'Aquisição de Instrumento Novo'),
    ]
    tipo_servico = CharField(choices=TIPO_SERVICO)
    
    # Valores (2.3)
    valor_unitario = DecimalField(max_digits=10, decimal_places=2)
    quantidade = IntegerField(default=1)
    valor_total = DecimalField(max_digits=10, decimal_places=2)  # Auto-calc
    
    # Observações específicas
    descricao_servico = TextField(blank=True)  # Detalhe do que será feito
    prazo_dias = IntegerField(null=True, blank=True)  # Dias para execução
    
    class Meta:
        unique_together = ('cotacao_fornecedor', 'instrumento')
```

### Interface (Step 2)
1. Exibir necessidades da `SolicitacaoCotacao`
2. Adicionar fornecedores via dropdown/search
3. Para cada fornecedor:
   - Tabela com instrumentos da solicitação
   - Checkbox "Pode atender?" para cada linha
   - Campo de tipo: Calibração | Aquisição
   - Campos: Valor, Prazo
   - Descrição/Observações específicas
4. Botões: "Salvar Cotação" | "Enviar Fornecedor" | "Cancelar"

---

## 3. ETAPA 3: Seleção de Cotações para Atender Necessidades

**Objetivo**: Escolher qual(is) cotação(ões) vai(ão) atender qual necessidade.

### Modelo: `AtendimentoSolicitacao` (novo)
```python
class AtendimentoSolicitacao(models.Model):
    solicitacao = ForeignKey(SolicitacaoCotacao)
    item_solicitacao = ForeignKey(ItemSolicitacaoCotacao)
    item_cotacao = ForeignKey(ItemCotacao)  # A cotação escolhida
    
    # Rastreamento
    data_escolha = DateTimeField(auto_now_add=True)
    responsavel = ForeignKey(User)
    
    # Planejamento (3.1)
    data_prevista_atendimento = DateField()  # Quando será feito?
    observacoes = TextField(blank=True)
    
    # Status
    STATUS = [
        ('PENDENTE', 'Pendente'),
        ('CONFIRMADA', 'Confirmada'),
        ('EXECUTANDO', 'Executando'),
        ('CONCLUIDA', 'Concluída'),
    ]
    status = CharField(choices=STATUS, default='PENDENTE')
    
    class Meta:
        # Um instrumento pode ter múltiplas cotações escolhidas
        # (ex: 2 fornecedores diferentes para diferentes serviços)
        unique_together = ('item_solicitacao', 'item_cotacao')
```

### Interface (Step 3)
1. Tabela com necessidades (ItemSolicitacaoCotacao)
2. Para cada necessidade:
   - Dropdown com cotações disponíveis (ItemCotacao.pode_atender=True)
   - Campo: Data prevista de atendimento
   - Botão: "Atribuir Cotação"
3. Visualizar atribuições feitas
4. Permitir múltiplas cotações para mesma necessidade (ex: 2 fornecedores para 2 instrumentos iguais)

---

## 4. ETAPA 4: Automatizações

**Objetivo**: Após confirmar atendimento, iniciar fluxos automáticos.

### Fluxo por Tipo de Serviço

#### A. Se `tipo_servico = 'AQUISICAO'`:
- **Ação**: Criar procedimento de **Substituição** do instrumento
- **Passo 1**: Desativar instrumento antigo (ou marcar com flag 'substituído')
- **Passo 2**: Marcar instrumento referência para substituição futura
- **Passo 3**: Registrar data prevista de recebimento
- **Status**: Aguardando recebimento da aquisição

#### B. Se `tipo_servico = 'CALIBRACAO'`:
- **Ação**: Criar **Histórico de Calibração** (RegistroCalibracao) em estado inicial
- **Passo 1**: Criar `RegistroCalibracao` com status = 'AGUARDANDO_ENVIO'
- **Passo 2**: Pré-preencher:
  - Data prevista (do AtendimentoSolicitacao.data_prevista_atendimento)
  - Fornecedor (da CotacaoFornecedor.fornecedor)
  - Instrumento (do ItemCotacao.instrumento)
  - Tipo de calibração (ex: "Calibração Completa")
- **Passo 3**: Deixar abertos os campos:
  - Resultado da calibração (faixas, incertezas)
  - Observações pós-calibração
  - Certificado enviado (sim/não)
  - Próximo vencimento (será calculado automaticamente)

### Modelo de Suporte: `ProcessoAutomatizacao` (novo - opcional rastreamento)
```python
class ProcessoAutomatizacao(models.Model):
    atendimento = ForeignKey(AtendimentoSolicitacao)
    
    TIPO = [('AQUISICAO', 'Aquisição'), ('CALIBRACAO', 'Calibração')]
    tipo_processo = CharField(choices=TIPO)
    
    data_inicio = DateTimeField(auto_now_add=True)
    data_conclusao = DateTimeField(null=True, blank=True)
    
    # Referência ao objeto criado
    id_objeto_criado = IntegerField(null=True, blank=True)  # ID do RegistroCalibracao ou similar
    nome_modelo_objeto = CharField(max_length=100)  # 'RegistroCalibracao' ou similar
    
    STATUS = [('ATIVA', 'Ativa'), ('CONCLUIDA', 'Concluída'), ('ERRO', 'Erro')]
    status = CharField(choices=STATUS)
    
    observacoes = TextField(blank=True)
```

---

## Diagrama de Fluxo

```
┌─────────────────────────────────────────────────────────────────────┐
│ ETAPA 1: Abrir Cotação - SolicitacaoCotacao + ItemSolicitacaoCotacao│
│ ├─ Selecionar instrumentos vencendo (30/60/90 dias)               │
│ ├─ Indicar necessidade para cada instrumento                      │
│ └─ Status: ABERTA → AGUARDANDO_COTACOES                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ ETAPA 2: Seleção de Fornecedores - CotacaoFornecedor + ItemCotacao│
│ ├─ Cada fornecedor responde com propostas (ItemCotacao)          │
│ ├─ Marca pode_atender=True/False para cada instrumento           │
│ ├─ Define tipo_servico (Calibração ou Aquisição)                │
│ ├─ Preenche valores e prazos                                     │
│ └─ Status: RASCUNHO → ENVIADA → RESPONDIDA                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│ ETAPA 3: Seleção de Cotações - AtendimentoSolicitacao             │
│ ├─ Para cada necessidade, escolher qual cotação atender           │
│ ├─ Permite múltiplas cotações para mesma necessidade             │
│ ├─ Define data_prevista_atendimento                              │
│ └─ Status: PENDENTE → CONFIRMADA                                 │
└────────────────────────────┬───────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────┐
│ ETAPA 4: Automatizações - ProcessoAutomatizacao                    │
│ ├─ SE tipo_servico = 'AQUISICAO':                                │
│ │  ├─ Desativar instrumento antigo                               │
│ │  └─ Marcar para substituição                                   │
│ ├─ SE tipo_servico = 'CALIBRACAO':                               │
│ │  ├─ Criar RegistroCalibracao (AGUARDANDO_ENVIO)               │
│ │  ├─ Pré-preencher campos básicos                              │
│ │  └─ Deixar abertos resultados da calibração                   │
│ └─ Status: ATIVA → CONCLUIDA                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Mudanças no Modelo Existente

### A. Renomear / Reorganizar
- `Cotacao` → `CotacaoFornecedor` (mais específico)
- Remover campo `fornecedor` direto (passa a ser via `solicitacao` ou direto na nova tabela)

### B. Novos Modelos
- `SolicitacaoCotacao`
- `ItemSolicitacaoCotacao`
- `ItemCotacao`
- `AtendimentoSolicitacao`
- `ProcessoAutomatizacao`

### C. Modelos Relacionados (já existem, só usar)
- `RegistroCalibracao` (para histórico de calibração)
- `Instrumento`
- `Fornecedor`

---

## Benefícios da Arquitetura

✅ **Separação clara de conceitos**: Necessidade → Cotação → Atendimento  
✅ **Múltiplos fornecedores**: Vários fornecedores podem cotar a mesma necessidade  
✅ **Flexibilidade**: Um item pode ter múltiplas cotações escolhidas  
✅ **Rastreabilidade**: Histórico completo de cada decisão  
✅ **Automatização**: Fluxos claros para aquisição vs calibração  
✅ **Conformidade**: Registro de quem decidiu, quando e por quê  

---

## Próximas Etapas (Implementação)

1. **Criar migrations** para os novos modelos
2. **Criar forms** para cada etapa (4 forms diferentes)
3. **Criar views** para navegar o fluxo (possivelmente MultiStepForm)
4. **Criar templates** com interfaces claras para cada etapa
5. **Implementar sinais (signals)** para automatizações (etapa 4)
6. **Testes** de fluxo completo


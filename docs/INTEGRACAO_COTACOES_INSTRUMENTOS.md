# 📊 INTEGRAÇÃO: Cotações → Detalhamento de Instrumentos

## 📋 Mapeamento de Dados

### 1️⃣ **FLUXO: REGISTRO DE CALIBRAÇÃO**

**Quando?** 
- `ItemCotacao.tipo_servico = 'CALIBRACAO'`
- `AtendimentoSolicitacao` está confirmado
- `local_atendimento` = 'NO_LOCAL' ou 'NO_LABORATORIO'

**O que aparece?**
- Informações da cotação (fornecedor, valor, prazo)
- Data prevista de atendimento
- Data realizada (se já completado)
- Tecnician responsável (se NO_LOCAL)
- Botão para criar RegistroCalibracao automaticamente
- Status do processo (Aguardando, Executando, Concluído)

**Dados relacionados:**
```python
# ItemCotacao
- instrumento (FK)
- tipo_servico = 'CALIBRACAO'
- local_atendimento ('NO_LOCAL' ou 'NO_LABORATORIO')
- descricao_servico
- prazo_dias

# AtendimentoSolicitacao (ligado ao ItemCotacao)
- data_prevista_atendimento
- data_realizada (se NO_LOCAL)
- data_envio (se NO_LABORATORIO)
- data_retorno (se NO_LABORATORIO)
- tecnico_responsavel
- status

# ProcessoAutomatizacao (se criado)
- tipo_processo = 'CALIBRACAO'
- status
- id_objeto_criado (ID do RegistroCalibracao)
```

---

### 2️⃣ **FLUXO: RASTREIO (ORDENS)**

**Quando?**
- Qualquer `AtendimentoSolicitacao` com `local_atendimento = 'NO_LABORATORIO'`
- Independente do `tipo_servico`

**O que aparece?**
- Fornecedor responsável
- Data de envio
- Data de retorno prevista
- Data de retorno real (quando voltar)
- Status de rastreio (Aguardando envio, Em trânsito, Recebido, etc.)
- Botões para atualizar status

**Dados relacionados:**
```python
# ItemCotacao
- cotacao_fornecedor (FK → CotacaoFornecedor)
- local_atendimento = 'NO_LABORATORIO'

# CotacaoFornecedor
- fornecedor
- numero

# AtendimentoSolicitacao
- data_envio
- data_retorno_previsto
- data_retorno
- status
- observacoes
```

---

### 3️⃣ **FLUXO: SUBSTITUIÇÃO**

**Quando?**
- `ItemCotacao.tipo_servico = 'AQUISICAO'`
- OU `local_atendimento = 'COMPRAR_NOVO'`

**O que aparece?**
- Informação do novo instrumento (marca, modelo, série)
- Data de chegada prevista
- Data de chegada real
- Status de substituição (Solicitado, Em processo, Recebido, Instalado)
- Vincular com instrumento anterior (referência)
- Botão para processar substituição

**Dados relacionados:**
```python
# ItemCotacao
- tipo_servico = 'AQUISICAO'
- local_atendimento = 'COMPRAR_NOVO'
- descricao_servico (detalhes do novo instrumento)

# AtendimentoSolicitacao
- data_chegada
- status
- observacoes

# ProcessoAutomatizacao
- tipo_processo = 'AQUISICAO'
- id_objeto_criado (pode referenciar novo instrumento ou processo de substituição)
```

---

## 🛠️ IMPLEMENTAÇÃO

### ETAPA 1: Estender View `detalhe_instrumento_view`

**Arquivo:** `qms/views.py`

```python
def detalhe_instrumento_view(request, instrumento_id):
    # ... código existente ...
    
    # NOVO: Buscar cotações relacionadas
    cotacoes_itens = ItemCotacao.objects.filter(
        instrumento=instrumento
    ).select_related(
        'cotacao_fornecedor__fornecedor',
        'item_solicitacao__solicitacao'
    ).prefetch_related(
        'atendimentos'
    ).order_by('-data_criacao')
    
    # Agrupar por tipo de fluxo
    calibracoes = cotacoes_itens.filter(tipo_servico='CALIBRACAO')
    aquisicoes = cotacoes_itens.filter(tipo_servico='AQUISICAO')
    laboratorio = AtendimentoSolicitacao.objects.filter(
        item_solicitacao__instrumento=instrumento,
        item_cotacao__local_atendimento='NO_LABORATORIO'
    ).select_related('item_cotacao__cotacao_fornecedor').order_by('-data_escolha')
    
    # Processos de automatização
    processos = ProcessoAutomatizacao.objects.filter(
        atendimento__item_solicitacao__instrumento=instrumento
    ).order_by('-data_inicio')
    
    context = {
        'instrumento': instrumento,
        # ... dados existentes ...
        'cotacoes_calibracao': calibracoes,
        'cotacoes_aquisicao': aquisicoes,
        'rastreios_laboratorio': laboratorio,
        'processos_automatizacao': processos,
    }
```

---

### ETAPA 2: Criar Template com 3 Abas

**Arquivo:** `metrologia/templates/metrologia/instrumento_detalhe.html`

**Nova estrutura de tabs:**

```html
<!-- Abas existentes -->
<li class="nav-item">
    <button class="nav-link" id="cotacoes-tab" ...>
        📋 Cotações
    </button>
</li>

<!-- Conteúdo das Cotações -->
<div class="tab-pane fade" id="cotacoes">
    <!-- TAB 1: REGISTRO DE CALIBRAÇÃO -->
    <div class="accordion" id="accordionCotacoes">
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button" data-bs-toggle="collapse" 
                        data-bs-target="#calibracaoPanel">
                    <i class="bi bi-clipboard-check"></i> Registros de Calibração
                </button>
            </h2>
            <div id="calibracaoPanel" class="accordion-collapse collapse show">
                <div class="accordion-body">
                    <!-- Tabela de calibrações -->
                    {% for cotacao in cotacoes_calibracao %}
                        {% for atendimento in cotacao.atendimentos.all %}
                            <!-- Card por atendimento -->
                        {% endfor %}
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <!-- TAB 2: RASTREIO -->
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button" data-bs-toggle="collapse" 
                        data-bs-target="#rastreioPanel">
                    <i class="bi bi-geo-alt"></i> Rastreio em Laboratório
                </button>
            </h2>
            <div id="rastreioPanel" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <!-- Timeline de rastreio -->
                </div>
            </div>
        </div>
        
        <!-- TAB 3: SUBSTITUIÇÃO -->
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button" data-bs-toggle="collapse" 
                        data-bs-target="#substituicaoPanel">
                    <i class="bi bi-arrow-repeat"></i> Substituições/Aquisições
                </button>
            </h2>
            <div id="substituicaoPanel" class="accordion-collapse collapse">
                <div class="accordion-body">
                    <!-- Histórico de substituições -->
                </div>
            </div>
        </div>
    </div>
</div>
```

---

### ETAPA 3: Componentes por Fluxo

#### A) REGISTRO DE CALIBRAÇÃO

**Card estrutura:**
```
┌─────────────────────────────────────────┐
│ Calibração - TH-15                      │
├─────────────────────────────────────────┤
│ Fornecedor: Tecnolab                    │
│ Data Prevista: 20/12/2025               │
│ Data Realizada: 16/12/2025 ✅          │
│ Técnico: João Silva                     │
│ Prazo: 2 dias                           │
│ Status: CONCLUÍDA                       │
├─────────────────────────────────────────┤
│ [Ver Certificado] [Editar] [Remover]   │
└─────────────────────────────────────────┘
```

---

#### B) RASTREIO (LABORATÓRIO)

**Timeline estrutura:**
```
DATA ENVIO              DATA RETORNO PREVISTO      DATA RETORNO REAL
   ↓                           ↓                           ↓
┌──────────┐          ┌──────────────────┐       ┌──────────────────┐
│ 10/12    │ ────→    │ 20/12 (previsto) │ ────→ │ 19/12 (recebido) │
│ Enviado  │          │ Em Laboratório   │       │ Retornou         │
└──────────┘          └──────────────────┘       └──────────────────┘
  Fornecedor: Tecnolab
  Instrumento: TH-15
  Status: CONCLUÍDO
```

---

#### C) SUBSTITUIÇÃO/AQUISIÇÃO

**Status timeline:**
```
SOLICITADO → EM PROCESSO → CHEGADA PREVISTA → CHEGADA REAL → INSTALADO

Data Prevista: 25/12/2025
Data Chegada: 22/12/2025 ✅
Novo Instrumento: Marca XYZ, Modelo ABC, Série 12345
Referência: LE-02 (vinculado)
Status: Aguardando Instalação
```

---

## 🔄 FLUXO DE ATUALIZAÇÃO

### Para Calibração (NO_LOCAL)
1. Usuario acessa detalhamento do instrumento
2. Clica "Atualizar Data de Calibração"
3. Formulário inline aparece
4. Atualiza `data_realizada` no `AtendimentoSolicitacao`
5. Sistema chama `atualizar_status_automatico()`
6. Se todas as datas estão preenchidas, status vai para REALIZADO

### Para Rastreio (NO_LABORATORIO)
1. Usuario marca "Enviado" (preenche `data_envio`)
2. Usuario marca "Recebido" (preenche `data_retorno`)
3. Sistema atualiza `AtendimentoSolicitacao.status`
4. Timeline atualiza em tempo real

### Para Substituição (AQUISICAO/COMPRAR_NOVO)
1. Usuario marca "Recebido" (preenche `data_chegada`)
2. Botão "Processar Substituição" ativa
3. Cria/atualiza `ProcessoAutomatizacao`
4. Vincula novo instrumento à referência anterior
5. Marca instrumento antigo como inativo

---

## 📊 RESUMO DE MUDANÇAS

| Componente | Mudança |
|-----------|---------|
| **View** | Adicionar 3 queries ao context (`cotacoes_calibracao`, `rastreios_laboratorio`, `processos`) |
| **Template** | Adicionar aba "Cotações" com accordion de 3 fluxos |
| **JS** | Formulários inline para atualizar datas |
| **API** | Endpoints POST para atualizar `AtendimentoSolicitacao` |
| **Status** | Sincronizar automaticamente com `atualizar_status_automatico()` |

---

## 🎯 SEQUÊNCIA DE IMPLEMENTAÇÃO

1. ✅ Estender `detalhe_instrumento_view` com queries
2. ✅ Criar aba "Cotações" no template
3. ✅ Implementar card de Calibração com botões
4. ✅ Implementar timeline de Rastreio
5. ✅ Implementar histórico de Substituição
6. ✅ Criar endpoints API para atualizar dados
7. ✅ Testar fluxos completos


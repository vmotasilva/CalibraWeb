# Análise A3.xlsx e Revisão Gerencial.xlsx

## 1. A3.xlsx - Estrutura Completa

### Dimensões
- Arquivo: A3.xlsx
- Sheet: "A3"
- Range: A1:O51 (15 colunas, 51 linhas)

### Seções Identificadas

#### A. IDENTIFICAÇÃO (Linhas 2-6)
- **[B2]** - Título: "A3"
- **[B4:C4]** - A3 Nº: Data-based identifier (ex: 2026-01-01)
- **[D4:E4]** - Laboratório: Identificação do laboratório (ex: LabRio)
- **[B5:C5]** - Data: Data de criação (ex: 2026-01-13)
- **[D5:E5]** - Líder do Projeto: Nome do líder
- **[B6:C6]** - Participantes: Lista de participantes separados por /

#### B. PROBLEMA (Linhas 2-11)
- **[C2:D2]** - Problema: Descrição do problema (ex: "Ponto de HC")
- **[B7:C8]** - HISTÓRICO/IMPORTÂNCIA: Contexto do problema
- **[F10:F11]** - Observações Importantes: Notas adicionais

#### C. FERRAMENTAS DE QUALIDADE (Linhas 5-7)
- **[F5]** - Header: "Ferramentas de Qualidade utilizadas:"
- **[H5:N7]** - Checkboxes para ferramentas:
  - Fluxograma (H5)
  - Brainstorming (H6)
  - Diagrama de Ishikawa (H7)
  - 5 Porquês (L5)
  - Gráfico de Pareto (L6)
  - Check List (L7)
  - Gráfico Geral (N5)
  - Carta de Tendência (N6)
  - Antes x Depois (N7)

#### D. FASES PDCA (Linhas 18-51)

**D.1 - A.ANALISAR (Linhas 4-7)**
- **[F4]** - Header: "A.ANALISAR (Utilize pelo menos 01 Ferramenta da Qualidade)"
- Informações de problem statement e contexto

**D.2 - D.DEFINIR (Linhas 18-27)**
- **[B18:B19]** - Header: "D. DEFINIR"
- **[B19]** - Objetivo: Descrição dos objetivos do A3

**D.3 - I.IMPLEMENTAR (Linhas 18-39)**
- **[F18]** - Header: "I. IMPLEMENTAR (Plano de Ação)"
- **[F20:F23]** - Formulas de tracking:
  - Ações Planejadas (COUNTIF G28:G37 = "Planeada/Planejada")
  - Ações Completas (COUNTIFS G28:G37 = "Completa/Concluído")
  - Ações em Andamento (COUNTIFS G28:G37 = "En Curso/Andamento")
  - Ações Prioridade em Andamento (COUNTIFS G28:G37 = "En Curso/Andamento")
- **[F25:M27]** - Headers da tabela de ações:
  - F25: "AÇÃO | ACCIÓN"
  - F27: "Descrição | Descripción"
  - G27: "Status"
  - H27: "Prioridad"
  - I27: "Quem|Quién?"
  - J27: "Quando| Cuando" (1º Deadline)
  - K27: "Quando| Cuando" (Deadline)
  - L25: "COMENTÁRIOS"
  - M25: "Ação Eficaz | Acci n Eficaz?" (Sim/Não/Parcialmente)
- **[F28:F38]** - Dados de ações (até 10-15 ações)
  - Cada ação tem: Descrição, Status, Prioridade, Responsável, Deadlines, Comentários, Eficácia

**D.4 - M.MEDIR (Linhas 29-30)**
- **[B29]** - Header: "M. MEDIR (Estado Atual / "Anterior")"
- Dados de medições e estado atual

**D.5 - C.CONTROLE (Linhas 41-51)**
- **[F41]** - Header: "C. CONTROLE (Resutados)"
- Seção de controle e resultados

### Campos Mapeados para Django

**Tipo: CharField/TextField**
- a3_numero (baseado em data)
- laboratorio
- lider_projeto
- participantes (TextField para lista)
- problema
- historico_importancia (TextField)
- observacoes_importantes (TextField)
- objetivo (TextField)

**Tipo: BooleanField (Ferramentas de Qualidade)**
- ferramenta_fluxograma
- ferramenta_brainstorming
- ferramenta_ishikawa
- ferramenta_5_porques
- ferramenta_grafico_pareto
- ferramenta_checklist
- ferramenta_grafico_geral
- ferramenta_carta_tendencia
- ferramenta_antes_depois

**Tipo: DateField**
- data_criacao

**Tipo: IntegerField (Computed/Read-only)**
- total_acoes_planejadas (COUNTIF)
- total_acoes_completas (COUNTIFS)
- total_acoes_andamento (COUNTIFS)
- total_acoes_prioridade_andamento (COUNTIFS)

**Tipo: ForeignKey**
- acoes_relacionadas (many-to-many para PlanoAcao)

---

## 2. Revisão Gerencial.xlsx - Estrutura Especial

### Dimensões
- Arquivo: Revisão Gerencial.xlsx
- Sheets: 2 abas
  1. "Relatório de Revisão Gerencial" (A1:F27)
  2. "Plano de ação" (A1:O108)

### Estrutura COMPLETA

#### ABA 1: Relatório de Revisão Gerencial (Metadados)

**Seção 1 - Identificação (Linhas 2-7)**
- **[C2]** - Título: "RELATÓRIO DE REVISÃO GERENCIAL - Análise Crítica"
- **[B4:C4]** - Laboratório: Nome do laboratório (ex: "Tecnolens Laboratório Óptico Ltda")
- **[D4:E4]** - Período: Período da revisão (ex: "Agosto/2024 – Julho/2025")
- **[B5:C5]** - Nº Registro: Código da revisão (ex: "RG-TEC-001/2025")
- **[D5:E5]** - Data da reunião: Data de realização (ex: 2025-08-01)
- **[B6:C6]** - Representante da Direção: Nome (ex: "Jousival Vilela")
- **[D6:E6]** - Responsável pela Unidade: Nome (ex: "Fernando Ribeiro")
- **[B7:C7]** - Participantes: Lista de nomes (multiline)

**Seção 2 - Entradas e Saídas (Linhas 9-10)**
- **[B9]** - "Entradas:"
- **[D9]** - "Saídas:"
- **[B10:C10]** - Lista de entradas (ex: "1. Ações de acompanhamento; 2. Resultados de auditorias...")
- **[D10:E10]** - Lista de saídas (ex: "1. Melhoria da eficácia do SGQ...")

**Seção 3 - Análises Críticas (Linhas 12-27)**
- **[B12:D12]** - Headers: "Item | Descrição do Assunto | Análise da Diretoria"
- **[B13:D27]** - Itens de análise crítica com:
  - Número do item
  - Descrição do assunto
  - Análise e decisão da diretoria

#### ABA 2: Plano de ação (Integração com A3/RNC)

**Estrutura**: Idêntica ao Plano de Ação.xlsx mas com links para RG

**Headers (Linhas 2-8)**
- **[D2]** - "PLANO DE AÇÃO | PLAN DE ACCIÓN"
- **[B3:D3]** - Laboratório: Com referência para Relatório (ex: ='Relatório de Revisão Gerencial'!C4)
- **[G3]** - Formula: "AÇÕES PLANEJADAS (ACCIONES PLANEADAS): "&COUNTIF(I9:I108,"Planeada/Planejada")
- **[B5:D5]** - Nº Registro: Com referência (ex: ='Relatório de Revisão Gerencial'!C5)
- **[G3-G6]** - Formulas para tracking de ações:
  - AÇÕES PLANEJADAS
  - AÇÕES COMPLETAS
  - AÇÕES EM ANDAMENTO
  - AÇÕES PRIORIDADE EM ANDAMENTO

**Tabela de Ações (Linhas 8-108)**
- **[B8:N8]** - Headers:
  - B: "Nº Ação | Acción"
  - C: "Input"
  - D: "Problema"
  - E: "Lab"
  - F: "KPI"
  - G: "Descrição | Descripción"
  - H: "Classificação | Clasificación"
  - I: "Status"
  - J: "Prioridad"
  - K: "Quem|Quién Responsavel"
  - L: "Quando 1º Deadline"
  - M: "Quando Deadline"
  - N: "COMENTARIOS"

- **[B9:N108]** - 100+ ações com dados reais

### Campos Mapeados para Django

**MODELO: RevisaoGerencial (Nova estrutura)**

#### Identificação
- numero_rg (ex: "RG-TEC-001/2025")
- data_realizacao
- laboratorio
- periodo_inicio
- periodo_fim
- representante_direcao
- responsavel_unidade
- participantes (TextField)

#### Entradas/Saídas
- entradas_descricao (TextField)
- saidas_descricao (TextField)

#### Análises Críticas
- Esta será uma tabela separada (M2M)
  - numero_item
  - descricao_assunto
  - analise_diretoria

#### Plano de Ação Relacionado (ForeignKey)
- plano_acao (aponta para PlanoAcao)

#### Métricas
- total_acoes_planejadas (Computed)
- total_acoes_completas (Computed)
- total_acoes_andamento (Computed)
- total_acoes_prioridade_andamento (Computed)

---

## 3. Conclusão

### A3.xlsx
- Modelo **SolucaoA3** necessita ~20-25 novos campos
- Implementa metodologia PDCA com 4 fases
- Integra seleção de ferramentas de qualidade
- Vincula com PlanoAcao para execução
- Requer tabela de ações (até 15 linhas)

### Revisão Gerencial.xlsx
- Modelo **RevisaoGerencial** necessita ~15-20 novos campos
- Não é um tipo de solução independente
- É um metadocumento que:
  1. Registra reunião de revisão gerencial (RG)
  2. Contém análises críticas
  3. Vincula com PlanoAcao existente
  4. Poderia ser um modelo separado com ForeignKey para PlanoAcao

**Recomendação**: Criar RevisaoGerencial como modelo separado com:
- Dados de identificação da reunião
- Tabela de análises críticas (M2M)
- ForeignKey para PlanoAcao (múltiplas ações podem estar em 1 RG)


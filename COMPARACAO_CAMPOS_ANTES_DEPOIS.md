# Comparação: Campos Antigos vs Novos (Alinhados com Excel)

## 1. PLANO DE AÇÃO

### ANTES (campos legados)
```python
- solucao (ForeignKey)
- acao_proposta (TextField)
- responsavel_acao (ForeignKey)
- data_inicio (DateField)
- data_conclusao (DateField)
- status (CharField: planejado/em_execucao/concluido/cancelado)
- resultado (TextField)
```

### DEPOIS (alinhado com Excel Plano de Ação.xlsx)
```python
# Informações do Plano
- solucao (OneToOneField - MANTIDO)
- laboratorio_area_projeto (CharField)
- numero_registro (CharField, unique)

# Campos da tabela de ações (Row 8 do Excel)
- numero_acao (IntegerField)
- input_origem (CharField)
- problema (TextField)
- laboratorio (CharField)
- kpi (CharField)
- descricao (TextField) ← renomeado de acao_proposta
- classificacao (CharField: corretiva/preventiva/melhoria)
- status (CharField - NOVO SISTEMA: planejada/em_curso/completa/retardo/cancelada)
- prioridade (BooleanField - Y/N)
- responsavel_acao (ForeignKey - MANTIDO)
- data_primeira_deadline (DateField) ← 1º Deadline
- data_deadline (DateField) ← Deadline Final
- comentarios (TextField)
- acao_eficaz (CharField: eficaz/nao_eficaz)

# Resultado e Rastreamento
- resultado (TextField - MANTIDO)
- data_conclusao (DateField - REFATORADO)
- criado_em (DateTimeField, auto_now_add)
- atualizado_em (DateTimeField, auto_now)

# Método
+ percentual_conclusao() - Calcula progresso baseado no status
```

**Mapear do Excel → Django:**
| Excel | Django | Tipo |
|-------|--------|------|
| Nº Ação | numero_acao | Integer |
| Input | input_origem | CharField |
| Problema | problema | TextField |
| Lab | laboratorio | CharField |
| KPI | kpi | CharField |
| Descrição | descricao | TextField |
| Classificação | classificacao | Choice |
| Status | status | Choice (4 opções) |
| Prioridad | prioridade | Boolean |
| Quem/Responsavel | responsavel_acao | ForeignKey |
| 1º Deadline | data_primeira_deadline | DateField |
| Deadline | data_deadline | DateField |
| Comentarios | comentarios | TextField |
| Ação Eficaz | acao_eficaz | Choice |

---

## 2. RNC - REGISTRO DE NÃO CONFORMIDADE

### ANTES (campos legados)
```python
- solucao (OneToOneField)
- nc_descricao (TextField)
- nc_tipo (CharField: maior/menor)
- analise_causas (TextField)
- causa_raiz (TextField)
- acao_imediata (TextField)
- acao_corretiva (TextField)
- acao_preventiva (TextField, null)
- plano_verificacao (TextField)
- resultado (TextField, null)
```

### DEPOIS (alinhado com Excel RNC.xlsx - 14 colunas)
```python
# Identificação
- solucao (OneToOneField - MANTIDO)
- numero_rnc (CharField, unique)
- unidade (CharField)
- data_abertura (DateTimeField)

# Classificação
- origem (CharField: insumo/produto/indicador/auditoria/equipamento/processo/fornecedor/testes/outros)
- classificacao (CharField: critica/maior/menor/oportunidade_melhoria) ← expandido de nc_tipo
- requerimento_requisito (TextField)

# Descrição
- descricao_nc (TextField) ← renomeado de nc_descricao
- evidencia_nc (TextField)

# Gerenciamento de Risco
- frequencia (CharField: rara/ocasional/frequente)
- risco (CharField: baixo/medio/alto)

# Tratativas
- causa_raiz (TextField - MANTIDO)
- acao_contencao (TextField)
- acao_nc (CharField: aprovar_concessao/rejeitar/corrigir)
- gerar_plano_acao (BooleanField)
- plano_acao_relacionado (ForeignKey → PlanoAcao)

# Ações
- acao_imediata (TextField - MANTIDO)
- acao_corretiva (TextField - MANTIDO)
- acao_preventiva (TextField - MANTIDO)

# Análise
- analise_causas (TextField - MANTIDO)
- plano_verificacao (TextField - MANTIDO)
- resultado (TextField - MANTIDO)

# Conclusão
- eficacia (CharField: eficaz/nao_eficaz)
- evidencia_implementacao (TextField)
- responsavel (ForeignKey → Colaborador)
- data_fechamento (DateField)

# Rastreamento
- criado_em (DateTimeField, auto_now_add)
- atualizado_em (DateTimeField, auto_now)
```

**Mapear do Excel → Django:**
| Excel | Django | Tipo |
|-------|--------|------|
| Nº RNC | numero_rnc | CharField |
| Unidade | unidade | CharField |
| Data Abertura | data_abertura | DateTimeField |
| Origem | origem | Choice (9 opções) |
| Classificação | classificacao | Choice (4 opções) |
| Requerimento | requerimento_requisito | TextField |
| Descrição NC | descricao_nc | TextField |
| Evidência NC | evidencia_nc | TextField |
| Frequência | frequencia | Choice |
| Risco | risco | Choice |
| Causa Raiz | causa_raiz | TextField |
| Ação Contenção | acao_contencao | TextField |
| Ação NC | acao_nc | Choice |
| Eficácia | eficacia | Choice |
| Evidência Impl | evidencia_implementacao | TextField |
| Responsável | responsavel | ForeignKey |
| Data Fechamento | data_fechamento | DateField |

---

## 3. GESTÃO DE MUDANÇA (FOR.137.R5)

### ANTES (campos legados)
```python
- solucao (OneToOneField)
- mudanca_descricao (TextField)
- motivacao (TextField)
- impacto_processos (TextField)
- impacto_sistemas (TextField, null)
- impacto_pessoas (TextField, null)
- plano_implementacao (TextField)
- data_implementacao (DateField)
- status (CharField: proposta/analise/aprovada/implementada/rejeitada)
- plano_validacao (TextField, null)
- resultado_validacao (TextField, null)
```

### DEPOIS (alinhado com Excel FOR.137.R5 - 9 colunas, 61 linhas)
```python
# INFORMAÇÕES GERAIS
- solucao (OneToOneField - MANTIDO)
- unidade (CharField)
- data_abertura (DateTimeField)
- solicitante (CharField)
- numero_registro (CharField, unique)
- tipo_mudanca (CharField: regulatorio/qms_sgi/projetos)
- prioridade_mudanca (CharField: urgente/alto/medio)
- area_impactada (TextField)
- area_avaliadora (TextField)

# DADOS DA MUDANÇA
- situacao_antes (TextField)
- situacao_depois (TextField)
- justificativa (TextField)
- beneficios (TextField)
- data_mudanca (DateField)
- evidencia (TextField)

# IMPACTOS DE EHS (SEÇÃO COMPLETA - 12 CAMPOS)
# Pilares de EHS
- impacto_pessoas (TextField) ← mantém mas expandido
- referencia_pessoas (CharField: escolhas de impacto)
- impacto_ambiente (TextField)
- referencia_ambiente (CharField: escolhas de impacto)
- impacto_ativos (TextField)
- referencia_ativos (CharField: escolhas de impacto)
- impacto_compliance (TextField)
- referencia_compliance (CharField: escolhas de impacto)

# RISCOS ENVOLVIDOS
- processos_afetados (TextField)
- modulos_sistema_afetados (TextField)
- como_afeta_processo (TextField)
- consequencia_nao_mudanca (TextField)
- riscos_identificados (TextField)
- tratamento_riscos (TextField)
- plano_contingencia (TextField)
- areas_implantacao (TextField)
- observacoes (TextField)

# PLANO DE AÇÃO
- gerar_plano_acao (BooleanField)
- plano_acao_relacionado (ForeignKey → PlanoAcao)
- percentual_conclusao_plano (FloatField)

# ANÁLISE CRÍTICA (MÚLTIPLAS ÁREAS)
- sera_implantada (BooleanField)
- justificativa_area1 (TextField)
- responsavel_decisao_area1 (CharField)
- data_area1 (DateField)
- justificativa_area2 (TextField)
- responsavel_decisao_area2 (CharField)
- data_area2 (DateField)
- solicitante_informado (BooleanField)
- data_informada (DateField)

# STATUS E VALIDAÇÃO
- status (CharField - MANTIDO)
- plano_validacao (TextField - MANTIDO)
- resultado_validacao (TextField - MANTIDO)

# Rastreamento
- criado_em (DateTimeField, auto_now_add)
- atualizado_em (DateTimeField, auto_now)
```

**Mapear do Excel → Django:**
| Seção | Excel | Django | Tipo |
|-------|-------|--------|------|
| Geral | Unidade | unidade | CharField |
| | Data Abertura | data_abertura | DateTimeField |
| | Solicitante | solicitante | CharField |
| | Nº Registro | numero_registro | CharField |
| | Tipo Mudança | tipo_mudanca | Choice |
| | Prioridade | prioridade_mudanca | Choice |
| | Área Impactada | area_impactada | TextField |
| | Área Avaliadora | area_avaliadora | TextField |
| Mudança | Situação Antes | situacao_antes | TextField |
| | Situação Depois | situacao_depois | TextField |
| | Justificativa | justificativa | TextField |
| | Benefícios | beneficios | TextField |
| | Data Mudança | data_mudanca | DateField |
| | Evidência | evidencia | TextField |
| EHS | Pessoas | impacto_pessoas | TextField |
| | Ref Pessoas | referencia_pessoas | Choice |
| | Ambiente | impacto_ambiente | TextField |
| | Ref Ambiente | referencia_ambiente | Choice |
| | Ativos | impacto_ativos | TextField |
| | Ref Ativos | referencia_ativos | Choice |
| | Compliance | impacto_compliance | TextField |
| | Ref Compliance | referencia_compliance | Choice |
| Riscos | Processos | processos_afetados | TextField |
| | Módulos | modulos_sistema_afetados | TextField |
| | Impacto | como_afeta_processo | TextField |
| | Consequência | consequencia_nao_mudanca | TextField |
| | Riscos | riscos_identificados | TextField |
| | Tratamento | tratamento_riscos | TextField |
| | Contingência | plano_contingencia | TextField |
| | Áreas | areas_implantacao | TextField |
| Análise | Implementada | sera_implantada | Boolean |
| | Just Area1 | justificativa_area1 | TextField |
| | Resp Area1 | responsavel_decisao_area1 | CharField |
| | Data Area1 | data_area1 | DateField |
| | Just Area2 | justificativa_area2 | TextField |
| | Resp Area2 | responsavel_decisao_area2 | CharField |
| | Data Area2 | data_area2 | DateField |
| | Solicitante Info | solicitante_informado | Boolean |
| | Data Info | data_informada | DateField |

---

## 4. 8D - OITO DISCIPLINAS

### ANTES (campos legados)
```python
- solucao (OneToOneField)
- d1_time (TextField)
- d2_descricao (TextField)
- d2_especificacoes (TextField)
- d3_contencao (TextField, null)
- d4_causas (TextField, null)
- d4_causa_raiz (TextField, null)
- d5_contramedidas (TextField, null)
- d6_implementacao (TextField, null)
- d7_verificacao (TextField, null)
- d7_resultado (TextField, null)
- d8_padronizacao (TextField, null)
- d8_encerramento (TextField, null)
```

### DEPOIS (alinhado com Excel 8D.xlsx D1)
```python
# D1 - FORMAÇÃO DA EQUIPE
- solucao (OneToOneField - MANTIDO)
- numero_formulario (CharField, unique) ← Ex: RIO-8D-01-2024
- data_abertura (DateTimeField)
- lider_8d (ForeignKey → Colaborador)
- patrocinador (CharField)
- equipe (TextField)
- departamento (CharField)
- problema_identificado (TextField) ← expandido de d1_time
- prazo_projeto (DateField)

# D2 - DESCREVER O PROBLEMA
- d2_descricao (TextField) ← expandido
- d2_especificacoes (TextField) ← expandido

# D3 - CONTER O PROBLEMA
- d3_contencao (TextField)
- d3_responsavel (ForeignKey → Colaborador)
- d3_deadline (DateField)

# D4 - ANÁLISE DE CAUSA RAIZ
- d4_analise_causas (TextField) ← renomeado de d4_causas
- d4_ferramentas_qualidade (CharField) ← NOVO: referência às ferramentas usadas
- d4_causa_raiz (TextField) ← mantido

# D5 - DESENVOLVIMENTO DE CONTRAMEDIDAS
- d5_contramedidas (TextField) ← mantido
- d5_criterios_selecao (TextField) ← NOVO: critérios de seleção

# D6 - IMPLEMENTAÇÃO DE CONTRAMEDIDAS
- d6_implementacao (TextField) ← mantido
- d6_responsavel (ForeignKey → Colaborador) ← NOVO
- d6_deadline (DateField) ← NOVO
- d6_status (CharField) ← NOVO: rastreamento de status

# D7 - VERIFICAÇÃO DE EFETIVIDADE
- d7_verificacao (TextField) ← expandido
- d7_resultado (TextField) ← expandido
- d7_efetivo (BooleanField) ← NOVO: resultado binário

# D8 - PADRONIZAÇÃO E FECHAMENTO
- d8_padronizacao (TextField) ← mantido
- d8_documentos_atualizados (CharField) ← NOVO: ref. a documentos
- d8_treinamento (TextField) ← NOVO: plano de treinamento
- d8_encerramento (TextField) ← mantido

# Análise Geral
- analise_causas (TextField) ← mantido para compatibilidade
- causa_raiz (TextField) ← mantido para compatibilidade

# Rastreamento
- criado_em (DateTimeField, auto_now_add)
- atualizado_em (DateTimeField, auto_now)
```

**Mapear do Excel → Django:**
| D | Excel | Django | Tipo |
|---|-------|--------|------|
| D1 | Nº Formulário | numero_formulario | CharField |
| | Data Abertura | data_abertura | DateTimeField |
| | Líder 8D | lider_8d | ForeignKey |
| | Patrocinador | patrocinador | CharField |
| | Equipe | equipe | TextField |
| | Departamento | departamento | CharField |
| | Problema | problema_identificado | TextField |
| | Prazo | prazo_projeto | DateField |
| D2 | Descrição | d2_descricao | TextField |
| | Especificações | d2_especificacoes | TextField |
| D3 | Contenção | d3_contencao | TextField |
| | Responsável | d3_responsavel | ForeignKey |
| | Deadline | d3_deadline | DateField |
| D4 | Análise | d4_analise_causas | TextField |
| | Ferramentas | d4_ferramentas_qualidade | CharField |
| | Causa Raiz | d4_causa_raiz | TextField |
| D5 | Contramedidas | d5_contramedidas | TextField |
| | Critérios | d5_criterios_selecao | TextField |
| D6 | Implementação | d6_implementacao | TextField |
| | Responsável | d6_responsavel | ForeignKey |
| | Deadline | d6_deadline | DateField |
| | Status | d6_status | CharField |
| D7 | Verificação | d7_verificacao | TextField |
| | Resultado | d7_resultado | TextField |
| | Efetivo | d7_efetivo | Boolean |
| D8 | Padronização | d8_padronizacao | TextField |
| | Documentos | d8_documentos_atualizados | CharField |
| | Treinamento | d8_treinamento | TextField |
| | Encerramento | d8_encerramento | TextField |

---

## Resumo de Mudanças por Modelo

| Modelo | Campos Antes | Campos Depois | Adicionados | Removidos | Renomeados |
|--------|--------------|---------------|-------------|-----------|-----------|
| **PlanoAcao** | 7 | 19 | 14 | 2 | 1 |
| **SolucaoRNC** | 10 | 29 | 23 | 1 | 1 |
| **SolucaoGestaoDeMudanca** | 11 | 51 | 41 | 5 | 0 |
| **Solucao8D** | 13 | 35 | 25 | 2 | 1 |
| **TOTAL** | **41** | **134** | **103** | **10** | **3** |

## Próximas Etapas

1. ✅ Modelos refatorados e migrations aplicadas
2. ⏭️ Criar Django Forms para validação
3. ⏭️ Atualizar templates HTML
4. ⏭️ Implementar lógica de negócio
5. ⏭️ Testes e deploy

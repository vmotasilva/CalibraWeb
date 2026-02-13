# Análise dos Templates Excel vs Implementação Atual

## 1. PLANO DE AÇÃO

### Campos encontrados no Excel (Row 8):
| Coluna | Campo | Tipo |
|--------|-------|------|
| B | Nº Ação / Acción | Número |
| C | Input | Texto |
| D | Problema | Texto |
| E | Lab | Texto |
| F | KPI | Texto |
| G | Descrição / Descripción | Texto |
| H | Classificação / Clasificación | Seleção (lista de opções) |
| I | Status | Seleção: Planeada/Planejada, Completa/Concluído, En Curso/Andamento, Retardo/Atrasada |
| J | Prioridad | Seleção: Y/N (sim/não) |
| K | Quem/Quién Responsavel | Texto/Responsável |
| L | Quando/Cuando 1º Deadline | Data |
| M | Quando/Cuando Deadline | Data |
| N | COMENTARIOS | Texto |
| O | Ação Eficaz / Acción Eficaz? | Seleção: Eficaz/Não eficaz |

### Metadados do formulário:
- **Cabeçalho** (Rows 2-7): Informações do Plano
  - Row 3: Laboratório, Área ou Projeto
  - Row 5: Nº Registro
  - Row 3-6: Fórmulas para contagem de ações por status
  - Row 3: Percentual de Conclusão

### Dados encontrados:
- Bilíngue (Português/Espanhol)
- Formulas de rastreamento de progresso
- Suporte para múltiplas ações (rows 9-110+)

---

## 2. RNC - REGISTRO DE NÃO CONFORMIDADE

### Campos encontrados:
| Campo | Célula | Descrição |
|-------|--------|-----------|
| Unidade | B4:C4 | Campo de texto |
| Nº da RNC | B5:C5 | Identificador único |
| Data da Abertura | F5:G5 | Data |
| Origem | B6:C6 | Múltiplas opções: Insumo, Produto, Indicador, Auditoria, Equipamento de Medição, Processo, Fornecedor, Testes de Qualidade, Outros |
| Classificação | B8:C8 | Opções: Crítico, Maior, Menor, Oportunidade de Melhoria |
| Requerimento/Requisito | B9:C9 | Referência normativa (ex: NBR ISO 13.485/2016 - Req 8.5.2) |
| Descrição da Não Conformidade | B10:C10 | Texto descritivo |
| Evidência da Não Conformidade | B11 | Referência a fotos/prints/links |
| **Gerenciamento de Risco** | | Seção específica |
| Frequência | B13:C13 | Opções: Rara, Ocasional, Frequente |
| Risco | B14:C14 | Opções: Baixo, Médio, Alto |
| **Tratativas** | | Seção específica |
| Causa Raiz | B16:C16 | Análise usando ferramentas de qualidade |
| Ação de Contenção | B17 | Se aplicável |
| Ação sobre Não conformidade | B18:C18 | Opções: Aprovar sob concessão, Rejeitar, Corrigir |
| Gerar plano de ação | B19:C19 | Link para "Plano de Ação" |
| **Conclusão** | | Seção de fechamento |
| Análise Crítica da Eficácia | B22:C22 | Opções: Eficaz, Não eficaz |
| Evidência da Implementação | B23 | Fotos/registros |
| Responsável | B24 | Nome |
| Data do Fechamento | F24 | Data |

---

## 3. GESTÃO DE MUDANÇA (FOR.137.R5)

### Seções encontradas:

#### 1. INFORMAÇÕES GERAIS (Rows 4-10)
| Campo | Célula |
|-------|--------|
| Unidade | B5 |
| Data da abertura | F5 |
| Solicitante | B6 |
| Nº do Registro | F6 |
| Tipo de mudança | B7:C7 | Opções: Regulatório, QMS/SGI, Projetos |
| Prioridade de mudança | B8:C8 | Opções: Urgente, Alto, Médio |
| Área(s) impactada(s) | B9 |
| Área avaliadora | B10 |

#### 2. DADOS DA MUDANÇA (Rows 12-18)
| Campo | Célula |
|-------|--------|
| Situação (Antes da Mudança) | B13 |
| Situação Projetada (Após Mudança) | B14 |
| Justificativa | B15 |
| Benefícios | B16 |
| Data da Mudança / Projeto | B17 |
| Evidência | B18 |

#### 3. IMPACTOS DE EHS (Rows 20-28)
- **Pessoas** (Saúde, segurança química, elétrica, organizacional e ergonomia)
- **Meio Ambiente** (Emissões atmosféricas, produtos químicos, consumo de energia, resíduos)
- **Propriedades e ativos** (Instalações, equipamentos, preparação para emergências, prevenção)
- **Compliance** (Permissões locais ou regulamentos aplicáveis)

Cada seção tem:
- Descrição do pilar
- Referência Necessária (coluna G)
- Somatório (coluna G)
- Percentual (coluna H)

Utiliza FÓRMULAS para cálculo automático baseado em outras abas.

#### 4. RISCOS ENVOLVIDOS (Rows 29-38)
- Quais processos serão afetados
- Quais módulos do sistema serão afetados
- Como a mudança afeta o processo atual
- Consequência de não realizar a mudança
- Riscos identificados
- Tratamento dos riscos
- Plano de contingência
- Áreas envolvidas na implantação
- Observações

#### 5. ANÁLISE CRÍTICA PELAS ÁREAS AVALIADORAS (Rows 41-48)
- Mudança será implantada: Sim/Não
- Justificativa / parecer (área 1)
- Responsável pela decisão (área 1)
- Data (área 1)
- Justificativa / parecer (área 2)
- Responsável pela decisão (área 2)
- Data (área 2)
- Solicitante informado: Sim/Não
- Data informada
- Observações

---

## 4. 8D - D1: FORMAÇÃO DA EQUIPE

### Campos encontrados:
| Campo | Célula | Descrição |
|-------|--------|-----------|
| Número do Formulário | B5:D5 | Ex: RIO-8D-01-2024 |
| Data de abertura | G5:H5 | Data |
| Líder 8D | B6:D6 | Nome do responsável |
| Patrocinador | G6:H6 | Nome do patrocinador |
| Equipe | B7:D7 | Lista de nomes (multiline) |
| Departamento | G7:H7 | Ex: Melhoria Contínua |
| Problema identificado | B8:D8 | Descrição do problema |
| Prazo Projeto 8D | G8:H8 | Data limite |

### Estrutura:
- **Este é apenas D1 (Formação da Equipe)**
- Há indicação de que há outras abas para D2-D8
- Cada D tem seu próprio formulário estruturado

---

## Comparação: Implementação Atual vs Excel

### ✅ Campos que existem na implementação:
- Titulo/Descricao
- Data de criação/abertura
- Status
- Responsável
- Deadline

### ❌ Campos FALTANTES:

#### Plano de Ação:
- Input
- Lab (Laboratório)
- KPI
- Classificação (específica)
- Bilinguismo (PT/ES)
- Número de ação automático
- Fórmulas de progresso

#### RNC:
- Origem (múltiplas opções)
- Classificação (Crítico/Maior/Menor/Oportunidade)
- Requerimento/Requisito normativo
- Evidência da não conformidade
- Frequência (Rara/Ocasional/Frequente)
- Nível de Risco (Baixo/Médio/Alto)
- Ação de Contenção
- Ação sobre não conformidade (Aprovar/Rejeitar/Corrigir)
- Análise de eficácia
- Ligação com Plano de Ação

#### Gestão de Mudança:
- Tipo de mudança (Regulatório/QMS/Projetos)
- Prioridade (Urgente/Alto/Médio)
- Situação antes/depois
- Benefícios
- **IMPACTOS DE EHS** (seção inteira com fórmulas)
  - Pessoas
  - Meio Ambiente
  - Propriedades/Ativos
  - Compliance
- Processos afetados
- Módulos do sistema afetados
- Análise crítica por múltiplas áreas
- Ligação com Plano de Ação

#### 8D:
- Número do formulário
- Líder 8D
- Patrocinador
- Equipe (multiline)
- Departamento
- Prazo do projeto
- Indicação de submódulos (D2-D8)

---

## Próximos Passos

1. **Atualizar modelos** para incluir todos os campos
2. **Implementar relacionamentos** entre RNC/Gestão de Mudança e Plano de Ação
3. **Criar formulários** refatorados com os novos campos
4. **Alinhar templates HTML** com a estrutura dos Excel
5. **Adicionar validações** específicas para cada tipo
6. **Implementar bilinguismo** no Plano de Ação
7. **Criar dashboards** com métricas e fórmulas

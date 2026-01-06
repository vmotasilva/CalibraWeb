# Template de Importação de Treinamentos - Estrutura Completa

## Visão Geral

O template de importação foi atualizado para incluir **28 colunas** com informações detalhadas sobre os treinamentos, colaboradores e avaliações de eficácia.

## Estrutura do Template (28 Colunas)

### 1. Informações do Colaborador (Colunas 1-10)

| Coluna | Nome | Obrigatória | Descrição |
|--------|------|-------------|-----------|
| 1 | `cpf_colaborador` | Não | CPF do colaborador (informativo) |
| 2 | `nome_colaborador` | Não | Nome do colaborador (informativo) |
| 3 | `empresa` | Não | Empresa do colaborador |
| 4 | `genero` | Não | Gênero (M/F) |
| 5 | `matricula` | **SIM** | **Matrícula - vincula o treinamento ao colaborador** |
| 6 | `vinculo_emprego` | Não | Vínculo empregatício (CLT, PJ, etc.) |
| 7 | `cargo` | Não | Cargo do colaborador |
| 8 | `centro_custo` | Não | Centro de custo |
| 9 | `status_ocupacao` | Não | Status (Ativo, Inativo) |
| 10 | `estado_unidade` | Não | Estado da unidade |

### 2. Classificação do Treinamento (Colunas 11-14)

| Coluna | Nome | Obrigatória | Descrição |
|--------|------|-------------|-----------|
| 11 | `categoria_comunicacao` | Não | Forma de comunicação (Presencial, Online, EAD) |
| 12 | `metodologia_treinamento` | Não | Metodologia (Teórico, Prático, Teórico-Prático) |
| 13 | `tipo` | Não | Tipo: PROCEDIMENTO, ALINHAMENTO, REUNIAO, CAPACITACAO, OUTRO |
| 14 | `area_conhecimento` | Não | **Área de conhecimento - será preenchida automaticamente pelo procedimento** |

### 3. Conteúdo do Treinamento (Colunas 15-18)

| Coluna | Nome | Obrigatória | Descrição |
|--------|------|-------------|-----------|
| 15 | `titulo_treinamento` | Condicional* | Título do treinamento/reunião |
| 16 | `nome_procedimento` | Não | Nome do procedimento (informativo) |
| 17 | `codigo_documento` | Condicional** | **Código do procedimento (ex: PO-001)** |
| 18 | `numero_revisao` | Não | Número da revisão do procedimento |

\* Obrigatório quando não houver `codigo_documento`  
\*\* Obrigatório quando `tipo` = 'PROCEDIMENTO'

### 4. Datas e Execução (Colunas 19-25)

| Coluna | Nome | Obrigatória | Descrição |
|--------|------|-------------|-----------|
| 19 | `data_inicio_treinamento` | **SIM** | Data de início (formato: AAAA-MM-DD) |
| 20 | `data_final_treinamento` | Não | Data final do treinamento |
| 21 | `mes` | Não | Mês de referência (Janeiro, Fevereiro, etc.) |
| 22 | `facilitador_fornecedor` | Não | **Nome do responsável pela aplicação do treinamento** |
| 23 | `carga_horaria` | Não | Carga horária no formato hh:mm (ex: 04:00) |
| 24 | `custo_treinamento` | Não | Custo em R$ por pessoa (ex: 500.00) |
| 25 | `carga_horaria_horas` | Não | Carga horária em horas decimais (ex: 4) |

### 5. Avaliação de Eficácia (Colunas 26-28)

| Coluna | Nome | Obrigatória | Descrição |
|--------|------|-------------|-----------|
| 26 | `necessita_avaliacao_eficacia` | Não | SIM ou NAO |
| 27 | `data_limite_avaliacao_eficacia` | Não | Data limite para avaliação (AAAA-MM-DD) |
| 28 | `observacao` | Não | Observações adicionais |

## Regras de Validação

### Campos Obrigatórios

1. **matricula** - Sempre obrigatória para vincular ao colaborador
2. **data_inicio_treinamento** - Data de início é sempre obrigatória

### Campos Condicionais

1. **codigo_documento**:
   - Obrigatório se `tipo` = 'PROCEDIMENTO'
   - Opcional para outros tipos (ALINHAMENTO, REUNIAO, etc.)

2. **titulo_treinamento**:
   - Obrigatório quando não há `codigo_documento`
   - Usado para treinamentos sem procedimento vinculado

### Tipos de Treinamento Válidos

- `PROCEDIMENTO` - Treinamento em procedimento (requer código_documento)
- `ALINHAMENTO` - Alinhamento interno
- `REUNIAO` - Reunião
- `CAPACITACAO` - Capacitação/Curso externo
- `OUTRO` - Outros tipos

## Campos Automatizados

### Área de Conhecimento (Coluna 14)

Este campo será **preenchido automaticamente** pelo sistema quando houver um procedimento vinculado:

1. Se `codigo_documento` estiver preenchido:
   - Sistema busca o procedimento no banco de dados
   - Copia o campo `area_conhecimento` do procedimento
   - Sobrescreve qualquer valor informado na planilha

2. Se não houver procedimento:
   - Utiliza o valor informado na coluna 14
   - Permite classificação manual

**Importante**: Para que a área de conhecimento seja automatizada, é necessário cadastrar este campo nos procedimentos do sistema.

## Formatos Esperados

### Datas
```
Formato: AAAA-MM-DD
Exemplos: 
- 2025-01-15
- 2025-12-31
```

### Carga Horária (hh:mm)
```
Formato: HH:MM
Exemplos:
- 04:00 (4 horas)
- 08:30 (8 horas e 30 minutos)
- 16:00 (16 horas)
```

### Custo
```
Formato: Números com ponto decimal
Exemplos:
- 500.00
- 1250.50
- 0.00
```

### Avaliação de Eficácia
```
Valores aceitos para SIM: SIM, S, TRUE, 1, YES
Valores aceitos para NÃO: NAO, N, FALSE, 0, NO (ou vazio)
```

## Exemplos de Uso

### Exemplo 1: Treinamento em Procedimento

```excel
matricula: 123456
tipo: PROCEDIMENTO
titulo_treinamento: Treinamento PO-001
codigo_documento: PO-001
numero_revisao: 03
data_inicio_treinamento: 2025-01-15
facilitador_fornecedor: Maria Santos
carga_horaria: 04:00
categoria_comunicacao: Presencial
metodologia_treinamento: Teórico-Prático
```

### Exemplo 2: Capacitação Externa (sem procedimento)

```excel
matricula: 123457
tipo: CAPACITACAO
titulo_treinamento: Curso de Calibração
codigo_documento: (vazio)
data_inicio_treinamento: 2025-01-20
data_final_treinamento: 2025-01-22
facilitador_fornecedor: Instituto XYZ
carga_horaria: 16:00
custo_treinamento: 500.00
categoria_comunicacao: Online
metodologia_treinamento: Teórico
necessita_avaliacao_eficacia: NAO
```

### Exemplo 3: Alinhamento Interno

```excel
matricula: 123458
tipo: ALINHAMENTO
titulo_treinamento: Alinhamento Mensal - Qualidade
codigo_documento: (vazio)
data_inicio_treinamento: 2025-01-10
facilitador_fornecedor: João Silva - Gerente
carga_horaria: 01:30
categoria_comunicacao: Presencial
observacao: Reunião mensal do setor
```

## Processamento da Importação

### 1. Validação de Colaborador

O sistema busca o colaborador pela **matrícula**:
- Se encontrado → continua
- Se não encontrado → registro é ignorado com mensagem de erro

### 2. Validação de Procedimento

Para `tipo` = 'PROCEDIMENTO':
- Busca procedimento pelo **codigo_documento**
- Se encontrado → vincula ao registro
- Se não encontrado → registro é ignorado com mensagem de erro
- **Copia área_conhecimento do procedimento**

### 3. Agrupamento Automático (Opcional)

Se a opção "Criar listas automaticamente" estiver ativa:
- Treinamentos com mesma data, facilitador e título são agrupados
- Uma lista de presença é criada automaticamente
- Código gerado: LP2025-0001, LP2025-0002, etc.

### 4. Atualização vs Criação

Se `sobrescrever_existentes` estiver ativo:
- Registros existentes (mesma matrícula + data + procedimento/título) são atualizados
- Novos campos são preenchidos
- Campos existentes são sobrescritos

Se desativado:
- Registros duplicados geram erro
- Apenas novos registros são criados

## Campos Adicionados aos Models

### Procedimento
```python
area_conhecimento = models.CharField(
    max_length=200, 
    null=True, 
    blank=True,
    verbose_name="Área de Conhecimento"
)
```

### RegistroTreinamento
```python
# Classificação
categoria_comunicacao = CharField(max_length=100)
metodologia_treinamento = CharField(max_length=100)
area_conhecimento = CharField(max_length=200)

# Execução
facilitador_fornecedor = CharField(max_length=200)
carga_horaria = CharField(max_length=10)  # formato hh:mm
custo_treinamento = DecimalField(max_digits=10, decimal_places=2)
data_final_treinamento = DateField()
mes_referencia = CharField(max_length=20)

# Avaliação
necessita_avaliacao_eficacia = BooleanField(default=False)
data_limite_avaliacao_eficacia = DateField()
resultado_avaliacao = TextField()
```

## Como Usar

### 1. Baixar Template

Acesse: **Treinamentos → Importar Treinamentos → Baixar Template Excel**

Ou use a URL: `/procedures/lista-presenca/download-template/`

### 2. Preencher Planilha

- Use a aba "Treinamentos" para os dados
- Consulte a aba "Instruções" para detalhes
- Siga os formatos especificados
- Preencha os campos obrigatórios

### 3. Importar

1. Acesse: **Treinamentos → Importar Treinamentos**
2. Selecione o arquivo Excel preenchido
3. Escolha as opções:
   - ☐ Criar listas de presença automaticamente
   - ☐ Sobrescrever registros existentes
4. Clique em "Importar"

### 4. Verificar Resultados

O sistema mostrará:
- ✅ Registros criados com sucesso
- ℹ️ Registros atualizados
- ℹ️ Listas de presença criadas
- ⚠️ Erros encontrados (com detalhes)

## Migration Aplicada

**Migration**: `0011_procedimento_area_conhecimento_and_more.py`

**Operações**:
- Add field `area_conhecimento` to procedimento
- Add field `area_conhecimento` to registrotreinamento
- Add field `carga_horaria` to registrotreinamento
- Add field `categoria_comunicacao` to registrotreinamento
- Add field `custo_treinamento` to registrotreinamento
- Add field `data_final_treinamento` to registrotreinamento
- Add field `data_limite_avaliacao_eficacia` to registrotreinamento
- Add field `facilitador_fornecedor` to registrotreinamento
- Add field `mes_referencia` to registrotreinamento
- Add field `metodologia_treinamento` to registrotreinamento
- Add field `necessita_avaliacao_eficacia` to registrotreinamento
- Add field `resultado_avaliacao` to registrotreinamento

## Benefícios da Nova Estrutura

### 1. Informações Completas
- Registro detalhado de cada treinamento
- Rastreabilidade completa
- Dados para auditoria e certificação

### 2. Classificação Robusta
- Múltiplas dimensões de classificação
- Facilita análises e relatórios
- Compatível com ISO 9001

### 3. Controle de Custos
- Registro de investimentos
- Análise de ROI
- Controle orçamentário

### 4. Gestão de Eficácia
- Acompanhamento de prazos
- Registro de resultados
- Evidências para auditorias

### 5. Flexibilidade
- Suporta procedimentos E capacitações externas
- Suporta alinhamentos internos
- Suporta participantes externos

## Próximos Passos Recomendados

### 1. Cadastrar Áreas de Conhecimento
Acessar cada procedimento e preencher o campo `area_conhecimento`:
- Qualidade
- Metrologia
- Segurança do Trabalho
- Meio Ambiente
- etc.

### 2. Criar Relatórios
Desenvolver relatórios usando os novos campos:
- Treinamentos por área de conhecimento
- Investimentos em treinamento
- Avaliações de eficácia pendentes
- Metodologias mais utilizadas

### 3. Automações
Configurar alertas:
- Avaliações de eficácia próximas ao vencimento
- Treinamentos de alto custo
- Capacitações externas programadas

## Suporte

Para dúvidas ou problemas:
1. Verifique a aba "Instruções" no template Excel
2. Consulte este documento
3. Revise as mensagens de erro na importação
4. Contate o administrador do sistema

---

**Última Atualização**: 28/12/2025  
**Versão**: 2.0  
**Migration**: 0011_procedimento_area_conhecimento_and_more

# CalibraWeb — Mapeamento Completo do Sistema
**Versão**: 1.0 (Agosto 2026)  
**Propósito**: Documento de referência para recriação e evolução do sistema para uma versão nova e melhorada.

---

## 1. Visão Geral

O **CalibraWeb** é um sistema de gestão de qualidade laboratorial construído em Django, destinado a laboratórios ópticos. Ele cobre os processos de:

- **Metrologia**: Controle de instrumentos e calibrações
- **Treinamentos**: Gestão de procedimentos, competências e listas de presença
- **Pessoas (RH)**: Colaboradores, férias, ocorrências e histórico
- **Laboratório**: Ocorrências operacionais e processo de Coating (anti-reflexo)
- **Fornecedores**: Cadastro e avaliação de fornecedores
- **Auditoria**: Modelos de auditoria com checklist personalizável
- **Quadros (Boards)**: Kanban para gestão de atividades
- **Ações Corretivas**: Módulo legado (marcado para reconstrução)

---

## 2. Stack Tecnológico

| Camada | Tecnologia |
|--------|-----------|
| **Framework** | Django 5.0 |
| **Banco (produção)** | Neon PostgreSQL |
| **Banco (desenvolvimento)** | SQLite |
| **Cache** | Redis (multi-nível: ThreadLocal L1 + Redis L2) |
| **Filas** | Celery (workers assíncronos) |
| **Scheduler** | Celery Beat (tasks agendadas) |
| **Servidor Web** | Gunicorn + Nginx |
| **Frontend** | Bootstrap 5 + Django Templates (SSR) |
| **Armazenamento de Arquivos** | AWS S3 (produção) |
| **Deploy** | Render.com (containerizado via Docker) |
| **PDF** | ReportLab + PyMuPDF (carimbo digital) |
| **Excel** | openpyxl |
| **Autenticação 2FA** | django-otp |

---

## 3. Estrutura de Apps Django

```
CalibraWeb/
├── config/              # settings.py, wsgi.py, urls.py raiz
├── core/                # Modelos base, permissões nav_*, autenticação
├── organization/        # Estrutura organizacional (Setor, CentroCusto, HierarquiaSetor)
├── rh/                  # Recursos Humanos (Colaborador, Férias, Ocorrências)
├── metrologia/          # Instrumentos, Calibrações, Cotações
├── procedures/          # Procedimentos (GED), Treinamentos, Listas de Presença
├── training/            # App legado de training (sendo absorvido por procedures)
├── laboratorio/         # Ocorrências operacionais, Coating (anti-reflexo)
├── maquinas/            # Máquinas do laboratório
├── fornecedores/        # Fornecedores e Avaliações
├── auditoria/           # Modelos e registros de auditoria
├── boards/              # Quadros Kanban
├── qms/                 # App legado (contém views ainda em uso)
├── shared/              # Middlewares, permissões, context processors, utilidades
├── documents/           # Geração e gestão de documentos PDF
├── acoes/               # Ações Corretivas (legado, marcado para reconstrução)
└── procurements/        # App legado de cotações (substituído por metrologia)
```

> **ATENÇÃO**: Os apps `qms`, `training`, `procurements` são **legados**. O app `acoes` foi **excluído do escopo** da versão 2.0 e será reconstruído do zero.

---

## 4. Módulo `core` — Núcleo e Permissões

### 4.1 Modelos

#### `UnidadeMedida`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(50), unique |
| `descricao` | CharField(200), null |

#### `NavigationPermission`
Modelo virtual (`managed=False`) que registra permissões `nav_*` no Django. Não cria tabela — apenas declara permissões.

**Padrão de nomenclatura:**
```
nav_mod_<modulo>           → aparição do módulo no navbar
nav_<modulo>_<bloco>       → visibilidade de bloco/seção
nav_<modulo>_<funcao>      → acesso a uma função/tela específica
```

**Módulos com permissões declaradas:**
- `metrologia` — dashboard, instrumentos, categorias, cotações, importação
- `treinamentos` — matrizes, procedimentos, listas de presença, evidências, planejamento
- `pessoas` — colaboradores, férias, ocorrências, organização
- `laboratorio` — ocorrências, categorias, máquinas, coating
- `fornecedores` — lista, cadastro, avaliações
- `auditoria` — modelos, registros
- `boards` — quadros, cards
- `usuarios` — gestão de usuários e permissões

### 4.2 Constantes Globais
```python
STATUS_CHOICES = [("ATIVO", ...), ("INATIVO", ...), ("INSS", ...)]
TURNOS_CHOICES = [("ADM", ...), ("TURNO_1", ...), ("TURNO_2", ...), ("TURNO_3", ...), ("12X36", ...)]
```

---

## 5. Módulo `organization` — Estrutura Organizacional

#### `Setor`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(100), unique |
| `responsavel` | CharField(100), null |

#### `CentroCusto`
| Campo | Tipo |
|-------|------|
| `setor` | FK → Setor |
| `codigo` | CharField(20) |
| `descricao` | CharField(100), null |
| unique_together | (setor, codigo) |

#### `HierarquiaSetor`
Define a cadeia de liderança por setor + turno.

| Campo | Tipo |
|-------|------|
| `setor` | FK → Setor |
| `turno` | CharField (TURNOS_CHOICES) |
| `lider` | FK → rh.Colaborador, null |
| `supervisor` | FK → rh.Colaborador, null |
| `gerente` | FK → rh.Colaborador, null |
| `diretor` | FK → rh.Colaborador, null |
| unique_together | (setor, turno) |

---

## 6. Módulo `rh` — Recursos Humanos

#### `Colaborador`
Entidade central de pessoa no sistema. Liga-se a um `auth.User` via OneToOne.

| Campo | Tipo | Notas |
|-------|------|-------|
| `user_django` | OneToOneField → User | null |
| `matricula` | CharField(20) | unique |
| `cpf` | CharField(14) | unique, null |
| `nome_completo` | CharField(100) | |
| `cargo` | CharField(100) | null |
| `grupo` | CharField(50) | Macro-grupo |
| `setor` | FK → organization.Setor | null |
| `centro_custo` | FK → organization.CentroCusto | null |
| `turno` | CharField (TURNOS_CHOICES) | |
| `posto_lideranca` | CharField | NAO_APLICA / LIDER / SUPERVISOR / GERENTE |
| `salario` | DecimalField | null |
| `em_ferias` | BooleanField | sincronizado por signal |
| `afastado` | BooleanField | |
| `tipo_afastamento` | CharField | INSS, Licença, etc. |
| `data_inicio_afastamento` / `data_fim_afastamento` | DateField | null |
| `lider` / `supervisor` / `gerente` | FK → self | hierarquia direta |
| `pacotes_treinamento` | M2M → procedures.PacoteTreinamento | |
| `is_active` | BooleanField | ativo no RH |

#### `Ferias`
| Campo | Tipo |
|-------|------|
| `colaborador` | FK → Colaborador |
| `status` | PLANEJADO / EM_ANDAMENTO / CONCLUIDO (auto no save) |
| `data_inicio` / `data_fim` | DateField |
| `dias_solicitados` | IntegerField |
| `aprovada` | BooleanField |
| `vencimento` | DateField, null |

#### `Ocorrencia` (disciplinar/feedback)
| Campo | Tipo |
|-------|------|
| `colaborador` | FK → Colaborador |
| `condutor` | FK → User |
| `data_ocorrencia` | DateField |
| `tipo` | AVISO / ADVERTENCIA / SUSPENSAO / DEMISSAO / ELOGIO / REABILITACAO / FEEDBACK |
| `natureza` | POSITIVA / NEGATIVA / NEUTRA |
| `descricao` | TextField |
| `arquivo_evidencia` | FileField |

#### `DocumentoPessoal`
| Campo | Tipo |
|-------|------|
| `colaborador` | FK → Colaborador |
| `tipo_documento` / `numero_documento` | CharField |
| `data_emissao` / `data_validade` | DateField |
| `arquivo` | FileField |

#### Histórico de Mudanças (rastreabilidade)
- **`HistoricoSetor`** — mudanças de setor (anterior, novo, data, motivo, registrado_por)
- **`HistoricoPosto`** — mudanças de cargo
- **`HistoricoSalario`** — mudanças de salário

---

## 7. Módulo `metrologia` — Instrumentos e Calibração

### 7.1 Instrumentos

#### `CategoriaInstrumento`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(100) |
| `sigla` | CharField(3), null — prefixo do código (ex: TH) |
| `tratativa_calibracao` | INTERNA / EXTERNA |
| `frequencia_calibracao_meses` | IntegerField, default=12 |

#### `InstrumentoReferencia`
Rastreia substituição — mantém código mesmo ao trocar o físico.

| Campo | Tipo |
|-------|------|
| `codigo_referencia` | CharField(50), unique |
| `categoria` | FK → CategoriaInstrumento |

#### `Instrumento`
Entidade central da Metrologia.

| Campo | Tipo | Notas |
|-------|------|-------|
| `tag` | CharField(50) | unique — identificador principal |
| `codigo` | CharField(50) | código interno |
| `descricao` | CharField(200) | |
| `fabricante` / `modelo` / `serie` | CharField(100) | |
| `categoria` | FK → CategoriaInstrumento | |
| `referencia` | FK → InstrumentoReferencia | null |
| `tolerancia_processo` | DecimalField | |
| `ativo` | BooleanField | |
| `data_ultima_calibracao` / `data_proxima_calibracao` | DateField | |
| `frequencia_meses` | IntegerField | |
| `responsavel` | FK → rh.Colaborador | |
| `setor` | FK → organization.Setor | |
| `localizacao` | CharField(100) | |
| `tratativa_calibracao` | INTERNA / EXTERNA | |

#### `FaixaMedicao`
Faixa de medição de um instrumento.

| Campo | Tipo |
|-------|------|
| `instrumento` | FK → Instrumento |
| `unidade` | FK → core.UnidadeMedida |
| `valor_minimo` / `valor_maximo` | DecimalField(10,4) |
| `resolucao` / `nominal` / `tolerancia_mais_menos` | DecimalField |

#### `FaixaMedicaoPadrao` e `FaixaMedicaoPadraoCategoria`
Faixas de referência reutilizáveis para importação em massa e sugestão automática.

### 7.2 Calibração

#### `HistoricoCalibracao`
| Campo | Tipo | Notas |
|-------|------|-------|
| `instrumento` | FK → Instrumento | |
| `atendimento` | FK → AtendimentoSolicitacao | null — se oriunda de cotação |
| `data_calibracao` | DateField | |
| `numero_certificado` | CharField | default "S/N" |
| `tem_selo_rbc` | BooleanField | |
| `tipo_calibracao` | EXTERNA / INTERNA | |
| `responsavel` / `fornecedor` | CharField | técnico e laboratório |
| `erro_encontrado` / `incerteza` / `tolerancia_usada` | DecimalField | |
| `proxima_calibracao` | DateField | calculado no save() |
| `certificado` | FileField | |
| `certificado_validado` | BooleanField | |
| `certificado_carimbado` | FileField | PDF com carimbo digital |
| `resultado` | APROVADO_SEM_CORRECAO / APROVADO_COM_CORRECAO / REPROVADO | auto no save() |

**Lógica automática no `save()`**: calcula `resultado` comparando `|erro|` vs `tolerância`; calcula `proxima_calibracao` pela frequência da categoria.

#### `ResultadoFaixaCalibracao`
| Campo | Tipo |
|-------|------|
| `historico` | FK → HistoricoCalibracao |
| `faixa` | FK → FaixaMedicao |
| `erro` / `incerteza` / `tolerancia` | DecimalField |
| `ema` | DecimalField | Tolerância/2 (auto) |
| `eme` | DecimalField | \|erro\| + incerteza (auto) |
| `resultado` | APROVADO_SEM_CORRECAO / APROVADO_COM_CORRECAO / REPROVADO (auto) |
| `tabela_correcao` | JSONField | valores de correção |

#### `OrdemCalibracao`
| Campo | Tipo |
|-------|------|
| `instrumento` | FK → Instrumento |
| `fornecedor` | CharField |
| `tipo_local` | EXTERNO / IN_LOCO |
| `status` | AGENDADO / ENVIADO / EM_CALIBRACAO / RETORNOU / FINALIZADO |
| `data_prevista` / `data_envio` / `data_retorno` | DateField |

### 7.3 Fluxo de Cotações (4 Etapas)

#### `SolicitacaoCotacao` — Etapa 1
| Campo | Tipo |
|-------|------|
| `numero` | CharField, auto: `SOL-YYYY-####` |
| `status` | ABERTA → INSTRUMENTOS_SELECIONADOS → COTACAO_SOLICITADA → AGUARDANDO_PLANEJAMENTO → PARCIALMENTE_PLANEJADA → PLANEJADA → PARCIALMENTE_REALIZADO → REALIZADO → CONCLUIDA / CANCELADA |
| `prioridade` | BAIXA / MEDIA / ALTA / CRITICA |

O método `atualizar_status_automatico()` calcula o status percorrendo itens, cotações e atendimentos.

#### `ItemSolicitacao`
| Campo | Tipo |
|-------|------|
| `instrumento` | FK → Instrumento |
| `servico` | CALIBRACAO / RASTREIO_BRACO / SUBSTITUICAO |
| `local_atendimento` | NO_LABORATORIO / NO_LOCAL / COMPRAR_NOVO |

#### `CotacaoFornecedor` — Etapa 2
| Campo | Tipo |
|-------|------|
| `solicitacao` | FK → SolicitacaoCotacao |
| `fornecedor` | FK → fornecedores.Fornecedor |
| `status` | PENDENTE / RESPONDIDA / ACEITA / RECUSADA |

#### `AtendimentoSolicitacao` — Etapa 3
| Campo | Tipo |
|-------|------|
| `item_solicitacao` | FK → ItemSolicitacao |
| `data_prevista_atendimento` | DateField — planejamento |
| `data_realizada` / `data_retorno` / `data_chegada` | DateField — execução |

---

## 8. Módulo `procedures` — GED e Treinamentos

### 8.1 Gestão de Documentos (GED)

#### `Procedimento`
| Campo | Tipo |
|-------|------|
| `codigo` | CharField(50), unique |
| `nome` | CharField(200) |
| `descricao` | TextField |
| `pasta` | CharField — localização no DMS (Qualiex) |
| `classificacao` | CharField — tipo de procedimento |
| `numero_revisao` | CharField |
| `ultima_revisao` / `data_aprovacao` / `proxima_revisao` / `data_validade` | DateField |
| `matriz` | CharField — nome da matriz funcional |
| `sub_area` | CharField |
| `area_conhecimento` | CharField |
| `criticidade` | CRITICO / NAO_CRITICO |

#### `MatrizProcedimento`
Classificação funcional macro dos procedimentos.

| Campo | Tipo |
|-------|------|
| `nome` | CharField(120), unique |

#### `SubAreaProcedimento`
| Campo | Tipo |
|-------|------|
| `matriz` | FK → MatrizProcedimento |
| `nome` | CharField(120) |

#### `PacoteTreinamento`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(100), unique |
| `procedimentos` | M2M → Procedimento |

#### `ProcedimentoRevisao`
| Campo | Tipo |
|-------|------|
| `procedimento` | FK → Procedimento |
| `revisao` | CharField |
| `elaborador` / `revisor` / `aprovador` | FK → rh.Colaborador |
| `arquivo_prev` | FileField |

#### `ResponsavelTreinamentoMatriz`
Define o responsável pelos treinamentos de uma matriz/sub-área por turno.

| Campo | Tipo |
|-------|------|
| `matriz` | FK → MatrizProcedimento |
| `sub_area` | FK → SubAreaProcedimento, null |
| `turno` | CharField |
| `colaborador` | FK → rh.Colaborador |

### 8.2 Listas de Presença

#### `ListaPresenca`
| Campo | Tipo | Notas |
|-------|------|-------|
| `codigo` | CharField(50), auto: `LP{ano}-{seq:04d}` | |
| `titulo` | CharField(200) | |
| `instrutor_nome` | CharField(200) | texto livre |
| `instrutor` | FK → rh.Colaborador | null, vinculado auto |
| `data_sessao` | DateField | |
| `hora_inicio` / `hora_fim` | TimeField | |
| `carga_horaria` | DecimalField | |
| `local` | CharField | |
| `template` | FK → TemplateListaPresenca | layout Excel |
| `arquivo_assinado` | FileField | evidência documental |

#### `RegistroTreinamento`
| Campo | Tipo |
|-------|------|
| `colaborador_nome` | CharField — texto livre |
| `colaborador` | FK → rh.Colaborador, null |
| `participante_externo` | FK → ParticipanteExterno, null |
| `tipo` | PROCEDIMENTO / ALINHAMENTO / REUNIAO / CAPACITACAO / OUTRO |
| `procedimento` | FK → Procedimento, null |
| `titulo_treinamento` | CharField — obrigatório se sem procedimento |
| `lista_presenca` | FK → ListaPresenca |
| `data_treinamento` | DateField, null |
| `validade_treinamento` | DateField |
| `revisao_treinada` | CharField |

#### `ParticipanteExterno`
| Campo | Tipo |
|-------|------|
| `nome_completo` | CharField |
| `cpf` | CharField, null |
| `empresa` | CharField, null |
| `email` | EmailField, null |

---

## 9. Módulo `laboratorio` — Operações e Coating

#### `CategoriaLaboratorio`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(150), unique |
| `impacto` | BAIXO / MEDIO / ALTO / CRITICO |
| `ativo` | BooleanField |

Properties especiais: `exige_colaborador` e `exige_maquina` detectam categorias pelo nome normalizado (sem acento), tornando campos obrigatórios no formulário.

#### `OcorrenciaLaboratorio`
| Campo | Tipo |
|-------|------|
| `categoria` | FK → CategoriaLaboratorio |
| `assunto` | CharField(200) |
| `colaborador` | FK → rh.Colaborador, null |
| `maquina` | FK → maquinas.Maquina, null |
| `detalhamento` | TextField |
| `consequencias` | TextField |
| `impacto` | BAIXO / MEDIO / ALTO / CRITICO |
| `responsavel` | FK → User |
| `data_abertura` | DateTimeField |
| `data_encerramento` | DateTimeField, null |
| `status` | ABERTA / EM_ANDAMENTO / ENCERRADA |

#### Coating (Anti-Reflexo)
- **`TurnoCoating`** — regras de turno para o processo
- **`RegistroCoating`** — registro diário de produção (lotes processados)
- **`EquipeCoating`** — operadores do processo coating

---

## 10. Módulo `fornecedores` — Fornecedores

#### `Fornecedor`
| Campo | Tipo |
|-------|------|
| `empresa` | CharField(255) |
| `nome_fantasia` | CharField(255) |
| `endereco` | CharField |
| `cnpj` / `siret` / `ein` | CharField |
| `uf` | CharField(2) |
| `tipo` | CRITICO / NAO_CRITICO / TERCEIRIZADO |
| `ativo` | BooleanField |
| `licenca_funcionamento` | BooleanField |
| `autorizacao_funcionamento` | BooleanField |
| `certificado_iso` | BooleanField — ISO 9001/13485/17025 |

#### `AvaliacaoFornecedor`
| Campo | Tipo |
|-------|------|
| `fornecedor` | FK → Fornecedor |
| `data` | DateField |
| `avaliador` | FK → User |
| `tipo` | SELECAO / REAVALIACAO / MONITORAMENTO |
| `tipo_nota` | PRODUTO / SERVICO |
| `pontuacao_ano` | FloatField, default=100 |

#### `PerguntaAvaliacao`
Banco de perguntas configuráveis por tipo e produto/serviço.

| Campo | Tipo |
|-------|------|
| `texto` | CharField(255) |
| `tipo` | SELECAO / REAVALIACAO / MONITORAMENTO |
| `produto_servico` | PRODUTO / SERVICO / AMBOS |
| `ativo` / `ordem` | BooleanField / IntegerField |

#### `RespostaAvaliacao`
| Campo | Tipo |
|-------|------|
| `avaliacao` | FK → AvaliacaoFornecedor |
| `pergunta` | FK → PerguntaAvaliacao |
| `resposta` | BooleanField — Sim/Não |

#### `RespostaMatrizAvaliacao`
Avaliação por requisitos (A, B, C, D) de produto ou serviço específico.

| Campo | Tipo |
|-------|------|
| `avaliacao` | FK → AvaliacaoFornecedor |
| `tipo` | PRODUTO / SERVICO |
| `nome_item` | CharField |
| `requisito` | A (ISO) / B (AFE/Licença) / C (Docs legais) / D (Referência mercado) |

#### `DocumentoFornecedor`
Documentos vinculados ao fornecedor (contratos, certidões, etc.).

---

## 11. Módulo `auditoria` — Auditorias

#### `ModeloAuditoria`
Template de auditoria com checklist configurável.

| Campo | Tipo |
|-------|------|
| `nome` | CharField(150), unique |
| `objeto_auditoria` | TextField |
| `link_sharepoint` | URLField |
| `periodicidade` | UNICA / DIARIA / SEMANAL / QUINZENAL / MENSAL / TRIMESTRAL / SEMESTRAL / ANUAL |

#### `SecaoAuditoria` e `PerguntaAuditoria`
Estrutura hierárquica: Seção → Perguntas.

**Tipos de resposta:**
- `SIM_NAO` — boolean
- `LISTA` — opções pré-definidas
- `TEXTO` — resposta livre
- `NUMERO` — valor numérico

**Preset ISO disponível:**
```python
opcoes_resposta: ["Conforme", "Não Conforme", "Não Se Aplica", "Oportunidade de Melhoria"]
```

#### `RegistroAuditoria`
| Campo | Tipo |
|-------|------|
| `modelo` | FK → ModeloAuditoria |
| `data_auditoria` | DateField |
| `auditor` | FK → User |
| `status` | EM_ANDAMENTO / CONCLUIDA |

#### `RespostaAuditoria`
| Campo | Tipo |
|-------|------|
| `registro` | FK → RegistroAuditoria |
| `pergunta` | FK → PerguntaAuditoria |
| `resposta` | CharField |
| `evidencia` | FileField |

---

## 12. Módulo `boards` — Quadros Kanban

#### `Board`
| Campo | Tipo |
|-------|------|
| `nome` | CharField(100) |
| `criado_por` | FK → rh.Colaborador |
| `membros` | M2M → rh.Colaborador |
| `arquivado` | BooleanField |
| `todos_colaboradores` | BooleanField — visível para toda empresa |

#### `BoardColumn` — Colunas do Kanban
| Campo | Tipo |
|-------|------|
| `quadro` | FK → Board |
| `nome` | CharField(100) |
| `ordem` | IntegerField |

#### `Card` — Tarefa/cartão
| Campo | Tipo |
|-------|------|
| `coluna` | FK → BoardColumn |
| `etiquetas` | M2M → BoardLabel |
| `antecessora` | FK → self (dependência) |
| `titulo` | CharField(200) |
| `responsaveis` | M2M → rh.Colaborador |
| `data_entrega` | DateField |
| `prioridade` | BAIXA / ALTA |
| `periodicidade` | AVULSA / DIARIA / SEMANAL / QUINZENAL / MENSAL / BIMESTRAL / TRIMESTRAL / SEMESTRAL / ANUAL |

#### Modelos auxiliares
- **`BoardLabel`** — etiquetas coloridas
- **`BoardLink`** — links rápidos do quadro
- **`ChecklistItem`** — itens de checklist no card
- **`CardComment`** — comentários no card
- **`BoardMention`** — menções de colaboradores
- **`BoardNotification`** — notificações por atividade
- **`BoardActivity`** — log de auditoria do quadro
- **`CardPlanningDate`** — planejamentos de data/hora adicionais

---

## 13. Sistema de Permissões

### Estrutura

Permissões customizadas `nav_*` via modelo virtual `NavigationPermission`, armazenadas na tabela `auth_permission` do Django.

**3 camadas de controle:**
1. `is_staff` / `is_superuser` — Django padrão
2. `nav_mod_*` — acesso ao módulo no navbar
3. `nav_<modulo>_<funcao>` — acesso a funções específicas

**`NAV_STRUCTURE`** (em `shared/permissions.py`):  
Define hierarquia módulos → blocos → funções. O template base renderiza apenas o que o usuário tem permissão.

**Uso nas views:**
```python
@permission_required('core.nav_metrologia_lista_instrumentos')

class MinhaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.nav_metrologia_lista_instrumentos'
```

---

## 14. Sistema de Cache

### Arquitetura Multi-Nível

```
L1: ThreadLocal (por request)  — 0ms,  ~30-50% hit rate
L2: Worker Cache LRU (RLock)   — 0-1ms, ~40-60% hit rate, max 1000 itens
L3: Redis                       — 2-10ms
```

**Decorators:**
- `@cache_view(timeout)` — views inteiras
- `@cache_api(timeout)` — endpoints de API

**Invalidação**: Signals Django disparam invalidação por tags de modelo.

---

## 15. Tarefas Assíncronas (Celery)

| Task | Frequência | Descrição |
|------|-----------|-----------|
| Importação de matrizes | Sob demanda | Processa Excel/CSV em background |
| Exportação de listas | Sob demanda | Gera Excel de listas de presença |
| Cache warming | Agendado | Pré-carrega caches de dashboards |
| Verificação de vencimentos | Diária | Instrumentos com calibração vencida |

---

## 16. Fluxos de Negócio Principais

### Fluxo de Calibração de Instrumentos
```
1. Instrumento cadastrado com categoria + faixas de medição
2. Sistema monitora data_proxima_calibracao
3. SolicitacaoCotacao agrupa instrumentos vencendo
4. CotacaoFornecedor — proposta de preço do fornecedor
5. AtendimentoSolicitacao — planejamento da execução
6. Calibração realizada → HistoricoCalibracao com certificado
7. resultado calculado automaticamente (erro vs tolerância)
8. Datas atualizadas; proxima_calibracao recalculada
```

### Fluxo de Treinamento
```
1. Procedimento cadastrado (GED) com código, revisão, criticidade
2. PacoteTreinamento agrupa procedimentos relacionados
3. Pacotes atribuídos a Colaboradores (M2M em Colaborador.pacotes_treinamento)
4. ListaPresenca criada para uma sessão de treinamento
5. RegistroTreinamento por participante (colaborador ou externo)
6. Upload de arquivo_assinado como evidência documental
7. Relatório compara procedimentos exigidos vs. treinados
```

### Fluxo de Auditoria
```
1. ModeloAuditoria com Seções e Perguntas configuradas
2. Periodicidade determina frequência
3. RegistroAuditoria criado para cada aplicação
4. Auditor preenche RespostaAuditoria por pergunta
5. Dashboard exibe conformidade por seção (Conforme/NC/NA)
```

### Fluxo de Avaliação de Fornecedor
```
1. Fornecedor cadastrado (tipo: CRITICO/NAO_CRITICO/TERCEIRIZADO)
2. AvaliacaoFornecedor (SELECAO no cadastro inicial)
3. PerguntaAvaliacao respondidas (Sim/Não) por tipo
4. RespostaMatrizAvaliacao para requisitos A/B/C/D
5. Pontuação calculada; resultado determina aprovação
6. Ciclos periódicos: REAVALIACAO e MONITORAMENTO
```

---

## 17. Padrões Arquiteturais Adotados

| Padrão | Onde é usado |
|--------|-------------|
| **Fat Model, Thin View** | Lógica de negócio nos `save()` dos modelos |
| **Signals** | Sincronização entre modelos (ex: `em_ferias` no Colaborador) |
| **Class-Based Views** | Maioria das views com mixins de permissão |
| **Function-Based Views** | APIs e endpoints simples |
| **Soft Delete** | Não implementado — campos `ativo/arquivado` |
| **Auditoria interna** | Histórico explícito (HistoricoSetor, HistoricoPosto, etc.) |
| **Row-Level Tenancy** | **Futuro** — multi-tenancy via FK `laboratorio` |

---

## 18. Pontos de Atenção para v2.0

> **App `qms`**: Ainda contém views em uso (`qms/views.py`). Mapear todas antes de refatorar.

> **App `acoes`**: Excluído do escopo multi-tenancy. Reconstruir do zero na v2.0.

> **App `training` vs. `procedures`**: Duplicação entre apps. O `procedures` é o atual correto. Consolidar completamente na v2.0.

> **Permissões `nav_*` hardcoded**: Funcionam bem mas requerem codenames manuais. O sistema de Perfis de Usuário (ver `plano_multi_empresa_regional.md`) automatizará na v2.0.

> **Frontend SSR puro**: Django Templates + Bootstrap 5. Nenhum SPA. Avaliar HTMX na v2.0 para interatividade sem quebrar o padrão.

> **Sem soft delete**: Ao recriar, decidir se implementa soft delete global ou mantém o padrão de `ativo=False`.

---

## 19. Dependências Principais

```
Django==5.0.*
celery
redis / django-redis
psycopg2-binary
gunicorn
boto3                    # AWS S3
reportlab                # Geração de PDF
PyMuPDF / fitz          # Carimbo em PDF
openpyxl                 # Excel
django-otp               # 2FA
python-dateutil          # cálculos de datas relativas
```

---

## 20. Diagrama de Relações Entre Apps

```
                    ┌──────────────┐
                    │    core      │
                    │ UnidadeMedida│
                    │  nav_*perms  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────▼──┐  ┌──────▼──────┐  ┌─▼──────────┐
    │organization│  │     rh      │  │  metrologia │
    │  Setor     │  │ Colaborador │  │ Instrumento │
    │ CentroCusto│  │  Ferias     │  │ Historico   │
    │ Hierarquia │  │ Ocorrencia  │  │ Cotacoes    │
    └────────────┘  └──────┬──────┘  └─────────────┘
                           │
          ┌────────────────┼─────────────────────┐
          │                │                     │
  ┌───────▼──────┐  ┌──────▼──────┐  ┌──────────▼─────┐
  │  procedures  │  │  laboratorio│  │  fornecedores  │
  │ Procedimento │  │ Ocorrencia  │  │  Fornecedor    │
  │ ListaPresenca│  │  Coating    │  │  Avaliacao     │
  │ Treinamentos │  └─────────────┘  └────────────────┘
  └──────────────┘
          │
  ┌───────┴──────┐         ┌──────────┐
  │   auditoria  │         │  boards  │
  │ ModeloAudit  │         │  Board   │
  │  Registro    │         │  Card    │
  └──────────────┘         └──────────┘
```

---

*Última atualização: Agosto 2026*  
*Base: código-fonte analisado diretamente dos apps Django do projeto*  
*Próxima evolução planejada: [plano_multi_empresa_regional.md](./plano_multi_empresa_regional.md)*

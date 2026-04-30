# Fluxos de Negócio - CalibraWEB

## Módulos Principais

### 1. Core (Núcleo)

Funcionalidades principais e compartilhadas do sistema.

**Entidades principais**: 
- Usuários
- Permissões
- Autenticação

### 2. Metrologia

Gerenciamento de calibração, padrões e instrumentos de medição.

**Fluxo Principal**:
```
Instrumento
    ↓
Faixa de Medição
    ↓
Padrão de Calibração
    ↓
Histórico de Calibração
    ↓
Certificado de Calibração
```

**Funcionalidades**:
- Cadastro de instrumentos
- Configuração de faixas de medição
- Gerenciamento de padrões
- Geração de certificados
- Histórico de calibrações

### 3. RH (Recursos Humanos)

Gestão de recursos humanos, treinamentos e colaboradores.

**Fluxo Principal**:
```
Colaborador
    ↓
Treinamento (cadastro)
    ↓
Atribuição de Treinamento
    ↓
Validação/Conclusão
    ↓
Histórico de Treinamentos
```

**Funcionalidades**:
- Gestão de colaboradores
- Planejamento de treinamentos
- Listas de presença
- Controle de férias
- Relatórios de desempenho

### 4. Procedures (Procedimentos)

Gerenciamento de procedimentos operacionais e disciplinas.

**Fluxo Principal**:
```
Disciplina
    ↓
Procedimento
    ↓
Versão do Procedimento
    ↓
Publicação
```

**Funcionalidades**:
- Cadastro de disciplinas
- Criação de procedimentos
- Controle de versões
- Aprovações
- Histórico de mudanças

### 5. Organization (Organização)

Estrutura organizacional, departamentos e centros de custo.

**Entidades**:
- Centros de Custo
- Departamentos
- Posições
- Hierarquia Organizacional

### 6. Training (Treinamentos)

Sistema complementar de gestão de programas de treinamento.

**Funcionalidades**:
- Calendário de treinamentos
- Inscrições
- Avaliações
- Certificados

## Fluxos Principais de Dados

### Fluxo 1: Importação de Matrizes

```
Arquivo Excel/CSV
    ↓
Validação de Formato
    ↓
Mapeamento de Colunas
    ↓
Processamento em Batch (Celery)
    ↓
Atualização do Banco de Dados
    ↓
Notificação ao Usuário
```

### Fluxo 2: Processamento de Certificados

```
Solicitação de Certificado
    ↓
Coleta de Dados de Calibração
    ↓
Geração de PDF (ReportLab)
    ↓
Carimbo Digital (PyMuPDF)
    ↓
Armazenamento em S3
    ↓
Disponibilização ao Usuário
```

### Fluxo 3: Agendamentos Automáticos (Beat)

```
Celery Beat (Scheduler)
    ↓
Task Agendada (ex: limpeza de cache)
    ↓
Celery Worker
    ↓
Execução da Lógica
    ↓
Log e Notificações
```

## Integrações Externas

### AWS S3
- Armazenamento de certificados PDF
- Backup de documentos
- Arquivos enviados por usuários

### Email
- Notificações automáticas
- Relatórios agendados
- Confirmações de ações

### Redis
- Cache de sessões
- Fila de mensagens (Celery)
- Cache de dados frequentes

## Segurança

- Autenticação por sessão Django
- Permissões baseadas em roles
- CSRF protection
- SQL Injection prevention (ORM Django)
- Rate limiting (em estrutura de API)

---

Para setup e instalação, consulte [Setup Local](./setup.md)

Para detalhes técnicos, consulte [Arquitetura](./arquitetura.md)

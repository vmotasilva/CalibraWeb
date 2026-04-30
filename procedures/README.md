# 📦 Módulo Procedures

## Descrição

Módulo unificado que consolida funcionalidades de **Procedimentos**, **Treinamentos**, **Fornecedores** e **Cotações** em uma única aplicação Django.

Este módulo foi criado através da consolidação dos módulos `training` e `procurements` em **Dezembro de 2025**.

## 🏗️ Estrutura

```
procedures/
├── models.py              # 9 modelos consolidados
├── admin.py               # Interface admin
├── views/                 # 21 views
├── forms/                 # 8 formulários
├── urls.py                # Rotas (namespace: procedures)
├── apps.py                # Configuração
├── tests.py               # Testes
├── signals.py             # Signals Django
├── migrations/            # Migrações de banco
├── templates/procedures/  # Templates HTML
├── static/procedures/     # Arquivos estáticos
└── tasks/                 # Tasks Celery
```

## 📊 Modelos

### Procedimentos & Treinamentos
- `Procedimento` - Documentos operacionais (GED)
- `Area` - Classificação de áreas
- `PacoteTreinamento` - Agrupamento de procedimentos
- `ProcedimentoRevisao` - Histórico de versões
- `RegistroTreinamento` - Qualificação de colaboradores

### Fornecedores & Cotações
- `Fornecedor` - Dados do fornecedor
- `AvaliacaoFornecedor` - Avaliação de desempenho
- `ProcessoCotacao` - Solicitação de cotação
- `Orcamento` - Proposta de orçamento

## 🔗 URLs

Todas as rotas estão sob o namespace `procedures:`

```
/procedures/procedimentos/              - Lista
/procedures/procedimentos/novo/         - Criar
/procedures/procedimentos/<id>/         - Detalhes
/procedures/procedimentos/<id>/editar/  - Editar

/procedures/treinamentos/               - Lista
/procedures/treinamentos/novo/          - Criar
/procedures/treinamentos/<id>/          - Detalhes
/procedures/treinamentos/<id>/editar/   - Editar

/procedures/fornecedores/               - Lista
/procedures/fornecedores/novo/          - Criar
/procedures/fornecedores/<id>/          - Detalhes
/procedures/fornecedores/<id>/editar/   - Editar

/procedures/cotacoes/                   - Lista
/procedures/cotacoes/novo/              - Criar
/procedures/cotacoes/<id>/              - Detalhes
/procedures/cotacoes/<id>/editar/       - Editar

/procedures/orcamentos/novo/            - Criar
/procedures/orcamentos/<id>/editar/     - Editar
```

## 🎯 Views

### Procedimentos
- `procedimentos_list_view` - Lista com paginação e filtros
- `novo_procedimento_view` - Criar novo
- `editar_procedimento_view` - Editar existente
- `detalhe_procedimento_view` - Visualizar detalhes
- `export_procedimentos_excel_view` - Exportar para Excel

### Treinamentos
- `treinamentos_list_view` - Lista com filtros
- `novo_treinamento_view` - Registrar novo
- `editar_treinamento_view` - Editar registro
- `treinamentos_detalhe_view` - Visualizar detalhes

### Fornecedores
- `fornecedores_list_view` - Lista com filtros
- `novo_fornecedor_view` - Cadastrar
- `editar_fornecedor_view` - Editar dados
- `detalhe_fornecedor_view` - Visualizar perfil

### Avaliações
- `nova_avaliacao_fornecedor_view` - Registrar avaliação

### Cotações
- `cotacoes_list_view` - Lista de processos
- `nova_cotacao_view` - Abrir novo processo
- `editar_cotacao_view` - Editar processo
- `detalhe_cotacao_view` - Visualizar processo com orçamentos

### Orçamentos
- `novo_orcamento_view` - Receber orçamento
- `editar_orcamento_view` - Editar orçamento

## 📝 Formulários

- `ProcedimentoForm` - Criar/editar procedimentos
- `RegistroTreinamentoForm` - Registrar treinamentos
- `PacoteTreinamentoForm` - Criar pacotes
- `ImportacaoProcedimentosForm` - Importar em massa
- `FornecedorForm` - Cadastrar fornecedor
- `AvaliacaoFornecedorForm` - Avaliar fornecedor
- `ProcessoCotacaoForm` - Criar processo de cotação
- `OrcamentoForm` - Registrar orçamento

## ⚙️ Setup Inicial

### 1. Migração do Banco
```bash
python manage.py migrate procedures
```

### 2. Criar Super Usuário (se necessário)
```bash
python manage.py createsuperuser
```

### 3. Coletar Arquivos Estáticos
```bash
python manage.py collectstatic
```

## 🧪 Testes

Rodar testes do módulo:
```bash
python manage.py test procedures
```

## 📚 Documentação Relacionada

- `UNIFICACAO_PROCEDURES_COMPLETA.md` - Detalhes técnicos da unificação
- `UNIFICACAO_PROCEDURES_SUMARIO.md` - Sumário executivo

## 🔄 Integrações

### Com RH
- Relacionamento com `Colaborador` para treinamentos e avaliações

### Com Metrologia
- Relacionamento com `Instrumento` para cotações

## 🐛 Troubleshooting

### Importação de procedimentos não funciona
Verifique se o arquivo CSV/Excel tem as colunas esperadas

### Signals não disparam
Verifique se `procedures.apps.ProceduresConfig.ready()` está configurado

### Templates não aparecem
Certifique-se de rodar `python manage.py collectstatic`

## 👤 Contato

Para dúvidas sobre este módulo, consulte a documentação ou abra uma issue no repositório.

---

**Última atualização:** Dezembro 2025
**Status:** ✅ Pronto para Produção

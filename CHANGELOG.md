# CHANGELOG - CalibraWeb

Todas as alterações importantes do CalibraWeb são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e usa [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### 🔄 Em Desenvolvimento
Alterações que ainda não foram lançadas em uma versão oficial.

### ✨ Adicionado (Agenda)
- **Periodicidade dos checklists recorrentes**: além da diária (dias da semana), agora semanal, quinzenal (a cada 2 semanas nos dias marcados), mensal, bimestral, trimestral, semestral e anual (dia do mês; meses curtos usam o último dia). A contagem parte da data em que o checklist é salvo ou tem a periodicidade alterada. Migração aditiva `agenda.0007` (checklists existentes continuam diários).

### ✨ Adicionado (Módulo de Pessoas)
- **Estrutura de Equipes › topo compacto e fixo**: sem título; abas, busca escrita (setor, bloco, posto ou colaborador), botão de filtros (setor e turno, com contador), ícone de ajuda e ações (Importar, Novo setor, Voltar, Remover selecionados) numa única barra que fica congelada sob a barra de navegação.
- **Estrutura de Equipes › Quadro por turno em cards** (Setor › Bloco › Posto › turnos › colaboradores): cards de colaborador/VAGO/Reserva arrastáveis entre turnos, postos, blocos e setores (arrastar um card marcado leva todos os marcados), caixa de marcação e botão **Remover selecionados** para tirar o nome do posto.
- **Pop-up de alocação**: filtros por setor, turno, líder e cargo, opção "somente sem posto", paginação (10/25/50) e seleção mantida entre páginas; API de membros com `lider_id`, `cargo`, `pagina`, `por_pagina` e `opcoes`.
- **Estrutura de Equipes e Turnos** (menu Pessoas › Equipe): estrutura de trabalho em Setor › Bloco › Posto de trabalho, com titular e situação por turno e associação das pessoas aos postos
- Posto sem pessoa associada é marcado como **VAGO** (necessário contratar) ou **RESERVA** (equipamento reserva instalado); aba "Quadro por turno" com resumo de vagas e reservas
- Movimentação em lote de pessoas entre postos, com ajuste opcional de turno; efetivo planejado x atual por turno
- Novas permissões de navegação: visualizar e editar a estrutura
- **Construção livre da estrutura**: criar Setor, Bloco e Posto de trabalho direto na tela (botões "+" em cada nível) e, em cada posto, alocar por turno **Colaborador**, **VAGO** (necessário contratar) ou **Reserva** (equipamento reserva instalado), em qualquer quantidade; o mesmo colaborador pode atuar em vários postos. Uma VAGO vira colaborador ao editar a alocação (contratação)
- Estrutura de Equipes: **turnos próprios de cada setor**, definidos pelo usuário ao criar ou editar o setor (adicionar, renomear e remover; só é possível remover turnos sem alocações), independentes dos turnos de outros módulos. Filtro, painéis, Quadro por turno (uma tabela por setor) e formulários de alocação passam a usar os turnos do setor correspondente. Os setores existentes receberam os turnos Administrativo e Turno 01/02/03 e as alocações foram mantidas; a importação de planilha cria no setor escolhido os turnos da planilha que ainda não existirem
- Estrutura de Equipes: **setores próprios da tela**, independentes do cadastro de setores da empresa (criar, renomear e excluir setor aqui não altera nada fora da estrutura); a árvore deixa de listar os setores do cadastro. Os setores que já tinham blocos foram migrados. A aba Colaboradores ganhou um filtro separado pelo setor do cadastro do colaborador
- Estrutura de Equipes: **alocar em um ou mais turnos de uma vez** (caixas de seleção de turnos) no formulário de alocação e na aba Colaboradores; a quantidade de vagas/reservas vale para cada turno marcado
- Estrutura de Equipes: **botão de edição (lápis) em cada linha da árvore** (setor, bloco e posto); editar setor renomeia o setor
- Estrutura de Equipes: **ordenação automática** por nome (sem diferenciar acento/maiúsculas e com números em ordem natural: DLP 2 antes de DLP 10); o campo "Ordem" saiu do formulário
- Estrutura de Equipes: turnos limitados a Administrativo, Turno 01, 02 e 03 (12x36 removido desta tela; o cadastro de colaboradores não muda)
- Estrutura de Equipes: **filtro por setor** (vale para a árvore, o Quadro por turno e a lista de colaboradores) e aba **Colaboradores** para filtrar, selecionar vários e alocá-los em um posto/turno; o Quadro por turno ganhou "+ alocar" em cada célula e edição direta dos itens
- Build: build de **preview** não migra nem altera o banco (migrações, permissões e superusuário) a menos que `PREVIEW_DB_PROPRIO=1`, para não mexer no banco da produção; diagnóstico `[db-guard]` sem segredos no log
- Correção: a tela ficava vazia para quem pode editar (modais do Bootstrap eram criados antes do script ser carregado)
- **Importação por planilha (.xlsx)** da estrutura (bloco, posto e titular por turno), em duas etapas: prévia editável com revisão de nomes e escolha da pessoa em casos ambíguos, e gravação só após confirmar (tudo ou nada)

### 🐛 Corrigido (Módulo de Fornecedores)
- Botões protegidos por permissão (Editar, Novo Documento, Remover, Matriz, Responder...) nunca apareciam: as tags `can_nav_view` estavam fora do `{% block %}` dos templates
- Erro 500 ao enviar formulário de monitoramento inválido e ao editar/remover registros de seleção/reavaliação pela tela de monitoramento
- Reavaliação: regra de "uma por ano" não era aplicada; modal de nova reavaliação enviava para uma view incompatível
- Monitoramento: tipo da nota agora é obrigatório; atualização no mesmo dia mantém nota fiscal/observação; pontuação unificada (ano corrente, nunca negativa) entre lista e detalhe; matriz de seleção não polui mais os registros de monitoramento
- Excluir pergunta já respondida passa a desativá-la (antes apagava o histórico de respostas em cascata)
- Segurança: XSS armazenado nas perguntas/observações do monitoramento, remoção de avaliações sem checar permissão, upload de documentos sem validação de tipo/tamanho, nome de arquivo do Excel sem sanitização
- Campos vazios exibiam "None"; arquivos de documentos removidos ficavam órfãos

### ✨ Adicionado (Módulo de Fornecedores)
- Validação/normalização de CNPJ (dígitos verificadores e duplicidade) e UF; paginação e consultas otimizadas na lista
- Alertas de documentos vencidos/a vencer (detalhe e hub); exibição da última matriz de seleção no detalhe
- Testes automatizados do módulo

---

## [1.1.0] - 2026-08-27

### ✨ Adicionado
- Sistema automático de sincronização do changelog no processo de build
- Preenchimento de tabela de Principais Itens com NCs/OMs na aba Resultados do checklist

### 🐛 Corrigido
- Correção de duplicação triplicada de perguntas na avaliação de auditoria
- Correção na detecção completa de NCs no checklist e preservação de grafia do auditor

---

## [1.0.0] - 2026-08-19

### ✨ Adicionado
- Sistema integrado de gestão metrológica (CalibraWeb)
- Módulo de Calibração e Instrumentos (metrologia)
- Módulo de Recursos Humanos (rh)
- Módulo de Procedimentos, Treinamentos e Cotações (procedures)
- Dashboard principal com estatísticas
- Autenticação de usuários com roles e permissões
- Integração com AWS S3 para armazenamento de arquivos
- Sistema de cache com Redis
- Processamento assíncrono com Celery
- Deploy automático na Vercel
- Banco de dados PostgreSQL (Neon)

### 🎨 Interface
- Design responsivo com Bootstrap 5
- Templates reutilizáveis
- Sistema de navegação intuitivo

### 🔧 Infraestrutura
- Configuração para Vercel + Neon + Redis
- Variáveis de ambiente seguras
- Arquivo vercel.json para CI/CD automático

### 🧪 Qualidade
- Testes iniciais com pytest
- Linting com flake8 e black
- Checklist pré-deploy

---

## Guia de Uso

### Para Desenvolvedores

Ao fazer alterações no projeto, siga estes passos:

1. **Edite este arquivo** antes de fazer o commit
2. **Adicione sua mudança** na seção correspondente:
   - `✨ Adicionado` - para novas funcionalidades
   - `🔄 Alterado` - para mudanças em funcionalidades existentes
   - `🐛 Corrigido` - para bugs corrigidos
   - `🗑️ Removido` - para funcionalidades removidas
   - `⚠️ Descontinuado` - para funcionalidades que serão removidas
   - `🔒 Segurança` - para correções de segurança

3. **Use versionamento semântico**:
   - **MAJOR** (ex: 2.0.0) - mudanças incompatíveis
   - **MINOR** (ex: 1.1.0) - novas funcionalidades compatíveis
   - **PATCH** (ex: 1.0.1) - correções de bugs

4. **Exemplo de entrada**:
   ```markdown
   ### ✨ Adicionado
   - Nova funcionalidade X que faz Y
   - Integração com serviço Z
   
   ### 🐛 Corrigido
   - Erro ao salvar dados em procedimentos
   - Validação de formulário em treinamentos
   ```

### Para Usuários Finais

Verifique o CHANGELOG para ver:
- Quando novas funcionalidades estarão disponíveis
- O que foi corrigido na última versão
- O que mudou que possa afetar seu uso do sistema

---

## Versão Atual
- **Última Atualização**: 19 de Agosto de 2026
- **Versão**: 1.0.0
- **Status**: ✅ Em Produção

---

## Links Relacionados
- 🌐 [CalibraWeb Online](https://calibra-web.vercel.app)
- 📚 [Documentação](docs/README.md)
- 🐛 [Issues & Bugs](https://github.com/vmotasilva/CalibraWeb/issues)
- 🔀 [Pull Requests](https://github.com/vmotasilva/CalibraWeb/pulls)

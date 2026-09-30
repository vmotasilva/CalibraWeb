# Revisão do escopo de permissões por tela — todos os módulos

Data: 30/09/2026 · Base: `shared/permissions.py` (`NAV_STRUCTURE`), `core/models.py` (`NavigationPermission`), navbar (`shared/templates/base_desktop.html`), painel `rh/usuarios/<id>/` e inventário das 875 rotas do projeto (`get_resolver()`).

Legenda: ✅ permissão já existe · 🆕 permissão nova · ♻️ reaproveita permissão existente · ⚠️ problema encontrado

---

## 1. Padrão adotado (referência: Metrologia)

```
Módulo  (nav_mod_*)            → "No menu": chave mestra do módulo
 └─ Bloco = 1 tela do menu     → "Exibir bloco": permissão PRÓPRIA do bloco
     └─ Funções = ações da tela → uma permissão por ação (ver, criar, editar, excluir, importar, exportar…)
 └─ Bloco "PERMISSÕES ESPECIAIS" → regras que alteram ESCOPO de dados ou sobrepõem regras de dono/hierarquia
```

Regras que a revisão aplica a todos os módulos:

1. **Um bloco por item de menu.** Sub-telas (detalhe, formulário) e APIs AJAX da tela ficam dentro do bloco da tela que as chama.
2. **O bloco tem permissão exclusiva.** Não pode reutilizar a permissão de uma função (hoje o painel envia a *união* dos checkboxes com o mesmo codename, então desligar um deles não surte efeito).
3. **Ver ≠ escrever.** A permissão de listagem não pode liberar criação, edição ou gravação via API.
4. **Ações destrutivas e em massa têm permissão própria.**
5. **APIs somente-leitura de apoio** (autocomplete, filtros, combos) ficam **sem mapeamento**: várias são chamadas por telas de outros módulos, e prendê-las a uma tela quebraria essas telas quando a validação no servidor for ligada.
6. **Links públicos por token** (portal CAPA, avaliação do auditor, calendário público) ficam de fora de propósito, e isso fica documentado.

---

## 2. Achados críticos (transversais)

### 2.1 ⚠️ As permissões não são validadas no servidor (o mais grave)

- O middleware ativo é `shared/middleware/module_access.py` (o pacote `shared/middleware/` tem precedência sobre `shared/middleware.py`, que é código morto).
- `PUBLIC_URLS` contém `'/'` e a checagem é `request.path.startswith(url)`. **Toda URL começa com `/`**, então o middleware sai antes de verificar qualquer coisa.
- Esse middleware também não chama `has_view_access` (só a versão morta chama).
- Resultado: um usuário sem permissão acessa a tela digitando a URL. As permissões hoje **só escondem itens do menu**, exceto nas poucas views que checam por conta própria:

| App | Rotas | Mapeadas em `nav_*` | Com checagem própria no código | Sem mapeamento |
|---|---:|---:|---:|---:|
| auditoria | 141 | 104 | 2 | 37 |
| procedures + training | 214 | 108 | 5 | 106 |
| metrologia + qms + dashboard | 121 | 67 | 0 | 54 |
| rh | 71 | 33 | 16 | 38 |
| laboratorio + maquinas | 57 | 34 | 3 | 23 |
| boards | 35 | 5 | 1 | 30 |
| fornecedores | 23 | 18 | 0 | 5 |

- Além disso, as URLs de Metrologia na raiz (`/instrumento/...`, `/api/metrologia/...`, `/dashboard/`) e `/training/`, `/boards/`, `/imports/` nem entram no `URL_TO_MODULE_MAPPING` por prefixo.

**Recomendação:** trocar o prefixo pelo `view_name` resolvido (o `VIEW_NAME_TO_PERMISSION` já sabe o módulo de cada view), corrigir `'/'` para comparação exata e implantar em 2 etapas: **modo auditoria** (só registra em log quem seria bloqueado) → **modo bloqueio**. Ligar o bloqueio direto derrubaria acessos de hoje, porque muitos usuários só têm o "No menu" marcado.

### 2.2 ⚠️ Permissões que aparecem no painel mas não existem no banco

Estão no `NAV_STRUCTURE`, mas faltam em `NavigationPermission.Meta.permissions` e em qualquer migration (confirmado no `db.sqlite3` local: 0 linhas). O toggle aparece, mas **não grava nada**:

- `core.nav_metrologia_templates_etiquetas` (Metrologia › Modelos de Etiquetas)
- `core.nav_auditoria_excluir_registro` (Auditoria › Excluir Registro)
- `core.nav_treinamentos_templates_config` (Treinamentos › Configuração de Templates)

(`nav_pessoas_ver_todos_colaboradores` também não está no `Meta`, mas é criada pela migration 0011, então funciona.)

### 2.3 ⚠️ Bloco e função com a mesma permissão

| Onde | Permissão compartilhada |
|---|---|
| Metrologia › Históricos de Calibração | bloco = função `nav_metrologia_historicos_calibracao` |
| Metrologia › Categorias | bloco = função `nav_metrologia_categorias` |
| Metrologia › Unidades de Medida | bloco = função `nav_metrologia_unidades_medida` |
| Metrologia › Modelos de Etiquetas | bloco = função **Exportar Etiquetas** `nav_metrologia_export_etiquetas` |
| Auditoria › AÇÕES | bloco = bloco OPERAÇÃO `nav_auditoria_operacao` |
| Usuários › GESTÃO | bloco = módulo `nav_mod_usuarios` |

Além desses, várias funções diferentes usam a mesma permissão, e com isso "ver" libera "escrever":
- Treinamentos: `nav_treinamentos_registros` cobre a listagem **e** o registro de Avaliação de Eficácia (inclusive em massa).
- Treinamentos: `nav_treinamentos_planejamento` cobre listar **e** criar.
- Treinamentos: `nav_treinamentos_matrizes`, `disciplinas` e `perfis` cobrem listar **e** editar.
- Treinamentos: `nav_treinamentos_avaliacoes` cobre ver **e** salvar avaliação (API).
- Pessoas: `nav_pessoas_horas_extras_list` cobre listar, criar, editar **e** excluir.
- Laboratório/Coating: Painel, Tratamentos, Turnos e Equipe cobrem CRUD completo com 1 permissão.

### 2.4 ⚠️ "Exibir bloco" não esconde bloco nenhum

`can_nav_block` devolve `True` sempre que o flag do módulo está ligado. Na prática, o toggle do bloco só serve de trava no salvamento: funções de bloco desligado são descartadas. Além disso, o navbar ainda consulta `can_nav_block user 'metrologia' 'gestao'`, e essa chave foi renomeada para `instrumentos`.

### 2.5 ⚠️ Mapeamentos mortos e sobras

- View names mapeados que não existem: `boards:create_board`, `criar_colaborador`, `novo_colaborador`, `laboratorio:tratamento_delete`, `laboratorio:regra_turno_delete`, `exibir_botoes_acoes`.
- 67 permissões `nav_acoes_*` + `nav_mod_acoes` + `nav_metrologia_importacao` definidas sem uso (o app Ações Corretivas não existe mais no repositório).
- Treinamentos tem dois itens chamados "Importar Lista de Presença" com permissões diferentes (`treinamentos_importar` importa **treinamentos**).

### 2.6 ⚠️ Segurança (fora do escopo de permissões, mas urgente)

- `/api/migrate/` (`config/urls.py`) rodava `migrate` **sem autenticação nenhuma**. ✅ Corrigido na fase 1.
- `/procedures/api/debug-disciplina/` tem nome de debug, mas exige login e é usado pelo formulário de planejamento. Fica como está.

---

## 3. Permissões especiais — precisam de seção própria?

**Sim.** Elas não liberam uma tela. Elas mudam *quais registros* o usuário enxerga ou permitem passar por cima de regras de dono ou hierarquia. Hoje ficam misturadas com funções comuns (ex.: "Ver Todos os Colaboradores" é uma linha dentro de EQUIPE). Isso traz três problemas:

1. O efeito real não fica visível para quem concede. `nav_pessoas_ver_todos_colaboradores` vale para o **sistema inteiro**: Pessoas (lista, detalhe e salário), Inbox/Notificações (`_is_global_viewer`) e Auditoria (`_auditoria_is_admin` → edita modelos de qualquer responsável).
2. Ela é descartada ao salvar se o bloco EQUIPE estiver desligado, mesmo tendo efeito em outros módulos.
3. Boa parte das regras especiais nem aparece no painel, porque está fixa no código (tabela abaixo).

### 3.1 Inventário

| Regra | Onde | Como é hoje | Proposta |
|---|---|---|---|
| Ver todos os colaboradores | Pessoas, Inbox, Notificações, Auditoria | `nav_pessoas_ver_todos_colaboradores` ✅ | Mover para a seção **Global** (codename mantido) e separar a parte de Auditoria em 🆕 `nav_auditoria_admin` |
| Registrar férias de qualquer colaborador | Pessoas › Férias | `nav_pessoas_registrar_ferias_todos` ✅ | Especiais de Pessoas |
| Ver todos na tratativa de ponto | Pessoas › Ponto | `nav_pessoas_ponto_ver_todos` ✅ | Especiais de Pessoas |
| Exibir botões de ações em tabelas | Global | `nav_global_action_buttons` ✅ (dentro de Usuários) | Seção **Global** |
| Tratar como RH/DP/Qualidade | Férias, Ocorrências | fixo: nome do setor contém "RH", "DP" ou "QUALIDADE" (`_is_admin_setor`) | 🆕 `nav_pessoas_perfil_rh` (manter a regra do setor como fallback na transição) |
| Ver salário | Pessoas (lista e detalhe) | fixo: cargo GERENTE/DIRETOR, setor RH/DP, staff. ⚠️ **A lista e o detalhe usam regras diferentes** | 🆕 `nav_pessoas_ver_salario` |
| Registrar/editar/excluir/ver ocorrência (RH) | Pessoas › Ocorrências | perms de modelo `rh.add/change/delete/view_ocorrencia` (não aparecem no painel) | substituir por `nav_*` |
| Configurar meses de abono/13º; ver férias | Pessoas › Férias | `rh.change_ferias` / `rh.view_ferias` / staff | 🆕 `nav_pessoas_ferias_configuracao` |
| Encerrar ocorrência de outro usuário | Laboratório | fixo: criador ou staff | 🆕 `nav_laboratorio_encerrar_qualquer_ocorrencia` |
| Recalcular turnos de todos os lotes | Coating | fixo: staff | 🆕 `nav_laboratorio_coating_recalcular_todos` |
| Ver/alterar qualquer quadro (colunas, etiquetas, arquivar, PDF) | Quadros | fixo: superuser; os demais só nos quadros de que são criador ou membro | 🆕 `nav_boards_gerenciar_todos` |
| Validar/aprovar matrizes de competência | Treinamentos | fixo: superuser | 🆕 `nav_treinamentos_validar_matriz` |
| Excluir avaliação do auditor | Auditoria ISO | fixo: superuser | 🆕 `nav_auditoria_iso_avaliacao_excluir` |
| Restaurar perguntas-padrão globais | Auditoria ISO | sem checagem | Fase 4: criar a permissão exige passar a restringir quem hoje tem acesso |
| Gestão de usuários/permissões/2FA | Usuários | fixo: superuser/staff | **Manter fixo** (delegar isso é escalada de privilégio); documentar |

### 3.2 Como apresentar no painel

- **Por módulo:** um bloco final `PERMISSÕES ESPECIAIS` (chave `especiais`, atributo `"especial": True`) com visual de alerta, texto "Conceder" no lugar de "Acessar" e uma **descrição do efeito** em cada linha (novo campo `"descricao"` no `NAV_STRUCTURE`).
- **Global:** um card próprio "Permissões Globais", sem o toggle "No menu" (`module_perm = None`; o salvamento já ignora módulo sem permissão), para as regras que valem para vários módulos.

---

## 4. Proposta por módulo (bloco = tela)

> Em cada bloco, a 1ª função é a permissão de **visualizar** a tela. As APIs de leitura listadas entre parênteses herdam essa permissão.

### 4.1 Metrologia (ajustes no módulo de referência)

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Dashboard Metrologia | ✅ `visao_geral` | ✅ Dashboard (+ `api_dashboard_overview`, `api_instrumentos_vencendo`) · 🆕 Estatísticas de Calibração `estatisticas` (`qms:estatisticas_calibracao`) · ♻️ Exportar Estatísticas (movida de Instrumentos) · 🆕 Relatório de Vencidos `relatorio_vencidos` |
| Lista de Instrumentos | ✅ `gestao` | ✅ Lista (+ `qms:listar_instrumentos`, `qms:modulo_metrologia`, `api_faixa_medicao`) · ✅ Novo · ✅ Detalhe (+ `listar_substitucoes`) · ✅ Editar (+ `copiar_faixas_padrao`) · 🆕 Substituir Instrumento `substituir_instrumento` (hoje embutido em Editar) · 🆕 Atualizar Datas em Massa `atualizar_datas_massa` · ✅ Exportar · ✅ Importar (+ `dl_template_instr`) · ✅ Jobs de Importação · 🆕 Ocorrências do Instrumento: registrar / editar / encerrar / excluir (`metrologia:*_ocorrencia`) |
| Históricos de Calibração | 🆕 `historicos_bloco` ⚠️ | ✅ Lista · ✅ Registrar · 🆕 Registrar em Massa `registrar_historico_massa` · ✅ Visualizar · ✅ Editar (+ `salvar_edicao_historico_modal`) · ✅ Remover · ✅ Download certificado (+ `preview_certificado`) · 🆕 Aplicar Carimbo `aplicar_carimbo_certificado` · ✅ Remover Carimbo · ✅ Remover Certificado · ✅ Importar (+ `dl_template_historico`) |
| Categorias | 🆕 `categorias_bloco` ⚠️ | ✅ Lista (+ `categoria_detail`, `categorias_api`, `faixas_categoria_api`) · ✅ Nova · ✅ Editar · ✅ Deletar · ✅ Atualizações em Massa (+ `categoria_bulk_update_acao`, hoje sem mapeamento) · ✅ Faixa: nova / editar / deletar · ♻️ Remover Faixa-Instrumento e em Massa (movidas de Instrumentos: rodam em `categoria_detail.html`) · 🆕 Substituir Faixa-Instrumento (e em massa) `faixa_instrumento_replace` · 🆕 Aplicar Faixa a Instrumentos `faixa_categoria_add_to_instrument` · 🆕 Alterar Categoria em Massa `instrumento_bulk_change_category` · ✅ Arquivo Padrão: download / remover · ✅ Importar categorias (`dl_template_categorias`) |
| Unidades de Medida | 🆕 `unidades_bloco` ⚠️ | ✅ Lista (+ `unidade_detail`) · ✅ Nova · ✅ Editar · ✅ Deletar |
| Modelos de Etiquetas | 🆕 `etiquetas_bloco` ⚠️ | ⚠️ **criar** `templates_etiquetas` (Lista + download) · 🆕 Enviar Modelo `template_etiqueta_upload` · 🆕 Ativar/Desativar `template_etiqueta_toggle` · 🆕 Excluir Modelo `template_etiqueta_delete` · ✅ Exportar Etiquetas (+ `export_etiquetas_excel`) |
| Solicitações de Cotação | ✅ `cotacoes` | ✅ Lista (+ `solicitacao_detail`, `solicitacao_itens`, `cotacao_fornecedor_detail`, `atendimento_detail`, `qms:solicitacao_list`) · ✅ Nova · ✅ Editar · ✅ Deletar · 🆕 Alterar Status: concluir / cancelar / reabrir / reativar `solicitacao_status` · ✅ Item: editar / deletar · ✅ Cotação do Fornecedor: nova / editar · ✅ Novo Atendimento · 🆕 Confirmar Atendimento `atendimento_confirmar` · 🆕 Atualizar Atendimento (dados, cotação, data, chegada, rastreio) `atendimento_update` · ♻️ Registrar histórico via atendimento → `registrar_historico` · ♻️ Iniciar substituição → `substituir_instrumento` |

Especiais: nenhuma identificada. Remover o bloco órfão `nav_metrologia_importacao`.

### 4.2 Treinamentos

O bloco atual "GESTÃO DE TREINAMENTOS" tem 35 funções de 6 telas diferentes. Proposta:

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Dashboard | ♻️ `acompanhamento` | ✅ Dashboard (+ `training:dashboard_treinamentos`, `training:dashboard_filtered`, `training:colaboradores_autocomplete`) · ✅ Exportar CSV · 🆕 Gaps de Competência `gaps` (`dashboard_gaps`, `gap_detalhado`, `gaps_por_perfil`) |
| Calendário | 🆕 `calendario_bloco` | ✅ Calendário |
| Registros de Treinamento | ♻️ `gestao` | ✅ Lista (+ `treinamentos_historico`) · ✅ Novo · ✅ Detalhe · ✅ Editar · ✅ Importar Treinamentos (renomear) · ✅ Template · ✅ Exportar |
| Avaliação de Eficácia | 🆕 `eficacia_bloco` | 🆕 Lista `eficacia` (+ `search_options_api`) ⚠️ hoje usa a perm de Registros · 🆕 Registrar `eficacia_registrar` · 🆕 Registrar em Massa `eficacia_registrar_massa` · 🆕 Alterar Gestor em Massa `eficacia_alterar_gestor` · 🆕 Exportar (Excel / FOR.142 / FOR.142 em massa) `eficacia_export` |
| Listas de Presença | 🆕 `listas_presenca_bloco` | ✅ Lista (+ `lista_presenca_detail`, `visualizar_lista_presenca_assinada`) · ✅ Nova · ✅ Editar · ✅ Deletar · ✅ Importar · ✅ Exportar · ✅ PDF · ✅ Template · ✅ Erros de importação · ✅ Upload assinada · ✅ Remover assinada · 🆕 Gerar Lista (`selecionar_template_lista_presenca`, `gerar_lista_presenca_*`, `procedures:gerar_lista_presenca`) `lista_presenca_gerar` · ✅ Upload Template (+ `gerenciar_templates_presenca`) |
| Planejamento | 🆕 `planejamento_bloco` | ✅ Lista (+ `detalhe_planejamento`) · 🆕 Novo `planejamento_create` (+ `selecionar_tipo_planejamento`, `selecionar_matriz`, `gerar_planejamentos_matriz`) ⚠️ hoje = perm da lista · ✅ Editar (+ adicionar procedimento/colaborador, perguntas de auto-avaliação) · 🆕 Alterar Status `planejamento_status` · 🆕 Gerar Registros de Treinamento `planejamento_criar_registros` · ✅ Deletar · ✅ Excluir em Massa · ✅ Exportar (+ FOR.133, FOR.141 Excel/PDF/impressão) · ✅ Remover procedimento · ✅ Remover colaborador |
| Templates de Documentos | 🆕 `templates_bloco` | ⚠️ **criar** `templates_config` (+ `template_config_replace_file`) |
| Fornecedores e Cotações de Treinamento* | 🆕 `fornecedores_bloco` | 🆕 Lista `fornecedores` (+ `detalhe_fornecedor`, `cotacoes_list`, `detalhe_cotacao`) · ✅ Fornecedor: novo / editar · 🆕 Nova Cotação `cotacao_create` · ✅ Editar Cotação · ✅ Orçamento: novo / editar · 🆕 Nova Avaliação `fornecedor_avaliacao_create` |
| Matrizes | ♻️ `matriz` | ✅ Lista (+ `detalhe_matriz`, `matriz_colaboradores_api`, `colaboradores_disponiveis`) · 🆕 Nova `matriz_create` · 🆕 Editar `matriz_edit` ⚠️ hoje = lista · ✅ Deletar · ✅ Exportar · ✅ Importar · ✅ Template · 🆕 Associar Colaboradores `matriz_colaborador_add` · ✅ Remover/Desassociar Colaboradores · 🆕 Solicitar Validação `matriz_solicitar_validacao` |
| Disciplinas | 🆕 `disciplinas_bloco` | ✅ Lista (+ `detalhe_disciplina`, APIs de filtro) · 🆕 Nova `disciplina_create` · 🆕 Editar `disciplina_edit` ⚠️ hoje = lista · ✅ Deletar · 🆕 Adicionar Procedimentos `disciplina_procedimento_add` · ✅ Remover Procedimento |
| Avaliações de Colaboradores | 🆕 `avaliacoes_bloco` | ✅ Matriz de Avaliações (+ `exportar_matriz_excel`, `avaliacoes_colaborador`, `obter_avaliacao_api`) · ✅ Editar/Salvar Avaliação (+ `salvar_avaliacao_api`, `salvar_avaliacao_modal_api`, `salvar_avaliacao_lote_api`, `avaliar_matriz`, `avaliacao_rapida`) ⚠️ hoje salvar = ver |
| Perfis e Grupos | ✅ `perfis_bloco` | ✅ Lista (+ `detalhe_perfil`) · 🆕 Novo `perfil_create` · 🆕 Editar `perfil_edit` ⚠️ hoje = lista · ✅ Deletar / em massa · ✅ Importar perfis / estrutura · ✅ Exportar estrutura / erros · ✅ Templates (upload/remover) · ✅ Grupo e Subgrupo: novo / editar (+ mover) / deletar · ✅ Remover procedimento do subgrupo · 🆕 Adicionar procedimento ao subgrupo `subgrupo_procedimento_add` · 🆕 Pacotes de Integração: salvar/editar/copiar `perfis_integracao` e deletar `perfis_integracao_delete` · 🆕 Adicionar/Associar Colaborador `perfis_colaborador_add` · ✅ Editar colaborador (+ `reatribuir_todos_subgrupos`) · ✅ Remover colaborador / em massa |
| Procedimentos | ✅ `procedimentos_bloco` | ✅ Lista (+ `detalhe_procedimento`, `qms:procedimentos_lista`, `qms:detalhe_procedimento`, APIs de busca) · ✅ Novo · ✅ Editar · ✅ Importar (+ `dl_template_procedimentos`) · ✅ Exportar |
| Matrizes e Sub-áreas | 🆕 `proc_matrizes_bloco` | ✅ Lista · ✅ Importar · ✅ API sub-áreas |
| Perguntas Auto-Avaliação (FOR.141) | 🆕 `perguntas_auto_avaliacao_bloco` | 🆕 Lista/Preview `perguntas_auto_avaliacao` (+ preview Excel/PDF/impressão) ⚠️ hoje o menu usa a perm de Procedimentos · 🆕 Salvar Perguntas `perguntas_auto_avaliacao_edit` (+ `api_cadastrar_pergunta_rapida`) |

\* Telas fora do menu: confirmar se ainda estão em uso antes de criar as permissões.

Especiais de Treinamentos: 🆕 **Validar/Aprovar Matrizes** `validar_matriz` (`validacoes_pendentes`, `validar_matriz`, `validacao_rapida`, hoje só superuser).

### 4.3 Pessoas

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Colaboradores | ♻️ `equipe` | ✅ Lista (+ `api_colaboradores*`, `api_setores`, `api_cargos`, `api_grupos`, `api_lideres`, `api_supervisores`) · ✅ Novo · ✅ Detalhe · ✅ Editar · ✅ Excluir (API) · ✅ Excluir em Massa · ♻️ Importar Pessoas (movida do bloco IMPORTAÇÃO; + `dl_template_colab`, `dl_template_colab_dados`) |
| Gestão de Férias | 🆕 `ferias_bloco` | ✅ Gestão (+ `grid_ferias`, `projecao_mensal_ferias`, `api_ferias_detail`) · ✅ Registrar (+ `criar_ferias_colab`) · ✅ Editar · ✅ Excluir · ✅ Importar (+ `dl_template_ferias`) · ✅ Exportar · 🆕 Aprovar/Alterar Status `ferias_status` (hoje só staff) · 🆕 Vencimentos: criar/excluir `ferias_vencimentos` |
| Lideranças | 🆕 `liderancas_bloco` | ✅ Atualizar Lideranças · ♻️ Importar Hierarquia (movida do bloco IMPORTAÇÃO; + `dl_template_hierarquia`) |
| Ocorrências | 🆕 `ocorrencias_bloco` | ✅ Lista · 🆕 Registrar `registrar_ocorrencia` ⚠️ hoje sem mapeamento · ✅ Editar · ✅ Deletar |
| Horas Extras e Absenteísmo | ✅ `horas_extras` | ✅ Lista · 🆕 Criar `horas_extras_create` · 🆕 Editar `horas_extras_edit` · 🆕 Excluir `horas_extras_delete` ⚠️ hoje tudo = lista · 🆕 Motivos (lista/CRUD + `api_create_motivo`) `horas_extras_motivos` |
| Tratativa de Falhas de Ponto | ✅ `tratativa_ponto_bloco` | sem mudanças (✅ Demandas, ✅ Importar, ✅ Arquivar, ✅ Excluir) |

O bloco IMPORTAÇÃO é extinto, como já foi feito em Metrologia.

**Especiais de Pessoas:** ✅ Registrar Férias de Qualquer Colaborador · ✅ Ver Todos (Ponto) · 🆕 Perfil RH/DP `perfil_rh` · 🆕 Ver Salário `ver_salario` · 🆕 Configurar Abono/13º `ferias_configuracao`. "Ver Todos os Colaboradores" vai para a seção Global (item 3).

### 4.4 Fornecedores

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Lista de Fornecedores | ✅ `gestao` | ✅ Lista/Hub (+ `fornecedor_detail`) · ✅ Novo · ✅ Editar · ✅ Documento: novo / remover (movidos de AVALIAÇÃO: pertencem ao detalhe) |
| Avaliações do Fornecedor | ✅ `avaliacao` | 🆕 Listar Avaliações `avaliacoes` (`avaliacao_list`, `reavaliacao_list`, `api_respostas_avaliacao`) · ✅ Nova · ✅ Editar · ✅ Matriz · ✅ Seleção · ✅ Reavaliação: nova / deletar · ✅ Exportar |
| Perguntas de Avaliação | 🆕 `perguntas_bloco` | ✅ Lista (+ `perguntas_filtradas`) · ✅ Nova · ✅ Editar · ✅ Remover |

Especiais: nenhuma.

### 4.5 Auditoria

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Nova Auditoria | 🆕 `nova_bloco` ⚠️ hoje = OPERAÇÃO | ✅ Selecionar Modelo · ✅ Avaliação de Dados (com e sem modelo) |
| Modelos de Auditoria | ♻️ `cadastro` | ✅ Lista (+ `auditoria:modulo`) · ✅ Novo · ✅ Editar · ✅ Duplicar · ✅ Remover · 🆕 Encerrar/Arquivar `encerrar_modelo` · 🆕 Justificar Não Execução `justificar_nao_execucao` · 🆕 Tópicos/Categorias `modelo_topicos` (`modelo_categorias`, `topico_delete`, `reorder_topicos`, `api_modelo_topicos`) |
| Perguntas por Modelo | 🆕 `perguntas_bloco` | ✅ Lista (+ `api_next_pergunta_ordem`) · ✅ Nova · ✅ Editar · ✅ Duplicar · ✅ Remover · 🆕 Ações em Massa `perguntas_massa` (`bulk_set_topico`, `bulk_apply_resposta`) |
| Registros (Modelos Cadastrados / Período) | ✅ `operacao` | ✅ Lista · ✅ Por Modelo (+ `registros_por_modelo_compartilhado`) · ✅ Detalhe · ✅ Editar (+ `api_atualizar_resposta_inline`) · ⚠️ **criar** `excluir_registro` · ✅ Exportar Excel · 🆕 Exportar PDF `exportar_pdf` · ✅ Comentário: editar / remover |
| Dashboard Auditoria | ✅ `analise` | ✅ Dashboard |
| *Grupo ISO 13485* — Setup: Normas | 🆕 `iso_normas_bloco` | ♻️ `iso_normas` (ver/criar/editar/templates) · 🆕 `iso_normas_delete` (arquivar/excluir) |
| ISO — Setup: Itens da Norma | 🆕 `iso_itens_bloco` | ♻️ `iso_itens` · 🆕 `iso_itens_delete` |
| ISO — Setup: Banco de Perguntas | 🆕 `iso_perguntas_bloco` | ♻️ `iso_perguntas` · 🆕 `iso_perguntas_delete` |
| ISO — Setup: Modelos e Blocos | 🆕 `iso_modelos_bloco` | ♻️ `iso_modelos` · 🆕 `iso_modelos_delete` |
| ISO — Setup: Planejamento e Agendas | ♻️ `iso_setup_bloco` | ✅ Painel de Setup · ♻️ `iso_agendas` (+ `api_iso_auditoria_editar_planejamento`, `iso_agenda_toggle_conclusao`, `iso_auditoria_toggle_conclusao`) · 🆕 `iso_agendas_delete` |
| ISO — Modo Entrevista | ♻️ `iso_bloco` | ✅ Lista · ✅ Execução (+ `api_iso_autosave_resposta`, `api_iso_marcar_nao_aplicavel`, pontos fortes) · 🆕 Solicitações/Evidências `iso_solicitacoes` (CRUD, transferir, imagens, legenda) · ✅ Revisão · ✅ Matriz · ✅ Cronograma · ✅ Síntese · ✅ Fechamento · ✅ Amostras · ✅ CAPA · ✅ Avaliação do Auditor · ✅ Analytics · ✅ Exportar |

Públicos por token (ficam de fora de propósito): `capa_portal_publico`, `api_capa_*_publica`, `avaliacao_portal_publico`, `api_avaliacao_salvar_resposta_publica`.

**Especiais de Auditoria:** 🆕 Administrador de Auditoria `nav_auditoria_admin` (modelos, registros e comentários de qualquer responsável; hoje herdado de "ver todos colaboradores") · 🆕 Excluir Avaliação do Auditor `iso_avaliacao_excluir`.

### 4.6 Laboratório

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Observações Gerais | ♻️ `ocorrencias_gerais` | ✅ Módulo de Observações |
| Ocorrências | 🆕 `ocorrencias_bloco` | ✅ Listagem (+ `ocorrencia_detail`) · ✅ Nova · ✅ Editar · 🆕 Anotações `ocorrencia_anotar` · 🆕 Encerrar `ocorrencia_encerrar` · 🆕 Excluir `ocorrencia_delete` ⚠️ hoje sem mapeamento |
| Categorias de Ocorrência | 🆕 `categorias_bloco` | ✅ Lista · ✅ Nova · ✅ Editar |
| Dashboard Laboratório | 🆕 `dashboard_bloco` | ✅ Dashboard · 🆕 Exportar PDF `dashboard_pdf` |
| Cadastro de Máquinas | ✅ `maquinas` | ✅ Lista/Detalhe · ✅ Nova · ✅ Editar · ✅ Excluir |
| Categorias de Máquinas | 🆕 `maquinas_categorias_bloco` | ✅ Lista · ✅ Nova · ✅ Editar · ✅ Excluir |
| Coating: Painel Diário | ✅ `coating` | ✅ Painel (+ `obter_manutencoes_lote`, `obter_observacoes_lote`, `api_verificar_lote_coating`, `api_analisar_horarios_coating`) · 🆕 Editar Lançamentos `coating_painel_editar` (`atualizar_celula`, `editar_lote_completo`, `api_editar_linha`, `salvar_observacoes_lote`, `registrar_manutencao`, `api_recalcular_turno_registro`) · 🆕 Excluir Registro `coating_registro_delete` |
| Coating: Dashboard | 🆕 `coating_dashboard_bloco` | ✅ Dashboard |
| Coating: Importação | 🆕 `coating_importacao_bloco` | ✅ Importar + modelo |
| Coating: Tratamentos | 🆕 `coating_tratamentos_bloco` | ✅ Lista · 🆕 Novo · 🆕 Editar (remover `tratamento_delete`, que não existe) |
| Coating: Regras de Turno | 🆕 `coating_turnos_bloco` | ✅ Lista · 🆕 Nova · 🆕 Editar (remover `regra_turno_delete`, que não existe) |
| Coating: Ciclos de Manutenção | 🆕 `coating_ciclos_bloco` | ✅ Lista (+ `api_obter_ciclos_maquina`) · 🆕 Novo · ✅ Editar (+ `api_reordenar_ciclos`, `api_toggle_ciclo_ativo`, `configurar_checklist_ciclo`) · 🆕 Copiar Ciclos · 🆕 Excluir |
| Coating: Equipe | 🆕 `coating_equipe_bloco` | ✅ Lista · 🆕 Editar · 🆕 Excluir |

**Especiais de Laboratório:** 🆕 Encerrar Ocorrência de Qualquer Usuário · 🆕 Recalcular Turnos de Todos os Lotes. Remover `laboratorio:run_migrate_view`.

### 4.7 Quadros

A estrutura interna (colunas, cartões, checklist, comentários) é controlada **por quadro**: criador, membros e `todos_colaboradores`. Proposta: manter essa regra por objeto e não criar permissões por usuário para cada ação de cartão.

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Meus Quadros | ✅ `visao_geral` | ✅ Dashboard · ✅ Criar Quadro (corrigir o mapeamento `boards:create_board`, que não existe; a criação acontece no POST do dashboard) |
| Quadro | ✅ `gestao` | ✅ Detalhe (+ `column_focus`) · ✅ Editar · ✅ Arquivar/Desarquivar |

A exclusão de quadro está desativada no código (só arquivar), então não ganha permissão.

**Especiais de Quadros:** 🆕 Gerenciar Todos os Quadros. Público por token: `public_calendar`.

### 4.8 Usuários

| Bloco (tela) | Perm do bloco | Funções |
|---|---|---|
| Lista de Usuários | 🆕 `usuarios_lista_bloco` ⚠️ hoje = módulo | ✅ Lista |

Detalhe, criação, permissões, 2FA, staff/superuser e reset de senha continuam **exclusivos de superuser/staff, fixos no código** (de propósito). "Exibir Botões de Ações" vai para a seção Global.

### 4.9 Seção Global (nova)

| Permissão | Efeito |
|---|---|
| 🆕 `nav_global_visao_colaboradores` (substitui `nav_pessoas_ver_todos_colaboradores`) | Vê todos os colaboradores em Pessoas, Inbox e Notificações |
| ✅ `nav_global_action_buttons` | Exibe as colunas de ações nas tabelas |

---

## 5. Plano de implementação sugerido

| Fase | Conteúdo | Risco |
|---|---|---|
| 1 — Correções | Criar as 3 permissões inexistentes; separar as perms bloco = função; corrigir `'gestao'` no navbar; remover mapeamentos mortos; **proteger `/api/migrate/`** e remover o endpoint de debug | Baixo |
| 2 — Reestruturação | Novo `NAV_STRUCTURE` (seção 4) + blocos Especiais/Global + campo `descricao`; migration criando as novas `nav_*`; **migration de dados que preserva o acesso atual** (quem tinha o bloco antigo ou qualquer função dele recebe o bloco novo; cada função nova vai para quem tinha a perm que cobria aquela view antes); limpeza das `nav_acoes_*` | Médio |
| 3 — Validação no servidor | Middleware por `view_name` em modo auditoria (log) → modo bloqueio; esconder botões nos templates com `can_nav_view` | Alto (muda o comportamento) |
| 4 — Regras fixas → permissões | Converter `_is_admin_setor`, as regras de salário, `rh.*_ocorrencia` e as checagens `is_superuser` da seção 3 em permissões especiais, mantendo a regra antiga como fallback durante a transição | Médio |

---

## 6. Status da implementação — fases 1 e 2 (30/09/2026)

**Concluído**

- `shared/permissions.py`: novo `NAV_STRUCTURE` com 1 bloco por tela em todos os módulos, bloco `PERMISSÕES ESPECIAIS` (sem toggle de bloco, com `descricao`) e o card **Permissões Globais** (`module_perm = None`).
- `core/models.py`: `NavigationPermission.Meta.permissions` regenerado a partir da estrutura (inclui as 3 permissões que não existiam no banco).
- `core/migrations/0028` (opções do modelo) e `0029` (dados):
  - cria as 129 permissões novas;
  - **preserva o acesso atual**: cada permissão nova vai para quem tinha a permissão que cobria aquela view/ação antes (84 regras). Depois, cada bloco vai para quem tem alguma função dele;
  - remove as órfãs `nav_acoes_*`, `nav_mod_acoes`, `nav_metrologia_importacao` e `nav_pessoas_importacao`.
- Painel `rh/usuarios/<id>/`: seção especial destacada, com descrição e botão "Conceder"; card Global sem "No menu".
- Permissões especiais já funcionando no código (sempre somando à regra antiga, que continua valendo como fallback):
  - Pessoas: `perfil_rh`, `ver_salario`, `ferias_configuracao`, e a função `ferias_status`;
  - Treinamentos: `validar_matriz`;
  - Auditoria: `admin` (substitui "ver todos os colaboradores" no `_auditoria_is_admin`) e `iso_avaliacao_excluir`;
  - Laboratório: `encerrar_qualquer_ocorrencia` e `coating_recalcular_todos`;
  - Quadros: `gerenciar_todos`.
- Navbar desktop/mobile: chaves de bloco corrigidas e o item "Perguntas Auto-Avaliação" com permissão própria.
- "Exibir Botões de Ações" não depende mais do módulo Usuários.
- `/api/migrate/` passa a exigir `POST` com `Authorization: Bearer <MIGRATE_SECRET>` (ou `CRON_SECRET`).
- Testes: `core/test_nav_permissoes.py`.

**Permissões novas que começam desligadas para todos** (não havia regra anterior equivalente): todas as especiais; `nav_auditoria_excluir_registro` e `nav_treinamentos_templates_config` (antes não existiam no banco); `nav_pessoas_ferias_status`.

**Pendente:** fase 3 (validação no servidor) e fase 4 (conversão das demais regras fixas).

"""shared.permissions

Sistema de permissões de navegação e acesso por módulo.

Histórico:
- Existia um controle por *grupos* (Group) para liberar um módulo inteiro.
- Agora o controle principal passa a ser por permissões `core.nav_*`, estruturadas como:
    Módulo -> Blocos -> Funções.

Compatibilidade:
- Se o usuário ainda estiver usando grupos legados, o acesso continua funcionando.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# Definição dos módulos e suas permissões
MODULES_PERMISSIONS = {
    'boards': {
        'name': 'Quadros de Atividades',
        'permissions': [
            'add_board',
            'change_board',
            'delete_board',
            'view_board',
        ]
    },
    'metrologia': {
        'name': 'Metrologia - Calibração de Instrumentos',
        'permissions': [
            'add_instrumento',
            'change_instrumento',
            'delete_instrumento',
            'view_instrumento',
            'add_historicocalibracao',
            'change_historicocalibracao',
            'delete_historicocalibracao',
            'view_historicocalibracao',
            'add_solicitacaocotacao',
            'change_solicitacaocotacao',
            'delete_solicitacaocotacao',
            'view_solicitacaocotacao',
        ]
    },
    'rh': {
        'name': 'Recursos Humanos',
        'permissions': [
            'add_colaborador',
            'change_colaborador',
            'delete_colaborador',
            'view_colaborador',
            'add_ocorrencia',
            'change_ocorrencia',
            'delete_ocorrencia',
            'view_ocorrencia',
            'add_planejamentohoraextra',
            'change_planejamentohoraextra',
            'delete_planejamentohoraextra',
            'view_planejamentohoraextra',
        ]
    },
    'procurements': {
        'name': 'Procurement / Compras',
        'permissions': [
            'add_solicitacaoinstrumento',
            'change_solicitacaoinstrumento',
            'delete_solicitacaoinstrumento',
            'view_solicitacaoinstrumento',
        ]
    },
    'organization': {
        'name': 'Organização',
        'permissions': [
            'add_setor',
            'change_setor',
            'delete_setor',
            'view_setor',
        ]
    },
    'auditoria': {
        'name': 'Auditoria',
        'permissions': [
            'add_modeloauditoria',
            'change_modeloauditoria',
            'delete_modeloauditoria',
            'view_modeloauditoria',
            'add_perguntaauditoria',
            'change_perguntaauditoria',
            'delete_perguntaauditoria',
            'view_perguntaauditoria',
            'add_registroauditoria',
            'change_registroauditoria',
            'delete_registroauditoria',
            'view_registroauditoria',
            'add_respostaauditoria',
            'change_respostaauditoria',
            'delete_respostaauditoria',
            'view_respostaauditoria',
        ]
    },
    'laboratorio': {
        'name': 'Laboratorio',
        'permissions': [
            'add_categorialaboratorio',
            'change_categorialaboratorio',
            'delete_categorialaboratorio',
            'view_categorialaboratorio',
            'add_ocorrencialaboratorio',
            'change_ocorrencialaboratorio',
            'delete_ocorrencialaboratorio',
            'view_ocorrencialaboratorio',
        ]
    },
    'procedures': {
        'name': 'Procedimentos / Treinamentos',
        'permissions': []
    },
    'fornecedores': {
        'name': 'Fornecedores',
        'permissions': []
    },
    'acoes': {
        'name': 'Ações Corretivas',
        'permissions': []
    },
}


# ============================================================================== 
# NOVA ESTRUTURA: MÓDULO -> BLOCOS -> FUNÇÕES
# ============================================================================== 

# Observação: view_name deve bater com o que o Django resolve (namespace:name).
#
# Padrão (referência: Metrologia):
# - Módulo (module_perm)   -> "No menu": chave mestra do módulo.
# - Bloco = 1 tela do menu -> "Exibir bloco": permissão PRÓPRIA do bloco (nunca reutiliza a de uma função).
# - Funções = ações da tela (ver, criar, editar, excluir, importar, exportar...), uma permissão por ação.
# - Bloco "especial": True -> PERMISSÕES ESPECIAIS: alteram o escopo de dados ou sobrepõem regras de
#   dono/hierarquia. Não têm toggle de bloco (perm None) e cada item traz "descricao" do efeito.
# - Módulo com module_perm None (Permissões Globais) -> regras transversais, sem toggle "No menu".
#
# APIs somente-leitura de apoio (autocomplete, filtros, combos) e links públicos por token ficam
# de fora de propósito: herdam o acesso do módulo.
NAV_STRUCTURE = [
    {
        "key": "boards",
        "nome": "Quadros",
        "cor": "danger",
        "icone": "bi bi-kanban",
        "module_perm": "core.nav_mod_boards",
        "blocos": [
            {
                "key": "visao_geral",
                "nome": "Meus Quadros",
                "perm": "core.nav_boards_visao_geral",
                "funcoes": [
                    {"nome": "Acessar Dashboard", "view_name": "boards:dashboard", "perm": "core.nav_boards_dashboard"},
                    # A criação acontece no POST do dashboard (checada em boards.views).
                    {"nome": "Criar Quadro", "perm": "core.nav_boards_create"},
                ]
            },
            {
                "key": "gestao",
                "nome": "Quadro",
                "perm": "core.nav_boards_gestao",
                "funcoes": [
                    {"nome": "Detalhe de Quadro", "view_name": ["boards:board_detail", "boards:column_focus"], "perm": "core.nav_boards_detail"},
                    {"nome": "Editar Quadro", "view_name": "boards:edit_board", "perm": "core.nav_boards_edit"},
                    {"nome": "Arquivar Quadro", "view_name": ["boards:archive_board", "boards:unarchive_board"], "perm": "core.nav_boards_archive"},
                ]
            },
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Gerenciar Todos os Quadros",
                        "perm": "core.nav_boards_gerenciar_todos",
                        "descricao": "Vê e altera qualquer quadro (colunas, etiquetas, arquivamento e exportação), mesmo sem ser criador ou membro.",
                    },
                ],
            },
        ]
    },
    {
        "key": "diagramas",
        "nome": "Diagramas",
        "cor": "dark",
        "icone": "bi bi-diagram-3-fill",
        "module_perm": "core.nav_mod_diagramas",
        "blocos": [
            {
                "key": "fluxogramas",
                "nome": "Fluxogramas de Processos",
                "perm": "core.nav_diagramas_fluxos_bloco",
                "funcoes": [
                    {
                        "nome": "Listar Fluxogramas",
                        "view_name": "procedures:diagramas_lista",
                        "perm": "core.nav_diagramas_lista",
                        "descricao": "Acessa a listagem geral de diagramas e fluxogramas cadastrados.",
                    },
                    {
                        "nome": "Novo Fluxograma",
                        "view_name": "procedures:diagrama_novo",
                        "perm": "core.nav_diagramas_novo",
                        "descricao": "Cria um novo fluxograma com código documental e versão inicial.",
                    },
                    {
                        "nome": "Editor de Fluxograma (Canvas / Grelha)",
                        "view_name": "procedures:diagrama_editor",
                        "perm": "core.nav_diagramas_editor",
                        "descricao": "Edita a topologia, raias, nós e conexões nos modos Canvas e Grelha.",
                    },
                    {
                        "nome": "Cadastro e Mapeamento de Raias",
                        "view_name": "procedures:diagramas_raias",
                        "perm": "core.nav_diagramas_raias",
                        "descricao": "Cadastra o catálogo de raias (cor, ordem e vínculo com o setor do RH) usado nos diagramas.",
                    },
                    {
                        "nome": "Exportar PDF do Diagrama",
                        "view_name": "procedures:api_diagrama_versao_exportar_pdf",
                        "perm": "core.nav_diagramas_export_pdf",
                        "descricao": "Gera e faz download do documento oficial controlado do diagrama em PDF.",
                    },
                ],
            },
            {
                "key": "qms_workflow",
                "nome": "Governança QMS e Aprovação",
                "perm": "core.nav_diagramas_qms_bloco",
                "funcoes": [
                    {
                        "nome": "Submeter para Aprovação",
                        "view_name": "procedures:api_diagrama_versao_submeter",
                        "perm": "core.nav_diagramas_submeter",
                        "descricao": "Submete uma revisão em rascunho para aprovação da Qualidade.",
                    },
                    {
                        "nome": "Aprovar Fluxograma (ISO 13485)",
                        "view_name": "procedures:api_diagrama_versao_aprovar",
                        "perm": "core.nav_diagramas_aprovar",
                        "descricao": "Aprova formalmente a versão, tornando o documento imutável.",
                    },
                    {
                        "nome": "Criar Nova Revisão (R01...)",
                        "view_name": "procedures:api_diagrama_versao_criar_nova_revisao",
                        "perm": "core.nav_diagramas_nova_revisao",
                        "descricao": "Clona uma versão aprovada e inicia nova revisão em Rascunho com justificativa.",
                    },
                ],
            },
        ],
    },
    {
        "key": "kpi",
        "nome": "KPI",
        "cor": "danger",
        "icone": "bi bi-speedometer2",
        # Módulo exibido só dentro de Gestão > KPI: a flag do módulo é a própria chave do grupo.
        "module_perm": "core.nav_gestao_kpi",
        "blocos": [
            {
                "key": "painel",
                "grupo": "KPI",
                "nome": "Painel de Indicadores",
                "perm": "core.nav_kpi_bloco_painel",
                "funcoes": [
                    {"nome": "Ver Painel de Indicadores", "view_name": ["kpi:painel", "kpi:analise_dados"], "perm": "core.nav_kpi_painel"},
                    {
                        "nome": "Registrar Causas e Análises",
                        "view_name": ["kpi:analise_salvar", "kpi:analise_salvar_massa"],
                        "perm": "core.nav_kpi_analise",
                        "descricao": "Registra a causa e a análise dos períodos fora da meta (dia, semana e mês) e remove os registros existentes.",
                    },
                    {
                        "nome": "Dispensar Períodos da Análise",
                        "view_name": ["kpi:analise_dispensar", "kpi:analise_dispensar_massa"],
                        "perm": "core.nav_kpi_analise_dispensar",
                        "descricao": "Autorização especial: marca períodos fora da meta como dispensados de causa e análise (deixam de ser cobrados e de aparecer como pendentes) e reativa os dispensados.",
                    },
                    {"nome": "Lançar Valores e Motivos", "view_name": ["kpi:medicao_salvar", "kpi:motivo_salvar"], "perm": "core.nav_kpi_lancar"},
                    {"nome": "Excluir Lançamento", "view_name": "kpi:medicao_excluir", "perm": "core.nav_kpi_lancamento_excluir"},
                ],
            },
            {
                "key": "importacao",
                "grupo": "KPI",
                "nome": "Importação de Planilhas",
                "perm": "core.nav_kpi_bloco_importacao",
                "funcoes": [
                    {"nome": "Importar Valores e Tabelas", "view_name": ["kpi:importar", "kpi:modelo_importacao"], "perm": "core.nav_kpi_importar"},
                    {
                        "nome": "Registro por Colagem",
                        "view_name": ["kpi:colagem", "kpi:colagem_modelos", "kpi:colagem_modelo_novo", "kpi:colagem_modelo_editar", "kpi:colagem_modelo_excluir", "kpi:colagem_historico", "kpi:colagem_historico_detalhe", "kpi:colagem_desfazer"],
                        "perm": "core.nav_kpi_colagem",
                        "descricao": "Cola uma lista de números e distribui nas variáveis dos indicadores conforme o modelo; também cria e edita os modelos de colagem.",
                    },
                ],
            },
            {
                "key": "indicadores",
                "grupo": "KPI",
                "nome": "Cadastro de Indicadores",
                "perm": "core.nav_kpi_bloco_indicadores",
                "funcoes": [
                    {"nome": "Listar e Detalhar Indicadores", "view_name": ["kpi:indicadores", "kpi:indicador_detalhe"], "perm": "core.nav_kpi_indicadores"},
                    {"nome": "Criar e Editar Indicador", "view_name": ["kpi:indicador_novo", "kpi:indicador_editar", "kpi:indicador_mover"], "perm": "core.nav_kpi_indicador_editar"},
                    {"nome": "Excluir Indicador", "view_name": "kpi:indicador_excluir", "perm": "core.nav_kpi_indicador_excluir"},
                ],
            },
        ],
    },
    {
        "key": "pcp",
        "nome": "PCP",
        "cor": "primary",
        "icone": "bi bi-clipboard2-check",
        # Módulo exibido só dentro de Gestão > Processos > PCP: a flag do módulo é a própria chave do grupo.
        "module_perm": "core.nav_gestao_pcp",
        "blocos": [
            {
                "key": "preenchimento",
                "grupo": "Processos > PCP",
                "nome": "Preenchimento e Ocorrências",
                "perm": "core.nav_pcp_bloco_preenchimento",
                "funcoes": [
                    {
                        "nome": "Preencher Verificações",
                        "view_name": ["pcp:preencher", "pcp:preencher_pagina", "pcp:preencher_salvar", "pcp:preencher_item", "pcp:ocorrencia_registrar", "pcp:preencher_status"],
                        "perm": "core.nav_pcp_preencher",
                        "descricao": "Lança os resultados das verificações por página, data e turno, e registra observações e ocorrências.",
                    },
                    {
                        "nome": "Ver Pendências, Atrasos, Dashboard e Visão Semanal",
                        "view_name": ["pcp:pendencias", "pcp:atrasos", "pcp:atrasos_pagina", "pcp:dashboard", "pcp:semana"],
                        "perm": "core.nav_pcp_pendencias",
                        "descricao": "Mostra, por página e turno, as verificações devidas conforme a frequência e quais estão pendentes, e os atrasos do período (prazos encerrados sem resposta).",
                    },
                    {
                        "nome": "Exportar Planilha de Registros",
                        "view_name": ["pcp:exportar_pagina", "pcp:exportar_formulario", "pcp:exportar_dados_pagina", "pcp:exportar_dados_formulario", "pcp:exportar_template", "pcp:exportar_template_formulario"],
                        "perm": "core.nav_pcp_exportar",
                        "descricao": "Gera a planilha do mês (itens x dia/turno). Turnos com a máquina em manutenção ou parada saem com todos os itens preenchidos com a situação.",
                    },
                    {"nome": "Ver Ocorrências", "view_name": "pcp:ocorrencias", "perm": "core.nav_pcp_ocorrencias"},
                    {"nome": "Registrar Tratativa de Ocorrência", "view_name": "pcp:ocorrencia_tratar", "perm": "core.nav_pcp_ocorrencia_tratar"},
                ],
            },
            {
                "key": "formularios",
                "grupo": "Processos > PCP",
                "nome": "Formulários e Revisões",
                "perm": "core.nav_pcp_bloco_formularios",
                "funcoes": [
                    {
                        "nome": "Ver Formulários, Revisões e Páginas",
                        "view_name": ["pcp:formularios", "pcp:formulario_detalhe", "pcp:versao_detalhe", "pcp:pagina_detalhe"],
                        "perm": "core.nav_pcp_formularios",
                    },
                    {
                        "nome": "Criar e Editar Formulários, Páginas e Campos",
                        "view_name": [
                            "pcp:formulario_novo", "pcp:formulario_editar", "pcp:versao_nova",
                            "pcp:pagina_nova", "pcp:pagina_editar", "pcp:pagina_excluir", "pcp:pagina_alternar", "pcp:pagina_desativar",
                            "pcp:versao_grupos", "pcp:grupos", "pcp:grupo_criar", "pcp:grupo_renomear", "pcp:grupo_excluir",
                            "pcp:grupo_mover", "pcp:paginas_acao", "pcp:campo_mover", "pcp:ajustar_tipos", "pcp:sugerir_limites", "pcp:valores", "pcp:vincular_valores", "pcp:ajustes", "pcp:pagina_mover", "pcp:grupo_ordenar", "pcp:campo_alternar",
                            "pcp:campo_novo", "pcp:campo_editar", "pcp:campo_excluir",
                        ],
                        "perm": "core.nav_pcp_formulario_editar",
                        "descricao": "Monta a estrutura do formulário. Só revisões em rascunho são editáveis (na vigente: grupos, ordem e máquina, e desativar/excluir blocos e itens sem histórico); mudanças na estrutura nascem como nova revisão.",
                    },
                    {
                        "nome": "Importar Estrutura (planilha de formulário)",
                        "view_name": "pcp:importar",
                        "perm": "core.nav_pcp_importar",
                        "descricao": "Cria uma nova revisão (rascunho) a partir da estrutura de uma planilha .xlsx no padrão dos formulários de PCP. Não importa lançamentos.",
                    },
                    {
                        "nome": "Importar Registros já Feitos (planilha)",
                        "view_name": "pcp:importar_registros",
                        "perm": "core.nav_pcp_importar_registros",
                        "descricao": "Importa os lançamentos por data e turno de uma planilha para páginas já existentes. Separado da importação da estrutura; não sobrescreve respostas existentes.",
                    },
                    {
                        "nome": "Gerenciar Templates de Página",
                        "view_name": ["pcp:templates_pagina", "pcp:template_pagina_amostra", "pcp:template_pagina_baixar",
                                      "pcp:template_pagina_excluir", "pcp:template_pagina_alternar"],
                        "perm": "core.nav_pcp_templates",
                        "descricao": "Cadastra planilhas (.xlsx) com variáveis de marcação para extrair o PCP de uma página no layout desejado; baixa o modelo de exemplo.",
                    },
                    {
                        "nome": "Excluir Formulário",
                        "view_name": "pcp:formulario_excluir",
                        "perm": "core.nav_pcp_formulario_excluir",
                        "descricao": "Apaga o formulário com todas as revisões, páginas e campos (por exemplo, para importar de novo). Com verificações lançadas, exige confirmação digitada e apaga também o histórico.",
                    },
                    {
                        "nome": "Publicar, Excluir e Ajustar Vigência de Revisões",
                        "view_name": ["pcp:versao_publicar", "pcp:versao_excluir", "pcp:versao_vigencia"],
                        "perm": "core.nav_pcp_versao_publicar",
                        "descricao": "Torna uma revisão em rascunho vigente (a anterior fica obsoleta) ou exclui um rascunho.",
                    },
                ],
            },
            {
                "key": "cadastros",
                "grupo": "Processos > PCP",
                "nome": "Cadastros Base",
                "perm": "core.nav_pcp_bloco_cadastros",
                "funcoes": [
                    {"nome": "Turnos", "view_name": ["pcp:turnos", "pcp:turno_novo", "pcp:turno_editar", "pcp:turno_excluir"], "perm": "core.nav_pcp_turnos"},
                    {"nome": "Frequências", "view_name": ["pcp:frequencias", "pcp:frequencia_nova", "pcp:frequencia_editar", "pcp:frequencia_excluir"], "perm": "core.nav_pcp_frequencias"},
                    {"nome": "Listas de Opções", "view_name": ["pcp:listas", "pcp:lista_nova", "pcp:lista_editar", "pcp:lista_excluir"], "perm": "core.nav_pcp_listas"},
                ],
            },
        ],
    },
    {
        "key": "perdas",
        "nome": "Motivos de Perdas",
        "cor": "danger",
        "icone": "bi bi-x-octagon",
        # Módulo exibido só dentro de Gestão > Processos > Motivos de Perdas: a flag do módulo é a própria chave do grupo.
        "module_perm": "core.nav_gestao_motivos_perdas",
        "blocos": [
            {
                "key": "cadastros",
                "grupo": "Processos > Motivos de Perdas",
                "nome": "Cadastro de Motivos",
                "perm": "core.nav_perdas_bloco_cadastros",
                "funcoes": [
                    {"nome": "Ver Motivos de Perdas", "view_name": "kpi:motivos_perdas", "perm": "core.nav_perdas_ver_perda"},
                    {"nome": "Ver Motivos de Retorno", "view_name": "kpi:motivos_retorno", "perm": "core.nav_perdas_ver_retorno"},
                    {
                        "nome": "Cadastrar e Editar Motivos",
                        "view_name": "kpi:motivo_cadastro_salvar",
                        "perm": "core.nav_perdas_editar",
                        "descricao": "Cria e altera motivos de perdas e de retorno (nome, descrição, ordem e situação).",
                    },
                    {"nome": "Excluir Motivos", "view_name": "kpi:motivo_cadastro_excluir", "perm": "core.nav_perdas_excluir"},
                ],
            },
        ],
    },
    {
        "key": "metrologia",
        "nome": "Metrologia",

        "cor": "success",
        "icone": "bi bi-tools",
        "module_perm": "core.nav_mod_metrologia",
        "blocos": [
            {
                "key": "visao_geral",
                "nome": "Dashboard Metrologia",
                "perm": "core.nav_metrologia_visao_geral",
                "funcoes": [
                    {"nome": "Dashboard Metrologia", "view_name": ["dashboard", "metrologia:api_dashboard_overview", "metrologia:api_instrumentos_vencendo"], "perm": "core.nav_metrologia_dashboard"},
                    {"nome": "Estatísticas de Calibração", "view_name": "qms:estatisticas_calibracao", "perm": "core.nav_metrologia_estatisticas"},
                    {"nome": "Exportar Estatísticas", "view_name": "qms:exportar_estatisticas", "perm": "core.nav_metrologia_export_estatisticas"},
                    {"nome": "Relatório de Vencidos", "view_name": "qms:relatorio_vencidos", "perm": "core.nav_metrologia_relatorio_vencidos"},
                ],
            },
            {
                "key": "instrumentos",
                "nome": "Lista de Instrumentos",
                "perm": "core.nav_metrologia_gestao",
                "funcoes": [
                    {"nome": "Lista de Instrumentos", "view_name": ["modulo_metrologia", "qms:modulo_metrologia", "qms:listar_instrumentos"], "perm": "core.nav_metrologia_lista_instrumentos"},
                    {"nome": "Novo Instrumento", "view_name": ["metrologia:novo_instrumento", "novo_instrumento", "qms:novo_instrumento"], "perm": "core.nav_metrologia_novo_instrumento"},
                    {
                        "nome": "Detalhe do Instrumento",
                        "view_name": ["detalhe_instrumento", "visualizar_instrumento", "qms:visualizar_instrumento", "listar_substitucoes", "qms:listar_substitucoes"],
                        "perm": "core.nav_metrologia_detalhe_instrumento",
                    },
                    {
                        "nome": "Editar Instrumento",
                        "view_name": ["editar_instrumento_custom", "qms:editar_instrumento", "gerenciar_faixas_instrumento", "atualizar_datas_calibracao", "qms:copiar_faixas_padrao"],
                        "perm": "core.nav_metrologia_editar_instrumento",
                    },
                    {
                        "nome": "Substituir Instrumento",
                        "view_name": ["substituir_instrumento", "qms:substituir_instrumento", "metrologia:atendimento_iniciar_substituicao"],
                        "perm": "core.nav_metrologia_substituir_instrumento",
                    },
                    {"nome": "Atualizar Datas de Calibração em Massa", "view_name": "metrologia:atualizar_todas_datas_calibracao", "perm": "core.nav_metrologia_atualizar_datas_massa"},
                    {"nome": "Exportar Instrumentos (Excel/CSV)", "view_name": ["export_metrologia", "exportar_instrumentos", "qms:exportar_instrumentos"], "perm": "core.nav_metrologia_export_instrumentos"},
                    {"nome": "Importar Instrumentos", "view_name": ["qms:importar_instrumentos", "dl_template_instr"], "perm": "core.nav_metrologia_importar_instrumentos"},
                    {"nome": "Acompanhar Importações (Jobs)", "view_name": ["import_jobs", "import_jobs_json"], "perm": "core.nav_metrologia_import_jobs"},
                    {"nome": "Registrar Ocorrência do Instrumento", "view_name": "metrologia:registrar_ocorrencia", "perm": "core.nav_metrologia_ocorrencia_registrar"},
                    {"nome": "Editar/Encerrar Ocorrência do Instrumento", "view_name": ["metrologia:editar_ocorrencia", "metrologia:encerrar_ocorrencia", "metrologia:reabrir_ocorrencia", "metrologia:atribuir_responsavel_ocorrencia", "metrologia:adicionar_mensagem_ocorrencia"], "perm": "core.nav_metrologia_ocorrencia_editar"},
                    {"nome": "Excluir Ocorrência do Instrumento", "view_name": "metrologia:deletar_ocorrencia", "perm": "core.nav_metrologia_ocorrencia_excluir"},
                    {"nome": "Relatório de Ocorrências (Tratativas)", "view_name": "metrologia:relatorio_ocorrencias", "perm": "core.nav_metrologia_ocorrencias_relatorio"},
                ],
            },
            {
                "key": "historicos",
                "nome": "Históricos de Calibração",
                "perm": "core.nav_metrologia_historicos_bloco",
                "funcoes": [
                    {"nome": "Históricos de Calibração", "view_name": "qms:listar_historicos_calibracao", "perm": "core.nav_metrologia_historicos_calibracao"},
                    {
                        "nome": "Registrar Histórico de Calibração",
                        "view_name": ["registrar_historico_calibracao", "qms:novo_historico_from_listagem", "metrologia:atendimento_registrar_historico"],
                        "perm": "core.nav_metrologia_registrar_historico",
                    },
                    {"nome": "Registrar Históricos em Massa", "view_name": "metrologia:registrar_historico_massa", "perm": "core.nav_metrologia_registrar_historico_massa"},
                    {"nome": "Visualizar Histórico de Calibração", "view_name": "visualizar_historico_calibracao", "perm": "core.nav_metrologia_visualizar_historico"},
                    {
                        "nome": "Editar Histórico de Calibração",
                        "view_name": ["editar_historico_calibracao", "anexar_certificado_historico", "salvar_edicao_historico_modal"],
                        "perm": "core.nav_metrologia_editar_historico",
                    },
                    {"nome": "Remover Histórico de Calibração", "view_name": "remover_historico", "perm": "core.nav_metrologia_remover_historico"},
                    {"nome": "Certificado (Download/Visualizar)", "view_name": ["download_certificado", "get_certificado_bytes", "preview_certificado"], "perm": "core.nav_metrologia_download_certificado"},
                    {"nome": "Certificado (Aplicar Carimbo)", "view_name": "aplicar_carimbo_certificado", "perm": "core.nav_metrologia_aplicar_carimbo_certificado"},
                    {"nome": "Certificado (Remover Carimbo)", "view_name": "remover_carimbo_certificado", "perm": "core.nav_metrologia_remover_carimbo_certificado"},
                    {"nome": "Certificado (Remover)", "view_name": "remover_certificado_historico", "perm": "core.nav_metrologia_remover_certificado_historico"},
                    {"nome": "Importar Histórico", "view_name": ["qms:importar_historico", "dl_template_historico", "qms:dl_template_historico"], "perm": "core.nav_metrologia_importar_historico"},
                ],
            },
            {
                "key": "categorias",
                "nome": "Categorias",
                "perm": "core.nav_metrologia_categorias_bloco",
                "funcoes": [
                    {"nome": "Categorias", "view_name": ["metrologia:categorias_list", "metrologia:categoria_detail", "dl_template_categorias"], "perm": "core.nav_metrologia_categorias"},
                    {"nome": "Nova Categoria", "view_name": "metrologia:categoria_create", "perm": "core.nav_metrologia_categoria_create"},
                    {"nome": "Editar Categoria", "view_name": "metrologia:categoria_update", "perm": "core.nav_metrologia_categoria_update"},
                    {"nome": "Deletar Categoria", "view_name": "metrologia:categoria_delete", "perm": "core.nav_metrologia_categoria_delete"},
                    {
                        "nome": "Atualizações em Massa (Frequência, Sigla, Tratativa, Ação)",
                        "view_name": [
                            "metrologia:categoria_bulk_update_frequencia",
                            "metrologia:categoria_bulk_update_sigla",
                            "metrologia:categoria_bulk_update_tratativa",
                            "metrologia:categoria_bulk_update_acao",
                        ],
                        "perm": "core.nav_metrologia_categoria_bulk_update",
                    },
                    {"nome": "Nova Faixa (Categoria)", "view_name": "metrologia:faixa_categoria_create", "perm": "core.nav_metrologia_faixa_categoria_create"},
                    {"nome": "Editar Faixa (Categoria)", "view_name": ["metrologia:faixa_categoria_update", "editar_faixa"], "perm": "core.nav_metrologia_faixa_categoria_update"},
                    {"nome": "Deletar Faixa (Categoria)", "view_name": "metrologia:faixa_categoria_delete", "perm": "core.nav_metrologia_faixa_categoria_delete"},
                    {"nome": "Aplicar Faixa a Instrumentos", "view_name": "metrologia:faixa_categoria_add_to_instrument", "perm": "core.nav_metrologia_faixa_instrumento_add"},
                    {
                        "nome": "Substituir Faixa-Instrumento (Individual e em Massa)",
                        "view_name": ["metrologia:faixa_instrumento_replace", "metrologia:faixa_instrumento_bulk_replace"],
                        "perm": "core.nav_metrologia_faixa_instrumento_replace",
                    },
                    {"nome": "Remover Faixa-Instrumento", "view_name": "metrologia:faixa_instrumento_delete", "perm": "core.nav_metrologia_faixa_instrumento_delete"},
                    {"nome": "Remover Faixa-Instrumento em Massa", "view_name": "metrologia:faixa_instrumento_bulk_delete", "perm": "core.nav_metrologia_faixa_instrumento_bulk_delete"},
                    {"nome": "Alterar Categoria de Instrumentos em Massa", "view_name": "metrologia:instrumento_bulk_change_category", "perm": "core.nav_metrologia_instrumento_bulk_change_category"},
                    {"nome": "Arquivo Padrão (Download)", "view_name": "download_arquivo_padrao", "perm": "core.nav_metrologia_download_arquivo_padrao"},
                    {"nome": "Arquivo Padrão (Remover)", "view_name": "remover_arquivo_padrao", "perm": "core.nav_metrologia_remover_arquivo_padrao"},
                ],
            },
            {
                "key": "unidades",
                "nome": "Unidades de Medida",
                "perm": "core.nav_metrologia_unidades_bloco",
                "funcoes": [
                    {"nome": "Unidades de Medida", "view_name": ["metrologia:unidades_list", "metrologia:unidade_detail"], "perm": "core.nav_metrologia_unidades_medida"},
                    {"nome": "Nova Unidade de Medida", "view_name": "metrologia:unidade_create", "perm": "core.nav_metrologia_unidade_create"},
                    {"nome": "Editar Unidade de Medida", "view_name": "metrologia:unidade_update", "perm": "core.nav_metrologia_unidade_update"},
                    {"nome": "Deletar Unidade de Medida", "view_name": "metrologia:unidade_delete", "perm": "core.nav_metrologia_unidade_delete"},
                ],
            },
            {
                "key": "modelos_etiquetas",
                "nome": "Modelos de Etiquetas",
                "perm": "core.nav_metrologia_etiquetas_bloco",
                "funcoes": [
                    {"nome": "Modelos de Etiquetas", "view_name": ["metrologia:templates_etiquetas_list", "metrologia:template_etiqueta_download"], "perm": "core.nav_metrologia_templates_etiquetas"},
                    {"nome": "Enviar Modelo", "view_name": "metrologia:template_etiqueta_upload", "perm": "core.nav_metrologia_template_etiqueta_upload"},
                    {"nome": "Ativar/Desativar Modelo", "view_name": "metrologia:template_etiqueta_toggle", "perm": "core.nav_metrologia_template_etiqueta_toggle"},
                    {"nome": "Excluir Modelo", "view_name": "metrologia:template_etiqueta_delete", "perm": "core.nav_metrologia_template_etiqueta_delete"},
                    {"nome": "Exportar Etiquetas", "view_name": ["metrologia:export_etiquetas", "export_etiquetas", "metrologia:export_etiquetas_excel"], "perm": "core.nav_metrologia_export_etiquetas"},
                ],
            },
            {
                "key": "cotacoes",
                "nome": "Solicitações de Cotação",
                "perm": "core.nav_metrologia_cotacoes",
                "funcoes": [
                    {
                        "nome": "Solicitações de Cotação",
                        "view_name": [
                            "metrologia:solicitacao_list",
                            "qms:solicitacao_list",
                            "metrologia:solicitacao_detail",
                            "metrologia:solicitacao_itens",
                            "metrologia:cotacao_fornecedor_detail",
                            "metrologia:atendimento_detail",
                        ],
                        "perm": "core.nav_metrologia_solicitacoes_cotacao",
                    },
                    {"nome": "Nova Solicitação de Cotação", "view_name": "metrologia:solicitacao_create", "perm": "core.nav_metrologia_solicitacao_create"},
                    {"nome": "Editar Solicitação de Cotação", "view_name": "metrologia:solicitacao_update", "perm": "core.nav_metrologia_solicitacao_update"},
                    {"nome": "Deletar Solicitação de Cotação", "view_name": "metrologia:solicitacao_delete", "perm": "core.nav_metrologia_solicitacao_delete"},
                    {
                        "nome": "Alterar Status (Concluir, Cancelar, Reabrir, Reativar)",
                        "view_name": ["metrologia:solicitacao_concluir", "metrologia:solicitacao_cancelar", "metrologia:solicitacao_reabrir", "metrologia:solicitacao_reativar"],
                        "perm": "core.nav_metrologia_solicitacao_status",
                    },
                    {"nome": "Editar Item da Solicitação", "view_name": "metrologia:item_solicitacao_edit", "perm": "core.nav_metrologia_item_solicitacao_edit"},
                    {"nome": "Deletar Item da Solicitação", "view_name": "metrologia:item_solicitacao_delete", "perm": "core.nav_metrologia_item_solicitacao_delete"},
                    {"nome": "Nova Cotação (Fornecedor)", "view_name": "metrologia:cotacao_fornecedor_create", "perm": "core.nav_metrologia_cotacao_fornecedor_create"},
                    {"nome": "Editar Cotação (Fornecedor)", "view_name": "metrologia:cotacao_fornecedor_update", "perm": "core.nav_metrologia_cotacao_fornecedor_update"},
                    {"nome": "Novo Atendimento", "view_name": ["metrologia:atendimento_create", "metrologia:atendimento_create_from_cotacao"], "perm": "core.nav_metrologia_atendimento_create"},
                    {"nome": "Confirmar Atendimento", "view_name": "metrologia:atendimento_confirmar", "perm": "core.nav_metrologia_atendimento_confirmar"},
                    {
                        "nome": "Atualizar Atendimento (Dados, Cotação, Datas, Chegada, Rastreio)",
                        "view_name": [
                            "metrologia:atendimento_atualizar_dados",
                            "metrologia:atendimento_atualizar_cotacao",
                            "metrologia:atendimento_atualizar_data_calibracao",
                            "metrologia:atendimento_atualizar_chegada",
                            "metrologia:atendimento_atualizar_rastreio",
                        ],
                        "perm": "core.nav_metrologia_atendimento_update",
                    },
                ],
            },
        ],
    },
    {
        "key": "procedures",
        "nome": "Treinamentos",
        "cor": "warning",
        "icone": "bi bi-mortarboard-fill",
        "module_perm": "core.nav_mod_treinamentos",
        "blocos": [
            {
                "key": "acompanhamento",
                "nome": "Dashboard",
                "perm": "core.nav_treinamentos_acompanhamento",
                "funcoes": [
                    {"nome": "Dashboard", "view_name": ["procedures:dashboard_treinamentos", "training:dashboard_treinamentos", "training:dashboard_filtered"], "perm": "core.nav_treinamentos_dashboard"},
                    {"nome": "Exportar Dashboard (CSV)", "view_name": "training:dashboard_exportar_csv", "perm": "core.nav_treinamentos_dashboard_export_csv"},
                    {"nome": "Gaps de Competência", "view_name": ["procedures:dashboard_gaps", "procedures:gap_detalhado", "procedures:gaps_por_perfil"], "perm": "core.nav_treinamentos_gaps"},
                ],
            },
            {
                "key": "calendario",
                "nome": "Calendário",
                "perm": "core.nav_treinamentos_calendario_bloco",
                "funcoes": [
                    {"nome": "Calendário", "view_name": "procedures:treinamentos_calendario", "perm": "core.nav_treinamentos_calendario"},
                ],
            },
            {
                "key": "gestao",
                "nome": "Registros de Treinamento",
                "perm": "core.nav_treinamentos_gestao",
                "funcoes": [
                    {"nome": "Registros de Treinamento", "view_name": ["procedures:treinamentos_list", "procedures:treinamentos_historico"], "perm": "core.nav_treinamentos_registros"},
                    {"nome": "Novo Treinamento", "view_name": "procedures:novo_treinamento", "perm": "core.nav_treinamentos_novo_treinamento"},
                    {"nome": "Detalhe do Treinamento", "view_name": "procedures:treinamentos_detalhe", "perm": "core.nav_treinamentos_detalhe_treinamento"},
                    {"nome": "Editar Treinamento", "view_name": "procedures:editar_treinamento", "perm": "core.nav_treinamentos_editar_treinamento"},
                    {"nome": "Importar Treinamentos", "view_name": "procedures:treinamentos_importar", "perm": "core.nav_treinamentos_importar_treinamentos"},
                    {"nome": "Template Importação (Download)", "view_name": "procedures:treinamentos_template_download", "perm": "core.nav_treinamentos_download_template"},
                    {"nome": "Exportar Treinamentos (Excel)", "view_name": "procedures:treinamentos_exportar_excel", "perm": "core.nav_treinamentos_exportar_treinamentos"},
                ],
            },
            {
                "key": "eficacia",
                "nome": "Avaliação de Eficácia",
                "perm": "core.nav_treinamentos_eficacia_bloco",
                "funcoes": [
                    {"nome": "Avaliação de Eficácia", "view_name": "procedures:avaliacao_eficacia_list", "perm": "core.nav_treinamentos_eficacia"},
                    {"nome": "Registrar Avaliação de Eficácia", "view_name": "procedures:avaliacao_eficacia_registrar", "perm": "core.nav_treinamentos_eficacia_registrar"},
                    {"nome": "Registrar Avaliação de Eficácia em Massa", "view_name": "procedures:avaliacao_eficacia_registrar_massa", "perm": "core.nav_treinamentos_eficacia_registrar_massa"},
                    {"nome": "Alterar Gestor em Massa", "view_name": "procedures:avaliacao_eficacia_alterar_gestor_massa", "perm": "core.nav_treinamentos_eficacia_alterar_gestor"},
                    {
                        "nome": "Exportar (Excel / FOR.142)",
                        "view_name": [
                            "procedures:avaliacao_eficacia_export_excel",
                            "procedures:exportar_avaliacao_eficacia_for142",
                            "procedures:exportar_avaliacao_eficacia_for142_massa",
                        ],
                        "perm": "core.nav_treinamentos_eficacia_export",
                    },
                ],
            },
            {
                "key": "listas_presenca",
                "nome": "Listas de Presença",
                "perm": "core.nav_treinamentos_listas_presenca_bloco",
                "funcoes": [
                    {
                        "nome": "Listas de Presença",
                        "view_name": ["procedures:lista_presenca_list", "procedures:lista_presenca_detail", "procedures:visualizar_lista_presenca_assinada"],
                        "perm": "core.nav_treinamentos_listas_presenca",
                    },
                    {"nome": "Nova Lista de Presença", "view_name": "procedures:lista_presenca_create", "perm": "core.nav_treinamentos_lista_presenca_create"},
                    {"nome": "Editar Lista de Presença", "view_name": "procedures:lista_presenca_edit", "perm": "core.nav_treinamentos_lista_presenca_edit"},
                    {"nome": "Deletar Lista de Presença", "view_name": "procedures:lista_presenca_delete", "perm": "core.nav_treinamentos_lista_presenca_delete"},
                    {"nome": "Importar Lista de Presença", "view_name": "procedures:lista_presenca_importar", "perm": "core.nav_treinamentos_lista_presenca_import"},
                    {"nome": "Exportar Listas de Presença", "view_name": "procedures:lista_presenca_export", "perm": "core.nav_treinamentos_lista_presenca_export"},
                    {"nome": "Exportar Lista de Presença (PDF)", "view_name": "procedures:lista_presenca_export_pdf", "perm": "core.nav_treinamentos_lista_presenca_export_pdf"},
                    {"nome": "Template de Importação", "view_name": "procedures:lista_presenca_download_template", "perm": "core.nav_treinamentos_lista_presenca_template"},
                    {"nome": "Download Erros Importação", "view_name": "procedures:lista_presenca_erros_download", "perm": "core.nav_treinamentos_lista_presenca_erros_download"},
                    {"nome": "Upload Lista Assinada", "view_name": "procedures:upload_lista_presenca_assinada", "perm": "core.nav_treinamentos_lista_presenca_upload_assinada"},
                    {"nome": "Remover Lista Assinada", "view_name": "procedures:remover_lista_presenca_assinada", "perm": "core.nav_treinamentos_lista_presenca_remover_assinada"},
                    {
                        "nome": "Gerar Lista de Presença (a partir do Planejamento)",
                        "view_name": [
                            "procedures:selecionar_template_lista_presenca",
                            "procedures:gerar_lista_presenca_desde_planejamento",
                            "procedures:gerar_lista_presenca_pdf",
                            "procedures:gerar_lista_presenca",
                        ],
                        "perm": "core.nav_treinamentos_lista_presenca_gerar",
                    },
                    {
                        "nome": "Templates de Lista de Presença",
                        "view_name": [
                            "procedures:upload_template_lista_presenca",
                            "procedures:mapear_template_fields",
                            "procedures:serve_pdf_template",
                            "procedures:gerenciar_templates_presenca",
                        ],
                        "perm": "core.nav_treinamentos_lista_presenca_template_upload",
                    },
                ],
            },
            {
                "key": "planejamento",
                "nome": "Planejamento",
                "perm": "core.nav_treinamentos_planejamento_bloco",
                "funcoes": [
                    {"nome": "Planejamento", "view_name": ["procedures:planejamentos_list", "procedures:detalhe_planejamento"], "perm": "core.nav_treinamentos_planejamento"},
                    {
                        "nome": "Novo Planejamento",
                        "view_name": [
                            "procedures:novo_planejamento",
                            "procedures:novo_planejamento_com_tipo",
                            "procedures:selecionar_tipo_planejamento",
                            "procedures:selecionar_matriz",
                            "procedures:gerar_planejamentos_matriz",
                        ],
                        "perm": "core.nav_treinamentos_planejamento_create",
                    },
                    {
                        "nome": "Editar Planejamento",
                        "view_name": [
                            "procedures:editar_planejamento",
                            "procedures:adicionar_procedimento_planejamento",
                            "procedures:adicionar_colaborador_planejamento",
                            "procedures:api_cadastrar_pergunta_rapida",
                        ],
                        "perm": "core.nav_treinamentos_planejamento_edit",
                    },
                    {"nome": "Alterar Status do Planejamento", "view_name": "procedures:alterar_status_planejamento", "perm": "core.nav_treinamentos_planejamento_status"},
                    {"nome": "Gerar Registros de Treinamento", "view_name": "procedures:criar_registros_planejamento", "perm": "core.nav_treinamentos_planejamento_criar_registros"},
                    {"nome": "Deletar Planejamento", "view_name": "procedures:deletar_planejamento", "perm": "core.nav_treinamentos_planejamento_delete"},
                    {"nome": "Excluir Planejamentos (Massa)", "view_name": "procedures:excluir_planejamentos_massa", "perm": "core.nav_treinamentos_planejamento_mass_delete"},
                    {
                        "nome": "Exportar Planejamentos (Excel, FOR.133, FOR.141)",
                        "view_name": [
                            "procedures:exportar_lista_planejamentos_excel",
                            "procedures:exportar_detalhe_planejamento_excel",
                            "procedures:exportar_planejamento_for133",
                            "procedures:exportar_planejamento_for133_single",
                            "procedures:exportar_auto_avaliacao_for141",
                            "procedures:exportar_auto_avaliacao_for141_pdf",
                            "procedures:auto_avaliacao_print",
                        ],
                        "perm": "core.nav_treinamentos_planejamento_export",
                    },
                    {"nome": "Remover Procedimento do Planejamento", "view_name": "procedures:remover_procedimento_planejamento", "perm": "core.nav_treinamentos_planejamento_procedimento_remove"},
                    {"nome": "Remover Colaborador do Planejamento", "view_name": "procedures:remover_colaborador_planejamento", "perm": "core.nav_treinamentos_planejamento_colaborador_remove"},
                ],
            },
            {
                "key": "templates",
                "nome": "Templates de Documentos",
                "perm": "core.nav_treinamentos_templates_bloco",
                "funcoes": [
                    {
                        "nome": "Configuração de Templates",
                        "view_name": [
                            "procedures:templates_config",
                            "procedures:template_config_upload",
                            "procedures:template_config_download",
                            "procedures:template_config_toggle_active",
                            "procedures:template_config_delete",
                            "procedures:template_config_replace_file",
                        ],
                        "perm": "core.nav_treinamentos_templates_config",
                    },
                ],
            },
            {
                "key": "fornecedores",
                "nome": "Fornecedores e Cotações de Treinamento",
                "perm": "core.nav_treinamentos_fornecedores_bloco",
                "funcoes": [
                    {
                        "nome": "Fornecedores e Cotações",
                        "view_name": ["procedures:fornecedores_list", "procedures:detalhe_fornecedor", "procedures:cotacoes_list", "procedures:detalhe_cotacao"],
                        "perm": "core.nav_treinamentos_fornecedores",
                    },
                    {"nome": "Novo Fornecedor", "view_name": "procedures:novo_fornecedor", "perm": "core.nav_treinamentos_fornecedor_create"},
                    {"nome": "Editar Fornecedor", "view_name": "procedures:editar_fornecedor", "perm": "core.nav_treinamentos_fornecedor_update"},
                    {"nome": "Nova Avaliação de Fornecedor", "view_name": "procedures:nova_avaliacao", "perm": "core.nav_treinamentos_fornecedor_avaliacao"},
                    {"nome": "Nova Cotação", "view_name": "procedures:nova_cotacao", "perm": "core.nav_treinamentos_cotacao_create"},
                    {"nome": "Editar Cotação", "view_name": "procedures:editar_cotacao", "perm": "core.nav_treinamentos_cotacao_update"},
                    {"nome": "Novo Orçamento", "view_name": "procedures:novo_orcamento", "perm": "core.nav_treinamentos_orcamento_create"},
                    {"nome": "Editar Orçamento", "view_name": "procedures:editar_orcamento", "perm": "core.nav_treinamentos_orcamento_update"},
                ],
            },
            {
                "key": "matriz",
                "nome": "Matrizes",
                "perm": "core.nav_treinamentos_matriz",
                "funcoes": [
                    {"nome": "Matrizes", "view_name": ["procedures:matrizes_list", "procedures:detalhe_matriz"], "perm": "core.nav_treinamentos_matrizes"},
                    {"nome": "Nova Matriz", "view_name": "procedures:nova_matriz", "perm": "core.nav_treinamentos_matriz_create"},
                    {"nome": "Editar Matriz", "view_name": "procedures:editar_matriz", "perm": "core.nav_treinamentos_matriz_edit"},
                    {"nome": "Deletar Matriz", "view_name": "procedures:deletar_matriz", "perm": "core.nav_treinamentos_matrizes_delete"},
                    {"nome": "Exportar Matrizes", "view_name": "procedures:exportar_matrizes", "perm": "core.nav_treinamentos_matrizes_export"},
                    {"nome": "Importação de Matriz", "view_name": ["procedures:importacao_matriz", "procedures:importacao_matriz_resultado"], "perm": "core.nav_treinamentos_matrizes_import"},
                    {"nome": "Template Importação Matriz", "view_name": "procedures:baixar_template_importacao", "perm": "core.nav_treinamentos_matrizes_template"},
                    {"nome": "Associar Colaboradores", "view_name": "procedures:associar_colaborador", "perm": "core.nav_treinamentos_matriz_colaborador_add"},
                    {"nome": "Remover/Desassociar Colaboradores", "view_name": ["procedures:remover_colaborador_matriz", "procedures:desassociar_colaboradores"], "perm": "core.nav_treinamentos_matrizes_colaborador_remove"},
                    {"nome": "Solicitar Validação", "view_name": "procedures:solicitar_validacao", "perm": "core.nav_treinamentos_matriz_solicitar_validacao"},
                ],
            },
            {
                "key": "disciplinas",
                "nome": "Disciplinas",
                "perm": "core.nav_treinamentos_disciplinas_bloco",
                "funcoes": [
                    {"nome": "Disciplinas", "view_name": ["procedures:disciplinas_list", "procedures:detalhe_disciplina", "procedures:api_disciplinas_por_matriz_novo"], "perm": "core.nav_treinamentos_disciplinas"},
                    {"nome": "Nova Disciplina", "view_name": "procedures:nova_disciplina", "perm": "core.nav_treinamentos_disciplina_create"},
                    {"nome": "Editar Disciplina", "view_name": "procedures:editar_disciplina", "perm": "core.nav_treinamentos_disciplina_edit"},
                    {"nome": "Deletar Disciplina", "view_name": "procedures:deletar_disciplina", "perm": "core.nav_treinamentos_disciplinas_delete"},
                    {
                        "nome": "Adicionar Procedimentos à Disciplina",
                        "view_name": ["procedures:adicionar_procedimento_disciplina", "procedures:adicionar_multiplos_procedimentos"],
                        "perm": "core.nav_treinamentos_disciplina_procedimento_add",
                    },
                    {"nome": "Remover Procedimento da Disciplina", "view_name": "procedures:remover_procedimento_disciplina", "perm": "core.nav_treinamentos_disciplina_procedimento_remove"},
                ],
            },
            {
                "key": "avaliacoes",
                "nome": "Avaliações de Colaboradores",
                "perm": "core.nav_treinamentos_avaliacoes_bloco",
                "funcoes": [
                    {
                        "nome": "Avaliações de Colaboradores",
                        "view_name": ["procedures:matriz_avaliacoes", "procedures:exportar_matriz_excel", "procedures:avaliacoes_colaborador"],
                        "perm": "core.nav_treinamentos_avaliacoes",
                    },
                    {
                        "nome": "Registrar/Editar Avaliação",
                        "view_name": [
                            "procedures:editar_avaliacao",
                            "procedures:salvar_avaliacao_api",
                            "procedures:salvar_avaliacao_modal_api",
                            "procedures:salvar_avaliacao_lote_api",
                            "procedures:avaliar_matriz",
                            "procedures:avaliacao_rapida",
                        ],
                        "perm": "core.nav_treinamentos_avaliacao_edit",
                    },
                ],
            },
            {
                "key": "perfis",
                "nome": "Perfis e Grupos",
                "perm": "core.nav_treinamentos_perfis_bloco",
                "funcoes": [
                    {"nome": "Perfis e Grupos", "view_name": ["procedures:perfis_list", "procedures:detalhe_perfil"], "perm": "core.nav_treinamentos_perfis"},
                    {"nome": "Novo Perfil", "view_name": "procedures:novo_perfil", "perm": "core.nav_treinamentos_perfil_create"},
                    {"nome": "Editar Perfil", "view_name": "procedures:editar_perfil", "perm": "core.nav_treinamentos_perfil_edit"},
                    {"nome": "Deletar Perfil", "view_name": "procedures:api_delete_perfil", "perm": "core.nav_treinamentos_perfis_delete"},
                    {"nome": "Deletar Perfis em Massa", "view_name": "procedures:api_delete_perfis_multiple", "perm": "core.nav_treinamentos_perfis_mass_delete"},
                    {"nome": "Importar Perfis", "view_name": "procedures:importar_perfis", "perm": "core.nav_treinamentos_perfis_import"},
                    {"nome": "Importar Estrutura", "view_name": "procedures:importar_estrutura", "perm": "core.nav_treinamentos_perfis_import_estrutura"},
                    {"nome": "Exportar Estrutura", "view_name": "procedures:exportar_estrutura", "perm": "core.nav_treinamentos_perfis_export_estrutura"},
                    {"nome": "Exportar Erros Importação", "view_name": "procedures:exportar_erros_importacao", "perm": "core.nav_treinamentos_perfis_export_erros"},
                    {"nome": "Template Importação (Download)", "view_name": "procedures:download_template_importacao", "perm": "core.nav_treinamentos_perfis_template_importacao"},
                    {
                        "nome": "Enviar/Mapear Templates (Excel e PDF)",
                        "view_name": [
                            "procedures:upload_excel_template",
                            "procedures:mapear_campos_template",
                            "procedures:preview_excel_abas_api",
                            "procedures:preview_excel_celulas_api",
                            "procedures:atualizar_mapeamento_campo_api",
                            "procedures:status_mapeamento_api",
                            "procedures:upload_pdf_template",
                        ],
                        "perm": "core.nav_treinamentos_perfis_upload_template",
                    },
                    {"nome": "Remover Template / Mapeamento", "view_name": ["procedures:remove_pdf_template", "procedures:remover_mapeamento_campo_api"], "perm": "core.nav_treinamentos_perfis_delete_template"},
                    {"nome": "Novo Grupo", "view_name": "procedures:novo_grupo", "perm": "core.nav_treinamentos_grupo_create"},
                    {"nome": "Editar/Reordenar Grupo", "view_name": ["procedures:editar_grupo", "procedures:mover_grupo"], "perm": "core.nav_treinamentos_grupo_update"},
                    {"nome": "Deletar Grupo", "view_name": "procedures:deletar_grupo", "perm": "core.nav_treinamentos_grupo_delete"},
                    {"nome": "Novo Subgrupo", "view_name": "procedures:novo_subgrupo", "perm": "core.nav_treinamentos_subgrupo_create"},
                    {"nome": "Editar/Reordenar Subgrupo", "view_name": ["procedures:editar_subgrupo", "procedures:mover_subgrupo"], "perm": "core.nav_treinamentos_subgrupo_update"},
                    {"nome": "Deletar Subgrupo", "view_name": "procedures:deletar_subgrupo", "perm": "core.nav_treinamentos_subgrupo_delete"},
                    {"nome": "Adicionar Procedimento ao Subgrupo", "view_name": "procedures:adicionar_procedimento_subgrupo", "perm": "core.nav_treinamentos_subgrupo_procedimento_add"},
                    {"nome": "Remover Procedimento do Subgrupo", "view_name": "procedures:remover_procedimento_subgrupo", "perm": "core.nav_treinamentos_subgrupo_procedimento_remove"},
                    {
                        "nome": "Pacotes de Integração (Salvar, Editar, Copiar)",
                        "view_name": [
                            "procedures:salvar_pacote_integracao",
                            "procedures:editar_pacote_integracao",
                            "procedures:copiar_grupo_para_pacote",
                            "procedures:copiar_pacote_entre_perfis",
                        ],
                        "perm": "core.nav_treinamentos_perfis_integracao",
                    },
                    {"nome": "Excluir Pacote de Integração", "view_name": "procedures:deletar_pacote_integracao", "perm": "core.nav_treinamentos_perfis_integracao_delete"},
                    {
                        "nome": "Adicionar/Associar Colaborador ao Perfil",
                        "view_name": ["procedures:adicionar_colaborador_perfil", "procedures:associar_perfil_colaborador"],
                        "perm": "core.nav_treinamentos_perfis_colaborador_add",
                    },
                    {"nome": "Editar Colaborador do Perfil", "view_name": ["procedures:editar_colaborador_perfil", "procedures:reatribuir_todos_subgrupos"], "perm": "core.nav_treinamentos_perfis_colaborador_edit"},
                    {
                        "nome": "Remover Colaborador do Perfil",
                        "view_name": ["procedures:remover_colaborador_perfil", "procedures:remover_associacao_perfil_colaborador"],
                        "perm": "core.nav_treinamentos_perfis_colaborador_remove",
                    },
                    {"nome": "Remover Colaboradores em Massa", "view_name": "procedures:remover_colaboradores_massa", "perm": "core.nav_treinamentos_perfis_colaborador_mass_remove"},
                ],
            },
            {
                "key": "procedimentos",
                "nome": "Procedimentos",
                "perm": "core.nav_treinamentos_procedimentos_bloco",
                "funcoes": [
                    {
                        "nome": "Procedimentos",
                        "view_name": ["procedures:procedimentos_list", "procedures:detalhe_procedimento", "qms:procedimentos_lista", "qms:detalhe_procedimento"],
                        "perm": "core.nav_treinamentos_procedimentos",
                    },
                    {"nome": "Novo Procedimento", "view_name": ["procedures:novo_procedimento", "qms:novo_procedimento"], "perm": "core.nav_treinamentos_novo_procedimento"},
                    {"nome": "Editar Procedimento", "view_name": ["procedures:editar_procedimento", "qms:editar_procedimento"], "perm": "core.nav_treinamentos_editar_procedimento"},

                    {
                        "nome": "Importar Procedimentos",
                        "view_name": ["procedures:importar_procedimentos", "procedures:dl_template_procedimentos", "dl_template_procedimentos"],
                        "perm": "core.nav_treinamentos_importar_procedimentos",
                    },
                    {"nome": "Exportar Procedimentos (Excel)", "view_name": "procedures:export_procedimentos_excel", "perm": "core.nav_treinamentos_exportar_procedimentos"},
                ],

            },
            {
                "key": "procedimentos_matrizes",
                "nome": "Matrizes e Sub-áreas",
                "perm": "core.nav_treinamentos_proc_matrizes_bloco",
                "funcoes": [
                    {
                        "nome": "Matrizes e Sub-áreas",
                        "view_name": ["procedures:procedimento_matrizes_list", "procedures:procedimento_matriz_detalhe", "procedures:procedimento_responsabilidades_treinamento"],
                        "perm": "core.nav_treinamentos_procedimentos_matrizes",
                    },
                    {
                        "nome": "Importar Matrizes e Sub-áreas",
                        "view_name": ["procedures:importar_matrizes_subareas", "procedures:download_template_matrizes_subareas"],
                        "perm": "core.nav_treinamentos_procedimentos_matrizes_import",
                    },
                    {"nome": "API Sub-áreas por Matriz", "view_name": "procedures:api_subareas_por_matriz", "perm": "core.nav_treinamentos_procedimentos_subareas_api"},
                ],
            },
            {
                "key": "perguntas_auto_avaliacao",
                "nome": "Perguntas Auto-Avaliação (FOR.141)",
                "perm": "core.nav_treinamentos_perguntas_auto_avaliacao_bloco",
                "funcoes": [
                    {
                        "nome": "Perguntas Auto-Avaliação (Lista e Pré-visualização)",
                        "view_name": [
                            "procedures:perguntas_avaliacao_list",
                            "procedures:exportar_preview_for141_procedimento",
                            "procedures:exportar_preview_for141_pdf_procedimento",
                            "procedures:preview_for141_print_procedimento",
                        ],
                        "perm": "core.nav_treinamentos_perguntas_auto_avaliacao",
                    },
                    {
                        "nome": "Salvar Perguntas de Auto-Avaliação",
                        "view_name": ["procedures:salvar_perguntas_procedimento_api", "procedures:api_salvar_perguntas_procedimento"],
                        "perm": "core.nav_treinamentos_perguntas_auto_avaliacao_edit",
                    },
                ],
            },
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Validar Qualquer Matriz de Competência",
                        "perm": "core.nav_treinamentos_validar_matriz",
                        "descricao": "Vê todas as validações pendentes e pode validar/rejeitar qualquer matriz, mesmo sem ser o validador designado.",
                    },
                ],
            },
        ],
    },
    {
        "key": "rh",
        "nome": "Pessoas",
        "cor": "primary",
        "icone": "bi bi-people",
        "module_perm": "core.nav_mod_pessoas",
        "blocos": [
            {
                "key": "equipe",
                "nome": "Colaboradores",
                "perm": "core.nav_pessoas_equipe",
                "funcoes": [
                    {"nome": "Colaboradores", "view_name": "modulo_rh", "perm": "core.nav_pessoas_colaboradores"},
                    {"nome": "Novo Colaborador", "view_name": "rh:criar_colaborador", "perm": "core.nav_pessoas_novo_colaborador"},
                    {"nome": "Detalhe do Colaborador", "view_name": ["rh:detalhe_colaborador", "detalhe_colaborador"], "perm": "core.nav_pessoas_detalhe_colaborador"},
                    {"nome": "Editar Colaborador", "view_name": "editar_colaborador", "perm": "core.nav_pessoas_editar_colaborador"},
                    {"nome": "Alterar Foto do Colaborador", "perm": "rh.pode_alterar_foto_colaborador", "descricao": "Permite fazer o upload/corte e alterar a foto de perfil do colaborador."},
                    {"nome": "Excluir Colaborador", "view_name": "rh:api_delete_colaborador", "perm": "core.nav_pessoas_api_delete_colaborador"},
                    {"nome": "Excluir Colaboradores em Massa", "view_name": "rh:api_delete_colaboradores_multiple", "perm": "core.nav_pessoas_api_delete_colaboradores_multiple"},
                    {"nome": "Importar Pessoas", "view_name": ["qms:importar_colaboradores", "dl_template_colab", "dl_template_colab_dados"], "perm": "core.nav_pessoas_importar_pessoas"},
                ],
            },
            {
                "key": "ferias",
                "nome": "Gestão de Férias",
                "perm": "core.nav_pessoas_ferias_bloco",
                "funcoes": [
                    {"nome": "Gestão de Férias", "view_name": ["rh:gestao_ferias", "rh:grid_ferias", "rh:projecao_mensal_ferias", "rh:api_ferias_detail"], "perm": "core.nav_pessoas_gestao_ferias"},
                    {"nome": "Registrar Férias", "view_name": ["rh:criar_ferias", "registrar_ferias", "rh:criar_ferias_colab"], "perm": "core.nav_pessoas_registrar_ferias"},
                    {"nome": "Editar Férias", "view_name": ["rh:editar_ferias", "editar_ferias"], "perm": "core.nav_pessoas_editar_ferias"},
                    {"nome": "Excluir Férias", "view_name": ["rh:excluir_ferias", "excluir_ferias"], "perm": "core.nav_pessoas_excluir_ferias"},
                    {"nome": "Atualizar Status das Férias", "view_name": "rh:atualizar_status_ferias", "perm": "core.nav_pessoas_ferias_status"},
                    {"nome": "Vencimentos de Férias (Criar/Excluir)", "view_name": ["rh:criar_vencimento_ferias", "rh:excluir_vencimento_ferias"], "perm": "core.nav_pessoas_ferias_vencimentos"},
                    {"nome": "Importar Férias", "view_name": ["rh:importar_ferias", "qms:importar_ferias", "dl_template_ferias"], "perm": "core.nav_pessoas_importar_ferias"},
                    {"nome": "Exportar Férias", "view_name": "rh:exportar_ferias", "perm": "core.nav_pessoas_exportar_ferias"},
                ],
            },
            {
                "key": "liderancas",
                "nome": "Lideranças",
                "perm": "core.nav_pessoas_liderancas_bloco",
                "funcoes": [
                    {"nome": "Lideranças", "view_name": "rh:atualizar_liderancas_em_massa", "perm": "core.nav_pessoas_liderancas"},
                    {"nome": "Importar Hierarquia", "view_name": ["qms:importar_hierarquia", "dl_template_hierarquia"], "perm": "core.nav_pessoas_importar_hierarquia"},
                ],
            },
            {
                "key": "ocorrencias",
                "nome": "Ocorrências",
                "perm": "core.nav_pessoas_ocorrencias_bloco",
                "funcoes": [
                    {"nome": "Ocorrências", "view_name": "listar_ocorrencias", "perm": "core.nav_pessoas_ocorrencias"},
                    {"nome": "Registrar Ocorrência", "view_name": "registrar_ocorrencia", "perm": "core.nav_pessoas_registrar_ocorrencia"},
                    {"nome": "Editar Ocorrência", "view_name": "editar_ocorrencia", "perm": "core.nav_pessoas_editar_ocorrencia"},
                    {"nome": "Deletar Ocorrência", "view_name": "deletar_ocorrencia", "perm": "core.nav_pessoas_deletar_ocorrencia"},
                ],
            },
            {
                "key": "horas_extras",
                "nome": "Horas Extras e Absenteísmo",
                "perm": "core.nav_pessoas_horas_extras",
                "funcoes": [
                    {"nome": "Planejamento de Horas Extras e Absenteísmo", "view_name": "rh:planejamento_hora_extra_list", "perm": "core.nav_pessoas_horas_extras_list"},
                    {"nome": "Novo Planejamento", "view_name": "rh:planejamento_hora_extra_create", "perm": "core.nav_pessoas_horas_extras_create"},
                    {"nome": "Editar Planejamento", "view_name": "rh:planejamento_hora_extra_edit", "perm": "core.nav_pessoas_horas_extras_edit"},
                    {"nome": "Excluir Planejamento", "view_name": "rh:planejamento_hora_extra_delete", "perm": "core.nav_pessoas_horas_extras_delete"},
                    {
                        "nome": "Motivos de Planejamento",
                        "view_name": [
                            "rh:motivo_planejamento_list",
                            "rh:motivo_planejamento_create",
                            "rh:motivo_planejamento_edit",
                            "rh:motivo_planejamento_delete",
                            "rh:api_create_motivo",
                        ],
                        "perm": "core.nav_pessoas_horas_extras_motivos",
                    },
                ],
            },
            {
                "key": "tratativa_ponto",
                "nome": "Tratativa de Falhas de Ponto",
                "perm": "core.nav_pessoas_tratativa_ponto_bloco",
                "funcoes": [
                    {
                        "nome": "Demandas & Cobranças de Ponto",
                        "view_name": [
                            "rh:demandas_falhas_ponto",
                            "rh:tratativa_falhas_ponto_demanda",
                            "rh:tratativa_falhas_ponto",
                            "rh:api_tratar_jornada",
                            "rh:api_confirmar_depara",
                        ],
                        "perm": "core.nav_pessoas_demandas_falhas_ponto",
                    },
                    {"nome": "Importar Relatório de Falhas (.xlsx)", "view_name": "rh:importar_falhas_ponto", "perm": "core.nav_pessoas_importar_falhas_ponto"},
                    {"nome": "Arquivar / Desarquivar Demanda", "view_name": "rh:api_alternar_status_demanda", "perm": "core.nav_pessoas_arquivar_demanda"},
                    {"nome": "Excluir Demanda (Permanente)", "view_name": "rh:api_excluir_demanda", "perm": "core.nav_pessoas_excluir_demanda"},
                ],
            },
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Registrar Férias de Qualquer Colaborador",
                        "perm": "core.nav_pessoas_registrar_ferias_todos",
                        "descricao": "Registra, edita e exclui férias de qualquer colaborador, sem depender da hierarquia.",
                    },
                    {
                        "nome": "Ver Todos os Colaboradores na Tratativa de Ponto",
                        "perm": "core.nav_pessoas_ponto_ver_todos",
                        "descricao": "Vê e trata as falhas de ponto de todos os colaboradores, não só da sua equipe.",
                    },
                    {
                        "nome": "Perfil RH/DP",
                        "perm": "core.nav_pessoas_perfil_rh",
                        "descricao": "Recebe as mesmas liberações do setor RH/DP/Qualidade: gestão, status e exportação de férias e registro, edição e exclusão de ocorrências de qualquer colaborador.",
                    },
                    {
                        "nome": "Ver Salário",
                        "perm": "core.nav_pessoas_ver_salario",
                        "descricao": "Exibe o salário na lista e no detalhe dos colaboradores que o usuário pode acessar.",
                    },
                    {
                        "nome": "Configurar Meses de Abono e Adiantamento de 13º",
                        "perm": "core.nav_pessoas_ferias_configuracao",
                        "descricao": "Altera os meses em que Abono Salarial e Adiantamento de 13º são permitidos no registro de férias.",
                    },
                ],
            },
        ],
    },
    {
        "key": "fornecedores",
        "nome": "Fornecedores",
        "cor": "secondary",
        "icone": "bi bi-truck",
        "module_perm": "core.nav_mod_fornecedores",
        "blocos": [
            {
                "key": "gestao",
                "nome": "Lista de Fornecedores",
                "perm": "core.nav_fornecedores_gestao",
                "funcoes": [
                    {
                        "nome": "Lista de Fornecedores",
                        "view_name": ["fornecedores:modulo", "fornecedores:hub", "fornecedores:fornecedor_list", "fornecedores:fornecedor_detail"],
                        "perm": "core.nav_fornecedores_lista",
                    },
                    {"nome": "Novo Fornecedor", "view_name": "fornecedores:fornecedor_create", "perm": "core.nav_fornecedores_novo"},
                    {"nome": "Editar Fornecedor", "view_name": "fornecedores:fornecedor_update", "perm": "core.nav_fornecedores_editar"},
                    {"nome": "Novo Documento", "view_name": "fornecedores:documento_create", "perm": "core.nav_fornecedores_documento_create"},
                    {"nome": "Remover Documento", "view_name": "fornecedores:documento_delete", "perm": "core.nav_fornecedores_documento_delete"},
                ],
            },
            {
                "key": "avaliacao",
                "nome": "Avaliações do Fornecedor",
                "perm": "core.nav_fornecedores_avaliacao",
                "funcoes": [
                    {"nome": "Avaliações e Reavaliações", "view_name": ["fornecedores:avaliacao_list", "fornecedores:reavaliacao_list"], "perm": "core.nav_fornecedores_avaliacoes"},
                    {"nome": "Nova Avaliação", "view_name": "fornecedores:avaliacao_create", "perm": "core.nav_fornecedores_avaliacao_create"},
                    {"nome": "Editar Avaliação", "view_name": "fornecedores:avaliacao_edit", "perm": "core.nav_fornecedores_avaliacao_edit"},
                    {"nome": "Criar Matriz de Avaliação", "view_name": "fornecedores:avaliacao_matriz_create", "perm": "core.nav_fornecedores_avaliacao_matriz"},
                    {"nome": "Criar Seleção", "view_name": "fornecedores:avaliacao_selecao_create", "perm": "core.nav_fornecedores_avaliacao_selecao"},
                    {"nome": "Nova Reavaliação", "view_name": ["fornecedores:reavaliacao_create", "fornecedores:avaliacao_reavaliacao_create"], "perm": "core.nav_fornecedores_reavaliacao_create"},
                    {"nome": "Deletar Reavaliação", "view_name": "fornecedores:reavaliacao_delete", "perm": "core.nav_fornecedores_reavaliacao_delete"},
                    {"nome": "Exportar Avaliações (Excel)", "view_name": "fornecedores:export_avaliacoes_excel", "perm": "core.nav_fornecedores_export_avaliacoes"},
                ],
            },
            {
                "key": "perguntas",
                "nome": "Perguntas de Avaliação",
                "perm": "core.nav_fornecedores_perguntas_bloco",
                "funcoes": [
                    {"nome": "Perguntas de Avaliação", "view_name": "fornecedores:pergunta_list", "perm": "core.nav_fornecedores_perguntas"},
                    {"nome": "Nova Pergunta", "view_name": "fornecedores:pergunta_create", "perm": "core.nav_fornecedores_pergunta_create"},
                    {"nome": "Editar Pergunta", "view_name": "fornecedores:pergunta_edit", "perm": "core.nav_fornecedores_pergunta_edit"},
                    {"nome": "Remover Pergunta", "view_name": "fornecedores:pergunta_delete", "perm": "core.nav_fornecedores_pergunta_delete"},
                ],
            },
        ],
    },
    {
        "key": "auditoria",
        "nome": "Auditoria",
        "cor": "info",
        "icone": "bi bi-clipboard2-check",
        "module_perm": "core.nav_mod_auditoria",
        "blocos": [
            {
                "key": "acoes",
                "nome": "Nova Auditoria",
                "perm": "core.nav_auditoria_nova_bloco",
                "funcoes": [
                    {"nome": "Nova Auditoria (Selecionar Modelo)", "view_name": "auditoria:selecionar_modelo_preenchimento", "perm": "core.nav_auditoria_nova"},
                    {"nome": "Avaliação de Dados", "view_name": ["auditoria:registro_create", "auditoria:registro_create_modelo"], "perm": "core.nav_auditoria_avaliacao"},
                ],
            },
            {
                "key": "cadastro",
                "nome": "Modelos de Auditoria",
                "perm": "core.nav_auditoria_cadastro",
                "funcoes": [
                    {"nome": "Modelos de Auditoria", "view_name": "auditoria:modelos_list", "perm": "core.nav_auditoria_modelos"},
                    {"nome": "Novo Modelo", "view_name": "auditoria:modelo_create", "perm": "core.nav_auditoria_novo_modelo"},
                    {"nome": "Editar Modelo", "view_name": "auditoria:modelo_edit", "perm": "core.nav_auditoria_editar_modelo"},
                    {"nome": "Duplicar Modelo", "view_name": "auditoria:modelo_duplicate", "perm": "core.nav_auditoria_duplicar_modelo"},
                    {"nome": "Remover Modelo", "view_name": "auditoria:modelo_delete", "perm": "core.nav_auditoria_remover_modelo"},
                    {"nome": "Encerrar/Arquivar Modelo", "view_name": ["auditoria:modelo_encerrar", "auditoria:modelo_arquivar"], "perm": "core.nav_auditoria_encerrar_modelo"},
                    {"nome": "Justificar Não Execução", "view_name": "auditoria:justificar_nao_execucao", "perm": "core.nav_auditoria_justificar_nao_execucao"},
                    {"nome": "Tópicos do Modelo", "view_name": ["auditoria:modelo_categorias", "auditoria:topico_delete", "auditoria:reorder_topicos"], "perm": "core.nav_auditoria_modelo_topicos"},
                ],
            },
            {
                "key": "perguntas",
                "nome": "Perguntas por Modelo",
                "perm": "core.nav_auditoria_perguntas_bloco",
                "funcoes": [
                    {"nome": "Perguntas por Modelo", "view_name": "auditoria:perguntas_list", "perm": "core.nav_auditoria_perguntas"},
                    {"nome": "Nova Pergunta", "view_name": "auditoria:pergunta_create", "perm": "core.nav_auditoria_nova_pergunta"},
                    {"nome": "Editar Pergunta", "view_name": "auditoria:pergunta_edit", "perm": "core.nav_auditoria_editar_pergunta"},
                    {"nome": "Duplicar Pergunta", "view_name": "auditoria:pergunta_duplicate", "perm": "core.nav_auditoria_duplicar_pergunta"},
                    {"nome": "Remover Pergunta", "view_name": "auditoria:pergunta_delete", "perm": "core.nav_auditoria_remover_pergunta"},
                    {"nome": "Ações em Massa (Tópico, Resposta)", "view_name": ["auditoria:perguntas_bulk_set_topico", "auditoria:perguntas_bulk_apply_resposta"], "perm": "core.nav_auditoria_perguntas_massa"},
                ],
            },
            {
                "key": "operacao",
                "nome": "Registros (Modelos Cadastrados / Período)",
                "perm": "core.nav_auditoria_operacao",
                "funcoes": [
                    {"nome": "Modelos Cadastrados / Período", "view_name": "auditoria:registros_list", "perm": "core.nav_auditoria_registros"},
                    {"nome": "Registros por Modelo", "view_name": ["auditoria:registros_por_modelo", "auditoria:registros_por_modelo_compartilhado"], "perm": "core.nav_auditoria_registros_por_modelo"},
                    {"nome": "Detalhe do Registro", "view_name": "auditoria:registro_detail", "perm": "core.nav_auditoria_detalhe_registro"},
                    {"nome": "Editar Registro", "view_name": ["auditoria:registro_edit", "auditoria:api_atualizar_resposta_inline"], "perm": "core.nav_auditoria_editar_registro"},
                    {"nome": "Excluir Registro", "view_name": "auditoria:registro_delete", "perm": "core.nav_auditoria_excluir_registro"},
                    {"nome": "Exportar Respostas (Excel)", "view_name": "auditoria:exportar_respostas_excel", "perm": "core.nav_auditoria_exportar_excel"},
                    {"nome": "Exportar Registro (PDF)", "view_name": "auditoria:registro_exportar_pdf", "perm": "core.nav_auditoria_exportar_pdf"},
                    {"nome": "Editar Comentário", "view_name": "auditoria:comentario_edit", "perm": "core.nav_auditoria_comentario_edit"},
                    {"nome": "Remover Comentário", "view_name": "auditoria:comentario_delete", "perm": "core.nav_auditoria_comentario_delete"},
                ],
            },
            {
                "key": "analise",
                "nome": "Dashboard Auditoria",
                "perm": "core.nav_auditoria_analise",
                "funcoes": [
                    {"nome": "Dashboard Auditoria", "view_name": "auditoria:dashboard", "perm": "core.nav_auditoria_dashboard"},
                ],
            },
            {
                "key": "iso_13485",
                "nome": "Modo Entrevista & Ferramentas",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_bloco",
                "funcoes": [
                    {"nome": "Modo Entrevista (Lista de Auditorias)", "view_name": "auditoria:iso_auditoria_list", "perm": "core.nav_auditoria_iso_lista"},
                    {
                        "nome": "Execução da Entrevista",
                        "view_name": [
                            "auditoria:iso_entrevista_view",
                            "auditoria:api_iso_autosave_resposta",
                            "auditoria:api_iso_marcar_nao_aplicavel",
                            "auditoria:api_iso_pontos_fortes_adicionar",
                            "auditoria:api_iso_pontos_fortes_remover", "auditoria:api_iso_pontos_fortes_listar"],
                        "perm": "core.nav_auditoria_iso_entrevista",
                    },
                    {
                        "nome": "Solicitações e Evidências",
                        "view_name": [
                            "auditoria:api_iso_solicitacao_create",
                            "auditoria:api_iso_solicitacao_update",
                            "auditoria:api_iso_solicitacao_delete",
                            "auditoria:api_iso_solicitacao_transferir",
                            "auditoria:api_iso_solicitacao_upload_imagem",
                            "auditoria:api_iso_solicitacao_delete_imagem",
                            "auditoria:api_iso_solicitacao_update_legenda_imagem", "auditoria:iso_imagem_solicitacao_arquivo"],
                        "perm": "core.nav_auditoria_iso_solicitacoes",
                    },
                    {"nome": "Painel de Revisão", "view_name": ["auditoria:iso_revisao_dashboard", "auditoria:api_iso_revisao_reverter", "auditoria:api_iso_revisao_criar_obs"], "perm": "core.nav_auditoria_iso_revisao"},
                    {"nome": "Matriz de Correlação", "view_name": "auditoria:iso_matriz_view", "perm": "core.nav_auditoria_iso_matriz"},
                    {"nome": "Cronograma & Horários", "view_name": ["auditoria:iso_auditoria_cronograma", "auditoria:api_iso_agenda_quick_edit", "auditoria:api_iso_agenda_ajustar_horario", "auditoria:api_iso_agenda_salvar_intervalo_evento", "auditoria:api_iso_agenda_criar_ajustada", "auditoria:api_iso_agenda_excluir_ajustada", "auditoria:api_iso_agenda_create_gap"], "perm": "core.nav_auditoria_iso_cronograma"},
                    {"nome": "Síntese da Auditoria", "view_name": ["auditoria:iso_auditoria_sintese", "auditoria:api_iso_sintese_salvar_secao"], "perm": "core.nav_auditoria_iso_sintese"},
                    {"nome": "Apresentação de Fechamento", "view_name": ["auditoria:iso_fechamento_presentation", "auditoria:api_iso_fechamento_salvar"], "perm": "core.nav_auditoria_iso_fechamento"},
                    {"nome": "Gestão de Amostras", "view_name": "auditoria:iso_gestao_amostras", "perm": "core.nav_auditoria_iso_amostras"},
                    {"nome": "Planos de Ação (CAPA)", "view_name": ["auditoria:iso_auditoria_capa", "auditoria:api_iso_capa_gerar_link", "auditoria:api_iso_capa_listar_links", "auditoria:api_iso_capa_revogar_link", "auditoria:api_iso_capa_revisar_solicitacao", "auditoria:iso_capa_evidencia_arquivo"], "perm": "core.nav_auditoria_iso_capa"},
                    {"nome": "Avaliação do Auditor & Feedback", "view_name": ["auditoria:api_iso_avaliacao_resumo", "auditoria:api_iso_avaliacao_gerar_link", "auditoria:api_iso_avaliacao_perguntas_list_create", "auditoria:api_iso_avaliacao_salvar_como_padrao", "auditoria:api_iso_avaliacao_perguntas_global_list_create", "auditoria:api_iso_avaliacao_pergunta_update_delete", "auditoria:api_iso_avaliacao_restaurar_padroes", "auditoria:api_iso_avaliacao_restaurar_padroes_global"], "perm": "core.nav_auditoria_iso_avaliacao"},
                    {"nome": "Analytics Executivo Global", "view_name": ["auditoria:iso_analytics_global", "auditoria:api_iso_analytics_global_data"], "perm": "core.nav_auditoria_iso_analytics"},
                    {"nome": "Exportar Relatórios (Excel/Word)", "view_name": ["auditoria:iso_auditoria_export_excel", "auditoria:iso_auditoria_export_docx", "auditoria:api_auditoria_exportar_planilha"], "perm": "core.nav_auditoria_iso_export"},
                ],
            },
            {
                "key": "iso_13485_setup",
                "nome": "Setup: Painel, Planejamento e Agendas",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_setup_bloco",
                "funcoes": [
                    {"nome": "Painel de Setup ISO", "view_name": "auditoria:iso_setup_dashboard", "perm": "core.nav_auditoria_iso_setup"},
                    {
                        "nome": "Planejamento e Agendas ISO",
                        "view_name": [
                            "auditoria:iso_auditoria_create",
                            "auditoria:iso_auditoria_detail",
                            "auditoria:iso_auditoria_edit",
                            "auditoria:iso_auditoria_import_modelo",
                            "auditoria:iso_auditoria_toggle_conclusao",
                            "auditoria:api_iso_auditoria_editar_planejamento",
                            "auditoria:iso_agenda_create",
                            "auditoria:iso_agenda_detail",
                            "auditoria:iso_agenda_edit",
                            "auditoria:iso_agenda_toggle_conclusao",
                            "auditoria:iso_agenda_perguntas_edit",
                            "auditoria:iso_agenda_pergunta_create",
                            "auditoria:iso_agenda_alvo_update",
                            "auditoria:iso_agenda_sincronizar_modelo",
                        ],
                        "perm": "core.nav_auditoria_iso_agendas",
                    },
                    {
                        "nome": "Arquivar/Excluir Auditorias e Agendas ISO",
                        "view_name": ["auditoria:iso_auditoria_archive", "auditoria:iso_auditoria_delete", "auditoria:iso_agenda_archive", "auditoria:iso_agenda_delete"],
                        "perm": "core.nav_auditoria_iso_agendas_delete",
                    },
                ],
            },
            {
                "key": "iso_normas",
                "nome": "Setup: Normas ISO",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_normas_bloco",
                "funcoes": [
                    {
                        "nome": "Normas ISO (Gestão e Templates)",
                        "view_name": [
                            "auditoria:iso_norma_create",
                            "auditoria:iso_norma_detail",
                            "auditoria:iso_norma_edit",
                            "auditoria:iso_norma_upload_template",
                            "auditoria:iso_norma_delete_template",
                            "auditoria:iso_norma_download_template",
                            "auditoria:iso_norma_download_template_padrao",
                            "auditoria:iso_norma_regras_salvar",
                        ],
                        "perm": "core.nav_auditoria_iso_normas",
                    },
                    {"nome": "Arquivar/Excluir Norma", "view_name": ["auditoria:iso_norma_archive", "auditoria:iso_norma_delete"], "perm": "core.nav_auditoria_iso_normas_delete"},
                ],
            },
            {
                "key": "iso_itens",
                "nome": "Setup: Itens da Norma",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_itens_bloco",
                "funcoes": [
                    {"nome": "Itens da Norma", "view_name": ["auditoria:iso_item_create", "auditoria:iso_item_edit", "auditoria:iso_item_detail_api", "auditoria:iso_item_toggle_atalho_api"], "perm": "core.nav_auditoria_iso_itens"},
                    {"nome": "Excluir Item da Norma", "view_name": "auditoria:iso_item_delete", "perm": "core.nav_auditoria_iso_itens_delete"},
                ],
            },
            {
                "key": "iso_perguntas",
                "nome": "Setup: Banco de Perguntas ISO",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_perguntas_bloco",
                "funcoes": [
                    {"nome": "Banco de Perguntas ISO", "view_name": ["auditoria:iso_pergunta_create", "auditoria:iso_pergunta_edit"], "perm": "core.nav_auditoria_iso_perguntas"},
                    {"nome": "Excluir Pergunta ISO", "view_name": "auditoria:iso_pergunta_delete", "perm": "core.nav_auditoria_iso_perguntas_delete"},
                ],
            },
            {
                "key": "iso_modelos",
                "nome": "Setup: Modelos e Blocos ISO",
                "grupo": "ISO 13485",
                "perm": "core.nav_auditoria_iso_modelos_bloco",
                "funcoes": [
                    {
                        "nome": "Modelos e Blocos ISO",
                        "view_name": [
                            "auditoria:iso_modelo_create",
                            "auditoria:iso_modelo_detail",
                            "auditoria:iso_modelo_edit",
                            "auditoria:iso_modelo_bloco_create",
                            "auditoria:iso_modelo_bloco_edit",
                            "auditoria:iso_modelo_bloco_perguntas",
                            "auditoria:iso_modelo_bloco_pergunta_create",
                            "auditoria:iso_modelo_bloco_sincronizar",
                            "auditoria:iso_modelo_bloco_alvo_update",
                        ],
                        "perm": "core.nav_auditoria_iso_modelos",
                    },
                    {
                        "nome": "Arquivar/Excluir Modelos e Blocos ISO",
                        "view_name": ["auditoria:iso_modelo_archive", "auditoria:iso_modelo_delete", "auditoria:iso_modelo_bloco_delete"],
                        "perm": "core.nav_auditoria_iso_modelos_delete",
                    },
                ],
            },
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Administrador de Auditoria",
                        "perm": "core.nav_auditoria_admin",
                        "descricao": "Vê e gerencia modelos, registros e comentários de qualquer responsável (sem precisar ser responsável ou autor).",
                    },
                    {
                        "nome": "Excluir Avaliação do Auditor (ISO)",
                        "view_name": ["auditoria:api_iso_avaliacao_excluir", "auditoria:api_iso_avaliacao_excluir_alias"],
                        "perm": "core.nav_auditoria_iso_avaliacao_excluir",
                        "descricao": "Exclui respostas individuais da avaliação do auditor recebidas pelo link público.",
                    },
                ],
            },
        ],
    },
    {
        "key": "laboratorio",
        "nome": "Laboratorio",
        "cor": "warning",
        "icone": "bi bi-eyedropper",
        "module_perm": "core.nav_mod_laboratorio",
        "blocos": [
            {
                "key": "ocorrencias_gerais",
                "grupo": "Ocorrências Gerais",
                "nome": "Observações Gerais",
                "perm": "core.nav_laboratorio_ocorrencias_gerais",
                "funcoes": [
                    {"nome": "Módulo de Observações Gerais", "view_name": "laboratorio:modulo", "perm": "core.nav_laboratorio_modulo"},
                ],
            },
            {
                "key": "ocorrencias",
                "grupo": "Ocorrências Gerais",
                "nome": "Ocorrências",
                "perm": "core.nav_laboratorio_ocorrencias_bloco",
                "funcoes": [
                    {"nome": "Listagem de Ocorrências", "view_name": "laboratorio:ocorrencias_list", "perm": "core.nav_laboratorio_lista_ocorrencias"},
                    {"nome": "Detalhe da Ocorrência", "view_name": "laboratorio:ocorrencia_detail", "perm": "core.nav_laboratorio_ocorrencia_detalhe"},
                    {"nome": "Nova Ocorrência", "view_name": "laboratorio:ocorrencia_create", "perm": "core.nav_laboratorio_nova_ocorrencia"},
                    {"nome": "Editar Ocorrência", "view_name": "laboratorio:ocorrencia_update", "perm": "core.nav_laboratorio_editar_ocorrencia"},
                    {"nome": "Registrar Anotações", "view_name": "laboratorio:ocorrencia_notes", "perm": "core.nav_laboratorio_ocorrencia_anotar"},
                    {"nome": "Encerrar Ocorrência", "view_name": "laboratorio:ocorrencia_close", "perm": "core.nav_laboratorio_ocorrencia_encerrar"},
                    {"nome": "Excluir Ocorrência", "view_name": "laboratorio:ocorrencia_delete", "perm": "core.nav_laboratorio_ocorrencia_delete"},
                ],
            },
            {
                "key": "categorias",
                "grupo": "Ocorrências Gerais",
                "nome": "Categorias de Ocorrência",
                "perm": "core.nav_laboratorio_categorias_bloco",
                "funcoes": [
                    {"nome": "Tabela de Categorias", "view_name": "laboratorio:categorias_list", "perm": "core.nav_laboratorio_categorias"},
                    {"nome": "Nova Categoria", "view_name": "laboratorio:categoria_create", "perm": "core.nav_laboratorio_categoria_create"},
                    {"nome": "Editar Categoria", "view_name": "laboratorio:categoria_update", "perm": "core.nav_laboratorio_categoria_update"},
                ],
            },
            {
                "key": "dashboard",
                "grupo": "Ocorrências Gerais",
                "nome": "Dashboard Laboratório",
                "perm": "core.nav_laboratorio_dashboard_bloco",
                "funcoes": [
                    {"nome": "Dashboard Laboratório", "view_name": "laboratorio:dashboard", "perm": "core.nav_laboratorio_dashboard"},
                    {"nome": "Exportar Dashboard (PDF)", "view_name": "laboratorio:dashboard_pdf", "perm": "core.nav_laboratorio_dashboard_pdf"},
                ],
            },
            {
                "key": "maquinas",
                "grupo": "Ocorrências Gerais > Configurações > Máquinas",
                "nome": "Cadastro de Máquinas",
                "perm": "core.nav_laboratorio_maquinas",
                "funcoes": [
                    {"nome": "Cadastro de Máquinas", "view_name": ["maquinas:maquinas_list", "maquinas:maquina_detail"], "perm": "core.nav_laboratorio_maquinas_lista"},
                    {"nome": "Nova Máquina", "view_name": "maquinas:maquina_create", "perm": "core.nav_laboratorio_maquina_create"},
                    {"nome": "Editar Máquina", "view_name": "maquinas:maquina_update", "perm": "core.nav_laboratorio_maquina_update"},
                    {"nome": "Excluir Máquina", "view_name": "maquinas:maquina_delete", "perm": "core.nav_laboratorio_maquina_delete"},
                ],
            },
            {
                "key": "maquinas_categorias",
                "grupo": "Ocorrências Gerais > Configurações > Máquinas",
                "nome": "Categorias de Máquinas",
                "perm": "core.nav_laboratorio_maquinas_categorias_bloco",
                "funcoes": [
                    {"nome": "Categorias de Máquinas", "view_name": "maquinas:categorias_list", "perm": "core.nav_laboratorio_maquinas_categorias"},
                    {"nome": "Nova Categoria de Máquina", "view_name": "maquinas:categoria_create", "perm": "core.nav_laboratorio_categoria_maquina_create"},
                    {"nome": "Editar Categoria de Máquina", "view_name": "maquinas:categoria_update", "perm": "core.nav_laboratorio_categoria_maquina_update"},
                    {"nome": "Excluir Categoria de Máquina", "view_name": "maquinas:categoria_delete", "perm": "core.nav_laboratorio_categoria_maquina_delete"},
                ],
            },
            {
                "key": "coating",
                "grupo": "HMC > Anti-Reflexo",
                "nome": "Coating: Painel Diário",
                "perm": "core.nav_laboratorio_coating",
                "funcoes": [
                    {"nome": "Painel Diário", "view_name": "laboratorio:coating_painel", "perm": "core.nav_laboratorio_coating_painel"},
                    {
                        "nome": "Editar Lançamentos (Células, Lotes, Observações, Manutenções)",
                        "view_name": [
                            "laboratorio:atualizar_celula_coating",
                            "laboratorio:editar_lote_completo_coating",
                            "laboratorio:api_editar_linha_coating",
                            "laboratorio:salvar_observacoes_lote",
                            "laboratorio:registrar_manutencao_coating",
                            "laboratorio:api_recalcular_turno_registro",
                        ],
                        "perm": "core.nav_laboratorio_coating_painel_editar",
                    },
                    {"nome": "Excluir Lote", "view_name": "laboratorio:registro_coating_delete", "perm": "core.nav_laboratorio_coating_registro_delete"},
                ],
            },
            {
                "key": "coating_dashboard",
                "grupo": "HMC > Anti-Reflexo",
                "nome": "Coating: Dashboard",
                "perm": "core.nav_laboratorio_coating_dashboard_bloco",
                "funcoes": [
                    {"nome": "Dashboard Coating", "view_name": "laboratorio:dashboard_coating", "perm": "core.nav_laboratorio_coating_dashboard"},
                ],
            },
            {
                "key": "coating_importacao",
                "grupo": "HMC > Anti-Reflexo",
                "nome": "Coating: Importação",
                "perm": "core.nav_laboratorio_coating_importacao_bloco",
                "funcoes": [
                    {"nome": "Importar Lotes", "view_name": ["laboratorio:importar_lotes_coating", "laboratorio:baixar_modelo_importacao_coating"], "perm": "core.nav_laboratorio_coating_importacao"},
                ],
            },
            {
                "key": "coating_tratamentos",
                "grupo": "HMC > Configurações",
                "nome": "Coating: Tratamentos",
                "perm": "core.nav_laboratorio_coating_tratamentos_bloco",
                "funcoes": [
                    {"nome": "Tratamentos", "view_name": "laboratorio:tratamento_list", "perm": "core.nav_laboratorio_coating_tratamentos"},
                    {"nome": "Novo Tratamento", "view_name": "laboratorio:tratamento_create", "perm": "core.nav_laboratorio_coating_tratamento_create"},
                    {"nome": "Editar Tratamento", "view_name": "laboratorio:tratamento_update", "perm": "core.nav_laboratorio_coating_tratamento_update"},
                ],
            },
            {
                "key": "coating_turnos",
                "grupo": "HMC > Configurações",
                "nome": "Coating: Regras de Turno",
                "perm": "core.nav_laboratorio_coating_turnos_bloco",
                "funcoes": [
                    {"nome": "Regras de Turno", "view_name": "laboratorio:regra_turno_list", "perm": "core.nav_laboratorio_coating_turnos"},
                    {"nome": "Nova Regra de Turno", "view_name": "laboratorio:regra_turno_create", "perm": "core.nav_laboratorio_coating_turno_create"},
                    {"nome": "Editar Regra de Turno", "view_name": "laboratorio:regra_turno_update", "perm": "core.nav_laboratorio_coating_turno_update"},
                ],
            },
            {
                "key": "coating_ciclos",
                "grupo": "HMC > Configurações",
                "nome": "Coating: Ciclos de Manutenção",
                "perm": "core.nav_laboratorio_coating_ciclos_bloco",
                "funcoes": [
                    {"nome": "Ciclos de Manutenção", "view_name": "laboratorio:ciclo_coating_list", "perm": "core.nav_laboratorio_coating_ciclos"},
                    {"nome": "Novo Ciclo", "view_name": "laboratorio:ciclo_coating_create", "perm": "core.nav_laboratorio_coating_ciclo_create"},
                    {
                        "nome": "Editar Ciclo (Checklist, Ordem, Ativação)",
                        "view_name": [
                            "laboratorio:ciclo_coating_update",
                            "laboratorio:configurar_checklist_ciclo",
                            "laboratorio:api_reordenar_ciclos",
                            "laboratorio:api_toggle_ciclo_ativo",
                        ],
                        "perm": "core.nav_laboratorio_coating_ciclo_update",
                    },
                    {"nome": "Copiar Ciclos", "view_name": "laboratorio:copiar_ciclos_coating", "perm": "core.nav_laboratorio_coating_ciclo_copy"},
                    {"nome": "Excluir Ciclo", "view_name": "laboratorio:ciclo_coating_delete", "perm": "core.nav_laboratorio_coating_ciclo_delete"},
                ],
            },
            {
                "key": "coating_equipe",
                "grupo": "HMC > Configurações",
                "nome": "Coating: Equipe",
                "perm": "core.nav_laboratorio_coating_equipe_bloco",
                "funcoes": [
                    {"nome": "Equipe HMC (Preparação, Montagem, Controle Final e HC)", "view_name": ["laboratorio:equipe_coating_list", "laboratorio:cf_colaboradores_busca"], "perm": "core.nav_laboratorio_coating_equipe"},
                    {"nome": "Editar Membro da Equipe", "view_name": "laboratorio:equipe_coating_update", "perm": "core.nav_laboratorio_coating_equipe_update"},
                    {"nome": "Excluir Membro da Equipe", "view_name": "laboratorio:equipe_coating_delete", "perm": "core.nav_laboratorio_coating_equipe_delete"},
                ],
            },
            {
                "key": "hc_dashboard",
                "grupo": "HMC > HC",
                "nome": "HC: Dashboard de Rendimento",
                "perm": "core.nav_laboratorio_hc_dashboard_bloco",
                "funcoes": [
                    {"nome": "Dashboard Rendimento HC", "view_name": "laboratorio:hc_dashboard", "perm": "core.nav_laboratorio_hc_dashboard"},
                    {"nome": "Dashboard Rendimento HC: Dia Hora a Hora", "view_name": "laboratorio:hc_dia_hora", "perm": "core.nav_laboratorio_hc_dia_hora"},
                ],
            },
            {
                "key": "hc_registros",
                "grupo": "HMC > HC",
                "nome": "HC: Formulário e Registros",
                "perm": "core.nav_laboratorio_hc_registros_bloco",
                "funcoes": [
                    {"nome": "Registros de Rendimento", "view_name": ["laboratorio:hc_registros", "laboratorio:hc_registro_detalhe"], "perm": "core.nav_laboratorio_hc_registros"},
                    {"nome": "Novo Lançamento de Rendimento", "view_name": "laboratorio:hc_registro_create", "perm": "core.nav_laboratorio_hc_registro_create"},
                    {"nome": "Editar Lançamento de Rendimento", "view_name": "laboratorio:hc_registro_update", "perm": "core.nav_laboratorio_hc_registro_update"},
                    {"nome": "Excluir Lançamento de Rendimento", "view_name": "laboratorio:hc_registro_delete", "perm": "core.nav_laboratorio_hc_registro_delete"},
                    {"nome": "Importar Planilha de Rendimento HC", "view_name": ["laboratorio:hc_importar", "laboratorio:hc_importar_preview", "laboratorio:hc_modelo"], "perm": "core.nav_laboratorio_hc_importar"},
                    {"nome": "Exportar Registros de Rendimento HC (planilha)", "view_name": "laboratorio:hc_exportar", "perm": "core.nav_laboratorio_hc_exportar"},
                ],
            },
            {
                "key": "hc_campos",
                "grupo": "HMC > Configurações",
                "nome": "HC: Campos do Formulário",
                "perm": "core.nav_laboratorio_hc_campos_bloco",
                "funcoes": [
                    {"nome": "Campos do Formulário", "view_name": "laboratorio:hc_config_campos", "perm": "core.nav_laboratorio_hc_campos"},
                    {"nome": "Salvar/Reordenar Campos e Meta", "view_name": ["laboratorio:hc_campo_save", "laboratorio:hc_campo_mover", "laboratorio:hc_config_meta"], "perm": "core.nav_laboratorio_hc_campo_save"},
                    {"nome": "Excluir Campo do Formulário", "view_name": "laboratorio:hc_campo_delete", "perm": "core.nav_laboratorio_hc_campo_delete"},
                ],
            },
            {
                "key": "hc_cadastros",
                "grupo": "HMC > Configurações",
                "nome": "HC: Cadastros Base",
                "perm": "core.nav_laboratorio_hc_cadastros_bloco",
                "funcoes": [
                    {"nome": "Cadastros Base (garras, materiais, motivos, equipe)", "view_name": "laboratorio:hc_config_cadastros", "perm": "core.nav_laboratorio_hc_cadastros"},
                    {"nome": "Salvar Cadastro Base / Membro da Equipe HC", "view_name": ["laboratorio:hc_cadastro_save", "laboratorio:hc_equipe_save"], "perm": "core.nav_laboratorio_hc_cadastro_save"},
                    {"nome": "Excluir Cadastro Base / Membro da Equipe HC", "view_name": ["laboratorio:hc_cadastro_delete", "laboratorio:hc_equipe_delete"], "perm": "core.nav_laboratorio_hc_cadastro_delete"},
                ],
            },
            {
                "key": "hc_integracoes",
                "grupo": "HMC > Configurações",
                "nome": "HC: Integrações e Sincronização",
                "perm": "core.nav_laboratorio_hc_integracoes_bloco",
                "funcoes": [
                    {"nome": "Integrações com cadastros do HMC e RH", "view_name": "laboratorio:hc_config_integracoes", "perm": "core.nav_laboratorio_hc_integracoes"},
                    {"nome": "Sincronizar Equipe / Vincular Nomes", "view_name": ["laboratorio:hc_sincronizar", "laboratorio:hc_vincular_nome"], "perm": "core.nav_laboratorio_hc_sincronizar"},
                ],
            },
            {
                "key": "cf_dashboard",
                "grupo": "HMC > Controle Final",
                "nome": "CF: Dashboard de Retrabalho",
                "perm": "core.nav_laboratorio_cf_dashboard_bloco",
                "funcoes": [
                    {"nome": "Dashboard Retrabalho CF", "view_name": "laboratorio:cf_dashboard", "perm": "core.nav_laboratorio_cf_dashboard"},
                    {"nome": "Dashboard Retrabalho CF: Dia Hora a Hora", "view_name": "laboratorio:cf_dia_hora", "perm": "core.nav_laboratorio_cf_dia_hora"},
                ],
            },
            {
                "key": "cf_registros",
                "grupo": "HMC > Controle Final",
                "nome": "CF: Formulário e Registros",
                "perm": "core.nav_laboratorio_cf_registros_bloco",
                "funcoes": [
                    {"nome": "Registros de Retrabalho", "view_name": ["laboratorio:cf_registros", "laboratorio:cf_registro_detalhe"], "perm": "core.nav_laboratorio_cf_registros"},
                    {"nome": "Novo Lançamento de Retrabalho", "view_name": "laboratorio:cf_registro_create", "perm": "core.nav_laboratorio_cf_registro_create"},
                    {"nome": "Editar Lançamento de Retrabalho", "view_name": "laboratorio:cf_registro_update", "perm": "core.nav_laboratorio_cf_registro_update"},
                    {"nome": "Excluir Lançamento de Retrabalho", "view_name": "laboratorio:cf_registro_delete", "perm": "core.nav_laboratorio_cf_registro_delete"},
                    {"nome": "Importar Planilha de Retrabalho CF", "view_name": ["laboratorio:cf_importar", "laboratorio:cf_importar_preview", "laboratorio:cf_modelo"], "perm": "core.nav_laboratorio_cf_importar"},
                    {"nome": "Exportar Registros de Retrabalho CF (planilha)", "view_name": "laboratorio:cf_exportar", "perm": "core.nav_laboratorio_cf_exportar"},
                ],
            },
            {
                "key": "cf_campos",
                "grupo": "HMC > Configurações",
                "nome": "CF: Campos do Formulário",
                "perm": "core.nav_laboratorio_cf_campos_bloco",
                "funcoes": [
                    {"nome": "Campos do Formulário CF", "view_name": "laboratorio:cf_config_campos", "perm": "core.nav_laboratorio_cf_campos"},
                    {"nome": "Salvar/Reordenar Campos e Meta CF", "view_name": ["laboratorio:cf_campo_save", "laboratorio:cf_campo_mover", "laboratorio:cf_config_meta"], "perm": "core.nav_laboratorio_cf_campo_save"},
                    {"nome": "Excluir Campo do Formulário CF", "view_name": "laboratorio:cf_campo_delete", "perm": "core.nav_laboratorio_cf_campo_delete"},
                ],
            },
            {
                "key": "cf_cadastros",
                "grupo": "HMC > Configurações",
                "nome": "CF: Cadastros Base",
                "perm": "core.nav_laboratorio_cf_cadastros_bloco",
                "funcoes": [
                    {"nome": "Cadastros Base CF (motivos, reprovação, equipe)", "view_name": "laboratorio:cf_config_cadastros", "perm": "core.nav_laboratorio_cf_cadastros"},
                    {"nome": "Salvar Cadastro Base / Membro da Equipe CF", "view_name": ["laboratorio:cf_cadastro_save", "laboratorio:cf_equipe_save"], "perm": "core.nav_laboratorio_cf_cadastro_save"},
                    {"nome": "Excluir Cadastro Base / Membro da Equipe CF", "view_name": ["laboratorio:cf_cadastro_delete", "laboratorio:cf_equipe_delete"], "perm": "core.nav_laboratorio_cf_cadastro_delete"},
                ],
            },
            {
                "key": "cf_integracoes",
                "grupo": "HMC > Configurações",
                "nome": "CF: Integrações e Sincronização",
                "perm": "core.nav_laboratorio_cf_integracoes_bloco",
                "funcoes": [
                    {"nome": "Integrações CF com HMC e RH", "view_name": "laboratorio:cf_config_integracoes", "perm": "core.nav_laboratorio_cf_integracoes"},
                    {"nome": "Sincronizar Equipe CF / Vincular Nomes", "view_name": ["laboratorio:cf_sincronizar", "laboratorio:cf_vincular", "laboratorio:cf_criar_tratamento"], "perm": "core.nav_laboratorio_cf_sincronizar"},
                ],
            },
            {
                "key": "tms",
                "grupo": "Ferramentas Auxiliares > Tempos e Movimentos (TMS)",
                "nome": "TMS - Tempos e Movimentos",
                "perm": "core.nav_laboratorio_tms_bloco",
                "funcoes": [
                    {"nome": "Previsão de Produção & Gargalos", "view_name": ["laboratorio:tms_dashboard", "laboratorio:api_tms_simular"], "perm": "core.nav_laboratorio_tms_dashboard"},
                    {"nome": "Linhas de Produção", "view_name": ["laboratorio:tms_fluxos_list", "laboratorio:tms_fluxo_create", "laboratorio:tms_fluxo_update", "laboratorio:tms_fluxo_delete", "laboratorio:tms_fluxo_duplicar", "laboratorio:tms_carregar_exemplo"], "perm": "core.nav_laboratorio_tms_fluxos"},
                    {"nome": "Etapas e Balanceamento", "view_name": ["laboratorio:tms_etapas_list", "laboratorio:tms_etapa_create", "laboratorio:tms_etapa_update", "laboratorio:tms_etapa_delete", "laboratorio:api_tms_reordenar_etapas", "laboratorio:tms_exportar_excel"], "perm": "core.nav_laboratorio_tms_etapas"},
                ],
            },
            {
                "key": "homologacoes",
                "grupo": "Qualidade > Homologações",
                "nome": "Homologações de Tratamentos",
                "perm": "core.nav_laboratorio_homologacoes_bloco",
                "funcoes": [
                    {"nome": "Acompanhamento de Homologações", "view_name": "laboratorio:homologacoes_resumo", "perm": "core.nav_laboratorio_homologacoes"},
                    {"nome": "Novo Plano de Testes", "view_name": "laboratorio:homologacao_plano_create", "perm": "core.nav_laboratorio_homologacao_create"},
                    {"nome": "Importar Planilha de Homologações", "view_name": "laboratorio:homologacoes_importar", "perm": "core.nav_laboratorio_homologacao_importar"},
                    {"nome": "Detalhar e Atualizar Plano de Testes", "view_name": "laboratorio:homologacao_plano_detail", "perm": "core.nav_laboratorio_homologacao_detail"},
                    {"nome": "Excluir Plano de Testes", "view_name": "laboratorio:homologacao_plano_delete", "perm": "core.nav_laboratorio_homologacao_delete"},
                ],
            },
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Encerrar Ocorrência de Qualquer Usuário",
                        "perm": "core.nav_laboratorio_encerrar_qualquer_ocorrencia",
                        "descricao": "Encerra ocorrências criadas por outras pessoas (sem a permissão, só quem criou pode encerrar).",
                    },
                    {
                        "nome": "Recalcular Turnos de Todos os Lotes",
                        "perm": "core.nav_laboratorio_coating_recalcular_todos",
                        "descricao": "Reprocessa o turno de todos os lotes de Coating com base nas regras de turno ativas.",
                    },
                ],
            },
        ],
    },
    {
        "key": "usuarios",
        "nome": "Usuários",
        "cor": "dark",
        "icone": "bi bi-person-gear",
        "module_perm": "core.nav_mod_usuarios",
        "blocos": [
            {
                "key": "gestao",
                "nome": "Lista de Usuários",
                "perm": "core.nav_usuarios_lista_bloco",
                "funcoes": [
                    # Detalhe, criação, permissões e 2FA seguem restritos a superuser/staff no código (de propósito).
                    {"nome": "Lista de Usuários", "view_name": "rh:listar_usuarios", "perm": "core.nav_usuarios_lista"},
                ],
            }
        ],
    },
    {
        "key": "global",
        "nome": "Permissões Globais",
        "cor": "secondary",
        "icone": "bi bi-globe2",
        # Sem "No menu": regras transversais, válidas em vários módulos.
        "module_perm": None,
        "blocos": [
            {
                "key": "especiais",
                "nome": "PERMISSÕES ESPECIAIS",
                "especial": True,
                "perm": None,
                "funcoes": [
                    {
                        "nome": "Ver Todos os Colaboradores",
                        "perm": "core.nav_pessoas_ver_todos_colaboradores",
                        "descricao": "Enxerga todos os colaboradores em Pessoas (lista, detalhe e salários) e recebe no Inbox/Notificações as pendências de todos, não só da sua equipe.",
                    },
                    {
                        "nome": "Exibir Botões de Ações em Tabelas",
                        "view_name": "exibir_botoes_acoes",
                        "perm": "core.nav_global_action_buttons",
                        "descricao": "Exibe as colunas de ações (ver/editar) em tabelas que, por padrão, só mostram ações ao responsável.",
                    },
                ],
            },
        ],
    },
]


# ==============================================================================
# GRUPOS (seções/subseções do menu) COM CHAVE MESTRA PRÓPRIA ("No menu")
# ==============================================================================
# Todo card do painel de permissões tem a sua flag. Um grupo desligado esconde o menu e bloqueia
# (middleware / has_view_access) todos os blocos e funções que estão dentro dele.
# Chave: caminho "A > B > C" do campo "grupo" dos blocos. "Gestão" é o módulo de exibição que reúne
# Ferramentas Auxiliares (TMS, Quadros, Diagramas), Processos e Qualidade.
# Quadros e Diagramas já têm a flag do próprio módulo (nav_mod_boards / nav_mod_diagramas).
GESTAO_GROUP = "Gestão"
NAV_GROUP_PERMS = {
    GESTAO_GROUP: "core.nav_mod_gestao",
    "Ferramentas Auxiliares": "core.nav_gestao_ferramentas",
    "Ferramentas Auxiliares > Tempos e Movimentos (TMS)": "core.nav_gestao_tms",
    "KPI": "core.nav_gestao_kpi",
    "Processos": "core.nav_gestao_processos",
    "Processos > PCP": "core.nav_gestao_pcp",
    "Processos > Motivos de Perdas": "core.nav_gestao_motivos_perdas",
    "Qualidade": "core.nav_gestao_qualidade",
    "Qualidade > Homologações": "core.nav_gestao_homologacoes",
    "ISO 13485": "core.nav_auditoria_iso_grupo",
    "Ocorrências Gerais": "core.nav_laboratorio_grupo_ocorrencias_gerais",
    "Ocorrências Gerais > Configurações": "core.nav_laboratorio_grupo_ocorrencias_config",
    "Ocorrências Gerais > Configurações > Máquinas": "core.nav_laboratorio_grupo_maquinas",
    "HMC": "core.nav_laboratorio_grupo_hmc",
    "HMC > Anti-Reflexo": "core.nav_laboratorio_grupo_hmc_ar",
    "HMC > HC": "core.nav_laboratorio_grupo_hmc_hc",
    "HMC > Controle Final": "core.nav_laboratorio_grupo_hmc_cf",
    "HMC > Configurações": "core.nav_laboratorio_grupo_hmc_config",
}
# Seções do módulo de exibição "Gestão" e módulos inteiros exibidos dentro dele.
GESTAO_SECOES = ("Ferramentas Auxiliares", "KPI", "Processos", "Qualidade")
# Módulos cujos blocos (campo "grupo") aparecem dentro de uma seção de Gestão.
GESTAO_MODULOS_COM_SECAO = ("laboratorio", "kpi", "pcp", "perdas")
GESTAO_MODULES = {"boards": "Ferramentas Auxiliares", "diagramas": "Ferramentas Auxiliares"}


def _group_paths(module_key: str, grupo: str | None) -> list[str]:
    """Caminhos de grupo (do mais externo ao mais interno) que contêm um item."""
    partes = [p.strip() for p in (grupo or GESTAO_MODULES.get(module_key, "")).split(">") if p.strip()]
    if module_key in GESTAO_MODULES or (partes and partes[0] in GESTAO_SECOES and module_key in GESTAO_MODULOS_COM_SECAO):
        caminhos = [GESTAO_GROUP]
    else:
        caminhos = []
    for i in range(len(partes)):
        caminhos.append(" > ".join(partes[: i + 1]))
    return caminhos


def get_block_group_perms(module_key: str, bloco: dict) -> list[str]:
    """Flags de grupo (core.nav_*) exigidas para o bloco e suas funções."""
    return [NAV_GROUP_PERMS[c] for c in _group_paths(module_key, bloco.get("grupo")) if c in NAV_GROUP_PERMS]


def get_nav_group_requirements() -> dict[str, list[str]]:
    """codename -> codenames das flags de grupo exigidas (módulos de Gestão, grupos aninhados, blocos e funções)."""

    def cn(full):
        return str(full).split(".", 1)[1]

    req: dict[str, list[str]] = {}
    for caminho, perm in NAV_GROUP_PERMS.items():
        if caminho == GESTAO_GROUP:
            req[cn(perm)] = []
            continue
        pais = [NAV_GROUP_PERMS[c] for c in _group_paths("laboratorio", caminho)[:-1] if c in NAV_GROUP_PERMS]
        req[cn(perm)] = [cn(p) for p in pais]
    for modulo in NAV_STRUCTURE:
        key = modulo.get("key")
        if key in GESTAO_MODULES and modulo.get("module_perm"):
            req[cn(modulo["module_perm"])] = [cn(p) for p in get_block_group_perms(key, {})]
        for bloco in modulo.get("blocos") or []:
            grupos = [cn(p) for p in get_block_group_perms(key, bloco)]
            if not grupos:
                continue
            if bloco.get("perm"):
                req[cn(bloco["perm"])] = grupos
            for func in bloco.get("funcoes") or []:
                if func.get("perm") and not bloco.get("especial"):
                    req[cn(func["perm"])] = grupos
    return req


def filter_codenames_by_groups(codenames: set[str]) -> set[str]:
    """Remove codenames cujas flags de grupo (seção do menu) não estão no conjunto."""
    req = get_nav_group_requirements()
    return {c for c in codenames if all(r in codenames for r in req.get(c, []))}


def get_nav_structure():
    return list(NAV_STRUCTURE)


def _nav_module_config(module_key: str):
    for item in NAV_STRUCTURE:
        if item.get("key") == module_key:
            return item
    return None


def get_view_permission_map() -> dict[str, dict[str, str]]:
    """Retorna um mapa: view_name -> {perm, module}.

    Modelo caso-a-caso:
    - Cada função (view) tem sua própria permissão `core.nav_*`.
    - Módulo/bloco controlam visibilidade no menu; não concedem automaticamente
      permissão de acessar funções.
    """
    result: dict[str, dict[str, str]] = {}
    for module in NAV_STRUCTURE:
        module_key = module.get("key")
        for bloco in module.get("blocos") or []:
            for func in bloco.get("funcoes") or []:
                view_name = func.get("view_name")
                perm = func.get("perm")
                if not view_name or not perm:
                    continue

                entry = {"perm": perm, "module": module_key}
                grupos = get_block_group_perms(module_key, bloco)
                if grupos:
                    entry["grupos"] = grupos

                # Suporta aliases: view_name pode ser uma lista/tupla/set de nomes.
                if isinstance(view_name, (list, tuple, set)):
                    for vn in view_name:
                        if vn:
                            result[vn] = dict(entry)
                else:
                    result[view_name] = dict(entry)
    return result


VIEW_NAME_TO_PERMISSION = get_view_permission_map()


def _has_legacy_module_group_access(user, module_key: str) -> bool:
    module_info = MODULES_PERMISSIONS.get(module_key)
    if not user or not module_info:
        return False

    try:
        group = Group.objects.get(name=module_info["name"])
    except Group.DoesNotExist:
        return False

    return user.groups.filter(id=group.id).exists()


def _user_has_direct_perm(user, full_perm: str | None) -> bool:
    """Checa permissão APENAS nas permissões diretas do usuário (não considera grupos).

    Usado para permissões `core.nav_*`, pois o painel de permissões manipula
    `user.user_permissions` (e não permissões de grupos). Assim, evita o cenário
    em que o toggle está desligado mas um grupo ainda concede acesso.
    """
    if not user or not full_perm or "." not in str(full_perm):
        return False

    app_label, codename = str(full_perm).split(".", 1)
    if not app_label or not codename:
        return False

    try:
        return user.user_permissions.filter(
            content_type__app_label=app_label,
            codename=codename,
        ).exists()
    except Exception:
        return False


def _user_has_nav_perm(user, full_perm: str | None) -> bool:
    """Checa permissões de navegação (core.nav_*) de forma consistente.

    Regra:
    - core.nav_*: somente permissões diretas do usuário (não grupos)
    - demais: usar user.has_perm (inclui grupos)
    """
    if not full_perm or "." not in str(full_perm):
        return False
    app_label, codename = str(full_perm).split(".", 1)
    if app_label == "core" and str(codename).startswith("nav_"):
        return _user_has_direct_perm(user, full_perm)
    return bool(user and user.has_perm(full_perm))


def is_legacy_module_transition_mode(user, module_key: str) -> bool:
    """Indica se o usuário ainda depende do grupo legado para entrar no módulo.

    Nesse cenário, mantemos as funções não destrutivas disponíveis até que o
    flag `nav_mod_*` seja explicitamente atribuído ao usuário.
    """
    if not user or not module_key:
        return False

    return bool(
        _has_legacy_module_group_access(user, module_key)
        and not has_module_nav_flag(user, module_key)
    )


def user_has_any_nav_perm_for_module(user, module_key: str) -> bool:
    """Indica se o usuário já está 'configurado' no novo modelo para o módulo."""
    module = _nav_module_config(module_key)
    if not module:
        return False
    module_perm = module.get("module_perm")
    if module_perm and _user_has_nav_perm(user, module_perm):
        return True
    for bloco in module.get("blocos") or []:
        block_perm = bloco.get("perm")
        if block_perm and _user_has_nav_perm(user, block_perm):
            return True
        for func in bloco.get("funcoes") or []:
            func_perm = func.get("perm")
            if func_perm and _user_has_nav_perm(user, func_perm):
                return True
    return False


def has_module_nav_flag(user, module_key: str) -> bool:
    module = _nav_module_config(module_key)
    if not module:
        return False
    return bool(_user_has_nav_perm(user, module.get("module_perm")))


def has_block_nav_flag(user, module_key: str, block_key: str) -> bool:
    module = _nav_module_config(module_key)
    if not module:
        return False
    for bloco in module.get("blocos") or []:
        if bloco.get("key") == block_key:
            return bool(_user_has_nav_perm(user, bloco.get("perm")))
    return False


def has_group_nav_flag(user, group_path: str) -> bool:
    """Flag "No menu" de uma seção/subseção do menu (ver NAV_GROUP_PERMS)."""
    perm = NAV_GROUP_PERMS.get(group_path)
    return bool(perm and _user_has_nav_perm(user, perm))


def has_view_access(user, view_name: str) -> bool:
    """Valida acesso a uma função (view_name).

    Regras:
    - Superuser/staff: True
    - Se view não estiver mapeada: True (não controlamos)
    - Se usuário está em modo legado (grupo do módulo) e não tem nenhum nav_* do módulo: True
    - Caso contrário: exige permissão nav_* da função
    """
    if not user:
        return False

    if user.is_superuser or user.is_staff:
        return True

    data = VIEW_NAME_TO_PERMISSION.get(view_name)
    if not data:
        return True

    module_key = data.get("module")
    required_perm = data.get("perm")

    # Cada seção do menu (grupo) tem a sua flag "No menu": desligada, bloqueia tudo o que está dentro dela.
    for group_perm in data.get("grupos") or []:
        if not _user_has_nav_perm(user, group_perm):
            return False

    def _is_destructive_nav_perm(full_perm: str | None) -> bool:
        if not full_perm or "." not in str(full_perm):
            return False
        codename = str(full_perm).split(".", 1)[1]
        destructive_keywords = (
            "delete",
            "deletar",
            "remover",
            "remove",
            "excluir",
            "mass_delete",
            "bulk_delete",
        )
        return any(key in codename for key in destructive_keywords)

    # Legado/transição: exige permissão estrita agora, conforme solicitado pelo usuário
    if module_key and is_legacy_module_transition_mode(user, module_key):
        return bool(required_perm and _user_has_nav_perm(user, required_perm))

    # Novo modelo (usuário já está "configurado" no nav_*):
    # Se o flag do módulo estiver ativo (nav_mod_*), antes permitíamos acesso às funções NÃO destrutivas.
    # Agora, para garantir controle subseção por subseção, exigimos a permissão sempre.
    if module_key and has_module_nav_flag(user, module_key):
        return bool(required_perm and _user_has_nav_perm(user, required_perm))

    return bool(required_perm and _user_has_nav_perm(user, required_perm))

def setup_module_groups():
    """
    Cria grupos de permissões para cada módulo.
    Execute esto com: python manage.py shell < setup_permissions.py
    ou via comando customizado: python manage.py setup_module_groups
    """
    from django.apps import apps

    for module_key, module_info in MODULES_PERMISSIONS.items():
        # Evita poluir logs (e criar grupos vazios) para apps que não estão instalados.
        # Ex.: o módulo legado `procurements` pode não existir após a unificação em `procedures`.
        if not apps.is_installed(module_key):
            print(
                f"[Aviso] Módulo não instalado: {module_key}. "
                f"Pulando criação/atualização do grupo '{module_info['name']}'."
            )
            continue

        group, created = Group.objects.get_or_create(name=module_info['name'])
        
        # Limpar permissões antigas
        group.permissions.clear()
        
        # Adicionar novas permissões
        for perm_codename in module_info['permissions']:
            try:
                # Tentar obter a permissão
                perm = Permission.objects.get(
                    content_type__app_label=module_key,
                    codename=perm_codename
                )
                group.permissions.add(perm)
            except (Permission.DoesNotExist, ValueError):
                print(f"[Aviso] Permissão não encontrada: {module_key}.{perm_codename}")
        
        status = "[Criado]" if created else "[Atualizado]"
        print(f"{status}: Grupo '{group.name}' com {group.permissions.count()} permissões")

def get_module_key(view_module):
    """
    Extrai o módulo (chave) a partir do caminho do módulo da view.
    Ex: 'metrologia.views.novo_fluxo_cotacao' -> 'metrologia'
    """
    return view_module.split('.')[0] if '.' in view_module else view_module

def is_admin_user(user) -> bool:
    """Superusuário ou staff: mesma regra da navbar e de has_view_access."""
    return bool(user and getattr(user, "is_authenticated", False) and (user.is_superuser or user.is_staff))


def user_has_nav_perm(user, full_perm: str) -> bool:
    """Regra única para views: admin (superusuário/staff) ou permissão direta `core.nav_*`
    concedida no painel de permissões (grupos não contam, como no menu e no middleware)."""
    return is_admin_user(user) or _user_has_nav_perm(user, full_perm)


def nav_permission_required(full_perm: str):
    """Decorator equivalente a @permission_required(raise_exception=True), com a regra de user_has_nav_perm."""
    from functools import wraps

    from django.core.exceptions import PermissionDenied

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not user_has_nav_perm(request.user, full_perm):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def has_module_access(user, module_key):
    """
    Verifica se um usuário tem acesso a um módulo.
    Returns: Boolean
    """
    if user.is_superuser or user.is_staff:
        return True

    # Novo modelo: permissão nav do módulo
    module = _nav_module_config(module_key)
    if module:
        module_perm = module.get("module_perm")
        if module_perm and _user_has_nav_perm(user, module_perm):
            return True

        if _has_legacy_module_group_access(user, module_key):
            return True

        return False

    # Legado: acesso via grupo
    return _has_legacy_module_group_access(user, module_key)

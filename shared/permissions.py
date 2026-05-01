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
    'insumos': {
        'name': 'Insumos',
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
NAV_STRUCTURE = [
    {
        "key": "metrologia",
        "nome": "Metrologia",
        "cor": "success",
        "icone": "bi bi-tools",
        "module_perm": "core.nav_mod_metrologia",
        "blocos": [
            {
                "key": "visao_geral",
                "nome": "VISÃO GERAL",
                "perm": "core.nav_metrologia_visao_geral",
                "funcoes": [
                    {
                        "nome": "Dashboard Metrologia",
                        "view_name": "dashboard",
                        "perm": "core.nav_metrologia_dashboard",
                    },
                ],
            },
            {
                "key": "gestao",
                "nome": "GESTÃO",
                "perm": "core.nav_metrologia_gestao",
                "funcoes": [
                    {
                        "nome": "Lista de Instrumentos",
                        "view_name": "modulo_metrologia",
                        "perm": "core.nav_metrologia_lista_instrumentos",
                    },
                    {
                        "nome": "Novo Instrumento",
                        "view_name": ["metrologia:novo_instrumento", "novo_instrumento", "qms:novo_instrumento"],
                        "perm": "core.nav_metrologia_novo_instrumento",
                    },
                    {
                        "nome": "Detalhe do Instrumento",
                        "view_name": ["detalhe_instrumento", "visualizar_instrumento", "qms:visualizar_instrumento"],
                        "perm": "core.nav_metrologia_detalhe_instrumento",
                    },
                    {
                        "nome": "Editar Instrumento",
                        "view_name": [
                            "editar_instrumento_custom",
                            "qms:editar_instrumento",
                            "gerenciar_faixas_instrumento",
                            "substituir_instrumento",
                            "atualizar_datas_calibracao",
                        ],
                        "perm": "core.nav_metrologia_editar_instrumento",
                    },
                    {
                        "nome": "Históricos de Calibração",
                        "view_name": "qms:listar_historicos_calibracao",
                        "perm": "core.nav_metrologia_historicos_calibracao",
                    },
                    {
                        "nome": "Registrar Histórico de Calibração",
                        "view_name": ["registrar_historico_calibracao", "qms:novo_historico_from_listagem"],
                        "perm": "core.nav_metrologia_registrar_historico",
                    },
                    {
                        "nome": "Visualizar Histórico de Calibração",
                        "view_name": "visualizar_historico_calibracao",
                        "perm": "core.nav_metrologia_visualizar_historico",
                    },
                    {
                        "nome": "Editar Histórico de Calibração",
                        "view_name": ["editar_historico_calibracao", "anexar_certificado_historico"],
                        "perm": "core.nav_metrologia_editar_historico",
                    },
                    {
                        "nome": "Remover Histórico de Calibração",
                        "view_name": "remover_historico",
                        "perm": "core.nav_metrologia_remover_historico",
                    },
                    {
                        "nome": "Categorias",
                        "view_name": "metrologia:categorias_list",
                        "perm": "core.nav_metrologia_categorias",
                    },
                    {
                        "nome": "Nova Categoria",
                        "view_name": "metrologia:categoria_create",
                        "perm": "core.nav_metrologia_categoria_create",
                    },
                    {
                        "nome": "Editar Categoria",
                        "view_name": "metrologia:categoria_update",
                        "perm": "core.nav_metrologia_categoria_update",
                    },
                    {
                        "nome": "Deletar Categoria",
                        "view_name": "metrologia:categoria_delete",
                        "perm": "core.nav_metrologia_categoria_delete",
                    },
                    {
                        "nome": "Atualizar Frequência em Massa",
                        "view_name": "metrologia:categoria_bulk_update_frequencia",
                        "perm": "core.nav_metrologia_categoria_bulk_update",
                    },
                    {
                        "nome": "Atualizar Sigla em Massa",
                        "view_name": "metrologia:categoria_bulk_update_sigla",
                        "perm": "core.nav_metrologia_categoria_bulk_update",
                    },
                    {
                        "nome": "Atualizar Tratativa em Massa",
                        "view_name": "metrologia:categoria_bulk_update_tratativa",
                        "perm": "core.nav_metrologia_categoria_bulk_update",
                    },
                    {
                        "nome": "Nova Faixa (Categoria)",
                        "view_name": "metrologia:faixa_categoria_create",
                        "perm": "core.nav_metrologia_faixa_categoria_create",
                    },
                    {
                        "nome": "Editar Faixa (Categoria)",
                        "view_name": ["metrologia:faixa_categoria_update", "editar_faixa"],
                        "perm": "core.nav_metrologia_faixa_categoria_update",
                    },
                    {
                        "nome": "Deletar Faixa (Categoria)",
                        "view_name": "metrologia:faixa_categoria_delete",
                        "perm": "core.nav_metrologia_faixa_categoria_delete",
                    },
                    {
                        "nome": "Remover Faixa-Instrumento",
                        "view_name": "metrologia:faixa_instrumento_delete",
                        "perm": "core.nav_metrologia_faixa_instrumento_delete",
                    },
                    {
                        "nome": "Remover Faixa-Instrumento em Massa",
                        "view_name": "metrologia:faixa_instrumento_bulk_delete",
                        "perm": "core.nav_metrologia_faixa_instrumento_bulk_delete",
                    },
                    {
                        "nome": "Unidades de Medida",
                        "view_name": "metrologia:unidades_list",
                        "perm": "core.nav_metrologia_unidades_medida",
                    },
                    {
                        "nome": "Nova Unidade de Medida",
                        "view_name": "metrologia:unidade_create",
                        "perm": "core.nav_metrologia_unidade_create",
                    },
                    {
                        "nome": "Editar Unidade de Medida",
                        "view_name": "metrologia:unidade_update",
                        "perm": "core.nav_metrologia_unidade_update",
                    },
                    {
                        "nome": "Deletar Unidade de Medida",
                        "view_name": "metrologia:unidade_delete",
                        "perm": "core.nav_metrologia_unidade_delete",
                    },

                    {
                        "nome": "Arquivo Padrão (Download)",
                        "view_name": "download_arquivo_padrao",
                        "perm": "core.nav_metrologia_download_arquivo_padrao",
                    },
                    {
                        "nome": "Arquivo Padrão (Remover)",
                        "view_name": "remover_arquivo_padrao",
                        "perm": "core.nav_metrologia_remover_arquivo_padrao",
                    },
                    {
                        "nome": "Certificado (Download)",
                        "view_name": ["download_certificado", "get_certificado_bytes"],
                        "perm": "core.nav_metrologia_download_certificado",
                    },
                    {
                        "nome": "Certificado (Remover Carimbo)",
                        "view_name": "remover_carimbo_certificado",
                        "perm": "core.nav_metrologia_remover_carimbo_certificado",
                    },
                    {
                        "nome": "Certificado (Remover)",
                        "view_name": "remover_certificado_historico",
                        "perm": "core.nav_metrologia_remover_certificado_historico",
                    },
                ],
            },
            {
                "key": "cotacoes",
                "nome": "COTAÇÕES",
                "perm": "core.nav_metrologia_cotacoes",
                "funcoes": [
                    {
                        "nome": "Solicitações de Cotação",
                        "view_name": "metrologia:solicitacao_list",
                        "perm": "core.nav_metrologia_solicitacoes_cotacao",
                    },
                    {
                        "nome": "Nova Solicitação de Cotação",
                        "view_name": "metrologia:solicitacao_create",
                        "perm": "core.nav_metrologia_solicitacao_create",
                    },
                    {
                        "nome": "Editar Solicitação de Cotação",
                        "view_name": "metrologia:solicitacao_update",
                        "perm": "core.nav_metrologia_solicitacao_update",
                    },
                    {
                        "nome": "Deletar Solicitação de Cotação",
                        "view_name": "metrologia:solicitacao_delete",
                        "perm": "core.nav_metrologia_solicitacao_delete",
                    },
                    {
                        "nome": "Editar Item da Solicitação",
                        "view_name": "metrologia:item_solicitacao_edit",
                        "perm": "core.nav_metrologia_item_solicitacao_edit",
                    },
                    {
                        "nome": "Deletar Item da Solicitação",
                        "view_name": "metrologia:item_solicitacao_delete",
                        "perm": "core.nav_metrologia_item_solicitacao_delete",
                    },
                    {
                        "nome": "Nova Cotação (Fornecedor)",
                        "view_name": "metrologia:cotacao_fornecedor_create",
                        "perm": "core.nav_metrologia_cotacao_fornecedor_create",
                    },
                    {
                        "nome": "Editar Cotação (Fornecedor)",
                        "view_name": "metrologia:cotacao_fornecedor_update",
                        "perm": "core.nav_metrologia_cotacao_fornecedor_update",
                    },
                    {
                        "nome": "Novo Atendimento",
                        "view_name": "metrologia:atendimento_create",
                        "perm": "core.nav_metrologia_atendimento_create",
                    },
                    {
                        "nome": "Criar Atendimento (via Cotação)",
                        "view_name": "metrologia:atendimento_create_from_cotacao",
                        "perm": "core.nav_metrologia_atendimento_create",
                    },
                    {
                        "nome": "Exportar Etiquetas",
                        "view_name": ["metrologia:export_etiquetas", "export_etiquetas"],
                        "perm": "core.nav_metrologia_export_etiquetas",
                    },
                    {
                        "nome": "Exportar Instrumentos (Excel/CSV)",
                        "view_name": ["export_metrologia", "exportar_instrumentos", "qms:exportar_instrumentos"],
                        "perm": "core.nav_metrologia_export_instrumentos",
                    },
                    {
                        "nome": "Exportar Estatísticas (Metrologia)",
                        "view_name": "qms:exportar_estatisticas",
                        "perm": "core.nav_metrologia_export_estatisticas",
                    },
                ],
            },
            {
                "key": "importacao",
                "nome": "IMPORTAÇÃO",
                "perm": "core.nav_metrologia_importacao",
                "funcoes": [
                    {
                        "nome": "Importar Instrumentos",
                        "view_name": "qms:importar_instrumentos",
                        "perm": "core.nav_metrologia_importar_instrumentos",
                    },
                    {
                        "nome": "Importar Histórico",
                        "view_name": "qms:importar_historico",
                        "perm": "core.nav_metrologia_importar_historico",
                    },
                    {
                        "nome": "Acompanhar Importações (Jobs)",
                        "view_name": ["import_jobs", "import_jobs_json"],
                        "perm": "core.nav_metrologia_import_jobs",
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
                "nome": "ACOMPANHAMENTO",
                "perm": "core.nav_treinamentos_acompanhamento",
                "funcoes": [
                    {"nome": "Dashboard", "view_name": "procedures:dashboard_treinamentos", "perm": "core.nav_treinamentos_dashboard"},
                    {"nome": "Calendário", "view_name": "procedures:treinamentos_calendario", "perm": "core.nav_treinamentos_calendario"},
                    {"nome": "Exportar Dashboard (CSV)", "view_name": "training:dashboard_exportar_csv", "perm": "core.nav_treinamentos_dashboard_export_csv"},
                ],
            },
            {
                "key": "gestao",
                "nome": "GESTÃO DE TREINAMENTOS",
                "perm": "core.nav_treinamentos_gestao",
                "funcoes": [
                    {"nome": "Registros de Treinamento", "view_name": "procedures:treinamentos_list", "perm": "core.nav_treinamentos_registros"},
                    {"nome": "Novo Treinamento", "view_name": "procedures:novo_treinamento", "perm": "core.nav_treinamentos_novo_treinamento"},
                    {"nome": "Detalhe do Treinamento", "view_name": "procedures:treinamentos_detalhe", "perm": "core.nav_treinamentos_detalhe_treinamento"},
                    {"nome": "Editar Treinamento", "view_name": "procedures:editar_treinamento", "perm": "core.nav_treinamentos_editar_treinamento"},
                    {"nome": "Importar Lista de Presença", "view_name": "procedures:treinamentos_importar", "perm": "core.nav_treinamentos_importar_treinamentos"},
                    {"nome": "Template Importação (Download)", "view_name": "procedures:treinamentos_template_download", "perm": "core.nav_treinamentos_download_template"},
                    {"nome": "Exportar Treinamentos (Excel)", "view_name": "procedures:treinamentos_exportar_excel", "perm": "core.nav_treinamentos_exportar_treinamentos"},
                    {"nome": "Listas de Presença", "view_name": "procedures:lista_presenca_list", "perm": "core.nav_treinamentos_listas_presenca"},
                    {"nome": "Nova Lista de Presença", "view_name": "procedures:lista_presenca_create", "perm": "core.nav_treinamentos_lista_presenca_create"},
                    {"nome": "Editar Lista de Presença", "view_name": "procedures:lista_presenca_edit", "perm": "core.nav_treinamentos_lista_presenca_edit"},
                    {"nome": "Deletar Lista de Presença", "view_name": "procedures:lista_presenca_delete", "perm": "core.nav_treinamentos_lista_presenca_delete"},
                    {"nome": "Importar Lista de Presença", "view_name": "procedures:lista_presenca_importar", "perm": "core.nav_treinamentos_lista_presenca_import"},
                    {"nome": "Exportar Listas de Presença", "view_name": "procedures:lista_presenca_export", "perm": "core.nav_treinamentos_lista_presenca_export"},
                    {"nome": "Exportar Lista de Presença (PDF)", "view_name": "procedures:lista_presenca_export_pdf", "perm": "core.nav_treinamentos_lista_presenca_export_pdf"},
                    {"nome": "Template Lista de Presença", "view_name": "procedures:lista_presenca_download_template", "perm": "core.nav_treinamentos_lista_presenca_template"},
                    {"nome": "Download Erros Importação", "view_name": "procedures:lista_presenca_erros_download", "perm": "core.nav_treinamentos_lista_presenca_erros_download"},
                    {"nome": "Upload Lista Assinada", "view_name": "procedures:upload_lista_presenca_assinada", "perm": "core.nav_treinamentos_lista_presenca_upload_assinada"},
                    {"nome": "Remover Lista Assinada", "view_name": "procedures:remover_lista_presenca_assinada", "perm": "core.nav_treinamentos_lista_presenca_remover_assinada"},
                    {
                        "nome": "Upload Template Lista de Presença",
                        "view_name": [
                            "procedures:upload_template_lista_presenca",
                            "procedures:mapear_template_fields",
                            "procedures:serve_pdf_template",
                        ],
                        "perm": "core.nav_treinamentos_lista_presenca_template_upload",
                    },
                    {"nome": "Planejamento", "view_name": "procedures:planejamentos_list", "perm": "core.nav_treinamentos_planejamento"},
                    {"nome": "Novo Planejamento", "view_name": ["procedures:novo_planejamento", "procedures:novo_planejamento_com_tipo"], "perm": "core.nav_treinamentos_planejamento"},
                    {"nome": "Editar Planejamento", "view_name": "procedures:editar_planejamento", "perm": "core.nav_treinamentos_planejamento"},
                    {"nome": "Deletar Planejamento", "view_name": "procedures:deletar_planejamento", "perm": "core.nav_treinamentos_planejamento_delete"},
                    {"nome": "Excluir Planejamentos (Massa)", "view_name": "procedures:excluir_planejamentos_massa", "perm": "core.nav_treinamentos_planejamento_mass_delete"},
                    {"nome": "Exportar Planejamentos (Excel)", "view_name": ["procedures:exportar_lista_planejamentos_excel", "procedures:exportar_detalhe_planejamento_excel"], "perm": "core.nav_treinamentos_planejamento_export"},

                    {"nome": "Novo Fornecedor (Treinamentos)", "view_name": "procedures:novo_fornecedor", "perm": "core.nav_treinamentos_fornecedor_create"},
                    {"nome": "Editar Fornecedor (Treinamentos)", "view_name": "procedures:editar_fornecedor", "perm": "core.nav_treinamentos_fornecedor_update"},
                    {"nome": "Editar Cotação (Treinamentos)", "view_name": "procedures:editar_cotacao", "perm": "core.nav_treinamentos_cotacao_update"},
                    {"nome": "Novo Orçamento (Treinamentos)", "view_name": "procedures:novo_orcamento", "perm": "core.nav_treinamentos_orcamento_create"},
                    {"nome": "Editar Orçamento (Treinamentos)", "view_name": "procedures:editar_orcamento", "perm": "core.nav_treinamentos_orcamento_update"},

                    {"nome": "Remover Procedimento do Planejamento", "view_name": "procedures:remover_procedimento_planejamento", "perm": "core.nav_treinamentos_planejamento_procedimento_remove"},
                    {"nome": "Remover Colaborador do Planejamento", "view_name": "procedures:remover_colaborador_planejamento", "perm": "core.nav_treinamentos_planejamento_colaborador_remove"},
                ],
            },
            {
                "key": "matriz",
                "nome": "MATRIZ DE COMPETÊNCIAS",
                "perm": "core.nav_treinamentos_matriz",
                "funcoes": [
                    {"nome": "Matrizes", "view_name": "procedures:matrizes_list", "perm": "core.nav_treinamentos_matrizes"},
                    {"nome": "Editar Matriz", "view_name": "procedures:editar_matriz", "perm": "core.nav_treinamentos_matrizes"},
                    {"nome": "Deletar Matriz", "view_name": "procedures:deletar_matriz", "perm": "core.nav_treinamentos_matrizes_delete"},
                    {"nome": "Exportar Matrizes", "view_name": "procedures:exportar_matrizes", "perm": "core.nav_treinamentos_matrizes_export"},
                    {"nome": "Importação de Matriz", "view_name": ["procedures:importacao_matriz", "procedures:importacao_matriz_resultado"], "perm": "core.nav_treinamentos_matrizes_import"},
                    {"nome": "Template Importação Matriz", "view_name": "procedures:baixar_template_importacao", "perm": "core.nav_treinamentos_matrizes_template"},
                    {"nome": "Disciplinas", "view_name": "procedures:disciplinas_list", "perm": "core.nav_treinamentos_disciplinas"},
                    {"nome": "Editar Disciplina", "view_name": "procedures:editar_disciplina", "perm": "core.nav_treinamentos_disciplinas"},
                    {"nome": "Deletar Disciplina", "view_name": "procedures:deletar_disciplina", "perm": "core.nav_treinamentos_disciplinas_delete"},
                    {"nome": "Avaliações de Colaboradores", "view_name": "procedures:matriz_avaliacoes", "perm": "core.nav_treinamentos_avaliacoes"},
                    {"nome": "Editar Avaliação", "view_name": "procedures:editar_avaliacao", "perm": "core.nav_treinamentos_avaliacao_edit"},
                    {"nome": "Salvar Avaliação (API)", "view_name": ["procedures:salvar_avaliacao_api", "procedures:salvar_avaliacao_modal_api"], "perm": "core.nav_treinamentos_avaliacoes"},

                    {"nome": "API Disciplinas por Matriz", "view_name": "procedures:api_disciplinas_por_matriz_novo", "perm": "core.nav_treinamentos_disciplinas"},
                    {"nome": "Remover Colaborador da Matriz", "view_name": "procedures:remover_colaborador_matriz", "perm": "core.nav_treinamentos_matrizes_colaborador_remove"},
                    {"nome": "Remover Procedimento da Disciplina", "view_name": "procedures:remover_procedimento_disciplina", "perm": "core.nav_treinamentos_disciplina_procedimento_remove"},
                ],
            },
            {
                "key": "perfis",
                "nome": "PERFIS DE TREINAMENTO",
                "perm": "core.nav_treinamentos_perfis_bloco",
                "funcoes": [
                    {"nome": "Perfis e Grupos", "view_name": "procedures:perfis_list", "perm": "core.nav_treinamentos_perfis"},
                    {"nome": "Novo Perfil", "view_name": "procedures:novo_perfil", "perm": "core.nav_treinamentos_perfis"},
                    {"nome": "Editar Perfil", "view_name": "procedures:editar_perfil", "perm": "core.nav_treinamentos_perfis"},
                    {"nome": "Deletar Perfil (API)", "view_name": "procedures:api_delete_perfil", "perm": "core.nav_treinamentos_perfis_delete"},
                    {"nome": "Deletar Perfis em Massa (API)", "view_name": "procedures:api_delete_perfis_multiple", "perm": "core.nav_treinamentos_perfis_mass_delete"},
                    {"nome": "Importar Perfis", "view_name": "procedures:importar_perfis", "perm": "core.nav_treinamentos_perfis_import"},
                    {"nome": "Importar Estrutura", "view_name": "procedures:importar_estrutura", "perm": "core.nav_treinamentos_perfis_import_estrutura"},
                    {"nome": "Exportar Estrutura", "view_name": "procedures:exportar_estrutura", "perm": "core.nav_treinamentos_perfis_export_estrutura"},
                    {"nome": "Exportar Erros Importação", "view_name": "procedures:exportar_erros_importacao", "perm": "core.nav_treinamentos_perfis_export_erros"},
                    {"nome": "Template Importação (Download)", "view_name": "procedures:download_template_importacao", "perm": "core.nav_treinamentos_perfis_template_importacao"},
                    {
                        "nome": "Upload Template Excel",
                        "view_name": [
                            "procedures:upload_excel_template",
                            "procedures:mapear_campos_template",
                            "procedures:preview_excel_abas_api",
                            "procedures:preview_excel_celulas_api",
                            "procedures:atualizar_mapeamento_campo_api",
                            "procedures:status_mapeamento_api",
                        ],
                        "perm": "core.nav_treinamentos_perfis_upload_template",
                    },
                    {"nome": "Upload Template PDF", "view_name": "procedures:upload_pdf_template", "perm": "core.nav_treinamentos_perfis_upload_template"},
                    {"nome": "Remover Template PDF", "view_name": "procedures:remove_pdf_template", "perm": "core.nav_treinamentos_perfis_delete_template"},
                    {"nome": "Remover Mapeamento Campo (API)", "view_name": "procedures:remover_mapeamento_campo_api", "perm": "core.nav_treinamentos_perfis_delete_template"},

                    {"nome": "Novo Grupo", "view_name": "procedures:novo_grupo", "perm": "core.nav_treinamentos_grupo_create"},
                    {"nome": "Editar Grupo", "view_name": "procedures:editar_grupo", "perm": "core.nav_treinamentos_grupo_update"},
                    {"nome": "Deletar Grupo", "view_name": "procedures:deletar_grupo", "perm": "core.nav_treinamentos_grupo_delete"},

                    {"nome": "Novo Subgrupo", "view_name": "procedures:novo_subgrupo", "perm": "core.nav_treinamentos_subgrupo_create"},
                    {"nome": "Editar Subgrupo", "view_name": "procedures:editar_subgrupo", "perm": "core.nav_treinamentos_subgrupo_update"},
                    {"nome": "Deletar Subgrupo", "view_name": "procedures:deletar_subgrupo", "perm": "core.nav_treinamentos_subgrupo_delete"},
                    {"nome": "Remover Procedimento do Subgrupo", "view_name": "procedures:remover_procedimento_subgrupo", "perm": "core.nav_treinamentos_subgrupo_procedimento_remove"},

                    {"nome": "Editar Colaborador do Perfil", "view_name": "procedures:editar_colaborador_perfil", "perm": "core.nav_treinamentos_perfis_colaborador_edit"},
                    {"nome": "Remover Colaborador do Perfil", "view_name": "procedures:remover_colaborador_perfil", "perm": "core.nav_treinamentos_perfis_colaborador_remove"},
                    {"nome": "Remover Associação Perfil-Colaborador", "view_name": "procedures:remover_associacao_perfil_colaborador", "perm": "core.nav_treinamentos_perfis_colaborador_remove"},
                    {"nome": "Remover Colaboradores em Massa", "view_name": "procedures:remover_colaboradores_massa", "perm": "core.nav_treinamentos_perfis_colaborador_mass_remove"},
                ],
            },
            {
                "key": "procedimentos",
                "nome": "PROCEDIMENTOS",
                "perm": "core.nav_treinamentos_procedimentos_bloco",
                "funcoes": [
                    {"nome": "Procedimentos", "view_name": "procedures:procedimentos_list", "perm": "core.nav_treinamentos_procedimentos"},
                    {"nome": "Novo Procedimento", "view_name": ["procedures:novo_procedimento", "qms:novo_procedimento"], "perm": "core.nav_treinamentos_novo_procedimento"},
                    {"nome": "Editar Procedimento", "view_name": ["procedures:editar_procedimento", "qms:editar_procedimento"], "perm": "core.nav_treinamentos_editar_procedimento"},
                    {"nome": "Importar Procedimentos", "view_name": ["procedures:importar_procedimentos", "procedures:dl_template_procedimentos"], "perm": "core.nav_treinamentos_importar_procedimentos"},
                    {"nome": "Exportar Procedimentos (Excel)", "view_name": "procedures:export_procedimentos_excel", "perm": "core.nav_treinamentos_exportar_procedimentos"},
                    {"nome": "Matrizes e Sub-áreas (Lista)", "view_name": ["procedures:procedimento_matrizes_list", "procedures:procedimento_matriz_detalhe"], "perm": "core.nav_treinamentos_procedimentos_matrizes"},
                    {"nome": "Importar Matrizes e Sub-áreas", "view_name": ["procedures:importar_matrizes_subareas", "procedures:download_template_matrizes_subareas"], "perm": "core.nav_treinamentos_procedimentos_matrizes_import"},
                    {"nome": "API Sub-áreas por Matriz", "view_name": "procedures:api_subareas_por_matriz", "perm": "core.nav_treinamentos_procedimentos_subareas_api"},
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
                "nome": "EQUIPE",
                "perm": "core.nav_pessoas_equipe",
                "funcoes": [
                    {"nome": "Colaboradores", "view_name": "modulo_rh", "perm": "core.nav_pessoas_colaboradores"},
                    {"nome": "Permissão Especial: Ver Todos os Colaboradores", "perm": "core.nav_pessoas_ver_todos_colaboradores"},
                    {"nome": "Novo Colaborador", "view_name": "rh:criar_colaborador", "perm": "core.nav_pessoas_novo_colaborador"},
                    {"nome": "Detalhe do Colaborador", "view_name": ["rh:detalhe_colaborador", "detalhe_colaborador"], "perm": "core.nav_pessoas_detalhe_colaborador"},
                    {"nome": "Editar Colaborador", "view_name": "editar_colaborador", "perm": "core.nav_pessoas_editar_colaborador"},
                    {"nome": "Gestão de Férias", "view_name": "rh:gestao_ferias", "perm": "core.nav_pessoas_gestao_ferias"},
                    {"nome": "Registrar Férias", "view_name": ["rh:criar_ferias", "registrar_ferias"], "perm": "core.nav_pessoas_registrar_ferias"},
                    {"nome": "Editar Férias", "view_name": ["rh:editar_ferias", "editar_ferias"], "perm": "core.nav_pessoas_editar_ferias"},
                    {"nome": "Excluir Férias", "view_name": ["rh:excluir_ferias", "excluir_ferias"], "perm": "core.nav_pessoas_excluir_ferias"},
                    {"nome": "Importar Férias", "view_name": ["rh:importar_ferias", "qms:importar_ferias"], "perm": "core.nav_pessoas_importar_ferias"},
                    {"nome": "Exportar Férias", "view_name": "rh:exportar_ferias", "perm": "core.nav_pessoas_exportar_ferias"},
                    {"nome": "Lideranças", "view_name": "rh:atualizar_liderancas_em_massa", "perm": "core.nav_pessoas_liderancas"},
                    {"nome": "Ocorrências", "view_name": "listar_ocorrencias", "perm": "core.nav_pessoas_ocorrencias"},
                    {"nome": "Editar Ocorrência", "view_name": "editar_ocorrencia", "perm": "core.nav_pessoas_editar_ocorrencia"},
                    {"nome": "Deletar Ocorrência", "view_name": "deletar_ocorrencia", "perm": "core.nav_pessoas_deletar_ocorrencia"},

                    {"nome": "Deletar Colaborador (API)", "view_name": "rh:api_delete_colaborador", "perm": "core.nav_pessoas_api_delete_colaborador"},
                    {"nome": "Deletar Colaboradores em Massa (API)", "view_name": "rh:api_delete_colaboradores_multiple", "perm": "core.nav_pessoas_api_delete_colaboradores_multiple"},
                ],
            },
            {
                "key": "importacao",
                "nome": "IMPORTAÇÃO",
                "perm": "core.nav_pessoas_importacao",
                "funcoes": [
                    {"nome": "Importar Pessoas", "view_name": "qms:importar_colaboradores", "perm": "core.nav_pessoas_importar_pessoas"},
                    {"nome": "Importar Hierarquia", "view_name": "qms:importar_hierarquia", "perm": "core.nav_pessoas_importar_hierarquia"},
                ],
            },
        ],
    },
    {
        "key": "acoes",
        "nome": "Ações Corretivas",
        "cor": "danger",
        "icone": "bi bi-exclamation-triangle",
        "module_perm": "core.nav_mod_acoes",
        "blocos": [
            {
                "key": "registro",
                "nome": "REGISTRO E SOLUÇÃO",
                "perm": "core.nav_acoes_registro",
                "funcoes": [
                    {"nome": "Ações Corretivas/Preventivas", "view_name": "acoes:listar_acoes", "perm": "core.nav_acoes_listar_acoes"},
                    {"nome": "Salvar Ação (Modal)", "view_name": "acoes:salvar_acao_corretiva_modal", "perm": "core.nav_acoes_salvar_acao"},
                    {"nome": "Próximo Número (API)", "view_name": "acoes:obter_proximo_numero", "perm": "core.nav_acoes_api_proximo_numero"},
                    {"nome": "Detalhe da Ação", "view_name": "acoes:detalhe_acao", "perm": "core.nav_acoes_detalhe_acao"},
                    {"nome": "Ações Registradas", "view_name": "acoes:acoes_registradas", "perm": "core.nav_acoes_registradas"},
                    {"nome": "Controle de Registros", "view_name": "acoes:listar_solucoes", "perm": "core.nav_acoes_controle_registros"},

                    {"nome": "Detalhe da Solução (Legacy)", "view_name": "acoes:detalhe_solucao", "perm": "core.nav_acoes_detalhe_solucao"},
                    {"nome": "Criar Solução (Legacy)", "view_name": "acoes:criar_solucao", "perm": "core.nav_acoes_criar_solucao"},
                    {"nome": "Editar Solução (Legacy)", "view_name": "acoes:editar_solucao", "perm": "core.nav_acoes_editar_solucao"},

                    {"nome": "Criar Registro (Modal - Legacy)", "view_name": "acoes:criar_registro_modal", "perm": "core.nav_acoes_criar_registro_modal"},
                    {"nome": "Adicionar Ação (Modal - Legacy)", "view_name": "acoes:criar_plano_acao_modal", "perm": "core.nav_acoes_linha_create"},
                    {"nome": "Editar Ação (Modal - Legacy)", "view_name": "acoes:editar_linha_acao_modal", "perm": "core.nav_acoes_linha_update"},

                    {"nome": "Importar Controle de Registros", "view_name": "acoes:importar_controle_registros", "perm": "core.nav_acoes_importar_controle_registros"},
                    {"nome": "Template Controle de Registros", "view_name": "acoes:download_template_controle_registros", "perm": "core.nav_acoes_download_template_controle_registros"},
                    {"nome": "Importar Plano de Ação", "view_name": "acoes:importar_plano_acao", "perm": "core.nav_acoes_importar_plano_acao"},
                    {"nome": "Template Plano de Ação", "view_name": "acoes:download_template_plano_acao", "perm": "core.nav_acoes_download_template_plano_acao"},

                    {"nome": "Importar Ações Associadas", "view_name": "acoes:importar_acoes_associadas", "perm": "core.nav_acoes_importar_acoes_associadas"},
                    {"nome": "Template Ações Associadas", "view_name": "acoes:download_template_acoes_associadas", "perm": "core.nav_acoes_download_template_acoes_associadas"},
                    {"nome": "Exportar Ações Associadas", "view_name": "acoes:exportar_acoes_associadas", "perm": "core.nav_acoes_exportar_acoes_associadas"},
                    {"nome": "Deletar Ações Associadas", "view_name": "acoes:deletar_acoes_associadas", "perm": "core.nav_acoes_deletar_acoes_associadas"},
                ],
            },
            {
                "key": "plano",
                "nome": "PLANO DE AÇÃO",
                "perm": "core.nav_acoes_plano",
                "funcoes": [
                    {"nome": "Dashboard", "view_name": "acoes:dashboard", "perm": "core.nav_acoes_dashboard"},
                    {"nome": "Templates (Lista)", "view_name": "acoes:listar_templates", "perm": "core.nav_acoes_listar_templates"},
                    {"nome": "Template (Download)", "view_name": "acoes:download_template", "perm": "core.nav_acoes_download_template"},

                    {"nome": "Planos de Ação (Lista)", "view_name": "acoes:plano_acao_list", "perm": "core.nav_acoes_plano_list"},
                    {"nome": "Novo Plano de Ação", "view_name": "acoes:plano_acao_create", "perm": "core.nav_acoes_plano_create"},
                    {"nome": "Editar Plano de Ação", "view_name": "acoes:plano_acao_update", "perm": "core.nav_acoes_plano_update"},
                    {"nome": "Deletar Plano de Ação", "view_name": "acoes:plano_acao_delete", "perm": "core.nav_acoes_plano_delete"},
                    {"nome": "Detalhe do Plano de Ação", "view_name": "acoes:plano_acao_detail", "perm": "core.nav_acoes_plano_detail"},

                    {"nome": "Editar Linha de Ação", "view_name": "acoes:linha_acao_update", "perm": "core.nav_acoes_linha_update"},
                    {"nome": "Deletar Linha de Ação", "view_name": "acoes:linha_acao_delete", "perm": "core.nav_acoes_linha_delete"},
                    {"nome": "Dados da Linha de Ação", "view_name": "acoes:obter_dados_linha_acao", "perm": "core.nav_acoes_linha_dados"},

                    {"nome": "Solução A3 (Lista)", "view_name": "acoes:a3_list", "perm": "core.nav_acoes_a3_list"},
                    {"nome": "Solução A3 (Nova)", "view_name": "acoes:a3_create", "perm": "core.nav_acoes_a3_create"},
                    {"nome": "Solução A3 (Editar)", "view_name": "acoes:a3_update", "perm": "core.nav_acoes_a3_update"},
                    {"nome": "Solução A3 (Detalhe)", "view_name": "acoes:a3_detail", "perm": "core.nav_acoes_a3_detail"},

                    {"nome": "Solução 8D (Lista)", "view_name": "acoes:8d_list", "perm": "core.nav_acoes_8d_list"},
                    {"nome": "Solução 8D (Nova)", "view_name": "acoes:8d_create", "perm": "core.nav_acoes_8d_create"},
                    {"nome": "Solução 8D (Editar)", "view_name": "acoes:8d_update", "perm": "core.nav_acoes_8d_update"},
                    {"nome": "Solução 8D (Detalhe)", "view_name": "acoes:8d_detail", "perm": "core.nav_acoes_8d_detail"},

                    {"nome": "Solução RNC (Lista)", "view_name": "acoes:rnc_list", "perm": "core.nav_acoes_rnc_list"},
                    {"nome": "Solução RNC (Nova)", "view_name": "acoes:rnc_create", "perm": "core.nav_acoes_rnc_create"},
                    {"nome": "Solução RNC (Editar)", "view_name": "acoes:rnc_update", "perm": "core.nav_acoes_rnc_update"},
                    {"nome": "Solução RNC (Detalhe)", "view_name": "acoes:rnc_detail", "perm": "core.nav_acoes_rnc_detail"},

                    {"nome": "Gestão de Mudança (Lista)", "view_name": "acoes:gestao_mudanca_list", "perm": "core.nav_acoes_mudanca_list"},
                    {"nome": "Gestão de Mudança (Nova)", "view_name": "acoes:gestao_mudanca_create", "perm": "core.nav_acoes_mudanca_create"},
                    {"nome": "Gestão de Mudança (Editar)", "view_name": "acoes:gestao_mudanca_update", "perm": "core.nav_acoes_mudanca_update"},
                    {"nome": "Gestão de Mudança (Detalhe)", "view_name": "acoes:gestao_mudanca_detail", "perm": "core.nav_acoes_mudanca_detail"},

                    {"nome": "Revisão Gerencial (Lista)", "view_name": "acoes:revisao_gerencial_list", "perm": "core.nav_acoes_revisao_list"},
                    {"nome": "Revisão Gerencial (Nova)", "view_name": "acoes:revisao_gerencial_create", "perm": "core.nav_acoes_revisao_create"},
                    {"nome": "Revisão Gerencial (Editar)", "view_name": "acoes:revisao_gerencial_update", "perm": "core.nav_acoes_revisao_update"},
                    {"nome": "Revisão Gerencial (Detalhe)", "view_name": "acoes:revisao_gerencial_detail", "perm": "core.nav_acoes_revisao_detail"},
                ],
            },
            {
                "key": "referencia",
                "nome": "REFERÊNCIA DE DADOS",
                "perm": "core.nav_acoes_referencia",
                "funcoes": [
                    {"nome": "Origens de Problemas", "view_name": "acoes:origem_problema_list", "perm": "core.nav_acoes_origens"},
                    {"nome": "Nova Origem de Problema", "view_name": "acoes:origem_problema_create", "perm": "core.nav_acoes_origens_create"},
                    {"nome": "Editar Origem de Problema", "view_name": "acoes:origem_problema_update", "perm": "core.nav_acoes_origens_update"},
                    {"nome": "Deletar Origem de Problema", "view_name": "acoes:origem_problema_delete", "perm": "core.nav_acoes_origens_delete"},
                    {"nome": "Tipos de Solução", "view_name": "acoes:tipo_solucao_list", "perm": "core.nav_acoes_tipos"},
                    {"nome": "Novo Tipo de Solução", "view_name": "acoes:tipo_solucao_create", "perm": "core.nav_acoes_tipos_create"},
                    {"nome": "Editar Tipo de Solução", "view_name": "acoes:tipo_solucao_update", "perm": "core.nav_acoes_tipos_update"},
                    {"nome": "Deletar Tipo de Solução", "view_name": "acoes:tipo_solucao_delete", "perm": "core.nav_acoes_tipos_delete"},
                    {"nome": "KPIs", "view_name": "acoes:kpi_opcao_list", "perm": "core.nav_acoes_kpis"},
                    {"nome": "Novo KPI", "view_name": "acoes:kpi_opcao_create", "perm": "core.nav_acoes_kpis_create"},
                    {"nome": "Editar KPI", "view_name": "acoes:kpi_opcao_update", "perm": "core.nav_acoes_kpis_update"},
                    {"nome": "Deletar KPI", "view_name": "acoes:kpi_opcao_delete", "perm": "core.nav_acoes_kpis_delete"},
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
                "nome": "GESTÃO",
                "perm": "core.nav_fornecedores_gestao",
                "funcoes": [
                    {"nome": "Lista de Fornecedores", "view_name": "fornecedores:fornecedor_list", "perm": "core.nav_fornecedores_lista"},
                    {"nome": "Novo Fornecedor", "view_name": "fornecedores:fornecedor_create", "perm": "core.nav_fornecedores_novo"},
                    {"nome": "Editar Fornecedor", "view_name": "fornecedores:fornecedor_update", "perm": "core.nav_fornecedores_editar"},
                ],
            },
            {
                "key": "avaliacao",
                "nome": "AVALIAÇÃO",
                "perm": "core.nav_fornecedores_avaliacao",
                "funcoes": [
                    {"nome": "Perguntas de Avaliação", "view_name": "fornecedores:pergunta_list", "perm": "core.nav_fornecedores_perguntas"},
                    {"nome": "Nova Pergunta", "view_name": "fornecedores:pergunta_create", "perm": "core.nav_fornecedores_pergunta_create"},
                    {"nome": "Editar Pergunta", "view_name": "fornecedores:pergunta_edit", "perm": "core.nav_fornecedores_pergunta_edit"},
                    {"nome": "Remover Pergunta", "view_name": "fornecedores:pergunta_delete", "perm": "core.nav_fornecedores_pergunta_delete"},

                    {"nome": "Nova Avaliação", "view_name": "fornecedores:avaliacao_create", "perm": "core.nav_fornecedores_avaliacao_create"},
                    {"nome": "Editar Avaliação", "view_name": "fornecedores:avaliacao_edit", "perm": "core.nav_fornecedores_avaliacao_edit"},
                    {"nome": "Criar Matriz de Avaliação", "view_name": "fornecedores:avaliacao_matriz_create", "perm": "core.nav_fornecedores_avaliacao_matriz"},
                    {"nome": "Criar Reavaliação (Base)", "view_name": "fornecedores:avaliacao_reavaliacao_create", "perm": "core.nav_fornecedores_reavaliacao_create"},
                    {"nome": "Criar Seleção", "view_name": "fornecedores:avaliacao_selecao_create", "perm": "core.nav_fornecedores_avaliacao_selecao"},

                    {"nome": "Nova Reavaliação", "view_name": "fornecedores:reavaliacao_create", "perm": "core.nav_fornecedores_reavaliacao_create"},
                    {"nome": "Deletar Reavaliação", "view_name": "fornecedores:reavaliacao_delete", "perm": "core.nav_fornecedores_reavaliacao_delete"},

                    {"nome": "Novo Documento", "view_name": "fornecedores:documento_create", "perm": "core.nav_fornecedores_documento_create"},
                    {"nome": "Remover Documento", "view_name": "fornecedores:documento_delete", "perm": "core.nav_fornecedores_documento_delete"},

                    {"nome": "Exportar Avaliações (Excel)", "view_name": "fornecedores:export_avaliacoes_excel", "perm": "core.nav_fornecedores_export_avaliacoes"},
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
                "key": "cadastro",
                "nome": "CADASTRO",
                "perm": "core.nav_auditoria_cadastro",
                "funcoes": [
                    {"nome": "Modelos de Auditoria", "view_name": "auditoria:modelos_list", "perm": "core.nav_auditoria_modelos"},
                    {"nome": "Novo Modelo", "view_name": "auditoria:modelo_create", "perm": "core.nav_auditoria_novo_modelo"},
                    {"nome": "Editar Modelo", "view_name": "auditoria:modelo_edit", "perm": "core.nav_auditoria_editar_modelo"},
                    {"nome": "Duplicar Modelo", "view_name": "auditoria:modelo_duplicate", "perm": "core.nav_auditoria_duplicar_modelo"},
                    {"nome": "Remover Modelo", "view_name": "auditoria:modelo_delete", "perm": "core.nav_auditoria_remover_modelo"},
                    {"nome": "Perguntas por Modelo", "view_name": "auditoria:perguntas_list", "perm": "core.nav_auditoria_perguntas"},
                    {"nome": "Nova Pergunta", "view_name": "auditoria:pergunta_create", "perm": "core.nav_auditoria_nova_pergunta"},
                    {"nome": "Editar Pergunta", "view_name": "auditoria:pergunta_edit", "perm": "core.nav_auditoria_editar_pergunta"},
                    {"nome": "Duplicar Pergunta", "view_name": "auditoria:pergunta_duplicate", "perm": "core.nav_auditoria_duplicar_pergunta"},
                    {"nome": "Remover Pergunta", "view_name": "auditoria:pergunta_delete", "perm": "core.nav_auditoria_remover_pergunta"},
                ],
            },
            {
                "key": "operacao",
                "nome": "OPERAÇÃO",
                "perm": "core.nav_auditoria_operacao",
                "funcoes": [
                    {"nome": "Modelos Cadastrados / Período", "view_name": "auditoria:registros_list", "perm": "core.nav_auditoria_registros"},
                    {"nome": "Avaliação de Dados", "view_name": "auditoria:registro_create", "perm": "core.nav_auditoria_avaliacao"},
                    {"nome": "Avaliação de Dados (com Modelo)", "view_name": "auditoria:registro_create_modelo", "perm": "core.nav_auditoria_avaliacao"},
                    {"nome": "Editar Registro", "view_name": "auditoria:registro_edit", "perm": "core.nav_auditoria_editar_registro"},
                    {"nome": "Excluir Registro", "view_name": "auditoria:registro_delete", "perm": "core.nav_auditoria_excluir_registro"},
                    {"nome": "Detalhe do Registro", "view_name": "auditoria:registro_detail", "perm": "core.nav_auditoria_detalhe_registro"},
                    {"nome": "Registros por Modelo", "view_name": "auditoria:registros_por_modelo", "perm": "core.nav_auditoria_registros_por_modelo"},
                    {"nome": "Exportar Respostas (Excel)", "view_name": "auditoria:exportar_respostas_excel", "perm": "core.nav_auditoria_exportar_excel"},
                    {"nome": "Editar Comentário", "view_name": "auditoria:comentario_edit", "perm": "core.nav_auditoria_comentario_edit"},
                    {"nome": "Remover Comentário", "view_name": "auditoria:comentario_delete", "perm": "core.nav_auditoria_comentario_delete"},
                ],
            },
            {
                "key": "analise",
                "nome": "ANÁLISE",
                "perm": "core.nav_auditoria_analise",
                "funcoes": [
                    {"nome": "Dashboard Auditoria", "view_name": "auditoria:dashboard", "perm": "core.nav_auditoria_dashboard"},
                ],
            },
            {
                "key": "acoes",
                "nome": "AÇÕES",
                "perm": "core.nav_auditoria_operacao",
                "funcoes": [
                    {"nome": "Nova Auditoria", "view_name": "auditoria:selecionar_modelo_preenchimento", "perm": "core.nav_auditoria_nova"},
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
                "nome": "OCORRENCIAS GERAIS",
                "perm": "core.nav_laboratorio_ocorrencias_gerais",
                "funcoes": [
                    {"nome": "Modulo Laboratorio", "view_name": "laboratorio:modulo", "perm": "core.nav_laboratorio_modulo"},
                    {"nome": "Nova Ocorrencia", "view_name": "laboratorio:ocorrencia_create", "perm": "core.nav_laboratorio_nova_ocorrencia"},
                    {"nome": "Listagem de Ocorrencias", "view_name": "laboratorio:ocorrencias_list", "perm": "core.nav_laboratorio_lista_ocorrencias"},
                    {"nome": "Editar Ocorrencia", "view_name": "laboratorio:ocorrencia_update", "perm": "core.nav_laboratorio_editar_ocorrencia"},
                    {"nome": "Tabela de Categorias", "view_name": "laboratorio:categorias_list", "perm": "core.nav_laboratorio_categorias"},
                    {"nome": "Nova Categoria", "view_name": "laboratorio:categoria_create", "perm": "core.nav_laboratorio_categoria_create"},
                    {"nome": "Editar Categoria", "view_name": "laboratorio:categoria_update", "perm": "core.nav_laboratorio_categoria_update"},
                    {"nome": "Dashboard Laboratorio", "view_name": "laboratorio:dashboard", "perm": "core.nav_laboratorio_dashboard"},
                ],
            },
            {
                "key": "maquinas",
                "nome": "MAQUINAS",
                "perm": "core.nav_laboratorio_maquinas",
                "funcoes": [
                    {"nome": "Cadastro de Maquinas", "view_name": "maquinas:maquinas_list", "perm": "core.nav_laboratorio_maquinas_lista"},
                    {"nome": "Nova Maquina", "view_name": "maquinas:maquina_create", "perm": "core.nav_laboratorio_maquina_create"},
                    {"nome": "Editar Maquina", "view_name": "maquinas:maquina_update", "perm": "core.nav_laboratorio_maquina_update"},
                    {"nome": "Excluir Maquina", "view_name": "maquinas:maquina_delete", "perm": "core.nav_laboratorio_maquina_delete"},
                    {"nome": "Categorias de Maquinas", "view_name": "maquinas:categorias_list", "perm": "core.nav_laboratorio_maquinas_categorias"},
                    {"nome": "Nova Categoria de Maquina", "view_name": "maquinas:categoria_create", "perm": "core.nav_laboratorio_categoria_maquina_create"},
                    {"nome": "Editar Categoria de Maquina", "view_name": "maquinas:categoria_update", "perm": "core.nav_laboratorio_categoria_maquina_update"},
                    {"nome": "Excluir Categoria de Maquina", "view_name": "maquinas:categoria_delete", "perm": "core.nav_laboratorio_categoria_maquina_delete"},
                ],
            },
        ],
    },
    {
        "key": "insumos",
        "nome": "Insumos",
        "cor": "info",
        "icone": "bi bi-box-seam",
        "module_perm": "core.nav_mod_insumos",
        "blocos": [
            {
                "key": "cadastro",
                "nome": "CADASTRO",
                "perm": "core.nav_insumos_cadastro",
                "funcoes": [
                    {"nome": "Modelos de Insumos", "view_name": "insumos:modelos_list", "perm": "core.nav_insumos_modelos"},
                    {"nome": "Novo Modelo", "view_name": "insumos:modelo_create", "perm": "core.nav_insumos_novo_modelo"},
                    {"nome": "Editar Modelo", "view_name": "insumos:modelo_edit", "perm": "core.nav_insumos_editar_modelo"},
                    {"nome": "Remover Modelo", "view_name": "insumos:modelo_delete", "perm": "core.nav_insumos_remover_modelo"},
                    {"nome": "Perguntas por Modelo", "view_name": "insumos:perguntas_list", "perm": "core.nav_insumos_perguntas"},
                    {"nome": "Nova Pergunta", "view_name": "insumos:pergunta_create", "perm": "core.nav_insumos_nova_pergunta"},
                    {"nome": "Editar Pergunta", "view_name": "insumos:pergunta_edit", "perm": "core.nav_insumos_editar_pergunta"},
                    {"nome": "Remover Pergunta", "view_name": "insumos:pergunta_delete", "perm": "core.nav_insumos_remover_pergunta"},
                ],
            },
            {
                "key": "operacao",
                "nome": "OPERAÇÃO",
                "perm": "core.nav_insumos_operacao",
                "funcoes": [
                    {"nome": "Modelos Cadastrados / Período", "view_name": "insumos:registros_list", "perm": "core.nav_insumos_registros"},
                    {"nome": "Avaliação de Dados", "view_name": "insumos:registro_create", "perm": "core.nav_insumos_avaliacao"},
                    {"nome": "Avaliação de Dados (com Modelo)", "view_name": "insumos:registro_create_modelo", "perm": "core.nav_insumos_avaliacao"},
                    {"nome": "Editar Registro", "view_name": "insumos:registro_edit", "perm": "core.nav_insumos_editar_registro"},
                    {"nome": "Excluir Registro", "view_name": "insumos:registro_delete", "perm": "core.nav_insumos_excluir_registro"},
                    {"nome": "Detalhe do Registro", "view_name": "insumos:registro_detail", "perm": "core.nav_insumos_detalhe_registro"},
                    {"nome": "Registros por Modelo", "view_name": "insumos:registros_por_modelo", "perm": "core.nav_insumos_registros_por_modelo"},
                    {"nome": "Exportar Respostas (Excel)", "view_name": "insumos:exportar_respostas_excel", "perm": "core.nav_insumos_exportar_excel"},
                    {"nome": "Editar Comentário", "view_name": "insumos:comentario_edit", "perm": "core.nav_insumos_comentario_edit"},
                    {"nome": "Remover Comentário", "view_name": "insumos:comentario_delete", "perm": "core.nav_insumos_comentario_delete"},
                ],
            },
            {
                "key": "analise",
                "nome": "ANÁLISE",
                "perm": "core.nav_insumos_analise",
                "funcoes": [
                    {"nome": "Dashboard Insumos", "view_name": "insumos:dashboard", "perm": "core.nav_insumos_dashboard"},
                ],
            },
            {
                "key": "acoes",
                "nome": "AÇÕES",
                "perm": "core.nav_insumos_operacao",
                "funcoes": [
                    {"nome": "Novo Registro", "view_name": "insumos:selecionar_modelo_preenchimento", "perm": "core.nav_insumos_novo"},
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
                "nome": "GESTÃO",
                "perm": "core.nav_mod_usuarios",
                "funcoes": [
                    {"nome": "Lista de Usuários", "view_name": "rh:listar_usuarios", "perm": "core.nav_usuarios_lista"},
                ],
            }
        ],
    },
]


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

                # Suporta aliases: view_name pode ser uma lista/tupla/set de nomes.
                if isinstance(view_name, (list, tuple, set)):
                    for vn in view_name:
                        if vn:
                            result[vn] = {"perm": perm, "module": module_key}
                else:
                    result[view_name] = {"perm": perm, "module": module_key}
    return result


VIEW_NAME_TO_PERMISSION = get_view_permission_map()


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

    # Legado: se o usuário tem acesso ao módulo via grupo e ainda não tem nenhum nav_* do módulo,
    # permitir transição suave, EXCETO para ações destrutivas (delete/remover/excluir).
    if module_key and has_module_access(user, module_key) and not user_has_any_nav_perm_for_module(user, module_key):
        if _is_destructive_nav_perm(required_perm):
            return bool(required_perm and user.has_perm(required_perm))
        return True

    # Novo modelo (usuário já está "configurado" no nav_*):
    # Se o flag do módulo estiver ativo (nav_mod_*), permitir acesso às funções NÃO destrutivas,
    # mesmo sem permissão granular por função. Isso atende ao caso de "acesso total" por módulo,
    # mantendo exigência explícita para ações destrutivas.
    if module_key and has_module_nav_flag(user, module_key) and not _is_destructive_nav_perm(required_perm):
        return True

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
                f"⚠️  Módulo não instalado: {module_key}. "
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
                print(f"⚠️  Permissão não encontrada: {module_key}.{perm_codename}")
        
        status = "✓ Criado" if created else "✓ Atualizado"
        print(f"{status}: Grupo '{group.name}' com {group.permissions.count()} permissões")

def get_module_key(view_module):
    """
    Extrai o módulo (chave) a partir do caminho do módulo da view.
    Ex: 'metrologia.views.novo_fluxo_cotacao' -> 'metrologia'
    """
    return view_module.split('.')[0] if '.' in view_module else view_module

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
        # Se o usuário já está no novo modelo para este módulo (tem algum nav_* do módulo),
        # considerar acesso ao módulo SOMENTE quando o flag do módulo (nav_mod_*) estiver ativo.
        if user_has_any_nav_perm_for_module(user, module_key):
            module_perm = module.get("module_perm")
            return bool(module_perm and _user_has_nav_perm(user, module_perm))

        # Caso contrário (ainda não configurado no novo modelo), segue fallback legado via grupo.

    # Legado: acesso via grupo
    module_info = MODULES_PERMISSIONS.get(module_key)
    if not module_info:
        return False

    try:
        group = Group.objects.get(name=module_info["name"])
    except Group.DoesNotExist:
        return False

    return user.groups.filter(id=group.id).exists()

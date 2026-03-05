"""shared.permissions

Sistema de permissões de navegação e acesso por módulo.

Histórico:
- Existia um controle por *grupos* (Group) para liberar um módulo inteiro.
- Agora o controle principal passa a ser por permissões `core.nav_*`, estruturadas como:
    Módulo -> Blocos -> Funções.

Compatibilidade:
- Se o usuário ainda estiver usando grupos legados, o acesso continua funcionando.
"""

import unicodedata

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
                        "view_name": ["metrologia:novo_instrumento", "novo_instrumento"],
                        "perm": "core.nav_metrologia_novo_instrumento",
                    },
                    {
                        "nome": "Detalhe do Instrumento",
                        "view_name": ["detalhe_instrumento", "visualizar_instrumento"],
                        "perm": "core.nav_metrologia_detalhe_instrumento",
                    },
                    {
                        "nome": "Editar Instrumento",
                        "view_name": "editar_instrumento_custom",
                        "perm": "core.nav_metrologia_editar_instrumento",
                    },
                    {
                        "nome": "Históricos de Calibração",
                        "view_name": "qms:listar_historicos_calibracao",
                        "perm": "core.nav_metrologia_historicos_calibracao",
                    },
                    {
                        "nome": "Registrar Histórico de Calibração",
                        "view_name": "registrar_historico_calibracao",
                        "perm": "core.nav_metrologia_registrar_historico",
                    },
                    {
                        "nome": "Visualizar Histórico de Calibração",
                        "view_name": "visualizar_historico_calibracao",
                        "perm": "core.nav_metrologia_visualizar_historico",
                    },
                    {
                        "nome": "Editar Histórico de Calibração",
                        "view_name": "editar_historico_calibracao",
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
                        "nome": "Unidades de Medida",
                        "view_name": "metrologia:unidades_list",
                        "perm": "core.nav_metrologia_unidades_medida",
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
                    {"nome": "Planejamento", "view_name": "procedures:planejamentos_list", "perm": "core.nav_treinamentos_planejamento"},
                ],
            },
            {
                "key": "matriz",
                "nome": "MATRIZ DE COMPETÊNCIAS",
                "perm": "core.nav_treinamentos_matriz",
                "funcoes": [
                    {"nome": "Matrizes", "view_name": "procedures:matrizes_list", "perm": "core.nav_treinamentos_matrizes"},
                    {"nome": "Disciplinas", "view_name": "procedures:disciplinas_list", "perm": "core.nav_treinamentos_disciplinas"},
                    {"nome": "Avaliações de Colaboradores", "view_name": "procedures:matriz_avaliacoes", "perm": "core.nav_treinamentos_avaliacoes"},
                ],
            },
            {
                "key": "perfis",
                "nome": "PERFIS DE TREINAMENTO",
                "perm": "core.nav_treinamentos_perfis_bloco",
                "funcoes": [
                    {"nome": "Perfis e Grupos", "view_name": "procedures:perfis_list", "perm": "core.nav_treinamentos_perfis"},
                    {"nome": "Procedimentos", "view_name": "procedures:procedimentos_list", "perm": "core.nav_treinamentos_procedimentos"},
                    {"nome": "Novo Procedimento", "view_name": "procedures:novo_procedimento", "perm": "core.nav_treinamentos_novo_procedimento"},
                    {"nome": "Editar Procedimento", "view_name": "procedures:editar_procedimento", "perm": "core.nav_treinamentos_editar_procedimento"},
                    {"nome": "Importar Procedimentos", "view_name": "procedures:importar_procedimentos", "perm": "core.nav_treinamentos_importar_procedimentos"},
                    {"nome": "Exportar Procedimentos (Excel)", "view_name": "procedures:export_procedimentos_excel", "perm": "core.nav_treinamentos_exportar_procedimentos"},
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
                    {"nome": "Novo Colaborador", "view_name": "rh:criar_colaborador", "perm": "core.nav_pessoas_novo_colaborador"},
                    {"nome": "Detalhe do Colaborador", "view_name": ["rh:detalhe_colaborador", "detalhe_colaborador"], "perm": "core.nav_pessoas_detalhe_colaborador"},
                    {"nome": "Editar Colaborador", "view_name": "editar_colaborador", "perm": "core.nav_pessoas_editar_colaborador"},
                    {"nome": "Gestão de Férias", "view_name": "rh:gestao_ferias", "perm": "core.nav_pessoas_gestao_ferias"},
                    {"nome": "Registrar Férias", "view_name": ["rh:criar_ferias", "registrar_ferias"], "perm": "core.nav_pessoas_registrar_ferias"},
                    {"nome": "Editar Férias", "view_name": ["rh:editar_ferias", "editar_ferias"], "perm": "core.nav_pessoas_editar_ferias"},
                    {"nome": "Excluir Férias", "view_name": ["rh:excluir_ferias", "excluir_ferias"], "perm": "core.nav_pessoas_excluir_ferias"},
                    {"nome": "Importar Férias", "view_name": "rh:importar_ferias", "perm": "core.nav_pessoas_importar_ferias"},
                    {"nome": "Exportar Férias", "view_name": "rh:exportar_ferias", "perm": "core.nav_pessoas_exportar_ferias"},
                    {"nome": "Lideranças", "view_name": "rh:atualizar_liderancas_em_massa", "perm": "core.nav_pessoas_liderancas"},
                    {"nome": "Ocorrências", "view_name": "listar_ocorrencias", "perm": "core.nav_pessoas_ocorrencias"},
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
                    {"nome": "Ações Registradas", "view_name": "acoes:acoes_registradas", "perm": "core.nav_acoes_registradas"},
                    {"nome": "Controle de Registros", "view_name": "acoes:listar_solucoes", "perm": "core.nav_acoes_controle_registros"},
                ],
            },
            {
                "key": "referencia",
                "nome": "REFERÊNCIA DE DADOS",
                "perm": "core.nav_acoes_referencia",
                "funcoes": [
                    {"nome": "Origens de Problemas", "view_name": "acoes:origem_problema_list", "perm": "core.nav_acoes_origens"},
                    {"nome": "Tipos de Solução", "view_name": "acoes:tipo_solucao_list", "perm": "core.nav_acoes_tipos"},
                    {"nome": "KPIs", "view_name": "acoes:kpi_opcao_list", "perm": "core.nav_acoes_kpis"},
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
                ],
            },
            {
                "key": "avaliacao",
                "nome": "AVALIAÇÃO",
                "perm": "core.nav_fornecedores_avaliacao",
                "funcoes": [
                    {"nome": "Perguntas de Avaliação", "view_name": "fornecedores:pergunta_list", "perm": "core.nav_fornecedores_perguntas"},
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
                    {"nome": "Detalhe do Registro", "view_name": "auditoria:registro_detail", "perm": "core.nav_auditoria_detalhe_registro"},
                    {"nome": "Registros por Modelo", "view_name": "auditoria:registros_por_modelo", "perm": "core.nav_auditoria_registros_por_modelo"},
                    {"nome": "Exportar Respostas (Excel)", "view_name": "auditoria:exportar_respostas_excel", "perm": "core.nav_auditoria_exportar_excel"},
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
                    {"nome": "Detalhe do Registro", "view_name": "insumos:registro_detail", "perm": "core.nav_insumos_detalhe_registro"},
                    {"nome": "Registros por Modelo", "view_name": "insumos:registros_por_modelo", "perm": "core.nav_insumos_registros_por_modelo"},
                    {"nome": "Exportar Respostas (Excel)", "view_name": "insumos:exportar_respostas_excel", "perm": "core.nav_insumos_exportar_excel"},
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
    def _sort_key(text: str | None) -> str:
        value = str(text or "")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        return value.casefold()

    return sorted(NAV_STRUCTURE, key=lambda m: _sort_key(m.get("nome")))


def _nav_module_config(module_key: str):
    for item in NAV_STRUCTURE:
        if item.get("key") == module_key:
            return item
    return None


def get_view_permission_map() -> dict[str, dict[str, str]]:
    """Retorna um mapa: view_name -> {perm, module_key}."""
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


def user_has_any_nav_perm_for_module(user, module_key: str) -> bool:
    """Indica se o usuário já está 'configurado' no novo modelo para o módulo."""
    module = _nav_module_config(module_key)
    if not module:
        return False
    if user.has_perm(module.get("module_perm")):
        return True
    for bloco in module.get("blocos") or []:
        if user.has_perm(bloco.get("perm")):
            return True
        for func in bloco.get("funcoes") or []:
            if user.has_perm(func.get("perm")):
                return True
    return False


def has_module_nav_flag(user, module_key: str) -> bool:
    module = _nav_module_config(module_key)
    if not module:
        return False
    return user.has_perm(module.get("module_perm"))


def has_block_nav_flag(user, module_key: str, block_key: str) -> bool:
    module = _nav_module_config(module_key)
    if not module:
        return False
    for bloco in module.get("blocos") or []:
        if bloco.get("key") == block_key:
            return user.has_perm(bloco.get("perm"))
    return False


def has_view_access(user, view_name: str) -> bool:
    """Valida acesso a uma função (view_name).

    Regras:
    - Superuser/staff: True
    - Se view não estiver mapeada: True (não controlamos)
    - Se usuário está em modo legado (grupo do módulo) e não tem nenhum nav_* do módulo: True
    - Caso contrário: exige permissão nav_* da função
    """
    if user.is_superuser or user.is_staff:
        return True

    data = VIEW_NAME_TO_PERMISSION.get(view_name)
    if not data:
        return True

    module_key = data.get("module")
    required_perm = data.get("perm")

    # Legado: se o usuário tem acesso ao módulo via grupo e ainda não tem nenhum nav_* no módulo,
    # não bloquear as funções (transição suave).
    if module_key and has_module_access(user, module_key) and not user_has_any_nav_perm_for_module(user, module_key):
        return True

    return bool(required_perm and user.has_perm(required_perm))

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
            return bool(module_perm and user.has_perm(module_perm))

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

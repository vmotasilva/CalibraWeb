from django.db import models

# ==============================================================================
# CORE - CONSTANTES E MODELOS BASE
# ==============================================================================

# CONSTANTES GLOBAIS (Reutilizadas por todos os apps)
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]


# ==============================================================================
# MODELO: UnidadeMedida
# ==============================================================================
class UnidadeMedida(models.Model):
    nome = models.CharField(
        max_length=50, unique=True, verbose_name="Unidade de Medida"
    )
    descricao = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="Descrição"
    )

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["nome"]


# ==============================================================================
# PERMISSÕES DE NAVEGAÇÃO (NAVBAR / MÓDULOS / BLOCOS / FUNÇÕES)
# ==============================================================================
class NavigationPermission(models.Model):
    """Modelo 'virtual' apenas para registrar permissões customizadas.

    Não cria tabela; serve para o Django criar entradas em auth_permission
    com codenames nav_* que controlam:
    - Aparição do módulo no NAVBAR
    - Visibilidade de blocos dentro do módulo
    - Acesso/visibilidade de funções (itens do menu)
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            # --- MÓDULOS (aparecem no navbar) ---
            ("nav_mod_metrologia", "NAV: Módulo Metrologia"),
            ("nav_mod_treinamentos", "NAV: Módulo Treinamentos"),
            ("nav_mod_pessoas", "NAV: Módulo Pessoas"),
            ("nav_mod_acoes", "NAV: Módulo Ações Corretivas"),
            ("nav_mod_fornecedores", "NAV: Módulo Fornecedores"),
            ("nav_mod_auditoria", "NAV: Módulo Auditoria"),
            ("nav_mod_insumos", "NAV: Módulo Insumos"),
            ("nav_mod_usuarios", "NAV: Módulo Usuários"),

            # --- METROLOGIA: blocos ---
            ("nav_metrologia_visao_geral", "NAV: Metrologia / Bloco Visão Geral"),
            ("nav_metrologia_gestao", "NAV: Metrologia / Bloco Gestão"),
            ("nav_metrologia_cotacoes", "NAV: Metrologia / Bloco Cotações"),
            ("nav_metrologia_importacao", "NAV: Metrologia / Bloco Importação"),

            # --- METROLOGIA: funções ---
            ("nav_metrologia_dashboard", "NAV: Metrologia / Dashboard"),
            ("nav_metrologia_lista_instrumentos", "NAV: Metrologia / Lista de Instrumentos"),
            ("nav_metrologia_novo_instrumento", "NAV: Metrologia / Novo Instrumento"),
            ("nav_metrologia_detalhe_instrumento", "NAV: Metrologia / Detalhe do Instrumento"),
            ("nav_metrologia_editar_instrumento", "NAV: Metrologia / Editar Instrumento"),
            ("nav_metrologia_historicos_calibracao", "NAV: Metrologia / Históricos de Calibração"),
            ("nav_metrologia_registrar_historico", "NAV: Metrologia / Registrar Histórico de Calibração"),
            ("nav_metrologia_visualizar_historico", "NAV: Metrologia / Visualizar Histórico de Calibração"),
            ("nav_metrologia_editar_historico", "NAV: Metrologia / Editar Histórico de Calibração"),
            ("nav_metrologia_remover_historico", "NAV: Metrologia / Remover Histórico de Calibração"),
            ("nav_metrologia_categorias", "NAV: Metrologia / Categorias"),
            ("nav_metrologia_categoria_create", "NAV: Metrologia / Nova Categoria"),
            ("nav_metrologia_categoria_update", "NAV: Metrologia / Editar Categoria"),
            ("nav_metrologia_categoria_delete", "NAV: Metrologia / Deletar Categoria"),
            ("nav_metrologia_categoria_bulk_update", "NAV: Metrologia / Atualizações em Massa (Categoria)"),
            ("nav_metrologia_faixa_categoria_create", "NAV: Metrologia / Nova Faixa (Categoria)"),
            ("nav_metrologia_faixa_categoria_update", "NAV: Metrologia / Editar Faixa (Categoria)"),
            ("nav_metrologia_faixa_categoria_delete", "NAV: Metrologia / Deletar Faixa (Categoria)"),
            ("nav_metrologia_faixa_instrumento_delete", "NAV: Metrologia / Remover Faixa-Instrumento"),
            ("nav_metrologia_faixa_instrumento_bulk_delete", "NAV: Metrologia / Remover Faixa-Instrumento em Massa"),
            ("nav_metrologia_unidades_medida", "NAV: Metrologia / Unidades de Medida"),
            ("nav_metrologia_unidade_create", "NAV: Metrologia / Nova Unidade de Medida"),
            ("nav_metrologia_unidade_update", "NAV: Metrologia / Editar Unidade de Medida"),
            ("nav_metrologia_unidade_delete", "NAV: Metrologia / Deletar Unidade de Medida"),

            ("nav_metrologia_download_arquivo_padrao", "NAV: Metrologia / Arquivo Padrão (Download)"),
            ("nav_metrologia_remover_arquivo_padrao", "NAV: Metrologia / Arquivo Padrão (Remover)"),
            ("nav_metrologia_download_certificado", "NAV: Metrologia / Certificado (Download)"),
            ("nav_metrologia_remover_carimbo_certificado", "NAV: Metrologia / Certificado (Remover Carimbo)"),
            ("nav_metrologia_remover_certificado_historico", "NAV: Metrologia / Certificado (Remover)"),
            ("nav_metrologia_solicitacoes_cotacao", "NAV: Metrologia / Solicitações de Cotação"),
            ("nav_metrologia_solicitacao_create", "NAV: Metrologia / Nova Solicitação de Cotação"),
            ("nav_metrologia_solicitacao_update", "NAV: Metrologia / Editar Solicitação de Cotação"),
            ("nav_metrologia_solicitacao_delete", "NAV: Metrologia / Deletar Solicitação de Cotação"),
            ("nav_metrologia_item_solicitacao_edit", "NAV: Metrologia / Editar Item da Solicitação"),
            ("nav_metrologia_item_solicitacao_delete", "NAV: Metrologia / Deletar Item da Solicitação"),
            ("nav_metrologia_cotacao_fornecedor_create", "NAV: Metrologia / Nova Cotação (Fornecedor)"),
            ("nav_metrologia_cotacao_fornecedor_update", "NAV: Metrologia / Editar Cotação (Fornecedor)"),
            ("nav_metrologia_atendimento_create", "NAV: Metrologia / Novo Atendimento"),
            ("nav_metrologia_export_etiquetas", "NAV: Metrologia / Exportar Etiquetas"),
            ("nav_metrologia_export_instrumentos", "NAV: Metrologia / Exportar Instrumentos"),
            ("nav_metrologia_export_estatisticas", "NAV: Metrologia / Exportar Estatísticas"),
            ("nav_metrologia_importar_instrumentos", "NAV: Metrologia / Importar Instrumentos"),
            ("nav_metrologia_importar_historico", "NAV: Metrologia / Importar Histórico"),
            ("nav_metrologia_import_jobs", "NAV: Metrologia / Acompanhar Importações (Jobs)"),

            # --- TREINAMENTOS: blocos ---
            ("nav_treinamentos_acompanhamento", "NAV: Treinamentos / Bloco Acompanhamento"),
            ("nav_treinamentos_gestao", "NAV: Treinamentos / Bloco Gestão de Treinamentos"),
            ("nav_treinamentos_matriz", "NAV: Treinamentos / Bloco Matriz de Competências"),
            ("nav_treinamentos_perfis_bloco", "NAV: Treinamentos / Bloco Perfis de Treinamento"),
            ("nav_treinamentos_procedimentos_bloco", "NAV: Treinamentos / Bloco Procedimentos"),

            # --- TREINAMENTOS: funções ---
            ("nav_treinamentos_dashboard", "NAV: Treinamentos / Dashboard"),
            ("nav_treinamentos_calendario", "NAV: Treinamentos / Calendário"),
            ("nav_treinamentos_dashboard_export_csv", "NAV: Treinamentos / Exportar Dashboard (CSV)"),
            ("nav_treinamentos_registros", "NAV: Treinamentos / Registros de Treinamento"),
            ("nav_treinamentos_novo_treinamento", "NAV: Treinamentos / Novo Treinamento"),
            ("nav_treinamentos_detalhe_treinamento", "NAV: Treinamentos / Detalhe do Treinamento"),
            ("nav_treinamentos_editar_treinamento", "NAV: Treinamentos / Editar Treinamento"),
            ("nav_treinamentos_importar_treinamentos", "NAV: Treinamentos / Importar Lista de Presença"),
            ("nav_treinamentos_download_template", "NAV: Treinamentos / Download Template Importação"),
            ("nav_treinamentos_exportar_treinamentos", "NAV: Treinamentos / Exportar Treinamentos (Excel)"),
            ("nav_treinamentos_listas_presenca", "NAV: Treinamentos / Listas de Presença"),
            ("nav_treinamentos_lista_presenca_create", "NAV: Treinamentos / Nova Lista de Presença"),
            ("nav_treinamentos_lista_presenca_edit", "NAV: Treinamentos / Editar Lista de Presença"),
            ("nav_treinamentos_lista_presenca_delete", "NAV: Treinamentos / Deletar Lista de Presença"),
            ("nav_treinamentos_lista_presenca_import", "NAV: Treinamentos / Importar Lista de Presença"),
            ("nav_treinamentos_lista_presenca_export", "NAV: Treinamentos / Exportar Listas de Presença"),
            ("nav_treinamentos_lista_presenca_export_pdf", "NAV: Treinamentos / Exportar Lista de Presença (PDF)"),
            ("nav_treinamentos_lista_presenca_template", "NAV: Treinamentos / Template Lista de Presença"),
            ("nav_treinamentos_lista_presenca_template_upload", "NAV: Treinamentos / Upload Template Lista de Presença"),
            ("nav_treinamentos_lista_presenca_erros_download", "NAV: Treinamentos / Download Erros Importação"),
            ("nav_treinamentos_lista_presenca_upload_assinada", "NAV: Treinamentos / Upload Lista Assinada"),
            ("nav_treinamentos_lista_presenca_remover_assinada", "NAV: Treinamentos / Remover Lista Assinada"),
            ("nav_treinamentos_planejamento", "NAV: Treinamentos / Planejamento"),
            ("nav_treinamentos_planejamento_delete", "NAV: Treinamentos / Deletar Planejamento"),
            ("nav_treinamentos_planejamento_mass_delete", "NAV: Treinamentos / Excluir Planejamentos (Massa)"),
            ("nav_treinamentos_planejamento_export", "NAV: Treinamentos / Exportar Planejamentos (Excel)"),
            ("nav_treinamentos_planejamento_procedimento_remove", "NAV: Treinamentos / Remover Procedimento do Planejamento"),
            ("nav_treinamentos_planejamento_colaborador_remove", "NAV: Treinamentos / Remover Colaborador do Planejamento"),

            ("nav_treinamentos_fornecedor_create", "NAV: Treinamentos / Novo Fornecedor"),
            ("nav_treinamentos_fornecedor_update", "NAV: Treinamentos / Editar Fornecedor"),
            ("nav_treinamentos_cotacao_update", "NAV: Treinamentos / Editar Cotação"),
            ("nav_treinamentos_orcamento_create", "NAV: Treinamentos / Novo Orçamento"),
            ("nav_treinamentos_orcamento_update", "NAV: Treinamentos / Editar Orçamento"),
            ("nav_treinamentos_matrizes", "NAV: Treinamentos / Matrizes"),
            ("nav_treinamentos_matrizes_delete", "NAV: Treinamentos / Deletar Matriz"),
            ("nav_treinamentos_matrizes_export", "NAV: Treinamentos / Exportar Matrizes"),
            ("nav_treinamentos_matrizes_import", "NAV: Treinamentos / Importação de Matriz"),
            ("nav_treinamentos_matrizes_template", "NAV: Treinamentos / Template Importação Matriz"),
            ("nav_treinamentos_matrizes_colaborador_remove", "NAV: Treinamentos / Remover Colaborador da Matriz"),
            ("nav_treinamentos_disciplinas", "NAV: Treinamentos / Disciplinas"),
            ("nav_treinamentos_disciplinas_delete", "NAV: Treinamentos / Deletar Disciplina"),
            ("nav_treinamentos_disciplina_procedimento_remove", "NAV: Treinamentos / Remover Procedimento da Disciplina"),
            ("nav_treinamentos_avaliacoes", "NAV: Treinamentos / Avaliações de Colaboradores"),
            ("nav_treinamentos_avaliacao_edit", "NAV: Treinamentos / Editar Avaliação"),
            ("nav_treinamentos_perfis", "NAV: Treinamentos / Perfis e Grupos"),
            ("nav_treinamentos_perfis_delete", "NAV: Treinamentos / Deletar Perfil (API)"),
            ("nav_treinamentos_perfis_mass_delete", "NAV: Treinamentos / Deletar Perfis em Massa (API)"),
            ("nav_treinamentos_perfis_import", "NAV: Treinamentos / Importar Perfis"),
            ("nav_treinamentos_perfis_import_estrutura", "NAV: Treinamentos / Importar Estrutura"),
            ("nav_treinamentos_perfis_export_estrutura", "NAV: Treinamentos / Exportar Estrutura"),
            ("nav_treinamentos_perfis_export_erros", "NAV: Treinamentos / Exportar Erros Importação"),
            ("nav_treinamentos_perfis_template_importacao", "NAV: Treinamentos / Template Importação (Download)"),
            ("nav_treinamentos_perfis_upload_template", "NAV: Treinamentos / Upload Template"),
            ("nav_treinamentos_perfis_delete_template", "NAV: Treinamentos / Remover Template"),
            ("nav_treinamentos_grupo_create", "NAV: Treinamentos / Novo Grupo"),
            ("nav_treinamentos_grupo_update", "NAV: Treinamentos / Editar Grupo"),
            ("nav_treinamentos_grupo_delete", "NAV: Treinamentos / Deletar Grupo"),
            ("nav_treinamentos_subgrupo_create", "NAV: Treinamentos / Novo Subgrupo"),
            ("nav_treinamentos_subgrupo_update", "NAV: Treinamentos / Editar Subgrupo"),
            ("nav_treinamentos_subgrupo_delete", "NAV: Treinamentos / Deletar Subgrupo"),
            ("nav_treinamentos_subgrupo_procedimento_remove", "NAV: Treinamentos / Remover Procedimento do Subgrupo"),
            ("nav_treinamentos_perfis_colaborador_edit", "NAV: Treinamentos / Editar Colaborador do Perfil"),
            ("nav_treinamentos_perfis_colaborador_remove", "NAV: Treinamentos / Remover Colaborador do Perfil"),
            ("nav_treinamentos_perfis_colaborador_mass_remove", "NAV: Treinamentos / Remover Colaboradores em Massa"),
            ("nav_treinamentos_procedimentos", "NAV: Treinamentos / Procedimentos"),
            ("nav_treinamentos_novo_procedimento", "NAV: Treinamentos / Novo Procedimento"),
            ("nav_treinamentos_editar_procedimento", "NAV: Treinamentos / Editar Procedimento"),
            ("nav_treinamentos_importar_procedimentos", "NAV: Treinamentos / Importar Procedimentos"),
            ("nav_treinamentos_exportar_procedimentos", "NAV: Treinamentos / Exportar Procedimentos (Excel)"),
            ("nav_treinamentos_procedimentos_matrizes", "NAV: Treinamentos / Matrizes e Sub-áreas (Procedimentos)"),
            ("nav_treinamentos_procedimentos_matrizes_import", "NAV: Treinamentos / Importar Matrizes e Sub-áreas (Procedimentos)"),
            ("nav_treinamentos_procedimentos_subareas_api", "NAV: Treinamentos / API Sub-áreas por Matriz"),

            # --- PESSOAS: blocos ---
            ("nav_pessoas_equipe", "NAV: Pessoas / Bloco Equipe"),
            ("nav_pessoas_importacao", "NAV: Pessoas / Bloco Importação"),

            # --- PESSOAS: funções ---
            ("nav_pessoas_colaboradores", "NAV: Pessoas / Colaboradores"),
            ("nav_pessoas_novo_colaborador", "NAV: Pessoas / Novo Colaborador"),
            ("nav_pessoas_detalhe_colaborador", "NAV: Pessoas / Detalhe do Colaborador"),
            ("nav_pessoas_editar_colaborador", "NAV: Pessoas / Editar Colaborador"),
            ("nav_pessoas_gestao_ferias", "NAV: Pessoas / Gestão de Férias"),
            ("nav_pessoas_registrar_ferias", "NAV: Pessoas / Registrar Férias"),
            ("nav_pessoas_editar_ferias", "NAV: Pessoas / Editar Férias"),
            ("nav_pessoas_excluir_ferias", "NAV: Pessoas / Excluir Férias"),
            ("nav_pessoas_importar_ferias", "NAV: Pessoas / Importar Férias"),
            ("nav_pessoas_exportar_ferias", "NAV: Pessoas / Exportar Férias"),
            ("nav_pessoas_liderancas", "NAV: Pessoas / Lideranças"),
            ("nav_pessoas_ocorrencias", "NAV: Pessoas / Ocorrências"),
            ("nav_pessoas_editar_ocorrencia", "NAV: Pessoas / Editar Ocorrência"),
            ("nav_pessoas_deletar_ocorrencia", "NAV: Pessoas / Deletar Ocorrência"),
            ("nav_pessoas_api_delete_colaborador", "NAV: Pessoas / Deletar Colaborador (API)"),
            ("nav_pessoas_api_delete_colaboradores_multiple", "NAV: Pessoas / Deletar Colaboradores em Massa (API)"),
            ("nav_pessoas_importar_pessoas", "NAV: Pessoas / Importar Pessoas"),
            ("nav_pessoas_importar_hierarquia", "NAV: Pessoas / Importar Hierarquia"),

            # --- AÇÕES CORRETIVAS: blocos ---
            ("nav_acoes_registro", "NAV: Ações Corretivas / Bloco Registro e Solução"),
            ("nav_acoes_referencia", "NAV: Ações Corretivas / Bloco Referência de Dados"),

            # --- AÇÕES CORRETIVAS: funções ---
            ("nav_acoes_registradas", "NAV: Ações Corretivas / Ações Registradas"),
            ("nav_acoes_controle_registros", "NAV: Ações Corretivas / Controle de Registros"),
            ("nav_acoes_origens", "NAV: Ações Corretivas / Origens de Problemas"),
            ("nav_acoes_tipos", "NAV: Ações Corretivas / Tipos de Solução"),
            ("nav_acoes_kpis", "NAV: Ações Corretivas / KPIs"),

            ("nav_acoes_listar_acoes", "NAV: Ações Corretivas / Listar Ações"),
            ("nav_acoes_salvar_acao", "NAV: Ações Corretivas / Salvar Ação (Modal)"),
            ("nav_acoes_detalhe_acao", "NAV: Ações Corretivas / Detalhe da Ação"),

            ("nav_acoes_detalhe_solucao", "NAV: Ações Corretivas / Detalhe da Solução (Legacy)"),
            ("nav_acoes_criar_solucao", "NAV: Ações Corretivas / Criar Solução (Legacy)"),
            ("nav_acoes_editar_solucao", "NAV: Ações Corretivas / Editar Solução (Legacy)"),

            ("nav_acoes_importar_controle_registros", "NAV: Ações Corretivas / Importar Controle de Registros"),
            ("nav_acoes_download_template_controle_registros", "NAV: Ações Corretivas / Template Controle de Registros"),
            ("nav_acoes_importar_plano_acao", "NAV: Ações Corretivas / Importar Plano de Ação"),
            ("nav_acoes_download_template_plano_acao", "NAV: Ações Corretivas / Template Plano de Ação"),

            ("nav_acoes_importar_acoes_associadas", "NAV: Ações Corretivas / Importar Ações Associadas"),
            ("nav_acoes_download_template_acoes_associadas", "NAV: Ações Corretivas / Template Ações Associadas"),
            ("nav_acoes_exportar_acoes_associadas", "NAV: Ações Corretivas / Exportar Ações Associadas"),
            ("nav_acoes_deletar_acoes_associadas", "NAV: Ações Corretivas / Deletar Ações Associadas"),

            ("nav_acoes_plano", "NAV: Ações Corretivas / Bloco Plano de Ação"),
            ("nav_acoes_dashboard", "NAV: Ações Corretivas / Dashboard"),
            ("nav_acoes_listar_templates", "NAV: Ações Corretivas / Templates (Lista)"),
            ("nav_acoes_download_template", "NAV: Ações Corretivas / Template (Download)"),
            ("nav_acoes_api_proximo_numero", "NAV: Ações Corretivas / Próximo Número (API)"),
            ("nav_acoes_criar_registro_modal", "NAV: Ações Corretivas / Criar Registro (Modal - Legacy)"),
            ("nav_acoes_plano_list", "NAV: Ações Corretivas / Planos de Ação (Lista)"),
            ("nav_acoes_plano_create", "NAV: Ações Corretivas / Novo Plano de Ação"),
            ("nav_acoes_plano_update", "NAV: Ações Corretivas / Editar Plano de Ação"),
            ("nav_acoes_plano_delete", "NAV: Ações Corretivas / Deletar Plano de Ação"),
            ("nav_acoes_plano_detail", "NAV: Ações Corretivas / Detalhe do Plano de Ação"),

            ("nav_acoes_linha_create", "NAV: Ações Corretivas / Adicionar Linha de Ação"),
            ("nav_acoes_linha_update", "NAV: Ações Corretivas / Editar Linha de Ação"),
            ("nav_acoes_linha_delete", "NAV: Ações Corretivas / Deletar Linha de Ação"),
            ("nav_acoes_linha_dados", "NAV: Ações Corretivas / Dados da Linha de Ação"),

            ("nav_acoes_a3_list", "NAV: Ações Corretivas / A3 (Lista)"),
            ("nav_acoes_a3_create", "NAV: Ações Corretivas / A3 (Nova)"),
            ("nav_acoes_a3_update", "NAV: Ações Corretivas / A3 (Editar)"),
            ("nav_acoes_a3_detail", "NAV: Ações Corretivas / A3 (Detalhe)"),

            ("nav_acoes_8d_list", "NAV: Ações Corretivas / 8D (Lista)"),
            ("nav_acoes_8d_create", "NAV: Ações Corretivas / 8D (Nova)"),
            ("nav_acoes_8d_update", "NAV: Ações Corretivas / 8D (Editar)"),
            ("nav_acoes_8d_detail", "NAV: Ações Corretivas / 8D (Detalhe)"),

            ("nav_acoes_rnc_list", "NAV: Ações Corretivas / RNC (Lista)"),
            ("nav_acoes_rnc_create", "NAV: Ações Corretivas / RNC (Nova)"),
            ("nav_acoes_rnc_update", "NAV: Ações Corretivas / RNC (Editar)"),
            ("nav_acoes_rnc_detail", "NAV: Ações Corretivas / RNC (Detalhe)"),

            ("nav_acoes_mudanca_list", "NAV: Ações Corretivas / Gestão de Mudança (Lista)"),
            ("nav_acoes_mudanca_create", "NAV: Ações Corretivas / Gestão de Mudança (Nova)"),
            ("nav_acoes_mudanca_update", "NAV: Ações Corretivas / Gestão de Mudança (Editar)"),
            ("nav_acoes_mudanca_detail", "NAV: Ações Corretivas / Gestão de Mudança (Detalhe)"),

            ("nav_acoes_revisao_list", "NAV: Ações Corretivas / Revisão Gerencial (Lista)"),
            ("nav_acoes_revisao_create", "NAV: Ações Corretivas / Revisão Gerencial (Nova)"),
            ("nav_acoes_revisao_update", "NAV: Ações Corretivas / Revisão Gerencial (Editar)"),
            ("nav_acoes_revisao_detail", "NAV: Ações Corretivas / Revisão Gerencial (Detalhe)"),

            ("nav_acoes_origens_create", "NAV: Ações Corretivas / Nova Origem de Problema"),
            ("nav_acoes_origens_update", "NAV: Ações Corretivas / Editar Origem de Problema"),
            ("nav_acoes_origens_delete", "NAV: Ações Corretivas / Deletar Origem de Problema"),
            ("nav_acoes_tipos_create", "NAV: Ações Corretivas / Novo Tipo de Solução"),
            ("nav_acoes_tipos_update", "NAV: Ações Corretivas / Editar Tipo de Solução"),
            ("nav_acoes_tipos_delete", "NAV: Ações Corretivas / Deletar Tipo de Solução"),
            ("nav_acoes_kpis_create", "NAV: Ações Corretivas / Novo KPI"),
            ("nav_acoes_kpis_update", "NAV: Ações Corretivas / Editar KPI"),
            ("nav_acoes_kpis_delete", "NAV: Ações Corretivas / Deletar KPI"),

            # --- FORNECEDORES: bloco ---
            ("nav_fornecedores_gestao", "NAV: Fornecedores / Bloco Gestão"),
            ("nav_fornecedores_avaliacao", "NAV: Fornecedores / Bloco Avaliação"),

            # --- FORNECEDORES: funções ---
            ("nav_fornecedores_lista", "NAV: Fornecedores / Lista de Fornecedores"),
            ("nav_fornecedores_novo", "NAV: Fornecedores / Novo Fornecedor"),
            ("nav_fornecedores_perguntas", "NAV: Fornecedores / Perguntas de Avaliação"),
            ("nav_fornecedores_editar", "NAV: Fornecedores / Editar Fornecedor"),
            ("nav_fornecedores_pergunta_create", "NAV: Fornecedores / Nova Pergunta"),
            ("nav_fornecedores_pergunta_edit", "NAV: Fornecedores / Editar Pergunta"),
            ("nav_fornecedores_pergunta_delete", "NAV: Fornecedores / Remover Pergunta"),
            ("nav_fornecedores_avaliacao_create", "NAV: Fornecedores / Nova Avaliação"),
            ("nav_fornecedores_avaliacao_edit", "NAV: Fornecedores / Editar Avaliação"),
            ("nav_fornecedores_avaliacao_matriz", "NAV: Fornecedores / Criar Matriz de Avaliação"),
            ("nav_fornecedores_reavaliacao_create", "NAV: Fornecedores / Nova Reavaliação"),
            ("nav_fornecedores_reavaliacao_delete", "NAV: Fornecedores / Deletar Reavaliação"),
            ("nav_fornecedores_avaliacao_selecao", "NAV: Fornecedores / Criar Seleção"),
            ("nav_fornecedores_documento_create", "NAV: Fornecedores / Novo Documento"),
            ("nav_fornecedores_documento_delete", "NAV: Fornecedores / Remover Documento"),
            ("nav_fornecedores_export_avaliacoes", "NAV: Fornecedores / Exportar Avaliações (Excel)"),

            # --- AUDITORIA: blocos ---
            ("nav_auditoria_cadastro", "NAV: Auditoria / Bloco Cadastro"),
            ("nav_auditoria_operacao", "NAV: Auditoria / Bloco Operação"),
            ("nav_auditoria_analise", "NAV: Auditoria / Bloco Análise"),

            # --- AUDITORIA: funções ---
            ("nav_auditoria_nova", "NAV: Auditoria / Nova Auditoria"),
            ("nav_auditoria_modelos", "NAV: Auditoria / Modelos de Auditoria"),
            ("nav_auditoria_novo_modelo", "NAV: Auditoria / Novo Modelo"),
            ("nav_auditoria_editar_modelo", "NAV: Auditoria / Editar Modelo"),
            ("nav_auditoria_duplicar_modelo", "NAV: Auditoria / Duplicar Modelo"),
            ("nav_auditoria_remover_modelo", "NAV: Auditoria / Remover Modelo"),
            ("nav_auditoria_perguntas", "NAV: Auditoria / Perguntas por Modelo"),
            ("nav_auditoria_nova_pergunta", "NAV: Auditoria / Nova Pergunta"),
            ("nav_auditoria_editar_pergunta", "NAV: Auditoria / Editar Pergunta"),
            ("nav_auditoria_duplicar_pergunta", "NAV: Auditoria / Duplicar Pergunta"),
            ("nav_auditoria_remover_pergunta", "NAV: Auditoria / Remover Pergunta"),
            ("nav_auditoria_registros", "NAV: Auditoria / Modelos Cadastrados / Período"),
            ("nav_auditoria_avaliacao", "NAV: Auditoria / Avaliação de Dados"),
            ("nav_auditoria_editar_registro", "NAV: Auditoria / Editar Registro"),
            ("nav_auditoria_detalhe_registro", "NAV: Auditoria / Detalhe do Registro"),
            ("nav_auditoria_registros_por_modelo", "NAV: Auditoria / Registros por Modelo"),
            ("nav_auditoria_exportar_excel", "NAV: Auditoria / Exportar Respostas (Excel)"),
            ("nav_auditoria_comentario_edit", "NAV: Auditoria / Editar Comentário"),
            ("nav_auditoria_comentario_delete", "NAV: Auditoria / Remover Comentário"),
            ("nav_auditoria_dashboard", "NAV: Auditoria / Dashboard"),

            # --- INSUMOS: blocos ---
            ("nav_insumos_cadastro", "NAV: Insumos / Bloco Cadastro"),
            ("nav_insumos_operacao", "NAV: Insumos / Bloco Operação"),
            ("nav_insumos_analise", "NAV: Insumos / Bloco Análise"),

            # --- INSUMOS: funções ---
            ("nav_insumos_novo", "NAV: Insumos / Novo Registro"),
            ("nav_insumos_modelos", "NAV: Insumos / Modelos"),
            ("nav_insumos_novo_modelo", "NAV: Insumos / Novo Modelo"),
            ("nav_insumos_editar_modelo", "NAV: Insumos / Editar Modelo"),
            ("nav_insumos_remover_modelo", "NAV: Insumos / Remover Modelo"),
            ("nav_insumos_perguntas", "NAV: Insumos / Perguntas"),
            ("nav_insumos_nova_pergunta", "NAV: Insumos / Nova Pergunta"),
            ("nav_insumos_editar_pergunta", "NAV: Insumos / Editar Pergunta"),
            ("nav_insumos_remover_pergunta", "NAV: Insumos / Remover Pergunta"),
            ("nav_insumos_registros", "NAV: Insumos / Registros"),
            ("nav_insumos_avaliacao", "NAV: Insumos / Avaliação de Dados"),
            ("nav_insumos_editar_registro", "NAV: Insumos / Editar Registro"),
            ("nav_insumos_detalhe_registro", "NAV: Insumos / Detalhe do Registro"),
            ("nav_insumos_registros_por_modelo", "NAV: Insumos / Registros por Modelo"),
            ("nav_insumos_exportar_excel", "NAV: Insumos / Exportar Respostas (Excel)"),
            ("nav_insumos_comentario_edit", "NAV: Insumos / Editar Comentário"),
            ("nav_insumos_comentario_delete", "NAV: Insumos / Remover Comentário"),
            ("nav_insumos_dashboard", "NAV: Insumos / Dashboard"),

            # --- USUÁRIOS: funções ---
            ("nav_usuarios_lista", "NAV: Usuários / Lista"),
        ]

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
            ("nav_metrologia_unidades_medida", "NAV: Metrologia / Unidades de Medida"),
            ("nav_metrologia_solicitacoes_cotacao", "NAV: Metrologia / Solicitações de Cotação"),
            ("nav_metrologia_importar_instrumentos", "NAV: Metrologia / Importar Instrumentos"),
            ("nav_metrologia_importar_historico", "NAV: Metrologia / Importar Histórico"),

            # --- TREINAMENTOS: blocos ---
            ("nav_treinamentos_gestao", "NAV: Treinamentos / Bloco Gestão de Treinamentos"),
            ("nav_treinamentos_matriz", "NAV: Treinamentos / Bloco Matriz de Competências"),
            ("nav_treinamentos_perfis_bloco", "NAV: Treinamentos / Bloco Perfis de Treinamento"),

            # --- TREINAMENTOS: funções ---
            ("nav_treinamentos_dashboard", "NAV: Treinamentos / Dashboard"),
            ("nav_treinamentos_registros", "NAV: Treinamentos / Registros de Treinamento"),
            ("nav_treinamentos_novo_treinamento", "NAV: Treinamentos / Novo Treinamento"),
            ("nav_treinamentos_detalhe_treinamento", "NAV: Treinamentos / Detalhe do Treinamento"),
            ("nav_treinamentos_editar_treinamento", "NAV: Treinamentos / Editar Treinamento"),
            ("nav_treinamentos_importar_treinamentos", "NAV: Treinamentos / Importar Lista de Presença"),
            ("nav_treinamentos_download_template", "NAV: Treinamentos / Download Template Importação"),
            ("nav_treinamentos_exportar_treinamentos", "NAV: Treinamentos / Exportar Treinamentos (Excel)"),
            ("nav_treinamentos_listas_presenca", "NAV: Treinamentos / Listas de Presença"),
            ("nav_treinamentos_planejamento", "NAV: Treinamentos / Planejamento"),
            ("nav_treinamentos_matrizes", "NAV: Treinamentos / Matrizes"),
            ("nav_treinamentos_disciplinas", "NAV: Treinamentos / Disciplinas"),
            ("nav_treinamentos_avaliacoes", "NAV: Treinamentos / Avaliações de Colaboradores"),
            ("nav_treinamentos_perfis", "NAV: Treinamentos / Perfis e Grupos"),
            ("nav_treinamentos_procedimentos", "NAV: Treinamentos / Procedimentos"),
            ("nav_treinamentos_novo_procedimento", "NAV: Treinamentos / Novo Procedimento"),
            ("nav_treinamentos_editar_procedimento", "NAV: Treinamentos / Editar Procedimento"),
            ("nav_treinamentos_importar_procedimentos", "NAV: Treinamentos / Importar Procedimentos"),
            ("nav_treinamentos_exportar_procedimentos", "NAV: Treinamentos / Exportar Procedimentos (Excel)"),

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

            # --- FORNECEDORES: bloco ---
            ("nav_fornecedores_gestao", "NAV: Fornecedores / Bloco Gestão"),
            ("nav_fornecedores_avaliacao", "NAV: Fornecedores / Bloco Avaliação"),

            # --- FORNECEDORES: funções ---
            ("nav_fornecedores_lista", "NAV: Fornecedores / Lista de Fornecedores"),
            ("nav_fornecedores_novo", "NAV: Fornecedores / Novo Fornecedor"),
            ("nav_fornecedores_perguntas", "NAV: Fornecedores / Perguntas de Avaliação"),

            # --- AUDITORIA: blocos ---
            ("nav_auditoria_cadastro", "NAV: Auditoria / Bloco Cadastro"),
            ("nav_auditoria_operacao", "NAV: Auditoria / Bloco Operação"),
            ("nav_auditoria_analise", "NAV: Auditoria / Bloco Análise"),

            # --- AUDITORIA: funções ---
            ("nav_auditoria_nova", "NAV: Auditoria / Nova Auditoria"),
            ("nav_auditoria_modelos", "NAV: Auditoria / Modelos de Auditoria"),
            ("nav_auditoria_perguntas", "NAV: Auditoria / Perguntas por Modelo"),
            ("nav_auditoria_registros", "NAV: Auditoria / Modelos Cadastrados / Período"),
            ("nav_auditoria_avaliacao", "NAV: Auditoria / Avaliação de Dados"),
            ("nav_auditoria_dashboard", "NAV: Auditoria / Dashboard"),

            # --- INSUMOS: blocos ---
            ("nav_insumos_cadastro", "NAV: Insumos / Bloco Cadastro"),
            ("nav_insumos_operacao", "NAV: Insumos / Bloco Operação"),
            ("nav_insumos_analise", "NAV: Insumos / Bloco Análise"),

            # --- INSUMOS: funções ---
            ("nav_insumos_novo", "NAV: Insumos / Novo Registro"),
            ("nav_insumos_modelos", "NAV: Insumos / Modelos"),
            ("nav_insumos_perguntas", "NAV: Insumos / Perguntas"),
            ("nav_insumos_registros", "NAV: Insumos / Registros"),
            ("nav_insumos_avaliacao", "NAV: Insumos / Avaliação de Dados"),
            ("nav_insumos_dashboard", "NAV: Insumos / Dashboard"),

            # --- USUÁRIOS: funções ---
            ("nav_usuarios_lista", "NAV: Usuários / Lista"),
        ]

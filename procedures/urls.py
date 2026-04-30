# -*- coding: utf-8 -*-
"""
URLs para o módulo Procedures
Consolida training + procurements
"""

from django.urls import path
from . import views
from .views import habilidades_views, perfis_views, avaliacoes_views, planejamento_views, gap_analysis_views, lista_presenca_views, validacao_views, template_mapeamento_views, acompanhamento_views
from .views.planejamento_api_matriz import api_disciplinas_por_matriz_view, api_procedimentos_por_disciplina_view, api_colaboradores_por_matriz_view, api_procedimentos_buscar_view, api_colaboradores_buscar_view
from training.views import views as training_views

app_name = 'procedures'

urlpatterns = [


    # ==========================
    # API ENDPOINTS
    # ==========================
    path('api/procedimentos/', views.api_procedimentos_list, name='api_procedimentos_list'),
    path('api/procedimentos-json/', lista_presenca_views.api_procedimentos_json_view, name='api_procedimentos_json'),
    path('api/procedimentos-busca/', lista_presenca_views.api_procedimentos_busca_view, name='api_procedimentos_busca'),
    path('api/colaboradores-json/', lista_presenca_views.api_colaboradores_json_view, name='api_colaboradores_json'),
    path('api/colaboradores-busca/', lista_presenca_views.api_colaboradores_busca_view, name='api_colaboradores_busca'),
    path('api/filtros-colaboradores/', habilidades_views.filtros_colaboradores_api, name='filtros_colaboradores_api'),
    path('api/subareas-por-matriz/', views.api_subareas_por_matriz_view, name='api_subareas_por_matriz'),
    
    # ==========================
    # PROCEDIMENTOS
    # ==========================
    path('procedimentos/', views.procedimentos_list_view, name='procedimentos_list'),
    path('procedimentos/export/excel/', views.export_procedimentos_excel_view, name='export_procedimentos_excel'),
    path('procedimentos/template/download/', views.download_template_procedimentos_view, name='dl_template_procedimentos'),
    path('procedimentos/importar/', views.importar_procedimentos_view, name='importar_procedimentos'),
    path('procedimentos/matrizes/', views.procedimento_matrizes_list_view, name='procedimento_matrizes_list'),
    path('procedimentos/matrizes/<int:matriz_id>/', views.procedimento_matriz_detalhe_view, name='procedimento_matriz_detalhe'),
    path('procedimentos/matrizes/importar/', views.importar_matrizes_subareas_view, name='importar_matrizes_subareas'),
    path('procedimentos/matrizes/template/', views.download_template_matrizes_subareas_view, name='download_template_matrizes_subareas'),
    path('procedimentos/novo/', views.novo_procedimento_view, name='novo_procedimento'),
    path('procedimentos/<int:procedimento_id>/editar/', views.editar_procedimento_view, name='editar_procedimento'),
    path('procedimentos/<int:procedimento_id>/', views.detalhe_procedimento_view, name='detalhe_procedimento'),
    
    # ==========================
    # TREINAMENTOS
    # ==========================
    path('treinamentos/', views.treinamentos_list_view, name='treinamentos_list'),
    path('treinamentos/historico/', views.treinamentos_historico_view, name='treinamentos_historico'),
    path('treinamentos/exportar-excel/', views.treinamentos_exportar_excel_view, name='treinamentos_exportar_excel'),
    path('treinamentos/<int:treinamento_id>/', views.treinamentos_detalhe_view, name='treinamentos_detalhe'),
    path('treinamentos/novo/', views.novo_treinamento_view, name='novo_treinamento'),
    path('treinamentos/<int:treinamento_id>/editar/', views.editar_treinamento_view, name='editar_treinamento'),
    path('treinamentos/importar/', lista_presenca_views.lista_presenca_importar_view, name='treinamentos_importar'),
    path('treinamentos/template-download/', lista_presenca_views.lista_presenca_download_template_view, name='treinamentos_template_download'),
    path('dashboard/', training_views.dashboard_treinamentos_view, name='dashboard_treinamentos'),
    path('treinamentos/calendario/', acompanhamento_views.calendario_treinamentos_view, name='treinamentos_calendario'),
    
    # ==========================
    # FORNECEDORES
    # ==========================
    path('fornecedores/', views.fornecedores_list_view, name='fornecedores_list'),
    path('fornecedores/novo/', views.novo_fornecedor_view, name='novo_fornecedor'),
    path('fornecedores/<int:fornecedor_id>/editar/', views.editar_fornecedor_view, name='editar_fornecedor'),
    path('fornecedores/<int:fornecedor_id>/', views.detalhe_fornecedor_view, name='detalhe_fornecedor'),
    
    # ==========================
    # AVALIAÇÕES
    # ==========================
    path('avaliações/novo/', views.nova_avaliacao_fornecedor_view, name='nova_avaliacao'),
    
    # ==========================
    # COTAÇÕES
    # ==========================
    path('cotacoes/', views.cotacoes_list_view, name='cotacoes_list'),
    path('cotacoes/novo/', views.nova_cotacao_view, name='nova_cotacao'),
    path('cotacoes/<int:cotacao_id>/editar/', views.editar_cotacao_view, name='editar_cotacao'),
    path('cotacoes/<int:cotacao_id>/', views.detalhe_cotacao_view, name='detalhe_cotacao'),
    
    # ==========================
    # ORÇAMENTOS
    # ==========================
    path('orcamentos/novo/', views.novo_orcamento_view, name='novo_orcamento'),
    path('orcamentos/<int:orcamento_id>/editar/', views.editar_orcamento_view, name='editar_orcamento'),
    
    # ==========================
    # MATRIZ DE HABILIDADES - DISCIPLINAS
    # ==========================
    path('disciplinas/', habilidades_views.disciplinas_list_view, name='disciplinas_list'),
    path('disciplinas/nova/', habilidades_views.nova_disciplina_view, name='nova_disciplina'),
    path('disciplinas/<int:disciplina_id>/editar/', habilidades_views.editar_disciplina_view, name='editar_disciplina'),
    path('disciplinas/<int:disciplina_id>/', habilidades_views.detalhe_disciplina_view, name='detalhe_disciplina'),
    path('disciplinas/<int:disciplina_id>/deletar/', habilidades_views.deletar_disciplina_view, name='deletar_disciplina'),
    path('disciplinas/<int:disciplina_id>/procedimento/adicionar/', habilidades_views.adicionar_procedimento_disciplina_view, name='adicionar_procedimento_disciplina'),
    path('disciplinas/<int:disciplina_id>/procedimento/adicionar-multiplos/', habilidades_views.adicionar_multiplos_procedimentos_view, name='adicionar_multiplos_procedimentos'),
    path('disciplinas/<int:disciplina_id>/procedimento/<int:assoc_id>/remover/', habilidades_views.remover_procedimento_disciplina_view, name='remover_procedimento_disciplina'),
    path('disciplinas/<int:disciplina_id>/api/filtrar-procedimentos/', habilidades_views.filtrar_procedimentos_view, name='filtrar_procedimentos'),
    path('disciplinas/<int:disciplina_id>/api/opcoes-filtro/', habilidades_views.obter_opcoes_filtro_view, name='opcoes_filtro'),
    
    # ==========================
    # MATRIZ DE HABILIDADES - MATRIZES
    # ==========================
    path('matrizes/', habilidades_views.matrizes_list_view, name='matrizes_list'),
    path('matrizes/nova/', habilidades_views.nova_matriz_view, name='nova_matriz'),
    path('matrizes/<int:matriz_id>/editar/', habilidades_views.editar_matriz_view, name='editar_matriz'),
    path('matrizes/<int:matriz_id>/deletar/', habilidades_views.deletar_matriz_view, name='deletar_matriz'),
    path('matrizes/<int:matriz_id>/', habilidades_views.detalhe_matriz_view, name='detalhe_matriz'),
    path('matrizes/<int:matriz_id>/avaliar/', habilidades_views.avaliar_matriz_view, name='avaliar_matriz'),
    path('matriz/<int:matriz_id>/colaboradores/', habilidades_views.matriz_colaboradores_api, name='matriz_colaboradores_api'),
    path('colaborador-matriz/<int:assoc_id>/remover/', habilidades_views.remover_colaborador_matriz, name='remover_colaborador_matriz'),
    
    # Importação em massa de matrizes
    path('matrizes/importacao/', habilidades_views.importacao_matriz_view, name='importacao_matriz'),
    path('matrizes/importacao/resultado/', habilidades_views.importacao_matriz_resultado_view, name='importacao_matriz_resultado'),
    path('matrizes/importacao/download-template/<str:formato>/', habilidades_views.baixar_template_importacao_view, name='baixar_template_importacao'),
    
    # Exportação de matrizes
    path('matrizes/exportar/<str:formato>/', habilidades_views.exportar_matrizes_view, name='exportar_matrizes'),
    
    # ==========================
    # PERFIS DE TREINAMENTO
    # ==========================
    path('perfis/', perfis_views.perfis_list_view, name='perfis_list'),
    path('perfis/novo/', perfis_views.novo_perfil_view, name='novo_perfil'),
    path('perfis/<int:perfil_id>/editar/', perfis_views.editar_perfil_view, name='editar_perfil'),
    path('perfis/<int:perfil_id>/', perfis_views.detalhe_perfil_view, name='detalhe_perfil'),
    path('perfil/<int:perfil_id>/reatribuir-todos-subgrupos/', perfis_views.reatribuir_todos_subgrupos_view, name='reatribuir_todos_subgrupos'),
    
    # API de deleção de perfis
    path('api/perfil/<int:perfil_id>/delete/', perfis_views.api_delete_perfil, name='api_delete_perfil'),
    path('api/perfis/delete-multiple/', perfis_views.api_delete_perfis_multiple, name='api_delete_perfis_multiple'),
    
    # Importação em massa
    path('perfis/importar/', perfis_views.importar_perfis_view, name='importar_perfis'),
    path('perfis/importar-estrutura/', perfis_views.importar_estrutura_completa_view, name='importar_estrutura'),
    path('perfis/exportar-estrutura/', perfis_views.exportar_estrutura_view, name='exportar_estrutura'),
    path('perfis/template-importacao/', perfis_views.download_template_importacao_view, name='download_template_importacao'),
    path('perfis/exportar-erros/', perfis_views.exportar_erros_importacao_view, name='exportar_erros_importacao'),
    
    # ==========================
    # GRUPOS DE TREINAMENTO
    # ==========================
    path('perfis/<int:perfil_id>/grupos/novo/', perfis_views.novo_grupo_view, name='novo_grupo'),
    path('grupos/<int:grupo_id>/editar/', perfis_views.editar_grupo_view, name='editar_grupo'),
    path('grupos/<int:grupo_id>/deletar/', perfis_views.deletar_grupo_view, name='deletar_grupo'),
    path('grupos/<int:grupo_id>/mover/<str:direcao>/', perfis_views.mover_grupo_view, name='mover_grupo'),
    
    # ==========================
    # SUBGRUPOS DE TREINAMENTO
    # ==========================
    path('grupos/<int:grupo_id>/subgrupos/novo/', perfis_views.novo_subgrupo_view, name='novo_subgrupo'),
    path('subgrupos/<int:subgrupo_id>/editar/', perfis_views.editar_subgrupo_view, name='editar_subgrupo'),
    path('subgrupos/<int:subgrupo_id>/deletar/', perfis_views.deletar_subgrupo_view, name='deletar_subgrupo'),
    path('subgrupos/<int:subgrupo_id>/mover/<str:direcao>/', perfis_views.mover_subgrupo_view, name='mover_subgrupo'),
    path('subgrupos/<int:subgrupo_id>/adicionar-procedimento/', perfis_views.adicionar_procedimento_subgrupo_view, name='adicionar_procedimento_subgrupo'),
    path('subgrupos/<int:subgrupo_id>/remover-procedimento/', perfis_views.remover_procedimento_subgrupo_view, name='remover_procedimento_subgrupo'),
    
    # ==========================
    # COLABORADORES E PERFIS
    # ==========================
    path('perfis/<int:perfil_id>/colaboradores/adicionar/', perfis_views.adicionar_colaborador_perfil_view, name='adicionar_colaborador_perfil'),
    path('perfis/<int:perfil_id>/colaboradores/editar/', perfis_views.editar_colaborador_perfil_view, name='editar_colaborador_perfil'),
    path('perfis/<int:perfil_id>/colaboradores/remover-massa/', perfis_views.remover_colaboradores_massa_view, name='remover_colaboradores_massa'),
    path('colaborador-perfil/<int:cp_id>/remover/', perfis_views.remover_colaborador_perfil_view, name='remover_colaborador_perfil'),
    path('colaboradores/<int:colaborador_id>/associar-perfil/', perfis_views.associar_perfil_colaborador_view, name='associar_perfil_colaborador'),
    path('colaborador-perfil/remover/<int:colaborador_id>/<int:perfil_id>/', perfis_views.remover_associacao_perfil_colaborador_view, name='remover_associacao_perfil_colaborador'),
    
    # ==========================
    # AVALIAÇÕES DE HABILIDADE
    # ==========================
    path('avaliacoes/', avaliacoes_views.matriz_avaliacoes_view, name='matriz_avaliacoes'),
    path('avaliacoes/<int:matriz_id>/<int:colaborador_id>/<int:disciplina_id>/', avaliacoes_views.editar_avaliacao_view, name='editar_avaliacao'),
    path('avaliacoes/colaborador/<int:colaborador_id>/', avaliacoes_views.avaliacoes_colaborador_view, name='avaliacoes_colaborador'),
    path('avaliacoes/rapida/', avaliacoes_views.avaliacao_rapida_view, name='avaliacao_rapida'),
    path('avaliacoes/salvar/', habilidades_views.salvar_avaliacao_api, name='salvar_avaliacao_api'),
    
    # APIs para Modal de Avaliação
    path('api/avaliacoes/<int:matriz_id>/<int:colaborador_id>/<int:disciplina_id>/', avaliacoes_views.obter_avaliacao_api, name='obter_avaliacao_api'),
    path('api/avaliacoes/<int:matriz_id>/<int:colaborador_id>/<int:disciplina_id>/salvar/', avaliacoes_views.salvar_avaliacao_api, name='salvar_avaliacao_modal_api'),
    
    # Gerenciamento de Colaboradores na Matriz
    path('matrizes/<int:matriz_id>/desassociar-colaboradores/', avaliacoes_views.desassociar_colaboradores_view, name='desassociar_colaboradores'),
    path('matrizes/<int:matriz_id>/associar-colaborador/', avaliacoes_views.associar_colaborador_view, name='associar_colaborador'),
    path('matrizes/<int:matriz_id>/colaboradores-disponiveis/', avaliacoes_views.colaboradores_disponiveis_view, name='colaboradores_disponiveis'),
    
    # ==========================
    # VALIDAÇÃO DE MATRIZ
    # ==========================
    path('matrizes/<int:matriz_id>/solicitar-validacao/', validacao_views.solicitar_validacao_view, name='solicitar_validacao'),
    path('matrizes/<int:matriz_id>/validacao-rapida/', validacao_views.validacao_rapida_view, name='validacao_rapida'),
    path('validacoes/pendentes/', validacao_views.validacoes_pendentes_view, name='validacoes_pendentes'),
    path('validacoes/<int:solicitacao_id>/validar/', validacao_views.validar_matriz_view, name='validar_matriz'),
    
    # ==========================
    # PLANEJAMENTO DE TREINAMENTOS
    # ==========================
    path('planejamentos/', planejamento_views.planejamentos_list_view, name='planejamentos_list'),
    path('planejamentos/novo/<str:tipo>/', planejamento_views.novo_planejamento_view, name='novo_planejamento_com_tipo'),
    path('planejamentos/novo/', planejamento_views.selecionar_tipo_planejamento_view, name='novo_planejamento'),
    path('planejamentos/tipo/', planejamento_views.selecionar_tipo_planejamento_view, name='selecionar_tipo_planejamento'),
    path('planejamentos/matriz/selecionar/', planejamento_views.selecionar_matriz_view, name='selecionar_matriz'),
    path('planejamentos/matriz/<int:matriz_id>/gerar/', planejamento_views.gerar_planejamentos_matriz_view, name='gerar_planejamentos_matriz'),
    path('planejamentos/<int:planejamento_id>/', planejamento_views.detalhe_planejamento_view, name='detalhe_planejamento'),
    path('planejamentos/<int:planejamento_id>/editar/', planejamento_views.editar_planejamento_view, name='editar_planejamento'),
    path('planejamentos/<int:planejamento_id>/status/', planejamento_views.alterar_status_planejamento_view, name='alterar_status_planejamento'),
    path('planejamentos/<int:planejamento_id>/deletar/', planejamento_views.deletar_planejamento_view, name='deletar_planejamento'),
    path('planejamentos/excluir-massa/', planejamento_views.excluir_planejamentos_massa_view, name='excluir_planejamentos_massa'),
    path('planejamentos/<int:planejamento_id>/criar-registros/', planejamento_views.criar_registros_planejamento_view, name='criar_registros_planejamento'),
    
    # Export para Excel
    path('planejamentos/export/lista-excel/', planejamento_views.exportar_lista_planejamentos_excel_view, name='exportar_lista_planejamentos_excel'),
    path('planejamentos/<int:planejamento_id>/export/excel/', planejamento_views.exportar_detalhe_planejamento_excel_view, name='exportar_detalhe_planejamento_excel'),
    
    # Gerenciar itens do planejamento via AJAX
    path('planejamentos/<int:planejamento_id>/procedimentos/adicionar/', planejamento_views.adicionar_procedimento_planejamento, name='adicionar_procedimento_planejamento'),
    path('planejamentos/<int:planejamento_id>/procedimentos/<int:procedimento_id>/remover/', planejamento_views.remover_procedimento_planejamento, name='remover_procedimento_planejamento'),
    path('planejamentos/<int:planejamento_id>/colaboradores/adicionar/', planejamento_views.adicionar_colaborador_planejamento, name='adicionar_colaborador_planejamento'),
    path('planejamentos/<int:planejamento_id>/colaboradores/<int:colaborador_id>/remover/', planejamento_views.remover_colaborador_planejamento, name='remover_colaborador_planejamento'),
    
    # ==========================
    # API ENDPOINTS
    # ==========================
    path('api/procedimentos/', planejamento_views.api_procedimentos_filtros_view, name='api_procedimentos_filtros'),
    path('api/procedimentos/buscar/', api_procedimentos_buscar_view, name='api_procedimentos_buscar'),
    path('api/colaboradores/buscar/', api_colaboradores_buscar_view, name='api_colaboradores_buscar'),
    path('api/matrizes/', planejamento_views.api_matrizes_list_view, name='api_matrizes_list'),
    path('api/matrizes-bd/', planejamento_views.api_matrizes_bd_view, name='api_matrizes_bd'),
    path('api/areas/', planejamento_views.api_areas_list_view, name='api_areas_list'),
    path('api/subgrupos/', planejamento_views.api_subgrupos_list_view, name='api_sub_areas_list'),  # Retorna sub-áreas dos procedimentos
    path('api/disciplinas-por-matriz/', api_disciplinas_por_matriz_view, name='api_disciplinas_por_matriz_novo'),
    path('api/procedimentos-por-disciplina/', api_procedimentos_por_disciplina_view, name='api_procedimentos_por_disciplina'),
    path('api/colaboradores-por-matriz/', api_colaboradores_por_matriz_view, name='api_colaboradores_por_matriz'),
    path('api/colaboradores-por-disciplina/', planejamento_views.api_colaboradores_por_disciplina_view, name='api_colaboradores_por_disciplina'),
    path('api/demandas-por-perfil/', planejamento_views.api_demandas_por_perfil_view, name='api_demandas_por_perfil'),
    path('api/debug-disciplina/', planejamento_views.api_debug_disciplina_view, name='api_debug_disciplina'),
    
    # ==========================
    # GAP ANALYSIS
    # ==========================
    path('gaps/', gap_analysis_views.dashboard_gaps_view, name='dashboard_gaps'),
    path('gaps/colaborador/<int:colaborador_id>/', gap_analysis_views.gap_detalhado_view, name='gap_detalhado'),
    path('gaps/perfil/<int:perfil_id>/', gap_analysis_views.gaps_por_perfil_view, name='gaps_por_perfil'),
    
    # ==========================
    # LISTAS DE PRESENÇA
    # ==========================
    path('listas-presenca/', lista_presenca_views.lista_presenca_list_view, name='lista_presenca_list'),
    path('listas-presenca/nova/', lista_presenca_views.lista_presenca_create_view, name='lista_presenca_create'),
    path('listas-presenca/exportar/', lista_presenca_views.lista_presenca_export_view, name='lista_presenca_export'),
    path('listas-presenca/<int:pk>/', lista_presenca_views.lista_presenca_detail_view, name='lista_presenca_detail'),
    path('listas-presenca/<int:pk>/editar/', lista_presenca_views.lista_presenca_edit_view, name='lista_presenca_edit'),
    path('listas-presenca/import/erros/download/', lista_presenca_views.lista_presenca_erros_download_view, name='lista_presenca_erros_download'),
    path('listas-presenca/<int:pk>/deletar/', lista_presenca_views.lista_presenca_delete_view, name='lista_presenca_delete'),
    path('listas-presenca/<int:pk>/pdf/', lista_presenca_views.lista_presenca_export_pdf_view, name='lista_presenca_export_pdf'),
    path('listas-presenca/importar/', lista_presenca_views.lista_presenca_importar_view, name='lista_presenca_importar'),
    path('listas-presenca/template/', lista_presenca_views.lista_presenca_download_template_view, name='lista_presenca_download_template'),
    path('listas-presenca/<int:pk>/upload-assinada/', lista_presenca_views.upload_lista_presenca_assinada, name='upload_lista_presenca_assinada'),
    path('listas-presenca/<int:pk>/remover-assinada/', lista_presenca_views.remover_lista_presenca_assinada, name='remover_lista_presenca_assinada'),
    path('listas-presenca/<int:pk>/visualizar-assinada/', lista_presenca_views.visualizar_lista_presenca_assinada, name='visualizar_lista_presenca_assinada'),
    
    # ==========================
    # TEMPLATES DE LISTAS DE PRESENÇA
    # ==========================
    path('templates-presenca/', lista_presenca_views.gerenciar_templates_presenca_view, name='gerenciar_templates_presenca'),
    path('templates-presenca/novo/', lista_presenca_views.upload_template_lista_presenca, name='upload_template_lista_presenca'),
    path('templates-presenca/<int:template_id>/mapear/', lista_presenca_views.mapear_template_fields, name='mapear_template_fields'),
    path('templates-presenca/<int:template_id>/pdf/', lista_presenca_views.serve_pdf_template, name='serve_pdf_template'),
    path('api/template/<int:template_id>/upload-pdf/', lista_presenca_views.upload_pdf_template, name='upload_pdf_template'),
    path('api/template/<int:template_id>/remove-pdf/', lista_presenca_views.remove_pdf_template, name='remove_pdf_template'),
    path('listas-presenca/gerar/', lista_presenca_views.selecionar_template_lista_presenca, name='selecionar_template_lista_presenca'),
    path('listas-presenca/gerar/<int:planejamento_id>/', lista_presenca_views.gerar_lista_presenca_desde_planejamento, name='gerar_lista_presenca_desde_planejamento'),
    path('listas-presenca/gerar/<int:planejamento_id>/<int:template_id>/pdf/', lista_presenca_views.gerar_lista_presenca_pdf, name='gerar_lista_presenca_pdf'),
    
    # Template Mapeamento - Upload e Configuração
    path('api/template-mapeamento/<int:pk>/upload/', template_mapeamento_views.upload_excel_template_view, name='upload_excel_template'),
    path('api/template-mapeamento/<int:pk>/mapear/', template_mapeamento_views.mapear_campos_template_view, name='mapear_campos_template'),
    path('api/template-mapeamento/<int:pk>/preview-abas/', template_mapeamento_views.preview_excel_abas_api, name='preview_excel_abas_api'),
    path('api/template-mapeamento/<int:pk>/preview-celulas/', template_mapeamento_views.preview_excel_celulas_api, name='preview_excel_celulas_api'),
    path('api/template-mapeamento/<int:pk>/atualizar-campo/', template_mapeamento_views.atualizar_mapeamento_campo_api, name='atualizar_mapeamento_campo_api'),
    path('api/template-mapeamento/<int:pk>/remover-campo/', template_mapeamento_views.remover_mapeamento_campo_api, name='remover_mapeamento_campo_api'),
    path('api/template-mapeamento/<int:pk>/status/', template_mapeamento_views.status_mapeamento_api, name='status_mapeamento_api'),
]
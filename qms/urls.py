from django.urls import path
from . import views

urlpatterns = [
    # Application module routes
    path("metrologia/", views.modulo_metrologia_view, name="modulo_metrologia"),
    path("metrologia/instrumentos/", views.listar_instrumentos_view, name="listar_instrumentos"),
    path("metrologia/instrumentos/exportar/", views.exportar_instrumentos_view, name="exportar_instrumentos"),
    path("metrologia/estatisticas/", views.estatisticas_calibracao_view, name="estatisticas_calibracao"),
    path("metrologia/estatisticas/exportar/", views.exportar_estatisticas_view, name="exportar_estatisticas"),
    path("metrologia/vencidos/", views.relatorio_vencidos_view, name="relatorio_vencidos"),
    path("instrumento/<int:instrumento_id>/", views.detalhe_instrumento_view, name="visualizar_instrumento"),
    path("faixa/<int:faixa_id>/", views.api_faixa_medicao_view, name="api_faixa_medicao"),
    path("imp-inst/", views.imp_instr_view, name="importar_instrumentos"),
    path("imp-historico/", views.imp_historico_view, name="importar_historico"),
    path("imp-colab/", views.imp_colab_view, name="importar_colaboradores"),
    path("imp-hierarquia/", views.imp_hierarquia_view, name="importar_hierarquia"),
    path("imp-ferias/", views.imp_ferias_view, name="importar_ferias"),
    path("novo/", views.novo_instrumento_view, name="novo_instrumento"),
    path("instrumento/<int:instrumento_id>/editar/", views.editar_instrumento_view, name="editar_instrumento"),
    path("procedimentos/", views.procedimentos_list_view, name="procedimentos_lista"),
    path("procedimento/novo/", views.novo_procedimento_view, name="novo_procedimento"),
    path("procedimento/<int:procedimento_id>/", views.detalhe_procedimento_view, name="detalhe_procedimento"),
    path("procedimento/<int:procedimento_id>/editar/", views.editar_procedimento_view, name="editar_procedimento"),
    path("dl-template-hist/", views.dl_template_historico, name="dl_template_historico"),
    # Instrument Substitution and Reference Management URLs
    path("instrumento/<int:instrumento_id>/substituir/", views.substituir_instrumento_view, name="substituir_instrumento"),
    path("instrumento/<int:instrumento_id>/copiar-faixas-padrao/", views.copiar_faixas_padrao_view, name="copiar_faixas_padrao"),
    path("referencia/<str:codigo_referencia>/substitucoes/", views.listar_substitucoes_view, name="listar_substitucoes"),
]



































from django.urls import path

from . import views, views_hc, views_tms_mix
from shared.views import laboratorio_hub_view

app_name = "laboratorio"

urlpatterns = [
    path("", views.modulo_laboratorio_view, name="modulo"),
    path("hub/", laboratorio_hub_view, name="hub"),
    path("ocorrencias/", views.ocorrencias_list, name="ocorrencias_list"),
    path("ocorrencias/nova/", views.ocorrencia_create, name="ocorrencia_create"),
    path("ocorrencias/<int:pk>/", views.ocorrencia_detail, name="ocorrencia_detail"),
    path("ocorrencias/<int:pk>/anotacoes/", views.ocorrencia_notes, name="ocorrencia_notes"),
    path("ocorrencias/<int:pk>/editar/", views.ocorrencia_update, name="ocorrencia_update"),
    path("ocorrencias/<int:pk>/encerrar/", views.ocorrencia_close, name="ocorrencia_close"),
    path("ocorrencias/<int:pk>/excluir/", views.ocorrencia_delete, name="ocorrencia_delete"),
    path("categorias/", views.categorias_list, name="categorias_list"),
    path("categorias/nova/", views.categoria_create, name="categoria_create"),
    path("categorias/<int:pk>/editar/", views.categoria_update, name="categoria_update"),
    path("dashboard/", views.dashboard_laboratorio, name="dashboard"),
    path("dashboard/pdf/", views.dashboard_laboratorio_pdf, name="dashboard_pdf"),
    
    # Rotas para Tratamento Antirreflexo
    path("tratamentos/", views.tratamento_list, name="tratamento_list"),
    path("tratamentos/novo/", views.tratamento_create, name="tratamento_create"),
    path("tratamentos/<int:pk>/editar/", views.tratamento_update, name="tratamento_update"),
    
    # Rotas para Regra de Turno Coating
    path("coating/regras-turno/", views.regra_turno_list, name="regra_turno_list"),
    path("coating/regras-turno/nova/", views.regra_turno_create, name="regra_turno_create"),
    path("coating/regras-turno/<int:pk>/editar/", views.regra_turno_update, name="regra_turno_update"),
    
    # Rota para Painel de Registro de Coating
    path("coating/painel/", views.coating_painel, name="coating_painel"),
    path("coating/dashboard/", views.dashboard_coating, name="dashboard_coating"),
    path("coating/registro/<int:pk>/excluir/", views.registro_coating_delete, name="registro_coating_delete"),
    path("coating/registro/editar_linha/", views.api_editar_linha_coating, name="api_editar_linha_coating"),
    path("coating/registro/editar_lote_completo/", views.editar_lote_completo_coating, name="editar_lote_completo_coating"),
    path("coating/celula/atualizar/", views.atualizar_celula_coating, name="atualizar_celula_coating"),
    path("coating/registro/analisar-horarios/", views.api_analisar_horarios_coating, name="api_analisar_horarios_coating"),
    path("coating/manutencao/salvar/", views.registrar_manutencao_coating, name="registrar_manutencao_coating"),
    path("coating/registro/obter-manutencoes/", views.obter_manutencoes_lote, name="obter_manutencoes_lote"),
    path("coating/registro/obter-observacoes/", views.obter_observacoes_lote, name="obter_observacoes_lote"),
    path("coating/registro/salvar-observacoes/", views.salvar_observacoes_lote, name="salvar_observacoes_lote"),
    path("coating/importar/", views.importar_lotes_coating, name="importar_lotes_coating"),
    path("coating/importar/modelo/", views.baixar_modelo_importacao_coating, name="baixar_modelo_importacao_coating"),
    
    # Rota para Equipe e Ciclos
    path("coating/equipe/", views.equipe_coating_list, name="equipe_coating_list"),
    path("coating/equipe/<int:pk>/editar/", views.equipe_coating_update, name="equipe_coating_update"),
    path("coating/equipe/<int:pk>/excluir/", views.equipe_coating_delete, name="equipe_coating_delete"),
    path("coating/ciclos/", views.ciclo_coating_list, name="ciclo_coating_list"),
    path("coating/ciclos/novo/", views.ciclo_coating_create, name="ciclo_coating_create"),
    path("coating/ciclos/<int:pk>/editar/", views.ciclo_coating_update, name="ciclo_coating_update"),
    path("coating/ciclos/<int:pk>/excluir/", views.ciclo_coating_delete, name="ciclo_coating_delete"),
    path("coating/ciclos/<int:ciclo_id>/checklist/", views.configurar_checklist_ciclo, name="configurar_checklist_ciclo"),
    path("coating/ciclos/copiar/", views.copiar_ciclos_coating, name="copiar_ciclos_coating"),
    path("coating/api/ciclos-maquina/", views.api_obter_ciclos_maquina, name="api_obter_ciclos_maquina"),
    path("coating/api/reordenar-ciclos/", views.api_reordenar_ciclos, name="api_reordenar_ciclos"),
    path("coating/api/toggle-ciclo/", views.api_toggle_ciclo_ativo, name="api_toggle_ciclo_ativo"),
    path("run-migrate-db/", views.run_migrate_view, name="run_migrate_view"),
    path("coating/api/recalcular-turno/", views.api_recalcular_turno_registro, name="api_recalcular_turno_registro"),
    path("coating/api/recalcular-todos-turnos/", views.api_recalcular_todos_turnos, name="api_recalcular_todos_turnos"),
    path("coating/api/verificar-lote/", views.api_verificar_lote_coating, name="api_verificar_lote_coating"),

    # Rotas para TMS - Tempos e Movimentos & Previsão de Produção
    path("tms/", views.tms_dashboard, name="tms_dashboard"),
    path("tms/fluxos/", views.tms_fluxos_list, name="tms_fluxos_list"),
    path("tms/fluxos/novo/", views.tms_fluxo_create, name="tms_fluxo_create"),
    path("tms/fluxos/<int:pk>/editar/", views.tms_fluxo_update, name="tms_fluxo_update"),
    path("tms/fluxos/<int:pk>/excluir/", views.tms_fluxo_delete, name="tms_fluxo_delete"),
    path("tms/fluxos/<int:pk>/duplicar/", views.tms_fluxo_duplicar, name="tms_fluxo_duplicar"),
    path("tms/fluxos/<int:fluxo_id>/etapas/", views.tms_etapas_list, name="tms_etapas_list"),
    path("tms/fluxos/<int:fluxo_id>/etapas/nova/", views.tms_etapa_create, name="tms_etapa_create"),
    path("tms/etapas/<int:pk>/editar/", views.tms_etapa_update, name="tms_etapa_update"),
    path("tms/etapas/<int:pk>/excluir/", views.tms_etapa_delete, name="tms_etapa_delete"),
    path("tms/fluxos/<int:fluxo_id>/mix/", views_tms_mix.tms_mix_materiais, name="tms_mix_materiais"),
    path("tms/etapas/<int:pk>/tempos/", views_tms_mix.tms_etapa_amostras, name="tms_etapa_amostras"),
    path("tms/api/reordenar-etapas/", views.api_tms_reordenar_etapas, name="api_tms_reordenar_etapas"),
    path("tms/api/simular/", views.api_tms_simular, name="api_tms_simular"),
    path("tms/fluxos/<int:fluxo_id>/excel/", views.tms_exportar_excel, name="tms_exportar_excel"),
    path("tms/carregar-exemplo/", views.tms_carregar_template_exemplo, name="tms_carregar_exemplo"),

    # Homologações de tratamentos (planos de teste por tratamento x máquina)
    path("homologacoes/", views.homologacoes_resumo, name="homologacoes_resumo"),
    path("homologacoes/novo/", views.homologacao_plano_create, name="homologacao_plano_create"),
    path("homologacoes/importar/", views.homologacoes_importar, name="homologacoes_importar"),
    path("homologacoes/<int:pk>/", views.homologacao_plano_detail, name="homologacao_plano_detail"),
    path("homologacoes/<int:pk>/excluir/", views.homologacao_plano_delete, name="homologacao_plano_delete"),

    # HMC > HC: Rendimento HC
    path("hc/", views_hc.hc_dashboard, name="hc_dashboard"),
    path("hc/registros/", views_hc.hc_registros, name="hc_registros"),
    path("hc/registros/novo/", views_hc.hc_registro_create, name="hc_registro_create"),
    path("hc/importar/", views_hc.hc_importar, name="hc_importar"),
    path("hc/importar/preview/", views_hc.hc_importar_preview, name="hc_importar_preview"),
    path("hc/registros/<int:pk>/editar/", views_hc.hc_registro_update, name="hc_registro_update"),
    path("hc/registros/<int:pk>/excluir/", views_hc.hc_registro_delete, name="hc_registro_delete"),
    path("hc/config/campos/", views_hc.hc_config_campos, name="hc_config_campos"),
    path("hc/config/campos/salvar/", views_hc.hc_campo_save, name="hc_campo_save"),
    path("hc/config/campos/<int:pk>/mover/", views_hc.hc_campo_mover, name="hc_campo_mover"),
    path("hc/config/campos/<int:pk>/excluir/", views_hc.hc_campo_delete, name="hc_campo_delete"),
    path("hc/config/meta/", views_hc.hc_config_meta, name="hc_config_meta"),
    path("hc/config/cadastros/", views_hc.hc_config_cadastros, name="hc_config_cadastros"),
    path("hc/config/cadastros/salvar/", views_hc.hc_cadastro_save, name="hc_cadastro_save"),
    path("hc/config/cadastros/<int:pk>/excluir/", views_hc.hc_cadastro_delete, name="hc_cadastro_delete"),
    path("hc/config/equipe/salvar/", views_hc.hc_equipe_save, name="hc_equipe_save"),
    path("hc/config/equipe/<int:pk>/excluir/", views_hc.hc_equipe_delete, name="hc_equipe_delete"),
    path("hc/config/integracoes/", views_hc.hc_config_integracoes, name="hc_config_integracoes"),
    path("hc/config/integracoes/sincronizar/", views_hc.hc_sincronizar, name="hc_sincronizar"),
    path("hc/config/integracoes/vincular/", views_hc.hc_vincular_nome, name="hc_vincular_nome"),
]

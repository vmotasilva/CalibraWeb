

































from django.urls import path

from . import views

app_name = "laboratorio"

urlpatterns = [
    path("", views.modulo_laboratorio_view, name="modulo"),
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
    path("coating/registro/<int:pk>/excluir/", views.registro_coating_delete, name="registro_coating_delete"),
    path("coating/registro/editar_lote_completo/", views.editar_lote_completo_coating, name="editar_lote_completo_coating"),
    path("coating/celula/atualizar/", views.atualizar_celula_coating, name="atualizar_celula_coating"),
    path("coating/manutencao/salvar/", views.registrar_manutencao_coating, name="registrar_manutencao_coating"),
    
    # Rota para Equipe e Ciclos
    path("coating/equipe/", views.equipe_coating_list, name="equipe_coating_list"),
    path("coating/equipe/<int:pk>/excluir/", views.equipe_coating_delete, name="equipe_coating_delete"),
    path("coating/ciclos/", views.ciclo_coating_list, name="ciclo_coating_list"),
    path("coating/ciclos/novo/", views.ciclo_coating_create, name="ciclo_coating_create"),
    path("coating/ciclos/<int:pk>/excluir/", views.ciclo_coating_delete, name="ciclo_coating_delete"),
    path("coating/ciclos/<int:ciclo_id>/checklist/", views.configurar_checklist_ciclo, name="configurar_checklist_ciclo"),
    path("run-migrate-db/", views.run_migrate_view, name="run_migrate_view"),
]

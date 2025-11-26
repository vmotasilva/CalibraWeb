from django.urls import path

from . import views

urlpatterns = [
	path("healthz/", views.health_check, name="healthz"),
	path("import-jobs/", views.import_jobs_view, name="import_jobs"),
	path("imp-inst/", views.imp_instr_view, name="importar_instrumentos"),
	path("imp-historico/", views.imp_historico_view, name="importar_historico"),
	path("imp-colab/", views.imp_colab_view, name="importar_colaboradores"),
	path("imp-hierarquia/", views.imp_hierarquia_view, name="importar_hierarquia"),
	path("imp-ferias/", views.imp_ferias_view, name="importar_ferias"),
]

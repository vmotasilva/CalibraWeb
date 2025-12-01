from django.urls import path

from . import views


urlpatterns = [
	path("healthz/", views.health_check, name="healthz"),
	path("import-jobs/", views.import_jobs_view, name="import_jobs"),
	path("import-jobs/<uuid:job_id>/retry/", views.retry_import_job_view, name="retry_import_job"),
	path("imp-inst/", views.imp_instr_view, name="importar_instrumentos"),
	path("imp-historico/", views.imp_historico_view, name="importar_historico"),
	path("imp-colab/", views.imp_colab_view, name="importar_colaboradores"),
	path("imp-hierarquia/", views.imp_hierarquia_view, name="importar_hierarquia"),
	path("imp-ferias/", views.imp_ferias_view, name="importar_ferias"),
	path("novo/", views.novo_instrumento_view, name="novo_instrumento"),
	path(
		"instrumento/<int:instrumento_id>/registrar-historico/",
		views.registrar_historico_calibracao_view,
		name="registrar_historico_calibracao",
	),
	path("", views.dashboard_view, name="dashboard"),
	path("metrologia/", views.modulo_metrologia_view, name="modulo_metrologia"),
	path("instrumento/<int:instrumento_id>/", views.detalhe_instrumento_view, name="detalhe_instrumento"),
	path("instrumento/<int:instrumento_id>/editar/", views.novo_instrumento_view, name="editar_instrumento"),
	path("colaborador/<int:colab_id>/", views.detalhe_colaborador_view, name="detalhe_colaborador"),
	path("colaborador/<int:colab_id>/editar/", views.editar_colaborador_view, name="editar_colaborador"),
	path("procedimentos/", views.procedimentos_list_view, name="procedimentos_list"),
	path("procedimento/novo/", views.novo_procedimento_view, name="novo_procedimento"),
	path("procedimento/<int:procedimento_id>/", views.detalhe_procedimento_view, name="detalhe_procedimento"),
	path("procedimento/<int:procedimento_id>/editar/", views.editar_procedimento_view, name="editar_procedimento"),
]

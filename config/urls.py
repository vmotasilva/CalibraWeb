from django.conf import settings
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from qms.admin import admin_site
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic.base import RedirectView

from qms import views

urlpatterns = [
    # 1. Redireciona a raiz do site direto para o login
    path("", RedirectView.as_view(url="/login/")),
    # 2. Admin
    path("admin/", admin_site.urls),
    # 3. Autenticação
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # 4. Dashboard
    path("home/", views.dashboard_view, name="home"),
    # 5. Módulos Principais
    path("metrologia/", views.modulo_metrologia_view, name="modulo_metrologia"),
    path("metrologia/export/", views.export_metrologia_view, name="export_metrologia"),
    path("metrologia/etiquetas/", views.export_etiquetas_view, name="export_etiquetas"),
    path("metrologia/novo/", views.novo_instrumento_view, name="novo_instrumento"),
    path("rh/", views.modulo_rh_view, name="modulo_rh"),
    # Detalhes e Edição
    path(
        "rh/colaborador/<int:colab_id>/",
        views.detalhe_colaborador_view,
        name="detalhe_colaborador",
    ),
    path(
        "rh/editar/<int:colab_id>/",
        views.editar_colaborador_view,
        name="editar_colaborador",
    ),
    path(
        "metrologia/instrumento/<int:instrumento_id>/",
        views.detalhe_instrumento_view,
        name="detalhe_instrumento",
    ),
    # --- NOVA ROTA PARA SOLICITAÇÕES ---
    path("solicitacao/nova/", views.nova_solicitacao, name="nova_solicitacao"),
    # 6. Funcionalidades Específicas
    path("carimbar/", views.carimbar_view, name="carimbar"),
    path(
        "metrologia/historico/remover/<int:historico_id>/",
        views.remover_historico_view,
        name="remover_historico",
    ),
    path(
        "metrologia/historico/<int:historico_id>/anexar/",
        views.anexar_certificado_historico_view,
        name="anexar_certificado_historico",
    ),
    path(
        "metrologia/historico/<int:historico_id>/remover-certificado/",
        views.remover_certificado_historico_view,
        name="remover_certificado_historico",
    ),
    # 7. Downloads de Templates (CORRIGIDO: Os nomes agora batem com o HTML)
    path("dl-template-inst/", views.dl_template_instr, name="template_instrumentos"),
    path(
        "dl-template-colab/", views.dl_template_colab, name="template_colaboradores"
    ),  # <--- CORRIGIDO AQUI
    path("dl-template-hier/", views.dl_template_hierarquia, name="template_hierarquia"),
    path("dl-template-hist/", views.dl_template_historico, name="template_historico"),
    path("dl-template-ferias/", views.dl_template_ferias, name="dl_template_ferias"),
    path("dl-template-categorias/", views.dl_template_categorias, name="dl_template_categorias"),
    path("dl-template-procedimentos/", views.dl_template_procedimentos, name="template_procedimentos"),
    path("dl-dados-colab/", views.dl_template_colab_dados, name="dl_colaboradores_dados"),
    # Admin-only endpoint to seed demo data quickly
    path("seed-demo/", views.seed_demo_view, name="seed_demo"),
    path("fix-historico/", views.fix_historico_proxima_view, name="fix_historico_proxima"),
    # 8. Importações (Excel)
    path("imp-inst/", views.imp_instr_view, name="importar_instrumentos"),
    path("imp-categorias/", views.imp_categorias_view, name="importar_categorias"),
    # Import jobs listing and retry actions
    path("import-jobs/", views.import_jobs_view, name="import_jobs"),
    path("import-jobs/<uuid:job_id>/retry/", views.retry_import_job_view, name="retry_import_job"),
    path("import-jobs.json", views.import_jobs_json_view, name="import_jobs_json"),
        # Procedimentos público (consulta)
        path("procedimentos/", views.procedimentos_list_view, name="procedimentos_list"),
        path("procedimentos/export/xlsx/", views.export_procedimentos_excel_view, name="export_procedimentos_excel"),
        path("procedimentos/export/pdf/", views.export_procedimentos_pdf_view, name="export_procedimentos_pdf"),
        path("procedimentos/importar/", views.imp_procedimentos_view, name="importar_procedimentos"),
        path("procedimentos/novo/", views.novo_procedimento_view, name="novo_procedimento"),
        path("procedimentos/<int:procedimento_id>/", views.detalhe_procedimento_view, name="detalhe_procedimento"),
        path("procedimentos/<int:procedimento_id>/editar/", views.editar_procedimento_view, name="editar_procedimento"),
    path("imp-colab/", views.imp_colab_view, name="importar_colaboradores"),
    path("imp-hist/", views.imp_historico_view, name="importar_historico"),
    path("imp-hierarquia/", views.imp_hierarquia_view, name="importar_hierarquia"),
    path("imp-ferias/", views.imp_ferias_view, name="importar_ferias"),
    path("imp-padroes/", views.imp_padroes_view, name="importar_padroes"),
    # Health check for uptime monitoring / readiness probes
    path("healthz/", views.health_check, name="healthz"),
    # 9. Ocorrência de Colaborador
    path("rh/ocorrencia/nova/", views.registrar_ocorrencia_view, name="registrar_ocorrencia"),

    # Treinamentos
    path("treinamentos/", views.treinamentos_list_view, name="treinamentos_lista"),
]

# Configuração para servir arquivos de mídia/estáticos em modo Debug
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

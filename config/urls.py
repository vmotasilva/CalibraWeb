from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from qms.admin import admin_site
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.http import JsonResponse
from django.views.generic import TemplateView
from qms import views as qms_views

# Health check view for Railway
def health_check(request):
    """Simple health check endpoint for Railway infrastructure"""
    return JsonResponse({"status": "ok"}, status=200)


# Root view - redirect to dashboard if authenticated, otherwise to login
def root_view(request):
    """Root view that redirects to dashboard if authenticated, else to login"""
    if request.user.is_authenticated:
        return qms_views.dashboard_view(request)
    else:
        from django.shortcuts import redirect
        return redirect('login')

# Minimal URL configuration
urlpatterns = [
    # 1. Health check for Railway
    path("healthz", health_check, name="health_check"),
    path("health", health_check, name="health"),
    
    # 2. Dashboard principal
    path("", root_view, name="dashboard"),
    
    # 3. Admin
    path("admin/", admin_site.urls),
    
    # 4. Autenticação
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    
    # 5. Application modules URLs (without the root path to avoid conflict)
    path("metrologia/", qms_views.modulo_metrologia_view, name="modulo_metrologia"),
    path("instrumento/<int:instrumento_id>/", qms_views.detalhe_instrumento_view, name="detalhe_instrumento"),
    path("instrumento/<int:instrumento_id>/editar/", qms_views.novo_instrumento_view, name="editar_instrumento"),
    path("instrumento/<int:instrumento_id>/registrar-historico/", qms_views.registrar_historico_calibracao_view, name="registrar_historico_calibracao"),
    path("metrologia/historico/<int:historico_id>/preview/", qms_views.preview_certificado_view, name="preview_certificado"),
    path("metrologia/historico/<int:historico_id>/download/", qms_views.download_certificado_view, name="download_certificado"),
    path("metrologia/historico/<int:historico_id>/visualizar/", qms_views.visualizar_historico_calibracao_view, name="visualizar_historico_calibracao"),
    path("metrologia/historico/<int:historico_id>/remover/", qms_views.remover_historico_view, name="remover_historico"),
    path("metrologia/historico/<int:historico_id>/anexar-certificado/", qms_views.anexar_certificado_historico_view, name="anexar_certificado_historico"),
    path("metrologia/historico/<int:historico_id>/remover-certificado/", qms_views.remover_certificado_historico_view, name="remover_certificado_historico"),
    path("metrologia/historico/<int:historico_id>/aplicar-carimbo/", qms_views.aplicar_carimbo_certificado_view, name="aplicar_carimbo_certificado"),
    path("renomear-arquivo-padrao/<int:arquivo_id>/", qms_views.renomear_arquivo_padrao_view, name="renomear_arquivo_padrao"),
    path("remover-arquivo-padrao/<int:arquivo_id>/", qms_views.remover_arquivo_padrao_view, name="remover_arquivo_padrao"),
    path("import-jobs/", qms_views.import_jobs_view, name="import_jobs"),
    path("import-jobs/<uuid:job_id>/retry/", qms_views.retry_import_job_view, name="retry_import_job"),
    path("api/faixa/<int:faixa_id>/", qms_views.api_faixa_medicao_view, name="api_faixa_medicao"),
    path("imp-inst/", qms_views.imp_instr_view, name="importar_instrumentos"),
    path("imp-historico/", qms_views.imp_historico_view, name="importar_historico"),
    path("imp-colab/", qms_views.imp_colab_view, name="importar_colaboradores"),
    path("imp-hierarquia/", qms_views.imp_hierarquia_view, name="importar_hierarquia"),
    path("imp-ferias/", qms_views.imp_ferias_view, name="importar_ferias"),
    path("novo/", qms_views.novo_instrumento_view, name="novo_instrumento"),
    path("colaborador/<int:colab_id>/", qms_views.detalhe_colaborador_view, name="detalhe_colaborador"),
    path("colaborador/<int:colab_id>/editar/", qms_views.editar_colaborador_view, name="editar_colaborador"),
    path("procedimentos/", qms_views.procedimentos_list_view, name="procedimentos_list"),
    path("procedimento/novo/", qms_views.novo_procedimento_view, name="novo_procedimento"),
    path("procedimento/<int:procedimento_id>/", qms_views.detalhe_procedimento_view, name="detalhe_procedimento"),
    path("procedimento/<int:procedimento_id>/editar/", qms_views.editar_procedimento_view, name="editar_procedimento"),
    path("dl-template-hist/", qms_views.dl_template_historico, name="dl_template_historico"),
]

# Configuração para servir arquivos de mídia/estáticos em modo Debug
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

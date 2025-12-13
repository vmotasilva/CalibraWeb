from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from qms.admin import admin_site
from django.contrib.auth import views as auth_views
from django.shortcuts import render, redirect
from django.urls import path, include
from django.http import JsonResponse
from procurements.views import nova_solicitacao
from rh.views import modulo_rh_view, detalhe_colaborador_view, editar_colaborador_view, registrar_ocorrencia_view, editar_ocorrencia_view, deletar_ocorrencia_view, registrar_ferias_view, editar_ferias_view, excluir_ferias_view
from metrologia.views import export_metrologia_view, export_etiquetas_view, detalhe_instrumento_view, modulo_metrologia_view
from qms.views import (
    editar_instrumento_view, gerenciar_faixas_instrumento_view, editar_faixa_view,
    registrar_historico_calibracao_view, preview_certificado_view, download_certificado_view,
    get_certificado_bytes_view,
    visualizar_historico_calibracao_view, editar_historico_calibracao_view, remover_historico_view,
    anexar_certificado_historico_view, remover_certificado_historico_view, aplicar_carimbo_certificado_view,
    remover_carimbo_certificado_view
)
from shared.views import (
    dl_template_instr, dl_template_colab, dl_template_hierarquia,
    dl_template_historico, dl_template_ferias, dl_template_categorias,
    dl_template_procedimentos, dl_template_colab_dados
)

# Health check view for Railway
def health_check(request):
    """Simple health check endpoint for Railway infrastructure"""
    return JsonResponse({"status": "ok"}, status=200)


# Root view - show dashboard if authenticated, otherwise redirect to login
def root_view(request):
    """Root view that handles authentication and shows dashboard"""
    if request.user.is_authenticated:
        # Import here to avoid circular imports
        from metrologia.models import Instrumento
        from procurements.models import ProcessoCotacao
        from rh.models import Colaborador
        from qms.models import SolicitacaoInstrumento
        from datetime import date, timedelta
        
        try:
            nome_display = request.user.username
            hoje = date.today()
            trinta_dias = hoje + timedelta(days=30)

            # Metrologia
            qtd_vencidos = Instrumento.objects.filter(
                data_proxima_calibracao__lt=hoje, ativo=True
            ).count()
            qtd_avencer = Instrumento.objects.filter(
                data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True
            ).count()
            lista_urgentes = Instrumento.objects.filter(
                data_proxima_calibracao__lte=trinta_dias, ativo=True
            ).order_by("data_proxima_calibracao")[:5]

            # Procurements
            qtd_pendentes = SolicitacaoInstrumento.objects.filter(status="PENDENTE").count()

            context = {
                "nome_display": nome_display,
                "qtd_vencidos": qtd_vencidos,
                "qtd_avencer": qtd_avencer,
                "lista_urgentes": lista_urgentes,
                "qtd_cotacoes": ProcessoCotacao.objects.filter(status="ABERTO").count(),
                "qtd_pendentes": qtd_pendentes,
                "today": hoje,
            }
        except Exception as e:
            # If there's a database error, show minimal context
            context = {
                "nome_display": request.user.username,
                "qtd_vencidos": 0,
                "qtd_avencer": 0,
                "lista_urgentes": [],
                "qtd_cotacoes": 0,
                "qtd_pendentes": 0,
                "today": date.today(),
                "error": str(e),
            }
        
        return render(request, 'shared/dashboard.html', context)
    else:
        return redirect('login')


# Alias for training/procedures
def treinamentos_lista_redirect(request):
    """Redirect to procedures list with 'treinamentos_lista' URL name"""
    from django.views.decorators.http import require_http_methods
    from qms.views import procedimentos_list_view
    return procedimentos_list_view(request)

# Minimal URL configuration
urlpatterns = [
    # 1. Health check for Railway
    path("healthz", health_check, name="health_check"),
    path("health", health_check, name="health"),
    
    # 2. Dashboard principal
    path("", root_view, name="home"),  # 'home' is used in templates
    path("dashboard/", root_view, name="dashboard"),  # alternative name
    
    # 3. Admin
    path("admin/", admin_site.urls),
    
    # 4. Autenticação
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    
    # 5. Metrologia export routes
    path("api/export-metrologia/", export_metrologia_view, name="export_metrologia"),
    path("api/export-etiquetas/", export_etiquetas_view, name="export_etiquetas"),
    
    # 5a. Template download routes
    path("api/dl-template-instr/", dl_template_instr, name="dl_template_instr"),
    path("api/dl-template-colab/", dl_template_colab, name="dl_template_colab"),
    path("api/dl-template-hierarquia/", dl_template_hierarquia, name="dl_template_hierarquia"),
    path("api/dl-template-historico/", dl_template_historico, name="dl_template_historico"),
    path("api/dl-template-ferias/", dl_template_ferias, name="dl_template_ferias"),
    path("api/dl-template-categorias/", dl_template_categorias, name="dl_template_categorias"),
    path("api/dl-template-colab-dados/", dl_template_colab_dados, name="dl_template_colab_dados"),
    
    # 5b. Shared URLs (imports, jobs, etc)
    path("", include("shared.urls")),
    path("api/dl-template-procedimentos/", dl_template_procedimentos, name="dl_template_procedimentos"),
    path("api/dl-template-colab-dados/", dl_template_colab_dados, name="dl_template_colab_dados"),
    
    # 6a. Metrologia app URLs
    path("metrologia/", modulo_metrologia_view, name="modulo_metrologia"),
    path("metrologia/instrumento/<int:instrumento_id>/", detalhe_instrumento_view, name="detalhe_instrumento"),
    path("instrumento/<int:instrumento_id>/editar/", editar_instrumento_view, name="editar_instrumento_custom"),
    path("instrumento/<int:instrumento_id>/faixas/", gerenciar_faixas_instrumento_view, name="gerenciar_faixas_instrumento"),
    path("faixa/<int:faixa_id>/editar/", editar_faixa_view, name="editar_faixa"),
    path("instrumento/<int:instrumento_id>/registrar-historico/", registrar_historico_calibracao_view, name="registrar_historico_calibracao"),
    path("metrologia/historico/<int:historico_id>/preview/", preview_certificado_view, name="preview_certificado"),
    path("metrologia/historico/<int:historico_id>/download/", download_certificado_view, name="download_certificado"),
    path("metrologia/historico/<int:historico_id>/certificado-bytes/", get_certificado_bytes_view, name="get_certificado_bytes"),
    path("metrologia/historico/<int:historico_id>/visualizar/", visualizar_historico_calibracao_view, name="visualizar_historico_calibracao"),
    path("metrologia/historico/<int:historico_id>/editar/", editar_historico_calibracao_view, name="editar_historico_calibracao"),
    path("metrologia/historico/<int:historico_id>/remover/", remover_historico_view, name="remover_historico"),
    path("metrologia/historico/<int:historico_id>/anexar-certificado/", anexar_certificado_historico_view, name="anexar_certificado_historico"),
    path("metrologia/historico/<int:historico_id>/remover-certificado/", remover_certificado_historico_view, name="remover_certificado_historico"),
    path("metrologia/historico/<int:historico_id>/aplicar-carimbo/", aplicar_carimbo_certificado_view, name="aplicar_carimbo_certificado"),
    path("metrologia/historico/<int:historico_id>/remover-carimbo/", remover_carimbo_certificado_view, name="remover_carimbo_certificado"),
    
    # 6. Application modules URLs - include all qms URLs with prefix to avoid conflicts
    path("api/", include("qms.urls")),
    # Fornecedores
    path("fornecedores/", include("fornecedores.urls")),
    
    # 7. RH app URLs
    path("rh/", modulo_rh_view, name="modulo_rh"),
    path("rh/colaborador/<int:colab_id>/", detalhe_colaborador_view, name="detalhe_colaborador"),
    path("rh/colaborador/<int:colab_id>/editar/", editar_colaborador_view, name="editar_colaborador"),
    path("rh/colaborador/<int:colab_id>/ferias/registrar/", registrar_ferias_view, name="registrar_ferias"),
    path("rh/colaborador/<int:colab_id>/ferias/<int:ferias_id>/editar/", editar_ferias_view, name="editar_ferias"),
    path("rh/colaborador/<int:colab_id>/ferias/<int:ferias_id>/excluir/", excluir_ferias_view, name="excluir_ferias"),
    path("rh/ocorrencia/", registrar_ocorrencia_view, name="registrar_ocorrencia"),
    path("rh/ocorrencia/<int:occ_id>/editar/", editar_ocorrencia_view, name="editar_ocorrencia"),
    path("rh/ocorrencia/<int:occ_id>/deletar/", deletar_ocorrencia_view, name="deletar_ocorrencia"),
    
    # 7. Training app URLs
    path("training/", include("training.urls")),
    path("api/treinamentos/", treinamentos_lista_redirect, name="treinamentos_lista"),
    
    # 8. Procurements app URLs
    path("procurements/novo/", nova_solicitacao, name="nova_solicitacao"),
    path("procurements/", include("procurements.urls")),
    
    # 9. Documents app URLs
    path("documents/", include("documents.urls")),
]

# Configuração para servir arquivos de mídia/estáticos em modo Debug
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

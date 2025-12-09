from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from qms.admin import admin_site
from django.contrib.auth import views as auth_views
from django.shortcuts import render, redirect
from django.urls import path, include
from django.http import JsonResponse
from procurements.views import nova_solicitacao
from rh.views import modulo_rh_view, detalhe_colaborador_view, editar_colaborador_view, registrar_ocorrencia_view

# Health check view for Railway
def health_check(request):
    """Simple health check endpoint for Railway infrastructure"""
    return JsonResponse({"status": "ok"}, status=200)


# Root view - show dashboard if authenticated, otherwise redirect to login
def root_view(request):
    """Root view that handles authentication and shows dashboard"""
    if request.user.is_authenticated:
        # Import here to avoid circular imports
        from metrologia.models import Instrumento, HistoricoCalibracao
        from rh.models import Colaborador
        from training.models import Procedimento
        
        try:
            context = {
                'total_instrumentos': Instrumento.objects.count(),
                'total_calibracoes': HistoricoCalibracao.objects.count(),
                'total_colaboradores': Colaborador.objects.count(),
                'total_procedimentos': Procedimento.objects.count(),
            }
        except Exception as e:
            # If there's a database error, show empty context
            context = {
                'total_instrumentos': 0,
                'total_calibracoes': 0,
                'total_colaboradores': 0,
                'total_procedimentos': 0,
                'error': str(e),
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
    
    # 5. Application modules URLs - include all qms URLs with prefix to avoid conflicts
    path("api/", include("qms.urls")),
    
    # 6. RH app URLs
    path("rh/", modulo_rh_view, name="modulo_rh"),
    path("rh/colaborador/<int:colab_id>/", detalhe_colaborador_view, name="detalhe_colaborador"),
    path("rh/colaborador/<int:colab_id>/editar/", editar_colaborador_view, name="editar_colaborador"),
    path("rh/ocorrencia/", registrar_ocorrencia_view, name="registrar_ocorrencia"),
    
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

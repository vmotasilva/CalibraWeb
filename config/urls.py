from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from qms.admin import admin_site
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.generic.base import RedirectView

# NOTE: Most views are currently disabled due to architecture migration
# See ARCHITECTURE_MIGRATION_NOTES.md for details
# Only importing views that don't depend on disabled apps

# Minimal URL configuration for testing
urlpatterns = [
    # 1. Redireciona a raiz do site direto para o login
    path("", RedirectView.as_view(url="/login/")),
    # 2. Admin
    path("admin/", admin_site.urls),
    
    # 4. Autenticação
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

# Configuração para servir arquivos de mídia/estáticos em modo Debug
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

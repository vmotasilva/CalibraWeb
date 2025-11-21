from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings 
from django.conf.urls.static import static
from qms import views
from django.views.generic.base import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/login/')),
    path('admin/', admin.site.urls),
    path('qms/', include('qms.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('', views.dashboard_view, name='home'),
    path('metrologia/', views.modulo_metrologia_view, name='modulo_metrologia'),
    path('rh/', views.modulo_rh_view, name='modulo_rh'),
    
    path('carimbar/', views.carimbar_view, name='carimbar'),
    path('detalhe/<int:instrumento_id>/', views.detalhe_instrumento_view, name='detalhe_instrumento'),
    
    path('dl-template-inst/', views.dl_template_instr, name='template_instrumentos'),
    path('dl-template-colab/', views.dl_template_colab, name='template_colaboradores'),
    path('dl-template-hier/', views.dl_template_hierarquia, name='template_hierarquia'),

    path('imp-inst/', views.imp_instr_view, name='importar_instrumentos'),
    path('imp-colab/', views.imp_colab_view, name='importar_colaboradores'),

    path('imp-hist/', views.imp_historico_view, name='importar_historico'),
    path('dl-template-hist/', views.dl_template_historico, name='template_historico'),
        
    path('imp-hierarquia/', views.imp_hierarquia_view, name='importar_hierarquia'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
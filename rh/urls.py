from django.urls import path
from rh.views import views

app_name = 'rh'

urlpatterns = [
    # API Endpoints
    path('api/colaboradores/', views.api_colaboradores, name='api_colaboradores'),
    path('api/setores/', views.api_setores, name='api_setores'),
    path('api/cargos/', views.api_cargos, name='api_cargos'),
    path('api/grupos/', views.api_grupos, name='api_grupos'),
    path('api/lideres/', views.api_lideres, name='api_lideres'),
    path('api/supervisores/', views.api_supervisores, name='api_supervisores'),
]

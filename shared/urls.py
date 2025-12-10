from django.urls import path
from . import views

urlpatterns = [
    # Import Jobs
    path('imports/jobs/', views.import_jobs_view, name='import_jobs'),
    path('imports/jobs/json/', views.import_jobs_json_view, name='import_jobs_json'),
    
    # Shared URLs
    # path('', views.dashboard_view, name='dashboard'),
    # path('health/', views.health_check, name='health_check'),
    # Mais URLs serão adicionadas na Fase 3
]

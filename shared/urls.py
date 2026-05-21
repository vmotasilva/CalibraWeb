from django.urls import path
from . import views

urlpatterns = [
    # Account / Password APIs
    path('api/account/change-password/', views.api_change_password, name='api_change_password'),
    path('api/account/reset-password-totp/', views.api_reset_password_totp, name='api_reset_password_totp'),

    # Import Jobs
    path('imports/jobs/', views.import_jobs_view, name='import_jobs'),
    path('imports/jobs/json/', views.import_jobs_json_view, name='import_jobs_json'),
    
    # Access Control (temporariamente comentado - será re-ativado após rebuild do Docker)
    # path('acesso-negado/<str:module>/', views.access_denied_view, name='access_denied'),
    # path('acesso-negado/', views.access_denied_view, name='access_denied'),
    
    # Shared URLs
    path('hub/', views.hub_view, name='hub'),
    # path('', views.dashboard_view, name='dashboard'),
    # path('health/', views.health_check, name='health_check'),
    # Mais URLs serão adicionadas na Fase 3
    path('api/cron/run-tasks/', views.run_cron_tasks, name='run_cron_tasks'),
]


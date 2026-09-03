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
    path('hub/<slug:module_slug>/', views.module_hub_view, name='module_hub'),
    path('inbox/', views.inbox_view, name='inbox'),
    path('changelog/', views.changelog_view, name='changelog'),
    # path('', views.dashboard_view, name='dashboard'),
    # path('health/', views.health_check, name='health_check'),
    path('api/hub/search/', views.api_hub_search, name='api_hub_search'),
    path('api/cron/run-tasks/', views.run_cron_tasks, name='run_cron_tasks'),
]


from django.urls import path
from .views import views

app_name = 'training'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_treinamentos_view, name='dashboard_treinamentos'),
    path('dashboard/filtered/', views.dashboard_treinamentos_filtered_view, name='dashboard_filtered'),
    path('dashboard/exportar-csv/', views.dashboard_treinamentos_exportar_csv_view, name='dashboard_exportar_csv'),

    # API
    path('api/colaboradores-autocomplete/', views.colaboradores_autocomplete_view, name='colaboradores_autocomplete'),
]

from django.urls import path
from .views import views

app_name = 'training'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_treinamentos_view, name='dashboard_treinamentos'),
    path('dashboard/filtered/', views.dashboard_treinamentos_filtered_view, name='dashboard_filtered'),
]

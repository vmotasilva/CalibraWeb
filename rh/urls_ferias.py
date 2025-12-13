from django.urls import path
from rh.views import editar_ferias_view, excluir_ferias_view

urlpatterns = [
    path('colaborador/<int:colab_id>/ferias/<int:ferias_id>/editar/', editar_ferias_view, name='editar_ferias'),
    path('colaborador/<int:colab_id>/ferias/<int:ferias_id>/excluir/', excluir_ferias_view, name='excluir_ferias'),
]

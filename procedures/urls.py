# -*- coding: utf-8 -*-
"""
URLs para o módulo Procedures
Consolida training + procurements
"""

from django.urls import path
from . import views

app_name = 'procedures'

urlpatterns = [
    # ==========================
    # PROCEDIMENTOS
    # ==========================
    path('procedimentos/', views.procedimentos_list_view, name='procedimentos_list'),
    path('procedimentos/export/excel/', views.export_procedimentos_excel_view, name='export_procedimentos_excel'),
    path('procedimentos/template/download/', views.download_template_procedimentos_view, name='dl_template_procedimentos'),
    path('procedimentos/importar/', views.importar_procedimentos_view, name='importar_procedimentos'),
    path('procedimentos/novo/', views.novo_procedimento_view, name='novo_procedimento'),
    path('procedimentos/<int:procedimento_id>/editar/', views.editar_procedimento_view, name='editar_procedimento'),
    path('procedimentos/<int:procedimento_id>/', views.detalhe_procedimento_view, name='detalhe_procedimento'),
    
    # ==========================
    # TREINAMENTOS
    # ==========================
    path('treinamentos/', views.treinamentos_list_view, name='treinamentos_list'),
    path('treinamentos/<int:treinamento_id>/', views.treinamentos_detalhe_view, name='treinamentos_detalhe'),
    path('treinamentos/novo/', views.novo_treinamento_view, name='novo_treinamento'),
    path('treinamentos/<int:treinamento_id>/editar/', views.editar_treinamento_view, name='editar_treinamento'),
    
    # ==========================
    # FORNECEDORES
    # ==========================
    path('fornecedores/', views.fornecedores_list_view, name='fornecedores_list'),
    path('fornecedores/novo/', views.novo_fornecedor_view, name='novo_fornecedor'),
    path('fornecedores/<int:fornecedor_id>/editar/', views.editar_fornecedor_view, name='editar_fornecedor'),
    path('fornecedores/<int:fornecedor_id>/', views.detalhe_fornecedor_view, name='detalhe_fornecedor'),
    
    # ==========================
    # AVALIAÇÕES
    # ==========================
    path('avaliações/novo/', views.nova_avaliacao_fornecedor_view, name='nova_avaliacao'),
    
    # ==========================
    # COTAÇÕES
    # ==========================
    path('cotacoes/', views.cotacoes_list_view, name='cotacoes_list'),
    path('cotacoes/novo/', views.nova_cotacao_view, name='nova_cotacao'),
    path('cotacoes/<int:cotacao_id>/editar/', views.editar_cotacao_view, name='editar_cotacao'),
    path('cotacoes/<int:cotacao_id>/', views.detalhe_cotacao_view, name='detalhe_cotacao'),
    
    # ==========================
    # ORÇAMENTOS
    # ==========================
    path('orcamentos/novo/', views.novo_orcamento_view, name='novo_orcamento'),
    path('orcamentos/<int:orcamento_id>/editar/', views.editar_orcamento_view, name='editar_orcamento'),
]

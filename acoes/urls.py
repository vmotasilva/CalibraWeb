from django.urls import path
from .views import listar_acoes, detalhe_acao, obter_proximo_numero, salvar_acao_corretiva_modal
from .views_solucoes import (
    listar_solucoes,
    detalhe_solucao,
    criar_solucao,
    editar_solucao,
    listar_templates,
    download_template,
    criar_registro_modal,
    criar_plano_acao_modal,
    editar_linha_acao_modal,
)
from .views_aggregated import AcoesRegistradasView
from .views_origem_problema import (
    OrigemProblemaListView,
    OrigemProblemaCreateView,
    OrigemProblemaUpdateView,
    OrigemProblemaDeleteView,
)
from .views_kpi import (
    KPIOpcaoListView,
    KPIOpcaoCreateView,
    KPIOpcaoUpdateView,
    KPIOpcaoDeleteView,
)
from .views_importacao_controles import (
    importar_controle_registros,
    download_template_controle_registros,
    importar_plano_acao,
    download_template_plano_acao,
)
from .views import (
    # Dashboard
    AcoesDashboardView,
    # Plano de Ação
    PlanoAcaoListView,
    PlanoAcaoCreateView,
    PlanoAcaoUpdateView,
    PlanoAcaoDetailView,
    plano_acao_delete,
    # Linha de Ação
    LinhaAcaoUpdateView,
    linha_acao_delete,
    # Solução A3
    SolucaoA3ListView,
    SolucaoA3CreateView,
    SolucaoA3UpdateView,
    SolucaoA3DetailView,
    # Solução 8D
    Solucao8DListView,
    Solucao8DCreateView,
    Solucao8DUpdateView,
    Solucao8DDetailView,
    # Solução RNC
    SolucaoRNCListView,
    SolucaoRNCCreateView,
    SolucaoRNCUpdateView,
    SolucaoRNCDetailView,
    # Gestão de Mudança
    SolucaoGestaoDeMudancaListView,
    SolucaoGestaoDeMudancaCreateView,
    SolucaoGestaoDeMudancaUpdateView,
    SolucaoGestaoDeMudancaDetailView,
    # Revisão Gerencial
    RevisaoGerencialListView,
    RevisaoGerencialCreateView,
    RevisaoGerencialUpdateView,
    RevisaoGerencialDetailView,
)

app_name = 'acoes'

urlpatterns = [
    # ========================================================================
    # LEGACY ROUTES (Manutenção de compatibilidade com código anterior)
    # ========================================================================
    # Ações Corretivas/Preventivas
    path('', listar_acoes, name='listar_acoes'),
    path('acao/<int:acao_id>/', detalhe_acao, name='detalhe_acao'),
    path('acao/salvar-modal/', salvar_acao_corretiva_modal, name='salvar_acao_corretiva_modal'),
    
    # Soluções Legacy
    path('solucoes/', listar_solucoes, name='listar_solucoes'),
    path('solucoes/criar-registro/', criar_registro_modal, name='criar_registro_modal'),
    path('solucoes/criar-acao-plano/', criar_plano_acao_modal, name='criar_plano_acao_modal'),
    path('solucoes/editar-acao-plano/<int:linha_id>/', editar_linha_acao_modal, name='editar_linha_acao_modal'),
    path('solucoes/importar-controles/', importar_controle_registros, name='importar_controle_registros'),
    path('solucoes/importar-controles/template/', download_template_controle_registros, name='download_template_controle_registros'),
    path('solucoes/importar-plano-acao/', importar_plano_acao, name='importar_plano_acao'),
    path('solucoes/importar-plano-acao/template/', download_template_plano_acao, name='download_template_plano_acao'),
    path('solucao/<int:solucao_id>/', detalhe_solucao, name='detalhe_solucao'),
    path('acao/<int:acao_id>/solucao/criar/', criar_solucao, name='criar_solucao'),
    path('solucao/<int:solucao_id>/editar/', editar_solucao, name='editar_solucao'),
    
    # Templates
    path('templates/', listar_templates, name='listar_templates'),
    path('template/<int:template_id>/download/', download_template, name='download_template'),

    # ========================================================================
    # KPI (Referencia de Dados)
    # ========================================================================
    path('kpis/', KPIOpcaoListView.as_view(), name='kpi_opcao_list'),
    path('kpis/novo/', KPIOpcaoCreateView.as_view(), name='kpi_opcao_create'),
    path('kpis/<int:pk>/editar/', KPIOpcaoUpdateView.as_view(), name='kpi_opcao_update'),
    path('kpis/<int:pk>/deletar/', KPIOpcaoDeleteView.as_view(), name='kpi_opcao_delete'),
    
    # ========================================================================
    # DASHBOARD
    # ========================================================================
    path('dashboard/', AcoesDashboardView.as_view(), name='dashboard'),
    
    # ========================================================================
    # AÇÕES REGISTRADAS (Agregação de todos os tipos)
    # ========================================================================
    path('acoes-registradas/', AcoesRegistradasView.as_view(), name='acoes_registradas'),
    
    # ========================================================================
    # PLANO DE AÇÃO
    # ========================================================================
    path('plano-acao/', PlanoAcaoListView.as_view(), name='plano_acao_list'),
    path('plano-acao/novo/', PlanoAcaoCreateView.as_view(), name='plano_acao_create'),
    path('plano-acao/<int:pk>/editar/', PlanoAcaoUpdateView.as_view(), name='plano_acao_update'),
    path('plano-acao/<int:pk>/deletar/', plano_acao_delete, name='plano_acao_delete'),
    path('plano-acao/<int:pk>/', PlanoAcaoDetailView.as_view(), name='plano_acao_detail'),
    
    # ========================================================================
    # LINHA DE AÇÃO
    # ========================================================================
    path('linha-acao/<int:pk>/editar/', LinhaAcaoUpdateView.as_view(), name='linha_acao_update'),
    path('linha-acao/<int:pk>/deletar/', linha_acao_delete, name='linha_acao_delete'),
    
    # ========================================================================
    # SOLUÇÃO A3
    # ========================================================================
    path('a3/', SolucaoA3ListView.as_view(), name='a3_list'),
    path('a3/novo/', SolucaoA3CreateView.as_view(), name='a3_create'),
    path('a3/<int:pk>/editar/', SolucaoA3UpdateView.as_view(), name='a3_update'),
    path('a3/<int:pk>/', SolucaoA3DetailView.as_view(), name='a3_detail'),
    
    # ========================================================================
    # SOLUÇÃO 8D
    # ========================================================================
    path('8d/', Solucao8DListView.as_view(), name='8d_list'),
    path('8d/novo/', Solucao8DCreateView.as_view(), name='8d_create'),
    path('8d/<int:pk>/editar/', Solucao8DUpdateView.as_view(), name='8d_update'),
    path('8d/<int:pk>/', Solucao8DDetailView.as_view(), name='8d_detail'),
    
    # ========================================================================
    # RNC (Registro de Não Conformidade)
    # ========================================================================
    path('rnc/', SolucaoRNCListView.as_view(), name='rnc_list'),
    path('rnc/novo/', SolucaoRNCCreateView.as_view(), name='rnc_create'),
    path('rnc/<int:pk>/editar/', SolucaoRNCUpdateView.as_view(), name='rnc_update'),
    path('rnc/<int:pk>/', SolucaoRNCDetailView.as_view(), name='rnc_detail'),
    
    # ========================================================================
    # GESTÃO DE MUDANÇA
    # ========================================================================
    path('gestao-mudanca/', SolucaoGestaoDeMudancaListView.as_view(), name='gestao_mudanca_list'),
    path('gestao-mudanca/novo/', SolucaoGestaoDeMudancaCreateView.as_view(), name='gestao_mudanca_create'),
    path('gestao-mudanca/<int:pk>/editar/', SolucaoGestaoDeMudancaUpdateView.as_view(), name='gestao_mudanca_update'),
    path('gestao-mudanca/<int:pk>/', SolucaoGestaoDeMudancaDetailView.as_view(), name='gestao_mudanca_detail'),
    
    # ========================================================================
    # REVISÃO GERENCIAL
    # ========================================================================
    path('revisao-gerencial/', RevisaoGerencialListView.as_view(), name='revisao_gerencial_list'),
    path('revisao-gerencial/novo/', RevisaoGerencialCreateView.as_view(), name='revisao_gerencial_create'),
    path('revisao-gerencial/<int:pk>/editar/', RevisaoGerencialUpdateView.as_view(), name='revisao_gerencial_update'),
    path('revisao-gerencial/<int:pk>/', RevisaoGerencialDetailView.as_view(), name='revisao_gerencial_detail'),
    
    # ========================================================================
    # ORIGEM DO PROBLEMA (Referência de Dados)
    # ========================================================================
    path('origem-problema/', OrigemProblemaListView.as_view(), name='origem_problema_list'),
    path('origem-problema/novo/', OrigemProblemaCreateView.as_view(), name='origem_problema_create'),
    path('origem-problema/<int:pk>/editar/', OrigemProblemaUpdateView.as_view(), name='origem_problema_update'),
    path('origem-problema/<int:pk>/deletar/', OrigemProblemaDeleteView.as_view(), name='origem_problema_delete'),
    
    # ========================================================================
    # API ENDPOINTS
    # ========================================================================
    path('api/proximo-numero/', obter_proximo_numero, name='obter_proximo_numero'),
]

"""
Automated Tests for Phase 3 - HTML Templates & CRUD Operations
Tests for all 6 solution types with full CRUD workflow coverage
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

from organization.models import Setor
from rh.models import Colaborador

from acoes.models import (
    AcaoCorretiva,
    PlanoAcao,
    SolucaoA3,
    Solucao8D,
    SolucaoRNC,
    SolucaoGestaoDeMudanca,
    RevisaoGerencial,
    Solucao
)


@pytest.fixture
def user(db):
    """Create a test user for authentication"""
    import uuid
    unique_username = f'testuser_{uuid.uuid4().hex[:8]}'
    return User.objects.create_user(
        username=unique_username,
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def plano_acao_data():
    """Fixture for PlanoAcao test data"""
    return {
        'numero': 'PA001',
        'descricao': 'Implementar novo processo de qualidade',
        'responsavel': 'João Silva',
        'status': 'planejada',
        'classificacao': 'melhoria',
        'data_vencimento': datetime.now().date() + timedelta(days=30),
        'prioridade': True,
        'efetividade': 'alta',
        'resultado_esperado': 'Aumentar conformidade em 20%',
    }


@pytest.fixture
def solucao_a3_data():
    """Fixture for SolucaoA3 test data"""
    return {
        'numero_a3': 'A3001',
        'laboratorio': None,
        'lider_projeto': 'Maria Santos',
        'descricao_problema': 'Reprocessamento alto de amostras',
        'situacao_atual': 'Reprocessamento em 15%',
        'situacao_desejada': 'Reprocessamento em 5%',
        'problema_identificado': 'sistema',
        'resultado': 'Redução alcançada de 10%',
        'indicador': 'Taxa de reprocessamento',
    }


@pytest.fixture
def setor(db):
    import uuid
    return Setor.objects.create(nome=f"Setor Teste {uuid.uuid4().hex[:8]}")


@pytest.fixture
def colaborador_factory(db, setor):
    import uuid

    def _create(nome_completo: str) -> Colaborador:
        return Colaborador.objects.create(
            matricula=f"T{uuid.uuid4().hex[:10]}",
            nome_completo=nome_completo,
            grupo="Teste",
            setor=setor,
        )

    return _create


@pytest.fixture
def solucao_8d_data():
    """Fixture for Solucao8D test data"""
    return {
        'numero_formulario': '8D001',
        'data_abertura': datetime.now().date(),
        'lider_8d': 'Carlos Mendes',
        'departamento': 'Qualidade',
        'problema_identificado': 'Variação em resultados de testes',
        'prazo_projeto': datetime.now().date() + timedelta(days=60),
        'd2_descricao': 'Problema de calibração',
        'd3_contencao': 'Suspender testes até resolução',
        'd4_causa_raiz': 'Falha no equipamento',
        'd5_contramedidas': 'Substituição do equipamento',
        'd6_implementacao': 'Já implementado',
        'd6_status': 'implementada',
    }


@pytest.fixture
def solucao_rnc_data():
    """Fixture for SolucaoRNC test data"""
    return {
        'numero_rnc': 'RNC001',
        'data_identificacao': datetime.now().date(),
        'responsavel_abertura': 'Ana Costa',
        'descricao': 'Amostra processada com protocolo incorreto',
        'origem': 'interno',
        'classificacao': 'nc',
        'nivel_risco': 'alto',
        'acao_corretiva': 'Implementar checklist de verificação',
        'data_target_implementacao': datetime.now().date() + timedelta(days=15),
    }


@pytest.fixture
def solucao_mudanca_data():
    """Fixture for SolucaoGestaoDeMudanca test data"""
    return {
        'numero_registro': 'MUD001',
        'data_solicitacao': datetime.now().date(),
        'solicitante': 'Roberto Alves',
        'titulo': 'Atualização de SOP de Qualidade',
        'descricao': 'Implementar novo procedimento de auditorias internas',
        'tipo_mudanca': 'preventiva',
        'prioridade': 'medio',
        'status': 'analise',
    }


@pytest.fixture
def revisao_gerencial_data():
    """Fixture for RevisaoGerencial test data"""
    return {
        'numero_rg': 'RG001',
        'data_revisao': datetime.now().date(),
        'periodo_inicio': datetime.now().date() - timedelta(days=365),
        'periodo_fim': datetime.now().date(),
        'desempenho_processos': 'Processos operando dentro dos limites',
        'conformidade_requisitos': '100% em conformidade',
        'satisfacao_cliente': 'Satisfação em 95%',
    }


# ============================================================================
# PLANO DE AÇÃO TESTS
# ============================================================================

@pytest.mark.django_db
class TestPlanoAcaoListView:
    """Test PlanoAcao list view"""
    
    def test_list_view_accessible(self, client, user):
        """Test that list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_list'))
        assert response.status_code == 200
        assert 'object_list' in response.context
    
    def test_list_view_shows_planos(self, client, user, plano_acao_data):
        """Test that list view shows created planos"""
        PlanoAcao.objects.create(**plano_acao_data)
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_list'))
        assert response.status_code == 200
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestPlanoAcaoCRUD:
    """Test PlanoAcao CRUD operations"""
    
    def test_create_plano_acao(self, client, user, plano_acao_data):
        """Test creating a new PlanoAcao"""
        client.force_login(user)
        response = client.post(reverse('acoes:plano_acao_create'), plano_acao_data)
        assert PlanoAcao.objects.count() == 1
        plano = PlanoAcao.objects.first()
        assert plano.numero == 'PA001'
    
    def test_edit_plano_acao(self, client, user, plano_acao_data):
        """Test editing a PlanoAcao"""
        plano = PlanoAcao.objects.create(**plano_acao_data)
        client.force_login(user)
        plano_acao_data['descricao'] = 'Descrição atualizada'
        response = client.post(reverse('acoes:plano_acao_edit', args=[plano.pk]), plano_acao_data)
        plano.refresh_from_db()
        assert plano.descricao == 'Descrição atualizada'
    
    def test_detail_view_plano_acao(self, client, user, plano_acao_data):
        """Test viewing PlanoAcao detail"""
        plano = PlanoAcao.objects.create(**plano_acao_data)
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_detail', args=[plano.pk]))
        assert response.status_code == 200
        assert response.context['object'] == plano


# ============================================================================
# SOLUÇÃO A3 TESTS
# ============================================================================

@pytest.mark.django_db
class TestSolucaoA3ListeView:
    """Test SolucaoA3 list view"""
    
    def test_a3_list_view_accessible(self, client, user):
        """Test that A3 list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:a3_list'))
        assert response.status_code == 200
    
    def test_a3_list_shows_entries(self, client, user, colaborador_factory):
        """Test that A3 list shows entries"""
        lider = colaborador_factory("Maria Santos")
        acao = AcaoCorretiva.objects.create(
            titulo="Ação teste A3",
            descricao="Descrição teste",
            data_vencimento=timezone.now().date() + timedelta(days=30),
            criado_por=lider,
            responsavel=lider,
        )
        solucao = Solucao.objects.create(
            acao_corretiva=acao,
            tipo="a3",
            titulo="Solução A3 teste",
            descricao="Descrição solução",
            responsavel=lider,
        )
        SolucaoA3.objects.create(
            solucao=solucao,
            a3_numero="A3-TESTE-001",
            data_criacao=timezone.now().date(),
            laboratorio="Lab",
            lider_projeto=lider,
            problema="Problema teste",
        )
        client.force_login(user)
        response = client.get(reverse('acoes:a3_list'))
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestSolucaoA3CRUD:
    """Test SolucaoA3 CRUD operations"""
    
    def test_create_a3(self, client, user, solucao_a3_data):
        """Test creating a new A3"""
        client.force_login(user)
        response = client.post(reverse('acoes:a3_create'), solucao_a3_data)
        assert SolucaoA3.objects.count() == 1
    
    def test_edit_a3(self, client, user, solucao_a3_data):
        """Test editing an A3"""
        a3 = SolucaoA3.objects.create(**solucao_a3_data)
        client.force_login(user)
        solucao_a3_data['descricao_problema'] = 'Problema atualizado'
        response = client.post(reverse('acoes:a3_edit', args=[a3.pk]), solucao_a3_data)
        a3.refresh_from_db()
        assert a3.descricao_problema == 'Problema atualizado'
    
    def test_detail_view_a3(self, client, user, solucao_a3_data):
        """Test viewing A3 detail"""
        a3 = SolucaoA3.objects.create(**solucao_a3_data)
        client.force_login(user)
        response = client.get(reverse('acoes:a3_detail', args=[a3.pk]))
        assert response.status_code == 200
        assert response.context['object'] == a3


# ============================================================================
# SOLUÇÃO 8D TESTS
# ============================================================================

@pytest.mark.django_db
class TestSolucao8DListView:
    """Test Solucao8D list view"""
    
    def test_8d_list_view_accessible(self, client, user):
        """Test that 8D list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:8d_list'))
        assert response.status_code == 200
    
    def test_8d_list_shows_entries(self, client, user, colaborador_factory):
        """Test that 8D list shows entries"""
        lider = colaborador_factory("Carlos Mendes")
        acao = AcaoCorretiva.objects.create(
            titulo="Ação teste 8D",
            descricao="Descrição teste",
            data_vencimento=timezone.now().date() + timedelta(days=30),
            criado_por=lider,
            responsavel=lider,
        )
        solucao = Solucao.objects.create(
            acao_corretiva=acao,
            tipo="8d",
            titulo="Solução 8D teste",
            descricao="Descrição solução",
            responsavel=lider,
        )
        Solucao8D.objects.create(
            solucao=solucao,
            numero_formulario="8D-TESTE-001",
            data_abertura=timezone.now(),
            lider_8d=lider,
            departamento="Qualidade",
            problema_identificado="Problema 8D teste",
        )
        client.force_login(user)
        response = client.get(reverse('acoes:8d_list'))
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestSolucao8DCRUD:
    """Test Solucao8D CRUD operations"""
    
    def test_create_8d(self, client, user, solucao_8d_data):
        """Test creating a new 8D"""
        client.force_login(user)
        response = client.post(reverse('acoes:8d_create'), solucao_8d_data)
        assert Solucao8D.objects.count() == 1
    
    def test_edit_8d(self, client, user, solucao_8d_data):
        """Test editing an 8D"""
        oito_d = Solucao8D.objects.create(**solucao_8d_data)
        client.force_login(user)
        solucao_8d_data['lider_8d'] = 'Novo Líder'
        response = client.post(reverse('acoes:8d_edit', args=[oito_d.pk]), solucao_8d_data)
        oito_d.refresh_from_db()
        assert oito_d.lider_8d == 'Novo Líder'
    
    def test_detail_view_8d(self, client, user, solucao_8d_data):
        """Test viewing 8D detail"""
        oito_d = Solucao8D.objects.create(**solucao_8d_data)
        client.force_login(user)
        response = client.get(reverse('acoes:8d_detail', args=[oito_d.pk]))
        assert response.status_code == 200
        assert response.context['object'] == oito_d


# ============================================================================
# SOLUÇÃO RNC TESTS
# ============================================================================

@pytest.mark.django_db
class TestSolucaoRNCListView:
    """Test SolucaoRNC list view"""
    
    def test_rnc_list_view_accessible(self, client, user):
        """Test that RNC list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:rnc_list'))
        assert response.status_code == 200
    
    def test_rnc_list_shows_entries(self, client, user, colaborador_factory):
        """Test that RNC list shows entries"""
        responsavel = colaborador_factory("Ana Costa")
        acao = AcaoCorretiva.objects.create(
            titulo="Ação teste RNC",
            descricao="Descrição teste",
            data_vencimento=timezone.now().date() + timedelta(days=30),
            criado_por=responsavel,
            responsavel=responsavel,
        )
        solucao = Solucao.objects.create(
            acao_corretiva=acao,
            tipo="rnc",
            titulo="Solução RNC teste",
            descricao="Descrição solução",
            responsavel=responsavel,
        )
        SolucaoRNC.objects.create(
            solucao=solucao,
            numero_rnc="RNC-TESTE-001",
            data_abertura=timezone.now(),
            origem="processo",
            risco="alto",
            descricao_nc="Descrição NC teste",
            responsavel=responsavel,
        )
        client.force_login(user)
        response = client.get(reverse('acoes:rnc_list'))
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestSolucaoRNCCRUD:
    """Test SolucaoRNC CRUD operations"""
    
    def test_create_rnc(self, client, user, solucao_rnc_data):
        """Test creating a new RNC"""
        client.force_login(user)
        response = client.post(reverse('acoes:rnc_create'), solucao_rnc_data)
        assert SolucaoRNC.objects.count() == 1
    
    def test_edit_rnc(self, client, user, solucao_rnc_data):
        """Test editing an RNC"""
        rnc = SolucaoRNC.objects.create(**solucao_rnc_data)
        client.force_login(user)
        solucao_rnc_data['descricao'] = 'Descrição atualizada'
        response = client.post(reverse('acoes:rnc_edit', args=[rnc.pk]), solucao_rnc_data)
        rnc.refresh_from_db()
        assert rnc.descricao == 'Descrição atualizada'
    
    def test_detail_view_rnc(self, client, user, solucao_rnc_data):
        """Test viewing RNC detail"""
        rnc = SolucaoRNC.objects.create(**solucao_rnc_data)
        client.force_login(user)
        response = client.get(reverse('acoes:rnc_detail', args=[rnc.pk]))
        assert response.status_code == 200
        assert response.context['object'] == rnc
    
    def test_rnc_risk_levels(self, client, user, solucao_rnc_data):
        """Test RNC with different risk levels"""
        for risk in ['alto', 'medio', 'baixo']:
            solucao_rnc_data['nivel_risco'] = risk
            rnc = SolucaoRNC.objects.create(**solucao_rnc_data)
            assert rnc.nivel_risco == risk
            rnc.delete()


# ============================================================================
# GESTÃO DE MUDANÇA TESTS
# ============================================================================

@pytest.mark.django_db
class TestSolucaoMudancaListView:
    """Test SolucaoGestaoDeMudanca list view"""
    
    def test_mudanca_list_view_accessible(self, client, user):
        """Test that Mudança list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:mudanca_list'))
        assert response.status_code == 200
    
    def test_mudanca_list_shows_entries(self, client, user, solucao_mudanca_data):
        """Test that Mudança list shows entries"""
        SolucaoGestaoDeMudanca.objects.create(**solucao_mudanca_data)
        client.force_login(user)
        response = client.get(reverse('acoes:mudanca_list'))
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestSolucaoMudancaCRUD:
    """Test SolucaoGestaoDeMudanca CRUD operations"""
    
    def test_create_mudanca(self, client, user, solucao_mudanca_data):
        """Test creating a new Mudança"""
        client.force_login(user)
        response = client.post(reverse('acoes:mudanca_create'), solucao_mudanca_data)
        assert SolucaoGestaoDeMudanca.objects.count() == 1
    
    def test_edit_mudanca(self, client, user, solucao_mudanca_data):
        """Test editing a Mudança"""
        mudanca = SolucaoGestaoDeMudanca.objects.create(**solucao_mudanca_data)
        client.force_login(user)
        solucao_mudanca_data['titulo'] = 'Título atualizado'
        response = client.post(reverse('acoes:mudanca_edit', args=[mudanca.pk]), solucao_mudanca_data)
        mudanca.refresh_from_db()
        assert mudanca.titulo == 'Título atualizado'
    
    def test_detail_view_mudanca(self, client, user, solucao_mudanca_data):
        """Test viewing Mudança detail"""
        mudanca = SolucaoGestaoDeMudanca.objects.create(**solucao_mudanca_data)
        client.force_login(user)
        response = client.get(reverse('acoes:mudanca_detail', args=[mudanca.pk]))
        assert response.status_code == 200
        assert response.context['object'] == mudanca


# ============================================================================
# REVISÃO GERENCIAL TESTS
# ============================================================================

@pytest.mark.django_db
class TestRevisaoGerencialListView:
    """Test RevisaoGerencial list view"""
    
    def test_rg_list_view_accessible(self, client, user):
        """Test that RG list view is accessible"""
        client.force_login(user)
        response = client.get(reverse('acoes:revisao_gerencial_list'))
        assert response.status_code == 200
    
    def test_rg_list_shows_entries(self, client, user, revisao_gerencial_data):
        """Test that RG list shows entries"""
        RevisaoGerencial.objects.create(**revisao_gerencial_data)
        client.force_login(user)
        response = client.get(reverse('acoes:revisao_gerencial_list'))
        assert len(response.context['object_list']) == 1


@pytest.mark.django_db
class TestRevisaoGerencialCRUD:
    """Test RevisaoGerencial CRUD operations"""
    
    def test_create_rg(self, client, user, revisao_gerencial_data):
        """Test creating a new RG"""
        client.force_login(user)
        response = client.post(reverse('acoes:revisao_gerencial_create'), revisao_gerencial_data)
        assert RevisaoGerencial.objects.count() == 1
    
    def test_edit_rg(self, client, user, revisao_gerencial_data):
        """Test editing a RG"""
        rg = RevisaoGerencial.objects.create(**revisao_gerencial_data)
        client.force_login(user)
        revisao_gerencial_data['numero_rg'] = 'RG002'
        response = client.post(reverse('acoes:revisao_gerencial_edit', args=[rg.pk]), revisao_gerencial_data)
        rg.refresh_from_db()
        assert rg.numero_rg == 'RG002'
    
    def test_detail_view_rg(self, client, user, revisao_gerencial_data):
        """Test viewing RG detail"""
        rg = RevisaoGerencial.objects.create(**revisao_gerencial_data)
        client.force_login(user)
        response = client.get(reverse('acoes:revisao_gerencial_detail', args=[rg.pk]))
        assert response.status_code == 200
        assert response.context['object'] == rg


# ============================================================================
# FORM VALIDATION TESTS
# ============================================================================

@pytest.mark.django_db
class TestFormValidation:
    """Test form validation for all solution types"""
    
    def test_plano_acao_form_required_fields(self, client, user):
        """Test PlanoAcao form requires essential fields"""
        client.force_login(user)
        response = client.post(reverse('acoes:plano_acao_create'), {})
        assert response.status_code == 200  # Form re-rendered with errors
    
    def test_rnc_classification_choices(self, client, user, solucao_rnc_data):
        """Test RNC classification choices"""
        for classification in ['nc', 'ac', 'op']:
            solucao_rnc_data['classificacao'] = classification
            rnc = SolucaoRNC.objects.create(**solucao_rnc_data)
            assert rnc.classificacao == classification
            rnc.delete()


# ============================================================================
# URL ROUTING TESTS
# ============================================================================

@pytest.mark.django_db
class TestURLRouting:
    """Test all URL patterns"""
    
    def test_all_list_urls_accessible(self, client, user):
        """Test all list view URLs"""
        urls = [
            'acoes:plano_acao_list',
            'acoes:a3_list',
            'acoes:8d_list',
            'acoes:rnc_list',
            'acoes:mudanca_list',
            'acoes:revisao_gerencial_list',
        ]
        client.force_login(user)
        for url_name in urls:
            response = client.get(reverse(url_name))
            assert response.status_code == 200, f"URL {url_name} failed"
    
    def test_create_urls_accessible(self, client, user):
        """Test all create view URLs"""
        urls = [
            'acoes:plano_acao_create',
            'acoes:a3_create',
            'acoes:8d_create',
            'acoes:rnc_create',
            'acoes:mudanca_create',
            'acoes:revisao_gerencial_create',
        ]
        client.force_login(user)
        for url_name in urls:
            response = client.get(reverse(url_name))
            assert response.status_code == 200, f"URL {url_name} failed"


# ============================================================================
# TEMPLATE RENDERING TESTS
# ============================================================================

@pytest.mark.django_db
class TestTemplateRendering:
    """Test that all templates render correctly"""
    
    def test_list_templates_use_correct_template(self, client, user, plano_acao_data):
        """Test that list views use correct templates"""
        PlanoAcao.objects.create(**plano_acao_data)
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_list'))
        assert 'plano_acao_list.html' in [t.name for t in response.templates]
    
    def test_form_templates_use_correct_template(self, client, user):
        """Test that form views use correct templates"""
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_create'))
        assert 'planoacao_form.html' in [t.name for t in response.templates]
    
    def test_detail_templates_use_correct_template(self, client, user, plano_acao_data):
        """Test that detail views use correct templates"""
        plano = PlanoAcao.objects.create(**plano_acao_data)
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_detail', args=[plano.pk]))
        assert 'planoacao_detail.html' in [t.name for t in response.templates]


# ============================================================================
# AUTHENTICATION & PERMISSION TESTS
# ============================================================================

@pytest.mark.django_db
class TestAuthentication:
    """Test authentication requirements"""
    
    def test_unauthenticated_user_redirected(self, client):
        """Test that unauthenticated users are redirected"""
        response = client.get(reverse('acoes:plano_acao_list'))
        assert response.status_code == 302  # Redirect to login
    
    def test_authenticated_user_can_access(self, client, user):
        """Test that authenticated users can access views"""
        client.force_login(user)
        response = client.get(reverse('acoes:plano_acao_list'))
        assert response.status_code == 200

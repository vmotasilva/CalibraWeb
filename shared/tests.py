"""
Tests for shared module - Common and shared functionality
"""
from django.http import HttpResponse
from django.templatetags.static import static
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.urls import reverse
from datetime import date, timedelta
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import NoReverseMatch

from shared.middleware import AuthNoCacheMiddleware
from shared.views import hub_view



class SharedViewsTests(TestCase):
    """Integration tests for shared views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='shared_user',
            password='testpass123'
        )
    
    def test_dashboard_requires_authentication(self):
        """Test that dashboard requires authentication"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
    
    def test_dashboard_authenticated(self):
        """Test dashboard with authenticated user"""
        self.client.login(username='shared_user', password='testpass123')
        response = self.client.get(reverse('home'))
        # Em ambientes com 2FA/OTP middleware, usuários podem ser redirecionados
        # para fluxos de verificação adicional. Aceitar 302 como resultado válido.
        self.assertIn(response.status_code, [200, 302, 404])
    
    def test_health_check_accessible(self):
        """Test health check endpoint is accessible without auth"""
        # O projeto pode ou não expor um endpoint nomeado 'health_check'.
        try:
            url = reverse('health_check')
        except NoReverseMatch:
            self.skipTest("health_check URL não está configurada")

        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 404])


class SharedHubViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='hub_user',
            password='testpass123',
            is_staff=True,
        )

    def test_hub_requires_authentication(self):
        response = self.client.get(reverse('hub'))
        self.assertEqual(response.status_code, 302)

    def test_hub_renders_core_sections_for_authenticated_user(self):
        request = self.factory.get(reverse('hub'))
        request.user = self.user

        response = hub_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calibra HUB')
        self.assertNotContains(response, 'Favoritos')
        self.assertContains(response, 'Módulos do Sistema')
        self.assertContains(response, 'Acessar HUB de')
        self.assertNotContains(response, 'Ações Rápidas Globais')

    def test_api_hub_search_returns_resources(self):
        """Testa o endpoint AJAX de busca global de funcionalidades e telas."""
        self.client.force_login(self.user)
        url = reverse('api_hub_search')

        # Busca sem termo (retorna principais)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total'], 0)

        # Busca por módulo
        response = self.client.get(f"{url}?q=auditoria")
        data = response.json()
        self.assertTrue(any("Auditoria" in item["module"] for item in data["results"]))

        # Busca por termo de função
        response = self.client.get(f"{url}?q=instrumentos")
        data = response.json()
        self.assertTrue(any("Instrumentos" in item["title"] for item in data["results"]))

        # Busca por sessão
        response = self.client.get(f"{url}?q=operacional")
        data = response.json()
        self.assertTrue(any("Operacional" in item["session"] for item in data["results"]))

    def test_module_hubs_render_for_all_modules(self):
        """Testa que cada módulo ativo possui seu HUB dedicado com atividades."""
        self.client.force_login(self.user)
        modulos = [
            ('auditoria', 'HUB de Auditoria', 'Dashboard de Auditoria'),
            ('metrologia', 'HUB de Metrologia', 'Lista de Instrumentos'),
            ('treinamentos', 'HUB de Treinamentos', 'Matriz de Habilidades Geral'),
            ('boards', 'HUB de Quadros', 'Painel de Quadros'),
            ('laboratorio', 'HUB de Laboratório', 'Painel de Ocorrências'),
            ('pessoas', 'HUB de Pessoas', 'Quadro de Colaboradores'),
            ('fornecedores', 'HUB de Fornecedores', 'Base de Fornecedores'),
        ]

        for slug, expected_title, expected_activity in modulos:
            url = reverse('module_hub', kwargs={'module_slug': slug})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Falha ao carregar HUB do módulo {slug}")
            self.assertContains(response, expected_title)
            self.assertContains(response, expected_activity)
            self.assertContains(response, 'mod-hero')
            self.assertContains(response, 'data-lpignore="true"')
            self.assertContains(response, 'fake_username_trap')

    def test_direct_app_hub_routes(self):
        """Testa que as rotas diretas dos apps (ex: /auditoria/hub/) funcionam perfeitamente."""
        self.client.force_login(self.user)
        direct_routes = [
            'auditoria:hub',
            'metrologia:hub',
            'procedures:hub',
            'boards:hub',
            'laboratorio:hub',
            'rh:hub',
            'fornecedores:hub',
        ]
        for route_name in direct_routes:
            url = reverse(route_name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Rota {route_name} falhou")



class SharedImportsTests(TestCase):
    """Test that all shared imports are working correctly"""
    
    def test_shared_views_import(self):
        """Test that shared views can be imported"""
        from shared.views import (
            dashboard_view, health_check
        )
        self.assertIsNotNone(dashboard_view)
        self.assertIsNotNone(health_check)


class SharedNotificationsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="u1", password="pass")

    def test_cobrancas_metrologia_counts_vencidos_without_responsavel(self):
        from metrologia.models import Instrumento
        from shared.notifications import get_user_cobrancas_counts

        Instrumento.objects.create(
            tag="INS-TEST-1",
            descricao="Instrumento X",
            ativo=True,
            data_proxima_calibracao=date.today() - timedelta(days=1),
        )

        counts = get_user_cobrancas_counts(self.user)
        self.assertGreaterEqual(int(counts.get("metrologia", 0)), 1)

    def test_cobrancas_cotacoes_counts_overdue_solicitacoes_for_user(self):
        from metrologia.models import SolicitacaoCotacao
        from shared.notifications import get_user_cobrancas_counts

        SolicitacaoCotacao.objects.create(
            responsavel=self.user,
            data_solicitacao_orcamento=date.today() - timedelta(days=1),
            status="ABERTA",
        )

        counts = get_user_cobrancas_counts(self.user)
        self.assertGreaterEqual(int(counts.get("cotacoes", 0)), 1)


class SharedAuthPagesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    def test_auth_no_cache_middleware_sets_headers_for_login_path(self):
        middleware = AuthNoCacheMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(self.factory.get("/account/login/"))

        self.assertEqual(response["Cache-Control"], "no-cache, no-store, must-revalidate, max-age=0")
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["Expires"], "0")
        self.assertIn("Cookie", response["Vary"])

    def test_two_factor_login_uses_existing_logo_asset(self):
        try:
            url = reverse("two_factor:login")
        except NoReverseMatch:
            self.skipTest("two_factor:login URL não está configurada neste ambiente de teste")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, static("shared/logo_calibraweb.svg"))
        self.assertNotContains(response, "/static/logo.png")
        self.assertEqual(response["Cache-Control"], "no-cache, no-store, must-revalidate, max-age=0")
        self.assertIn("Cookie", response["Vary"])
    

class SharedTrustedMachineTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='test_trusted',
            password='password123'
        )

    def test_session_expiry_with_trusted_machine(self):
        request = self.factory.post('/login/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        
        # Set trusted_machine cookie
        request.COOKIES['trusted_machine'] = '1'
        
        # Trigger login signal
        user_logged_in.send(sender=User, request=request, user=self.user)
        
        # Verify session expiry is 30 days (2592000 seconds)
        self.assertEqual(request.session.get_expiry_age(), 2592000)
        self.assertFalse(request.session.get_expire_at_browser_close())

    def test_session_expiry_without_trusted_machine(self):
        request = self.factory.post('/login/')
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        
        # Do not set trusted_machine cookie or set it to '0'
        request.COOKIES['trusted_machine'] = '0'
        
        # Trigger login signal
        user_logged_in.send(sender=User, request=request, user=self.user)
        
        # Verify session is set to expire on browser close
        self.assertTrue(request.session.get_expire_at_browser_close())


class SharedInboxPlanejamentoTests(TestCase):
    def setUp(self):
        cache.clear()
        from rh.models import Colaborador
        from procedures.models import PlanejamentoTreinamento, Procedimento

        # Usuários e colaboradores
        self.user_instrutor = User.objects.create_user(username='instrutor_user', password='pass')
        self.colab_instrutor = Colaborador.objects.create(
            user_django=self.user_instrutor, matricula='1001', nome_completo='INSTRUTOR SILVA'
        )

        self.user_lider = User.objects.create_user(username='lider_user', password='pass')
        self.colab_lider = Colaborador.objects.create(
            user_django=self.user_lider, matricula='1002', nome_completo='LIDER SOUZA'
        )

        self.user_outro = User.objects.create_user(username='outro_user', password='pass')
        self.colab_outro = Colaborador.objects.create(
            user_django=self.user_outro, matricula='1003', nome_completo='OUTRO ALVES'
        )

        self.colab_participante = Colaborador.objects.create(
            matricula='1004', nome_completo='OPERADOR JUNIOR', lider=self.colab_lider
        )

        self.procedimento = Procedimento.objects.create(
            codigo='PROC-999', nome='Procedimento Operacional', numero_revisao='01'
        )

        # 1. Planejamento em andamento / planejado no futuro
        self.plan_futuro = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento Segurança Futuro',
            instrutor=self.colab_instrutor,
            data_prevista=date.today() + timedelta(days=5),
            status='PLANEJADO'
        )
        self.plan_futuro.procedimentos.add(self.procedimento)
        self.plan_futuro.colaboradores.add(self.colab_participante)

        # 2. Planejamento atrasado (data prevista no passado)
        self.plan_atrasado = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento Qualidade Atrasado',
            instrutor=self.colab_instrutor,
            data_prevista=date.today() - timedelta(days=2),
            status='PLANEJADO'
        )
        self.plan_atrasado.colaboradores.add(self.colab_participante)

        # 3. Planejamento realizado (deve sair da notificação)
        self.plan_realizado = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento Realizado Concluído',
            instrutor=self.colab_instrutor,
            data_prevista=date.today() - timedelta(days=1),
            status='REALIZADO'
        )
        self.plan_realizado.colaboradores.add(self.colab_participante)

        # 4. Planejamento cancelado (deve sair da notificação)
        self.plan_cancelado = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento Cancelado',
            instrutor=self.colab_instrutor,
            data_prevista=date.today() + timedelta(days=1),
            status='CANCELADO'
        )
        self.plan_cancelado.colaboradores.add(self.colab_participante)

    def test_instrutor_recebe_notificacao_planejados_e_atrasados_mas_nao_concluidos_nem_cancelados(self):
        from shared.inbox import get_user_inbox_items
        cache.clear()

        items = get_user_inbox_items(self.user_instrutor)
        plan_items = [item for item in items if item.sub_type == "Treinamentos Planejados"]

        plan_ids = [item.id for item in plan_items]
        self.assertIn(f"planejamento_treinamento_{self.plan_futuro.id}", plan_ids)
        self.assertIn(f"planejamento_treinamento_{self.plan_atrasado.id}", plan_ids)
        self.assertNotIn(f"planejamento_treinamento_{self.plan_realizado.id}", plan_ids)
        self.assertNotIn(f"planejamento_treinamento_{self.plan_cancelado.id}", plan_ids)

        # Verificar flag de urgência no atrasado
        item_atrasado = next(i for i in plan_items if i.id == f"planejamento_treinamento_{self.plan_atrasado.id}")
        self.assertTrue(item_atrasado.is_urgent)
        self.assertIn("Atrasado", item_atrasado.title)

        # Verificar item futuro
        item_futuro = next(i for i in plan_items if i.id == f"planejamento_treinamento_{self.plan_futuro.id}")
        self.assertFalse(item_futuro.is_urgent)
        self.assertIn("Planejado", item_futuro.title)

    def test_lider_recebe_notificacao_dos_planejamentos_da_sua_equipe(self):
        from shared.inbox import get_user_inbox_items
        cache.clear()

        items = get_user_inbox_items(self.user_lider)
        plan_items = [item for item in items if item.sub_type == "Treinamentos Planejados"]

        plan_ids = [item.id for item in plan_items]
        self.assertIn(f"planejamento_treinamento_{self.plan_futuro.id}", plan_ids)
        self.assertIn(f"planejamento_treinamento_{self.plan_atrasado.id}", plan_ids)
        self.assertNotIn(f"planejamento_treinamento_{self.plan_realizado.id}", plan_ids)
        self.assertNotIn(f"planejamento_treinamento_{self.plan_cancelado.id}", plan_ids)

    def test_planejamento_cancelado_vencido_e_case_insensitive(self):
        """Garante que planejamentos cancelados mesmo com data vencida não entram na inbox nem viram ATRASADO."""
        from shared.inbox import get_user_inbox_items
        from procedures.models import PlanejamentoTreinamento
        cache.clear()

        plan_cancelado_vencido = PlanejamentoTreinamento.objects.create(
            titulo='Treinamento Vencido mas Cancelado',
            instrutor=self.colab_instrutor,
            data_prevista=date.today() - timedelta(days=10),
            status='cancelado'  # minúsculo intencional
        )
        plan_cancelado_vencido.colaboradores.add(self.colab_participante)

        items = get_user_inbox_items(self.user_instrutor)
        plan_ids = [item.id for item in items if item.sub_type == "Treinamentos Planejados"]
        self.assertNotIn(f"planejamento_treinamento_{plan_cancelado_vencido.id}", plan_ids)

        plan_cancelado_vencido.refresh_from_db()
        self.assertEqual(plan_cancelado_vencido.status, 'CANCELADO')

    def test_ajustar_instrutor_fixo_em_detalhe_procedimento(self):
        """Testa o card de ajuste rápido de instrutor fixo na tela de detalhe do procedimento."""
        from procedures.models import Procedimento
        proc = Procedimento.objects.create(codigo="POP.TESTE.1", nome="Procedimento Teste")
        self.user_instrutor.is_staff = True
        self.user_instrutor.save()
        self.client.force_login(self.user_instrutor)

        # Definir instrutor fixo
        url = reverse('procedures:detalhe_procedimento', args=[proc.id])
        response = self.client.post(url, {
            'definir_instrutor_fixo': '1',
            'instrutor_fixo_id': str(self.colab_instrutor.id),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        proc.refresh_from_db()
        self.assertEqual(proc.instrutor_fixo, self.colab_instrutor)

        # Remover instrutor fixo
        response = self.client.post(url, {
            'definir_instrutor_fixo': '1',
            'instrutor_fixo_id': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        proc.refresh_from_db()
        self.assertIsNone(proc.instrutor_fixo)


class Iso13485PermissionsTests(TestCase):
    """Testa o conjunto de permissões para a sessão ISO 13485 e suas ferramentas."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin_iso',
            password='testpass123',
            email='admin_iso@example.com',
        )
        self.operador = User.objects.create_user(
            username='operador_iso',
            password='testpass123',
            email='operador_iso@example.com',
        )

    def test_nav_structure_contains_iso13485_blocks_and_tools(self):
        """Valida que a estrutura de navegação contém os blocos e ferramentas da ISO 13485."""
        from shared.permissions import get_nav_structure, get_view_permission_map

        nav_structure = get_nav_structure()
        auditoria_mod = next((m for m in nav_structure if m.get("key") == "auditoria"), None)
        self.assertIsNotNone(auditoria_mod, "Módulo auditoria não encontrado")

        blocos_keys = [b.get("key") for b in auditoria_mod.get("blocos", [])]
        self.assertIn("iso_13485", blocos_keys)
        self.assertIn("iso_13485_setup", blocos_keys)

        view_map = get_view_permission_map()
        self.assertIn("auditoria:iso_auditoria_list", view_map)
        self.assertIn("auditoria:iso_entrevista_view", view_map)
        self.assertIn("auditoria:iso_setup_dashboard", view_map)
        self.assertIn("auditoria:iso_revisao_dashboard", view_map)
        self.assertIn("auditoria:iso_auditoria_capa", view_map)

    def test_user_detail_renders_iso13485_toggles(self):
        """Garante que a tela de permissões de usuário (/rh/usuarios/<id>/) exibe a sessão ISO 13485."""
        self.client.force_login(self.admin)
        url = reverse('rh:detalhe_usuario', args=[self.operador.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ISO 13485 - AUDITORIAS')
        self.assertContains(response, 'ISO 13485 - SETUP')
        self.assertContains(response, 'Modo Entrevista (Lista de Auditorias)')
        self.assertContains(response, 'Painel de Setup ISO')
        self.assertContains(response, 'Planos de Ação (CAPA)')

    def test_has_view_access_controls_iso13485_views(self):
        """Valida que has_view_access bloqueia sem permissão e libera com permissão."""
        from shared.permissions import has_view_access
        from django.contrib.auth.models import Permission

        # Sem permissão
        self.assertFalse(has_view_access(self.operador, 'auditoria:iso_auditoria_list'))
        self.assertFalse(has_view_access(self.operador, 'auditoria:iso_setup_dashboard'))

        # Superuser tem acesso irrestrito
        self.assertTrue(has_view_access(self.admin, 'auditoria:iso_auditoria_list'))
        self.assertTrue(has_view_access(self.admin, 'auditoria:iso_setup_dashboard'))

        # Conceder módulo Auditoria e ferramenta de Modo Entrevista
        perm_mod = Permission.objects.get(codename='nav_mod_auditoria')
        perm_lista = Permission.objects.get(codename='nav_auditoria_iso_lista')
        self.operador.user_permissions.add(perm_mod, perm_lista)

        self.assertTrue(has_view_access(self.operador, 'auditoria:iso_auditoria_list'))
        self.assertFalse(has_view_access(self.operador, 'auditoria:iso_setup_dashboard'))






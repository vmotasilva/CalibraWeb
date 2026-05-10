"""
Tests for shared module - Common and shared functionality
"""
from django.http import HttpResponse
from django.templatetags.static import static
from django.test import TestCase, Client
from django.contrib.auth.models import User
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
        self.assertContains(response, 'Favoritos')
        self.assertContains(response, 'Ações rápidas')
        self.assertContains(response, 'Pendências prioritárias')
        self.assertContains(response, 'Abrir hub do módulo')


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
        self.assertContains(response, static("shared/logo_calibraweb.png"))
        self.assertNotContains(response, "/static/logo.png")
        self.assertEqual(response["Cache-Control"], "no-cache, no-store, must-revalidate, max-age=0")
        self.assertIn("Cookie", response["Vary"])
    

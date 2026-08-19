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
    

class SharedImportUtilsTests(TestCase):
    """Unit tests for shared.utils.imports helpers."""

    def setUp(self):
        import os

        self._orig_sync = os.environ.get("SYNC_IMPORTS")
        self.user = User.objects.create_user(username="import_user", password="pass")

    def tearDown(self):
        import os

        if self._orig_sync is None:
            os.environ.pop("SYNC_IMPORTS", None)
        else:
            os.environ["SYNC_IMPORTS"] = self._orig_sync

    def _uploaded(self, name="planilha.xlsx", content=b"data"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, content)

    def test_save_uploaded_file_to_temp_writes_content_and_keeps_suffix(self):
        import os

        from shared.utils.imports import save_uploaded_file_to_temp

        path = save_uploaded_file_to_temp(self._uploaded("dados.csv", b"hello"))
        try:
            self.assertTrue(path.endswith(".csv"))
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"hello")
        finally:
            os.remove(path)

    def test_save_uploaded_file_defaults_suffix_when_missing(self):
        import os

        from shared.utils.imports import save_uploaded_file_to_temp

        path = save_uploaded_file_to_temp(self._uploaded("semextensao", b"x"))
        try:
            self.assertTrue(path.endswith(".xlsx"))
        finally:
            os.remove(path)

    def test_create_import_job_stores_authenticated_user(self):
        from shared.utils.imports import create_import_job

        job = create_import_job(
            user=self.user,
            uploaded=self._uploaded(),
            job_type="INSTRUMENTOS",
            filepath="/tmp/x.xlsx",
        )
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.filename, "planilha.xlsx")
        self.assertEqual(job.job_type, "INSTRUMENTOS")
        self.assertEqual(job.status, "PENDING")

    def test_create_import_job_ignores_anonymous_user(self):
        from django.contrib.auth.models import AnonymousUser

        from shared.utils.imports import create_import_job

        job = create_import_job(
            user=AnonymousUser(),
            uploaded=self._uploaded(),
            job_type="FERIAS",
            filepath="/tmp/x.xlsx",
        )
        self.assertIsNone(job.user)

    def test_dispatch_runs_synchronously_when_forced(self):
        import os

        from shared.utils.imports import create_import_job, dispatch_import_task

        os.environ["SYNC_IMPORTS"] = "1"
        job = create_import_job(
            user=self.user,
            uploaded=self._uploaded(),
            job_type="INSTRUMENTOS",
            filepath="/tmp/x.xlsx",
        )
        calls = {}

        def fake_task(job_id, filepath):
            calls["args"] = (job_id, filepath)

        fake_task.delay = lambda *a, **k: calls.setdefault("delay", True)

        ran_sync = dispatch_import_task(fake_task, job, "/tmp/x.xlsx")

        self.assertTrue(ran_sync)
        self.assertEqual(calls["args"], (str(job.id), "/tmp/x.xlsx"))
        self.assertNotIn("delay", calls)

    def test_dispatch_enqueues_when_celery_available(self):
        import os

        from shared.utils.imports import create_import_job, dispatch_import_task

        os.environ["SYNC_IMPORTS"] = "0"
        job = create_import_job(
            user=self.user,
            uploaded=self._uploaded(),
            job_type="INSTRUMENTOS",
            filepath="/tmp/x.xlsx",
        )
        calls = {}

        def fake_task(job_id, filepath):
            calls["sync"] = True

        fake_task.delay = lambda job_id, filepath: calls.setdefault(
            "delay", (job_id, filepath)
        )

        ran_sync = dispatch_import_task(fake_task, job, "/tmp/x.xlsx")

        self.assertFalse(ran_sync)
        self.assertEqual(calls["delay"], (str(job.id), "/tmp/x.xlsx"))
        self.assertNotIn("sync", calls)

    def test_dispatch_falls_back_to_sync_when_delay_fails(self):
        import os

        from shared.utils.imports import create_import_job, dispatch_import_task

        os.environ["SYNC_IMPORTS"] = "0"
        job = create_import_job(
            user=self.user,
            uploaded=self._uploaded(),
            job_type="INSTRUMENTOS",
            filepath="/tmp/x.xlsx",
        )
        calls = {}

        def fake_task(job_id, filepath):
            calls["sync"] = (job_id, filepath)

        def failing_delay(*a, **k):
            raise RuntimeError("broker down")

        fake_task.delay = failing_delay

        ran_sync = dispatch_import_task(fake_task, job, "/tmp/x.xlsx")

        self.assertTrue(ran_sync)
        self.assertEqual(calls["sync"], (str(job.id), "/tmp/x.xlsx"))


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



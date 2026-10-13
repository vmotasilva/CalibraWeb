from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from shared.permissions import VIEW_NAME_TO_PERMISSION


class ModuleAccessMiddlewareTests(TestCase):
    view_name = "rh:api_delete_colaborador"

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("semperm", password="x")
        self.client.force_login(self.user)
        self.url = reverse(self.view_name, args=[999999])

    def test_view_esta_mapeada(self):
        self.assertIn(self.view_name, VIEW_NAME_TO_PERMISSION)

    @override_settings(PERMISSIONS_ENFORCEMENT="enforce")
    def test_enforce_bloqueia_sem_permissao(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 403)

    @override_settings(PERMISSIONS_ENFORCEMENT="log")
    def test_log_nao_bloqueia_mas_registra(self):
        with self.assertLogs("shared.access", level="WARNING"):
            self.client.post(self.url)

    @override_settings(PERMISSIONS_ENFORCEMENT="enforce")
    def test_enforce_libera_com_modulo_e_funcao(self):
        for codename in ("nav_mod_pessoas", "nav_pessoas_api_delete_colaborador"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label="core"))
        resp = self.client.post(self.url)
        self.assertNotEqual(resp.status_code, 403)  # passa o middleware (a view responde 400/404 ao id inexistente)
        self.assertNotEqual(resp.status_code, 302)

    @override_settings(PERMISSIONS_ENFORCEMENT="enforce")
    def test_superuser_passa(self):
        self.user.is_superuser = True
        self.user.save()
        resp = self.client.post(self.url)
        self.assertNotEqual(resp.status_code, 403)

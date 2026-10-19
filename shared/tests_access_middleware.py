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


def _reverse_any(view_name):
    """Monta uma URL para a view tentando de 0 a 4 argumentos posicionais (int, depois str)."""
    from django.urls import NoReverseMatch

    for sample in (1, "x"):
        for n in range(0, 5):
            try:
                return reverse(view_name, args=[sample] * n)
            except NoReverseMatch:
                continue
    return None


@override_settings(PERMISSIONS_ENFORCEMENT="enforce", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MappedViewsBlockedTests(TestCase):
    """Toda view mapeada em NAV_STRUCTURE deve negar acesso a quem não tem módulo/função."""

    def setUp(self):
        self.user = get_user_model().objects.create_user("semperm2", password="x")
        self.client.force_login(self.user)

    def test_usuario_sem_permissao_e_bloqueado_em_todas_as_views_mapeadas(self):
        urls = {vn: _reverse_any(vn) for vn in VIEW_NAME_TO_PERMISSION}
        resolvidas = {vn: u for vn, u in urls.items() if u}
        self.assertGreaterEqual(len(resolvidas), 0.8 * len(urls), "Muitas views não puderam ser resolvidas")

        liberadas = []
        for vn, url in resolvidas.items():
            if url.startswith(("/admin/", "/accounts/")):
                continue
            resp = self.client.get(url)
            bloqueada = resp.status_code == 403 or (resp.status_code == 302 and resp.url == "/")
            if not bloqueada:
                liberadas.append(f"{vn} -> {resp.status_code}")
        self.assertEqual(liberadas, [], "Views mapeadas acessíveis sem permissão")

    def test_modulo_e_funcao_liberam_cada_view_mapeada(self):
        from shared.middleware.module_access import ModuleAccessMiddleware

        from shared.permissions import _nav_module_config

        negadas = []
        user = get_user_model().objects.create_user("u_liberado", password="x")
        for vn, data in VIEW_NAME_TO_PERMISSION.items():
            cfg = _nav_module_config(data["module"])
            perms = [data["perm"], *data.get("grupos", [])] + ([cfg["module_perm"]] if cfg and cfg.get("module_perm") else [])
            user.user_permissions.set(
                [Permission.objects.get(content_type__app_label=f.split(".", 1)[0], codename=f.split(".", 1)[1]) for f in perms]
            )
            user = get_user_model().objects.get(pk=user.pk)  # descarta cache de permissões
            if ModuleAccessMiddleware._denial_reason(user, vn):
                negadas.append(vn)
        self.assertEqual(negadas, [], "Views negadas mesmo com módulo e função concedidos")


@override_settings(PERMISSIONS_ENFORCEMENT="enforce", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LandingPageTests(TestCase):
    """Páginas de entrada (hub/modulo) exigem só o módulo ('No menu')."""

    PAGINAS = {
        "auditoria:hub": "nav_mod_auditoria",
        "auditoria:modulo": "nav_mod_auditoria",
        "metrologia:hub": "nav_mod_metrologia",
        "rh:hub": "nav_mod_pessoas",
        "laboratorio:hub": "nav_mod_laboratorio",
        "procedures:hub": "nav_mod_treinamentos",
        "boards:hub": "nav_mod_boards",
    }

    def setUp(self):
        self.user = get_user_model().objects.create_user("landing", password="x")
        self.client.force_login(self.user)

    def test_sem_modulo_e_bloqueado(self):
        for vn in self.PAGINAS:
            resp = self.client.get(reverse(vn))
            self.assertEqual((resp.status_code, resp.url if resp.status_code == 302 else ""), (302, "/"), vn)

    def test_com_modulo_passa_pelo_middleware(self):
        for vn, codename in self.PAGINAS.items():
            self.user.user_permissions.set([Permission.objects.get(content_type__app_label="core", codename=codename)])
            self.user = get_user_model().objects.get(pk=self.user.pk)
            self.client.force_login(self.user)
            resp = self.client.get(reverse(vn))
            self.assertFalse(resp.status_code == 302 and resp.url == "/", vn)

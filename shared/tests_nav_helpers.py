from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings

from shared.permissions import is_admin_user, nav_permission_required, user_has_nav_perm

PERM = "core.nav_diagramas_editor"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class UserHasNavPermTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.perm = Permission.objects.get(content_type__app_label="core", codename="nav_diagramas_editor")

    def _user(self, name, **kw):
        return self.User.objects.create_user(name, password="x", **kw)

    def test_sem_permissao_nega(self):
        self.assertFalse(user_has_nav_perm(self._user("a"), PERM))

    def test_permissao_direta_libera(self):
        u = self._user("b")
        u.user_permissions.add(self.perm)
        self.assertTrue(user_has_nav_perm(self.User.objects.get(pk=u.pk), PERM))

    def test_permissao_por_grupo_nao_conta(self):
        u = self._user("c")
        g = Group.objects.create(name="g")
        g.permissions.add(self.perm)
        u.groups.add(g)
        self.assertFalse(user_has_nav_perm(self.User.objects.get(pk=u.pk), PERM))

    def test_staff_e_superuser_sao_admin(self):
        self.assertTrue(is_admin_user(self._user("d", is_staff=True)))
        self.assertTrue(user_has_nav_perm(self._user("e", is_superuser=True), PERM))
        self.assertTrue(user_has_nav_perm(self._user("f", is_staff=True), PERM))

    def test_decorator_levanta_403_sem_permissao(self):
        @nav_permission_required(PERM)
        def view(request):
            return "ok"

        req = RequestFactory().get("/")
        req.user = self._user("g")
        with self.assertRaises(PermissionDenied):
            view(req)
        req.user = self._user("h", is_staff=True)
        self.assertEqual(view(req), "ok")

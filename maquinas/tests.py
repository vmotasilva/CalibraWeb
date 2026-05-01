from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from laboratorio.models import OcorrenciaLaboratorio
from organization.models import Setor
from shared.permissions import VIEW_NAME_TO_PERMISSION, has_view_access
from shared.templatetags.nav_access import can_nav_block

from .models import CategoriaMaquina, Maquina


class MaquinasViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="maquinas_tester",
            password="senha-forte-123",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.setor = Setor.objects.create(nome="Producao")
        self.categoria = CategoriaMaquina.objects.create(nome="Bombas")

    def test_create_machine_flow(self):
        response = self.client.post(
            reverse("maquinas:maquina_create"),
            {
                "codigo": "MQ-001",
                "numero_serie": "SER-001",
                "fabricante": "Atlas Copco",
                "setor": self.setor.pk,
                "categoria": self.categoria.pk,
                "status": "on",
            },
        )

        self.assertRedirects(response, reverse("maquinas:maquinas_list"))
        self.assertTrue(
            Maquina.objects.filter(
                codigo="MQ-001",
                numero_serie="SER-001",
                fabricante="Atlas Copco",
                categoria=self.categoria,
                setor=self.setor,
            ).exists()
        )

    def test_list_filters_by_status(self):
        Maquina.objects.create(codigo="MQ-AT", fabricante="Misturador", categoria=self.categoria, status=True)
        Maquina.objects.create(codigo="MQ-IN", fabricante="Homogeneizador", categoria=self.categoria, status=False)

        response = self.client.get(reverse("maquinas:maquinas_list"), {"status": "inativas"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MQ-IN")
        self.assertNotContains(response, "MQ-AT")

    def test_category_list_shows_machine_count(self):
        Maquina.objects.create(nome="Agitador", codigo="MQ-002", categoria=self.categoria, status=True)

        response = self.client.get(reverse("maquinas:categorias_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bombas")
        self.assertContains(response, ">1<", html=False)

    def test_delete_machine_when_unused(self):
        maquina = Maquina.objects.create(nome="Seladora", codigo="MQ-003", categoria=self.categoria, status=True)

        response = self.client.post(reverse("maquinas:maquina_delete", args=[maquina.pk]))

        self.assertRedirects(response, reverse("maquinas:maquinas_list"))
        self.assertFalse(Maquina.objects.filter(pk=maquina.pk).exists())

    def test_delete_machine_is_blocked_when_linked_to_occurrence(self):
        maquina = Maquina.objects.create(nome="Envasadora", codigo="MQ-004", categoria=self.categoria, status=True)
        OcorrenciaLaboratorio.objects.create(
            assunto="Falha em linha",
            detalhamento="Parada da maquina durante a operacao.",
            maquina=maquina,
        )

        response = self.client.post(reverse("maquinas:maquina_delete", args=[maquina.pk]))

        self.assertRedirects(response, reverse("maquinas:maquinas_list"))
        self.assertTrue(Maquina.objects.filter(pk=maquina.pk).exists())

    def test_delete_machine_confirmation_page_renders(self):
        maquina = Maquina.objects.create(nome="Rotuladora", codigo="MQ-006", categoria=self.categoria, status=True)

        response = self.client.get(reverse("maquinas:maquina_delete", args=[maquina.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmar exclusao da maquina")
        self.assertContains(response, "MQ-006")
        self.assertContains(response, "Rotuladora")

    def test_delete_category_is_blocked_when_it_has_machines(self):
        Maquina.objects.create(nome="Dosadora", codigo="MQ-005", categoria=self.categoria, status=True)

        response = self.client.post(reverse("maquinas:categoria_delete", args=[self.categoria.pk]))

        self.assertRedirects(response, reverse("maquinas:categorias_list"))
        self.assertTrue(CategoriaMaquina.objects.filter(pk=self.categoria.pk).exists())

    def test_delete_category_confirmation_page_renders(self):
        Maquina.objects.create(nome="Esteira", codigo="MQ-007", categoria=self.categoria, status=True)

        response = self.client.get(reverse("maquinas:categoria_delete", args=[self.categoria.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmar exclusao da categoria")
        self.assertContains(response, "Esteira")

    def test_view_permission_map_includes_machine_routes(self):
        expected_permissions = {
            "maquinas:maquinas_list": "core.nav_laboratorio_maquinas_lista",
            "maquinas:maquina_create": "core.nav_laboratorio_maquina_create",
            "maquinas:maquina_update": "core.nav_laboratorio_maquina_update",
            "maquinas:maquina_delete": "core.nav_laboratorio_maquina_delete",
            "maquinas:categorias_list": "core.nav_laboratorio_maquinas_categorias",
            "maquinas:categoria_create": "core.nav_laboratorio_categoria_maquina_create",
            "maquinas:categoria_update": "core.nav_laboratorio_categoria_maquina_update",
            "maquinas:categoria_delete": "core.nav_laboratorio_categoria_maquina_delete",
        }

        for view_name, perm in expected_permissions.items():
            self.assertIn(view_name, VIEW_NAME_TO_PERMISSION)
            self.assertEqual(VIEW_NAME_TO_PERMISSION[view_name]["perm"], perm)
            self.assertEqual(VIEW_NAME_TO_PERMISSION[view_name]["module"], "laboratorio")

    def test_legacy_laboratorio_group_keeps_machine_category_create_visible(self):
        legacy_user = get_user_model().objects.create_user(
            username="maquinas_legado",
            password="senha-forte-123",
        )
        legacy_group, _ = Group.objects.get_or_create(name="Laboratorio")
        legacy_user.groups.add(legacy_group)
        legacy_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="core",
                codename="nav_laboratorio_categorias",
            )
        )

        self.client.force_login(legacy_user)

        response = self.client.get(reverse("maquinas:categorias_list"))

        self.assertTrue(can_nav_block(legacy_user, "laboratorio", "maquinas"))
        self.assertTrue(has_view_access(legacy_user, "maquinas:categoria_create"))
        self.assertEqual(response.status_code, 200)

    def test_laboratorio_module_flag_shows_machine_ctas_without_block_permission(self):
        module_user = get_user_model().objects.create_user(
            username="maquinas_modulo",
            password="senha-forte-123",
        )
        module_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="core",
                codename="nav_mod_laboratorio",
            )
        )

        self.client.force_login(module_user)

        response = self.client.get(reverse("maquinas:categorias_list"))
        maquinas_response = self.client.get(reverse("maquinas:maquinas_list"))

        self.assertTrue(can_nav_block(module_user, "laboratorio", "maquinas"))
        self.assertTrue(has_view_access(module_user, "maquinas:maquina_create"))
        self.assertTrue(has_view_access(module_user, "maquinas:categoria_create"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(maquinas_response.status_code, 200)
        self.assertContains(response, "Nova categoria")
        self.assertContains(response, "Editar")
        self.assertNotContains(response, "Sem acoes")
        self.assertContains(maquinas_response, "Nova maquina")

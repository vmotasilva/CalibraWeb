"""Testes da estrutura de permissões de navegação (1 bloco por tela) e da migration de dados."""
import json
import os
from collections import Counter
from importlib import import_module
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from core.models import NavigationPermission
from shared.permissions import NAV_STRUCTURE, has_view_access


PSEUDO_VIEW_NAMES = {"exibir_botoes_acoes"}  # usada só via can_nav_view em templates


def _all_url_names():
    names = set()

    def walk(patterns, ns=None):
        for p in patterns:
            if isinstance(p, URLResolver):
                new_ns = f"{ns}:{p.namespace}" if (ns and p.namespace) else (p.namespace or ns)
                walk(p.url_patterns, new_ns)
            elif isinstance(p, URLPattern) and p.name:
                names.add(f"{ns}:{p.name}" if ns else p.name)

    walk(get_resolver().url_patterns)
    return names


def _iter_perms():
    """Permissões core.* do NAV_STRUCTURE (as de outros apps, ex.: rh.pode_alterar_foto_colaborador, vivem nos seus models)."""
    for perm in _iter_all_perms():
        if str(perm).startswith("core."):
            yield perm


def _iter_all_perms():
    for modulo in NAV_STRUCTURE:
        if modulo.get("module_perm"):
            yield modulo["module_perm"]
        for bloco in modulo["blocos"]:
            if bloco.get("perm"):
                yield bloco["perm"]
            for func in bloco["funcoes"]:
                if func.get("perm"):
                    yield func["perm"]


def _perm(codename):
    return Permission.objects.get(content_type__app_label="core", codename=codename)


class NavStructureTests(TestCase):
    def test_todas_as_permissoes_estao_declaradas_no_model(self):
        declaradas = {f"core.{codename}" for codename, _ in NavigationPermission._meta.permissions}
        faltando = sorted(set(_iter_perms()) - declaradas)
        self.assertEqual(faltando, [], "Permissões usadas no NAV_STRUCTURE sem declaração em NavigationPermission")

    def test_permissoes_existem_no_banco(self):
        codenames = {p.split(".", 1)[1] for p in _iter_perms()}
        existentes = set(
            Permission.objects.filter(content_type__app_label="core", codename__in=codenames).values_list("codename", flat=True)
        )
        self.assertEqual(sorted(codenames - existentes), [])

    def test_permissoes_de_qualquer_app_existem_no_banco(self):
        """Inclui as que vivem nos models de outros apps (ex.: rh.pode_alterar_foto_colaborador): sem a linha em Permission
        o toggle da tela de usuários não consegue gravar (um segundo "class Meta" no model já escondeu uma delas)."""
        faltando = []
        for perm in set(_iter_all_perms()):
            app_label, codename = str(perm).split(".", 1)
            if not Permission.objects.filter(content_type__app_label=app_label, codename=codename).exists():
                faltando.append(perm)
        self.assertEqual(sorted(faltando), [])

    def test_nenhuma_permissao_repetida(self):
        # Bloco com a mesma permissão de uma função (ou duas funções com a mesma) impede desligar só uma delas no painel.
        repetidas = [p for p, n in Counter(_iter_perms()).items() if n > 1]
        self.assertEqual(repetidas, [])

    def test_view_names_existem_e_nao_se_repetem(self):
        urls = _all_url_names()
        vistas = Counter()
        for modulo in NAV_STRUCTURE:
            for bloco in modulo["blocos"]:
                for func in bloco["funcoes"]:
                    vn = func.get("view_name")
                    for v in (vn if isinstance(vn, (list, tuple)) else [vn] if vn else []):
                        vistas[v] += 1
        inexistentes = sorted(v for v in vistas if v not in urls and v not in PSEUDO_VIEW_NAMES)
        self.assertEqual(inexistentes, [])
        self.assertEqual([v for v, n in vistas.items() if n > 1], [])

    def test_blocos_especiais_sem_toggle_e_com_descricao(self):
        for modulo in NAV_STRUCTURE:
            for bloco in modulo["blocos"]:
                if bloco.get("especial"):
                    self.assertIsNone(bloco.get("perm"), bloco["nome"])
                    for func in bloco["funcoes"]:
                        self.assertTrue(func.get("descricao"), func["nome"])
                else:
                    self.assertTrue(bloco.get("perm"), f"{modulo['key']}/{bloco['key']} sem permissão de bloco")

    def test_permissao_global_de_botoes_nao_depende_do_modulo_usuarios(self):
        user = User.objects.create_user("botoes", password="x")
        self.assertFalse(has_view_access(user, "exibir_botoes_acoes"))
        user.user_permissions.add(_perm("nav_global_action_buttons"))
        user = User.objects.get(pk=user.pk)
        self.assertTrue(has_view_access(user, "exibir_botoes_acoes"))


class PainelPermissoesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin_perm", "a@a.com", "x")
        self.alvo = User.objects.create_user("alvo_perm", password="x")
        self.client.force_login(self.admin)

    def _salvar(self, codenames):
        return self.client.post(
            reverse("rh:api_atualizar_permissoes_lote"),
            data=json.dumps({"user_id": self.alvo.pk, "permissoes": {"core": codenames}}),
            content_type="application/json",
        )

    def _codenames(self):
        return set(self.alvo.user_permissions.values_list("codename", flat=True))

    def test_permissao_de_foto_do_colaborador_e_salva_e_volta_marcada(self):
        resp = self.client.post(
            reverse("rh:api_atualizar_permissoes_lote"),
            data=json.dumps({"user_id": self.alvo.pk, "permissoes": {"core": [], "rh": ["pode_alterar_foto_colaborador"]}}),
            content_type="application/json",
        )
        self.assertEqual(resp.json()["success"], True)
        self.assertIn("pode_alterar_foto_colaborador", self._codenames())
        html = self.client.get(reverse("rh:detalhe_usuario", args=[self.alvo.pk])).content.decode("utf-8")
        i = html.index('id="perm_rh_pode_alterar_foto_colaborador"')
        self.assertIn("checked", html[i:html.index(">", i)])

    def test_especiais_salvam_sem_toggle_de_bloco_e_globais_sem_modulo(self):
        resp = self._salvar(["nav_mod_pessoas", "nav_pessoas_ver_salario", "nav_pessoas_ver_todos_colaboradores"])
        self.assertEqual(resp.status_code, 200)
        self.assertTrue({"nav_pessoas_ver_salario", "nav_pessoas_ver_todos_colaboradores"} <= self._codenames())

    def test_especial_do_modulo_e_descartada_sem_o_modulo(self):
        self._salvar(["nav_pessoas_ver_salario"])
        self.assertNotIn("nav_pessoas_ver_salario", self._codenames())

    def test_funcao_exige_bloco_da_tela(self):
        self._salvar(["nav_mod_metrologia", "nav_metrologia_templates_etiquetas"])
        self.assertNotIn("nav_metrologia_templates_etiquetas", self._codenames())
        self._salvar(["nav_mod_metrologia", "nav_metrologia_etiquetas_bloco", "nav_metrologia_templates_etiquetas"])
        self.assertIn("nav_metrologia_templates_etiquetas", self._codenames())

    def test_detalhe_do_usuario_renderiza_secoes_especiais_e_global(self):
        resp = self.client.get(reverse("rh:detalhe_usuario", args=[self.alvo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Permissões Globais")
        self.assertContains(resp, "PERMISSÕES ESPECIAIS")
        self.assertContains(resp, "Conceder")


class PermissoesEspeciaisTests(TestCase):
    def test_encerrar_ocorrencia_de_outro_usuario(self):
        from laboratorio.views import _can_user_close_occurrence

        class Ocorrencia:
            criado_por_id = -1

        user = User.objects.create_user("lab", password="x")
        self.assertFalse(_can_user_close_occurrence(user, Ocorrencia()))
        user.user_permissions.add(_perm("nav_laboratorio_encerrar_qualquer_ocorrencia"))
        self.assertTrue(_can_user_close_occurrence(User.objects.get(pk=user.pk), Ocorrencia()))

    def test_gerenciar_todos_os_quadros(self):
        from boards.views import _is_board_admin

        user = User.objects.create_user("quadros", password="x")
        self.assertFalse(_is_board_admin(user))
        user.user_permissions.add(_perm("nav_boards_gerenciar_todos"))
        self.assertTrue(_is_board_admin(User.objects.get(pk=user.pk)))

    def test_admin_de_auditoria_nao_vem_mais_de_ver_todos_colaboradores(self):
        from auditoria.views import _auditoria_is_admin

        user = User.objects.create_user("aud", password="x")
        user.user_permissions.add(_perm("nav_pessoas_ver_todos_colaboradores"))
        self.assertFalse(_auditoria_is_admin(User.objects.get(pk=user.pk)))
        user.user_permissions.add(_perm("nav_auditoria_admin"))
        self.assertTrue(_auditoria_is_admin(User.objects.get(pk=user.pk)))


class TriggerMigrateProtecaoTests(TestCase):
    url = "/api/migrate/"

    def test_get_nao_permitido(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_sem_token_configurado_nega(self):
        with mock.patch.dict(os.environ, {"MIGRATE_SECRET": "", "CRON_SECRET": ""}):
            resp = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer ")
        self.assertEqual(resp.status_code, 403)

    def test_token_errado_nega(self):
        with mock.patch.dict(os.environ, {"MIGRATE_SECRET": "certo"}):
            resp = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer errado")
        self.assertEqual(resp.status_code, 403)

    def test_token_correto_executa(self):
        with mock.patch.dict(os.environ, {"MIGRATE_SECRET": "certo"}), mock.patch(
            "django.core.management.call_command"
        ) as call_command:
            resp = self.client.post(self.url, HTTP_AUTHORIZATION="Bearer certo")
        self.assertEqual(resp.status_code, 200)
        call_command.assert_called_once()


class MigracaoPermissoesPorTelaTests(TestCase):
    """Aplica a 0029 sobre usuários com as permissões antigas e confere a preservação dos acessos.

    Os testes rodam com migrations desativadas (settings_test), então a função `forwards`
    é chamada diretamente com o registro de apps real.
    """

    def setUp(self):
        ct, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")

        def perm(codename):
            return Permission.objects.get_or_create(content_type=ct, codename=codename, defaults={"name": codename})[0]

        self.antigo = User.objects.create_user("usuario_antigo", password="x")
        self.antigo.user_permissions.add(
            perm("nav_mod_metrologia"),
            perm("nav_metrologia_export_etiquetas"),  # antes também era a permissão do bloco "Modelos de Etiquetas"
            perm("nav_mod_treinamentos"),
            perm("nav_treinamentos_gestao"),
            perm("nav_treinamentos_registros"),  # antes cobria Avaliação de Eficácia
            perm("nav_laboratorio_coating_painel"),  # antes cobria editar e excluir lançamentos
            perm("nav_pessoas_ver_todos_colaboradores"),  # antes dava admin de Auditoria
            perm("nav_acoes_plano"),  # órfã
        )
        self.sem_nada = User.objects.create_user("usuario_sem_nada", password="x")
        perm("nav_metrologia_importacao")

        migration = import_module("core.migrations.0029_nav_permissoes_por_tela_dados")
        migration.forwards(django_apps, None)

    def _codenames(self, user):
        return set(User.objects.get(pk=user.pk).user_permissions.values_list("codename", flat=True))

    def test_preserva_acessos_e_concede_blocos(self):
        perms = self._codenames(self.antigo)
        esperadas = {
            "nav_metrologia_templates_etiquetas",
            "nav_metrologia_template_etiqueta_upload",
            "nav_metrologia_etiquetas_bloco",
            "nav_treinamentos_eficacia",
            "nav_treinamentos_eficacia_registrar",
            "nav_treinamentos_eficacia_registrar_massa",
            "nav_treinamentos_eficacia_bloco",
            "nav_laboratorio_coating_painel_editar",
            "nav_laboratorio_coating_registro_delete",
            "nav_laboratorio_coating",
            "nav_auditoria_admin",
        }
        self.assertTrue(esperadas <= perms, sorted(esperadas - perms))

    def test_nao_concede_permissoes_especiais_sem_origem(self):
        perms = self._codenames(self.antigo)
        for codename in ("nav_treinamentos_validar_matriz", "nav_boards_gerenciar_todos", "nav_pessoas_perfil_rh"):
            self.assertNotIn(codename, perms)
        self.assertEqual(self._codenames(self.sem_nada), set())

    def test_remove_permissoes_orfas(self):
        self.assertFalse(Permission.objects.filter(codename="nav_acoes_plano").exists())
        self.assertFalse(Permission.objects.filter(codename="nav_metrologia_importacao").exists())
        self.assertNotIn("nav_acoes_plano", self._codenames(self.antigo))


class FlagsDeGrupoTests(TestCase):
    """Todo card (seção/subseção do menu) tem flag "No menu"; desligada, bloqueia tudo o que está dentro."""

    def test_flags_de_grupo_existem_no_banco_e_no_model(self):
        from shared.permissions import NAV_GROUP_PERMS

        declaradas = {f"core.{codename}" for codename, _ in NavigationPermission._meta.permissions}
        self.assertEqual(sorted(set(NAV_GROUP_PERMS.values()) - declaradas), [])
        for perm in NAV_GROUP_PERMS.values():
            self.assertTrue(Permission.objects.filter(content_type__app_label="core", codename=perm.split(".", 1)[1]).exists(), perm)

    def test_todo_grupo_do_painel_tem_flag(self):
        from shared.permissions import NAV_GROUP_PERMS

        caminhos = set()
        for modulo in NAV_STRUCTURE:
            for bloco in modulo["blocos"]:
                partes = [p.strip() for p in (bloco.get("grupo") or "").split(">") if p.strip()]
                caminhos.update(" > ".join(partes[: i + 1]) for i in range(len(partes)))
        self.assertEqual(sorted(c for c in caminhos if c not in NAV_GROUP_PERMS), [])

    def test_homologacoes_exigem_gestao_qualidade_e_homologacoes(self):
        user = User.objects.create_user("homolog", password="x")
        base = ["nav_mod_laboratorio", "nav_laboratorio_homologacoes_bloco", "nav_laboratorio_homologacoes"]
        user.user_permissions.add(*[_perm(c) for c in base])
        self.assertFalse(has_view_access(User.objects.get(pk=user.pk), "laboratorio:homologacoes_resumo"))
        for grupo in ("nav_mod_gestao", "nav_gestao_qualidade"):
            user.user_permissions.add(_perm(grupo))
            self.assertFalse(has_view_access(User.objects.get(pk=user.pk), "laboratorio:homologacoes_resumo"), grupo)
        user.user_permissions.add(_perm("nav_gestao_homologacoes"))
        self.assertTrue(has_view_access(User.objects.get(pk=user.pk), "laboratorio:homologacoes_resumo"))

    def test_tag_can_nav_group(self):
        from shared.templatetags.nav_access import can_nav_group

        user = User.objects.create_user("tag", password="x")
        self.assertFalse(can_nav_group(user, "Qualidade"))
        user.user_permissions.add(_perm("nav_gestao_qualidade"))
        self.assertTrue(can_nav_group(User.objects.get(pk=user.pk), "Qualidade"))
        self.assertTrue(can_nav_group(User.objects.create_superuser("su", "s@s.com", "x"), "Qualidade"))

    def test_painel_salva_grupo_como_mestre_dos_filhos(self):
        admin = User.objects.create_superuser("admin_grp", "a@a.com", "x")
        alvo = User.objects.create_user("alvo_grp", password="x")
        self.client.force_login(admin)

        def salvar(codenames):
            self.client.post(
                reverse("rh:api_atualizar_permissoes_lote"),
                data=json.dumps({"user_id": alvo.pk, "permissoes": {"core": codenames}}),
                content_type="application/json",
            )
            return set(alvo.user_permissions.values_list("codename", flat=True))

        itens = ["nav_mod_laboratorio", "nav_laboratorio_homologacoes_bloco", "nav_laboratorio_homologacoes"]
        self.assertEqual(salvar(itens), {"nav_mod_laboratorio"})
        completo = itens + ["nav_mod_gestao", "nav_gestao_qualidade", "nav_gestao_homologacoes"]
        self.assertEqual(salvar(completo), set(completo))
        # Desligar o grupo intermediário derruba tudo que está abaixo dele
        sem_qualidade = [c for c in completo if c != "nav_gestao_qualidade"]
        self.assertEqual(salvar(sem_qualidade), {"nav_mod_laboratorio", "nav_mod_gestao"})

    def test_painel_exibe_flag_em_todos_os_cards_de_grupo(self):
        admin = User.objects.create_superuser("admin_card", "a@a.com", "x")
        alvo = User.objects.create_user("alvo_card", password="x")
        self.client.force_login(admin)
        html = self.client.get(reverse("rh:detalhe_usuario", args=[alvo.pk])).content.decode("utf-8")
        from shared.permissions import NAV_GROUP_PERMS

        for perm in NAV_GROUP_PERMS.values():
            self.assertIn(f'id="perm_core_{perm.split(".", 1)[1]}"', html, perm)

    def test_migration_concede_flag_a_quem_ja_tinha_itens_do_grupo(self):
        ct, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")
        antigo = User.objects.create_user("antigo_grp", password="x")
        antigo.user_permissions.add(_perm("nav_laboratorio_tms_dashboard"), _perm("nav_laboratorio_coating_painel"))
        vazio = User.objects.create_user("vazio_grp", password="x")
        import_module("core.migrations.0037_nav_grupos_flag").forwards(django_apps, None)
        perms = set(User.objects.get(pk=antigo.pk).user_permissions.values_list("codename", flat=True))
        esperadas = {
            "nav_mod_gestao", "nav_gestao_ferramentas", "nav_gestao_tms",
            "nav_laboratorio_grupo_hmc", "nav_laboratorio_grupo_hmc_ar",
        }
        self.assertTrue(esperadas <= perms, sorted(esperadas - perms))
        self.assertNotIn("nav_gestao_qualidade", perms)
        self.assertEqual(set(User.objects.get(pk=vazio.pk).user_permissions.values_list("codename", flat=True)), set())

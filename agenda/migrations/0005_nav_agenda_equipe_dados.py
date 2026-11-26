"""Libera o painel Equipe (vistoria) da Agenda para a chefia que já usa a Agenda.

Concede `nav_agenda_equipe_bloco` e `nav_agenda_equipe` aos usuários ativos que:
- têm "Módulo Agenda" (core.nav_mod_agenda) atribuído direto; e
- são Líder, Vice-Líder, Supervisor ou Gerente de ao menos um colaborador ativo (vínculos do cadastro de pessoas).

Quem não é chefia não recebe (a tela ficaria vazia). Grupos são ignorados pelo sistema
(ver shared.permissions._user_has_nav_perm).

Os nomes abaixo são um retrato congelado da data da migration (não importar shared.permissions aqui).
"""
from django.db import migrations
from django.db.models import Q

PERM_NAMES = {
    "nav_agenda_equipe_bloco": "NAV: Agenda / Bloco Equipe (Vistoria dos Liderados)",
    "nav_agenda_equipe": "NAV: Agenda / Acessar Equipe",
}
REQUISITO = "nav_mod_agenda"


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")
    Colaborador = apps.get_model("rh", "Colaborador")

    content_type, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")
    novas = [
        Permission.objects.update_or_create(content_type=content_type, codename=codename, defaults={"name": name})[0]
        for codename, name in PERM_NAMES.items()
    ]
    chefes = set()
    for campo in ("lider", "vice_lider", "supervisor", "gerente"):
        chefes |= set(
            Colaborador.objects.filter(is_active=True, **{f"{campo}__isnull": False}).values_list(f"{campo}_id", flat=True)
        )
    ids_usuarios = set(
        Colaborador.objects.filter(pk__in=chefes, user_django__isnull=False).values_list("user_django_id", flat=True)
    )
    com_agenda = User.objects.filter(
        pk__in=ids_usuarios,
        is_active=True,
        user_permissions__content_type=content_type,
        user_permissions__codename=REQUISITO,
    ).distinct()
    for user in com_agenda:
        user.user_permissions.add(*novas)


def backwards(apps, schema_editor):
    """Não desfaz: as permissões podem ter sido concedidas manualmente depois."""


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0004_hierarquia"),
        ("core", "0076_hierarquia"),
        ("rh", "0038_alocacao_posto"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]

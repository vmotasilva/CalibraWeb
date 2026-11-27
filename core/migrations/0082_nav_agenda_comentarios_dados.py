"""Libera comentários e ocorrências do Meu checklist para quem já usa a Agenda.

Concede `nav_agenda_comentarios` e `nav_agenda_ocorrencia` aos usuários ativos que têm "Módulo Agenda" (core.nav_mod_agenda) atribuído direto.
Grupos são ignorados pelo sistema (ver shared.permissions._user_has_nav_perm).

Os nomes abaixo são um retrato congelado da data da migration (não importar shared.permissions aqui).
"""
from django.db import migrations

PERM_NAMES = {
    "nav_agenda_comentarios": "NAV: Agenda / Comentar Itens do Meu Checklist",
    "nav_agenda_ocorrencia": "NAV: Agenda / Abrir Ocorrência a partir do Meu Checklist",
}
REQUISITO = "nav_mod_agenda"


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")

    content_type, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")
    novas = [
        Permission.objects.update_or_create(content_type=content_type, codename=codename, defaults={"name": name})[0]
        for codename, name in PERM_NAMES.items()
    ]
    com_agenda = User.objects.filter(
        is_active=True, user_permissions__content_type=content_type, user_permissions__codename=REQUISITO
    ).distinct()
    for user in com_agenda:
        user.user_permissions.add(*novas)


def backwards(apps, schema_editor):
    """Não desfaz: as permissões podem ter sido concedidas manualmente depois."""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0081_comentarios_ocorrencia"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]

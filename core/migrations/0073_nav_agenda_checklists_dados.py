"""Libera os Checklists (modelos) da Agenda para quem já usa a Agenda.

Concede as novas permissões de uso aos usuários ativos que têm "Módulo Agenda" (core.nav_mod_agenda)
atribuído direto. Grupos são ignorados pelo sistema (ver shared.permissions._user_has_nav_perm).
A permissão especial "Criar Eventos na Agenda Comum" não é tocada.

Os nomes abaixo são um retrato congelado da data da migration (não importar shared.permissions aqui).
"""
from django.db import migrations

PERM_NAMES = {
    "nav_agenda_item_toggle": "NAV: Agenda / Marcar Item de Checklist Associado",
    "nav_agenda_modelos_bloco": "NAV: Agenda / Bloco Meus Checklists (Modelos)",
    "nav_agenda_modelos_listar": "NAV: Agenda / Acessar Meus Checklists",
    "nav_agenda_modelo_detalhe": "NAV: Agenda / Detalhe do Checklist",
    "nav_agenda_modelo_salvar": "NAV: Agenda / Criar e Editar Checklist",
    "nav_agenda_modelo_excluir": "NAV: Agenda / Excluir Checklist",
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
        ("core", "0072_checklists"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]

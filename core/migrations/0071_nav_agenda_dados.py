"""Libera a Agenda para quem já usa Quadros.

Concede as permissões de uso da Agenda (módulo, blocos e funções) aos usuários ativos que têm
"Módulo Quadros" (core.nav_mod_boards) atribuído direto. A permissão especial "Criar Eventos na Agenda
Comum" NÃO é concedida: continua sendo liberada à parte no painel de permissões.

Permissões core.nav_* só valem quando atribuídas direto ao usuário (grupos são ignorados pelo sistema,
ver shared.permissions._user_has_nav_perm); por isso grupos não são tocados.

Os nomes abaixo são um retrato congelado da data da migration (não importar shared.permissions aqui).
"""
from django.db import migrations

PERM_NAMES = {
    "nav_mod_agenda": "NAV: Módulo Agenda",
    "nav_agenda_calendario_bloco": "NAV: Agenda / Bloco Calendário",
    "nav_agenda_calendario": "NAV: Agenda / Acessar Calendário",
    "nav_agenda_eventos_listar": "NAV: Agenda / Listar Eventos (API do calendário)",
    "nav_agenda_evento_detalhe": "NAV: Agenda / Detalhe do Evento",
    "nav_agenda_evento_salvar": "NAV: Agenda / Criar e Editar Evento",
    "nav_agenda_evento_excluir": "NAV: Agenda / Excluir Evento",
    "nav_agenda_convite": "NAV: Agenda / Responder Convite",
    "nav_agenda_checklist_bloco": "NAV: Agenda / Bloco Checklist Diário",
    "nav_agenda_checklist": "NAV: Agenda / Acessar Checklist do Dia",
    "nav_agenda_checklist_toggle": "NAV: Agenda / Marcar Item do Checklist",
}
REQUISITO = "nav_mod_boards"


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")

    content_type, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")
    novas = [
        Permission.objects.update_or_create(content_type=content_type, codename=codename, defaults={"name": name})[0]
        for codename, name in PERM_NAMES.items()
    ]
    com_quadros = User.objects.filter(
        is_active=True, user_permissions__content_type=content_type, user_permissions__codename=REQUISITO
    ).distinct()
    for user in com_quadros:
        user.user_permissions.add(*novas)


def backwards(apps, schema_editor):
    """Não desfaz: as permissões podem ter sido concedidas manualmente depois."""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0070_nav_agenda"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]

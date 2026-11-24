"""Auditoria Livre passa a ter seção própria no menu, com permissões próprias.

Até aqui as telas da Auditoria Livre dependiam da permissão "ISO 13485 - Modo Entrevista (Lista)" e da
seção "ISO 13485". Esta migration cria as permissões novas e as concede a quem já conseguia usar a
Auditoria Livre, para ninguém perder acesso.

Permissões core.nav_* só valem quando atribuídas direto ao usuário (grupos são ignorados pelo sistema,
ver shared.permissions._user_has_nav_perm). Por isso só usuários com as duas permissões antigas atribuídas
direto recebem as novas; grupos não são tocados.

Os nomes abaixo são um retrato congelado da data da migration (não importar shared.permissions aqui).
"""
from django.db import migrations

PERM_NAMES = {
    "nav_auditoria_livre_grupo": "NAV: Auditoria / Seção Auditoria Livre",
    "nav_auditoria_livre_bloco": "NAV: Auditoria / Bloco Auditoria Livre",
    "nav_auditoria_livre_lista": "NAV: Auditoria / Auditoria Livre - Lista de Auditorias",
    "nav_auditoria_livre_gerenciar": "NAV: Auditoria / Auditoria Livre - Criar, Editar, Arquivar e Excluir",
    "nav_auditoria_livre_conducao": "NAV: Auditoria / Auditoria Livre - Condução (Solicitações, Itens e Fotos)",
    "nav_auditoria_livre_capa": "NAV: Auditoria / Auditoria Livre - Plano de Ação (CAPA)",
    "nav_auditoria_livre_export": "NAV: Auditoria / Auditoria Livre - Exportar (Excel e Word)",
}
# Quem tinha estas duas conseguia abrir a Auditoria Livre.
REQUISITOS_ANTIGOS = {"nav_auditoria_iso_lista", "nav_auditoria_iso_grupo"}


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")

    content_type, _ = ContentType.objects.get_or_create(app_label="core", model="navigationpermission")
    novas = []
    for codename, name in PERM_NAMES.items():
        perm, _ = Permission.objects.update_or_create(
            content_type=content_type, codename=codename, defaults={"name": name}
        )
        novas.append(perm)

    for user in User.objects.filter(is_active=True):
        diretas = set(
            user.user_permissions.filter(content_type__app_label="core").values_list("codename", flat=True)
        )
        if REQUISITOS_ANTIGOS <= diretas:
            user.user_permissions.add(*novas)


def backwards(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(content_type__app_label="core", codename__in=list(PERM_NAMES)).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0068_nav_auditoria_livre"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]

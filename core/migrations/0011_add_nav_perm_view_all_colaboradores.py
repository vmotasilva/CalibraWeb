from django.db import migrations


CODENAME = 'nav_pessoas_ver_todos_colaboradores'
PERM_NAME = 'NAV: Pessoas / Permissão Especial: Ver Todos os Colaboradores'


def create_special_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    content_type, _ = ContentType.objects.get_or_create(
        app_label='core',
        model='navigationpermission',
    )

    Permission.objects.update_or_create(
        content_type=content_type,
        codename=CODENAME,
        defaults={'name': PERM_NAME},
    )


def remove_special_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    Permission.objects.filter(
        content_type__app_label='core',
        codename=CODENAME,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_navigationpermission_options'),
    ]

    operations = [
        migrations.RunPython(create_special_permission, remove_special_permission),
    ]

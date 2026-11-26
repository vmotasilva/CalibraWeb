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
        # Permission.name só passa a caber 255 caracteres na auth.0002; sem esta dependência, num banco novo
        # (PostgreSQL) esta migration podia rodar antes e falhar com "value too long for type character varying(50)".
        ('auth', '0002_alter_permission_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_special_permission, remove_special_permission),
    ]

from django.db import migrations


CODENAME = 'nav_metrologia_ocorrencias_relatorio'
PERM_NAME = 'NAV: Metrologia / Relatório de Ocorrências e Tratativas'


def create_permission(apps, schema_editor):
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


def remove_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    Permission.objects.filter(
        content_type__app_label='core',
        codename=CODENAME,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_alter_navigationpermission_options'),
    ]

    operations = [
        migrations.RunPython(create_permission, remove_permission),
    ]

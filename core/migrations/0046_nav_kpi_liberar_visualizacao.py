from django.db import migrations

# Só visualização do KPI: seção Gestão > KPI (e o módulo Gestão, pai dela), bloco do painel e "Ver Painel".
FLAGS = {
    'nav_mod_gestao': 'NAV: Gestão (módulo de exibição) / No menu',
    'nav_gestao_kpi': 'NAV: Gestão / Seção KPI',
    'nav_kpi_bloco_painel': 'NAV: KPI / Bloco Painel de Indicadores',
    'nav_kpi_painel': 'NAV: KPI / Ver Painel de Indicadores',
}


def forwards(apps, schema_editor):
    """O KPI era aberto a todos antes de ganhar permissões: mantém a visualização para os usuários ativos, sem edição."""
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    User = apps.get_model('auth', 'User')

    ct, _ = ContentType.objects.get_or_create(app_label='core', model='navigationpermission')
    perms = [Permission.objects.get_or_create(content_type=ct, codename=c, defaults={'name': n[:255]})[0] for c, n in FLAGS.items()]
    Through = User.user_permissions.through
    Through.objects.bulk_create(
        [Through(user_id=u, permission_id=p.pk) for u in User.objects.filter(is_active=True).values_list('pk', flat=True) for p in perms],
        ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_nav_kpi'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

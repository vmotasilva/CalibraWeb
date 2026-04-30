# Generated migration to remove periodo_aquisitivo fields from Ferias

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0012_alter_ferias_status"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ferias",
            name="periodo_aquisitivo_fim",
        ),
        migrations.RemoveField(
            model_name="ferias",
            name="periodo_aquisitivo_inicio",
        ),
    ]

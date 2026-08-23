# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0066_convert_unidade_auditor_lider_to_charfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditoriaiso',
            name='responsavel_qms',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Representante QMS'),
        ),
    ]

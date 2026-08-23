# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0067_auditoriaiso_responsavel_qms'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditoriaiso',
            name='municipio',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Município / Estado'),
        ),
    ]

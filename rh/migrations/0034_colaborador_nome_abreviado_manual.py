# Generated manually: Nome Abreviado do colaborador (usado nos diagramas)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0033_alter_colaborador_foto'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='nome_abreviado_manual',
            field=models.CharField(
                blank=True, default='', help_text='Versão curta do nome, usada nos diagramas. Em branco: primeiro e último nome.',
                max_length=60, verbose_name='Nome Abreviado',
            ),
        ),
    ]

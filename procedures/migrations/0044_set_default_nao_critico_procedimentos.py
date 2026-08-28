# Generated manually for Procedimento default and data migration of criticidade

from django.db import migrations, models


def set_default_nao_critico(apps, schema_editor):
    Procedimento = apps.get_model('procedures', 'Procedimento')
    # Atualiza todos os procedimentos que não são CRITICO para NAO_CRITICO
    Procedimento.objects.exclude(criticidade='CRITICO').update(criticidade='NAO_CRITICO')


def reverse_nao_critico(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('procedures', '0043_perguntaavaliacao_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='procedimento',
            name='criticidade',
            field=models.CharField(
                blank=True,
                choices=[('CRITICO', 'Crítico'), ('NAO_CRITICO', 'Não Crítico')],
                default='NAO_CRITICO',
                help_text='Nível de criticidade do procedimento',
                max_length=20,
                null=True,
                verbose_name='Criticidade'
            ),
        ),
        migrations.RunPython(set_default_nao_critico, reverse_nao_critico),
    ]

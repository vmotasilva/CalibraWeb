from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0025_kpi_hierarquico'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelocolagem',
            name='padrao',
            field=models.BooleanField(default=False, help_text='Vem selecionado na tela de colagem.', verbose_name='Modelo padrão'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0033_hier_importacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='hieritem',
            name='exibir_un_kg',
            field=models.BooleanField(default=False, help_text='Só na exibição: 1.000 kg aparece como 1,00 UN (kg). Vale para itens em kg; consumo e meta continuam em kg.', verbose_name='Exibir kg como UN (kg)'),
        ),
    ]

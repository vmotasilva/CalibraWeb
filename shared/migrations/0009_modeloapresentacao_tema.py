from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0008_modeloapresentacao_slides'),
    ]

    operations = [
        migrations.AddField(
            model_name='modeloapresentacao',
            name='tema',
            field=models.CharField(choices=[('escuro', 'Escuro'), ('claro', 'Claro')], default='escuro', max_length=10, verbose_name='Tema dos slides'),
        ),
    ]

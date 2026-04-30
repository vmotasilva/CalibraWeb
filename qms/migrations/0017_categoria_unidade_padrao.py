from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('qms', '0016_create_importjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoriainstrumento',
            name='unidade_padrao',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to='qms.unidademedida', verbose_name='Unidade Padrão'),
        ),
    ]

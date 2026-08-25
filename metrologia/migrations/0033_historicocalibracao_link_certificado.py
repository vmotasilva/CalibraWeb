# Generated manually for link_certificado field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('metrologia', '0032_categoriainstrumento_acao'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicocalibracao',
            name='link_certificado',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='Link Externo do Certificado'),
        ),
    ]

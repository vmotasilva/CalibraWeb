from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0060_pontoforteauditoriaiso"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditoriaiso",
            name="empresa_auditada",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Empresa / Laboratório Auditado",
            ),
        ),
        migrations.AddField(
            model_name="auditoriaiso",
            name="escopo",
            field=models.CharField(
                blank=True,
                default="Fabricação de Lentes Oftálmicas",
                max_length=500,
                verbose_name="Escopo da Auditoria",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0062_norma_template_uploads"),
    ]

    operations = [
        migrations.AddField(
            model_name="norma",
            name="template_docx_base64",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Conteúdo Base64 Template DOCX",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_xlsx_base64",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Conteúdo Base64 Template XLSX",
            ),
        ),
    ]

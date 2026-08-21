from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0061_auditoriaiso_empresa_auditada_escopo"),
    ]

    operations = [
        migrations.AddField(
            model_name="norma",
            name="template_docx",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="auditoria/templates_norma/docx/",
                verbose_name="Template de Relatório Executivo (.docx)",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_docx_atualizado_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Data de Atualização do DOCX",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_docx_nome_original",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Nome Original do DOCX",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_xlsx",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="auditoria/templates_norma/xlsx/",
                verbose_name="Template de Checklist (.xlsx)",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_xlsx_atualizado_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Data de Atualização do XLSX",
            ),
        ),
        migrations.AddField(
            model_name="norma",
            name="template_xlsx_nome_original",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Nome Original do XLSX",
            ),
        ),
    ]

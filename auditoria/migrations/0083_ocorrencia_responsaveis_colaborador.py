from django.db import migrations, models


def copiar_usuarios_para_colaboradores(apps, schema_editor):
    Comentario = apps.get_model("auditoria", "ComentarioRespostaAuditoria")
    Colaborador = apps.get_model("rh", "Colaborador")
    for oc in Comentario.objects.filter(responsaveis__isnull=False).distinct():
        colabs = Colaborador.objects.filter(user_django__in=oc.responsaveis.all())
        oc.responsaveis_colab.set(colabs)


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0082_ocorrencia_acao"),
        ("rh", "0035_colaborador_permissao_foto"),
    ]

    operations = [
        migrations.AddField(
            model_name="comentariorespostaauditoria",
            name="responsaveis_colab",
            field=models.ManyToManyField(
                blank=True,
                related_name="auditoria_ocorrencias_responsavel_tmp",
                to="rh.colaborador",
                verbose_name="Responsáveis pela tratativa",
            ),
        ),
        migrations.RunPython(copiar_usuarios_para_colaboradores, migrations.RunPython.noop),
        migrations.RemoveField(model_name="comentariorespostaauditoria", name="responsaveis"),
        migrations.RenameField(
            model_name="comentariorespostaauditoria",
            old_name="responsaveis_colab",
            new_name="responsaveis",
        ),
        migrations.AlterField(
            model_name="comentariorespostaauditoria",
            name="responsaveis",
            field=models.ManyToManyField(
                blank=True,
                related_name="auditoria_ocorrencias_responsavel",
                to="rh.colaborador",
                verbose_name="Responsáveis pela tratativa",
            ),
        ),
    ]

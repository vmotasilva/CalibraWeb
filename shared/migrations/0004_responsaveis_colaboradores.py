from django.db import migrations, models


def usuarios_para_colaboradores(apps, schema_editor):
    """Cada responsável (usuário) passa a ser o colaborador vinculado a ele; usuários sem colaborador não têm equivalente."""
    Acao = apps.get_model("shared", "AcaoOcorrencia")
    Colaborador = apps.get_model("rh", "Colaborador")
    por_user = dict(Colaborador.objects.filter(user_django__isnull=False).values_list("user_django_id", "pk"))
    for acao in Acao.objects.all():
        ids = [por_user[u] for u in acao.responsaveis.values_list("pk", flat=True) if u in por_user]
        if ids:
            acao.responsaveis_colab.add(*ids)


def colaboradores_para_usuarios(apps, schema_editor):
    Acao = apps.get_model("shared", "AcaoOcorrencia")
    Colaborador = apps.get_model("rh", "Colaborador")
    por_colab = dict(Colaborador.objects.filter(user_django__isnull=False).values_list("pk", "user_django_id"))
    for acao in Acao.objects.all():
        ids = [por_colab[c] for c in acao.responsaveis_colab.values_list("pk", flat=True) if c in por_colab]
        if ids:
            acao.responsaveis.add(*ids)


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0036_colaborador_vice_lider"),
        ("shared", "0003_comentarioacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="acaoocorrencia",
            name="responsaveis_colab",
            field=models.ManyToManyField(blank=True, related_name="+", to="rh.colaborador"),
        ),
        migrations.RunPython(usuarios_para_colaboradores, colaboradores_para_usuarios),
        migrations.RemoveField(model_name="acaoocorrencia", name="responsaveis"),
        migrations.RenameField(model_name="acaoocorrencia", old_name="responsaveis_colab", new_name="responsaveis"),
        migrations.AlterField(
            model_name="acaoocorrencia",
            name="responsaveis",
            field=models.ManyToManyField(blank=True, related_name="acoes_ocorrencia", to="rh.colaborador", verbose_name="Responsáveis"),
        ),
    ]

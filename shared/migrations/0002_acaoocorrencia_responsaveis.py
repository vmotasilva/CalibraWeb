from django.conf import settings
from django.db import migrations, models


def copiar_responsavel(apps, schema_editor):
    """Cada ação passa a ter a lista de responsáveis; o responsável único anterior vira o primeiro da lista."""
    Acao = apps.get_model("shared", "AcaoOcorrencia")
    for acao in Acao.objects.exclude(responsavel__isnull=True):
        acao.responsaveis.add(acao.responsavel_id)


def devolver_responsavel(apps, schema_editor):
    Acao = apps.get_model("shared", "AcaoOcorrencia")
    for acao in Acao.objects.all():
        primeiro = acao.responsaveis.order_by("pk").first()
        if primeiro:
            acao.responsavel_id = primeiro.pk
            acao.save(update_fields=["responsavel"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("shared", "0001_initial"),
    ]

    operations = [
        # libera o related_name "acoes_ocorrencia" para o novo campo
        migrations.AlterField(
            model_name="acaoocorrencia",
            name="responsavel",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="+",
                to=settings.AUTH_USER_MODEL, verbose_name="Responsável",
            ),
        ),
        migrations.AddField(
            model_name="acaoocorrencia",
            name="responsaveis",
            field=models.ManyToManyField(
                blank=True, related_name="acoes_ocorrencia", to=settings.AUTH_USER_MODEL, verbose_name="Responsáveis",
            ),
        ),
        migrations.RunPython(copiar_responsavel, devolver_responsavel),
        migrations.RemoveField(model_name="acaoocorrencia", name="responsavel"),
    ]

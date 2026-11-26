from django.db import migrations


def copiar_setores(apps, schema_editor):
    """Cria um SetorEquipe para cada setor do cadastro que já tem blocos na estrutura e liga blocos e postos.

    Setores do cadastro da empresa sem blocos NÃO são copiados (a tela passa a mostrar só o que foi montado nela).
    """
    Grupo = apps.get_model("organization", "GrupoEquipe")
    SetorEquipe = apps.get_model("organization", "SetorEquipe")
    for bloco in Grupo.objects.filter(parent__isnull=True, setor__isnull=False, setor_estrutura__isnull=True).select_related("setor"):
        novo, _ = SetorEquipe.objects.get_or_create(nome=bloco.setor.nome)
        Grupo.objects.filter(pk=bloco.pk).update(setor_estrutura=novo)
        Grupo.objects.filter(parent_id=bloco.pk).update(setor_estrutura=novo)


class Migration(migrations.Migration):

    dependencies = [
        ("organization", "0006_setor_equipe"),
    ]

    operations = [
        migrations.RunPython(copiar_setores, migrations.RunPython.noop),
    ]

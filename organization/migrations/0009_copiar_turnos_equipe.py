from django.db import migrations

NOMES = {"ADM": "Administrativo", "TURNO_1": "Turno 01", "TURNO_2": "Turno 02", "TURNO_3": "Turno 03", "12X36": "12x36"}
PADRAO = ("ADM", "TURNO_1", "TURNO_2", "TURNO_3")


def copiar_turnos(apps, schema_editor):
    """Cria os turnos por setor e liga as alocações existentes a eles (idempotente).

    Cada setor da estrutura recebe os 4 turnos que a tela usava (Administrativo e Turno 01/02/03) para continuar
    utilizável; o usuário pode renomear, remover (se sem alocações) ou acrescentar turnos. Alocações em outros
    códigos (ex.: 12x36) ganham o turno correspondente no setor.
    """
    SetorEquipe = apps.get_model("organization", "SetorEquipe")
    TurnoEquipe = apps.get_model("organization", "TurnoEquipe")
    Aloc = apps.get_model("organization", "AlocacaoPosto")
    for setor in SetorEquipe.objects.all():
        for cod in PADRAO:
            TurnoEquipe.objects.get_or_create(setor=setor, nome=NOMES[cod])
    for a in Aloc.objects.filter(turno_estrutura__isnull=True, turno__isnull=False).select_related("posto"):
        setor_id = a.posto.setor_estrutura_id
        if not setor_id or not a.turno:
            continue
        turno, _ = TurnoEquipe.objects.get_or_create(setor_id=setor_id, nome=NOMES.get(a.turno, a.turno))
        Aloc.objects.filter(pk=a.pk).update(turno_estrutura=turno)


class Migration(migrations.Migration):

    dependencies = [
        ("organization", "0008_turno_equipe"),
    ]

    operations = [
        migrations.RunPython(copiar_turnos, migrations.RunPython.noop),
    ]

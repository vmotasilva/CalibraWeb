from django.db import migrations


TITULOS_PADRAO = [
    "Pontualidade e Cumprimento da Agenda",
    "Clareza e Comunicação",
    "Cordialidade, Postura e Empatia",
    "Pontos Fortes do Auditor",
    "Oportunidades de Melhoria",
]


def remover_perguntas_padrao(apps, schema_editor):
    """Remove perguntas padrão auto-criadas e renumera as restantes."""
    PerguntaAvaliacaoAuditorIso = apps.get_model("auditoria", "PerguntaAvaliacaoAuditorIso")

    # 1. Deletar perguntas com títulos padrão (em qualquer auditoria ou global)
    PerguntaAvaliacaoAuditorIso.objects.filter(titulo__in=TITULOS_PADRAO).delete()

    # 2. Renumerar perguntas restantes em ordem crescente por auditoria
    auditorias_ids = (
        PerguntaAvaliacaoAuditorIso.objects.values_list("auditoria_id", flat=True)
        .distinct()
    )
    for aud_id in auditorias_ids:
        perguntas = list(
            PerguntaAvaliacaoAuditorIso.objects.filter(auditoria_id=aud_id)
            .order_by("ordem", "id")
        )
        for nova_ordem, p in enumerate(perguntas, start=1):
            if p.ordem != nova_ordem:
                p.ordem = nova_ordem
                p.save()


def reverter(apps, schema_editor):
    """Sem reverter — dados já foram removidos."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0073_alter_perguntaavaliacaoauditoriso_tipo"),
    ]

    operations = [
        migrations.RunPython(remover_perguntas_padrao, reverter),
    ]

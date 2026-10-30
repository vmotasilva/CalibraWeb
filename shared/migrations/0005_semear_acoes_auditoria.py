from django.db import migrations


def semear(apps, schema_editor):
    """Ocorrências de Auditoria em aberto com ação/responsáveis/prazo no formato antigo viram a 1ª ação do plano."""
    Oc = apps.get_model("auditoria", "ComentarioRespostaAuditoria")
    Acao = apps.get_model("shared", "AcaoOcorrencia")
    ja_tem = set(Acao.objects.filter(origem="auditoria").values_list("ocorrencia_id", flat=True))
    for oc in Oc.objects.filter(requer_tratativa=True, status="ABERTA", unificada_em__isnull=True).prefetch_related("responsaveis"):
        if oc.pk in ja_tem:
            continue
        resp = list(oc.responsaveis.values_list("pk", flat=True))
        acao = (oc.acao or "").strip()
        if not resp and not acao:
            continue
        a = Acao.objects.create(
            origem="auditoria", ocorrencia_id=oc.pk, prazo=oc.prazo, criado_por_id=oc.autor_id,
            descricao=acao or f"Tratar a ocorrência: {(oc.texto or '').strip()[:200]}",
        )
        if resp:
            a.responsaveis.set(resp)


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0084_auditores_auditados"),
        ("shared", "0004_responsaveis_colaboradores"),
    ]

    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]

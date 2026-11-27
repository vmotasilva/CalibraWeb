from django.db import migrations


def converter(apps, schema_editor):
    """Análise e Ação dos cards antigos viram notas dentro do card. Uma ocorrência antiga passa a ser uma nota
    do tipo ocorrência (o plano de ação acompanha o novo id) e o card fica só com a causa."""
    Item = apps.get_model('kpi', 'AnaliseItem')
    Acao = apps.get_model('shared', 'AcaoOcorrencia')
    for card in Item.objects.filter(pai__isnull=True).order_by('pk'):
        if Item.objects.filter(pai=card).exists():  # já convertido (a função pode rodar de novo sem duplicar)
            continue
        partes = []
        if card.analise.strip():
            partes.append(card.analise.strip())
        if card.acao.strip():
            partes.append('Ação: ' + card.acao.strip())
        texto = '\n'.join(partes)
        if card.tipo == 'ocorrencia':
            texto = '\n'.join(p for p in (card.analise.strip(), card.acao.strip()) if p)  # sem o prefixo "Ação:"
            nota = Item.objects.create(
                registro_id=card.registro_id, pai=card, ordem=0, tipo='ocorrencia', texto=texto or card.causa,
                status=card.status, resolucao=card.resolucao, resolvido_em=card.resolvido_em,
                resolvido_por_id=card.resolvido_por_id, criado_em=card.criado_em)
            Acao.objects.filter(origem='kpi', ocorrencia_id=card.pk).update(ocorrencia_id=nota.pk)
            card.tipo, card.status, card.resolucao, card.resolvido_em, card.resolvido_por = 'comentario', 'ABERTA', '', None, None
            card.save(update_fields=['tipo', 'status', 'resolucao', 'resolvido_em', 'resolvido_por'])
        elif texto:
            Item.objects.create(registro_id=card.registro_id, pai=card, ordem=0, tipo='comentario', texto=texto,
                                criado_em=card.criado_em)


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0035_analise_item_notas'),
        ('shared', '0005_semear_acoes_auditoria'),
    ]

    operations = [
        migrations.RunPython(converter, migrations.RunPython.noop),
    ]

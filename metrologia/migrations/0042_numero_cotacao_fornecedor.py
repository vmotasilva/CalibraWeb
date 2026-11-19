from django.db import migrations


def preencher_numeros(apps, schema_editor):
    """Cotações criadas sem número (o campo único nunca era gerado) passam a ter COT-AAAA-SSSS-FORFFF."""
    Cotacao = apps.get_model("metrologia", "CotacaoFornecedor")
    sem_numero = Cotacao.objects.filter(numero="").order_by("id")
    for c in sem_numero:
        ano = c.data_criacao.year
        sequencia = Cotacao.objects.filter(numero__startswith=f"COT-{ano}-").count() + 1
        sufixo = f"FOR{c.fornecedor_id % 1000:03d}"
        while True:
            numero = f"COT-{ano}-{sequencia:04d}-{sufixo}"
            if not Cotacao.objects.filter(numero=numero).exists():
                break
            sequencia += 1
        Cotacao.objects.filter(pk=c.pk).update(numero=numero)


class Migration(migrations.Migration):

    dependencies = [
        ("metrologia", "0041_link_solicitacao_compras"),
    ]

    operations = [
        migrations.RunPython(preencher_numeros, migrations.RunPython.noop),
    ]

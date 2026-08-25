from django.db import migrations


def recalcular_ema_eme_resultado(apps, schema_editor):
    """
    Recalcula EMA, EME e resultado de TODOS os ResultadoFaixaCalibracao existentes.
    - Herda tolerancia da faixa se nula
    - EMA = Tolerancia * 2 / 4
    - EME = |Erro + Incerteza|
    - Resultado baseado em EME vs EMA*3
    """
    ResultadoFaixaCalibracao = apps.get_model("metrologia", "ResultadoFaixaCalibracao")

    for rf in ResultadoFaixaCalibracao.objects.select_related("faixa").all():
        changed = False

        # Herdar tolerancia da faixa se necessario
        if rf.tolerancia is None and rf.faixa_id:
            try:
                rf.tolerancia = rf.faixa.tolerancia_mais_menos
                changed = True
            except Exception:
                pass

        # Calcular EMA = Tolerancia * 2 / 4
        if rf.tolerancia is not None:
            new_ema = rf.tolerancia * 2 / 4
            if rf.ema != new_ema:
                rf.ema = new_ema
                changed = True

        # Calcular EME = |Erro + Incerteza|
        if rf.erro is not None and rf.incerteza is not None:
            new_eme = abs(rf.erro + rf.incerteza)
            if rf.eme != new_eme:
                rf.eme = new_eme
                changed = True

        # Calcular resultado
        if rf.eme is not None and rf.ema is not None:
            eme_val = abs(rf.eme)
            ema_val = abs(rf.ema)

            if eme_val > ema_val * 3:
                new_resultado = "REPROVADO"
            elif eme_val <= ema_val:
                new_resultado = "APROVADO_SEM_CORRECAO"
            else:
                new_resultado = "APROVADO_COM_CORRECAO"

            if rf.resultado != new_resultado:
                rf.resultado = new_resultado
                changed = True

        if changed:
            rf.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("metrologia", "0033_historicocalibracao_link_certificado"),
    ]

    operations = [
        migrations.RunPython(recalcular_ema_eme_resultado, noop),
    ]

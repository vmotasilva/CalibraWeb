import datetime

from django.db import migrations, transaction


def forwards(apps, schema_editor):
    """Compõe agora as semanas e meses recentes que ainda não existem a partir dos dias já lançados
    (ex.: o mês corrente aparecia sem barra no gráfico mês a mês). Valores já existentes não são alterados."""
    try:
        # Savepoint: se a consulta falhar (ex.: coluna de migration posterior ainda inexistente), o erro não aborta a transação da migration no PostgreSQL.
        with transaction.atomic():
            from kpi.consolidacao import consolidar_valores
            from kpi.models import Indicador, Medicao
            limite = datetime.date.today() - datetime.timedelta(days=70)
            for ind in Indicador.objects.exclude(formula=''):
                por_setor = {}
                for setor_id, periodo in Medicao.objects.filter(indicador=ind, granularidade='diaria', periodo__gte=limite).values_list('setor_id', 'periodo'):
                    por_setor.setdefault(setor_id, []).append(periodo)
                for setor_id, datas in por_setor.items():
                    consolidar_valores(ind, setor_id, datas)
    except Exception:  # a composição é só uma conveniência: nunca impedir a migração
        pass


class Migration(migrations.Migration):

    dependencies = [('kpi', '0016_analise_dispensa')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

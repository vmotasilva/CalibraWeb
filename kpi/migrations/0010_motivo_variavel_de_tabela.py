from django.db import migrations


def forwards(apps, schema_editor):
    """A variável "Motivo" alimenta só a tabela Top motivos: marca como variável de tabela para sair de Var 01/cálculo."""
    Indicador = apps.get_model('kpi', 'Indicador')
    for ind in Indicador.objects.exclude(campos=''):
        linhas, mudou = [], False
        for linha in ind.campos.splitlines():
            if linha.strip().lower() == 'motivo':
                linha, mudou = 'Motivo | tabela', True
            linhas.append(linha)
        if mudou:
            ind.campos = '\n'.join(linhas)
            ind.save(update_fields=['campos'])


class Migration(migrations.Migration):

    dependencies = [('kpi', '0009_motivo_consolidado')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

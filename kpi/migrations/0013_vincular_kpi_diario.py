from django.db import migrations

NOME = 'KPI Diário'

# rótulo -> [(indicador, variável, setor)]. Só preenche posições que ainda estão sem vínculo (só o rótulo),
# e só quando o indicador, a variável e o setor existem: o que já foi vinculado à mão nunca é alterado.
VINCULOS = {
    'TOTAL LENTES - ENVIADAS': [('Late Orders', 'Lentes enviadas', '')],
    'TOTAL LENTES - ENVIADAS COM ATRAZO > 2': [('Late Orders', 'Lentes com mais de 2 dias de atraso', '')],
    'SURFACAGEM - LENTES BOAS': [('Quebras', 'Lentes Produzidas', 'Surfaçagem')],
    'SURFACAGEM - LENTES QUEBRADAS': [('Quebras', 'Lentes Perdidas', 'Surfaçagem')],
    'HC - LENTES BOAS': [('Quebras', 'Lentes Produzidas', 'HMC')],
    'HC - LENTES QUEBRADAS': [('Quebras', 'Lentes Perdidas', 'HMC')],
    'AR - LENTES BOAS': [('Quebras', 'Lentes Produzidas', 'HMC')],
    'AR - LENTES QUEBRADAS': [('Quebras', 'Lentes Perdidas', 'HMC')],
    'E_M - LENTES BOAS': [('Quebras', 'Lentes Produzidas', 'Montagem')],
    'E_M - LENTES QUEBRADAS': [('Quebras', 'Lentes Perdidas', 'Montagem')],
}


def _campos(ind):
    return {ln.partition('|')[0].strip().lower(): ln.partition('|')[0].strip() for ln in (ind.campos or '').splitlines()
            if ln.strip() and ln.partition('|')[2].strip().lower() not in ('tabela', 'texto')}


def forwards(apps, schema_editor):
    Modelo = apps.get_model('kpi', 'ModeloColagem')
    Indicador = apps.get_model('kpi', 'Indicador')
    Setor = apps.get_model('kpi', 'SetorIndicador')
    modelo = Modelo.objects.filter(nome__iexact=NOME).first()
    if not modelo:
        return
    inds = {i.nome.strip().lower(): i for i in Indicador.objects.all()}
    novas, mudou = [], False
    for linha in modelo.linhas.splitlines():
        rotulo = linha.strip()
        destinos = []
        if rotulo and '|' not in rotulo:
            for nome, variavel, setor in VINCULOS.get(rotulo, []):
                ind = inds.get(nome.lower())
                if not ind or variavel.lower() not in _campos(ind):
                    continue
                if setor and not Setor.objects.filter(indicador=ind, nome__iexact=setor).exists():
                    continue
                destinos.append(' | '.join([ind.nome, _campos(ind)[variavel.lower()], setor, '+', '1']))
        if destinos:
            linha, mudou = rotulo + ' || ' + ' || '.join(destinos), True
        novas.append(linha)
    if mudou:
        modelo.linhas = '\n'.join(novas)
        modelo.save(update_fields=['linhas'])


class Migration(migrations.Migration):

    dependencies = [('kpi', '0012_modelo_colagem_kpi_diario')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

from django.db import migrations

NOME_MODELO = 'KPI Diário'
IND = 'Service Rate'
CAMPOS = 'Lentes enviadas no prazo\nLentes enviadas'
FORMULA = '[Lentes enviadas no prazo] / [Lentes enviadas] * 100'
VINCULOS = {
    'TOTAL LENTES - ENVIADAS NO PRAZO': ['Lentes enviadas no prazo'],
    'TOTAL LENTES - ENVIADAS': ['Lentes enviadas'],
}


def forwards(apps, schema_editor):
    """Service Rate = enviadas no prazo / enviadas x 100. Só define variáveis e fórmula se o indicador ainda não tem
    nenhuma; só acrescenta o vínculo se a variável existe e a posição ainda não aponta para ele."""
    Indicador = apps.get_model('kpi', 'Indicador')
    Modelo = apps.get_model('kpi', 'ModeloColagem')
    ind = Indicador.objects.filter(nome__iexact=IND).first()
    if not ind:
        return
    if not (ind.campos or '').strip() and not (ind.formula or '').strip():
        ind.campos, ind.formula = CAMPOS, FORMULA
        ind.save(update_fields=['campos', 'formula'])
    campos = {c.partition('|')[0].strip().lower(): c.partition('|')[0].strip() for c in (ind.campos or '').splitlines() if c.strip()}
    modelo = Modelo.objects.filter(nome__iexact=NOME_MODELO).first()
    if not modelo:
        return
    novas, mudou = [], False
    for linha in modelo.linhas.splitlines():
        rotulo = linha.split('||')[0].split('|')[0].strip()
        for variavel in VINCULOS.get(rotulo, []):
            nome = campos.get(variavel.lower())
            if not nome or f'{ind.nome} | {nome} |' in linha:
                continue
            bloco = f'{ind.nome} | {nome} |  | + | 1'
            if '||' in linha:
                linha += ' || ' + bloco
            elif '|' in linha:  # formato simples: converte para o completo preservando o destino existente
                p = [x.strip() for x in linha.split('|')] + ['', '', '']
                linha = f'{p[0]} || {p[1]} | {p[2]} | {p[3]} | + | 1 || {bloco}'
            else:
                linha = f'{rotulo} || {bloco}'
            mudou = True
        novas.append(linha)
    if mudou:
        modelo.linhas = '\n'.join(novas)
        modelo.save(update_fields=['linhas'])


class Migration(migrations.Migration):

    dependencies = [('kpi', '0013_vincular_kpi_diario')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

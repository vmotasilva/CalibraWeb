"""DECIDE: leitura da planilha semanal do medidor de lentes e cálculo dos indicadores de acompanhamento.

Cada linha da planilha é uma medição. Uma lente (Final TrackID) pode ter várias medições; a de "Last Measure" = 1
é a final. SYS_VERDICT = 2 significa lente reprovada. Os veredictos por parâmetro (S, C, SC, AXE, PD, PDH, PDV,
ADD, EP) valem 2 quando o parâmetro reprovou.
"""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

PARAMETROS = ['S', 'C', 'SC', 'AXE', 'PD', 'PDH', 'PDV', 'ADD', 'EP']
NOMES_PARAMETROS = {
    'S': 'Esfera', 'C': 'Cilindro', 'SC': 'Esfera + cilindro', 'AXE': 'Eixo', 'PD': 'DP', 'PDH': 'DP horizontal',
    'PDV': 'DP vertical', 'ADD': 'Adição', 'EP': 'Espessura',
}
OBRIGATORIAS = ['Final TrackID', 'Qty Pass', 'Last Measure', 'DATE_MESURE', 'SYS_VERDICT']

# chave -> (nome, unidade, sentido da meta: 'menor' | 'maior' | '')
MEDIDAS = {
    'reprovacao': ('% de lentes reprovadas (medição final)', '%', 'menor'),
    'aprovacao_1a': ('% de lentes aprovadas na 1ª medição', '%', 'maior'),
    'remedicao': ('% de lentes medidas mais de uma vez', '%', 'menor'),
    'lentes': ('Lentes medidas', 'un', ''),
    'reprovadas': ('Lentes reprovadas', 'un', ''),
    'medicoes': ('Medições realizadas', 'un', ''),
}
PERIODOS = {'dia': 'Dia a dia', 'semana': 'Semana a semana', 'mes': 'Mês a mês'}
# chave -> (nome, campo do DecideLente)
DIMENSOES = {
    'ilot': ('Ilot (medidor)', 'ilot'),
    'marca': ('Marca / design', 'marca'),
    'indice': ('Índice', 'indice'),
    'diametro': ('Diâmetro', 'diametro'),
    'olho': ('Olho (1 = direito, 2 = esquerdo)', 'olho'),
    'codigo_op': ('Código da operação', 'codigo_op'),
    'medidor': ('Operador (INI)', 'medidor'),
    'motivo': ('Motivo de reprovação (parâmetro)', None),
}
FILTROS = ['ilot', 'marca', 'indice', 'diametro', 'olho', 'codigo_op']


class ErroPlanilha(Exception):
    pass


def _texto(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _data(v):
    if isinstance(v, datetime.datetime):
        d = v
    else:
        s = _texto(v)
        try:
            d = datetime.datetime.fromisoformat(s.replace(' ', 'T'))
        except ValueError:
            return None
    return timezone.make_aware(d) if timezone.is_naive(d) else d


def importar(arquivo, usuario):
    """Lê a aba "Dados" (ou a primeira) e grava as medições; reimportar o mesmo arquivo substitui as linhas."""
    from kpi.models import DecideImportacao, DecideLente
    try:
        wb = load_workbook(arquivo, read_only=True, data_only=True)
    except Exception:
        raise ErroPlanilha('Não foi possível abrir o arquivo. Envie a planilha .xlsx exportada do DECIDE.')
    ws = wb['Dados'] if 'Dados' in wb.sheetnames else wb[wb.sheetnames[0]]
    linhas = ws.iter_rows(values_only=True)
    cab = next(linhas, None)
    if not cab:
        raise ErroPlanilha('A planilha está vazia.')
    ix = {str(c).strip(): i for i, c in enumerate(cab) if c is not None}
    faltam = [c for c in OBRIGATORIAS if c not in ix]
    if faltam:
        raise ErroPlanilha('Colunas não encontradas: ' + ', '.join(faltam) + '. É a planilha semanal do DECIDE?')

    def cel(linha, nome):
        i = ix.get(nome)
        return linha[i] if i is not None and i < len(linha) else None

    registros, ignoradas = [], 0
    for linha in linhas:
        track = _texto(cel(linha, 'Final TrackID'))
        quando = _data(cel(linha, 'DATE_MESURE'))
        if not track or quando is None:
            ignoradas += 1
            continue
        falhas = [p for p in PARAMETROS if _texto(cel(linha, f'{p}_VERDICT')) == '2']
        try:
            passagens = int(cel(linha, 'Qty Pass') or 1)
        except (TypeError, ValueError):
            passagens = 1
        registros.append({
            'track_id': track, 'passagens': passagens, 'medido_em': quando,
            'ultima': _texto(cel(linha, 'Last Measure')) == '1',
            'reprovada': _texto(cel(linha, 'SYS_VERDICT')) == '2',
            'ilot': _texto(cel(linha, 'ID_ILOT')), 'decisao': _texto(cel(linha, 'OP_DECISION')),
            'codigo_op': _texto(cel(linha, 'CODE_OP')), 'marca': _texto(cel(linha, 'MARQUE')),
            'indice': _texto(cel(linha, 'INDICE')), 'diametro': _texto(cel(linha, 'DIAMETRE')),
            'olho': _texto(cel(linha, 'OEIL')), 'medidor': _texto(cel(linha, 'INI')),
            'falhas': ','.join(falhas),
        })
    if not registros:
        raise ErroPlanilha('Nenhuma medição válida encontrada na planilha.')

    # Resultado da 1ª medição de cada lente, copiado para a linha final.
    por_lente = defaultdict(list)
    for r in registros:
        por_lente[r['track_id']].append(r)
    for medicoes in por_lente.values():
        medicoes.sort(key=lambda r: r['medido_em'])
        primeira = medicoes[0]['reprovada']
        for r in medicoes:
            r['reprovada_1a'] = primeira

    with transaction.atomic():
        imp = DecideImportacao.objects.create(
            arquivo=str(getattr(arquivo, 'name', ''))[:200], linhas=len(registros), lentes=len(por_lente),
            inicio=min(r['medido_em'] for r in registros).date(), fim=max(r['medido_em'] for r in registros).date(),
            criado_por=usuario)
        chaves = {(r['track_id'], r['medido_em']) for r in registros}
        antigos = [pk for pk, t, m in DecideLente.objects.filter(track_id__in=por_lente.keys()).values_list('pk', 'track_id', 'medido_em')
                   if (t, m) in chaves]
        DecideLente.objects.filter(pk__in=antigos).delete()
        DecideLente.objects.bulk_create([DecideLente(importacao=imp, **r) for r in registros], batch_size=500)
    imp.substituidas = len(antigos)
    imp.ignoradas = ignoradas
    return imp


# ---------------------------------------------------------------- cálculo
def _chave_periodo(d, periodo):
    d = timezone.localtime(d).date() if isinstance(d, datetime.datetime) else d
    if periodo == 'dia':
        return d, d.strftime('%d/%m')
    if periodo == 'semana':
        seg = d - datetime.timedelta(days=d.weekday())
        return seg, f'S{seg.isocalendar()[1]:02d} ({seg:%d/%m})'
    ini = d.replace(day=1)
    return ini, ini.strftime('%m/%Y')


def _valor(medida, b):
    """b: contadores do período (lentes, reprovadas, reprov_1a, remedidas, medicoes)."""
    if medida == 'lentes':
        return b['lentes']
    if medida == 'reprovadas':
        return b['reprovadas']
    if medida == 'medicoes':
        return b['medicoes']
    if not b['lentes']:
        return None
    chave = {'reprovacao': 'reprovadas', 'aprovacao_1a': None, 'remedicao': 'remedidas'}[medida]
    if medida == 'aprovacao_1a':
        return round((b['lentes'] - b['reprov_1a']) * 100 / b['lentes'], 2)
    return round(b[chave] * 100 / b['lentes'], 2)


def _zero():
    return {'lentes': 0, 'reprovadas': 0, 'reprov_1a': 0, 'remedidas': 0, 'medicoes': 0}


def inicio_periodo(d, periodo):
    """Primeiro dia do período (dia, segunda-feira da semana ou dia 1 do mês) que contém a data."""
    if periodo == 'semana':
        return d - datetime.timedelta(days=d.weekday())
    if periodo == 'mes':
        return d.replace(day=1)
    return d


def fim_periodo(d, periodo):
    """Último dia do período que contém a data."""
    if periodo == 'semana':
        return inicio_periodo(d, 'semana') + datetime.timedelta(days=6)
    if periodo == 'mes':
        return (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    return d


def _valores(v):
    return [v] if isinstance(v, str) else list(v or [])


def _filtrar(qs, filtros, de, ate, periodo, ignorar=None):
    """Aplica filtros (cada um aceita vários valores) e o intervalo De/Até, estendido aos períodos inteiros."""
    for f, v in (filtros or {}).items():
        vals = [x for x in _valores(v) if x]
        if vals and f in FILTROS and f != ignorar:
            qs = qs.filter(**{f'{f}__in': vals})
    if de:
        qs = qs.filter(medido_em__date__gte=inicio_periodo(de, periodo))
    if ate:
        qs = qs.filter(medido_em__date__lte=fim_periodo(ate, periodo))
    return qs


def _ordem(v):
    return (not v.isdigit(), int(v) if v.isdigit() else 0, v)


def opcoes_filtros(filtros=None, de=None, ate=None, periodo='dia'):
    """Opções de cada filtro em cascata: só valores que existem com os demais filtros e o intervalo aplicados."""
    from kpi.models import DecideLente
    filtros = {f: [x for x in _valores(v) if x] for f, v in (filtros or {}).items()}
    out = {}
    for f in FILTROS:
        qs = _filtrar(DecideLente.objects.all(), filtros, de, ate, periodo, ignorar=f)
        vals = set(qs.exclude(**{f: ''}).values_list(f, flat=True).distinct()) | set(filtros.get(f, []))
        out[f] = sorted(vals, key=_ordem)
    return out


def datas_com_medicao():
    """Datas (locais) que têm medição, em ordem crescente."""
    from django.db.models.functions import TruncDate
    from kpi.models import DecideLente
    return sorted(set(DecideLente.objects.annotate(d=TruncDate('medido_em')).values_list('d', flat=True)) - {None})


def opcoes_periodo(periodo, datas):
    """Lista (data ISO do início, rótulo) dos períodos com medição; None no modo dia (usa seletor de data)."""
    if periodo == 'dia':
        return None
    inicios = sorted({inicio_periodo(d, periodo) for d in datas})
    if periodo == 'semana':
        return [(i.isoformat(), f'S{i.isocalendar()[1]:02d} · {i:%d/%m/%Y}') for i in inicios]
    return [(i.isoformat(), f'{i:%m/%Y}') for i in inicios]


def calcular(medida, periodo, dimensao='', filtros=None, de=None, ate=None):
    """Devolve rótulos dos períodos, séries (uma por valor da dimensão, ou "Total"), pareto de parâmetros e resumo."""
    from kpi.models import DecideLente
    qs = _filtrar(DecideLente.objects.all(), filtros, de, ate, periodo)
    por_motivo = dimensao == 'motivo'
    campo = DIMENSOES[dimensao][1] if dimensao in DIMENSOES else None
    cols = ['medido_em', 'ultima', 'reprovada', 'reprovada_1a', 'passagens', 'falhas']
    if campo:
        cols.append(campo)

    series = defaultdict(lambda: defaultdict(_zero))
    totais = _zero()
    rotulos = {}
    falhas = defaultdict(int)
    lentes_periodo = defaultdict(int)  # denominador do % por motivo: todas as lentes do período
    for r in qs.values(*cols):
        chave, rotulo = _chave_periodo(r['medido_em'], periodo)
        rotulos[chave] = rotulo
        if r['ultima']:
            lentes_periodo[chave] += 1
        if por_motivo:
            # Uma lente reprovada conta em cada parâmetro que reprovou (pode estar em mais de um).
            if r['ultima'] and r['reprovada']:
                nomes = [NOMES_PARAMETROS.get(p, p) for p in filter(None, r['falhas'].split(','))] or ['(sem parâmetro)']
            else:
                nomes = []
        else:
            nomes = [(r[campo] or '(vazio)') if campo else 'Total']
        buckets = [series[n][chave] for n in nomes] + [totais]
        for b in buckets:
            b['medicoes'] += 1
            if r['ultima']:
                b['lentes'] += 1
                b['reprovadas'] += r['reprovada']
                b['reprov_1a'] += r['reprovada_1a']
                b['remedidas'] += r['passagens'] > 1
        if r['ultima'] and r['reprovada']:
            for p in filter(None, r['falhas'].split(',')):
                falhas[p] += 1
    if por_motivo:
        for dados in series.values():
            for k, b in dados.items():
                b['lentes'] = lentes_periodo[k]

    chaves = sorted(rotulos)
    por_serie = []
    for nome in sorted(series, key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else 0, n)):
        dados = series[nome]
        vazio = _zero()
        por_serie.append({
            'nome': nome,
            'valores': [_valor(medida, dados.get(k, vazio)) for k in chaves],
            'lentes': [dados[k]['lentes'] if k in dados else 0 for k in chaves],
            'reprovadas': [dados[k]['reprovadas'] if k in dados else 0 for k in chaves],
        })
    total_falhas = sum(falhas.values())
    pareto = [{'codigo': p, 'nome': NOMES_PARAMETROS[p], 'qtd': q, 'pct': round(q * 100 / total_falhas, 1)}
              for p, q in sorted(falhas.items(), key=lambda x: -x[1])]
    return {
        'rotulos': [rotulos[k] for k in chaves], 'series': por_serie, 'pareto': pareto,
        'resumo': {**totais, 'valor': _valor(medida, totais)},
    }


def _lista(dados, campo):
    """Valores de um filtro: aceita QueryDict (vários valores), lista ou texto da configuração antiga."""
    if hasattr(dados, 'getlist'):
        brutos = dados.getlist(campo)
    else:
        brutos = _valores(dados.get(campo))
    out = []
    for v in brutos:
        v = str(v).strip()
        if v and v not in out:
            out.append(v)
    return out


def ler_parametros(dados):
    """Normaliza os parâmetros do construtor (GET ou configuração salva)."""
    medida = dados.get('medida') if dados.get('medida') in MEDIDAS else 'reprovacao'
    periodo = dados.get('periodo') if dados.get('periodo') in PERIODOS else 'dia'
    dimensao = dados.get('dimensao') if dados.get('dimensao') in DIMENSOES else ''
    filtros = {f: _lista(dados, f) for f in FILTROS if _lista(dados, f)}

    def dt(k):
        try:
            return datetime.date.fromisoformat((dados.get(k) or '').strip())
        except ValueError:
            return None

    meta = (dados.get('meta') or '').strip().replace(',', '.')
    try:
        meta = Decimal(meta) if meta else None
    except Exception:
        meta = None
    de, ate = dt('de'), dt('ate')
    if de and ate and de > ate:
        de, ate = ate, de
    return {'medida': medida, 'periodo': periodo, 'dimensao': dimensao, 'filtros': filtros,
            'de': de, 'ate': ate, 'meta': meta}

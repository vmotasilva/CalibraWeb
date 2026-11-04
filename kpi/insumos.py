"""Insumos: importação do relatório "Consulta Movimento em Estoque" (almoxarifado) e cálculo do consumo mensal por item.

Aceita os dois formatos do relatório (o enxuto, sem cabeçalho, e o formatado, com cabeçalho, páginas e famílias),
em .xls ou .xlsx. Cada linha de dado tem, na ordem: código, material, quantidade, tipo de movimento, data, tipo
(saída), origem, estorno e identificador. As movimentações são guardadas inteiras; o consumo mensal de cada item é
calculado a partir delas (soma dos códigos vinculados × fator) e pode ser refeito a qualquer momento.
"""
import calendar
import datetime
import io
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth

from kpi.models import HierCodigo, HierConsumo, HierMovimento

# Tipos de movimento que contam como consumo (já normalizados: sem acento, maiúsculos). DEVOLUCAO fica de fora.
TIPOS_CONSUMO = frozenset({'UTILIZACOES', 'PERDAS'})
CASAS = Decimal('0.001')


class ErroImportacao(Exception):
    pass


def _norm(txt):
    s = unicodedata.normalize('NFKD', str(txt)).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(s.upper().split())


def _fim_do_mes(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def ler_linhas(conteudo, nome=''):
    """Lê a primeira aba. Retorna (linhas, datemode)."""
    if conteudo[:4] == b'\xd0\xcf\x11\xe0':  # .xls (BIFF)
        try:
            import xlrd
        except ImportError:
            raise ErroImportacao('Para ler arquivos .xls é preciso instalar o pacote xlrd (ou salve o relatório como .xlsx).')
        try:
            wb = xlrd.open_workbook(file_contents=conteudo, logfile=io.StringIO())
            ws = wb.sheet_by_index(0)
        except Exception as e:
            raise ErroImportacao(f'Não foi possível ler o arquivo .xls: {e}')
        return [[c.value for c in ws.row(i)] for i in range(ws.nrows)], wb.datemode
    if conteudo[:2] == b'PK':  # .xlsx
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
            return [list(r) for r in wb[wb.sheetnames[0]].iter_rows(values_only=True)], 0
        except Exception as e:
            raise ErroImportacao(f'Não foi possível ler o arquivo .xlsx: {e}')
    raise ErroImportacao('Arquivo não reconhecido: envie o relatório em .xls ou .xlsx.')


def _data(v, datemode):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, (int, float)) and v > 0:
        base = datetime.date(1904, 1, 1) if datemode == 1 else datetime.date(1899, 12, 30)
        return base + datetime.timedelta(days=int(v))
    if isinstance(v, str):
        try:
            return datetime.datetime.strptime(v.strip(), '%d/%m/%Y').date()
        except ValueError:
            return None
    return None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def interpretar(linhas, datemode=0):
    """Extrai as movimentações. Uma linha de dado tem 9 células preenchidas (as vazias do layout são descartadas, então
    o deslocamento de colunas do relatório formatado não importa); linhas "Família:" dão a família dos códigos seguintes."""
    registros, familia = [], ''
    ignoradas = estornos = 0
    for linha in linhas:
        vals = [v.strip() if isinstance(v, str) else v for v in linha]
        vals = [v for v in vals if v not in ('', None)]
        if not vals:
            continue
        if isinstance(vals[0], str) and _norm(vals[0]) == 'FAMILIA:':
            familia = str(vals[1]).strip() if len(vals) > 1 else ''
            continue
        if not (_num(vals[0]) and len(vals) > 1 and isinstance(vals[1], str)):
            continue  # cabeçalho, subtotal, rodapé de página...
        ok = (len(vals) == 9 and _num(vals[2]) and isinstance(vals[3], str) and _num(vals[4])
              and _num(vals[8]) and vals[0] == int(vals[0]) and vals[0] > 0)
        data = _data(vals[4], datemode) if ok else None
        if not ok or data is None:
            if len(vals) >= 5:  # tem cara de movimentação mas não bate com o layout (rodapés de página têm 2 células)
                ignoradas += 1
            continue
        if _norm(vals[7]).startswith('S'):  # estorno = SIM
            estornos += 1
            continue
        registros.append({
            'codigo': int(vals[0]), 'material': vals[1], 'familia': familia,
            'quantidade': Decimal(str(vals[2])).quantize(CASAS), 'tipo': _norm(vals[3])[:20],
            'data': data, 'origem': _norm(vals[6])[:30], 'identif': int(vals[8]),
        })
    return {'registros': registros, 'ignoradas': ignoradas, 'estornos': estornos}


def _partes_material(material):
    """'NOME / REFERÊNCIA / UN' -> ('NOME / REFERÊNCIA', 'UN')."""
    partes = [p.strip() for p in material.split(' / ')]
    if len(partes) >= 3 and 0 < len(partes[-1]) <= 6:
        return ' / '.join(partes[:-1])[:300], partes[-1]
    return material[:300], ''


def _chave(codigo, data, qtd, tipo, identif):
    return (codigo, data, qtd, tipo, identif)


def importar(registros):
    """Grava códigos e movimentações (sem duplicar o que já foi importado, contando repetições legítimas) e recalcula
    o consumo dos itens afetados. Pode ser reimportado com períodos sobrepostos."""
    if not registros:
        raise ErroImportacao('Nenhuma movimentação encontrada no arquivo. Confira se é o relatório "Consulta Movimento em Estoque".')
    info = {}
    for r in registros:
        desc, un = _partes_material(r['material'])
        antigo = info.get(r['codigo'], {})
        info[r['codigo']] = {'descricao': desc, 'unidade': un, 'familia': r['familia'] or antigo.get('familia', '')}

    with transaction.atomic():
        codigos = {c.codigo: c for c in HierCodigo.objects.filter(codigo__in=list(info))}
        novos = [HierCodigo(codigo=cod, **dados) for cod, dados in info.items() if cod not in codigos]
        HierCodigo.objects.bulk_create(novos, batch_size=500)
        alterar = []
        for cod, c in codigos.items():
            d = info[cod]
            mudou = False
            for campo in ('descricao', 'unidade', 'familia'):
                if d[campo] and getattr(c, campo) != d[campo]:
                    setattr(c, campo, d[campo])
                    mudou = True
            if mudou:
                alterar.append(c)
        if alterar:
            HierCodigo.objects.bulk_update(alterar, ['descricao', 'unidade', 'familia'], batch_size=500)
        codigos = {c.codigo: c for c in HierCodigo.objects.filter(codigo__in=list(info))}

        d0, d1 = min(r['data'] for r in registros), max(r['data'] for r in registros)
        no_banco = Counter(_chave(*t) for t in HierMovimento.objects.filter(data__range=(d0, d1)).values_list(
            'codigo__codigo', 'data', 'quantidade', 'tipo', 'identif'))
        no_arquivo = Counter(_chave(r['codigo'], r['data'], r['quantidade'], r['tipo'], r['identif']) for r in registros)
        origens = {_chave(r['codigo'], r['data'], r['quantidade'], r['tipo'], r['identif']): r['origem'] for r in registros}
        novos_mov, ja_existiam = [], 0
        for chave, n in no_arquivo.items():
            falta = max(n - no_banco.get(chave, 0), 0)
            ja_existiam += n - falta
            novos_mov += [HierMovimento(codigo=codigos[chave[0]], data=chave[1], quantidade=chave[2], tipo=chave[3],
                                        origem=origens[chave], identif=chave[4]) for _ in range(falta)]
        HierMovimento.objects.bulk_create(novos_mov, batch_size=1000)

        afetados = HierCodigo.objects.filter(codigo__in=list(info), item__isnull=False).values_list('item_id', flat=True)
        recalculo = recalcular(set(afetados))
        sem_vinculo = HierCodigo.objects.filter(codigo__in=list(info), item__isnull=True, ignorado=False).count()
    return {
        'lidas': len(registros), 'adicionadas': len(novos_mov), 'ja_existiam': ja_existiam,
        'codigos_novos': len(novos), 'codigos': len(info), 'inicio': d0, 'fim': d1,
        'sem_vinculo': sem_vinculo, 'itens_recalculados': len(set(afetados)), 'recalculo': recalculo,
    }


def recalcular(item_ids=None):
    """Refaz o consumo mensal 'importado' dos itens (todos, se item_ids for None). Lançamentos manuais não são alterados.
    Meses sem movimentação deixam de ter consumo importado (ex.: código desvinculado)."""
    movs = HierMovimento.objects.filter(codigo__item__isnull=False, tipo__in=TIPOS_CONSUMO)
    existentes = HierConsumo.objects.all()
    if item_ids is not None:
        item_ids = set(item_ids)
        movs = movs.filter(codigo__item_id__in=item_ids)
        existentes = existentes.filter(item_id__in=item_ids)
    total = Sum(ExpressionWrapper(F('quantidade') * F('codigo__fator'), output_field=DecimalField(max_digits=24, decimal_places=6)))
    calculado = {}
    for linha in (movs.annotate(mes=TruncMonth('data')).order_by().values('codigo__item_id', 'mes').annotate(total=total)):
        calculado[(linha['codigo__item_id'], _fim_do_mes(linha['mes']))] = Decimal(linha['total']).quantize(Decimal('0.01'))

    atuais = {(c.item_id, c.periodo): c for c in existentes}
    criar, atualizar, apagar = [], [], []
    for chave, valor in calculado.items():
        atual = atuais.get(chave)
        if atual is None:
            criar.append(HierConsumo(item_id=chave[0], periodo=chave[1], valor=valor, origem=HierConsumo.ORIGEM_IMPORTADO))
        elif atual.origem == HierConsumo.ORIGEM_IMPORTADO and atual.valor != valor:
            atual.valor = valor
            atualizar.append(atual)
    for chave, atual in atuais.items():
        if atual.origem == HierConsumo.ORIGEM_IMPORTADO and chave not in calculado:
            apagar.append(atual.pk)
    HierConsumo.objects.bulk_create(criar, batch_size=500)
    if atualizar:
        HierConsumo.objects.bulk_update(atualizar, ['valor'], batch_size=500)
    if apagar:
        HierConsumo.objects.filter(pk__in=apagar).delete()
    return {'criados': len(criar), 'atualizados': len(atualizar), 'removidos': len(apagar)}

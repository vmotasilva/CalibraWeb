"""Registro por colagem: o usuário cola uma lista de números e o modelo (posição -> destinos) distribui os valores.

Modelo (texto, uma linha por posição). Dois formatos:
- Simples: ``Rótulo | Indicador | Variável | Setor`` (um destino, soma).
- Completo: ``Rótulo || Indicador | Variável | Setor | Operação | Fator || Indicador | ...`` (vários destinos).
  Operação: ``+`` soma ao que as outras posições já mandaram para a mesma variável, ``-`` subtrai, ``=`` substitui.
  Fator multiplica o número antes de aplicar a operação (padrão 1).
- Só o rótulo: a posição é lida na colagem, mas não alimenta nenhum indicador.
- Variável vazia ou "Valor": o número é o valor do indicador. Setor vazio = acompanhamento geral.
"""
import re
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.db import transaction

from kpi import calculo, consolidacao
from kpi.models import Indicador, Medicao

OPERACOES = {'+': 'soma', '-': 'subtrai', '=': 'substitui'}


def _fator(txt):
    txt = (txt or '').strip().replace(' ', '')
    if not txt:
        return Decimal(1)
    if ',' in txt:
        txt = txt.replace('.', '').replace(',', '.')
    return Decimal(txt)


def _destino(indicadores, pos, partes, erros):
    """Monta um destino a partir de [indicador, variável, setor, operação, fator]; None se inválido."""
    partes = [p.strip() for p in partes] + ['', '', '', '', '']
    nome_ind, variavel, nome_setor, op, fator = partes[:5]
    ind = indicadores.get(nome_ind.lower())
    if not ind:
        erros.append(f'Linha {pos}: indicador "{nome_ind}" não encontrado.')
        return None
    destino = {'ind': ind, 'variavel': '', 'setor': None, 'op': '+', 'fator': Decimal(1)}
    if variavel and variavel.lower() != 'valor':
        campos = {c.lower(): c for c in calculo.lista_campos(ind)}
        if variavel.lower() not in campos:
            erros.append(f'Linha {pos}: "{variavel}" não é variável de "{ind.nome}" (variáveis: {", ".join(campos.values()) or "nenhuma"}).')
            return None
        destino['variavel'] = campos[variavel.lower()]
    if nome_setor:
        setor = next((s for s in ind.setores.all() if s.nome.strip().lower() == nome_setor.lower()), None)
        if not setor:
            erros.append(f'Linha {pos}: setor "{nome_setor}" não cadastrado em "{ind.nome}".')
            return None
        destino['setor'] = setor
    if op:
        if op not in OPERACOES:
            erros.append(f'Linha {pos}: operação "{op}" inválida (use +, - ou =).')
            return None
        destino['op'] = op
    try:
        destino['fator'] = _fator(fator)
    except InvalidOperation:
        erros.append(f'Linha {pos}: fator "{fator}" inválido.')
        return None
    return destino


def descrever(d):
    txt = f'{d["ind"].nome} · {d["variavel"] or "Valor"}'
    if d['setor']:
        txt += f' · {d["setor"].nome}'
    marca = {'+': '+', '-': '−', '=': '='}[d['op']]
    fator = '' if d['fator'] == 1 else f' × {d["fator"].normalize():f}'
    return f'{marca} {txt}{fator}'


def interpretar_modelo(texto):
    """Retorna (linhas, erros). Cada linha: dict(pos, rotulo, destinos, destino)."""
    indicadores = {i.nome.strip().lower(): i for i in Indicador.objects.prefetch_related('setores')}
    linhas, erros = [], []
    for texto_linha in (texto or '').splitlines():
        if not texto_linha.strip():
            continue
        pos = len(linhas) + 1
        destinos = []
        if '||' in texto_linha:
            blocos = texto_linha.split('||')
            rotulo = blocos[0].strip()
            for bloco in blocos[1:]:
                if bloco.strip():
                    d = _destino(indicadores, pos, bloco.split('|'), erros)
                    if d:
                        destinos.append(d)
        else:
            partes = [p.strip() for p in texto_linha.split('|')]
            rotulo = partes[0]
            if len(partes) > 1 and partes[1]:
                d = _destino(indicadores, pos, partes[1:4], erros)
                if d:
                    destinos.append(d)
        linhas.append({'pos': pos, 'rotulo': rotulo or f'Posição {pos}', 'destinos': destinos,
                       'destino': '; '.join(descrever(d) for d in destinos)})
    if not linhas:
        erros.append('O modelo está vazio.')
    return linhas, erros


def interpretar_valores(texto):
    """Um número por linha (aceita "rótulo<TAB>número" e vírgula decimal). Linha vazia é uma posição sem valor (None).
    Retorna (valores, erros)."""
    valores, erros = [], []
    for n, bruto in enumerate((texto or '').splitlines(), start=1):
        t = bruto.strip()
        token = re.split(r'[\t;]+|\s{2,}', t)[-1].strip().replace('%', '').replace(' ', '') if t else ''
        if not token:
            valores.append(None)
            continue
        if ',' in token:
            token = token.replace('.', '').replace(',', '.')
        try:
            valores.append(Decimal(token))
        except InvalidOperation:
            erros.append(f'Linha {n} da colagem: "{bruto.strip()}" não é um número.')
    return valores, erros


def _acumular(contribuicoes):
    """Combina as contribuições de uma mesma variável, na ordem das posições: + soma, - subtrai, = substitui."""
    total = Decimal(0)
    for op, v in contribuicoes:
        total = v if op == '=' else (total - v if op == '-' else total + v)
    return total


def aplicar(linhas, valores, gran, data, usuario, gravar):
    """Distribui os valores pelos destinos. Retorna dict(itens, avisos, salvos). Sem `gravar`, só simula."""
    from kpi.views import _normalizar

    periodo = _normalizar(gran, data)
    # (indicador, setor) -> {variável ('' = valor do indicador): [(op, valor × fator)]}
    grupos = OrderedDict()
    for linha, valor in zip(linhas, valores):
        if valor is None:
            continue  # posição colada em branco: não alimenta nada
        for d in linha['destinos']:
            grupos.setdefault((d['ind'], d['setor']), OrderedDict()).setdefault(d['variavel'], []).append((d['op'], valor * d['fator']))
    itens, avisos, salvos = [], [], 0
    with transaction.atomic():
        for (ind, setor), por_variavel in grupos.items():
            if not ind.permite_valor(gran):
                avisos.append(f'"{ind.nome}" não tem o gráfico {gran} habilitado: ignorado.')
                continue
            atual = Medicao.objects.filter(indicador=ind, setor=setor, periodo=periodo, granularidade=gran).first()
            dados = {k: Decimal(str(v)) for k, v in (atual.dados or {}).items()} if atual else {}
            valor = None
            for variavel, contribs in por_variavel.items():
                total = _acumular(contribs)
                if variavel:
                    dados[variavel] = total
                else:
                    valor = total
            if valor is None and ind.formula:
                try:
                    valor = calculo.calcular(ind.formula, dados)
                except ZeroDivisionError:
                    avisos.append(f'"{ind.nome}": divisão por zero na memória de cálculo.')
                    continue
                except ValueError as e:
                    avisos.append(f'"{ind.nome}": {e} — ainda faltam variáveis; nada foi gravado para ele.')
                    continue
            if valor is None:
                avisos.append(f'"{ind.nome}" não tem fórmula: use o destino "Valor" para informar o número dele.')
                continue
            itens.append({'ind': ind, 'setor': setor, 'dados': dados, 'valor': valor, 'existe': atual is not None})
            if gravar:
                Medicao.objects.update_or_create(
                    indicador=ind, setor=setor, periodo=periodo, granularidade=gran,
                    defaults={'valor': valor, 'dados': {k: str(v) for k, v in dados.items()}, 'registrado_por': usuario,
                              'observacao': atual.observacao if atual else 'Colagem'})
                salvos += 1
                if gran == 'diaria':
                    consolidacao.consolidar_valores(ind, setor.pk if setor else None, [periodo], usuario)
    return {'itens': itens, 'avisos': avisos, 'salvos': salvos, 'periodo': periodo}

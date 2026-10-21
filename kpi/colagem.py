"""Registro por colagem: o usuário cola uma lista de números e o modelo (posição -> indicador/variável) distribui os valores.

Modelo (texto, uma linha por posição): ``Rótulo | Indicador | Variável | Setor``.
- Só o rótulo: a posição é lida na colagem, mas não alimenta nenhum indicador.
- Variável vazia ou "Valor": o número é o valor do indicador.
- Setor é opcional (vazio = acompanhamento geral).
"""
import re
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.db import transaction

from kpi import calculo, consolidacao
from kpi.models import Indicador, Medicao


def interpretar_modelo(texto):
    """Retorna (linhas, erros). Cada linha: dict(pos, rotulo, ind, variavel, setor, destino)."""
    indicadores = {i.nome.strip().lower(): i for i in Indicador.objects.prefetch_related('setores')}
    linhas, erros = [], []
    for texto_linha in (texto or '').splitlines():
        if not texto_linha.strip():
            continue
        partes = [p.strip() for p in texto_linha.split('|')] + ['', '', '', '']
        rotulo, nome_ind, variavel, nome_setor = partes[:4]
        pos = len(linhas) + 1
        linha = {'pos': pos, 'rotulo': rotulo or f'Posição {pos}', 'ind': None, 'variavel': '', 'setor': None, 'destino': ''}
        if nome_ind:
            ind = indicadores.get(nome_ind.lower())
            if not ind:
                erros.append(f'Linha {pos}: indicador "{nome_ind}" não encontrado.')
            else:
                linha['ind'] = ind
                if variavel and variavel.lower() != 'valor':
                    campos = {c.lower(): c for c in calculo.lista_campos(ind)}
                    if variavel.lower() not in campos:
                        erros.append(f'Linha {pos}: "{variavel}" não é variável de "{ind.nome}" (variáveis: {", ".join(campos.values()) or "nenhuma"}).')
                    else:
                        linha['variavel'] = campos[variavel.lower()]
                if nome_setor:
                    setor = next((s for s in ind.setores.all() if s.nome.strip().lower() == nome_setor.lower()), None)
                    if not setor:
                        erros.append(f'Linha {pos}: setor "{nome_setor}" não cadastrado em "{ind.nome}".')
                    linha['setor'] = setor
                linha['destino'] = f'{ind.nome} · ' + (linha['variavel'] or 'Valor') + (f' · {linha["setor"].nome}' if linha['setor'] else '')
        linhas.append(linha)
    if not linhas:
        erros.append('O modelo está vazio.')
    return linhas, erros


def interpretar_valores(texto):
    """Um número por linha (aceita "rótulo<TAB>número" e vírgula decimal). Retorna (valores, erros)."""
    valores, erros = [], []
    for n, bruto in enumerate((texto or '').splitlines(), start=1):
        t = bruto.strip()
        if not t:
            continue
        token = re.split(r'[\t;]+|\s{2,}', t)[-1].strip().replace('%', '').replace(' ', '')
        if ',' in token:
            token = token.replace('.', '').replace(',', '.')
        try:
            valores.append(Decimal(token))
        except InvalidOperation:
            erros.append(f'Linha {n} da colagem: "{bruto.strip()}" não é um número.')
    return valores, erros


def aplicar(linhas, valores, gran, data, usuario, gravar):
    """Distribui os valores pelas variáveis. Retorna dict(itens, avisos, salvos). Sem `gravar`, só simula."""
    from kpi.views import _normalizar

    periodo = _normalizar(gran, data)
    grupos = OrderedDict()
    for linha, valor in zip(linhas, valores):
        if linha['ind']:
            grupos.setdefault((linha['ind'], linha['setor']), []).append((linha, valor))
    itens, avisos, salvos = [], [], 0
    with transaction.atomic():
        for (ind, setor), pares in grupos.items():
            if not ind.permite_valor(gran):
                avisos.append(f'"{ind.nome}" não tem o gráfico {gran} habilitado: ignorado.')
                continue
            atual = Medicao.objects.filter(indicador=ind, setor=setor, periodo=periodo, granularidade=gran).first()
            dados = {k: Decimal(str(v)) for k, v in (atual.dados or {}).items()} if atual else {}
            valor_direto = None
            for linha, v in pares:
                if linha['variavel']:
                    dados[linha['variavel']] = v
                else:
                    valor_direto = v
            valor = valor_direto
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
                avisos.append(f'"{ind.nome}" não tem fórmula: use a posição "Valor" para informar o número dele.')
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

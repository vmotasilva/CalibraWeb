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
import threading
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from kpi import calculo, compartilhamento, consolidacao
from kpi.models import Indicador, LoteColagem, Medicao, SetorIndicador

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
    """Um número por linha (aceita "rótulo<TAB>número" e vírgula decimal). Linha vazia é uma posição sem valor (None), que vale 0 ao distribuir.
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


_ativo = threading.local()


def _foto(med):
    return {'valor': str(med.valor), 'dados': {k: str(v) for k, v in (med.dados or {}).items()},
            'observacao': med.observacao, 'registrado_por_id': med.registrado_por_id}


def _chave(med):
    return (med.indicador_id, med.setor_id, med.granularidade, med.periodo.isoformat())


class _Gravador:
    """Anota o estado anterior de toda Medicao criada, alterada ou apagada enquanto a colagem grava
    (inclui o que a propagação entre indicadores e a consolidação semanal/mensal mexem)."""

    def __init__(self):
        self.antes = OrderedDict()

    def __enter__(self):
        _ativo.gravador = self
        return self

    def __exit__(self, *exc):
        _ativo.gravador = None

    def anotar(self, med, existente):
        self.antes.setdefault(_chave(med), _foto(existente) if existente else None)

    def alteracoes(self):
        """Lista de {antes, depois} para cada medição cujo valor final difere do inicial."""
        saida = []
        for (ind_id, setor_id, gran, periodo), antes in self.antes.items():
            atual = Medicao.objects.select_related('indicador', 'setor').filter(
                indicador_id=ind_id, setor_id=setor_id, granularidade=gran, periodo=periodo).first()
            depois = _foto(atual) if atual else None
            if antes == depois or (antes and depois and Decimal(antes['valor']) == Decimal(depois['valor'])
                                   and _dados(antes) == _dados(depois)):
                continue
            ind = atual.indicador if atual else Indicador.objects.filter(pk=ind_id).first()
            setor = atual.setor if atual else (SetorIndicador.objects.filter(pk=setor_id).first() if setor_id else None)
            saida.append({'indicador_id': ind_id, 'indicador': ind.nome if ind else f'#{ind_id}',
                          'setor_id': setor_id, 'setor': setor.nome if setor else '',
                          'granularidade': gran, 'periodo': periodo, 'antes': antes, 'depois': depois})
        return saida


def _dados(foto):
    return {k: Decimal(v) for k, v in foto['dados'].items()}


@receiver(pre_save, sender=Medicao)
def _antes_de_salvar(sender, instance, **kwargs):
    gravador = getattr(_ativo, 'gravador', None)
    if gravador:
        gravador.anotar(instance, Medicao.objects.filter(pk=instance.pk).first() if instance.pk else None)


@receiver(pre_delete, sender=Medicao)
def _antes_de_apagar(sender, instance, **kwargs):
    gravador = getattr(_ativo, 'gravador', None)
    if gravador:
        gravador.anotar(instance, instance)


def desfazer(lote, usuario, forcar=False):
    """Restaura as medições de um lote ao estado anterior à colagem.
    Se alguma foi alterada depois da colagem, não faz nada e devolve os conflitos, a menos que `forcar`.
    Retorna dict(conflitos, restauradas)."""
    conflitos, atuais = [], []
    for alt in lote.alteracoes:
        atual = Medicao.objects.filter(indicador_id=alt['indicador_id'], setor_id=alt['setor_id'],
                                       granularidade=alt['granularidade'], periodo=alt['periodo']).first()
        atuais.append(atual)
        depois = alt['depois']
        igual = (atual is None and depois is None) or (
            atual is not None and depois is not None and atual.valor == Decimal(depois['valor'])
            and _dados(_foto(atual)) == _dados(depois))
        if not igual:
            conflitos.append(alt)
    if conflitos and not forcar:
        return {'conflitos': conflitos, 'restauradas': 0}
    restauradas = 0
    with transaction.atomic():
        for alt, atual in zip(lote.alteracoes, atuais):
            antes = alt['antes']
            chave = dict(indicador_id=alt['indicador_id'], setor_id=alt['setor_id'],
                         granularidade=alt['granularidade'], periodo=alt['periodo'])
            if antes is None:
                if atual:
                    atual.delete()
                    restauradas += 1
            elif Indicador.objects.filter(pk=alt['indicador_id']).exists():
                Medicao.objects.update_or_create(**chave, defaults={
                    'valor': Decimal(antes['valor']), 'dados': antes['dados'], 'observacao': antes['observacao'],
                    'registrado_por_id': antes['registrado_por_id']})
                restauradas += 1
        lote.desfeito_em, lote.desfeito_por = timezone.now(), usuario
        lote.save(update_fields=['desfeito_em', 'desfeito_por'])
    return {'conflitos': conflitos, 'restauradas': restauradas}


def aplicar(linhas, valores, gran, data, usuario, gravar, modelo=None, texto=''):
    """Distribui os valores pelos destinos. Retorna dict(itens, avisos, salvos, lote). Sem `gravar`, só simula.
    Ao gravar, cria um LoteColagem com o antes/depois das medições para permitir desfazer."""
    from kpi.views import _normalizar

    periodo = _normalizar(gran, data)
    gravador = _Gravador() if gravar else None
    if gravador:
        gravador.__enter__()
    try:
        res = _aplicar(linhas, valores, gran, periodo, usuario, gravar)
        if gravador:
            alteracoes = gravador.alteracoes()
            if alteracoes:
                res['lote'] = LoteColagem.objects.create(
                    modelo=modelo, modelo_nome=modelo.nome if modelo else '', granularidade=gran, periodo=periodo,
                    texto=texto or '', alteracoes=alteracoes, criado_por=usuario)
    finally:
        if gravador:
            gravador.__exit__()
    return res


def _aplicar(linhas, valores, gran, periodo, usuario, gravar):
    # (indicador, setor) -> {variável ('' = valor do indicador): [(op, valor × fator)]}
    grupos = OrderedDict()
    for linha, valor in zip(linhas, valores):
        if valor is None:
            valor = Decimal(0)  # posição colada em branco vale 0
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
                dados = compartilhamento.completar(ind, setor, gran, periodo, dados)
                try:
                    valor = calculo.calcular_ou_none(ind.formula, dados)
                    if valor is None:
                        avisos.append(f'"{ind.nome}": sem dado (divisão por zero na memória de cálculo); nada foi gravado para ele.')
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
                compartilhamento.propagar(ind, setor, gran, periodo, dados, usuario)
                consolidacao.consolidar(ind, setor.pk if setor else None, gran, [periodo], usuario)
    return {'itens': itens, 'avisos': avisos, 'salvos': salvos, 'periodo': periodo}

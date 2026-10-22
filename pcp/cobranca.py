"""Cobrança do PCP no sino de notificações: verificações pendentes nos turnos em andamento e tratativas em aberto."""
import datetime

from django.core.cache import cache
from django.utils import timezone

from pcp import pendencias as pend
from pcp.models import FormularioVersao, Ocorrencia, Turno


def turnos_iniciados(agora=None):
    """[(data, turno)] dos turnos ativos que já começaram (inclusive o que atravessa a meia-noite e ainda está em curso).

    Turno sem horário cadastrado conta como iniciado hoje."""
    agora = agora or timezone.localtime()
    hoje, hora = agora.date(), agora.time()
    saida = []
    for t in Turno.objects.filter(ativo=True):
        if not (t.inicio and t.fim):
            saida.append((hoje, t))
        elif hora >= t.inicio:
            saida.append((hoje, t))
        elif t.fim < t.inicio and hora < t.fim:  # madrugada de um turno que começou ontem
            saida.append((hoje - datetime.timedelta(days=1), t))
    return saida


def pendentes_em_andamento(agora=None):
    """Quantidade de verificações devidas e ainda não feitas nos turnos iniciados.

    Itens de frequência por turno contam uma vez por turno; os demais (diária, semanal…) uma só vez."""
    por_data = {}
    for data, turno in turnos_iniciados(agora):
        por_data.setdefault(data, []).append(turno)
    chaves = set()
    versoes = FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
    for versao in versoes:
        for pagina in versao.paginas.filter(ativo=True).prefetch_related('campos__frequencia'):
            periodicidade = {c.pk: c.frequencia.periodicidade for c in pagina.campos.all() if c.frequencia_id}
            for data, turnos in por_data.items():
                for turno_id, campos in pend.avaliar_pagina(pagina, data, turnos).items():
                    for campo_id, feito in campos.items():
                        if feito:
                            continue
                        por_turno = periodicidade.get(campo_id) == 'turno'
                        chaves.add((campo_id, data, turno_id) if por_turno else (campo_id,))
    return len(chaves)


def tratativas_abertas():
    return Ocorrencia.objects.filter(tipo=Ocorrencia.TRATATIVA, status=Ocorrencia.ABERTA).count()


def contagens():
    """{'pendencias': n, 'tratativas': m}, com cache curto compartilhado entre os usuários."""
    chave = 'pcp_cobranca:v1'
    dados = cache.get(chave)
    if not isinstance(dados, dict):
        dados = {'pendencias': pendentes_em_andamento(), 'tratativas': tratativas_abertas()}
        cache.set(chave, dados, timeout=60)
    return dados

"""Cálculo das verificações devidas e pendentes por página, data e turno.

Uma verificação é "devida" quando o campo tem frequência cadastrada com periodicidade fixa; está "feita" quando
existe resposta para o item dentro da janela da periodicidade que contém a data:

- turno: a própria data e o próprio turno;      - diária: a própria data (qualquer turno);
- semanal: semana de segunda a domingo;         - quinzenal: janela móvel dos 14 dias até a data;
- mensal / trimestral / semestral / anual: período de calendário que contém a data.

Frequências "sob demanda / por evento" (ou campo sem frequência) nunca ficam pendentes.
O histórico é casado entre revisões do formulário pelo trio (item, etapa, descrição) dentro da página de mesmo nome,
para que uma nova revisão não "zere" verificações mensais já feitas.
"""
import calendar
import datetime
from collections import defaultdict

from pcp.models import FormularioVersao, Resposta


def janela(periodicidade, data):
    """(início, fim) da janela em que uma resposta cumpre a frequência na data; None quando não há prazo fixo."""
    if periodicidade in ('turno', 'diaria'):
        return data, data
    if periodicidade == 'semanal':
        ini = data - datetime.timedelta(days=data.weekday())
        return ini, ini + datetime.timedelta(days=6)
    if periodicidade == 'quinzenal':
        return data - datetime.timedelta(days=13), data
    if periodicidade == 'mensal':
        return data.replace(day=1), data.replace(day=calendar.monthrange(data.year, data.month)[1])
    meses = {'trimestral': 3, 'semestral': 6, 'anual': 12}.get(periodicidade)
    if meses:
        m0 = ((data.month - 1) // meses) * meses + 1
        m1 = m0 + meses - 1
        return datetime.date(data.year, m0, 1), datetime.date(data.year, m1, calendar.monthrange(data.year, m1)[1])
    return None


def chave(item, etapa, descricao):
    return (item or '', etapa or '', descricao or '')


def avaliar_pagina(pagina, data, turnos):
    """{turno_id: {campo_id: feito(bool)}} só com os campos devidos naquele turno."""
    campos = [c for c in pagina.campos.all() if c.ativo and c.frequencia_id and c.frequencia.periodicidade != 'evento']
    resultado = {t.pk: {} for t in turnos}
    janelas = {c.pk: janela(c.frequencia.periodicidade, data) for c in campos}
    campos = [c for c in campos if janelas[c.pk]]
    if not campos:
        return resultado
    inicio = min(janelas[c.pk][0] for c in campos)
    fim = max(janelas[c.pk][1] for c in campos)
    feitos = defaultdict(set)  # chave -> {(data, turno_id)}
    qs = (Resposta.objects
          .filter(verificacao__pagina__versao__formulario_id=pagina.versao.formulario_id,
                  verificacao__pagina__nome=pagina.nome, verificacao__data__range=(inicio, fim))
          .exclude(valor='')
          .values_list('campo__item', 'campo__etapa', 'campo__descricao', 'verificacao__data', 'verificacao__turno_id'))
    for item, etapa, desc, d, t in qs:
        feitos[chave(item, etapa, desc)].add((d, t))
    for turno in turnos:
        for c in campos:
            registros = feitos[chave(c.item, c.etapa, c.descricao)]
            if c.frequencia.periodicidade == 'turno':
                feito = (data, turno.pk) in registros
            else:
                ini, fim_c = janelas[c.pk]
                feito = any(ini <= d <= fim_c for d, _ in registros)
            resultado[turno.pk][c.pk] = feito
    return resultado


def painel(data, turnos, formulario_id=None):
    """Matriz página x turno das vigentes: lista de blocos por formulário com contagens de devidos/pendentes."""
    versoes = (FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
               .select_related('formulario__setor').order_by('formulario__codigo'))
    if formulario_id:
        versoes = versoes.filter(formulario_id=formulario_id)
    blocos, total_devidos, total_feitos = [], 0, 0
    for versao in versoes:
        grupos = {}
        paginas = (versao.paginas.filter(ativo=True).prefetch_related('campos__frequencia'))
        b_devidos = b_feitos = 0
        for pagina in paginas:
            por_turno = avaliar_pagina(pagina, data, turnos)
            celulas = []
            for t in turnos:
                devidos = len(por_turno[t.pk])
                feitos = sum(por_turno[t.pk].values())
                celulas.append({'turno': t, 'devidos': devidos, 'feitos': feitos, 'pendentes': devidos - feitos})
            b_devidos += sum(c['devidos'] for c in celulas)
            b_feitos += sum(c['feitos'] for c in celulas)
            grupos.setdefault(pagina.grupo or 'Sem grupo', []).append({'pagina': pagina, 'celulas': celulas})
        blocos.append({'versao': versao, 'grupos': grupos, 'devidos': b_devidos, 'feitos': b_feitos,
                       'percentual': round(100 * b_feitos / b_devidos) if b_devidos else None})
        total_devidos += b_devidos
        total_feitos += b_feitos
    return {'blocos': blocos, 'devidos': total_devidos, 'feitos': total_feitos, 'pendentes': total_devidos - total_feitos,
            'percentual': round(100 * total_feitos / total_devidos) if total_devidos else None}

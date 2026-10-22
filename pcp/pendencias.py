"""Cálculo das verificações devidas e pendentes por página, data e turno.

Uma verificação é "devida" quando o campo tem frequência cadastrada com periodicidade fixa; está "feita" quando
existe resposta para o item dentro da janela da periodicidade que contém a data:

- turno: a própria data e o próprio turno;      - diária: a própria data (qualquer turno);
- semanal: semana de segunda a domingo;         - quinzenal: quinzena civil (dias 1-15 ou 16-fim do mês);
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
        if data.day <= 15:
            return data.replace(day=1), data.replace(day=15)
        return data.replace(day=16), data.replace(day=calendar.monthrange(data.year, data.month)[1])
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
        blocos.append({'versao': versao, 'grupos': versao.formulario.ordenar_grupos(grupos), 'devidos': b_devidos, 'feitos': b_feitos,
                       'percentual': round(100 * b_feitos / b_devidos) if b_devidos else None})
        total_devidos += b_devidos
        total_feitos += b_feitos
    return {'blocos': blocos, 'devidos': total_devidos, 'feitos': total_feitos, 'pendentes': total_devidos - total_feitos,
            'percentual': round(100 * total_feitos / total_devidos) if total_devidos else None}


# --------------------------------------------------------------------------------------
# Atrasos: verificações devidas cujo prazo já encerrou sem resposta
# --------------------------------------------------------------------------------------

def inicio_rastreio(formulario):
    """Primeira data de vigência do formulário: antes dela nada é cobrado (ex.: formulário recém-implantado)."""
    datas = [v.vigencia for v in formulario.versoes.all() if v.vigencia]
    return min(datas) if datas else None


def _janelas_do_campo(campo, ini, fim, turnos):
    """[(inicio, fim, turno|None)] das janelas de prazo do campo que terminam dentro de [ini, fim]."""
    per = campo.frequencia.periodicidade
    dias = [ini + datetime.timedelta(days=n) for n in range((fim - ini).days + 1)]
    if per == 'turno':
        return [(d, d, t) for d in dias for t in turnos]
    janelas = {}
    for d in dias:
        j = janela(per, d)
        if j and ini <= j[1] <= fim:
            janelas[j] = None
    return [(a, b, None) for a, b in janelas]


def atrasos_pagina(pagina, ini, fim, turnos, hoje=None, rastreio=None):
    """Lista de atrasos da página no período: dicts {campo, inicio, fim, turno}. Só janelas já encerradas (antes de hoje)."""
    hoje = hoje or datetime.date.today()
    fim = min(fim, hoje - datetime.timedelta(days=1))
    if rastreio:
        ini = max(ini, rastreio)
    campos = [c for c in pagina.campos.all() if c.ativo and c.frequencia_id and c.frequencia.periodicidade != 'evento']
    if not campos or ini > fim:
        return [], 0
    todas = []
    for c in campos:
        for a, b, t in _janelas_do_campo(c, ini, fim, turnos):
            todas.append((c, a, b, t))
    if not todas:
        return [], 0
    feitos = defaultdict(set)
    qs = (Resposta.objects
          .filter(verificacao__pagina__versao__formulario_id=pagina.versao.formulario_id,
                  verificacao__pagina__nome=pagina.nome,
                  verificacao__data__range=(min(a for _, a, _, _ in todas), max(b for _, _, b, _ in todas)))
          .exclude(valor='')
          .values_list('campo__item', 'campo__etapa', 'campo__descricao', 'verificacao__data', 'verificacao__turno_id'))
    for item, etapa, desc, d, t in qs:
        feitos[chave(item, etapa, desc)].add((d, t))
    atrasos = []
    for c, a, b, t in todas:
        registros = feitos[chave(c.item, c.etapa, c.descricao)]
        if t is not None:
            feito = (a, t.pk) in registros
        else:
            feito = any(a <= d <= b for d, _ in registros)
        if not feito:
            atrasos.append({'campo': c, 'inicio': a, 'fim': b, 'turno': t})
    return atrasos, len(todas)


def painel_atrasos(ini, fim, turnos, formulario_id=None, hoje=None):
    """Matriz página x data dos atrasos do período, por formulário vigente."""
    hoje = hoje or datetime.date.today()
    fim = min(fim, hoje - datetime.timedelta(days=1))
    datas = [ini + datetime.timedelta(days=n) for n in range((fim - ini).days + 1)] if ini <= fim else []
    versoes = (FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
               .select_related('formulario__setor').order_by('formulario__codigo'))
    if formulario_id:
        versoes = versoes.filter(formulario_id=formulario_id)
    blocos, t_devidos, t_atrasos = [], 0, 0
    for versao in versoes:
        rastreio = inicio_rastreio(versao.formulario)
        grupos, b_devidos, b_atrasos = {}, 0, 0
        for pagina in versao.paginas.filter(ativo=True).prefetch_related('campos__frequencia'):
            atrasos, devidos = atrasos_pagina(pagina, ini, fim, turnos, hoje, rastreio)
            por_data = {}
            for a in atrasos:
                cel = por_data.setdefault(a['fim'], {'n': 0, 'turno': a['turno']})
                cel['n'] += 1
                cel['turno'] = cel['turno'] or a['turno']
            b_devidos += devidos
            b_atrasos += len(atrasos)
            grupos.setdefault(pagina.grupo or 'Sem grupo', []).append({
                'pagina': pagina, 'por_data': por_data, 'celulas': [(d, por_data.get(d)) for d in datas],
                'devidos': devidos, 'atrasados': len(atrasos),
                'percentual': round(100 * (devidos - len(atrasos)) / devidos) if devidos else None})
        blocos.append({'versao': versao, 'grupos': versao.formulario.ordenar_grupos(grupos), 'devidos': b_devidos, 'atrasados': b_atrasos, 'rastreio': rastreio,
                       'percentual': round(100 * (b_devidos - b_atrasos) / b_devidos) if b_devidos else None})
        t_devidos += b_devidos
        t_atrasos += b_atrasos
    return {'datas': datas, 'blocos': blocos, 'devidos': t_devidos, 'atrasados': t_atrasos,
            'percentual': round(100 * (t_devidos - t_atrasos) / t_devidos) if t_devidos else None}

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

from pcp.models import FormularioVersao, Resposta, Turno, Verificacao


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


def slots_parados(pagina, ini, fim):
    """{(data, turno_id): status} dos turnos em que a máquina (página) foi marcada como em manutenção ou parada.
    Vale para as páginas de mesmo nome em qualquer revisão do formulário."""
    qs = (Verificacao.objects.filter(pagina__versao__formulario_id=pagina.versao.formulario_id, pagina__nome=pagina.nome,
                                     data__range=(ini, fim))
          .exclude(status='').values_list('data', 'turno_id', 'status'))
    return {(d, t): s for d, t, s in qs}


def _janela_dispensada(parados, turnos, ini, fim):
    """True se a máquina esteve em manutenção/parada em TODOS os turnos de todos os dias da janela [ini, fim]."""
    dia = ini
    while dia <= fim:
        if any((dia, t.pk) not in parados for t in turnos):
            return False
        dia += datetime.timedelta(days=1)
    return bool(turnos)


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
    parados = slots_parados(pagina, inicio, data)
    ativos = list(Turno.objects.filter(ativo=True)) if parados else []
    dispensa_janela = {}
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
            ini, fim_c = janelas[c.pk]
            if c.frequencia.periodicidade == 'turno':
                if (data, turno.pk) in parados:
                    continue  # máquina em manutenção/parada neste turno: item dispensado (não é devido)
                feito = (data, turno.pk) in registros
            else:
                if parados:
                    janela_ = (ini, min(fim_c, data))
                    if janela_ not in dispensa_janela:
                        dispensa_janela[janela_] = _janela_dispensada(parados, ativos, *janela_)
                    if dispensa_janela[janela_]:
                        continue  # parada/manutenção em todos os turnos da janela até a data: dispensado
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
            parados = slots_parados(pagina, data, data)
            celulas = []
            for t in turnos:
                devidos = len(por_turno[t.pk])
                feitos = sum(por_turno[t.pk].values())
                status = parados.get((data, t.pk), '')
                celulas.append({'turno': t, 'devidos': devidos, 'feitos': feitos, 'pendentes': devidos - feitos, 'status': status,
                                'status_rotulo': dict(Verificacao.STATUS_MAQUINA).get(status, '')})
            b_devidos += sum(c['devidos'] for c in celulas)
            b_feitos += sum(c['feitos'] for c in celulas)
            campos = {c.pk: c for c in pagina.campos.all()}
            itens = []   # itens especificamente pendentes (com os turnos em que faltam)
            for pk in sorted({pk for t in turnos for pk, ok in por_turno[t.pk].items() if not ok}, key=lambda pk: (campos[pk].ordem, pk)):
                itens.append({'campo': campos[pk], 'turnos': [t for t in turnos if por_turno[t.pk].get(pk) is False]})
            grupos.setdefault(pagina.grupo or 'Sem grupo', []).append({'pagina': pagina, 'celulas': celulas, 'itens': itens})
        blocos.append({'versao': versao, 'grupos': versao.formulario.ordenar_grupos(grupos), 'devidos': b_devidos, 'feitos': b_feitos, 'pendentes': b_devidos - b_feitos,
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


def avaliar_janelas(pagina, ini, fim, turnos, hoje=None, rastreio=None):
    """[(campo, inicio, fim, turno|None, feito)] das janelas de prazo da página já encerradas (antes de hoje) no período.
    Janelas dispensadas (máquina em manutenção/parada) ficam de fora; `feito` indica se houve lançamento dentro do prazo."""
    hoje = hoje or datetime.date.today()
    fim = min(fim, hoje - datetime.timedelta(days=1))
    if rastreio:
        ini = max(ini, rastreio)
    campos = [c for c in pagina.campos.all() if c.ativo and c.frequencia_id and c.frequencia.periodicidade != 'evento']
    if not campos or ini > fim:
        return []
    todas = []
    for c in campos:
        for a, b, t in _janelas_do_campo(c, ini, fim, turnos):
            todas.append((c, a, b, t))
    if not todas:
        return []
    parados = slots_parados(pagina, min(a for _, a, _, _ in todas), max(b for _, _, b, _ in todas))
    if parados:  # máquina em manutenção/parada: o prazo não é devido
        dispensa = {}
        validas = []
        for c, a, b, t in todas:
            if t is not None:
                dispensado = (a, t.pk) in parados
            else:
                if (a, b) not in dispensa:
                    dispensa[(a, b)] = _janela_dispensada(parados, turnos, a, b)
                dispensado = dispensa[(a, b)]
            if not dispensado:
                validas.append((c, a, b, t))
        todas = validas
        if not todas:
            return []
    feitos = defaultdict(set)
    qs = (Resposta.objects
          .filter(verificacao__pagina__versao__formulario_id=pagina.versao.formulario_id,
                  verificacao__pagina__nome=pagina.nome,
                  verificacao__data__range=(min(a for _, a, _, _ in todas), max(b for _, _, b, _ in todas)))
          .exclude(valor='')
          .values_list('campo__item', 'campo__etapa', 'campo__descricao', 'verificacao__data', 'verificacao__turno_id'))
    for item, etapa, desc, d, t in qs:
        feitos[chave(item, etapa, desc)].add((d, t))
    avaliadas = []
    for c, a, b, t in todas:
        registros = feitos[chave(c.item, c.etapa, c.descricao)]
        if t is not None:
            feito = (a, t.pk) in registros
        else:
            feito = any(a <= d <= b for d, _ in registros)
        avaliadas.append((c, a, b, t, feito))
    return avaliadas


def atrasos_pagina(pagina, ini, fim, turnos, hoje=None, rastreio=None):
    """Lista de atrasos da página no período: dicts {campo, inicio, fim, turno}. Só janelas já encerradas (antes de hoje)."""
    avaliadas = avaliar_janelas(pagina, ini, fim, turnos, hoje, rastreio)
    atrasos = [{'campo': c, 'inicio': a, 'fim': b, 'turno': t} for c, a, b, t, feito in avaliadas if not feito]
    return atrasos, len(avaliadas)


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


# --------------------------------------------------------------------------------------
# Dashboard: cumprimento por página e frequência
# --------------------------------------------------------------------------------------
ORDEM_PERIODICIDADE = ['turno', 'diaria', 'semanal', 'quinzenal', 'mensal', 'trimestral', 'semestral', 'anual']


def _pct(feitos, devidos):
    return round(100 * feitos / devidos) if devidos else None


def dashboard(ini, fim, turnos, formulario_id=None, hoje=None):
    """Cumprimento das verificações com prazo encerrado no período, por página e por frequência (dados simples, prontos para cache).

    Cada verificação devida conta uma vez por prazo (turno, dia, semana, mês...); janelas em que a máquina esteve em manutenção/parada
    não entram. `colunas` lista as frequências existentes; cada linha de página traz `celulas` alinhadas a elas."""
    hoje = hoje or datetime.date.today()
    fim = min(fim, hoje - datetime.timedelta(days=1))
    versoes = list(FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
                   .select_related('formulario__setor').order_by('formulario__codigo'))
    if formulario_id:
        versoes = [v for v in versoes if v.formulario_id == int(formulario_id)]
    freq_info, serie, por_freq_total = {}, defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    itens_acc, itens_info = defaultdict(lambda: [0, 0]), {}
    brutos = []
    for versao in versoes:
        rastreio = inicio_rastreio(versao.formulario)
        grupos = {}
        for pagina in versao.paginas.filter(ativo=True).prefetch_related('campos__frequencia'):
            por_freq = defaultdict(lambda: [0, 0])
            for campo, a, b, t, feito in avaliar_janelas(pagina, ini, fim, turnos, hoje, rastreio):
                f = campo.frequencia
                freq_info[f.pk] = {'pk': f.pk, 'nome': f.nome, 'periodicidade': f.periodicidade, 'ordem': f.ordem}
                por_freq[f.pk][0] += 1
                por_freq[f.pk][1] += int(feito)
                por_freq_total[f.pk][0] += 1
                por_freq_total[f.pk][1] += int(feito)
                serie[b][0] += 1
                serie[b][1] += int(feito)
                itens_acc[campo.pk][0] += 1
                itens_acc[campo.pk][1] += int(feito)
                if campo.pk not in itens_info:
                    itens_info[campo.pk] = {
                        'campo_id': campo.pk, 'numero': campo.ordem, 'pagina_id': pagina.pk, 'pagina': pagina.nome, 'codigo': versao.formulario.codigo,
                        'item': campo.item, 'descricao': campo.descricao[:90], 'etapa': campo.etapa[:60], 'frequencia': f.nome,
                        'critico': campo.critico}
            grupos.setdefault(pagina.grupo or 'Sem grupo', []).append((pagina, dict(por_freq)))
        brutos.append((versao, versao.formulario.ordenar_grupos(grupos)))

    colunas = sorted(freq_info.values(), key=lambda f: (ORDEM_PERIODICIDADE.index(f['periodicidade']) if f['periodicidade'] in ORDEM_PERIODICIDADE else 99,
                                                        f['ordem'], f['nome']))
    blocos, t_dev, t_feit = [], 0, 0
    for versao, grupos in brutos:
        b_dev = b_feit = 0
        lista_grupos = []
        for nome_grupo, paginas in grupos.items():
            linhas = []
            for pagina, por_freq in paginas:
                dev = sum(v[0] for v in por_freq.values())
                feit = sum(v[1] for v in por_freq.values())
                b_dev += dev
                b_feit += feit
                celulas = [({'devidos': por_freq[c['pk']][0], 'feitos': por_freq[c['pk']][1], 'pct': _pct(por_freq[c['pk']][1], por_freq[c['pk']][0])}
                            if c['pk'] in por_freq else None) for c in colunas]
                linhas.append({'pagina_id': pagina.pk, 'nome': pagina.nome, 'devidos': dev, 'feitos': feit, 'atrasados': dev - feit,
                               'pct': _pct(feit, dev), 'celulas': celulas})
            lista_grupos.append({'nome': nome_grupo, 'linhas': linhas})
        blocos.append({'formulario_id': versao.formulario_id, 'versao_id': versao.pk, 'codigo': versao.formulario.codigo, 'titulo': versao.formulario.titulo,
                       'revisao': versao.revisao, 'grupos': lista_grupos, 'devidos': b_dev, 'feitos': b_feit, 'pct': _pct(b_feit, b_dev),
                       'rastreio': inicio_rastreio(versao.formulario)})
        t_dev += b_dev
        t_feit += b_feit

    # evolução: por dia (até 31 dias) ou por semana
    semanal = (fim - ini).days + 1 > 31
    agregada = defaultdict(lambda: [0, 0])
    for dia, (dev, feit) in serie.items():
        chave_ = dia - datetime.timedelta(days=dia.weekday()) if semanal else dia
        agregada[chave_][0] += dev
        agregada[chave_][1] += feit
    evolucao = [{'rotulo': (f'sem. {d:%d/%m}' if semanal else f'{d:%d/%m}'), 'devidos': v[0], 'feitos': v[1], 'pct': _pct(v[1], v[0])}
                for d, v in sorted(agregada.items())]
    por_frequencia = [{'nome': c['nome'], 'devidos': por_freq_total[c['pk']][0], 'feitos': por_freq_total[c['pk']][1],
                       'pct': _pct(por_freq_total[c['pk']][1], por_freq_total[c['pk']][0])} for c in colunas]
    itens = [dict(itens_info[pk], devidos=v[0], feitos=v[1], atrasados=v[0] - v[1], pct=_pct(v[1], v[0])) for pk, v in itens_acc.items()]
    paradas = 0
    if versoes and ini <= fim:
        paradas = (Verificacao.objects.filter(pagina__versao__formulario_id__in=[v.formulario_id for v in versoes], data__range=(ini, fim))
                   .exclude(status='').values('pagina__versao__formulario_id', 'pagina__nome', 'data', 'turno_id').distinct().count())
    return {'ini': ini, 'fim': fim, 'colunas': colunas, 'blocos': blocos, 'evolucao': evolucao, 'por_frequencia': por_frequencia, 'itens': itens,
            'agrupamento': 'semana' if semanal else 'dia',
            'devidos': t_dev, 'feitos': t_feit, 'atrasados': t_dev - t_feit, 'pct': _pct(t_feit, t_dev), 'paradas': paradas}


MIN_PRAZOS_PAGINA = 5
MIN_PRAZOS_ITEM = 3
TOPS = [10, 20, 50]


def ranking(d, ordem='pct', top=10):
    """(páginas, itens) com pior cumprimento do dashboard `d`. ordem 'pct' = menor % primeiro (empate: mais atrasos);
    'atrasos' = mais atrasos primeiro. Páginas/itens com poucos prazos no período ficam de fora."""
    paginas = [dict(l, codigo=b['codigo'], formulario_id=b['formulario_id']) for b in d['blocos'] for g in b['grupos']
               for l in g['linhas'] if l['devidos'] >= MIN_PRAZOS_PAGINA]
    itens = [i for i in d['itens'] if i['devidos'] >= MIN_PRAZOS_ITEM]
    if ordem == 'atrasos':
        chave_ = lambda x: (-x['atrasados'], x['pct'], x['nome'] if 'nome' in x else x['descricao'])  # noqa: E731
    else:
        chave_ = lambda x: (x['pct'], -x['atrasados'], x['nome'] if 'nome' in x else x['descricao'])  # noqa: E731
    return sorted(paginas, key=chave_)[:top], sorted(itens, key=chave_)[:top]


# --------------------------------------------------------------------------------------
# Farol: situação do prazo em andamento por página e frequência
# --------------------------------------------------------------------------------------
VERDE, AMARELO, VERMELHO = 'verde', 'amarelo', 'vermelho'
_GRAVIDADE = {VERDE: 0, AMARELO: 1, VERMELHO: 2}
_MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def rotulo_janela(periodicidade, data):
    """Texto curto do prazo em que `data` está (ex.: '19/10–25/10', 'out/2026', 'jul–set/2026')."""
    ini, fim = janela(periodicidade, data)
    if periodicidade in ('turno', 'diaria'):
        return f'{data:%d/%m}'
    if periodicidade in ('semanal', 'quinzenal'):
        return f'{ini:%d/%m}–{fim:%d/%m}'
    if periodicidade == 'mensal':
        return f'{_MESES[data.month - 1]}/{data.year}'
    if periodicidade in ('trimestral', 'semestral'):
        return f'{_MESES[ini.month - 1]}–{_MESES[fim.month - 1]}/{data.year}'
    return str(data.year)


def _turno_encerrado(turno, agora):
    """Turno de hoje já terminou? Sem horário cadastrado (ou turno que atravessa a meia-noite) conta como em andamento."""
    if turno.inicio and turno.fim and turno.inicio < turno.fim:
        return agora.time() >= turno.fim
    return False


def farol(data_obs, formulario_id=None, hoje=None, agora=None):
    """Situação dos prazos em andamento na data de observação, por página e frequência (dados simples, prontos para cache).

    Para cada frequência olha-se o prazo que contém a data (turno, dia, semana seg-dom, quinzena 1-15/16-fim, mês, trimestre
    Jan-Mar/Abr-Jun/Jul-Set/Out-Dez, semestre Jan-Jun/Jul-Dez, ano). Basta um lançamento em qualquer turno dentro do prazo.
    Verde = cumprido; amarelo = pendente com prazo em aberto; vermelho = pendente com prazo já encerrado.
    Máquina em manutenção/parada dispensa os itens (não entram)."""
    from django.utils import timezone
    agora = agora or timezone.localtime()
    hoje = hoje or agora.date()
    todos = list(Turno.objects.filter(ativo=True))
    if data_obs < hoje:
        consideradas = todos                                   # dia passado: todos os turnos já ocorreram
    elif data_obs == hoje:
        consideradas = [t for d, t in _turnos_iniciados_hoje(agora)]
    else:
        consideradas = []                                      # futuro: nada é devido ainda
    versoes = list(FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
                   .select_related('formulario__setor').order_by('formulario__codigo'))
    if formulario_id:
        versoes = [v for v in versoes if v.formulario_id == int(formulario_id)]
    freq_info, contagem, brutos = {}, {VERDE: 0, AMARELO: 0, VERMELHO: 0}, []
    for versao in versoes:
        rastreio = inicio_rastreio(versao.formulario)
        grupos = {}
        for pagina in versao.paginas.filter(ativo=True).prefetch_related('campos__frequencia'):
            resultado = avaliar_pagina(pagina, data_obs, todos) if todos else {}
            primeiro = todos[0].pk if todos else None
            celulas = {}
            for campo in pagina.campos.all():
                if not (campo.ativo and campo.frequencia_id) or campo.frequencia.periodicidade == 'evento':
                    continue
                per, f = campo.frequencia.periodicidade, campo.frequencia
                fim_prazo = janela(per, data_obs)[1]
                if rastreio and fim_prazo < rastreio:
                    continue                                    # prazo encerrou antes da vigência: não é cobrado
                if per == 'turno':
                    regs = [(t, resultado[t.pk][campo.pk]) for t in consideradas if campo.pk in resultado.get(t.pk, {})]
                else:
                    regs = [(None, resultado[primeiro][campo.pk])] if primeiro and campo.pk in resultado.get(primeiro, {}) else []
                if not regs:
                    continue
                c = celulas.setdefault(f.pk, {'devidos': 0, 'feitos': 0, 'cor': VERDE, 'pendente_encerrado': False})
                freq_info[f.pk] = {'pk': f.pk, 'nome': f.nome, 'periodicidade': per, 'ordem': f.ordem,
                                   'prazo': rotulo_janela(per, data_obs)}
                for turno, feito in regs:
                    c['devidos'] += 1
                    c['feitos'] += int(feito)
                    if feito:
                        continue
                    if per == 'turno':
                        vencido = data_obs < hoje or (data_obs == hoje and _turno_encerrado(turno, agora))
                    else:
                        vencido = fim_prazo < hoje
                    if per == 'diaria':
                        vencido = data_obs < hoje
                    c['pendente_encerrado'] = c['pendente_encerrado'] or vencido
                    c['cor'] = VERMELHO if (vencido or c['cor'] == VERMELHO) else AMARELO
            for f_pk, c in celulas.items():
                c['pendentes'] = c['devidos'] - c['feitos']
                per = freq_info[f_pk]['periodicidade']
                fim_prazo = janela(per, data_obs)[1]
                if c['cor'] == VERDE:
                    c['dica'] = f'Cumprido: {c["feitos"]} de {c["devidos"]} ({freq_info[f_pk]["prazo"]})'
                elif c['cor'] == VERMELHO:
                    c['dica'] = f'Prazo encerrado com {c["pendentes"]} pendente(s) de {c["devidos"]} ({freq_info[f_pk]["prazo"]})'
                else:
                    restam = (fim_prazo - hoje).days
                    quando = 'vence hoje' if restam == 0 else (f'vence em {restam} dia(s)' if restam > 0 else 'em andamento')
                    c['dica'] = f'{c["pendentes"]} pendente(s) de {c["devidos"]} ({freq_info[f_pk]["prazo"]}) · {quando}'
                contagem[c['cor']] += 1
                c.pop('pendente_encerrado', None)
            grupos.setdefault(pagina.grupo or 'Sem grupo', []).append((pagina, celulas))
        brutos.append((versao, versao.formulario.ordenar_grupos(grupos)))

    colunas = sorted(freq_info.values(), key=lambda f: (ORDEM_PERIODICIDADE.index(f['periodicidade']) if f['periodicidade'] in ORDEM_PERIODICIDADE else 99,
                                                        f['ordem'], f['nome']))
    blocos = []
    for versao, grupos in brutos:
        lista_grupos = []
        for nome_grupo, paginas in grupos.items():
            linhas = []
            for pagina, celulas in paginas:
                if not celulas:
                    continue
                pior = max((c['cor'] for c in celulas.values()), key=lambda x: _GRAVIDADE[x])
                linhas.append({'pagina_id': pagina.pk, 'nome': pagina.nome, 'cor': pior,
                               'celulas': [celulas.get(col['pk']) for col in colunas]})
            if linhas:
                lista_grupos.append({'nome': nome_grupo, 'linhas': linhas})
        if lista_grupos:
            blocos.append({'formulario_id': versao.formulario_id, 'versao_id': versao.pk, 'codigo': versao.formulario.codigo, 'titulo': versao.formulario.titulo,
                           'revisao': versao.revisao, 'grupos': lista_grupos, 'rastreio': inicio_rastreio(versao.formulario)})
    return {'data': data_obs, 'colunas': colunas, 'blocos': blocos, 'contagem': contagem, 'hoje': hoje}


def _turnos_iniciados_hoje(agora):
    from pcp.cobranca import turnos_iniciados
    return [(d, t) for d, t in turnos_iniciados(agora) if d == agora.date()]

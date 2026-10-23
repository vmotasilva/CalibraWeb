"""Visão semanal de uma página: um farol para cada prazo de cada item na semana (segunda a domingo).

Estados do farol:
- ok: lançado e conforme                      - nok: sem lançamento depois do prazo, ou lançado fora do especificado (limite/Nok)
- aberto: sem lançamento, prazo ainda aberto  - futuro: o prazo ainda não começou
- dispensado: máquina em manutenção/parada    - sem: antes do início do rastreio (vigência)
- info: lançamento de item sob demanda (sem exigência de prazo)

Forma dos prazos por frequência: "a cada turno" = um farol por turno e dia; diária = um por dia (qualquer turno vale); semanal, quinzenal,
mensal, trimestral, semestral e anual = um farol por prazo que toca a semana (qualquer turno, em qualquer dia do prazo, vale).
Cada farol traz os dados que o compõem (prazo, lançamentos, situação da máquina) para o pop-up.
"""
import datetime
from collections import Counter, defaultdict

from django.urls import reverse
from django.utils import timezone

from pcp.models import Resposta, Turno, Verificacao
from pcp.pendencias import _janela_dispensada, _turno_encerrado, chave, inicio_rastreio, janela, rotulo_janela

DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
PERIODICAS = ('semanal', 'quinzenal', 'mensal', 'trimestral', 'semestral', 'anual')
NOMES_PERIODO = {'semanal': 'Semana', 'quinzenal': 'Quinzena', 'mensal': 'Mês', 'trimestral': 'Trimestre', 'semestral': 'Semestre', 'anual': 'Ano'}
ROTULOS_ESTADO = {'ok': 'OK', 'nok': 'Não OK', 'aberto': 'Em aberto', 'futuro': 'Ainda não começou', 'dispensado': 'Dispensado',
                  'sem': 'Fora do rastreio', 'info': 'Registro'}
STATUS = dict(Verificacao.STATUS_MAQUINA)


def segunda_feira(data):
    return data - datetime.timedelta(days=data.weekday())


def _fmt(valor):
    return '' if valor is None else str(valor)


def visao_semanal(pagina, data_ref, hoje=None, agora=None):
    """Dados da visão semanal da página na semana que contém `data_ref` (dados simples, prontos para JSON)."""
    from pcp.cobranca import turnos_iniciados
    agora = agora or timezone.localtime()
    hoje = hoje or agora.date()
    ini = segunda_feira(data_ref)
    fim = ini + datetime.timedelta(days=6)
    dias = [ini + datetime.timedelta(days=n) for n in range(7)]
    turnos = list(Turno.objects.filter(ativo=True))
    formulario = pagina.versao.formulario
    rastreio = inicio_rastreio(formulario)
    campos = list(pagina.campos.filter(ativo=True).select_related('frequencia', 'lista').prefetch_related('lista__opcoes').order_by('ordem', 'pk'))
    iniciados_hoje = {t.pk for d, t in turnos_iniciados(agora) if d == hoje}

    # prazos periódicos que tocam a semana
    janelas_do_campo, lo, hi = {}, ini, fim
    for c in campos:
        per = c.frequencia.periodicidade if c.frequencia_id else 'evento'
        if per in PERIODICAS:
            js = sorted({janela(per, d) for d in dias})
            janelas_do_campo[c.pk] = js
            lo, hi = min(lo, js[0][0]), max(hi, js[-1][1])

    registros = defaultdict(list)  # chave do item -> [registro]
    qs = (Resposta.objects.filter(verificacao__pagina__versao__formulario=formulario, verificacao__pagina__nome=pagina.nome,
                                  verificacao__data__range=(lo, hi)).exclude(valor='')
          .order_by('verificacao__data', 'verificacao__turno__ordem')
          .values_list('campo__item', 'campo__etapa', 'campo__descricao', 'verificacao__data', 'verificacao__turno_id', 'verificacao__turno__sigla',
                       'valor', 'conforme', 'verificacao__responsavel__username', 'verificacao__atualizado_em'))
    for item, etapa, desc, dia, turno_id, sigla, valor, conforme, quem, quando in qs:
        registros[chave(item, etapa, desc)].append({
            'data': dia, 'turno_id': turno_id, 'turno': sigla, 'valor': valor, 'conforme': conforme, 'quem': quem or '',
            'quando': timezone.localtime(quando).strftime('%d/%m/%Y %H:%M') if quando else ''})
    parados = {(d, t): (s, m) for d, t, s, m in (Verificacao.objects.filter(
        pagina__versao__formulario=formulario, pagina__nome=pagina.nome, data__range=(lo, hi)).exclude(status='')
        .values_list('data', 'turno_id', 'status', 'motivo'))}
    status_simples = {k: v[0] for k, v in parados.items()}

    detalhes, itens, linhas, contagem = {}, {}, [], Counter()

    def estado_registros(regs):
        return 'nok' if regs and regs[-1]['conforme'] is False else 'ok'

    def estado_sem_registro(inicio, fim_prazo, turno=None):
        if rastreio and fim_prazo < rastreio:
            return 'sem'
        if inicio > hoje:
            return 'futuro'
        if turno is not None and inicio == hoje:
            if turno.pk not in iniciados_hoje:
                return 'futuro'
            return 'nok' if _turno_encerrado(turno, agora) else 'aberto'
        return 'nok' if fim_prazo < hoje else 'aberto'

    base_preencher = reverse('pcp:preencher_pagina', args=[pagina.pk])

    def destino(campo, dia, turno):
        """Link da tela de preenchimento na data e no turno do farol, com o item em destaque."""
        turno = turno or (turnos[0] if turnos else None)
        return {'data': f'{dia:%d/%m/%Y}', 'iso': f'{dia:%Y-%m-%d}', 'turno': turno.sigla if turno else '', 'turno_id': turno.pk if turno else 0,
                'url': f'{base_preencher}?data={dia:%Y-%m-%d}' + (f'&turno={turno.pk}' if turno else '') + f'#campo-{campo.pk}'}

    def registrar(key, campo, estado, titulo, prazo, regs, maquina='', lancar=None):
        resumo = {
            'ok': 'Lançado e dentro do especificado.', 'nok': ('Lançado fora do especificado (limite ou opção de desvio).' if regs
                                                                else 'Sem lançamento até o fim do prazo.'),
            'aberto': 'Sem lançamento ainda; o prazo continua aberto.', 'futuro': 'O prazo ainda não começou.',
            'dispensado': 'Item dispensado: a máquina esteve em manutenção ou parada.', 'sem': 'Antes do início do rastreio'
            + (f' ({rastreio:%d/%m/%Y})' if rastreio else '') + ': não é cobrado.', 'info': 'Registro de item sob demanda (sem prazo).'}[estado]
        detalhes[key] = {'campo': campo.pk, 'estado': estado, 'estado_rotulo': ROTULOS_ESTADO[estado], 'titulo': titulo, 'prazo': prazo, 'resumo': resumo,
                         'maquina': maquina, 'lancar': (lancar if estado != 'futuro' else None), 'registros': [
                             {'data': f'{r["data"]:%d/%m/%Y}', 'turno': r['turno'], 'valor': r['valor'], 'conforme': r['conforme'], 'quem': r['quem'],
                              'quando': r['quando']} for r in regs]}
        if estado != 'info':
            contagem[estado] += 1
        return {'key': key, 'estado': estado}

    def texto_maquina(chaves):
        partes = [f'{STATUS[parados[k][0]]}' + (f' ({parados[k][1]})' if parados[k][1] else '') for k in chaves if k in parados]
        return '; '.join(dict.fromkeys(partes))

    for campo in campos:
        per = campo.frequencia.periodicidade if campo.frequencia_id else 'evento'
        itens[campo.pk] = {
            'num': campo.ordem, 'item': campo.item, 'descricao': campo.descricao, 'etapa': campo.etapa, 'especificacao': campo.especificacao,
            'metodo': campo.metodo, 'plano': campo.plano_reacao, 'frequencia': str(campo.frequencia) if campo.frequencia_id else 'Sem frequência',
            'frequencia_id': campo.frequencia_id or 0, 'periodicidade': per, 'critico': campo.critico, 'tipo': campo.get_tipo_display(),
            'minimo': _fmt(campo.minimo), 'maximo': _fmt(campo.maximo), 'unidade': campo.unidade, 'tipo_codigo': campo.tipo,
            'opcoes': [o.valor for o in campo.lista.opcoes.all()] if campo.tipo == 'lista' and campo.lista_id else []}
        regs_item = registros.get(chave(campo.item, campo.etapa, campo.descricao), [])
        linha = {'campo': campo.pk, 'tipo': 'dias', 'dias': [[] for _ in dias], 'janelas': []}
        if per == 'turno':
            for i, dia in enumerate(dias):
                for turno in turnos:
                    regs = [r for r in regs_item if r['data'] == dia and r['turno_id'] == turno.pk]
                    parado = parados.get((dia, turno.pk))
                    if parado:
                        estado, maquina = 'dispensado', texto_maquina([(dia, turno.pk)])
                    else:
                        estado, maquina = (estado_registros(regs) if regs else estado_sem_registro(dia, dia, turno)), ''
                    d = registrar(f'{campo.pk}:{dia:%Y%m%d}:{turno.pk}', campo, estado, f'{dia:%d/%m/%Y} · turno {turno.sigla}',
                                  f'Dia {dia:%d/%m/%Y}, turno {turno.sigla}', regs, maquina, destino(campo, dia, turno))
                    d['rotulo'] = turno.sigla
                    linha['dias'][i].append(d)
        elif per == 'diaria':
            for i, dia in enumerate(dias):
                regs = [r for r in regs_item if r['data'] == dia]
                dia_todo_parado = bool(turnos) and all((dia, t.pk) in parados for t in turnos)
                if dia_todo_parado:
                    estado, maquina = 'dispensado', texto_maquina([(dia, t.pk) for t in turnos])
                else:
                    estado, maquina = (estado_registros(regs) if regs else estado_sem_registro(dia, dia)), ''
                    algum = [(dia, t.pk) for t in turnos if (dia, t.pk) in parados]
                    maquina = texto_maquina(algum) if algum else ''
                livre = next((t for t in turnos if not any(r['turno_id'] == t.pk for r in regs)), None)
                linha['dias'][i].append(registrar(f'{campo.pk}:{dia:%Y%m%d}:0', campo, estado, f'{dia:%d/%m/%Y}', f'Dia {dia:%d/%m/%Y} (qualquer turno)', regs, maquina,
                                                  destino(campo, dia, livre)))
        elif per in PERIODICAS:
            linha['tipo'] = 'janelas'
            for a, b in janelas_do_campo[campo.pk]:
                regs = [r for r in regs_item if a <= r['data'] <= b]
                limite = min(b, hoje)
                if limite >= a and _janela_dispensada(status_simples, turnos, a, limite):
                    estado, maquina = 'dispensado', texto_maquina([(a + datetime.timedelta(days=n), t.pk) for n in range((limite - a).days + 1) for t in turnos])
                else:
                    estado, maquina = (estado_registros(regs) if regs else estado_sem_registro(a, b)), ''
                nome = NOMES_PERIODO[per]
                d = registrar(f'{campo.pk}:j:{a:%Y%m%d}', campo, estado, f'{nome} {rotulo_janela(per, a)}',
                              f'{nome} {rotulo_janela(per, a)} (qualquer turno, em qualquer dia do prazo)', regs, maquina,
                              destino(campo, hoje if a <= hoje <= b else (b if b < hoje else a), None))
                d['rotulo'] = rotulo_janela(per, a)
                linha['janelas'].append(d)
        else:  # sob demanda ou sem frequência: só mostra o que foi lançado
            linha['tipo'] = 'eventos'
            linha['novos'] = [[] for _ in dias]   # "+": registrar uma ocorrência no dia/turno (só até hoje e onde ainda não há registro)
            for i, dia in enumerate(dias):
                for turno in turnos:
                    regs = [r for r in regs_item if r['data'] == dia and r['turno_id'] == turno.pk]
                    if not regs and dia <= hoje:
                        key = f'{campo.pk}:{dia:%Y%m%d}:{turno.pk}'
                        detalhes[key] = {'campo': campo.pk, 'estado': 'novo', 'estado_rotulo': 'Sem registro', 'titulo': f'{dia:%d/%m/%Y} · turno {turno.sigla}',
                                         'prazo': f'Dia {dia:%d/%m/%Y}, turno {turno.sigla}', 'maquina': '', 'registros': [], 'lancar': destino(campo, dia, turno),
                                         'resumo': 'Nenhum registro neste dia e turno. Registre abaixo quando houver ocorrência (item sob demanda).'}
                        linha['novos'][i].append({'rotulo': turno.sigla, 'key': key, **destino(campo, dia, turno)})
                    if regs:
                        d = registrar(f'{campo.pk}:{dia:%Y%m%d}:{turno.pk}', campo, 'info', f'{dia:%d/%m/%Y} · turno {turno.sigla}',
                                      f'Dia {dia:%d/%m/%Y}, turno {turno.sigla}', regs, '', destino(campo, dia, turno))
                        d['rotulo'] = turno.sigla
                        linha['dias'][i].append(d)
        linhas.append(linha)

    return {
        'ini': ini, 'fim': fim, 'hoje': hoje, 'rastreio': rastreio,
        'dias': [{'data': d, 'rotulo': DIAS[d.weekday()], 'curto': f'{d:%d/%m}', 'hoje': d == hoje, 'futuro': d > hoje} for d in dias],
        'turnos': [{'pk': t.pk, 'sigla': t.sigla} for t in turnos],
        'linhas': linhas, 'itens': itens, 'detalhes': detalhes,
        'contagem': {e: contagem.get(e, 0) for e in ('ok', 'nok', 'aberto', 'futuro', 'dispensado', 'sem')},
        'frequencias': sorted({(i['frequencia_id'], i['frequencia']) for i in itens.values()}, key=lambda x: (x[0] == 0, x[1])),
    }

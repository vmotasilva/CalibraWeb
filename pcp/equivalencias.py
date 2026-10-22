"""Vínculo de valores lançados que não correspondem às opções cadastradas ("falta", "ND", "Lofoam"...) às opções das listas.

Para cada valor não reconhecido sugere-se a opção mais próxima da própria lista do item (sinônimos conhecidos, prefixos e
semelhança de texto). O usuário confirma: vincular a uma opção (guarda a equivalência e corrige os lançamentos já gravados),
criar o valor como nova opção da lista, ou manter como está. Equivalências guardadas valem nas próximas importações de registros.
"""
import difflib
from collections import Counter

from django.db.models import Count

from pcp.importacao import RE_NUM, _chave
from pcp.tipos import aplicar_ajuste
from pcp.models import Campo, ListaOpcoes, OpcaoLista, Resposta, ValorEquivalente

# grupos de sinônimos -> chave da opção para a qual apontam (compara com a chave normalizada das opções da lista)
SINONIMOS = {
    'ok': {'ok', 'certo', 'correto', 'conforme', 'sim', 'c', 'aprovado', 'normal', 'okk'},
    'nok': {'nok', 'nc', 'naoconforme', 'errado', 'reprovado', 'ruim'},
    'realizado': {'realizado', 'feito', 'efetuado', 'executado', 'x'},
    'naorealizado': {'naorealizado', 'nao', 'falta', 'falt', 'faltou', 'naofeito', 'pendente'},
    'manut': {'manut', 'manutencao', 'emmanut', 'emmanutencao'},
    'maqparada': {'maqparada', 'maquinaparada', 'parada', 'mp', 'maqparado'},
}
CONFIANCA_ROTULO = {'alta': 'alta', 'media': 'média'}


def _candidatas(opcoes):
    """[(chave, opção)] das opções e dos sinônimos que apontam para elas."""
    por_chave = {_chave(o.valor): o for o in opcoes}
    candidatas = list(por_chave.items())
    for destino, sinonimos in SINONIMOS.items():
        if destino in por_chave:
            candidatas += [(s, por_chave[destino]) for s in sinonimos if s not in por_chave]
    return candidatas


def _melhor(k, candidatas):
    """(opção, confiança) entre as candidatas: igual, prefixo ou parecido (erro de digitação)."""
    exatas = {c: o for c, o in candidatas}
    if k in exatas:
        return exatas[k], 'alta'
    if len(k) >= 3:
        for c, o in candidatas:
            if len(c) >= 4 and (k.startswith(c) or (len(k) >= 4 and c.startswith(k))):
                return o, 'media'
    proximo = difflib.get_close_matches(k, list(exatas), n=1, cutoff=0.78)
    if proximo:
        return exatas[proximo[0]], 'media'
    return None, ''


def sugerir_opcao(valor, opcoes, outras_opcoes=()):
    """(opção, confiança, de_outra_lista) mais provável para o valor: primeiro entre as opções da própria lista do item;
    se nada servir, entre as opções das outras listas cadastradas. (None, '', False) se não houver sugestão."""
    k = _chave(valor)
    if not k:
        return None, '', False
    opcao, confianca = _melhor(k, _candidatas(opcoes))
    if opcao:
        return opcao, confianca, False
    opcao, confianca = _melhor(k, _candidatas(list(outras_opcoes)))
    return (opcao, confianca, True) if opcao else (None, '', False)


def montar_linhas(contagem, detalhe=None, totais=None, limite=200):
    """Linhas para a tabela de vínculos a partir de {(lista_id, valor): quantidade}.

    `detalhe` = {(lista_id, valor): {campo_id: quantidade}} e `totais` = {campo_id: total de lançamentos do item} permitem mostrar
    quais itens o valor afeta e a que parte do item ele corresponde (base da ação "marcar como texto livre").
    Valores numéricos ficam de fora (o caminho deles é Ajustar tipos); devolve (linhas, quantidade_de_lançamentos_numéricos)."""
    listas = {l.pk: l for l in ListaOpcoes.objects.prefetch_related('opcoes')}
    detalhe, totais = detalhe or {}, totais or {}
    ids = {cid for d in detalhe.values() for cid in d}
    campos = {c.pk: c for c in Campo.objects.filter(pk__in=ids).select_related('pagina')}
    linhas, numericos = [], 0
    for (lista_id, valor), n in Counter(contagem).most_common():
        if RE_NUM.match(valor):
            numericos += n
            continue
        lista = listas.get(lista_id)
        if lista is None:
            continue
        opcoes = list(lista.opcoes.all())
        outras = [(l, list(l.opcoes.all())) for l in listas.values() if l.pk != lista.pk and l.ativo]
        opcao, confianca, de_outra = sugerir_opcao(valor, opcoes, [o for _, ops in outras for o in ops])
        itens = []
        for cid, qtd in sorted(detalhe.get((lista_id, valor), {}).items(), key=lambda x: -x[1]):
            c = campos.get(cid)
            if c is None or c.tipo != Campo.LISTA:
                continue
            total = totais.get(cid) or qtd
            itens.append({'pk': cid, 'rotulo': f'{c.pagina.nome} · {c.item or c.descricao[:30]}', 'n': qtd, 'total': total,
                          'pct': round(100 * qtd / total)})
        linhas.append({
            'lista': lista, 'valor': valor, 'n': n, 'opcoes': opcoes, 'outras': outras, 'sugestao': opcao,
            'de_outra_lista': de_outra, 'confianca': CONFIANCA_ROTULO.get(confianca, ''),
            'itens': itens, 'itens_ids': ','.join(str(x['pk']) for x in itens),
            # sem opção parecida e o valor domina o item: provavelmente o item é de texto livre
            'texto_sugerido': bool(itens) and opcao is None and all(x['pct'] >= 50 for x in itens)})
    return linhas[:limite], numericos


def valores_do_formulario(formulario):
    """Valores já lançados em itens de lista do formulário que não coincidem com nenhuma opção da lista do item."""
    pares = (Resposta.objects.filter(campo__pagina__versao__formulario=formulario, campo__tipo='lista', campo__lista__isnull=False)
             .exclude(valor='').values('campo__lista_id', 'valor', 'campo_id').annotate(n=Count('id')))
    opcoes_exatas = {l.pk: {o.valor for o in l.opcoes.all()} for l in ListaOpcoes.objects.prefetch_related('opcoes')}
    contagem, detalhe, totais = Counter(), {}, Counter()
    for p in pares:
        totais[p['campo_id']] += p['n']
        if p['valor'] not in opcoes_exatas.get(p['campo__lista_id'], set()):
            chave = (p['campo__lista_id'], p['valor'])
            contagem[chave] += p['n']
            detalhe.setdefault(chave, {})[p['campo_id']] = p['n']
    return montar_linhas(contagem, detalhe, totais)


def aplicar_vinculos(linhas):
    """linhas: [(lista_id, valor, acao, ids_dos_itens)] com acao 'op:<id>' (vincular), 'novo:ok' ou 'novo:desvio' (criar opção)
    ou 'texto' (marcar os itens indicados como texto livre). Devolve {'vinculados', 'criadas', 'textos', 'lancamentos'}."""
    resumo = {'vinculados': 0, 'criadas': 0, 'textos': 0, 'lancamentos': 0}
    for lista_id, valor, acao, itens_ids in linhas:
        lista = ListaOpcoes.objects.filter(pk=lista_id).first()
        if not lista or not valor:
            continue
        lancamentos = Resposta.objects.filter(campo__lista=lista, valor=valor)
        if acao == 'texto':
            ids = [int(x) for x in itens_ids.split(',') if x.strip().isdigit()]
            for campo in Campo.objects.filter(pk__in=ids, tipo=Campo.LISTA, lista=lista).select_related('pagina__versao__formulario'):
                aplicar_ajuste(campo.pagina.versao.formulario, campo, Campo.TEXTO)
                resumo['textos'] += 1
            continue
        if acao.startswith('op:') and acao[3:].isdigit():
            opcao = OpcaoLista.objects.filter(pk=int(acao[3:])).first()  # pode ser de outra lista (ex.: Realizado num item Ok/Nok)
            if not opcao:
                continue
            ValorEquivalente.objects.update_or_create(lista=lista, chave=_chave(valor)[:120],
                                                      defaults={'texto': valor[:120], 'opcao': opcao})
            resumo['lancamentos'] += lancamentos.update(valor=opcao.valor, conforme=opcao.conforme)
            resumo['vinculados'] += 1
        elif acao in ('novo:ok', 'novo:desvio'):
            conforme = acao == 'novo:ok'
            ultimo = lista.opcoes.order_by('-ordem').values_list('ordem', flat=True).first()
            opcao, criada = OpcaoLista.objects.get_or_create(
                lista=lista, valor=valor[:60], defaults={'conforme': conforme, 'ordem': (ultimo + 1) if ultimo is not None else 0})
            resumo['criadas'] += int(criada)
            resumo['lancamentos'] += lancamentos.update(conforme=opcao.conforme)
    return resumo

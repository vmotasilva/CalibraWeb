# -*- coding: utf-8 -*-
"""
Aparência dos blocos e conexões no PDF (espelho de static/procedures/js/diagrama/estilo.js).

Precedência por propriedade: estilo explícito do bloco (data.style; data.bgColor legado = preenchimento)
> tema do diagrama para o nível do bloco > aparência padrão (propriedade ausente).
O token "branch" numa cor do tema vira a cor do ramo (paleta) quando o tema usa multiRamo.
Um teste compara esta implementação com a do JavaScript para garantir o mesmo resultado.
"""

FAMILIAS = ('sans', 'serif', 'mono')
BORDAS = ('solid', 'dashed', 'dotted', 'none')
TRACADOS = ('solid', 'dashed', 'dotted')
FORMATOS_LINHA = ('ortogonal', 'curva', 'reta')
ALINHAMENTOS = ('left', 'center', 'right')
FORMAS = ('rect', 'pill', 'decision', 'circle', 'parallelogram', 'brackets', 'underline', 'plain')

# família -> (normal, negrito, itálico, negrito+itálico) nas fontes padrão do PDF
FONTES_PDF = {
    'sans': ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique'),
    'serif': ('Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic'),
    'mono': ('Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique'),
}


def nome_da_fonte(familia: str, negrito: bool, italico: bool) -> str:
    normal, bold, italic, bold_italic = FONTES_PDF.get(familia or 'sans', FONTES_PDF['sans'])
    if negrito and italico:
        return bold_italic
    if negrito:
        return bold
    return italic if italico else normal


def luminancia(hexa: str) -> float:
    """Luminância relativa (WCAG) de uma cor #RRGGBB."""
    def canal(i):
        v = int(hexa[i:i + 2], 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * canal(1) + 0.7152 * canal(3) + 0.0722 * canal(5)


def cor_de_texto_para_fundo(hexa: str) -> str:
    return '#ffffff' if luminancia(hexa) < 0.4 else '#0f172a'


def _limpar(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def cor_do_ramo(tema, ramo):
    if not tema or not tema.get('multiRamo') or not tema.get('paleta') or ramo is None or ramo < 0:
        return None
    paleta = tema['paleta']
    return paleta[ramo % len(paleta)]


def _token(valor, tema, ramo):
    return cor_do_ramo(tema, ramo) if valor == 'branch' else valor


def resolver_estilo_no(no: dict, ctx: dict = None) -> dict:
    """Estilo efetivo do bloco: fill, noFill, color, fontFamily, fontSize, bold, italic, strike, align, border*."""
    ctx = ctx or {}
    dados = no.get('data') if isinstance(no.get('data'), dict) else {}
    tema = ctx.get('tema')
    tipo = no.get('type') or 'process'
    base = {}
    niveis = (tema or {}).get('niveis') or []
    if niveis and tipo not in ('start', 'end', 'decision'):
        nivel = niveis[min(ctx.get('profundidade') or 0, len(niveis) - 1)] or {}
        ramo = ctx.get('ramo')
        base = _limpar({
            'fill': _token(nivel.get('fill'), tema, ramo),
            'color': _token(nivel.get('texto'), tema, ramo),
            'borderColor': _token(nivel.get('borda'), tema, ramo),
            'borderWidth': nivel.get('larguraBorda'),
            'fontSize': nivel.get('tamanho'),
            'bold': nivel.get('negrito'),
            'italic': nivel.get('italico'),
            'fontFamily': nivel.get('familia'),
        })
    # Formas sem caixa (colchetes, sublinhado, só texto) nunca herdam o preenchimento do tema
    especial = dados.get('shape') in ('brackets', 'underline', 'plain')
    estilo_no = dados.get('style') if isinstance(dados.get('style'), dict) else {}
    if especial and not (estilo_no.get('fill') or dados.get('bgColor')):
        base.pop('fill', None)

    explicito = {}
    if dados.get('bgColor'):
        explicito['fill'] = dados['bgColor']
    if isinstance(dados.get('style'), dict):
        explicito.update(dados['style'])
    efetivo = {**base, **_limpar(explicito)}
    if efetivo.get('noFill'):
        efetivo.pop('fill', None)
    estilo = dados.get('style') if isinstance(dados.get('style'), dict) else {}
    if efetivo.get('fill') and estilo.get('fill') and estilo.get('color') is None:
        efetivo['color'] = cor_de_texto_para_fundo(efetivo['fill'])
    # Sem preenchimento (ou forma sem caixa) o texto cai sobre o fundo do diagrama: usa a cor legível sobre ele
    if (efetivo.get('noFill') or (especial and not efetivo.get('fill'))) and not estilo.get('color'):
        fundo = (tema or {}).get('fundo')
        efetivo['color'] = cor_de_texto_para_fundo(fundo if isinstance(fundo, str) and len(fundo) == 7 else '#ffffff')
    return efetivo


def resolver_estilo_conexao(aresta: dict, ctx: dict = None) -> dict:
    ctx = ctx or {}
    tema = ctx.get('tema')
    linha = (tema or {}).get('linha') or {}
    base = _limpar({
        'color': _token(linha.get('cor'), tema, ctx.get('ramo')),
        'width': linha.get('largura'),
        'dash': linha.get('tracejado'),
        'shape': linha.get('formato'),
    })
    proprio = aresta.get('style') if isinstance(aresta.get('style'), dict) else {}
    return {**base, **_limpar(proprio)}


def contexto_dos_nos(arvore: dict) -> dict:
    """{id: {'profundidade', 'ramo'}} a partir da árvore de diagram_arvore.montar_arvore."""
    pai, filhos = arvore['pai'], arvore['filhos']

    def nivel(no_id):
        n, atual = 0, pai.get(no_id)
        while atual is not None:
            n += 1
            atual = pai.get(atual)
        return n

    contexto = {}
    for no_id in filhos:
        profundidade = nivel(no_id)
        ramo = -1
        if profundidade >= 1:
            atual = no_id
            while pai.get(atual) is not None and nivel(atual) > 1:
                atual = pai[atual]
            raiz_do_ramo = pai.get(atual)
            irmaos = filhos.get(raiz_do_ramo, [])
            ramo = irmaos.index(atual) if atual in irmaos else -1
        contexto[no_id] = {'profundidade': profundidade, 'ramo': ramo}
    return contexto

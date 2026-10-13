# -*- coding: utf-8 -*-
"""
Importação de mapas mentais e outlines para o editor de diagramas: .xmind (XMind 8 e Zen/2020+), OPML e Markdown/texto
indentado. Tudo vira uma árvore intermediária de nós e, depois, uma topologia do editor (modos em árvore).

Árvore intermediária (dict): {titulo, filhos, estilo, forma, nota, links, etiquetas, marcadores}.
O conteúdo do arquivo é tratado como dado: limites de tamanho, sem expansão de entidades XML e sem caminhos de zip.
"""

import io
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET

from .diagram_conteudo import MAX_LINKS, MAX_MARCADORES, MAX_NOTA
from .diagram_validation import MAX_NODES, MAX_SUBTITULOS, URL_RE, validar_topologia

LIMITE_ARQUIVO = 10 * 1024 * 1024        # arquivo enviado
LIMITE_DESCOMPRIMIDO = 60 * 1024 * 1024  # soma dos itens do .xmind (proteção contra zip bomb)
LIMITE_ITENS_ZIP = 500
PROFUNDIDADE_MAXIMA = 60
MODOS_IMPORTACAO = ('organograma', 'logico', 'arvore')
EXTENSOES = ('.xmind', '.opml', '.md', '.markdown', '.txt')


class ErroImportacao(Exception):
    """Arquivo inválido ou fora dos limites (mensagem pronta para o usuário)."""


def _no(titulo: str) -> dict:
    return {'titulo': titulo, 'filhos': [], 'estilo': {}, 'forma': None, 'nota': '', 'links': [],
            'etiquetas': [], 'marcadores': []}


# ======================================================================== XMind
_CORES_XMIND = {'red': 'vermelho', 'orange': 'laranja', 'yellow': 'laranja', 'green': 'verde', 'blue': 'azul',
                'purple': 'roxo', 'gray': 'cinza', 'grey': 'cinza', 'dark-gray': 'cinza', 'light-blue': 'azul'}
_FORMAS_XMIND = {
    'underline': 'underline', 'doubleunderline': 'underline',
    'singlebreakangle': 'brackets', 'squarequote': 'brackets', 'brackets': 'brackets',
    'ellipse': 'pill', 'ellipserect': 'pill', 'roundedhexagon': 'pill', 'roundedrect': 'pill',
    'circle': 'circle', 'diamond': 'decision', 'parallelogram': 'parallelogram',
}
_PROGRESSO = {'task-start': 'prog-0', 'task-oct': 'prog-0', 'task-quarter': 'prog-25', 'task-half': 'prog-50',
              'task-3oct': 'prog-50', 'task-3quar': 'prog-75', 'task-7oct': 'prog-75', 'task-done': 'prog-100'}


def _cor_xmind(valor):
    """'#RRGGBB' ou '#RRGGBBAA' -> ('#rrggbb', transparente?)."""
    if not isinstance(valor, str):
        return None, False
    m = re.fullmatch(r'#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?', valor.strip())
    if not m:
        return None, False
    return '#' + m.group(1).lower(), (m.group(2) or 'ff').lower() == '00'


def _pt(valor):
    m = re.match(r'\s*([0-9]+(?:\.[0-9]+)?)', str(valor or ''))
    return float(m.group(1)) if m else None


def _estilo_xmind(props: dict):
    """Propriedades do XMind -> (estilo do editor, forma)."""
    estilo, forma = {}, None
    fill, transparente = _cor_xmind(props.get('svg:fill'))
    if transparente:
        estilo['noFill'] = True
    elif fill:
        estilo['fill'] = fill
    cor, _ = _cor_xmind(props.get('fo:color'))
    if cor:
        estilo['color'] = cor
    tam = _pt(props.get('fo:font-size'))
    if tam:
        estilo['fontSize'] = max(8, min(40, int(round(tam))))
    if str(props.get('fo:font-weight', '')).lower() in ('bold', '700', '800', '900'):
        estilo['bold'] = True
    if str(props.get('fo:font-style', '')).lower() == 'italic':
        estilo['italic'] = True
    if 'line-through' in str(props.get('fo:text-decoration', '')).lower():
        estilo['strike'] = True
    if props.get('fo:text-align') in ('left', 'center', 'right'):
        estilo['align'] = props['fo:text-align']
    largura = _pt(props.get('border-line-width'))
    if largura is not None:
        if largura <= 0:
            estilo['borderStyle'] = 'none'
        else:
            estilo['borderWidth'] = max(1, min(8, int(round(largura))))
    borda, _ = _cor_xmind(props.get('border-line-color'))
    if borda:
        estilo['borderColor'] = borda
    classe = str(props.get('shape-class', '')).rsplit('.', 1)[-1].lower()
    forma = _FORMAS_XMIND.get(classe)
    return estilo, forma


def _marcador_xmind(marker_id) -> str:
    """Id de marcador do XMind -> id do catálogo do editor ('' quando não há equivalente)."""
    marker_id = str(marker_id or '').lower()
    m = re.fullmatch(r'priority-([1-7])', marker_id)
    if m:
        return f'prio-{m.group(1)}'
    if marker_id in _PROGRESSO:
        return _PROGRESSO[marker_id]
    for prefixo, destino in (('flag-', 'band-'), ('star-', 'estr-'), ('people-', 'pess-')):
        if marker_id.startswith(prefixo):
            cor = _CORES_XMIND.get(marker_id[len(prefixo):])
            return f'{destino}{cor}' if cor else ''
    return ''


def _topico_json(t: dict, contexto: dict, profundidade=0) -> dict:
    if profundidade > PROFUNDIDADE_MAXIMA:
        raise ErroImportacao(f'O mapa tem mais de {PROFUNDIDADE_MAXIMA} níveis de profundidade.')
    no = _no(str(t.get('title') or ''))
    estilo, forma = _estilo_xmind(((t.get('style') or {}).get('properties')) or {})
    no['estilo'], no['forma'] = estilo, forma

    notas = t.get('notes')
    if isinstance(notas, dict):
        plano = (notas.get('plain') or {}).get('content') if isinstance(notas.get('plain'), dict) else None
        no['nota'] = str(plano or '').strip()
    href = t.get('href')
    if isinstance(href, str) and URL_RE.match(href) and len(href) <= 500:
        no['links'].append({'tipo': 'url', 'url': href, 'rotulo': ''})
    elif href:
        contexto['avisos'].add('links internos do XMind (arquivos e tópicos) foram ignorados')
    no['etiquetas'] = [str(x) for x in (t.get('labels') or []) if isinstance(x, str) and x.strip()]
    for m in t.get('markers') or []:
        mapeado = _marcador_xmind(m.get('markerId') if isinstance(m, dict) else m)
        if mapeado and mapeado not in no['marcadores']:
            no['marcadores'].append(mapeado)
    if t.get('extensions'):
        contexto['avisos'].add('extensões do XMind (por exemplo, tarefas) foram ignoradas')

    filhos = t.get('children') or {}
    for tipo, lista in filhos.items():
        if tipo == 'attached':
            for ch in lista:
                if isinstance(ch, dict):
                    no['filhos'].append(_topico_json(ch, contexto, profundidade + 1))
        elif lista:
            contexto['avisos'].add('tópicos soltos, resumos e conexões livres do XMind foram ignorados')
    for chave in ('summaries', 'boundaries', 'relationships'):
        if t.get(chave):
            contexto['avisos'].add('tópicos soltos, resumos e conexões livres do XMind foram ignorados')
    return no


def _topico_xml(el, ns: str, contexto: dict, profundidade=0) -> dict:
    if profundidade > PROFUNDIDADE_MAXIMA:
        raise ErroImportacao(f'O mapa tem mais de {PROFUNDIDADE_MAXIMA} níveis de profundidade.')
    titulo = el.find(f'{ns}title')
    no = _no(''.join(titulo.itertext()) if titulo is not None else '')
    filhos = el.find(f'{ns}children')
    if filhos is not None:
        for grupo in filhos.findall(f'{ns}topics'):
            if grupo.get('type') != 'attached':
                contexto['avisos'].add('tópicos soltos, resumos e conexões livres do XMind foram ignorados')
                continue
            for ch in grupo.findall(f'{ns}topic'):
                no['filhos'].append(_topico_xml(ch, ns, contexto, profundidade + 1))
    return no


def _ler_xmind(conteudo: bytes) -> list:
    try:
        z = zipfile.ZipFile(io.BytesIO(conteudo))
    except zipfile.BadZipFile:
        raise ErroImportacao('O arquivo não é um .xmind válido (pacote ZIP corrompido).')
    itens = z.infolist()
    if len(itens) > LIMITE_ITENS_ZIP or sum(i.file_size for i in itens) > LIMITE_DESCOMPRIMIDO:
        raise ErroImportacao('O arquivo .xmind excede os limites de segurança de tamanho.')
    nomes = {i.filename for i in itens}
    contexto = {'avisos': set()}
    folhas = []
    if 'content.json' in nomes:
        try:
            dados = json.loads(z.read('content.json').decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ErroImportacao('O conteúdo do .xmind (content.json) está ilegível.')
        if not isinstance(dados, list):
            raise ErroImportacao('Formato de .xmind não reconhecido.')
        for i, folha in enumerate(dados):
            raiz = folha.get('rootTopic') if isinstance(folha, dict) else None
            if isinstance(raiz, dict):
                folhas.append({'titulo': str(folha.get('title') or f'Planilha {i + 1}'),
                               'raiz': _topico_json(raiz, contexto)})
    elif 'content.xml' in nomes:
        bruto = z.read('content.xml')
        if b'<!DOCTYPE' in bruto or b'<!ENTITY' in bruto:
            raise ErroImportacao('O XML do arquivo contém declarações não permitidas.')
        try:
            raiz_xml = ET.fromstring(bruto)
        except ET.ParseError:
            raise ErroImportacao('O conteúdo do .xmind (content.xml) está ilegível.')
        ns = raiz_xml.tag[:raiz_xml.tag.index('}') + 1] if raiz_xml.tag.startswith('{') else ''
        for i, sheet in enumerate(raiz_xml.findall(f'{ns}sheet')):
            topico = sheet.find(f'{ns}topic')
            if topico is not None:
                titulo = sheet.find(f'{ns}title')
                folhas.append({'titulo': (titulo.text if titulo is not None and titulo.text else f'Planilha {i + 1}'),
                               'raiz': _topico_xml(topico, ns, contexto)})
    else:
        raise ErroImportacao('Não encontrei o conteúdo do mapa (content.json ou content.xml) no arquivo .xmind.')
    if not folhas:
        raise ErroImportacao('O arquivo .xmind não tem nenhuma planilha com mapa.')
    for f in folhas:
        f['avisos'] = sorted(contexto['avisos'])
    return folhas


# ======================================================================== OPML
def _ler_opml(conteudo: bytes, titulo_padrao: str) -> list:
    if b'<!DOCTYPE' in conteudo or b'<!ENTITY' in conteudo:
        raise ErroImportacao('O XML do arquivo contém declarações não permitidas.')
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        raise ErroImportacao('O arquivo OPML está ilegível.')
    corpo = raiz.find('body')
    if corpo is None:
        raise ErroImportacao('O arquivo OPML não tem a seção <body>.')

    def converter(el, profundidade=0):
        if profundidade > PROFUNDIDADE_MAXIMA:
            raise ErroImportacao(f'O mapa tem mais de {PROFUNDIDADE_MAXIMA} níveis de profundidade.')
        no = _no(el.get('text') or el.get('title') or '')
        no['nota'] = (el.get('_note') or '').strip()
        no['filhos'] = [converter(ch, profundidade + 1) for ch in el.findall('outline')]
        return no

    topo = [converter(o) for o in corpo.findall('outline')]
    cabecalho = raiz.find('head/title')
    titulo = (cabecalho.text.strip() if cabecalho is not None and cabecalho.text else titulo_padrao)
    return [{'titulo': titulo, 'raiz': _raiz_unica(topo, titulo), 'avisos': []}]


# ======================================================================== Markdown / texto indentado
_LINHA = re.compile(r'^(?P<indent>[ \t]*)(?:(?P<h>#{1,6})\s+|(?P<b>(?:[-*+]|\d+[.)])\s+))?(?P<texto>.*\S.*)$')


def _ler_texto(texto: str, titulo_padrao: str) -> list:
    pilha = []  # (nível, nó)
    topo = []
    base_heading = 0
    for linha in texto.replace('\r\n', '\n').split('\n'):
        if not linha.strip() or linha.strip().startswith(('---', '```', '<!--')):
            continue
        m = _LINHA.match(linha)
        if not m:
            continue
        recuo = len(m.group('indent').replace('\t', '    '))
        if m.group('h'):
            nivel = len(m.group('h')) - 1
            base_heading = nivel + 1
            recuo_nivel = nivel
        else:
            recuo_nivel = base_heading + recuo // 2 if m.group('b') or recuo else base_heading
        no = _no(m.group('texto').strip())
        while pilha and pilha[-1][0] >= recuo_nivel:
            pilha.pop()
        (pilha[-1][1]['filhos'] if pilha else topo).append(no)
        pilha.append((recuo_nivel, no))
    if not topo:
        raise ErroImportacao('Não encontrei nenhum item no texto (use títulos "#", listas "-" ou recuo).')
    return [{'titulo': titulo_padrao, 'raiz': _raiz_unica(topo, titulo_padrao), 'avisos': []}]


def _raiz_unica(topo: list, titulo: str) -> dict:
    if not topo:
        raise ErroImportacao('O arquivo não tem nenhum item.')
    if len(topo) == 1:
        return topo[0]
    raiz = _no(titulo)
    raiz['filhos'] = topo
    return raiz


# ======================================================================== entrada pública
def ler_arquivo(nome: str, conteudo: bytes) -> list:
    """Lê o arquivo e devolve as planilhas: [{titulo, raiz, avisos}]."""
    if len(conteudo) > LIMITE_ARQUIVO:
        raise ErroImportacao('O arquivo excede o limite de 10 MB.')
    base, ext = os.path.splitext(os.path.basename(nome or ''))
    ext = ext.lower()
    if ext not in EXTENSOES:
        raise ErroImportacao('Formato não suportado. Use .xmind, .opml, .md ou .txt.')
    titulo_padrao = (base or 'Mapa importado').strip()[:120]
    if ext == '.xmind':
        return _ler_xmind(conteudo)
    if ext == '.opml':
        return _ler_opml(conteudo, titulo_padrao)
    try:
        texto = conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = conteudo.decode('latin-1')
    return _ler_texto(texto, titulo_padrao)


def contar(raiz: dict) -> dict:
    """{blocos, niveis} de uma árvore intermediária."""
    blocos, niveis = 0, 0
    pilha = [(raiz, 1)]
    while pilha:
        no, nivel = pilha.pop()
        blocos += 1
        niveis = max(niveis, nivel)
        pilha.extend((f, nivel + 1) for f in no['filhos'])
    return {'blocos': blocos, 'niveis': niveis}


def _texto_do_bloco(titulo: str):
    """'Nome\\nCargo' -> (rótulo, subtítulos, vaga). '(Vago)\\nCargo' vira bloco de vaga com o cargo como rótulo."""
    linhas = [ln.strip() for ln in re.split(r'[\r\n]+', titulo or '') if ln.strip()]
    vaga = bool(linhas) and re.fullmatch(r'\(?\s*vag[oa]\s*\)?', linhas[0], re.IGNORECASE) is not None
    if vaga:
        linhas = linhas[1:] or ['Vaga']
    if not linhas:
        return 'Sem título', [], vaga
    return linhas[0][:300], [ln[:300] for ln in linhas[1:MAX_SUBTITULOS + 1]], vaga


def para_topologia(raiz: dict, modo: str = 'organograma', com_estilos: bool = True) -> dict:
    """Árvore intermediária -> topologia do editor. As posições vêm do auto-layout ao abrir (flag `precisa_layout`)."""
    if modo not in MODOS_IMPORTACAO:
        raise ErroImportacao('Layout inválido para importação.')
    if contar(raiz)['blocos'] > MAX_NODES:
        raise ErroImportacao(f'O mapa tem mais de {MAX_NODES} blocos (limite por diagrama).')

    nodes, edges = [], []
    pilha = [(raiz, None)]
    contador = 0
    while pilha:
        no, pai_id = pilha.pop()
        contador += 1
        nid = str(contador)
        rotulo, subs, vaga = _texto_do_bloco(no['titulo'])
        dados = {'label': rotulo, 'stepId': nid}
        if subs:
            dados['subtitles'] = subs
        if vaga:
            dados['vaga'] = True
        if pai_id is None:
            dados['isCentral'] = True
        if com_estilos:
            if no['estilo']:
                dados['style'] = dict(no['estilo'])
            # colchetes/sublinhado são formas sem caixa: com preenchimento explícito o bloco fica preenchido
            if no['forma'] and not (no['forma'] in ('brackets', 'underline', 'plain') and no['estilo'].get('fill')):
                dados['shape'] = no['forma']
        if no['nota']:
            dados['nota'] = no['nota'][:MAX_NOTA]
        if no['links']:
            dados['links'] = no['links'][:MAX_LINKS]
        if no['etiquetas']:
            dados['customTags'] = [e[:30] for e in no['etiquetas'][:8]]
        if no['marcadores']:
            dados['markers'] = no['marcadores'][:MAX_MARCADORES]
        nodes.append({'id': nid, 'type': 'process', 'position': {'x': 0, 'y': 0}, 'data': dados})
        if pai_id is not None:
            edges.append({'id': f'e{pai_id}-{nid}', 'source': pai_id, 'target': nid})
        # empilha ao contrário para visitar os filhos na ordem original
        for filho in reversed(no['filhos']):
            pilha.append((filho, nid))

    topologia = {'schema_version': 2, 'layout_modo': modo, 'estilo_linha': 'ortogonal',
                 'nodes': nodes, 'edges': edges, 'grid_data': [], 'precisa_layout': True}
    erros = validar_topologia(topologia)
    if erros:
        raise ErroImportacao('O mapa importado não passou na validação: ' + '; '.join(erros[:3]))
    return topologia


def resumo_das_folhas(folhas: list) -> list:
    return [{'indice': i, 'titulo': f['titulo'], 'avisos': f['avisos'], **contar(f['raiz'])} for i, f in enumerate(folhas)]

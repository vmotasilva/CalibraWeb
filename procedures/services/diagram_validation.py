# -*- coding: utf-8 -*-
"""
Validação de schema da topologia (nodes/edges/grid_data) enviada pelo editor de diagramas.
Sem dependências externas: usada pelo endpoint de auto-save.
"""

import json
import re

from .diagram_conteudo import MAX_LINKS, MAX_MARCADORES, MAX_NOTA, marcador_valido
from .diagram_estilo import ALINHAMENTOS, BORDAS, FAMILIAS, FORMAS, FORMATOS_LINHA, TRACADOS

MAX_NODES = 1000
MAX_EDGES = 3000
MAX_SUBTITULOS = 20
MAX_RAIAS = 100
MODOS_LAYOUT = ('raias', 'organograma', 'logico', 'arvore')
TIPOS_CONEXAO = ('hierarquia', 'relacao')


COR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
MAX_TAMANHO_TEMA = 8000


def _cor_valida(valor, permitir_ramo=False) -> bool:
    return isinstance(valor, str) and (bool(COR_RE.match(valor)) or (permitir_ramo and valor == 'branch'))


def _inteiro_entre(valor, minimo, maximo) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


URL_RE = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


def validar_conteudo_no(dados: dict, nid) -> list:
    """Marcadores, nota, links, vaga, imagem e dados extras do colaborador de um bloco."""
    erros = []
    marcadores = dados.get('markers')
    if marcadores is not None:
        if (not isinstance(marcadores, list) or len(marcadores) > MAX_MARCADORES
                or not all(marcador_valido(m) for m in marcadores) or len(set(marcadores)) != len(marcadores)):
            erros.append(f"Marcadores inválidos no nó {nid} (até {MAX_MARCADORES}, do catálogo e sem repetição).")
    nota = dados.get('nota')
    if nota is not None and (not isinstance(nota, str) or len(nota) > MAX_NOTA):
        erros.append(f"Nota inválida no nó {nid} (texto de até {MAX_NOTA} caracteres).")
    links = dados.get('links')
    if links is not None:
        if not isinstance(links, list) or len(links) > MAX_LINKS:
            erros.append(f"Links inválidos no nó {nid} (até {MAX_LINKS}).")
        else:
            for link in links:
                ok = isinstance(link, dict) and isinstance(link.get('rotulo', ''), str) and len(link.get('rotulo', '')) <= 120
                if ok and link.get('tipo') == 'url':
                    ok = isinstance(link.get('url'), str) and len(link['url']) <= 500 and bool(URL_RE.match(link['url']))
                elif ok and link.get('tipo') == 'procedimento':
                    ok = isinstance(link.get('id'), int) and not isinstance(link.get('id'), bool)
                elif ok and link.get('tipo') == 'diagrama':
                    ok = isinstance(link.get('id'), str) and 0 < len(link['id']) <= 64
                else:
                    ok = False
                if not ok:
                    erros.append(f"Link inválido no nó {nid}.")
                    break
    if dados.get('vaga') is not None and not isinstance(dados['vaga'], bool):
        erros.append(f"'vaga' deve ser verdadeiro/falso no nó {nid}.")
    imagem = dados.get('imagem')
    if imagem is not None and (not isinstance(imagem, dict) or not isinstance(imagem.get('id'), int) or isinstance(imagem.get('id'), bool)):
        erros.append(f"Imagem inválida no nó {nid}.")
    colab = dados.get('colab')
    if isinstance(colab, dict):
        if colab.get('cargoRH') is not None and (not isinstance(colab['cargoRH'], str) or len(colab['cargoRH']) > 200):
            erros.append(f"'cargoRH' inválido no nó {nid}.")
        if colab.get('removido') is not None and not isinstance(colab['removido'], bool):
            erros.append(f"'removido' inválido no nó {nid}.")
    return erros


def validar_estilo_no(estilo, nid) -> list:
    """Estilo explícito do bloco (data.style)."""
    if not isinstance(estilo, dict):
        return [f"Estilo inválido no nó {nid}."]
    erros = []
    permitidos = {'fontFamily', 'fontSize', 'bold', 'italic', 'strike', 'align', 'color', 'fill', 'noFill',
                  'borderStyle', 'borderColor', 'borderWidth'}
    for chave in estilo:
        if chave not in permitidos:
            erros.append(f"Propriedade de estilo desconhecida '{chave}' no nó {nid}.")
    if 'fontFamily' in estilo and estilo['fontFamily'] not in FAMILIAS:
        erros.append(f"Fonte inválida no nó {nid}.")
    if 'fontSize' in estilo and not _inteiro_entre(estilo['fontSize'], 8, 40):
        erros.append(f"Tamanho de fonte inválido no nó {nid} (8 a 40).")
    for chave in ('bold', 'italic', 'strike', 'noFill'):
        if chave in estilo and not isinstance(estilo[chave], bool):
            erros.append(f"'{chave}' deve ser verdadeiro/falso no nó {nid}.")
    if 'align' in estilo and estilo['align'] not in ALINHAMENTOS:
        erros.append(f"Alinhamento inválido no nó {nid}.")
    for chave in ('color', 'fill', 'borderColor'):
        if chave in estilo and not _cor_valida(estilo[chave]):
            erros.append(f"Cor inválida em '{chave}' no nó {nid} (use #RRGGBB).")
    if 'borderStyle' in estilo and estilo['borderStyle'] not in BORDAS:
        erros.append(f"Estilo de borda inválido no nó {nid}.")
    if 'borderWidth' in estilo and not _inteiro_entre(estilo['borderWidth'], 0, 8):
        erros.append(f"Espessura de borda inválida no nó {nid} (0 a 8).")
    return erros


def validar_estilo_conexao(estilo, eid) -> list:
    if not isinstance(estilo, dict):
        return [f"Estilo inválido na conexão {eid}."]
    erros = [f"Propriedade de estilo desconhecida '{k}' na conexão {eid}." for k in estilo
             if k not in ('color', 'width', 'dash', 'shape')]
    if 'color' in estilo and not _cor_valida(estilo['color']):
        erros.append(f"Cor inválida na conexão {eid} (use #RRGGBB).")
    if 'width' in estilo and not _inteiro_entre(estilo['width'], 1, 8):
        erros.append(f"Espessura inválida na conexão {eid} (1 a 8).")
    if 'dash' in estilo and estilo['dash'] not in TRACADOS:
        erros.append(f"Traçado inválido na conexão {eid}.")
    if 'shape' in estilo and estilo['shape'] not in FORMATOS_LINHA:
        erros.append(f"Formato de linha inválido na conexão {eid}.")
    return erros


def validar_tema(tema) -> list:
    """Tema do diagrama (também usado pelo catálogo de temas salvos)."""
    if not isinstance(tema, dict):
        return ["O tema deve ser um objeto."]
    if len(json.dumps(tema)) > MAX_TAMANHO_TEMA:
        return ["Tema grande demais."]
    erros = [f"Propriedade de tema desconhecida '{k}'." for k in tema
             if k not in ('nome', 'fundo', 'multiRamo', 'paleta', 'linha', 'niveis')]
    if 'nome' in tema and (not isinstance(tema['nome'], str) or len(tema['nome']) > 100):
        erros.append("Nome do tema inválido.")
    if tema.get('fundo') is not None and not _cor_valida(tema['fundo']):
        erros.append("Cor de fundo do tema inválida (use #RRGGBB).")
    if 'multiRamo' in tema and not isinstance(tema['multiRamo'], bool):
        erros.append("'multiRamo' deve ser verdadeiro/falso.")
    paleta = tema.get('paleta', [])
    if not isinstance(paleta, list) or len(paleta) > 12 or not all(_cor_valida(c) for c in paleta):
        erros.append("A paleta deve ter até 12 cores #RRGGBB.")
    linha = tema.get('linha', {})
    if not isinstance(linha, dict):
        erros.append("'linha' do tema inválida.")
    else:
        if 'cor' in linha and not _cor_valida(linha['cor'], permitir_ramo=True):
            erros.append("Cor da linha do tema inválida.")
        if 'largura' in linha and not _inteiro_entre(linha['largura'], 1, 8):
            erros.append("Espessura da linha do tema inválida (1 a 8).")
        if 'tracejado' in linha and linha['tracejado'] not in TRACADOS:
            erros.append("Traçado da linha do tema inválido.")
        if 'formato' in linha and linha['formato'] not in FORMATOS_LINHA:
            erros.append("Formato da linha do tema inválido.")
    niveis = tema.get('niveis', [])
    if not isinstance(niveis, list) or len(niveis) > 8:
        erros.append("O tema aceita até 8 níveis.")
    else:
        for i, nivel in enumerate(niveis):
            if not isinstance(nivel, dict):
                erros.append(f"Nível {i + 1} do tema inválido.")
                continue
            for k in nivel:
                if k not in ('fill', 'texto', 'borda', 'larguraBorda', 'tamanho', 'negrito', 'italico', 'familia'):
                    erros.append(f"Propriedade '{k}' desconhecida no nível {i + 1} do tema.")
            for k in ('fill', 'texto', 'borda'):
                if k in nivel and not _cor_valida(nivel[k], permitir_ramo=True):
                    erros.append(f"Cor '{k}' inválida no nível {i + 1} do tema.")
            if 'larguraBorda' in nivel and not _inteiro_entre(nivel['larguraBorda'], 0, 8):
                erros.append(f"Espessura de borda inválida no nível {i + 1} do tema.")
            if 'tamanho' in nivel and not _inteiro_entre(nivel['tamanho'], 8, 40):
                erros.append(f"Tamanho de fonte inválido no nível {i + 1} do tema.")
            for k in ('negrito', 'italico'):
                if k in nivel and not isinstance(nivel[k], bool):
                    erros.append(f"'{k}' deve ser verdadeiro/falso no nível {i + 1} do tema.")
            if 'familia' in nivel and nivel['familia'] not in FAMILIAS:
                erros.append(f"Fonte inválida no nível {i + 1} do tema.")
    return erros[:10]


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def validar_topologia(topologia: dict) -> list:
    """Retorna a lista de erros encontrados (vazia quando a topologia é válida)."""
    erros = []
    nodes = topologia.get('nodes')
    edges = topologia.get('edges')
    grid = topologia.get('grid_data', [])

    if not isinstance(nodes, list):
        return ["'nodes' deve ser uma lista."]
    if not isinstance(edges, list):
        return ["'edges' deve ser uma lista."]
    if not isinstance(grid, list):
        return ["'grid_data' deve ser uma lista."]
    if len(nodes) > MAX_NODES:
        return [f"Limite de {MAX_NODES} nós por diagrama excedido."]
    if len(edges) > MAX_EDGES:
        return [f"Limite de {MAX_EDGES} conexões por diagrama excedido."]

    if topologia.get('layout_modo') is not None and topologia['layout_modo'] not in MODOS_LAYOUT:
        return [f"'layout_modo' inválido. Use um destes: {', '.join(MODOS_LAYOUT)}."]
    versao_schema = topologia.get('schema_version')
    if versao_schema is not None and (isinstance(versao_schema, bool) or not isinstance(versao_schema, int)):
        return ["'schema_version' deve ser um número inteiro."]

    legenda = topologia.get('legenda')
    if legenda is not None:
        if (not isinstance(legenda, dict) or any(k not in ('mostrar', 'rotulos') for k in legenda)
                or not isinstance(legenda.get('mostrar', False), bool) or not isinstance(legenda.get('rotulos', {}), dict)
                or not all(marcador_valido(k) and isinstance(v, str) and len(v) <= 60 for k, v in legenda.get('rotulos', {}).items())):
            return ["'legenda' inválida (mostrar: verdadeiro/falso; rótulos de até 60 caracteres por marcador do catálogo)."]
    if topologia.get('mostrar_efetivo') is not None and not isinstance(topologia['mostrar_efetivo'], bool):
        return ["'mostrar_efetivo' deve ser verdadeiro/falso."]

    if topologia.get('tema') is not None:
        erros_tema = validar_tema(topologia['tema'])
        if erros_tema:
            return erros_tema

    for chave in ('lanes', 'raias_fixas'):
        lista = topologia.get(chave)
        if lista is not None and (not isinstance(lista, list) or len(lista) > MAX_RAIAS
                                  or not all(isinstance(x, str) and 0 < len(x) <= 100 for x in lista)):
            return [f"'{chave}' deve ser uma lista de até {MAX_RAIAS} nomes de raia (até 100 caracteres)."]

    cores_raias = topologia.get('raias_cores')
    if cores_raias is not None and (not isinstance(cores_raias, dict) or len(cores_raias) > MAX_RAIAS
                                    or not all(isinstance(k, str) and 0 < len(k) <= 100 and isinstance(c, str) and COR_RE.match(c)
                                               for k, c in cores_raias.items())):
        return ["'raias_cores' deve mapear nomes de raia para cores #RRGGBB."]

    ids_nos = set()
    for node in nodes:
        if not isinstance(node, dict) or 'id' not in node:
            erros.append("Cada nó deve ser um objeto com 'id'.")
            continue
        nid = str(node['id'])
        if nid in ids_nos:
            erros.append(f"ID de nó duplicado: {nid}")
        ids_nos.add(nid)
        pos = node.get('position')
        if not isinstance(pos, dict) or not (_numero(pos.get('x')) and _numero(pos.get('y'))):
            erros.append(f"Coordenadas x/y inválidas no nó {nid}.")
        data = node.get('data', {})
        if not isinstance(data, dict):
            erros.append(f"Campo 'data' inválido no nó {nid}.")
        else:
            subs = data.get('subtitles')
            if subs is not None and (not isinstance(subs, list) or len(subs) > MAX_SUBTITULOS
                                     or not all(isinstance(t, str) and len(t) <= 300 for t in subs)):
                erros.append(f"Subtítulos inválidos no nó {nid} (máx. {MAX_SUBTITULOS}, até 300 caracteres cada).")
            if data.get('collapsed') is not None and not isinstance(data['collapsed'], bool):
                erros.append(f"Campo 'collapsed' inválido no nó {nid}.")
            if data.get('style') is not None:
                erros.extend(validar_estilo_no(data['style'], nid))
            erros.extend(validar_conteudo_no(data, nid))
            if data.get('shape') is not None and data['shape'] not in FORMAS:
                erros.append(f"Forma inválida no nó {nid}.")
            colab = data.get('colab')
            if colab is not None and (not isinstance(colab, dict) or not isinstance(colab.get('id'), int)
                                      or isinstance(colab.get('id'), bool)):
                erros.append(f"Dados de colaborador inválidos no nó {nid}.")

    ids_arestas = set()
    for edge in edges:
        if not isinstance(edge, dict) or not all(k in edge for k in ('id', 'source', 'target')):
            erros.append("Cada aresta requer 'id', 'source' e 'target'.")
            continue
        if edge.get('kind') is not None and edge['kind'] not in TIPOS_CONEXAO:
            erros.append(f"Tipo de conexão inválido em '{edge.get('id')}' (use hierarquia ou relacao).")
        if edge.get('style') is not None:
            erros.extend(validar_estilo_conexao(edge['style'], edge.get('id')))
        eid = str(edge['id'])
        if eid in ids_arestas:
            erros.append(f"ID de aresta duplicado: {eid}")
        ids_arestas.add(eid)

    for linha in grid:
        if not isinstance(linha, dict):
            erros.append("Cada linha de 'grid_data' deve ser um objeto.")
            break

    return erros[:10]


def _rotulo_no(node: dict) -> str:
    return (node.get('data') or {}).get('label', '').strip() if isinstance(node.get('data'), dict) else ''


def validar_para_submissao(topologia: dict) -> list:
    """
    Regras de consistência exigidas antes de submeter o diagrama para aprovação.
    Retorna a lista de problemas (vazia quando está apto).

    As regras de fluxograma (Início/Fim, decisões) só valem quando o diagrama usa esses tipos de bloco;
    organogramas e mapas mentais não são obrigados a ter Início/Fim.
    """
    topologia = topologia or {}
    nodes = [n for n in (topologia.get('nodes') or []) if isinstance(n, dict) and 'id' in n]
    edges = [e for e in (topologia.get('edges') or []) if isinstance(e, dict)]
    problemas = []

    if not nodes:
        return ["O diagrama não possui blocos."]

    ids = {str(n['id']): n for n in nodes}
    saidas = {i: 0 for i in ids}
    entradas = {i: 0 for i in ids}

    for e in edges:
        origem, destino = str(e.get('source')), str(e.get('target'))
        if origem not in ids or destino not in ids:
            problemas.append(f"Conexão '{e.get('id')}' aponta para um bloco que não existe.")
            continue
        saidas[origem] += 1
        entradas[destino] += 1

    for i, n in ids.items():
        if not _rotulo_no(n):
            problemas.append(f"Bloco #{i} está sem texto.")

    eh_fluxograma = any(n.get('type') in ('start', 'end', 'decision') for n in nodes)
    if eh_fluxograma:
        if not any(n.get('type') == 'start' for n in nodes):
            problemas.append("O fluxograma precisa de um bloco de Início.")
        if not any(n.get('type') == 'end' for n in nodes):
            problemas.append("O fluxograma precisa de um bloco de Fim.")
        for i, n in ids.items():
            if n.get('type') == 'decision' and saidas[i] < 2:
                problemas.append(f"A decisão '{_rotulo_no(n) or i}' precisa de pelo menos 2 saídas (ex.: Sim / Não).")

    if len(nodes) > 1:
        for i, n in ids.items():
            if saidas[i] == 0 and entradas[i] == 0:
                problemas.append(f"O bloco '{_rotulo_no(n) or i}' está isolado (sem nenhuma conexão).")

    return problemas

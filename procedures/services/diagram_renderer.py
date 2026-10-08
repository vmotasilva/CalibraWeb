# -*- coding: utf-8 -*-
"""
Renderização vetorial (reportlab) da topologia do diagrama para o PDF DOC.071.
Reproduz a geometria do editor (raias, blocos, decisões e conexões ortogonais),
dispensando a captura de imagem no navegador.
"""

import io

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import Flowable

from .diagram_raias import raias_do_diagrama
from .diagram_arvore import MODOS_ARVORE, montar_arvore, ramos_recolhidos
from .diagram_conteudo import POR_ID, contagem_efetivo, eh_vaga, marcador_valido
from .diagram_estilo import contexto_dos_nos, nome_da_fonte, resolver_estilo_conexao, resolver_estilo_no

FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

# Dimensões do editor (px de canvas)
W_PROCESS, H_PROCESS = 180, 64
W_COLAB = 200
H_SUBTITULO = 13
W_STARTEND, H_STARTEND = 140, 48
SIZE_DECISION = 110
LANE_TOP, LANE_LEFT, LANE_BAND = 40, 20, 40
LANE_MIN_H = 220
MARGIN = 40

DARK_BG = {'#2563eb', '#334155', '#ef4444', '#8b5cf6'}


def desenhar_marcador_pdf(c, marcador: dict, cx: float, cy: float, tam: float):
    """Marcador (prioridade, progresso, bandeira, estrela, pessoa) centrado em (cx, cy), coordenadas do PDF."""
    r = tam / 2
    cor = colors.HexColor(marcador['cor'])
    tipo = marcador['tipo']
    c.saveState()
    c.setFillColor(cor)
    c.setStrokeColor(cor)
    if tipo == 'numero':
        c.circle(cx, cy, r, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', tam * 0.68)
        c.drawCentredString(cx, cy - tam * 0.24, str(marcador['valor']))
    elif tipo == 'progresso':
        valor = marcador['valor']
        if valor == 100:
            c.circle(cx, cy, r, stroke=0, fill=1)
            c.setStrokeColor(colors.white)
            c.setLineWidth(max(1, tam / 8))
            p = c.beginPath()
            p.moveTo(cx - r * 0.5, cy - r * 0.05)
            p.lineTo(cx - r * 0.12, cy - r * 0.42)
            p.lineTo(cx + r * 0.52, cy + r * 0.38)
            c.drawPath(p, stroke=1, fill=0)
        else:
            c.setFillColor(colors.white)
            c.setLineWidth(max(0.8, tam / 10))
            c.circle(cx, cy, r * 0.92, stroke=1, fill=1)
            if valor > 0:
                c.setFillColor(cor)
                c.wedge(cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7, 90, -valor * 3.6, stroke=0, fill=1)
    elif tipo == 'bandeira':
        c.setLineWidth(max(1, tam / 9))
        c.line(cx - r * 0.55, cy - r, cx - r * 0.55, cy + r)
        p = c.beginPath()
        p.moveTo(cx - r * 0.45, cy + r * 0.9)
        p.lineTo(cx + r * 0.85, cy + r * 0.9)
        p.lineTo(cx + r * 0.4, cy + r * 0.3)
        p.lineTo(cx + r * 0.85, cy - r * 0.3)
        p.lineTo(cx - r * 0.45, cy - r * 0.3)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    elif tipo == 'estrela':
        import math
        p = c.beginPath()
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            raio = r if i % 2 == 0 else r * 0.45
            px, py = cx + raio * math.cos(ang), cy + raio * math.sin(ang) - r * 0.05
            (p.moveTo if i == 0 else p.lineTo)(px, py)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    elif tipo == 'pessoa':
        c.circle(cx, cy + r * 0.45, r * 0.4, stroke=0, fill=1)
        c.wedge(cx - r * 0.9, cy - r * 0.85 - r * 1.1, cx + r * 0.9, cy - r * 0.85 + r * 1.1, 0, 180, stroke=0, fill=1)
    c.restoreState()


class MarcadorFlowable(Flowable):
    """Marcador como célula de tabela (legenda)."""

    def __init__(self, marcador: dict, tam: float = 12):
        super().__init__()
        self.marcador, self.tam = marcador, tam
        self.width = self.height = tam

    def wrap(self, w, h):
        return self.tam, self.tam

    def draw(self):
        desenhar_marcador_pdf(self.canv, self.marcador, self.tam / 2, self.tam / 2, self.tam)


def _txt(valor) -> str:
    """Texto seguro para as fontes padrão do PDF (Latin-1): remove emojis e símbolos não suportados."""
    if valor is None:
        return ''
    return str(valor).encode('latin-1', 'ignore').decode('latin-1').strip()


def _cor(hex_str, padrao):
    try:
        return colors.HexColor(hex_str)
    except Exception:
        return padrao


def _dados(node) -> dict:
    return node.get('data') if isinstance(node.get('data'), dict) else {}


def _subtitulos(node) -> list:
    return [_txt(t) for t in (_dados(node).get('subtitles') or []) if _txt(t)]


def _colab(node):
    c = _dados(node).get('colab')
    return c if isinstance(c, dict) else None


def nome_exibicao(colab: dict) -> str:
    """Nome completo ou, quando nomeCurto estiver ligado, primeiro + último nome."""
    nome = (colab.get('nome') or '').strip()
    partes = nome.split()
    if colab.get('nomeCurto') and len(partes) > 2:
        return f"{partes[0]} {partes[-1]}"
    return nome


def _tamanho(node):
    tipo = node.get('type')
    if tipo in ('start', 'end'):
        return W_STARTEND, H_STARTEND
    if tipo == 'decision':
        return SIZE_DECISION, SIZE_DECISION
    largura = W_COLAB if _colab(node) else W_PROCESS
    return largura, H_PROCESS + H_SUBTITULO * len(_subtitulos(node))


class DiagramaFlowable(Flowable):
    """Desenha o diagrama dentro de uma caixa max_w x max_h, preservando a proporção."""

    def __init__(self, topologia: dict, max_w: float, max_h: float, fotos: dict = None, raias_cores: dict = None):
        super().__init__()
        self.raias_cores = {str(k).lower(): v for k, v in (raias_cores or {}).items()}  # {nome_raia: '#RRGGBB'}
        self.fotos = fotos or {}  # {id_colaborador: bytes da imagem}
        todos = [
            n for n in (topologia.get('nodes') or [])
            if isinstance(n, dict) and isinstance(n.get('position'), dict) and 'id' in n
        ]
        self.edges = [e for e in (topologia.get('edges') or []) if isinstance(e, dict)]
        self.modo = topologia.get('layout_modo') or 'raias'
        self.tema = topologia.get('tema') if isinstance(topologia.get('tema'), dict) else None
        self.fundo = (self.tema or {}).get('fundo')
        self.estilo_linha = topologia.get('estilo_linha') or 'ortogonal'
        arvore = montar_arvore(todos, self.edges)
        self.ctx_estilo = contexto_dos_nos(arvore)
        self.efetivo = contagem_efetivo(todos, arvore) if topologia.get('mostrar_efetivo') is True else None
        self.com_filhos = {i for i, f in arvore['filhos'].items() if f}
        self.em_arvore = self.modo in MODOS_ARVORE
        # ramos recolhidos no editor não são desenhados; o bloco recolhido mostra o contador "+N"
        ocultos, self.contagem_ocultos = ramos_recolhidos(todos, self.edges) if self.em_arvore else (set(), {})
        self.nodes = [n for n in todos if str(n['id']) not in ocultos]
        self.grid = topologia.get('grid_data') or []
        self.by_id = {str(n['id']): n for n in self.nodes}

        self.lanes = [] if self.em_arvore else raias_do_diagrama(topologia)  # modos em árvore não usam raias
        self.lane_h = {}
        for lane in self.lanes:
            ys = [n['position']['y'] for n in self.nodes
                  if ((n.get('data') or {}).get('lane') or 'Geral') == lane]
            self.lane_h[lane] = max(LANE_MIN_H, (max(ys) - min(ys)) + 160) if ys else LANE_MIN_H

        self.cw = max([n['position']['x'] + _tamanho(n)[0] for n in self.nodes] + [LANE_LEFT + (0 if self.em_arvore else 400)]) + MARGIN
        max_y = max([n['position']['y'] + _tamanho(n)[1] for n in self.nodes] + [0]) + MARGIN
        self.ch = max_y if self.em_arvore else max(LANE_TOP + sum(self.lane_h.values()) + 20, max_y)

        self.scale = min(max_w / self.cw, max_h / self.ch, 1.0)
        self.width = self.cw * self.scale
        self.height = self.ch * self.scale

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    # --- utilidades de desenho -------------------------------------------------
    def _y(self, y):
        return self.ch - y  # canvas (topo=0) -> PDF (base=0)

    def _texto_centrado(self, c, texto, cx, cy, largura, tam=11, cor=colors.HexColor('#0F172A'),
                        fonte=FONT_BOLD, max_linhas=4, alinhar='center', riscar=False):
        linhas = (simpleSplit(texto, fonte, tam, largura) or [''])[:max_linhas]
        lead = tam * 1.2
        topo = cy + (len(linhas) - 1) * lead / 2
        c.setFont(fonte, tam)
        c.setFillColor(cor)
        c.setStrokeColor(cor)
        c.setLineWidth(max(0.5, tam / 14))
        for i, ln in enumerate(linhas):
            yy = topo - i * lead - tam * 0.3
            larg_ln = c.stringWidth(ln, fonte, tam)
            if alinhar == 'left':
                x0 = cx - largura / 2
            elif alinhar == 'right':
                x0 = cx + largura / 2 - larg_ln
            else:
                x0 = cx - larg_ln / 2
            c.drawString(x0, yy, ln)
            if riscar:
                c.line(x0, yy + tam * 0.3, x0 + larg_ln, yy + tam * 0.3)

    def draw(self):
        c = self.canv
        c.saveState()
        c.scale(self.scale, self.scale)
        if self.fundo:
            c.setFillColor(_cor(self.fundo, colors.white))
            c.rect(0, 0, self.cw, self.ch, stroke=0, fill=1)
        self._desenhar_raias(c)
        for e in self.edges:
            self._desenhar_aresta(c, e)
        for n in self.nodes:
            self._desenhar_no(c, n)
            self._desenhar_extras(c, n)
            if str(n['id']) in self.contagem_ocultos:
                self._desenhar_contador(c, n, self.contagem_ocultos[str(n['id'])])
        c.restoreState()

    def _desenhar_extras(self, c, n):
        """Marcadores (topo esquerdo), indicadores de nota/link/alerta (topo direito), selo VAGO e efetivo do ramo."""
        dados = _dados(n)
        w, h = _tamanho(n)
        x, y = n['position']['x'], n['position']['y']
        topo = self._y(y)

        marcadores = [m for m in (dados.get('markers') or []) if marcador_valido(m)]
        for i, marcador_id in enumerate(marcadores):
            desenhar_marcador_pdf(c, POR_ID[marcador_id], x + 9 + i * 15, topo, 12)

        glifos = []   # (letra, cor)
        colab = _colab(n)
        if colab and colab.get('removido'):
            glifos.append(('!', '#B45309'))
        if (dados.get('nota') or '').strip():
            glifos.append(('N', '#475569'))
        for _ in (dados.get('links') or []):
            glifos.append(('L', '#2563EB'))
        for i, (letra, cor) in enumerate(glifos):
            cx = x + w - 6 - i * 15
            c.saveState()
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor(cor))
            c.setLineWidth(1)
            c.circle(cx, topo, 6.5, stroke=1, fill=1)
            c.setFillColor(colors.HexColor(cor))
            c.setFont('Helvetica-Bold', 7)
            c.drawCentredString(cx, topo - 2.4, letra)
            c.restoreState()

        if eh_vaga(n):
            c.saveState()
            c.setFillColor(colors.HexColor('#FEF3C7'))
            c.setStrokeColor(colors.HexColor('#FCD34D'))
            c.setLineWidth(0.8)
            c.roundRect(x + 6, self._y(y + h) + 4, 34, 11, 5, stroke=1, fill=1)
            c.setFillColor(colors.HexColor('#92400E'))
            c.setFont('Helvetica-Bold', 7)
            c.drawCentredString(x + 23, self._y(y + h) + 7, 'VAGO')
            c.restoreState()

        if self.efetivo is not None and str(n['id']) in self.com_filhos:
            cont = self.efetivo.get(str(n['id']), {})
            if cont.get('pessoas') or cont.get('vagas'):
                texto = f"{cont['pessoas']}" + (f" - {cont['vagas']} vaga{'s' if cont['vagas'] > 1 else ''}" if cont['vagas'] else '')
                c.saveState()
                c.setFont('Helvetica-Bold', 7)
                larg = c.stringWidth(texto, 'Helvetica-Bold', 7) + 12
                base = self._y(y + h)
                c.setFillColor(colors.HexColor('#0F172A'))
                c.setStrokeColor(colors.white)
                c.roundRect(x + w - 6 - larg, base - 7, larg, 14, 7, stroke=1, fill=1)
                c.setFillColor(colors.white)
                c.drawCentredString(x + w - 6 - larg / 2, base - 2.5, texto)
                c.restoreState()

    def _desenhar_contador(self, c, n, quantidade):
        """Selo "+N" no ponto onde fica o botão de recolher do editor."""
        w, h = _tamanho(n)
        x, y = n['position']['x'], n['position']['y']
        if self.modo == 'logico':
            cx, cy = x + w, y + h / 2
        elif self.modo == 'arvore':
            cx, cy = x + 22, y + h
        else:
            cx, cy = x + w / 2, y + h
        texto = f'+{quantidade}'
        c.saveState()
        c.setFont(FONT_BOLD, 7)
        larg = max(18, c.stringWidth(texto, FONT_BOLD, 7) + 8)
        c.setFillColor(colors.HexColor('#2563EB'))
        c.setStrokeColor(colors.white)
        c.setLineWidth(1)
        c.roundRect(cx - larg / 2, self._y(cy) - 7, larg, 14, 7, stroke=1, fill=1)
        c.setFillColor(colors.white)
        c.drawCentredString(cx, self._y(cy) - 2.5, texto)
        c.restoreState()

    # --- raias -----------------------------------------------------------------
    def _desenhar_raias(self, c):
        y = LANE_TOP
        for lane in self.lanes:
            h = self.lane_h[lane]
            c.setFillColor(colors.HexColor('#F1F5F9'))
            c.setStrokeColor(colors.HexColor('#CBD5E1'))
            c.setLineWidth(1)
            c.setDash(4, 3)
            c.rect(LANE_LEFT, self._y(y + h), self.cw - LANE_LEFT, h, stroke=1, fill=1)
            c.setDash()
            c.setFillColor(_cor(self.raias_cores.get(str(lane).lower()) or '#334155', colors.HexColor('#334155')))
            c.rect(LANE_LEFT, self._y(y + h), LANE_BAND, h, stroke=0, fill=1)
            c.saveState()
            c.translate(LANE_LEFT + LANE_BAND / 2 + 4, self._y(y + h / 2))
            c.rotate(90)
            c.setFillColor(colors.white)
            c.setFont(FONT_BOLD, 14)
            nome = _txt(lane).upper()
            while nome and c.stringWidth(nome, FONT_BOLD, 14) > h - 20:
                nome = nome[:-2]
            c.drawCentredString(0, -5, nome)
            c.restoreState()
            y += h

    # --- nós -------------------------------------------------------------------
    # --- estilo ------------------------------------------------------------------
    def _estilo(self, n):
        ctx = {'tema': self.tema, **self.ctx_estilo.get(str(n['id']), {})}
        estilo = resolver_estilo_no(n, ctx)
        if eh_vaga(n) and 'borderStyle' not in estilo:
            estilo['borderStyle'] = 'dashed'   # posição vaga: contorno tracejado, como no editor
        return estilo

    @staticmethod
    def _tracejado(estilo_borda, largura):
        if estilo_borda == 'dashed':
            return (largura * 4, largura * 2.5)
        if estilo_borda == 'dotted':
            return (largura, largura * 2)
        return ()

    def _desenhar_caixa(self, c, x, y, w, h, raio, fill, borda, largura, st, forma=None):
        """Caixa do bloco respeitando preenchimento, borda (cor, espessura, traçado) e formas especiais."""
        c.saveState()
        estilo_borda = st.get('borderStyle', 'solid')
        larg = st.get('borderWidth', largura)
        cor_borda = _cor(st['borderColor'], borda) if st.get('borderColor') else borda
        topo, base = self._y(y), self._y(y + h)
        especial = forma in ('brackets', 'underline', 'plain')

        # preenchimento: formas especiais só preenchem quando há preenchimento definido
        if st.get('noFill'):
            fill = None
        elif especial:
            fill = _cor(st['fill'], colors.white) if st.get('fill') else None
        if fill is not None:
            c.setFillColor(fill)
            c.roundRect(x, base, w, h, 0 if especial else raio, stroke=0, fill=1)

        desenha_borda = estilo_borda != 'none' and larg > 0
        if especial:
            cor_borda = _cor(st['borderColor'], colors.HexColor('#334155')) if st.get('borderColor') else colors.HexColor('#334155')
        if desenha_borda and forma != 'plain':
            c.setStrokeColor(cor_borda)
            c.setLineWidth(larg)
            c.setDash(*self._tracejado(estilo_borda, larg))
            if forma == 'underline':
                c.line(x, base, x + w, base)
            elif forma == 'brackets':
                tam = min(14, w / 3, h / 3)
                for xa, ya, dx, dy in ((x, topo, 1, -1), (x + w, topo, -1, -1), (x, base, 1, 1), (x + w, base, -1, 1)):
                    p = c.beginPath()
                    p.moveTo(xa + dx * tam, ya)
                    p.lineTo(xa, ya)
                    p.lineTo(xa, ya + dy * tam)
                    c.drawPath(p, stroke=1, fill=0)
            else:
                c.roundRect(x, base, w, h, raio, stroke=1, fill=0)
        c.restoreState()

    def _desenhar_no(self, c, n):
        data = _dados(n)
        tipo = n.get('type')
        w, h = _tamanho(n)
        x, y = n['position']['x'], n['position']['y']
        label = _txt(data.get('label'))
        st = self._estilo(n)
        bg_custom = st.get('fill')
        forma = data.get('shape') if data.get('shape') in ('brackets', 'underline', 'plain') else None

        fonte = nome_da_fonte(st.get('fontFamily'), st.get('bold', True), st.get('italic', False))
        tam_px = st.get('fontSize')
        riscar = bool(st.get('strike'))
        alinhar = st.get('align', 'center')
        cor_estilo = _cor(st['color'], None) if st.get('color') else None

        if tipo in ('start', 'end'):
            fundo, borda, texto = (('#EFF6FF', '#3B82F6', '#1D4ED8') if tipo == 'start'
                                   else ('#ECFDF5', '#10B981', '#047857'))
            self._desenhar_caixa(c, x, y, w, h, h / 2, _cor(bg_custom or fundo, colors.white), _cor(borda, colors.grey), 1.6, st)
            cor_txt = cor_estilo or (colors.white if (bg_custom or '').lower() in DARK_BG else _cor(texto, colors.black))
            self._texto_centrado(c, label or ('INICIO' if tipo == 'start' else 'FIM'),
                                 x + w / 2, self._y(y + h / 2), w - 20, round(tam_px * 0.75, 1) if tam_px else 10,
                                 cor_txt, fonte=fonte, max_linhas=2, alinhar=alinhar, riscar=riscar)
        elif tipo == 'decision':
            cx, cy = x + w / 2, self._y(y + h / 2)
            r = 55
            c.saveState()
            if not st.get('noFill'):
                c.setFillColor(_cor(bg_custom or '#FFFBEB', colors.white))
            larg = st.get('borderWidth', 1.6)
            estilo_borda = st.get('borderStyle', 'solid')
            c.setStrokeColor(_cor(st['borderColor'], colors.HexColor('#F59E0B')) if st.get('borderColor') else colors.HexColor('#F59E0B'))
            c.setLineWidth(larg)
            c.setDash(*self._tracejado(estilo_borda, larg))
            p = c.beginPath()
            p.moveTo(cx, cy + r)
            p.lineTo(cx + r, cy)
            p.lineTo(cx, cy - r)
            p.lineTo(cx - r, cy)
            p.close()
            c.drawPath(p, stroke=1 if (estilo_borda != 'none' and larg > 0) else 0, fill=0 if st.get('noFill') else 1)
            c.restoreState()
            cor_txt = cor_estilo or (colors.white if (bg_custom or '').lower() in DARK_BG else colors.HexColor('#92400E'))
            self._texto_centrado(c, label or 'Decisao?', cx, cy, 70, round(tam_px * 0.75, 1) if tam_px else 9,
                                 cor_txt, fonte=fonte, max_linhas=4, alinhar=alinhar, riscar=riscar)
        else:
            central = data.get('isCentral')
            fundo = bg_custom or ('#2563EB' if central else '#FFFFFF')
            escuro = bool(central) or fundo.lower() in DARK_BG
            raio = h / 2 if data.get('shape') in ('pill', 'circle') else 8
            self._desenhar_caixa(c, x, y, w, h, raio, _cor(fundo, colors.white),
                                 colors.HexColor('#1D4ED8' if central else '#94A3B8'), 1.6, st, forma)
            cor_txt = cor_estilo or (colors.white if escuro else colors.HexColor('#0F172A'))
            cor_sub = colors.HexColor('#CBD5E1') if (escuro and not cor_estilo) else (cor_estilo or colors.HexColor('#64748B'))
            if cor_estilo and not escuro:
                cor_sub = colors.HexColor('#64748B')

            extras = []
            tags = [_txt(t) for t in (data.get('customTags') or []) if _txt(t)]
            if tags:
                extras.append(' | '.join(tags))
            ref = _txt(data.get('documentRef'))
            if ref:
                extras.append('Doc: ' + ref)
            subs = _subtitulos(n)
            colab = _colab(n)
            imagem = data.get('imagem') if isinstance(data.get('imagem'), dict) and not colab else None
            lateral = bool(colab or imagem)

            # Área de texto: com colaborador (foto do RH) ou imagem, ela ocupa a esquerda (círculo vazio sem foto)
            tx0, tx1 = x, x + w
            if lateral:
                diam = 40
                fx, fy = x + 10, self._y(y + h / 2) - diam / 2
                self._desenhar_foto(c, colab.get('id') if colab else f"img-{imagem.get('id')}", fx, fy, diam)
                tx0 = x + 10 + diam + 8
                tx1 = x + w - 8
            largura_txt = tx1 - tx0 - (0 if lateral else 20)
            cx = (tx0 + tx1) / 2

            titulo = nome_exibicao(colab) if colab else label
            tam_titulo = round(tam_px * 0.75, 1) if tam_px else 9
            linhas = []  # (texto, fonte, tamanho, cor, é_título)
            for ln in (simpleSplit(titulo, fonte, tam_titulo, largura_txt) or [''])[:2 if (colab or subs) else 4]:
                linhas.append((ln, fonte, tam_titulo, cor_txt, True))
            if colab and _txt(colab.get('cargo')):
                for ln in (simpleSplit(_txt(colab.get('cargo')), FONT, 7.5, largura_txt) or [''])[:1]:
                    linhas.append((ln, FONT, 7.5, cor_sub, False))
            for sub in subs:
                for ln in (simpleSplit(sub, FONT, 7.5, largura_txt) or [''])[:1]:
                    linhas.append((ln, FONT, 7.5, cor_sub, False))
            if extras:
                linhas.append((' - '.join(extras)[:46], FONT, 6.5, cor_sub, False))

            altura_total = sum(tam * 1.25 for _, _, tam, _, _ in linhas)
            ycur = self._y(y + h / 2) + altura_total / 2
            for texto, fnt, tam, cor, eh_titulo in linhas:
                ycur -= tam * 1.25
                c.setFont(fnt, tam)
                c.setFillColor(cor)
                larg_ln = c.stringWidth(texto, fnt, tam)
                if lateral or alinhar == 'left':
                    x0 = tx0 + (0 if lateral else 10)
                elif alinhar == 'right':
                    x0 = tx1 - 10 - larg_ln
                else:
                    x0 = cx - larg_ln / 2
                c.drawString(x0, ycur + tam * 0.3, texto)
                if riscar and eh_titulo:
                    c.setStrokeColor(cor)
                    c.setLineWidth(max(0.5, tam / 14))
                    c.line(x0, ycur + tam * 0.6, x0 + larg_ln, ycur + tam * 0.6)

    def _desenhar_foto(self, c, colab_id, x, y, diam):
        """Foto circular do colaborador; sem foto, apenas o espaço (círculo neutro, sem ícone)."""
        c.saveState()
        raio = diam / 2
        dados = self.fotos.get(colab_id)
        desenhou = False
        if dados:
            try:
                p = c.beginPath()
                p.circle(x + raio, y + raio, raio)
                c.clipPath(p, stroke=0, fill=0)
                c.drawImage(ImageReader(io.BytesIO(dados)), x, y, diam, diam, preserveAspectRatio=True, anchor='c', mask='auto')
                desenhou = True
            except Exception:
                desenhou = False
        c.restoreState()
        if not desenhou:
            c.saveState()
            c.setFillColor(colors.HexColor('#F1F5F9'))
            c.setStrokeColor(colors.HexColor('#E2E8F0'))
            c.setLineWidth(0.8)
            c.circle(x + raio, y + raio, raio, stroke=1, fill=1)
            c.restoreState()

    # --- conexões --------------------------------------------------------------
    def _desenhar_aresta(self, c, e):
        s = self.by_id.get(str(e.get('source')))
        t = self.by_id.get(str(e.get('target')))
        if not s or not t:
            return
        sw, sh = _tamanho(s)
        tw, th = _tamanho(t)
        sl, st = s['position']['x'], s['position']['y']
        tl, tt = t['position']['x'], t['position']['y']
        sr, sb = sl + sw, st + sh
        tr, tb = tl + tw, tt + th
        smx, smy = sl + sw / 2, st + sh / 2
        tmx, tmy = tl + tw / 2, tt + th / 2
        label = _txt(e.get('label'))
        nao = s.get('type') == 'decision' and label.lower() in ('nao', 'não')

        livre = (e.get('kind') or 'hierarquia') == 'relacao'
        ctx_destino = self.ctx_estilo.get(str(e.get('target')), {})
        est = resolver_estilo_conexao(e, {'tema': self.tema, 'ramo': ctx_destino.get('ramo')})
        formato = est.get('shape') or self.estilo_linha
        if self.modo == 'arvore' and not livre and e.get('sourceHandle') == 'bottom' and e.get('targetHandle') == 'left':
            tronco = sl + 20
            pts = [(tronco, sb), (tronco, tmy), (tl, tmy)]
        elif livre:
            pts = [(smx, smy), (tmx, tmy)]
        elif e.get('sourceHandle') == 'right' or nao:
            pts = self._horizontal(sr, smy, tl, tmy)
        elif tt >= sb - 10:
            pts = self._vertical(smx, sb, tmx, tt)
        elif tb <= st + 10:
            lx = max(sr, tr) + 40
            pts = [(sr, smy), (lx, smy), (lx, tmy), (tr, tmy)]
        else:
            pts = self._horizontal(sr, smy, tl, tmy) if tl >= sr else self._horizontal(sl, smy, tr, tmy)

        cor_linha = _cor(est['color'], colors.HexColor('#64748B')) if est.get('color') else colors.HexColor('#64748B')
        largura = (est['width'] * 0.65) if est.get('width') else 1.4
        tracado = est.get('dash') or ('dashed' if livre else 'solid')
        c.setStrokeColor(cor_linha)
        c.setFillColor(cor_linha)
        c.setLineWidth(largura)
        if tracado != 'solid':
            c.setDash(*self._tracejado(tracado, largura))
        (sx0, sy0), (sx1, sy1) = pts[0], pts[-1]
        p = c.beginPath()
        p.moveTo(sx0, self._y(sy0))
        if (formato == 'curva' or livre) and not (self.modo == 'arvore' and not livre and e.get('sourceHandle') == 'bottom' and e.get('targetHandle') == 'left'):
            dx, dy = (sx1 - sx0) * 0.5, (sy1 - sy0) * 0.5
            vertical = e.get('sourceHandle') == 'bottom' or (tt >= sb - 10 and e.get('sourceHandle') != 'right')
            if vertical:   # fluxo vertical (organogramas): a curva sai e chega na vertical, como no editor
                p.curveTo(sx0, self._y(sy0 + dy), sx1, self._y(sy1 - dy), sx1, self._y(sy1))
                pts = [(sx1, sy1 - dy), (sx1, sy1)]
            else:
                p.curveTo(sx0 + dx, self._y(sy0), sx1 - dx, self._y(sy1), sx1, self._y(sy1))
                pts = [(sx1 - dx, sy1), (sx1, sy1)]
        elif formato == 'reta' and not livre:
            p.lineTo(sx1, self._y(sy1))
            pts = [(sx0, sy0), (sx1, sy1)]
        else:
            for px, py in pts[1:]:
                p.lineTo(px, self._y(py))
        c.drawPath(p, stroke=1, fill=0)
        c.setDash()
        self._seta(c, pts[-2], pts[-1])

        if label:
            i = len(pts) // 2
            a, b = pts[i - 1], pts[i]
            lx, ly = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            c.setFont(FONT_BOLD, 8)
            larg = c.stringWidth(label, FONT_BOLD, 8) + 8
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor('#CBD5E1'))
            c.setLineWidth(0.6)
            c.roundRect(lx - larg / 2, self._y(ly) - 6, larg, 12, 4, stroke=1, fill=1)
            c.setFillColor(colors.HexColor('#334155'))
            c.drawCentredString(lx, self._y(ly) - 2.5, label)

    @staticmethod
    def _vertical(sx, sy, ex, ey):
        if abs(sx - ex) < 4:
            return [(sx, sy), (ex, ey)]
        mid = round(sy + (ey - sy) / 2)
        return [(sx, sy), (sx, mid), (ex, mid), (ex, ey)]

    @staticmethod
    def _horizontal(sx, sy, ex, ey):
        if abs(sy - ey) < 4:
            return [(sx, sy), (ex, ey)]
        mid = round(sx + (ex - sx) / 2)
        return [(sx, sy), (mid, sy), (mid, ey), (ex, ey)]

    def _seta(self, c, a, b):
        ax, ay, bx, by = a[0], self._y(a[1]), b[0], self._y(b[1])
        dx, dy = bx - ax, by - ay
        ln = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / ln, dy / ln
        tam = 9
        p = c.beginPath()
        p.moveTo(bx, by)
        p.lineTo(bx - ux * tam + uy * tam * 0.4, by - uy * tam - ux * tam * 0.4)
        p.lineTo(bx - ux * tam - uy * tam * 0.4, by - uy * tam + ux * tam * 0.4)
        p.close()
        c.drawPath(p, stroke=0, fill=1)

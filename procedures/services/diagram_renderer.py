# -*- coding: utf-8 -*-
"""
Renderização vetorial (reportlab) da topologia do diagrama para o PDF DOC.071.
Reproduz a geometria do editor (raias, blocos, decisões e conexões ortogonais),
dispensando a captura de imagem no navegador.
"""

from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import Flowable

FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

# Dimensões do editor (px de canvas)
W_PROCESS, H_PROCESS = 180, 64
W_STARTEND, H_STARTEND = 140, 48
SIZE_DECISION = 110
LANE_TOP, LANE_LEFT, LANE_BAND = 40, 20, 40
LANE_MIN_H = 220
MARGIN = 40

DARK_BG = {'#2563eb', '#334155', '#ef4444', '#8b5cf6'}


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


def _tamanho(node):
    tipo = node.get('type')
    if tipo in ('start', 'end'):
        return W_STARTEND, H_STARTEND
    if tipo == 'decision':
        return SIZE_DECISION, SIZE_DECISION
    return W_PROCESS, H_PROCESS


def _raias(nodes, grid):
    ordem = []
    nomes = [(n.get('data') or {}).get('lane') or 'Geral' for n in nodes]
    nomes += [(r or {}).get('lane') or 'Geral' for r in grid if isinstance(r, dict)]
    for lane in nomes:
        if lane not in ordem:
            ordem.append(lane)
    return ordem or ['Geral']


class DiagramaFlowable(Flowable):
    """Desenha o diagrama dentro de uma caixa max_w x max_h, preservando a proporção."""

    def __init__(self, topologia: dict, max_w: float, max_h: float):
        super().__init__()
        self.nodes = [
            n for n in (topologia.get('nodes') or [])
            if isinstance(n, dict) and isinstance(n.get('position'), dict) and 'id' in n
        ]
        self.edges = [e for e in (topologia.get('edges') or []) if isinstance(e, dict)]
        self.grid = topologia.get('grid_data') or []
        self.by_id = {str(n['id']): n for n in self.nodes}

        self.lanes = _raias(self.nodes, self.grid)
        self.lane_h = {}
        for lane in self.lanes:
            ys = [n['position']['y'] for n in self.nodes
                  if ((n.get('data') or {}).get('lane') or 'Geral') == lane]
            self.lane_h[lane] = max(LANE_MIN_H, (max(ys) - min(ys)) + 160) if ys else LANE_MIN_H

        self.cw = max([n['position']['x'] + _tamanho(n)[0] for n in self.nodes] + [LANE_LEFT + 400]) + MARGIN
        max_y = max([n['position']['y'] + _tamanho(n)[1] for n in self.nodes] + [0]) + MARGIN
        self.ch = max(LANE_TOP + sum(self.lane_h.values()) + 20, max_y)

        self.scale = min(max_w / self.cw, max_h / self.ch, 1.0)
        self.width = self.cw * self.scale
        self.height = self.ch * self.scale

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    # --- utilidades de desenho -------------------------------------------------
    def _y(self, y):
        return self.ch - y  # canvas (topo=0) -> PDF (base=0)

    def _texto_centrado(self, c, texto, cx, cy, largura, tam=11, cor=colors.HexColor('#0F172A'),
                        fonte=FONT_BOLD, max_linhas=4):
        linhas = (simpleSplit(texto, fonte, tam, largura) or [''])[:max_linhas]
        lead = tam * 1.2
        topo = cy + (len(linhas) - 1) * lead / 2
        c.setFont(fonte, tam)
        c.setFillColor(cor)
        for i, ln in enumerate(linhas):
            c.drawCentredString(cx, topo - i * lead - tam * 0.3, ln)

    def draw(self):
        c = self.canv
        c.saveState()
        c.scale(self.scale, self.scale)
        self._desenhar_raias(c)
        for e in self.edges:
            self._desenhar_aresta(c, e)
        for n in self.nodes:
            self._desenhar_no(c, n)
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
            c.setFillColor(colors.HexColor('#334155'))
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
    def _desenhar_no(self, c, n):
        data = n.get('data') or {}
        tipo = n.get('type')
        w, h = _tamanho(n)
        x, y = n['position']['x'], n['position']['y']
        label = _txt(data.get('label'))
        bg_custom = data.get('bgColor')
        c.setLineWidth(1.6)

        if tipo in ('start', 'end'):
            fundo, borda, texto = (('#EFF6FF', '#3B82F6', '#1D4ED8') if tipo == 'start'
                                   else ('#ECFDF5', '#10B981', '#047857'))
            c.setFillColor(_cor(bg_custom or fundo, colors.white))
            c.setStrokeColor(_cor(borda, colors.grey))
            c.roundRect(x, self._y(y + h), w, h, h / 2, stroke=1, fill=1)
            cor_txt = colors.white if (bg_custom or '').lower() in DARK_BG else _cor(texto, colors.black)
            self._texto_centrado(c, label or ('INICIO' if tipo == 'start' else 'FIM'),
                                 x + w / 2, self._y(y + h / 2), w - 20, 10, cor_txt, max_linhas=2)
        elif tipo == 'decision':
            cx, cy = x + w / 2, self._y(y + h / 2)
            r = 55
            c.setFillColor(_cor(bg_custom or '#FFFBEB', colors.white))
            c.setStrokeColor(colors.HexColor('#F59E0B'))
            p = c.beginPath()
            p.moveTo(cx, cy + r)
            p.lineTo(cx + r, cy)
            p.lineTo(cx, cy - r)
            p.lineTo(cx - r, cy)
            p.close()
            c.drawPath(p, stroke=1, fill=1)
            cor_txt = colors.white if (bg_custom or '').lower() in DARK_BG else colors.HexColor('#92400E')
            self._texto_centrado(c, label or 'Decisao?', cx, cy, 70, 9, cor_txt, max_linhas=4)
        else:
            central = data.get('isCentral')
            fundo = bg_custom or ('#2563EB' if central else '#FFFFFF')
            escuro = bool(central) or fundo.lower() in DARK_BG
            c.setFillColor(_cor(fundo, colors.white))
            c.setStrokeColor(colors.HexColor('#1D4ED8' if central else '#94A3B8'))
            raio = h / 2 if data.get('shape') in ('pill', 'circle') else 8
            c.roundRect(x, self._y(y + h), w, h, raio, stroke=1, fill=1)
            cor_txt = colors.white if escuro else colors.HexColor('#0F172A')

            extras = []
            tags = [_txt(t) for t in (data.get('customTags') or []) if _txt(t)]
            if tags:
                extras.append(' | '.join(tags))
            ref = _txt(data.get('documentRef'))
            if ref:
                extras.append('Doc: ' + ref)

            cy = self._y(y + h / 2) + (4 if extras else 0)
            self._texto_centrado(c, label, x + w / 2, cy, w - 20, 9, cor_txt, max_linhas=3 if extras else 4)
            if extras:
                c.setFont(FONT, 6.5)
                c.setFillColor(colors.HexColor('#CBD5E1') if escuro else colors.HexColor('#64748B'))
                c.drawCentredString(x + w / 2, self._y(y + h) + 5, ' - '.join(extras)[:46])

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

        if e.get('sourceHandle') == 'right' or nao:
            pts = self._horizontal(sr, smy, tl, tmy)
        elif tt >= sb - 10:
            pts = self._vertical(smx, sb, tmx, tt)
        elif tb <= st + 10:
            lx = max(sr, tr) + 40
            pts = [(sr, smy), (lx, smy), (lx, tmy), (tr, tmy)]
        else:
            pts = self._horizontal(sr, smy, tl, tmy) if tl >= sr else self._horizontal(sl, smy, tr, tmy)

        c.setStrokeColor(colors.HexColor('#64748B'))
        c.setFillColor(colors.HexColor('#64748B'))
        c.setLineWidth(1.4)
        p = c.beginPath()
        p.moveTo(pts[0][0], self._y(pts[0][1]))
        for px, py in pts[1:]:
            p.lineTo(px, self._y(py))
        c.drawPath(p, stroke=1, fill=0)
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

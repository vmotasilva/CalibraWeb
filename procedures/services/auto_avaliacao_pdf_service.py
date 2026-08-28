# -*- coding: utf-8 -*-
"""
Serviço de Geração de Auto-Avaliação em PDF Oficial (FOR.141.r02)
Gera o PDF de 1 página A4 reproduzindo com 100% de fidelidade o layout do Excel oficial.
"""

import math
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.graphics.shapes import Drawing, Polygon, Line, String, Rect
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from procedures.models import PlanejamentoTreinamento, Colaborador


def _obter_perguntas_avaliacao(planejamento: PlanejamentoTreinamento, perguntas_selecionadas=None):
    """Obtém até 5 perguntas para o formulário."""
    if perguntas_selecionadas:
        from procedures.models import PerguntaAvaliacao
        ids_validos = []
        textos_diretos = []
        for item in perguntas_selecionadas:
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                ids_validos.append(int(item))
            elif isinstance(item, str) and item.strip():
                textos_diretos.append(item.strip())
        
        if ids_validos:
            qs = PerguntaAvaliacao.objects.filter(id__in=ids_validos)
            mapa = {p.id: p.texto for p in qs}
            res = [mapa[pid] for pid in ids_validos if pid in mapa]
            if res:
                return res[:5]
        if textos_diretos:
            return textos_diretos[:5]

    perguntas = []
    for proc in planejamento.procedimentos.all():
        for p in proc.perguntas.filter(ativo=True):
            if p.texto not in perguntas:
                perguntas.append(p.texto)
            if len(perguntas) == 5:
                break
        if len(perguntas) == 5:
            break

    perguntas_padrao = [
        "Qual o objetivo principal deste procedimento operacional e quais os impactos de eventuais não conformidades no processo?",
        "Quais os equipamentos de proteção individual (EPIs), ferramentas e requisitos de segurança obrigatórios para esta atividade?",
        "Descreva a sequência padrão de execução das etapas e os principais parâmetros operacionais a serem rigorosamente controlados.",
        "Quais são os pontos críticos de controle (PCC), tolerâncias permitidas e critérios de aceitação do produto/serviço?",
        "Em caso de desvio, defeito ou falha identificada durante a operação, qual é o fluxo correto de contenção e comunicação imediata?"
    ]

    while len(perguntas) < 5:
        perguntas.append(perguntas_padrao[len(perguntas)])

    return perguntas[:5]


def _criar_grafico_radar_pdf(perguntas, w_box=19.4 * cm, h_box=16.2 * cm):
    """
    Desenha o radar pentagonal com tamanho fixo imutável (radius=4.5cm), linhas azuis (#4472c4),
    escala central de 0 a 5 e as 5 perguntas nos vértices em posições fixas.
    """
    d = Drawing(w_box, h_box)
    
    cx = w_box / 2.0
    cy = h_box / 2.0 - 0.2 * cm
    radius = 4.5 * cm  # Raio do pentágono nível 5 (proporcional à folha A4)

    angulos = [-90, -18, 54, 126, 198]
    cor_azul_excel = colors.HexColor('#4472c4')
    cor_texto_excel = colors.HexColor('#595959')

    # 1. Desenhar os 5 pentágonos concêntricos (escala 1 a 5)
    for nivel in range(1, 6):
        r_nivel = radius * (nivel / 5.0)
        pontos = []
        for ang in angulos:
            rad = math.radians(ang)
            px = cx + r_nivel * math.cos(rad)
            py = cy - r_nivel * math.sin(rad)
            pontos.extend([px, py])

        d.add(Polygon(
            pontos,
            strokeColor=cor_azul_excel,
            strokeWidth=1.1 if nivel == 5 else 0.8,
            fillColor=None
        ))

    # 2. Linhas radiais do centro aos 5 vértices
    for ang in angulos:
        rad = math.radians(ang)
        px = cx + radius * math.cos(rad)
        py = cy - radius * math.sin(rad)
        d.add(Line(cx, cy, px, py, strokeColor=cor_azul_excel, strokeWidth=0.8))

    # 3. Números da escala central (0 a 5)
    for nivel in range(0, 6):
        r_nivel = radius * (nivel / 5.0)
        ny = cy + r_nivel - 2.5
        d.add(String(
            cx + 3, ny,
            str(nivel),
            fontName='Helvetica-Bold',
            fontSize=8.0,
            fillColor=cor_azul_excel
        ))

    # 4. Textos das 5 perguntas nos 5 vértices
    def wrap_text(texto, max_chars=40):
        palavras = texto.split()
        linhas = []
        linha_atual = []
        for p in palavras:
            if sum(len(x) for x in linha_atual) + len(linha_atual) + len(p) <= max_chars:
                linha_atual.append(p)
            else:
                if linha_atual:
                    linhas.append(" ".join(linha_atual))
                linha_atual = [p]
        if linha_atual:
            linhas.append(" ".join(linha_atual))
        return linhas

    # P1 (Topo - Vértice 0)
    p1_lines = wrap_text(perguntas[0], max_chars=55)
    base_y1 = cy + radius + 10 + (len(p1_lines) * 9.5)
    for idx, l in enumerate(p1_lines):
        d.add(String(cx, base_y1 - (idx * 9.5), l, fontName='Helvetica', fontSize=7.5, fillColor=cor_texto_excel, textAnchor='middle'))

    # P2 (Superior Direito - Vértice 1)
    p2_lines = wrap_text(perguntas[1], max_chars=36)
    px2 = cx + radius * math.cos(math.radians(-18)) + 12
    py2 = cy - radius * math.sin(math.radians(-18)) + 10
    for idx, l in enumerate(p2_lines):
        d.add(String(px2, py2 - (idx * 9.5), l, fontName='Helvetica', fontSize=7.5, fillColor=cor_texto_excel, textAnchor='start'))

    # P3 (Inferior Direito - Vértice 2)
    p3_lines = wrap_text(perguntas[2], max_chars=36)
    px3 = cx + radius * math.cos(math.radians(54)) + 10
    py3 = cy - radius * math.sin(math.radians(54)) - 10
    for idx, l in enumerate(p3_lines):
        d.add(String(px3, py3 - (idx * 9.5), l, fontName='Helvetica', fontSize=7.5, fillColor=cor_texto_excel, textAnchor='start'))

    # P4 (Inferior Esquerdo - Vértice 3)
    p4_lines = wrap_text(perguntas[3], max_chars=36)
    px4 = cx + radius * math.cos(math.radians(126)) - 10
    py4 = cy - radius * math.sin(math.radians(126)) - 10
    for idx, l in enumerate(p4_lines):
        d.add(String(px4, py4 - (idx * 9.5), l, fontName='Helvetica', fontSize=7.5, fillColor=cor_texto_excel, textAnchor='end'))

    # P5 (Superior Esquerdo - Vértice 4)
    p5_lines = wrap_text(perguntas[4], max_chars=36)
    px5 = cx + radius * math.cos(math.radians(198)) - 12
    py5 = cy - radius * math.sin(math.radians(198)) + 10
    for idx, l in enumerate(p5_lines):
        d.add(String(px5, py5 - (idx * 9.5), l, fontName='Helvetica', fontSize=7.5, fillColor=cor_texto_excel, textAnchor='end'))

    return d


def gerar_auto_avaliacao_pdf(planejamento: PlanejamentoTreinamento, colaborador_id=None, perguntas_selecionadas=None) -> BytesIO:
    """Gera o documento PDF oficial da Auto-Avaliação (FOR.141.r02) idêntico ao Excel."""
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.7 * cm,
        rightMargin=0.7 * cm,
        topMargin=0.6 * cm,
        bottomMargin=0.6 * cm
    )

    elements = []
    styles = getSampleStyleSheet()
    w_total = 19.6 * cm

    style_title = ParagraphStyle(
        'DocTitleExcel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#595959')
    )

    style_meta_label = ParagraphStyle(
        'MetaLabelExcel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#595959')
    )

    style_meta_val = ParagraphStyle(
        'MetaValExcel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#000000')
    )

    style_banner_title = ParagraphStyle(
        'BannerTitleExcel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#ffffff')
    )

    style_banner_sub = ParagraphStyle(
        'BannerSubExcel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#595959')
    )

    style_leg_title = ParagraphStyle(
        'LegTitleExcel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#595959')
    )

    style_leg_text = ParagraphStyle(
        'LegTextExcel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.0,
        leading=9.0,
        textColor=colors.HexColor('#000000')
    )

    style_escala_th = ParagraphStyle(
        'EscalaTh',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8.0,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#334155')
    )

    style_escala_td = ParagraphStyle(
        'EscalaTd',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.0,
        leading=7.5,
        textColor=colors.HexColor('#475569')
    )

    # Dados
    colab = None
    if colaborador_id:
        try:
            colab = Colaborador.objects.get(id=colaborador_id)
        except Exception:
            colab = None

    if not colab:
        colab = planejamento.colaboradores.first()

    colab_nome = colab.nome_completo if colab else ""
    colab_setor = colab.setor if colab and colab.setor else (getattr(colab, 'posto_trabalho', '') if colab else "")
    instrutor_nome = planejamento.instrutor.nome_completo if planejamento.instrutor else ""
    data_str = planejamento.data_prevista.strftime("%d/%m/%Y") if planejamento.data_prevista else ""

    procedimentos = list(planejamento.procedimentos.all())
    proc_str = " / ".join([f"{p.codigo} - {p.nome}" for p in procedimentos]) if procedimentos else (planejamento.titulo or "")

    perguntas = _obter_perguntas_avaliacao(planejamento, perguntas_selecionadas)

    # 1. Título Limpo Centralizado
    elements.append(Paragraph("<strong>FORMULÁRIO DE AUTO-AVALIAÇÃO</strong>", style_title))
    elements.append(Spacer(1, 0.15 * cm))

    # 2. Caixa de Metadados Unificada (Linhas 3 a 7 do Excel)
    meta_data = [
        [Paragraph("<strong>Nome:</strong>", style_meta_label), Paragraph(colab_nome, style_meta_val)],
        [Paragraph("<strong>Laboratório:</strong>", style_meta_label), Paragraph(colab_setor, style_meta_val)],
        [Paragraph("<strong>Treinamento:</strong>", style_meta_label), Paragraph(proc_str, style_meta_val)],
        [Paragraph("<strong>Data:</strong>", style_meta_label), Paragraph(data_str, style_meta_val)],
        [Paragraph("<strong>Instrutor:</strong>", style_meta_label), Paragraph(instrutor_nome, style_meta_val)],
    ]

    t_meta = Table(meta_data, colWidths=[2.6 * cm, 17.0 * cm])
    t_meta.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#bfbfbf')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 0.15 * cm))

    # 3. Faixa de Instrução
    t_banner = Table([[Paragraph("<strong>AUTO-AVALIAÇÃO (Como me avalio antes e depois desta sessão de treinamento?)</strong>", style_banner_title)]], colWidths=[w_total])
    t_banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#707070')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_banner)
    elements.append(Spacer(1, 0.08 * cm))

    sub_txt = "Para cada critério, marque ou faça um círculo em torno da opção que expresse a sua opinião<br/>(0 = nenhum; 3 = parcialmente; 5 = totalmente)"
    elements.append(Paragraph(sub_txt, style_banner_sub))
    elements.append(Spacer(1, 0.1 * cm))

    # 4. Gráfico Radar Pentagonal (Tamanho Proporcional à folha A4)
    elements.append(_criar_grafico_radar_pdf(perguntas, w_box=w_total, h_box=16.2 * cm))
    elements.append(Spacer(1, 0.15 * cm))

    # 5. Seção Inferior: Legenda à Esquerda e Tabela Escala à Direita
    leg_d1 = Drawing(26, 8)
    leg_d1.add(Rect(0, 0, 24, 7, fillColor=colors.HexColor('#c00000'), strokeColor=None))

    leg_d2 = Drawing(26, 8)
    leg_d2.add(Rect(0, 0, 24, 7, fillColor=colors.HexColor('#4472c4'), strokeColor=None))

    t_escala_data = [
        [Paragraph("<strong>Escala de Avaliação</strong>", style_escala_th), ""],
        [Paragraph("<strong>0</strong>", style_escala_th), Paragraph("Não conheço o tópico", style_escala_td)],
        [Paragraph("<strong>1</strong>", style_escala_th), Paragraph("Conheço, mas muito pouco", style_escala_td)],
        [Paragraph("<strong>2</strong>", style_escala_th), Paragraph("Faço com dificuldade", style_escala_td)],
        [Paragraph("<strong>3</strong>", style_escala_th), Paragraph("Sei fazer bem", style_escala_td)],
        [Paragraph("<strong>4</strong>", style_escala_th), Paragraph("Faço muito bem", style_escala_td)],
        [Paragraph("<strong>5</strong>", style_escala_th), Paragraph("Domino este Tópico", style_escala_td)],
    ]
    t_escala = Table(t_escala_data, colWidths=[0.6 * cm, 4.2 * cm])
    t_escala.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#bfbfbf')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#bfbfbf')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))

    t_leg_left_data = [
        [Paragraph("<strong>Legenda:</strong>", style_leg_title), leg_d1, Paragraph("Marque de <strong>vermelho</strong> para sua auto avaliação <strong>Antes</strong> do Treinamento", style_leg_text)],
        ["", leg_d2, Paragraph("Marque de <strong>Azul</strong> para sua auto avaliação <strong>Após</strong> do Treinamento", style_leg_text)],
    ]
    t_leg_left = Table(t_leg_left_data, colWidths=[1.8 * cm, 1.0 * cm, 11.2 * cm])
    t_leg_left.setStyle(TableStyle([
        ('SPAN', (0, 0), (0, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))

    t_bottom = Table([[t_leg_left, t_escala]], colWidths=[14.4 * cm, 5.2 * cm])
    t_bottom.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_bottom)

    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# -*- coding: utf-8 -*-
"""
Serviço de Geração de PDF para Auto-Avaliação de Treinamento Crítico (FOR.141.r02)
Reproduz 100% a fidelidade visual, proporções e disposição do template oficial FOR.141.r02:
1. Cabeçalho oficial "FORMULÁRIO DE AUTO-AVALIAÇÃO"
2. Metadados: Nome, Laboratório, Treinamento, Data, Instrutor
3. Faixa: "AUTO-AVALIAÇÃO (Como me avalio antes e depois desta sessão de treinamento?)"
4. Grande Gráfico Radar Pentagonal com 5 eixos (0 a 5) e as 5 Caixas de Perguntas nos 5 vértices
5. Legenda oficial (Vermelho = Antes / Azul = Após)
"""

import math
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing, Polygon, Line, Circle, String, Rect

from django.utils import timezone
from procedures.models import PlanejamentoTreinamento
from procedures.services.treinamento_excel_export_service import (
    _extrair_dados_colaborador_avaliado,
    _obter_perguntas_treinamento
)


def gerar_auto_avaliacao_pdf(planejamento: PlanejamentoTreinamento, colaborador_id: int = None, perguntas_selecionadas: list = None) -> BytesIO:
    """
    Gera o documento PDF oficial da Auto-Avaliação de Treinamento Crítico (FOR.141.r02)
    reproduzindo exatamente o layout e as formas do template Excel original em 1 página A4.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm
    )

    elements = []
    styles = getSampleStyleSheet()
    w_total = 18.6 * cm

    # 1. Resolução dos Dados
    colaborador = None
    if hasattr(planejamento, 'colaboradores'):
        if colaborador_id:
            colaborador = planejamento.colaboradores.select_related('setor', 'lider', 'supervisor', 'gerente').filter(id=colaborador_id).first()
        if not colaborador and planejamento.colaboradores.exists():
            colaborador = planejamento.colaboradores.select_related('setor', 'lider', 'supervisor', 'gerente').first()

    d_colab = _extrair_dados_colaborador_avaliado(colaborador)
    perguntas = _obter_perguntas_treinamento(planejamento, perguntas_selecionadas=perguntas_selecionadas)

    if hasattr(planejamento, '_mock_procs') and planejamento._mock_procs:
        procs = list(planejamento._mock_procs)
    elif hasattr(planejamento, 'procedimentos'):
        procs = list(planejamento.procedimentos.all())
    else:
        procs = []

    proc_str = ", ".join([f"{p.codigo} - {p.nome}" for p in procs]) if procs else (planejamento.titulo or "")
    instrutor_nome = (planejamento.instrutor.nome_completo if getattr(planejamento, 'instrutor', None) else "")
    data_str = planejamento.data_prevista.strftime("%d/%m/%Y") if getattr(planejamento, 'data_prevista', None) else timezone.now().strftime("%d/%m/%Y")
    laboratorio_str = d_colab.get('setor', '') or d_colab.get('posto_trabalho', '')

    # 2. Estilos Tipográficos
    style_header_title = ParagraphStyle('HeaderTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=TA_CENTER, textColor=colors.HexColor('#000000'))
    style_meta_label = ParagraphStyle('MetaLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#000000'))
    style_meta_val = ParagraphStyle('MetaVal', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor('#000000'))
    style_section_title = ParagraphStyle('SecTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#000000'))
    style_section_sub = ParagraphStyle('SecSub', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#1E293B'))

    # 3. TÍTULO DO FORMULÁRIO
    title_data = [[Paragraph("FORMULÁRIO DE AUTO-AVALIAÇÃO", style_header_title)]]
    t_title = Table(title_data, colWidths=[w_total])
    t_title.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#000000')), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC'))]))
    elements.append(t_title)
    elements.append(Spacer(1, 4))

    # 4. METADADOS
    meta_rows = [
        [Paragraph("Nome:", style_meta_label), Paragraph(d_colab.get('nome', ''), style_meta_val), Paragraph("Data:", style_meta_label), Paragraph(data_str, style_meta_val)],
        [Paragraph("Laboratório:", style_meta_label), Paragraph(laboratorio_str, style_meta_val), Paragraph("Instrutor:", style_meta_label), Paragraph(instrutor_nome, style_meta_val)],
        [Paragraph("Treinamento:", style_meta_label), Paragraph(proc_str, style_meta_val), Paragraph("", style_meta_label), Paragraph("", style_meta_val)],
    ]
    t_meta = Table(meta_rows, colWidths=[2.6 * cm, 8.8 * cm, 2.2 * cm, 5.0 * cm])
    t_meta.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5), ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#000000')), ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')), ('SPAN', (1, 2), (3, 2))]))
    elements.append(t_meta)
    elements.append(Spacer(1, 8))

    # 5. FAIXA
    banner_rows = [
        [Paragraph("AUTO-AVALIAÇÃO (Como me avalio antes e depois desta sessão de treinamento?)", style_section_title)],
        [Paragraph("Para cada critério, marque ou faça um círculo em torno da opção que expresse a sua opinião<br/>(0 = nenhum; 3 = parcialmente; 5 = totalmente)", style_section_sub)],
    ]
    t_banner = Table(banner_rows, colWidths=[w_total])
    t_banner.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#000000')), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9'))]))
    elements.append(t_banner)
    elements.append(Spacer(1, 10))

    # 6. RADAR
    drawing_h = 360
    d_radar = Drawing(w_total, drawing_h)
    cx = w_total / 2.0
    cy = 180.0
    raio_max = 90.0
    angulos = [math.pi / 2.0, math.pi / 2.0 - 1 * (2 * math.pi / 5.0), math.pi / 2.0 - 2 * (2 * math.pi / 5.0), math.pi / 2.0 - 3 * (2 * math.pi / 5.0), math.pi / 2.0 - 4 * (2 * math.pi / 5.0)]

    for nivel in range(1, 6):
        r_nivel = raio_max * (nivel / 5.0)
        pontos = []
        for ang in angulos:
            px = cx + r_nivel * math.cos(ang)
            py = cy + r_nivel * math.sin(ang)
            pontos.extend([px, py])
        d_radar.add(Polygon(pontos, strokeColor=colors.HexColor('#000000') if nivel == 5 else colors.HexColor('#94A3B8'), fillColor=colors.HexColor('#FAFAFA') if nivel == 5 else colors.transparent, strokeWidth=1.0 if nivel == 5 else 0.6))

    for ang in angulos:
        px = cx + raio_max * math.cos(ang)
        py = cy + raio_max * math.sin(ang)
        d_radar.add(Line(cx, cy, px, py, strokeColor=colors.HexColor('#475569'), strokeWidth=0.8))
        d_radar.add(Circle(px, py, 2.5, fillColor=colors.HexColor('#000000'), strokeColor=colors.HexColor('#000000'), strokeWidth=0.5))

    d_radar.add(String(cx + 3, cy - 3, "0", fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#334155')))
    for nivel in range(1, 6):
        r_nivel = raio_max * (nivel / 5.0)
        py_num = cy + r_nivel * math.sin(angulos[0])
        d_radar.add(String(cx + 3, py_num - 3, str(nivel), fontName="Helvetica-Bold", fontSize=7.5, fillColor=colors.HexColor('#000000')))

    # 7. CAIXAS PERGUNTAS
    def quebrar_texto_linhas(txt, max_chars=42):
        palavras = txt.split(); linhas = []; linha_atual = []; len_atual = 0
        for p in palavras:
            if len_atual + len(p) + 1 > max_chars:
                linhas.append(" ".join(linha_atual)); linha_atual = [p]; len_atual = len(p)
            else: linha_atual.append(p); len_atual += len(p) + 1
        if linha_atual: linhas.append(" ".join(linha_atual))
        return linhas[:4]

    caixas_configs = [
        {'idx': 0, 'box_w': 180, 'box_h': 42, 'bx': cx - 90, 'by': cy + raio_max + 8, 'align': 'center'},
        {'idx': 1, 'box_w': 145, 'box_h': 44, 'bx': cx + raio_max * math.cos(angulos[1]) + 8, 'by': cy + raio_max * math.sin(angulos[1]) - 14, 'align': 'left'},
        {'idx': 2, 'box_w': 145, 'box_h': 44, 'bx': cx + raio_max * math.cos(angulos[2]) + 4, 'by': cy + raio_max * math.sin(angulos[2]) - 32, 'align': 'left'},
        {'idx': 3, 'box_w': 145, 'box_h': 44, 'bx': cx + raio_max * math.cos(angulos[3]) - 149, 'by': cy + raio_max * math.sin(angulos[3]) - 32, 'align': 'right'},
        {'idx': 4, 'box_w': 145, 'box_h': 44, 'bx': cx + raio_max * math.cos(angulos[4]) - 153, 'by': cy + raio_max * math.sin(angulos[4]) - 14, 'align': 'right'},
    ]

    for cfg in caixas_configs:
        q_idx = cfg['idx']; txt_q = perguntas[q_idx] if q_idx < len(perguntas) and perguntas[q_idx] else f"Critério operacional e controle técnico {q_idx+1}."
        linhas = quebrar_texto_linhas(txt_q, max_chars=34 if cfg['box_w'] < 160 else 46)
        bx, by, bw, bh = cfg['bx'], cfg['by'], cfg['box_w'], max(36, len(linhas) * 9 + 12)
        d_radar.add(Rect(bx, by, bw, bh, fillColor=colors.HexColor('#FFFFFF'), strokeColor=colors.HexColor('#000000'), strokeWidth=0.8))
        y_start = by + bh - 10
        for i_lin, lin in enumerate(linhas):
            lin_y = y_start - (i_lin * 8.5)
            tx = bx + (bw / 2.0) if cfg['align'] == 'center' else bx + 5
            d_radar.add(String(tx, lin_y, lin, fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor('#000000'), textAnchor='middle' if cfg['align'] == 'center' else 'start'))

    elements.append(d_radar)
    elements.append(Spacer(1, 10))

    # 8. LEGENDA
    legenda_rows = [
        [Paragraph("<b>Legenda:</b>", style_meta_label), Paragraph("<font color='#DC2626'>■</font> Marque de <b>vermelho</b> para sua auto avaliação <b>Antes</b> do Treinamento", style_meta_val)],
        [Paragraph("", style_meta_label), Paragraph("<font color='#2563EB'>■</font> Marque de <b>Azul</b> para sua auto avaliação <b>Após</b> do Treinamento", style_meta_val)],
    ]
    t_legenda = Table(legenda_rows, colWidths=[2.2 * cm, 16.4 * cm])
    t_legenda.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#000000')), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC'))]))
    elements.append(t_legenda)

    doc.build(elements)
    buffer.seek(0)
    return buffer

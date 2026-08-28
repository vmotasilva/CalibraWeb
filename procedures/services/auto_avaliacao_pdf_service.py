# -*- coding: utf-8 -*-
"""
Serviço de Geração de Auto-Avaliação em PDF Oficial (FOR.141.r02)
Gera o formulário em alta fidelidade com ReportLab em 1 página A4,
incluindo gráfico radar pentagonal (5 eixos), perguntas técnicas e bloco de assinaturas.
"""

import math
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Polygon, Line, Circle, String, Rect

from django.utils import timezone
from procedures.models import PlanejamentoTreinamento
from procedures.services.treinamento_excel_export_service import (
    _extrair_dados_colaborador_avaliado,
    _obter_perguntas_treinamento
)


def gerar_auto_avaliacao_pdf(planejamento: PlanejamentoTreinamento, colaborador_id: int = None) -> BytesIO:
    """
    Gera o documento PDF oficial da Auto-Avaliação de Treinamento Crítico (FOR.141.r02)
    perfeitamente diagramado para 1 página A4 com Gráfico Radar Pentagonal.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm
    )

    elements = []
    styles = getSampleStyleSheet()
    w_total = 19.4 * cm

    # 1. Resolução de Dados
    colaborador = None
    if hasattr(planejamento, 'colaboradores'):
        if colaborador_id:
            colaborador = planejamento.colaboradores.select_related('setor', 'lider', 'supervisor', 'gerente').filter(id=colaborador_id).first()
        if not colaborador and planejamento.colaboradores.exists():
            colaborador = planejamento.colaboradores.select_related('setor', 'lider', 'supervisor', 'gerente').first()

    d_colab = _extrair_dados_colaborador_avaliado(colaborador)
    perguntas = _obter_perguntas_treinamento(planejamento)

    if hasattr(planejamento, '_mock_procs') and planejamento._mock_procs:
        procs = list(planejamento._mock_procs)
    elif hasattr(planejamento, 'procedimentos'):
        procs = list(planejamento.procedimentos.all())
    else:
        procs = []

    proc_str = ", ".join([f"{p.codigo} - {p.nome}" for p in procs]) if procs else (planejamento.titulo or "-")
    instrutor_nome = (planejamento.instrutor.nome_completo if getattr(planejamento, 'instrutor', None) else "-")
    data_str = planejamento.data_prevista.strftime("%d/%m/%Y") if getattr(planejamento, 'data_prevista', None) else timezone.now().strftime("%d/%m/%Y")
    carga_horaria_str = f"{planejamento.carga_horaria} Minutos" if getattr(planejamento, 'carga_horaria', None) else "-"

    # 2. Estilos Tipográficos
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#FFFFFF')
    )

    style_sec_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#FFFFFF')
    )

    style_instr = ParagraphStyle(
        'Instr',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#334155')
    )

    style_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor('#0F172A')
    )

    style_val = ParagraphStyle(
        'Val',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=8.5,
        textColor=colors.HexColor('#1E293B')
    )

    style_q_num = ParagraphStyle(
        'QNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1E3A8A')
    )

    style_q_txt = ParagraphStyle(
        'QTxt',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.8,
        leading=8.2,
        textColor=colors.HexColor('#0F172A')
    )

    # 3. Cabeçalho Principal (FOR.141.r02)
    header_data = [[
        Paragraph("FOR.141.r02 - AUTO-AVALIAÇÃO DE TREINAMENTO CRÍTICO", style_title)
    ]]
    t_header = Table(header_data, colWidths=[w_total])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0F172A')),
    ]))
    elements.append(t_header)

    # 4. Dados do Colaborador, Gestor e Treinamento
    dados_meta = [
        [
            Paragraph(f"<b>Colaborador:</b> {d_colab['nome']}", style_val),
            Paragraph(f"<b>Matrícula:</b> {d_colab['matricula']}", style_val),
            Paragraph(f"<b>Setor:</b> {d_colab['setor']}", style_val),
        ],
        [
            Paragraph(f"<b>Cargo:</b> {d_colab['cargo']}", style_val),
            Paragraph(f"<b>Gestor / Chefia:</b> {d_colab['gestor']}", style_val),
            Paragraph(f"<b>Data da Sessão:</b> {data_str}", style_val),
        ],
        [
            Paragraph(f"<b>Procedimento:</b> {proc_str}", style_val),
            Paragraph(f"<b>Instrutor:</b> {instrutor_nome}", style_val),
            Paragraph(f"<b>Carga Horária:</b> {carga_horaria_str}", style_val),
        ]
    ]
    t_meta = Table(dados_meta, colWidths=[8.0 * cm, 6.5 * cm, 4.9 * cm])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 3))

    # 5. Faixa de Instrução
    banner_data = [
        [Paragraph("AUTO-AVALIAÇÃO (Como me avalio antes e depois desta sessão de treinamento?)", style_sec_title)],
        [Paragraph("Para cada critério, marque de 0 a 5: (0 = Nenhum conhecimento; 3 = Parcialmente dominado; 5 = Totalmente dominado).", style_instr)]
    ]
    t_banner = Table(banner_data, colWidths=[w_total])
    t_banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#334155')),
    ]))
    elements.append(t_banner)
    elements.append(Spacer(1, 2))

    # 6. Gráfico Radar Pentagonal (5 eixos, escala 0 a 5)
    d_radar = Drawing(w_total, 160)
    cx = w_total / 2.0
    cy = 82.0
    raio_max = 54.0
    angulos = [math.pi/2 - i * (2 * math.pi / 5) for i in range(5)]

    # Pentágonos concêntricos (1 a 5)
    for nivel in range(1, 6):
        r_nivel = raio_max * (nivel / 5.0)
        pontos = []
        for ang in angulos:
            px = cx + r_nivel * math.cos(ang)
            py = cy + r_nivel * math.sin(ang)
            pontos.extend([px, py])
        
        fill_color = colors.HexColor('#F8FAFC') if nivel == 5 else colors.transparent
        stroke_color = colors.HexColor('#0F172A') if nivel == 5 else colors.HexColor('#94A3B8')
        stroke_width = 1.0 if nivel == 5 else 0.5
        d_radar.add(Polygon(pontos, strokeColor=stroke_color, fillColor=fill_color, strokeWidth=stroke_width))

    # Eixos radiais
    for i, ang in enumerate(angulos):
        px = cx + raio_max * math.cos(ang)
        py = cy + raio_max * math.sin(ang)
        d_radar.add(Line(cx, cy, px, py, strokeColor=colors.HexColor('#475569'), strokeWidth=0.8))
        d_radar.add(Circle(px, py, 2.5, fillColor=colors.HexColor('#1E3A8A'), strokeColor=colors.HexColor('#0F172A'), strokeWidth=0.8))

    # Escala 0 a 5 no eixo vertical
    d_radar.add(String(cx + 3, cy - 2, "0", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor('#334155')))
    for nivel in range(1, 6):
        r_nivel = raio_max * (nivel / 5.0)
        py_num = cy + r_nivel * math.sin(angulos[0])
        d_radar.add(String(cx + 3, py_num - 2, str(nivel), fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor('#1E3A8A')))

    # Rótulos dos Vértices (Q1 a Q5)
    rotulos_pos = [
        (cx - 20, cy + raio_max + 4, "Questão 1 (Objetivo / Impactos)"),
        (cx + raio_max + 6, cy + 8, "Questão 2 (EPIs / Segurança)"),
        (cx + raio_max - 15, cy - raio_max - 2, "Questão 3 (Execução / Parâmetros)"),
        (cx - raio_max - 110, cy - raio_max - 2, "Questão 4 (Desvios / Ações Imediatas)"),
        (cx - raio_max - 110, cy + 8, "Questão 5 (Registros / Rastreabilidade)"),
    ]
    for rx, ry, rtxt in rotulos_pos:
        d_radar.add(String(rx, ry, rtxt, fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#1E3A8A')))

    # Legenda de cores inferior
    d_radar.add(Rect(cx - 150, 2, 10, 5, fillColor=colors.HexColor('#DC2626'), strokeColor=colors.HexColor('#991B1B'), strokeWidth=0.5))
    d_radar.add(String(cx - 136, 2, "Vermelho: Autoavaliação ANTES do Treinamento", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#1E293B')))

    d_radar.add(Rect(cx + 20, 2, 10, 5, fillColor=colors.HexColor('#2563EB'), strokeColor=colors.HexColor('#1D4ED8'), strokeWidth=0.5))
    d_radar.add(String(cx + 34, 2, "Azul: Autoavaliação APÓS o Treinamento", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor('#1E293B')))

    elements.append(d_radar)
    elements.append(Spacer(1, 2))

    # 7. Tabela das 5 Perguntas e Espaço de Avaliação
    tabela_perguntas_data = [[
        Paragraph("<b>Nº</b>", style_q_num),
        Paragraph("<b>Questão Técnica / Critério Avaliado</b>", style_label),
        Paragraph("<b>Nota Antes<br/>(0 a 5)</b>", style_q_num),
        Paragraph("<b>Nota Depois<br/>(0 a 5)</b>", style_q_num),
        Paragraph("<b>Evidências / Parecer do Colaborador</b>", style_label)
    ]]

    for idx in range(5):
        p_txt = perguntas[idx] if idx < len(perguntas) and perguntas[idx] else f"Pergunta técnica {idx+1} sobre os parâmetros do procedimento operacional."
        tabela_perguntas_data.append([
            Paragraph(f"<b>Q{idx+1}</b>", style_q_num),
            Paragraph(p_txt, style_q_txt),
            Paragraph("[   ]", style_q_num),
            Paragraph("[   ]", style_q_num),
            Paragraph("________________________________________________", style_instr)
        ])

    t_perguntas = Table(
        tabela_perguntas_data,
        colWidths=[1.0 * cm, 10.4 * cm, 2.0 * cm, 2.0 * cm, 4.0 * cm]
    )
    t_perguntas.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_perguntas)
    elements.append(Spacer(1, 8))

    # 8. Bloco de Assinaturas
    ass_data = [
        [
            Paragraph(f"________________________________________________<br/><b>Assinatura do Colaborador:</b> {d_colab['nome']}", ParagraphStyle('Ass1', parent=styles['Normal'], alignment=TA_CENTER, fontSize=7, leading=9)),
            Paragraph(f"________________________________________________<br/><b>Assinatura do Instrutor:</b> {instrutor_nome}", ParagraphStyle('Ass2', parent=styles['Normal'], alignment=TA_CENTER, fontSize=7, leading=9))
        ]
    ]
    t_ass = Table(ass_data, colWidths=[9.7 * cm, 9.7 * cm])
    t_ass.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(t_ass)

    doc.build(elements)
    buffer.seek(0)
    return buffer

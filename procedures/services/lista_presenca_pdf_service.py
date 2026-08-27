# -*- coding: utf-8 -*-
"""
Serviço de Geração de Lista de Presença em PDF Oficial (FOR.033)
Gera um documento PDF em padrão A4 de alta fidelidade com ReportLab.
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from procedures.models import PlanejamentoTreinamento
from procedures.services.lista_presenca_excel_service import _obter_mapeamento_checkboxes


def gerar_lista_presenca_pdf(planejamento: PlanejamentoTreinamento, overrides: dict = None) -> BytesIO:
    """Gera o documento PDF oficial da Lista de Presença (FOR.033) ajustado para 1 página A4."""
    buffer = BytesIO()
    
    # Configuração do documento A4 com margens ajustadas de 0.7cm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.7 * cm,
        rightMargin=0.7 * cm,
        topMargin=0.7 * cm,
        bottomMargin=0.7 * cm
    )

    elements = []
    styles = getSampleStyleSheet()

    # Largura útil da página A4 (21.0cm - 1.4cm = 19.6cm)
    w_total = 19.6 * cm

    # Estilos de Texto
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#000000')
    )

    style_header_label = ParagraphStyle(
        'HeaderLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#000000')
    )

    style_header_val = ParagraphStyle(
        'HeaderVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#000000')
    )

    style_th = ParagraphStyle(
        'TableTh',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#000000')
    )

    style_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#000000')
    )

    # 1. Obter marcações de checkboxes
    checkbox_map = _obter_mapeamento_checkboxes(planejamento, overrides=overrides)

    # 2. Dados do cabeçalho
    if planejamento.horario_previsto:
        data_hora_str = planejamento.horario_previsto.strftime("%d/%m/%Y às %H:%M")
    elif planejamento.data_prevista and hasattr(planejamento, 'horario_inicio') and planejamento.horario_inicio:
        data_hora_str = f"{planejamento.data_prevista.strftime('%d/%m/%Y')} às {planejamento.horario_inicio.strftime('%H:%M')}"
    elif planejamento.data_prevista:
        data_hora_str = planejamento.data_prevista.strftime("%d/%m/%Y")
    else:
        data_hora_str = "-"

    carga_horaria_str = f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else "-"
    instrutor_nome = planejamento.instrutor.nome_completo if planejamento.instrutor else "-"

    # Textos formatados de checkboxes
    cat_str = f"{checkbox_map.get('{{CHK_TREIN}}', '○')} Treinamento &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_REUN}}', '○')} Reunião &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_RECIC}}', '○')} Reciclagem"
    met_str = f"{checkbox_map.get('{{CHK_TRAD}}', '○')} Tradicional &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_LOFT}}', '○')} LOFT"
    
    outros_txt = overrides.get('outros_texto', '') if overrides else ''
    outros_label = f"Outros: {outros_txt}" if outros_txt else "Outros: ____________"
    area_str = (
        f"{checkbox_map.get('{{CHK_ADM}}', '○')} Administrativo &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_QUALIDADE}}', '○')} Qualidade &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_EHS}}', '○')} EHS &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_ESTOQUE}}', '○')} Estoque &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_PRODUCAO}}', '○')} Produção &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_OUTROS}}', '○')} {outros_label}"
    )

    aval_str = f"{checkbox_map.get('{{CHK_AVAL_SIM}}', '○')} Sim &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_AVAL_NAO}}', '○')} Não"

    # Tabela de Cabeçalho / Metadados do Treinamento
    header_data = [
        # Linha 1: Título Principal
        [Paragraph("<strong>LISTA DE PRESENÇA DE TREINAMENTO</strong>", style_title), ""],
        # Linha 2: Título do Treinamento
        [Paragraph("<strong>Título do treinamento:</strong>", style_header_label), Paragraph(f"<strong>{planejamento.titulo or '-'}</strong>", style_header_val)],
        # Linha 3: Categoria e Metodologia
        [Paragraph("<strong>Categoria do Treinamento:</strong>", style_header_label), Paragraph(f"{cat_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong>Metodologia:</strong> &nbsp;&nbsp; {met_str}", style_header_val)],
        # Linha 4: Área de Conhecimento
        [Paragraph("<strong>Área de Conhecimento:</strong>", style_header_label), Paragraph(area_str, style_header_val)],
        # Linha 5: Necessita de Avaliação
        [Paragraph("<strong>Necessita de Avaliação:</strong>", style_header_label), Paragraph(aval_str, style_header_val)],
        # Linha 6: Facilitador
        [Paragraph("<strong>Nome do Facilitador:</strong>", style_header_label), Paragraph(instrutor_nome, style_header_val)],
        # Linha 7: Data e Carga Horária
        [Paragraph("<strong>Data e hora:</strong>", style_header_label), Paragraph(f"{data_hora_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong>Carga horária:</strong> {carga_horaria_str}", style_header_val)],
    ]

    t_header = Table(header_data, colWidths=[4.2 * cm, 15.4 * cm])
    t_header.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 0.15 * cm))

    # 3. Tabela de Participantes (Linhas em branco prontas para assinatura)
    table_part_data = [
        [
            Paragraph("<strong>NOME DO COLABORADOR</strong>", style_th),
            Paragraph("<strong>CPF / MATRÍCULA</strong>", style_th),
            Paragraph("<strong>CARGO</strong>", style_th),
            Paragraph("<strong>DEPARTAMENTO</strong>", style_th),
            Paragraph("<strong>ASSINATURA</strong>", style_th),
        ]
    ]

    # Gerar 15 linhas limpas com altura compacta e ideal para preenchimento
    for _ in range(15):
        table_part_data.append(["", "", "", "", ""])

    col_widths_part = [6.0 * cm, 3.4 * cm, 3.4 * cm, 3.4 * cm, 3.4 * cm]
    t_part = Table(table_part_data, colWidths=col_widths_part, rowHeights=[16] + [18] * 15)
    t_part.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    elements.append(t_part)
    elements.append(Spacer(1, 0.15 * cm))

    # 4. Bloco Conteúdo do Treinamento (Procedimentos)
    procedimentos = list(planejamento.procedimentos.all())
    procs_data = [
        [Paragraph("<strong>CONTEÚDO DO TREINAMENTO / PROCEDIMENTOS ABORDADOS</strong>", style_th)]
    ]

    if procedimentos:
        for p in procedimentos:
            texto = f"• <strong>{p.codigo or ''}</strong> - {p.nome or ''}"
            procs_data.append([Paragraph(texto, style_cell)])
    else:
        procs_data.append([Paragraph("• Conteúdo programático e instruções gerais de treinamento.", style_cell)])

    t_procs = Table(procs_data, colWidths=[w_total])
    t_procs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_procs)

    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


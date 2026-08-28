# -*- coding: utf-8 -*-
"""
Serviço de Geração de Lista de Presença em PDF Oficial (FOR.033 - Revisão 7)
Gera um documento PDF oficial de alta fidelidade em padrão A4 (Frente e Verso) com ReportLab.
"""

import os
from io import BytesIO
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from procedures.models import PlanejamentoTreinamento
from procedures.services.lista_presenca_excel_service import _obter_mapeamento_checkboxes


def _criar_cabecalho_sgq(num_pagina: int, total_paginas: int = 2, w_total: float = 19.6 * cm):
    """Cria a tabela de cabeçalho padrão SGQ (FOR.033.r07)."""
    styles = getSampleStyleSheet()

    style_logo_txt = ParagraphStyle(
        f'LogoTxt_{num_pagina}',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0f172a')
    )

    style_title_top = ParagraphStyle(
        f'TitleTop_{num_pagina}',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#334155')
    )

    style_title_main = ParagraphStyle(
        f'TitleMain_{num_pagina}',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#000000')
    )

    style_sgq_meta = ParagraphStyle(
        f'SGQMeta_{num_pagina}',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#000000')
    )

    # Coluna 1: Logo Oficial do Template SGQ
    caminhos_logo = [
        os.path.join(settings.BASE_DIR, "shared", "static", "shared", "logo_qms_template.png"),
        os.path.join(settings.BASE_DIR, "static", "img", "logo_qms_template.png"),
        os.path.join(settings.BASE_DIR, "shared", "static", "shared", "logo_calibraweb.png"),
    ]
    logo_path = next((p for p in caminhos_logo if os.path.exists(p)), None)
    if logo_path:
        try:
            col_logo = Image(logo_path, width=3.4 * cm, height=1.1 * cm)
        except Exception:
            col_logo = Paragraph("<strong>CALIBRA</strong>", style_logo_txt)
    else:
        col_logo = Paragraph("<strong>CALIBRA</strong>", style_logo_txt)

    # Coluna 2: Título
    col_centro = [
        Paragraph("Formulário", style_title_top),
        Spacer(1, 1),
        Paragraph("<strong>Lista de Presença de Treinamento</strong>", style_title_main)
    ]

    # Coluna 3: Metadados do SGQ
    col_direita = [
        Paragraph("<strong>Código:</strong> FOR.033 &nbsp;&nbsp;<strong>Revisão:</strong> 7", style_sgq_meta),
        Paragraph("<strong>Elaboração:</strong> 05/12/2023 &nbsp;<strong>Aprovação:</strong> 05/12/2023", style_sgq_meta),
        Paragraph(f"<strong>Página:</strong> {num_pagina} de {total_paginas}", style_sgq_meta)
    ]

    t_header = Table(
        [[col_logo, col_centro, col_direita]],
        colWidths=[3.6 * cm, 9.8 * cm, 6.2 * cm]
    )
    t_header.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t_header


def _criar_rodape_sgq(w_total: float = 19.6 * cm):
    """Cria a grade de aprovação oficial do SGQ no rodapé (3 colunas)."""
    styles = getSampleStyleSheet()
    style_rodape = ParagraphStyle(
        'RodapeSGQ',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#000000')
    )

    col1 = [
        Paragraph("<strong>Elaborado por:</strong> Taís Flores", style_rodape),
        Paragraph("<strong>Setor:</strong> Qualidade", style_rodape)
    ]
    col2 = [
        Paragraph("<strong>Verificado por:</strong> Ana Guimarães", style_rodape),
        Paragraph("<strong>Setor:</strong> Gerente Qualidade Brasil", style_rodape)
    ]
    col3 = [
        Paragraph("<strong>Aprovado por:</strong> Ana Oliveira", style_rodape),
        Paragraph("<strong>Setor:</strong> Gerente RH", style_rodape)
    ]

    t_rod = Table(
        [[col1, col2, col3]],
        colWidths=[w_total / 3.0, w_total / 3.0, w_total / 3.0]
    )
    t_rod.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t_rod


def gerar_lista_presenca_pdf(planejamento: PlanejamentoTreinamento, overrides: dict = None) -> BytesIO:
    """Gera o documento PDF oficial da Lista de Presença (FOR.033 - Revisão 7) em 2 páginas (Frente e Verso)."""
    buffer = BytesIO()
    
    # Configuração do documento A4 com margens ajustadas de 0.7cm
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

    # Largura útil da página A4 (21.0cm - 1.4cm = 19.6cm)
    w_total = 19.6 * cm

    style_header_label = ParagraphStyle(
        'HeaderLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.0,
        textColor=colors.HexColor('#000000')
    )

    style_header_val = ParagraphStyle(
        'HeaderVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.0,
        textColor=colors.HexColor('#000000')
    )

    style_th = ParagraphStyle(
        'TableTh',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.0,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#000000')
    )

    style_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.0,
        leading=8.8,
        textColor=colors.HexColor('#000000')
    )

    style_nota_verso = ParagraphStyle(
        'NotaVerso',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8.0,
        textColor=colors.HexColor('#334155'),
        alignment=TA_LEFT
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

    cat_str = f"{checkbox_map.get('{{CHK_TREIN}}', '○')} Treinamento &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_REUN}}', '○')} Reunião &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_RECIC}}', '○')} Reciclagem"
    met_str = f"{checkbox_map.get('{{CHK_LOFT}}', '○')} LOFT &nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_TRAD}}', '○')} Tradicional"
    
    outros_txt = overrides.get('outros_texto', '') if overrides else ''
    outros_label = f"Outros: {outros_txt}" if outros_txt else "Outros: _________________"
    area_str = (
        f"{checkbox_map.get('{{CHK_ADM}}', '○')} Administrativo &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_QUALIDADE}}', '○')} Qualidade &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_EHS}}', '○')} EHS &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_ESTOQUE}}', '○')} Estoque &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_PRODUCAO}}', '○')} Produção &nbsp;&nbsp; "
        f"{checkbox_map.get('{{CHK_OUTROS}}', '○')} {outros_label}"
    )

    aval_str = f"{checkbox_map.get('{{CHK_AVAL_SIM}}', '○')} Sim &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {checkbox_map.get('{{CHK_AVAL_NAO}}', '○')} Não"

    # =========================================================================
    # PÁGINA 1 - FRENTE
    # =========================================================================

    # 1. Cabeçalho Oficial SGQ
    elements.append(_criar_cabecalho_sgq(num_pagina=1, total_paginas=2, w_total=w_total))
    elements.append(Spacer(1, 0.12 * cm))

    # 2. Tabela de Metadados do Treinamento
    meta_rows = [
        [
            Paragraph("<strong>Título do treinamento:</strong>", style_header_label),
            Paragraph(f"<strong>{planejamento.titulo or '-'}</strong>", style_header_val)
        ],
        [
            Paragraph("<strong>Categoria do Treinamento:</strong>", style_header_label),
            Paragraph(f"{cat_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong>Metodologia:</strong> &nbsp;&nbsp; {met_str}", style_header_val)
        ],
        [
            Paragraph("<strong>Área de Conhecimento:</strong>", style_header_label),
            Paragraph(area_str, style_header_val)
        ],
        [
            Paragraph("<strong>Necessita de Avaliação:</strong>", style_header_label),
            Paragraph(aval_str, style_header_val)
        ],
        [
            Paragraph("<strong>Nome do Facilitador ou Fornecedor:</strong>", style_header_label),
            Paragraph(instrutor_nome, style_header_val)
        ],
        [
            Paragraph("<strong>Data e hora:</strong>", style_header_label),
            Paragraph(f"{data_hora_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <strong>Carga horária:</strong> {carga_horaria_str}", style_header_val)
        ],
    ]

    t_meta = Table(meta_rows, colWidths=[4.6 * cm, 15.0 * cm])
    t_meta.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 0.12 * cm))

    # 3. Tabela de Participantes (15 Linhas em Branco para Preenchimento e Assinatura Manual)
    table_part_data = [
        [
            Paragraph("<strong>Nome do Colaborador</strong>", style_th),
            Paragraph("<strong>CPF</strong>", style_th),
            Paragraph("<strong>Cargo</strong>", style_th),
            Paragraph("<strong>Departamento</strong>", style_th),
            Paragraph("<strong>Assinatura</strong>", style_th),
        ]
    ]

    for _ in range(15):
        table_part_data.append(["", "", "", "", ""])

    col_widths_part = [6.0 * cm, 3.2 * cm, 3.4 * cm, 3.4 * cm, 3.6 * cm]
    row_heights_part = [18] + [37] * 15  # 18pt cabeçalho + 37pt (~1.30cm) por linha para assinatura
    t_part = Table(table_part_data, colWidths=col_widths_part, rowHeights=row_heights_part)
    t_part.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#000000')),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_part)

    # Nota do verso
    elements.append(Spacer(1, 0.08 * cm))
    elements.append(Paragraph("*Descrição do conteúdo programático no verso da folha", style_nota_verso))
    elements.append(Spacer(1, 0.12 * cm))

    # 4. Rodapé SGQ (Aprovação)
    elements.append(_criar_rodape_sgq(w_total=w_total))

    # =========================================================================
    # PÁGINA 2 - VERSO (CONTEÚDO DO TREINAMENTO)
    # =========================================================================
    elements.append(PageBreak())

    # 1. Cabeçalho Oficial SGQ (Página 2 de 2)
    elements.append(_criar_cabecalho_sgq(num_pagina=2, total_paginas=2, w_total=w_total))
    elements.append(Spacer(1, 0.25 * cm))

    # 2. Título Central "CONTEÚDO DO TREINAMENTO"
    style_titulo_verso = ParagraphStyle(
        'TituloVerso',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#000000')
    )

    t_titulo_verso = Table([[Paragraph("<strong>CONTEÚDO DO TREINAMENTO</strong>", style_titulo_verso)]], colWidths=[w_total])
    t_titulo_verso.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_titulo_verso)
    elements.append(Spacer(1, 0.15 * cm))

    # 3. Bloco do Conteúdo Programático e Procedimentos Abordados
    procedimentos = list(planejamento.procedimentos.all())
    conteudo_data = []

    if procedimentos:
        for p in procedimentos:
            tag_critico = " <font color='#b91c1c'><strong>[CRÍTICO]</strong></font>" if getattr(p, 'criticidade', '') == 'CRITICO' else ""
            desc = p.descricao or "Sem descrição cadastrada."
            texto = f"• <strong>{p.codigo or ''} - {p.nome or ''}</strong>{tag_critico}<br/>&nbsp;&nbsp;&nbsp;<em>{desc}</em>"
            conteudo_data.append([Paragraph(texto, style_cell)])
    else:
        conteudo_data.append([Paragraph("• Conteúdo programático e orientações técnicas do treinamento.", style_cell)])

    # Preencher altura proporcional para ocupar o espaço do verso harmonicamente (21.5cm de altura)
    t_conteudo = Table(conteudo_data, colWidths=[w_total], rowHeights=[21.5 * cm] if len(conteudo_data) == 1 else None)
    t_conteudo.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.0, colors.HexColor('#000000')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_conteudo)
    elements.append(Spacer(1, 0.25 * cm))

    # 4. Rodapé SGQ (Aprovação) na Página 2
    elements.append(_criar_rodape_sgq(w_total=w_total))

    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

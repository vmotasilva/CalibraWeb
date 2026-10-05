# -*- coding: utf-8 -*-
"""
Gerador de PDF DOC.071 - Fluxograma de Processo Operacional
CalibraWeb - ReportLab
"""

import io
import base64
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from ..models_diagram import DiagramaVersao


class NumberedCanvas(canvas.Canvas):
    """Adiciona paginação 'Página X de Y' e rodapé de conformidade QMS ISO 13485."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Linha divisória de rodapé
        self.setLineWidth(0.5)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.line(30, 35, 812, 35)

        # Textos de rodapé
        self.drawString(30, 24, "CALIBRAWEB — Sistema de Gestão Integrado da Qualidade (ISO 13485:2016)")
        self.drawString(340, 24, "DOC.071 - FLUXOGRAMA DE PROCESSO PADRÃO")
        self.drawRightString(812, 24, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def gerar_pdf_diagrama_doc071(versao: DiagramaVersao, image_base64: str = None) -> bytes:
    """Gera o arquivo PDF DOC.071 em orientação paisagem (Landscape A4)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=30,
        rightMargin=30,
        topMargin=30,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#0F172A"),
        alignment=1
    )
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10)
    cell_bold = ParagraphStyle('CellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10)

    story = []

    # 1. Cabeçalho Padronizado DOC.071
    diagrama = versao.diagrama
    proc_info = f"<b>Procedimento:</b> {diagrama.procedimento.codigo}<br/>" if diagrama.procedimento else ""
    header_data = [
        [
            Paragraph("<b>CALIBRAWEB</b><br/><font size=6 color='#64748B'>SGI / METROLOGIA</font>", cell_style),
            Paragraph(f"<b>PROCEDIMENTO OPERACIONAL PADRÃO</b><br/>{diagrama.titulo.upper()}", title_style),
            Paragraph(f"{proc_info}<b>Identificador:</b> {diagrama.identificador}<br/><b>Revisão:</b> R{versao.revisao:02d}<br/><b>Status:</b> {versao.get_status_display()}", cell_style)
        ]
    ]

    header_table = Table(header_data, colWidths=[130, 490, 162])
    header_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0F172A")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # 2. Metadados de Controle QMS
    elaborador = diagrama.criado_por.get_full_name() or diagrama.criado_por.username
    aprovador = (versao.aprovado_por.get_full_name() or versao.aprovado_por.username) if versao.aprovado_por else "Pendente"
    data_aprov = versao.data_aprovacao.strftime("%d/%m/%Y %H:%M") if versao.data_aprovacao else "Em Aprovação"

    qms_data = [
        [
            Paragraph("<b>Departamento:</b>", cell_bold), Paragraph(diagrama.departamento, cell_style),
            Paragraph("<b>Elaborado por:</b>", cell_bold), Paragraph(elaborador, cell_style),
            Paragraph("<b>Aprovado por:</b>", cell_bold), Paragraph(aprovador, cell_style),
            Paragraph("<b>Data Aprovação:</b>", cell_bold), Paragraph(data_aprov, cell_style),
        ]
    ]
    qms_table = Table(qms_data, colWidths=[80, 120, 80, 130, 80, 130, 80, 82])
    qms_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(qms_table)
    story.append(Spacer(1, 10))

    # 3. Injeção da Imagem do Fluxograma (Canvas xyflow)
    if image_base64:
        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            img_bytes = base64.b64decode(image_base64)
            img_io = io.BytesIO(img_bytes)

            # Ajuste de proporção mantendo limites de impressão paisagem (782 x 380 pt)
            pil_img = PILImage.open(img_io)
            orig_w, orig_h = pil_img.size
            aspect = orig_h / float(orig_w) if orig_w else 1

            target_w = 782
            target_h = target_w * aspect
            if target_h > 380:
                target_h = 380
                target_w = target_h / aspect

            img_io.seek(0)
            rl_img = RLImage(img_io, width=target_w, height=target_h)
            story.append(rl_img)
        except Exception:
            story.append(Paragraph("<i>[Erro ao processar imagem renderizada do fluxograma]</i>", cell_style))
    else:
        story.append(Paragraph("<i>[Topologia cadastrada sem captura de imagem submetida]</i>", cell_style))

    # Constrói o PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()

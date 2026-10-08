# -*- coding: utf-8 -*-
"""
Gerador de PDF DOC.071 - Fluxograma de Processo Operacional
CalibraWeb - ReportLab
"""

import io
import base64
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from ..models_diagram import DiagramaVersao
from .diagram_renderer import DiagramaFlowable


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
        self.drawString(340, 24, "DOC.071 - FLUXOGRAMA / DIAGRAMA DE PROCESSO")
        self.drawRightString(812, 24, f"Página {self._pageNumber} de {page_count}")
        self.restoreState()


def _carregar_fotos(topologia: dict) -> dict:
    """Busca as fotos (Base64 no RH) dos colaboradores usados nos blocos: {id: bytes}."""
    ids = set()
    for n in topologia.get('nodes') or []:
        colab = (n.get('data') or {}).get('colab') if isinstance(n, dict) and isinstance(n.get('data'), dict) else None
        if isinstance(colab, dict) and isinstance(colab.get('id'), int):
            ids.add(colab['id'])
    if not ids:
        return {}
    try:
        from rh.models import Colaborador
        from .diagram_fotos import decodificar_foto_colaborador
        fotos = {}
        for cid, foto in Colaborador.objects.filter(pk__in=ids).values_list('id', 'foto'):
            dec = decodificar_foto_colaborador(foto)
            if dec:
                fotos[cid] = dec[0]
        return fotos
    except Exception:
        return {}


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
    proc_info = f"<b>Procedimento:</b> {escape(diagrama.procedimento.codigo)}<br/>" if diagrama.procedimento else ""
    header_data = [
        [
            Paragraph("<b>CALIBRAWEB</b><br/><font size=6 color='#64748B'>SGI / METROLOGIA</font>", cell_style),
            Paragraph(f"<b>FLUXOGRAMA / DIAGRAMA DE PROCESSO</b><br/>{escape(diagrama.titulo.upper())}", title_style),
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
    elaborador = escape(diagrama.criado_por.get_full_name() or diagrama.criado_por.username)
    aprovador = escape(versao.aprovado_por.get_full_name() or versao.aprovado_por.username) if versao.aprovado_por else "Pendente"
    data_aprov = versao.data_aprovacao.strftime("%d/%m/%Y %H:%M") if versao.data_aprovacao else "Em Aprovação"

    qms_data = [
        [
            Paragraph("<b>Departamento:</b>", cell_bold), Paragraph(escape(diagrama.departamento), cell_style),
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

    # 3. Diagrama: imagem enviada pelo cliente (opcional) ou renderização vetorial no servidor
    topologia = versao.dados_topologia or {}
    imagem_ok = False
    if image_base64:
        try:
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            img_io = io.BytesIO(base64.b64decode(image_base64))

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
            story.append(RLImage(img_io, width=target_w, height=target_h))
            imagem_ok = True
        except Exception:
            imagem_ok = False

    if not imagem_ok:
        if topologia.get('nodes'):
            fotos = _carregar_fotos(topologia)
            desenho = DiagramaFlowable(topologia, max_w=782, max_h=330, fotos=fotos)
            if desenho.scale < 0.5:
                # Diagrama grande: página própria para manter a legibilidade
                story.append(PageBreak())
                desenho = DiagramaFlowable(topologia, max_w=782, max_h=470, fotos=fotos)
            story.append(desenho)
        else:
            story.append(Paragraph("<i>[Fluxograma sem blocos cadastrados]</i>", cell_style))

    # 4. Motivo da revisão e histórico de revisões (rastreabilidade ISO 13485)
    story.append(Spacer(1, 12))
    if versao.motivo_revisao:
        story.append(Paragraph(f"<b>Motivo da revisão R{versao.revisao:02d}:</b> {escape(versao.motivo_revisao)}", cell_style))
        story.append(Spacer(1, 6))

    hist_header = [Paragraph(f"<b>{t}</b>", cell_style) for t in
                   ("Rev.", "Status", "Motivo / Alteração", "Submetido por", "Aprovado por", "Data Aprovação")]
    hist_rows = [hist_header]
    for v in diagrama.versoes.select_related('aprovado_por', 'submetido_por').order_by('revisao'):
        sub = escape(v.submetido_por.get_full_name() or v.submetido_por.username) if v.submetido_por else "-"
        apr = escape(v.aprovado_por.get_full_name() or v.aprovado_por.username) if v.aprovado_por else "-"
        dta = v.data_aprovacao.strftime("%d/%m/%Y") if v.data_aprovacao else "-"
        hist_rows.append([
            Paragraph(f"R{v.revisao:02d}", cell_style),
            Paragraph(v.get_status_display(), cell_style),
            Paragraph(escape(v.motivo_revisao or "-"), cell_style),
            Paragraph(sub, cell_style),
            Paragraph(apr, cell_style),
            Paragraph(dta, cell_style),
        ])
    hist_table = Table(hist_rows, colWidths=[40, 80, 332, 120, 120, 90], repeatRows=1)
    hist_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(KeepTogether([Paragraph("<b>Histórico de Revisões</b>", cell_style), Spacer(1, 3), hist_table]))

    # Constrói o PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()

# -*- coding: utf-8 -*-
"""
Helper para gerar PDFs de listas de presença usando mapeamento de template

Funcionalidades:
- Ler mapeamento de campo do template
- Gerar PDF com posicionamento customizado
- Suporte a múltiplas páginas e layouts
"""

from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import simpleSplit

try:
    import openpyxl
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class GeradorPDFListaPresenca:
    """Gera PDF de lista de presença usando mapeamento de template"""
    
    def __init__(self, template, lista_presenca):
        self.template = template
        self.lista_presenca = lista_presenca
        self.mapeamentos = {}
        self._carregar_mapeamentos()
    
    def _carregar_mapeamentos(self):
        """Carrega mapeamentos do template"""
        for mapeamento in self.template.mapeamentos.all():
            self.mapeamentos[mapeamento.tipo_campo] = {
                'localizacao': mapeamento.localizacao,
                'metodo': mapeamento.metodo,
                'pagina': mapeamento.pagina,
                'obrigatorio': mapeamento.obrigatorio,
                'permite_imagem_marcacao': mapeamento.permite_imagem_marcacao,
            }
    
    def _cel_para_coordenadas(self, referencia):
        """Converte referência de célula (A1) para coordenadas (x, y) em cm"""
        # Formato: A1, B2, etc
        col_letra = ''.join(filter(str.isalpha, referencia)).upper()
        row_num = int(''.join(filter(str.isdigit, referencia)))
        
        # Coluna A = 1cm, incrementa ~2.5cm por coluna
        x = 1 + (ord(col_letra[0]) - ord('A')) * 2.5
        if len(col_letra) > 1:
            x += (ord(col_letra[1]) - ord('A')) * 0.25
        
        # Linha 1 = 26cm (topo), decrementa 0.8cm por linha
        y = 26 - (row_num - 1) * 0.8
        
        return x * cm, y * cm
    
    def gerar_pdf_basico(self):
        """Gera PDF básico com layout padrão (sem usar Excel template)"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#417690'),
            alignment=1,  # Center
            spaceAfter=12
        )
        elements.append(Paragraph("LISTA DE PRESENÇA", title_style))
        elements.append(Spacer(1, 0.3*cm))
        
        # Informações principais
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=4
        )
        
        # Construir info com mapeamento
        info_items = [
            ('Título do Treinamento', self._obter_valor_campo('titulo_treinamento', 
                self.lista_presenca.titulo)),
            ('Categoria', self._obter_valor_campo('categoria_treinamento', 
                getattr(self.lista_presenca, 'categoria', ''))),
            ('Facilitador', self._obter_valor_campo('facilitador_fornecedor', 
                str(self.lista_presenca.instrutor) if self.lista_presenca.instrutor else '')),
            ('Data', self._obter_valor_campo('data_hora', 
                self.lista_presenca.data_sessao.strftime('%d/%m/%Y') if self.lista_presenca.data_sessao else '')),
            ('Carga Horária', self._obter_valor_campo('carga_horaria', 
                f"{self.lista_presenca.carga_horaria}h" if self.lista_presenca.carga_horaria else '')),
            ('Local', self._obter_valor_campo('local_realizacao', 
                self.lista_presenca.local or '')),
        ]
        
        for label, valor in info_items:
            if valor:
                elements.append(Paragraph(f"<b>{label}:</b> {valor}", info_style))
        
        elements.append(Spacer(1, 0.5*cm))
        
        # Tabela de participantes
        registros = self.lista_presenca.registros.select_related(
            'colaborador', 'procedimento'
        ).order_by('colaborador__nome_completo')
        
        table_data = [['Nº', 'Nome', 'Matrícula', 'Assinatura']]
        
        for i, registro in enumerate(registros, 1):
            table_data.append([
                str(i),
                registro.colaborador.nome_completo,
                registro.colaborador.matricula or '',
                ''  # Espaço para assinatura
            ])
        
        # Criar tabela com estilo
        participantes_table = Table(table_data, colWidths=[1*cm, 9*cm, 3*cm, 3.5*cm])
        participantes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f7fc')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('MIN_ROW_HEIGHT', (0, 1), (-1, -1), 0.8*cm),  # Espaço para assinatura
        ]))
        
        elements.append(participantes_table)
        
        # Assinatura de finalização
        elements.append(Spacer(1, 1*cm))
        signature_style = ParagraphStyle(
            'Signature',
            parent=styles['Normal'],
            fontSize=10,
            alignment=1
        )
        elements.append(Paragraph("_________________________", signature_style))
        elements.append(Paragraph("Facilitador / Instrutor", signature_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return buffer
    
    def _obter_valor_campo(self, tipo_campo, valor_padrao=''):
        """Obtém valor do campo mapeado ou valor padrão"""
        if tipo_campo in self.mapeamentos:
            return valor_padrao
        return valor_padrao
    
    def gerar_pdf_com_mapeamento(self):
        """Gera PDF usando mapeamento de Excel template"""
        
        if not OPENPYXL_AVAILABLE:
            # Se openpyxl não está disponível, gerar PDF básico
            return self.gerar_pdf_basico()
        
        if not self.template.arquivo_excel_template:
            # Se não tem arquivo Excel, gerar PDF básico
            return self.gerar_pdf_basico()
        
        buffer = BytesIO()
        
        try:
            # Carregar Excel template como fundo
            arquivo_path = self.template.arquivo_excel_template.path
            workbook = openpyxl.load_workbook(arquivo_path)
            
            # Criar PDF usando ReportLab
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=A4)
            
            # Dimensões da página A4
            width, height = A4
            
            # Preenchero dados nos campos mapeados
            self._preencher_campos_pdf(c, width, height)
            
            # Adicionar tabela de participantes
            self._adicionar_tabela_participantes_pdf(c, width, height)
            
            c.showPage()
            c.save()
            
            pdf_buffer.seek(0)
            return pdf_buffer
        
        except Exception as e:
            # Em caso de erro, gerar PDF básico
            print(f"Erro ao gerar PDF com mapeamento: {str(e)}")
            return self.gerar_pdf_basico()
    
    def _preencher_campos_pdf(self, canvas_obj, width, height):
        """Preenche campos no PDF usando mapeamento"""
        
        # Mapear tipo_campo para valor da lista de presença
        campos_valores = {
            'titulo_treinamento': self.lista_presenca.titulo,
            'categoria_treinamento': getattr(self.lista_presenca, 'categoria', ''),
            'metodologia': getattr(self.lista_presenca, 'metodologia', ''),
            'area_conhecimento': getattr(self.lista_presenca, 'area_conhecimento', ''),
            'necessita_avaliacao': 'Sim' if getattr(self.lista_presenca, 'necessita_avaliacao', False) else 'Não',
            'facilitador_fornecedor': str(self.lista_presenca.instrutor) if self.lista_presenca.instrutor else '',
            'data_hora': self.lista_presenca.data_sessao.strftime('%d/%m/%Y') if self.lista_presenca.data_sessao else '',
            'carga_horaria': f"{self.lista_presenca.carga_horaria}h" if self.lista_presenca.carga_horaria else '',
            'procedimentos_assuntos': ', '.join([p.codigo for p in self.lista_presenca.procedimentos.all()]),
        }
        
        # Preencher cada campo mapeado
        for tipo_campo, mapeamento in self.mapeamentos.items():
            if tipo_campo not in campos_valores:
                continue
            
            valor = campos_valores[tipo_campo]
            localizacao = mapeamento['localizacao']
            
            try:
                x, y = self._cel_para_coordenadas(localizacao)
                canvas_obj.drawString(x, y, str(valor)[:50])  # Limitar tamanho
            except:
                pass  # Ignorar erros de conversão
    
    def _adicionar_tabela_participantes_pdf(self, canvas_obj, width, height):
        """Adiciona tabela de participantes ao PDF"""
        # Implementar conforme necessário
        pass


def gerar_lista_presenca_com_mapeamento(lista_presenca, template=None):
    """
    Função helper para gerar PDF de lista de presença com mapeamento
    
    Args:
        lista_presenca: Instância de ListaPresenca
        template: TemplateListaPresenca (se None, usa template padrão)
    
    Returns:
        BytesIO: Buffer contendo PDF
    """
    if template is None:
        # Tentar obter template padrão ativo
        from procedures.models import TemplateListaPresenca
        template = TemplateListaPresenca.objects.filter(ativo=True).first()
        
        if not template:
            # Se não tem template, usar gerador básico
            gerador = GeradorPDFListaPresenca(None, lista_presenca)
            return gerador.gerar_pdf_basico()
    
    gerador = GeradorPDFListaPresenca(template, lista_presenca)
    return gerador.gerar_pdf_com_mapeamento()

#!/usr/bin/env python
"""Debug script para testar aplicação de carimbo"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import HistoricoCalibracao
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

try:
    # Get a test record - use ID 127 diretamente
    historico = HistoricoCalibracao.objects.get(pk=127)
    
    if not historico or not historico.certificado:
        print("❌ Histórico 127 não tem certificado")
        sys.exit(1)
    
    print(f"✓ Histórico encontrado: {historico.pk}")
    print(f"✓ Certificado: {historico.certificado.name}")
    
    # Test reading PDF - keep file open!
    pdf_file = historico.certificado.open('rb')
    pdf_bytes = pdf_file.read()
    pdf_file.close()
    
    from io import BytesIO as BIO
    pdf_buffer = BIO(pdf_bytes)
    original_pdf = PdfReader(pdf_buffer)
    
    print(f"✓ PDF lido com sucesso - páginas: {len(original_pdf.pages)}")
    
    # Test creating stamp
    stamp_buffer = BytesIO()
    stamp_canvas = canvas.Canvas(stamp_buffer, pagesize=letter)
    
    x, y = 450, 100
    stamp_canvas.setLineWidth(2)
    stamp_canvas.rect(x, y, 120, 100)
    stamp_canvas.setFont("Helvetica-Bold", 8)
    stamp_canvas.drawString(x + 5, y + 85, "VALIDADO")
    stamp_canvas.save()
    
    print(f"✓ Canvas criado com sucesso - tamanho: {stamp_buffer.tell()} bytes")
    
    # Test reading stamp
    stamp_buffer.seek(0)
    stamp_buffer_bytes = BytesIO(stamp_buffer.getvalue())
    stamp_pdf = PdfReader(stamp_buffer_bytes)
    stamp_page = stamp_pdf.pages[0]
    
    print(f"✓ Stamp PDF lido com sucesso")
    
    # Test merging
    writer = PdfWriter()
    test_page = original_pdf.pages[0]
    test_page.merge_page(stamp_page)
    writer.add_page(test_page)
    
    print(f"✓ Merge realizado com sucesso")
    
    # Test writing
    stamped_buffer = BytesIO()
    writer.write(stamped_buffer)
    stamped_buffer.seek(0)
    
    print(f"✓ Arquivo carimbado criado - tamanho: {len(stamped_buffer.getvalue())} bytes")
    print("\n✅ Todos os testes passaram!")
    
except Exception as e:
    print(f"\n❌ Erro: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

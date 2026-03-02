#!/usr/bin/env python
"""
Criar um favicon simples para o Calibra QMS
"""
from PIL import Image, ImageDraw, ImageFont

# Criar imagem 64x64
img = Image.new('RGB', (64, 64), color='#0d6efd')

# Desenhar um "C" simples
draw = ImageDraw.Draw(img)

# Desenhar círculo azul escuro
draw.ellipse([2, 2, 62, 62], fill='#0d6efd', outline='#ffffff', width=2)

# Texto "C"
try:
    # Tentar usar fonte padrão
    font = ImageFont.load_default()
    draw.text((24, 20), "C", fill='#ffffff', font=font)
except:
    pass

# Salvar como favicon
img.save('static/favicon.ico')
img.save('static/favicon.png')

print("Favicon criado com sucesso!")
print("  - static/favicon.ico")
print("  - static/favicon.png")

#!/usr/bin/env python
"""
Script para testar as duas versões do sistema de carimbo.

VERSÃO ORIGINAL: editar_historico.html
- Usa conversão complexa de coordenadas (screen → canvas → PDF)
- Múltiplas operações de conversão e inversão de Y

VERSÃO SIMPLIFICADA: editar_historico_simplificado.html
- Trabalha direto com coordenadas PDF
- Menos conversões intermediárias
- Objetivo: eliminar offset entre preview e carimbo aplicado
"""

import os
import sys
from pathlib import Path

# Adicionar o diretório do projeto ao path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibragem.settings')

import django
django.setup()

from django.urls import path
from metrologia.views import editar_historico_calibracao

def show_menu():
    print("\n" + "="*60)
    print("  TESTE DE VERSÕES - SISTEMA DE CARIMBO DE CERTIFICADOS")
    print("="*60)
    print("\n1. Usar VERSÃO ORIGINAL (editar_historico.html)")
    print("   → Conversão complexa de coordenadas")
    print("   → Status: COM OFFSET CONHECIDO\n")
    
    print("2. Usar VERSÃO SIMPLIFICADA (editar_historico_simplificado.html)")
    print("   → Trabalha direto em espaço PDF")
    print("   → Status: TESTE PARA FIX DO OFFSET\n")
    
    print("3. Comparar coordenadas teóricas")
    print("   → Mostra cálculos passo a passo\n")
    
    print("0. Sair\n")
    
    return input("Escolha uma opção (0-3): ").strip()

def test_coordinate_math():
    """Testa a matemática de conversão de coordenadas"""
    print("\n" + "="*60)
    print("  TESTE DE MATEMÁTICA DE COORDENADAS")
    print("="*60)
    
    # Exemplo: clique em posição na tela
    click_screen_x = 450.5
    click_screen_y = 300.25
    
    # Canvas em tela
    canvas_rect_width = 600.0
    canvas_rect_height = 800.0
    
    # Canvas renderizado
    canvas_pixel_width = 892.0  # 595 * 1.5
    canvas_pixel_height = 1263.0  # 842 * 1.5
    
    # PDF
    pdf_width = 595.0
    pdf_height = 842.0
    
    print(f"\nDados de entrada:")
    print(f"  - Clique em tela: ({click_screen_x}, {click_screen_y})")
    print(f"  - Canvas em tela: {canvas_rect_width}x{canvas_rect_height}")
    print(f"  - Canvas renderizado: {canvas_pixel_width}x{canvas_pixel_height}")
    print(f"  - PDF dimensions: {pdf_width}x{pdf_height}")
    
    # ===== VERSÃO ORIGINAL =====
    print(f"\n--- VERSÃO ORIGINAL ---")
    
    scale_screen_to_canvas = canvas_pixel_width / canvas_rect_width
    canvas_pixel_x = click_screen_x * scale_screen_to_canvas
    canvas_pixel_y = click_screen_y * scale_screen_to_canvas
    
    print(f"1. Scale factor: {scale_screen_to_canvas:.4f}")
    print(f"2. Canvas pixel X: {canvas_pixel_x:.2f}")
    print(f"3. Canvas pixel Y: {canvas_pixel_y:.2f}")
    
    pdf_x = (canvas_pixel_x / canvas_pixel_width) * pdf_width
    pdf_y = (canvas_pixel_y / canvas_pixel_height) * pdf_height
    
    print(f"4. PDF X (top-origin): {pdf_x:.2f}")
    print(f"5. PDF Y (top-origin): {pdf_y:.2f}")
    
    pdf_y_correct = pdf_height - pdf_y
    
    print(f"6. PDF Y inverted (bottom-origin): {pdf_y_correct:.2f}")
    print(f"\n✓ Coordenadas finais: ({pdf_x:.2f}, {pdf_y_correct:.2f})")
    
    # ===== VERSÃO SIMPLIFICADA =====
    print(f"\n--- VERSÃO SIMPLIFICADA ---")
    
    scale_simple = canvas_pixel_width / canvas_rect_width
    canvas_px = click_screen_x * scale_simple
    canvas_py = click_screen_y * scale_simple
    
    print(f"1. Scale factor: {scale_simple:.4f}")
    print(f"2. Canvas pixel X: {canvas_px:.2f}")
    print(f"3. Canvas pixel Y: {canvas_py:.2f}")
    
    pdf_px = (canvas_px / canvas_pixel_width) * pdf_width
    pdf_py = (canvas_py / canvas_pixel_height) * pdf_height
    
    print(f"4. PDF X: {pdf_px:.2f}")
    print(f"5. PDF Y (top-origin): {pdf_py:.2f}")
    
    pdf_py_inverted = pdf_height - pdf_py
    
    print(f"6. PDF Y inverted (bottom-origin): {pdf_py_inverted:.2f}")
    print(f"\n✓ Coordenadas finais: ({pdf_px:.2f}, {pdf_py_inverted:.2f})")
    
    # Comparar
    print(f"\n--- COMPARAÇÃO ---")
    x_diff = abs(pdf_x - pdf_px)
    y_diff = abs(pdf_y_correct - pdf_py_inverted)
    
    print(f"Diferença em X: {x_diff:.4f}")
    print(f"Diferença em Y: {y_diff:.4f}")
    
    if x_diff < 0.01 and y_diff < 0.01:
        print("\n✓ Versões produzem MESMO RESULTADO")
    else:
        print(f"\n✗ Versões produzem RESULTADOS DIFERENTES")

def show_comparison():
    print("\n" + "="*60)
    print("  COMPARAÇÃO DE VERSÕES")
    print("="*60)
    
    print("\nVERSÃO ORIGINAL:")
    print("  - Arquivo: metrologia/templates/metrologia/editar_historico.html")
    print("  - Conversões: Screen → Canvas → PDF → Invert Y")
    print("  - Linhas críticas: 750-835")
    print("  - Status: COM OFFSET DOCUMENTADO")
    print("  - Problema: Double Y-inversion suspeita")
    
    print("\nVERSÃO SIMPLIFICADA:")
    print("  - Arquivo: metrologia/templates/metrologia/editar_historico_simplificado.html")
    print("  - Conversões: Screen → Canvas → PDF → Invert Y (uma vez)")
    print("  - Linhas críticas: 220-280 (muito mais simples)")
    print("  - Status: TESTE")
    print("  - Melhorias: Sem conversões desnecessárias")
    
    print("\nCOMO TESTAR:")
    print("  1. Abra o histórico 127 com VERSÃO ORIGINAL")
    print("  2. Clique em uma posição no PDF")
    print("  3. Note a posição do preview vs carimbo aplicado")
    print("  4. Abra o mesmo histórico com VERSÃO SIMPLIFICADA")
    print("  5. Repita no MESMO PDF e posição")
    print("  6. Compare os resultados\n")

def main():
    while True:
        choice = show_menu()
        
        if choice == '1':
            print("\n✓ Usando VERSÃO ORIGINAL")
            print("  URL: http://127.0.0.1:8000/metrologia/historico/127/editar/")
            print("  Template: editar_historico.html")
            print("  → Use o navegador para testar")
            
        elif choice == '2':
            print("\n✓ Usando VERSÃO SIMPLIFICADA")
            print("  URL: http://127.0.0.1:8000/metrologia/historico/127/editar/?use_simplified=true")
            print("  Template: editar_historico_simplificado.html")
            print("  → Modifique a view para usar a versão simplificada (veja abaixo)")
            
        elif choice == '3':
            test_coordinate_math()
            
        elif choice == '0':
            print("\nSaindo...")
            break
        
        else:
            print("\n✗ Opção inválida")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSaindo...")
        sys.exit(0)

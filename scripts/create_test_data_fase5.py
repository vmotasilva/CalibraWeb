#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fixture script to generate test data for Phase 5 - Exports and Reports

Usage:
    python manage.py shell < scripts/create_test_data_fase5.py
    or
    python scripts/create_test_data_fase5.py

This script creates:
    - 5 categories (Categorias de Instrumento)
    - 3 sectors (Setores)
    - 20 test instruments with various statuses
    - 40 calibration histories with different dates
"""

import os
import sys
import django
from datetime import datetime, timedelta
from random import randint, choice, random

# Setup Django
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

from django.contrib.auth.models import User
from metrologia.models import (
    Instrumento,
    CategoriaInstrumento,
    HistoricoCalibracao,
    FaixaMedicao,
)
from organization.models import Setor
from rh.models import Colaborador

print("=" * 80)
print("CREATING TEST DATA FOR PHASE 5 - EXPORTS AND REPORTS")
print("=" * 80)

# ==============================================================================
# 1. CREATE CATEGORIES
# ==============================================================================
print("\n[1/5] Creating instrument categories...")

categories = [
    ("Paquímetro", "Instrumentos de medição linear"),
    ("Termômetro", "Instrumentos de medição de temperatura"),
    ("Manômetro", "Instrumentos de medição de pressão"),
    ("Multímetro", "Instrumentos de medição elétrica"),
    ("Escala", "Instrumentos de pesagem"),
]

cat_objects = []
for name, description in categories:
    cat, created = CategoriaInstrumento.objects.get_or_create(
        nome=name,
        defaults={"descricao": description}
    )
    if created:
        print(f"  ✓ Criada categoria: {name}")
    else:
        print(f"  ℹ Categoria já existe: {name}")
    cat_objects.append(cat)

# ==============================================================================
# 2. CREATE SECTORS
# ==============================================================================
print("\n[2/5] Creating sectors...")

sectors = [
    ("Metrologia", "Admin Metrologia"),
    ("TI", "Admin TI"),
    ("Produção", "Admin Produção"),
]

setor_objects = []
for name, responsavel in sectors:
    setor, created = Setor.objects.get_or_create(
        nome=name,
        defaults={"responsavel": responsavel}
    )
    if created:
        print(f"  ✓ Criado setor: {name}")
    else:
        print(f"  ℹ Setor já existe: {name}")
    setor_objects.append(setor)

# ==============================================================================
# 3. CREATE TEST INSTRUMENTS
# ==============================================================================
print("\n[3/5] Creating test instruments...")

today = datetime.now().date()
instruments_data = [
    ("INSTR-001", "PAQ-001", "Paquímetro Digital 0-150mm", 0),  # Vigente
    ("INSTR-002", "PAQ-002", "Paquímetro Analógico 0-200mm", -30),  # Vencido 30 dias
    ("INSTR-003", "TERM-001", "Termômetro Digital -50 a 50°C", 15),  # Vence em 15 dias
    ("INSTR-004", "TERM-002", "Termômetro Analógico -20 a 100°C", -60),  # Vencido 60 dias
    ("INSTR-005", "MAN-001", "Manômetro 0-10 bar", 45),  # Vence em 45 dias
    ("INSTR-006", "MAN-002", "Manômetro 0-100 bar", -5),  # Vencido 5 dias
    ("INSTR-007", "MULTI-001", "Multímetro Digital", 90),  # Vence em 90 dias
    ("INSTR-008", "MULTI-002", "Multímetro Analógico", -120),  # Vencido 120 dias
    ("INSTR-009", "ESCA-001", "Escala 0-500g", 20),  # Vence em 20 dias
    ("INSTR-010", "ESCA-002", "Escala 0-5kg", -10),  # Vencido 10 dias
    ("INSTR-011", "PAQ-003", "Paquímetro Digital 0-300mm", 60),  # Vence em 60 dias
    ("INSTR-012", "TERM-003", "Termômetro com Sonda", 5),  # Vence em 5 dias
    ("INSTR-013", "MAN-003", "Manômetro Digital 0-50bar", 35),  # Vence em 35 dias
    ("INSTR-014", "MULTI-003", "Multímetro Profissional", -45),  # Vencido 45 dias
    ("INSTR-015", "ESCA-003", "Escala Analógica 0-2kg", 75),  # Vence em 75 dias
    ("INSTR-016", "PAQ-004", "Paquímetro Vernier 0-150mm", 10),  # Vence em 10 dias
    ("INSTR-017", "TERM-004", "Termômetro Infravermelho", 55),  # Vence em 55 dias
    ("INSTR-018", "MAN-004", "Manômetro de Ressort", -25),  # Vencido 25 dias
    ("INSTR-019", "MULTI-004", "Multímetro Clamp", 40),  # Vence em 40 dias
    ("INSTR-020", "ESCA-004", "Escala Eletrônica 0-10kg", 8),  # Vence em 8 dias
]

instrumento_objects = []
for tag, codigo, descricao, dias_diff in instruments_data:
    categoria = choice(cat_objects)
    setor = choice(setor_objects)
    data_proxima_calibracao = today + timedelta(days=dias_diff)
    
    instrumento, created = Instrumento.objects.get_or_create(
        tag=tag,
        defaults={
            "codigo": codigo,
            "descricao": descricao,
            "categoria": categoria,
            "setor": setor,
            "ativo": True,
            "data_proxima_calibracao": data_proxima_calibracao,
            "data_ultima_calibracao": today - timedelta(days=365),
            "frequencia_meses": 12,
            "fabricante": "Fabricante Teste",
            "modelo": f"Modelo-{codigo}",
        }
    )
    
    if created:
        status = "VENCIDO" if dias_diff < 0 else f"VENCE EM {dias_diff}d"
        print(f"  ✓ Instrumento criado: {tag} [{status}]")
    else:
        print(f"  ℹ Instrumento já existe: {tag}")
    
    instrumento_objects.append(instrumento)

# ==============================================================================
# 4. CREATE CALIBRATION HISTORIES
# ==============================================================================
print("\n[4/5] Creating calibration histories...")

# Get or create an admin user for records
admin_user, _ = User.objects.get_or_create(
    username="admin_calibrador",
    defaults={"email": "admin@calibraweb.com", "is_staff": True}
)

# Get or create a Colaborador
try:
    colaborador = Colaborador.objects.filter(user=admin_user).first()
    if not colaborador:
        colaborador, _ = Colaborador.objects.get_or_create(
            usuario=admin_user.username,
            defaults={
                "nome": "Admin Calibrador",
                "user": admin_user,
                "ativo": True,
            }
        )
except:
    colaborador = None

histórico_count = 0
for instrumento in instrumento_objects:
    # Create 2 calibration records per instrument
    for i in range(2):
        dias_passados = (i + 1) * 180 + randint(0, 30)
        data_calibracao = today - timedelta(days=dias_passados)
        data_proxima = data_calibracao + timedelta(days=365)
        
        historico, created = HistoricoCalibracao.objects.get_or_create(
            instrumento=instrumento,
            data_calibracao=data_calibracao,
            defaults={
                "resultado": choice(["Dentro da Tolerância", "Fora da Tolerância - Ajustado"]),
                "data_proxima_calibracao": data_proxima,
                "nro_certificado": f"CERT-{instrumento.codigo}-{i+1}-{data_calibracao.year}",
                "fornecedor": choice(["Inmetro", "Labtest", "Calibrações Teste"]),
                "observacoes": f"Calibração {i+1} de {instrumento.codigo}",
                "ativo": True,
            }
        )
        
        if created:
            histórico_count += 1

print(f"  ✓ Criados {histórico_count} registros de calibração")

# ==============================================================================
# 5. SUMMARY
# ==============================================================================
print("\n" + "=" * 80)
print("TEST DATA CREATED SUCCESSFULLY!")
print("=" * 80)

summary = {
    "Categorias": CategoriaInstrumento.objects.filter(ativa=True).count(),
    "Setores": Setor.objects.filter(ativa=True).count(),
    "Instrumentos": Instrumento.objects.filter(ativo=True).count(),
    "Históricos de Calibração": HistoricoCalibracao.objects.filter(ativo=True).count(),
}

for key, value in summary.items():
    print(f"  {key}: {value}")

print("\n📊 Test Data Statistics:")
vencidos = Instrumento.objects.filter(
    ativo=True,
    data_proxima_calibracao__lt=today
).count()
vencendo_30d = Instrumento.objects.filter(
    ativo=True,
    data_proxima_calibracao__gte=today,
    data_proxima_calibracao__lte=today + timedelta(days=30)
).count()

print(f"  • Instrumentos vencidos: {vencidos}")
print(f"  • Vencendo em 30 dias: {vencendo_30d}")
print(f"  • Vigentes: {Instrumento.objects.filter(ativo=True).count() - vencidos - vencendo_30d}")

print("\n✅ Dados prontos para testes de export!")
print("   Tente: Dashboard → Metrologia → Instrumentos → Exportar")
print("=" * 80)

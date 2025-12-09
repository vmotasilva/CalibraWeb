# -*- coding: utf-8 -*-
"""
Django management command to create test data for Phase 5

Usage:
    python manage.py create_test_data_fase5
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from random import choice

from metrologia.models import Instrumento, CategoriaInstrumento, HistoricoCalibracao
from organization.models import Setor


class Command(BaseCommand):
    help = "Create test data for Phase 5 - Exports and Reports"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("CREATING TEST DATA FOR PHASE 5"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

        # Create categories
        self.stdout.write("\n[1/4] Creating instrument categories...")
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
                self.stdout.write(f"  [OK] Criada categoria: {name}")
            else:
                self.stdout.write(f"  [EXISTE] Categoria ja existe: {name}")
            cat_objects.append(cat)

        # Create sectors
        self.stdout.write("\n[2/4] Creating sectors...")
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
                self.stdout.write(f"  [OK] Criado setor: {name}")
            else:
                self.stdout.write(f"  [EXISTE] Setor ja existe: {name}")
            setor_objects.append(setor)

        # Create instruments
        self.stdout.write("\n[3/4] Creating test instruments...")
        today = timezone.now().date()
        instruments_data = [
            ("INSTR-001", "PAQ-001", "Paquímetro Digital 0-150mm", 0),
            ("INSTR-002", "PAQ-002", "Paquímetro Analógico 0-200mm", -30),
            ("INSTR-003", "TERM-001", "Termômetro Digital -50 a 50°C", 15),
            ("INSTR-004", "TERM-002", "Termômetro Analógico -20 a 100°C", -60),
            ("INSTR-005", "MAN-001", "Manômetro 0-10 bar", 45),
            ("INSTR-006", "MAN-002", "Manômetro 0-100 bar", -5),
            ("INSTR-007", "MULTI-001", "Multímetro Digital", 90),
            ("INSTR-008", "MULTI-002", "Multímetro Analógico", -120),
            ("INSTR-009", "ESCA-001", "Escala 0-500g", 20),
            ("INSTR-010", "ESCA-002", "Escala 0-5kg", -10),
            ("INSTR-011", "PAQ-003", "Paquímetro Digital 0-300mm", 60),
            ("INSTR-012", "TERM-003", "Termômetro com Sonda", 5),
            ("INSTR-013", "MAN-003", "Manômetro Digital 0-50bar", 35),
            ("INSTR-014", "MULTI-003", "Multímetro Profissional", -45),
            ("INSTR-015", "ESCA-003", "Escala Analógica 0-2kg", 75),
            ("INSTR-016", "PAQ-004", "Paquímetro Vernier 0-150mm", 10),
            ("INSTR-017", "TERM-004", "Termômetro Infravermelho", 55),
            ("INSTR-018", "MAN-004", "Manômetro de Ressort", -25),
            ("INSTR-019", "MULTI-004", "Multímetro Clamp", 40),
            ("INSTR-020", "ESCA-004", "Escala Eletrônica 0-10kg", 8),
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
                self.stdout.write(f"  [OK] Instrumento criado: {tag} [{status}]")
            else:
                self.stdout.write(f"  [EXISTE] Instrumento ja existe: {tag}")

            instrumento_objects.append(instrumento)

        # Create calibration histories
        self.stdout.write("\n[4/4] Creating calibration histories...")
        histórico_count = 0
        for instrumento in instrumento_objects:
            for i in range(2):
                dias_passados = (i + 1) * 180 + 15
                data_calibracao = today - timedelta(days=dias_passados)

                historico, created = HistoricoCalibracao.objects.get_or_create(
                    instrumento=instrumento,
                    data_calibracao=data_calibracao,
                    defaults={
                        "numero_certificado": f"CERT-{instrumento.codigo}-{i+1}-{data_calibracao.year}",
                        "tipo_calibracao": "EXTERNA",
                        "fornecedor": choice(["Inmetro", "Labtest", "Calibracoes Teste"]),
                        "responsavel": "Tecnico de Calibracao",
                        "tem_selo_rbc": choice([True, False]),
                    }
                )

                if created:
                    histórico_count += 1

        self.stdout.write(f"  [OK] Criados {histórico_count} registros de calibracao")

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("[SUCCESS] TEST DATA CREATED SUCCESSFULLY!"))
        self.stdout.write("=" * 80)

        summary = {
            "Categorias": CategoriaInstrumento.objects.count(),
            "Setores": Setor.objects.count(),
            "Instrumentos": Instrumento.objects.filter(ativo=True).count(),
            "Historicos": HistoricoCalibracao.objects.count(),
        }

        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

        # Statistics
        self.stdout.write("\n[STATS] Test Data Statistics:")
        vencidos = Instrumento.objects.filter(
            ativo=True,
            data_proxima_calibracao__lt=today
        ).count()
        vencendo_30d = Instrumento.objects.filter(
            ativo=True,
            data_proxima_calibracao__gte=today,
            data_proxima_calibracao__lte=today + timedelta(days=30)
        ).count()

        vigentes = Instrumento.objects.filter(ativo=True).count() - vencidos - vencendo_30d

        self.stdout.write(f"  - Instrumentos vencidos: {vencidos}")
        self.stdout.write(f"  - Vencendo em 30 dias: {vencendo_30d}")
        self.stdout.write(f"  - Vigentes: {vigentes}")

        self.stdout.write("\n[SUCCESS] Dados prontos para testes de export!")
        self.stdout.write("   Tente: Dashboard -> Metrologia -> Instrumentos -> Exportar")
        self.stdout.write("=" * 80)

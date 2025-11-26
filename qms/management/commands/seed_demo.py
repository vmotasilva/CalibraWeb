from datetime import date, timedelta

from django.core.management.base import BaseCommand

from qms.models import (
    CategoriaInstrumento,
    CentroCusto,
    Colaborador,
    HistoricoCalibracao,
    Instrumento,
    PacoteTreinamento,
    Procedimento,
    Setor,
    UnidadeMedida,
)


class Command(BaseCommand):
    help = "Populate the database with a small demo dataset for RH and Metrologia"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding demo data..."))

        # --- Setores & Centros de Custo ---
        setores = {}
        for nome in ["METROLOGIA", "RH", "PRODUCAO"]:
            s, _ = Setor.objects.get_or_create(nome=nome)
            setores[nome] = s
        cc_met, _ = CentroCusto.objects.get_or_create(setor=setores["METROLOGIA"], codigo="100", defaults={"descricao": "Metrologia"})
        cc_rh, _ = CentroCusto.objects.get_or_create(setor=setores["RH"], codigo="200", defaults={"descricao": "RH"})
        cc_prod, _ = CentroCusto.objects.get_or_create(setor=setores["PRODUCAO"], codigo="300", defaults={"descricao": "Produção"})

        # --- RH: Colaboradores (hierarquia simples) ---
        gerente, _ = Colaborador.objects.get_or_create(
            matricula="G001",
            defaults={
                "nome_completo": "GERENTE QUALIDADE",
                "cpf": "00000000191",
                "cargo": "Gerente da Qualidade",
                "grupo": "ADM",
                "setor": setores["METROLOGIA"],
                "centro_custo": cc_met,
                "turno": "ADM",
                "salario": 12000,
            },
        )
        supervisor, _ = Colaborador.objects.get_or_create(
            matricula="S001",
            defaults={
                "nome_completo": "SUPERVISOR METROLOGIA",
                "cpf": "00000000272",
                "cargo": "Supervisor de Metrologia",
                "grupo": "ADM",
                "setor": setores["METROLOGIA"],
                "centro_custo": cc_met,
                "turno": "ADM",
                "salario": 8500,
                "gerente": gerente,
            },
        )
        tec1, _ = Colaborador.objects.get_or_create(
            matricula="T001",
            defaults={
                "nome_completo": "TECNICO 1",
                "cpf": "00000000353",
                "cargo": "Técnico de Metrologia",
                "grupo": "OPER",
                "setor": setores["METROLOGIA"],
                "centro_custo": cc_met,
                "turno": "ADM",
                "salario": 4500,
                "lider": supervisor,
                "supervisor": supervisor,
                "gerente": gerente,
            },
        )
        tec2, _ = Colaborador.objects.get_or_create(
            matricula="T002",
            defaults={
                "nome_completo": "TECNICO 2",
                "cpf": "00000000434",
                "cargo": "Técnico de Metrologia",
                "grupo": "OPER",
                "setor": setores["METROLOGIA"],
                "centro_custo": cc_met,
                "turno": "ADM",
                "salario": 4600,
                "lider": supervisor,
                "supervisor": supervisor,
                "gerente": gerente,
            },
        )

        # --- GED + Treinamentos (mínimo para RH tela) ---
        proc_pop, _ = Procedimento.objects.get_or_create(
            codigo="POP.MET.001",
            defaults={"titulo": "CONTROLE DE INSTRUMENTOS", "revisao_atual": "A", "aplica_treinamento": True, "setor": setores["METROLOGIA"]},
        )
        pacote, _ = PacoteTreinamento.objects.get_or_create(nome="PACOTE METROLOGIA", defaults={"descricao": "Treinamentos base"})
        pacote.procedimentos.add(proc_pop)
        for c in [tec1, tec2]:
            c.pacotes_treinamento.add(pacote)

        # --- Metrologia: Unidades, Categorias, Instrumentos ---
        mm, _ = UnidadeMedida.objects.get_or_create(nome="Milímetro", sigla="mm")
        kg, _ = UnidadeMedida.objects.get_or_create(nome="Quilograma", sigla="kg")

        cat_paq, _ = CategoriaInstrumento.objects.get_or_create(nome="PAQUIMETRO")
        cat_bal, _ = CategoriaInstrumento.objects.get_or_create(nome="BALANCA")

        hoje = date.today()
        inst1, _ = Instrumento.objects.get_or_create(
            tag="MET-PAQ-001",
            defaults={
                "descricao": "Paquímetro 150mm",
                "fabricante": "Mitutoyo",
                "modelo": "500-196",
                "categoria": cat_paq,
                "setor": setores["METROLOGIA"],
                "frequencia_meses": 12,
                "data_ultima_calibracao": hoje - timedelta(days=320),
                "data_proxima_calibracao": hoje + timedelta(days=40),
                "responsavel": tec1,
            },
        )
        inst2, _ = Instrumento.objects.get_or_create(
            tag="PRD-BAL-010",
            defaults={
                "descricao": "Balança 5kg",
                "fabricante": "Toledo",
                "modelo": "2095",
                "categoria": cat_bal,
                "setor": setores["PRODUCAO"],
                "frequencia_meses": 6,
                "data_ultima_calibracao": hoje - timedelta(days=220),
                "data_proxima_calibracao": hoje - timedelta(days=10),
                "responsavel": tec2,
            },
        )

        # histórico mínimo para alimentar datas
        HistoricoCalibracao.objects.get_or_create(
            instrumento=inst1,
            data_calibracao=hoje - timedelta(days=320),
            numero_certificado="CERT-PAQ-001",
            defaults={
                "proxima_calibracao": hoje + timedelta(days=40),
                "resultado": "APROVADO",
                "responsavel": "LAB X",
                "fornecedor": "LAB X",
                "erro_encontrado": 0.01,
                "incerteza": 0.01,
                "tolerancia_usada": 0.1,
            },
        )
        HistoricoCalibracao.objects.get_or_create(
            instrumento=inst2,
            data_calibracao=hoje - timedelta(days=220),
            numero_certificado="CERT-BAL-010",
            defaults={
                "proxima_calibracao": hoje - timedelta(days=10),
                "resultado": "CONDICIONAL",
                "responsavel": "LAB Y",
                "fornecedor": "LAB Y",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

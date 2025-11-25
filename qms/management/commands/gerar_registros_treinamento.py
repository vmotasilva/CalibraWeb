"""Command: python manage.py gerar_registros_treinamento

Gera registros iniciais de treinamento (RegistroTreinamento) para colaboradores.
Opcoes:
  --setor=NOME            Limita aos colaboradores de um setor (pode repetir parametro)
  --incluir-sem-pacote    Inclui colaboradores mesmo sem pacotes atribuidos (usa todos pacotes existentes)
  --dry-run               Simula sem criar nada, apenas mostra contagem

Por padrao processa somente colaboradores ativos que possuem ao menos um pacote.
"""

from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from qms.models import Colaborador, RegistroTreinamento, PacoteTreinamento


class Command(BaseCommand):
    help = "Gera registros iniciais de treinamento para colaboradores"

    def add_arguments(self, parser):
        parser.add_argument(
            "--setor",
            action="append",
            dest="setores",
            help="Nome(s) de setor a filtrar (pode usar multiplos)",
        )
        parser.add_argument(
            "--incluir-sem-pacote",
            action="store_true",
            help="Processa colaboradores mesmo sem pacotes (usa todos pacotes)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas simula e exibe contagens, nao cria registros",
        )

    def handle(self, *args, **options):
        setores = options.get("setores") or []
        incluir_sem_pacote = options.get("incluir_sem_pacote")
        dry_run = options.get("dry_run")

        qs = Colaborador.objects.filter(is_active=True)
        if setores:
            qs = qs.filter(setor__nome__in=setores)

        total_colabs = qs.count()
        if total_colabs == 0:
            self.stdout.write("Nenhum colaborador ativo encontrado com filtros fornecidos.")
            return

        pacotes_todos = list(PacoteTreinamento.objects.all())
        if not pacotes_todos:
            self.stdout.write("Nenhum pacote de treinamento cadastrado. Saindo.")
            return

        self.stdout.write(
            f"Colaboradores alvo: {total_colabs} | Pacotes existentes: {len(pacotes_todos)}"
        )
        self.stdout.write(
            "Modo: "
            + ("INCLUIR-SEM-PACOTE" if incluir_sem_pacote else "APENAS-COM-PACOTE")
            + (" (dry-run)" if dry_run else "")
        )

        total_criados = 0
        total_existentes = 0
        total_procedimentos_avaliados = 0

        # Precarrega procedimentos por pacote para eficiencia
        pacote_to_procs = {
            p.id: [proc for proc in p.procedimentos.all() if proc.aplica_treinamento]
            for p in pacotes_todos
        }

        with transaction.atomic():
            for colab in qs.iterator():
                if incluir_sem_pacote:
                    pacotes_relevantes = pacotes_todos
                else:
                    pacotes_relevantes = list(colab.pacotes_treinamento.all())
                if not pacotes_relevantes:
                    continue

                procedimentos_set = set()
                for p in pacotes_relevantes:
                    for proc in pacote_to_procs[p.id]:
                        procedimentos_set.add(proc)

                for proc in procedimentos_set:
                    total_procedimentos_avaliados += 1
                    if dry_run:
                        # Apenas conta, nao cria
                        if RegistroTreinamento.objects.filter(
                            colaborador=colab, procedimento=proc
                        ).exists():
                            total_existentes += 1
                        else:
                            total_criados += 1
                        continue
                    obj, created = RegistroTreinamento.objects.get_or_create(
                        colaborador=colab,
                        procedimento=proc,
                        defaults={
                            "revisao_treinada": "PENDENTE",
                            "data_treinamento": date.today(),
                        },
                    )
                    if created:
                        total_criados += 1
                    else:
                        total_existentes += 1

        self.stdout.write("\n==== RESUMO ====")
        self.stdout.write(f"Procedimentos avaliados (colab x proc): {total_procedimentos_avaliados}")
        self.stdout.write(f"Registros que ja existiam: {total_existentes}")
        self.stdout.write(
            ("Registros que seriam criados" if dry_run else "Registros criados")
            + f": {total_criados}"
        )
        self.stdout.write("Concluido.")

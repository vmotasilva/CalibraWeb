from datetime import date

from django.core.management.base import BaseCommand

from rh.models import Colaborador
from procedures.models import RegistroTreinamento


class Command(BaseCommand):
    help = (
        "Recria registros de treinamento (RegistroTreinamento) a partir dos pacotes de treinamento associados aos colaboradores."
    )

    def handle(self, *args, **options):
        total_created = 0
        total_existing = 0

        colaboradores = Colaborador.objects.prefetch_related(
            "pacotes_treinamento__procedimentos"
        ).all()

        for colaborador in colaboradores:
            pacotes = colaborador.pacotes_treinamento.all()
            for pacote in pacotes:
                for proc in pacote.procedimentos.all():
                    if not getattr(proc, "aplica_treinamento", False):
                        continue
                    obj, created = RegistroTreinamento.objects.get_or_create(
                        colaborador=colaborador,
                        procedimento=proc,
                        defaults={
                            "revisao_treinada": "PENDENTE",
                            "data_treinamento": date.today(),
                        },
                    )
                    if created:
                        total_created += 1
                    else:
                        total_existing += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processo concluído. Criados: {total_created}. Já existentes: {total_existing}."
            )
        )
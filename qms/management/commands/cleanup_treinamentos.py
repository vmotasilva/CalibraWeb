from django.core.management.base import BaseCommand

from qms.models import Colaborador, RegistroTreinamento


class Command(BaseCommand):
    help = (
        "Remove registros de treinamento órfãos ou de procedimentos que não exigem treinamento."
    )

    def handle(self, *args, **options):
        removidos = 0

        # Conjunto permitido: (colaborador_id, procedimento_id) a partir dos pacotes atuais e que aplicam treinamento
        allowed_pairs = set()
        for colaborador in Colaborador.objects.prefetch_related(
            "pacotes_treinamento__procedimentos"
        ):
            for pacote in colaborador.pacotes_treinamento.all():
                for proc in pacote.procedimentos.all():
                    if getattr(proc, "aplica_treinamento", False):
                        allowed_pairs.add((colaborador.id, proc.id))

        # Itera todos registros e remove os não permitidos
        for registro in RegistroTreinamento.objects.select_related("colaborador", "procedimento"):
            if not getattr(registro.procedimento, "aplica_treinamento", False):
                registro.delete()
                removidos += 1
                continue
            key = (registro.colaborador_id, registro.procedimento_id)
            if key not in allowed_pairs:
                registro.delete()
                removidos += 1

        self.stdout.write(self.style.WARNING(f"Registros removidos: {removidos}"))
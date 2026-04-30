from django.core.management.base import BaseCommand

from procedures.models import RegistroTreinamento


class Command(BaseCommand):
    help = (
        "Sincroniza revisao_treinada com a revisao_atual do procedimento para procedimentos que aplicam treinamento."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra quantos registros seriam atualizados sem aplicar mudanças.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run")
        to_update = []

        # Seleciona todos registros com procedimento aplicando treinamento onde revisao difere
        for reg in RegistroTreinamento.objects.select_related("procedimento"):
            proc = reg.procedimento
            if not getattr(proc, "aplica_treinamento", False):
                continue
            if str(reg.revisao_treinada).strip() != str(proc.revisao_atual).strip():
                to_update.append(reg)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: {len(to_update)} registro(s) seriam atualizados."
                )
            )
            return

        for reg in to_update:
            reg.revisao_treinada = reg.procedimento.revisao_atual.strip()
            reg.save(update_fields=["revisao_treinada"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronização concluída. Registros atualizados: {len(to_update)}"
            )
        )
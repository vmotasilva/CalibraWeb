from django.core.management.base import BaseCommand
from django.db import transaction
from dateutil.relativedelta import relativedelta

from metrologia.models import HistoricoCalibracao, Instrumento


class Command(BaseCommand):
    help = (
        "Recalculate HistoricoCalibracao.proxima_calibracao from data_calibracao + "
        "Instrumento.frequencia_meses and sync Instrumento dates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--recalc",
            action="store_true",
            help="Recompute proxima_calibracao even if already set.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write changes, only report what would change.",
        )

    def handle(self, *args, **options):
        recalc = options.get("recalc", False)
        dry_run = options.get("dry_run", False)

        updated_hist = 0
        inspected_hist = 0
        updated_inst = 0
        missing_freq = 0

        # Pass 1: ensure all historicos have proxima_calibracao
        qs = HistoricoCalibracao.objects.select_related("instrumento").all()
        for h in qs.iterator():
            inspected_hist += 1
            inst = h.instrumento
            if not inst or not h.data_calibracao:
                continue
            freq = inst.frequencia_meses or 0
            if freq <= 0:
                missing_freq += 1
                continue
            needs = recalc or (h.proxima_calibracao is None)
            if needs:
                new_next = h.data_calibracao + relativedelta(months=+int(freq))
                if not dry_run:
                    h.proxima_calibracao = new_next
                    h.save(update_fields=["proxima_calibracao"])
                updated_hist += 1

        # Pass 2: sync each instrument's dates from latest historico
        for inst in Instrumento.objects.all().iterator():
            latest = inst.historico_calibracoes.order_by("-data_calibracao").first()
            if not latest:
                continue
            new_last = latest.data_calibracao
            new_next = latest.proxima_calibracao
            if (inst.data_ultima_calibracao != new_last) or (inst.data_proxima_calibracao != new_next):
                if not dry_run:
                    inst.data_ultima_calibracao = new_last
                    inst.data_proxima_calibracao = new_next
                    inst.save(update_fields=["data_ultima_calibracao", "data_proxima_calibracao"])
                updated_inst += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Historicos inspected={inspected_hist}, updated={updated_hist}; "
                f"Instrumentos updated={updated_inst}; missing_freq={missing_freq}."
            )
        )

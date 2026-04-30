from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction

from metrologia.models import Instrumento, FaixaMedicao


class Command(BaseCommand):
    help = (
        "Create minimal FaixaMedicao for instruments without ranges using the category's unidade_padrao. "
        "Dry-run by default; use --apply to persist."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes (without this flag only a dry-run summary is shown)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        apply = options.get("apply", False)

        qs = (
            Instrumento.objects.select_related("categoria", "categoria__unidade_padrao")
            .prefetch_related("faixas")
            .all()
        )

        candidates = []
        for inst in qs:
            if inst.faixas.all().exists():
                continue
            cat = inst.categoria
            if not cat or not getattr(cat, "unidade_padrao", None):
                continue
            candidates.append(inst)

        created = 0
        with transaction.atomic():
            for inst in candidates:
                unidade = inst.categoria.unidade_padrao
                # Minimal faixa 0..1 with the default unit; tolerances can be set later
                if apply:
                    FaixaMedicao.objects.create(
                        instrumento=inst,
                        unidade=unidade,
                        valor_minimo=0,
                        valor_maximo=1,
                    )
                    created += 1

            if not apply:
                # Rollback by raising inside atomic? Instead, simply not writing anything
                pass

        if apply:
            self.stdout.write(self.style.SUCCESS(f"Faixas criadas: {created}"))
        else:
            self.stdout.write(self.style.WARNING(f"Dry-run: candidatos={len(candidates)}; criaria {len(candidates)} faixas"))

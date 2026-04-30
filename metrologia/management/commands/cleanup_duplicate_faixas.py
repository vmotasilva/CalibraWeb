from django.core.management.base import BaseCommand
from metrologia.models import FaixaMedicao


class Command(BaseCommand):
    help = 'Remove duplicate faixas de medicao with same min/max/unit'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--instrument-id',
            type=int,
            help='Only check/fix a specific instrument ID',
        )

    def handle(self, *args, **options):
        from metrologia.models import Instrumento
        
        dry_run = options['dry_run']
        instrument_id = options.get('instrument_id')
        
        if instrument_id:
            instruments = Instrumento.objects.filter(id=instrument_id)
        else:
            instruments = Instrumento.objects.all()
        
        total_removed = 0
        
        for inst in instruments:
            faixas = inst.faixas.all().order_by('id')
            if faixas.count() < 2:
                continue
            
            # Group by (min, max, unit) and find duplicates
            seen = {}
            to_remove = []
            
            for faixa in faixas:
                key = (
                    faixa.valor_minimo,
                    faixa.valor_maximo,
                    faixa.unidade_id
                )
                
                if key in seen:
                    # This is a duplicate, mark for removal (keep the first one)
                    to_remove.append(faixa)
                else:
                    seen[key] = faixa
            
            if to_remove:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n{inst.tag}: Found {len(to_remove)} duplicate faixa(s)"
                    )
                )
                
                for faixa in to_remove:
                    self.stdout.write(
                        f"  Duplicate: {faixa.valor_minimo} - {faixa.valor_maximo} "
                        f"{faixa.unidade.nome} (ID: {faixa.id})"
                    )
                    
                    if not dry_run:
                        faixa.delete()
                        self.stdout.write(
                            self.style.SUCCESS(f"    Deleted ID {faixa.id}")
                        )
                    total_removed += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDry run: Would remove {total_removed} duplicate(s). "
                    f"Run without --dry-run to actually delete."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRemoved {total_removed} duplicate faixa(s)."
                )
            )

"""
Management command para recalcular data da próxima calibração de todos os instrumentos
baseado na frequência definida em cada categoria.
"""
from django.core.management.base import BaseCommand
from metrologia.models import HistoricoCalibracao, CategoriaInstrumento
from dateutil.relativedelta import relativedelta


class Command(BaseCommand):
    help = 'Recalcula a data da próxima calibração para todos os históricos baseado na frequência da categoria'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categoria',
            type=int,
            help='Recalcular apenas para uma categoria específica (ID)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar alterações sem salvar',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        categoria_id = options.get('categoria')

        # Get all histories or filter by category
        historicos = HistoricoCalibracao.objects.select_related('instrumento__categoria')
        
        if categoria_id:
            try:
                categoria = CategoriaInstrumento.objects.get(id=categoria_id)
                historicos = historicos.filter(instrumento__categoria=categoria)
                self.stdout.write(f"Recalculando para categoria: {categoria.nome}")
            except CategoriaInstrumento.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Categoria {categoria_id} não encontrada"))
                return

        atualizado = 0
        sem_frequencia = 0

        for historico in historicos:
            if not historico.instrumento or not historico.instrumento.categoria:
                sem_frequencia += 1
                continue

            categoria = historico.instrumento.categoria
            if not categoria.frequencia_calibracao_meses:
                sem_frequencia += 1
                continue

            # Calcular próxima calibração
            meses = categoria.frequencia_calibracao_meses
            proxima = historico.data_calibracao + relativedelta(months=meses)

            if dry_run:
                self.stdout.write(
                    f"[PREVIEW] {historico.instrumento.tag}: "
                    f"Data: {historico.data_calibracao} -> "
                    f"Próxima: {proxima} "
                    f"(+{meses} meses)"
                )
            else:
                if historico.proxima_calibracao != proxima:
                    historico.proxima_calibracao = proxima
                    historico.save(update_fields=['proxima_calibracao'])
                    atualizado += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {historico.instrumento.tag}: {historico.data_calibracao} -> {proxima}"
                        )
                    )

        total = historicos.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Processados: {total} | "
                f"Atualizados: {atualizado} | "
                f"Sem frequência: {sem_frequencia}"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] Nenhuma alteração foi salva"))

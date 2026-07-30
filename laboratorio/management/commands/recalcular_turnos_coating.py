from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime

from laboratorio.models import RegistroCoating, RegraTurnoCoating, TurnoCoating


def _get_regra_para_hora(hora_entrada):
    """
    Retorna a RegraTurnoCoating correspondente à hora local do datetime fornecido.
    """
    hora_time = timezone.localtime(hora_entrada).time()
    regras = RegraTurnoCoating.objects.filter(ativo=True)

    for regra in regras:
        if regra.hora_inicio <= regra.hora_fim:
            if regra.hora_inicio <= hora_time <= regra.hora_fim:
                return regra
        else:
            # Turno que vira a meia-noite (ex: 22:00 → 06:00)
            if hora_time >= regra.hora_inicio or hora_time <= regra.hora_fim:
                return regra

    return None


class Command(BaseCommand):
    help = (
        "Recalcula e corrige o turno_coating de todos os RegistroCoating com "
        "hora_entrada preenchida, baseando-se nas regras de turno ativas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simula as alterações, sem salvar no banco.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo DRY-RUN: nenhuma alteração será salva.'))

        registros = RegistroCoating.objects.select_related(
            'turno_coating', 'turno_coating__regra'
        ).filter(hora_entrada__isnull=False)

        total = registros.count()
        self.stdout.write(f'Total de registros com hora_entrada: {total}')

        atualizados = 0
        sem_regra = 0
        sem_mudanca = 0

        for reg in registros:
            regra_encontrada = _get_regra_para_hora(reg.hora_entrada)

            if not regra_encontrada:
                sem_regra += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  [SEM REGRA] Registro pk={reg.pk} lote={reg.lote} lado={reg.lado} '
                        f'hora_entrada={timezone.localtime(reg.hora_entrada).strftime("%d/%m/%Y %H:%M")}'
                    )
                )
                continue

            data_local = timezone.localtime(reg.hora_entrada).date()
            turno_diario, _ = TurnoCoating.objects.get_or_create(
                data=data_local,
                regra=regra_encontrada,
            )

            if reg.turno_coating_id == turno_diario.pk:
                sem_mudanca += 1
                continue

            turno_anterior = str(reg.turno_coating)
            turno_novo = str(turno_diario)

            self.stdout.write(
                f'  [ATUALIZAR] pk={reg.pk} lote={reg.lote} lado={reg.lado} '
                f'{turno_anterior} → {turno_novo}'
            )

            if not dry_run:
                reg.turno_coating = turno_diario
                reg.save(update_fields=['turno_coating'])

            atualizados += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Concluído!'))
        self.stdout.write(f'  Atualizados : {atualizados}')
        self.stdout.write(f'  Já corretos : {sem_mudanca}')
        self.stdout.write(f'  Sem regra   : {sem_regra}')

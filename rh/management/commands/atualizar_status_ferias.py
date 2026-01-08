# -*- coding: utf-8 -*-
"""
Management command para atualizar status de férias manualmente
Útil para testes e atualização imediata sem aguardar Celery Beat
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
import logging

from rh.models import Ferias, Colaborador

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Atualiza automaticamente o status das férias baseado nas datas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--colaborador',
            type=int,
            help='ID do colaborador para atualizar apenas suas férias',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Exibir detalhes de cada férias processada',
        )

    def handle(self, *args, **options):
        hoje = date.today()
        atualizadas = 0
        erros = 0
        verbose = options['verbose']
        colaborador_id = options.get('colaborador')

        self.stdout.write(
            self.style.SUCCESS(f'\n📅 Atualizando férias - Data: {hoje.strftime("%d/%m/%Y")}\n')
        )

        try:
            # Buscar férias
            if colaborador_id:
                ferias_qs = Ferias.objects.filter(colaborador_id=colaborador_id)
                self.stdout.write(f'Processando férias do colaborador ID {colaborador_id}...')
            else:
                ferias_qs = Ferias.objects.all()
                self.stdout.write('Processando todas as férias...')

            total = ferias_qs.count()
            self.stdout.write(f'Total de registros: {total}\n')

            for ferias in ferias_qs:
                try:
                    status_anterior = ferias.status
                    novo_status = None

                    # Lógica de atualização de status (mesmo do modelo)
                    if ferias.data_inicio > hoje:
                        novo_status = "PLANEJADO"
                    elif ferias.data_inicio <= hoje <= ferias.data_fim:
                        novo_status = "EM_ANDAMENTO"
                    elif hoje > ferias.data_fim:
                        novo_status = "CONCLUIDO"

                    # Atualizar se houver mudança
                    if novo_status and ferias.status != novo_status:
                        ferias.status = novo_status
                        ferias.save(update_fields=['status'])
                        atualizadas += 1

                        if verbose:
                            self.stdout.write(
                                f'  ✓ {ferias.colaborador.nome_completo}: '
                                f'{status_anterior} → {novo_status} '
                                f'({ferias.data_inicio} a {ferias.data_fim})'
                            )

                        # Atualizar campo em_ferias do colaborador
                        colaborador = ferias.colaborador
                        ferias_ativas = Ferias.objects.filter(
                            colaborador=colaborador,
                            aprovada=True,
                            data_inicio__lte=hoje,
                            data_fim__gte=hoje
                        ).exists()

                        if colaborador.em_ferias != ferias_ativas:
                            colaborador.em_ferias = ferias_ativas
                            colaborador.save(update_fields=['em_ferias'])

                    elif verbose and novo_status:
                        self.stdout.write(f'  - {ferias.colaborador.nome_completo}: {novo_status} (sem mudanças)')

                except Exception as e:
                    erros += 1
                    logger.error(f'Erro ao atualizar férias {ferias.id}: {str(e)}', exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Erro na férias {ferias.id}: {str(e)}')
                    )

            # Resultado final
            self.stdout.write(f'\n📊 Resultado:')
            self.stdout.write(self.style.SUCCESS(f'  ✓ {atualizadas} férias atualizadas'))
            if erros > 0:
                self.stdout.write(self.style.ERROR(f'  ✗ {erros} erros encontrados'))

            self.stdout.write(self.style.SUCCESS('\n✅ Processo concluído!\n'))

        except Exception as e:
            logger.error(f'Erro na atualização de férias: {str(e)}', exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'\n❌ Erro: {str(e)}\n')
            )

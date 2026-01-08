#!/usr/bin/env python
"""
Django Management Command: python manage.py atualizar_revisoes_treinamento

Atualiza revisao_treinada em todos os registros de treinamento baseado na revisão atual do procedimento.
Resolve o problema onde "Vigentes" sempre mostra 0.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from training.models import RegistroTreinamento
from procedures.models import Procedimento


class Command(BaseCommand):
    help = 'Atualiza revisao_treinada nos registros de treinamento para corrigir status VIGENTE/PENDENTE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer realmente',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('ATUALIZAR REVISÕES DE TREINAMENTO'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        total_registros = RegistroTreinamento.objects.count()
        self.stdout.write(f'\nTotal de registros: {total_registros}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN MODE] Nada será alterado!\n'))
        
        # Separar problemas
        sem_revisao = []
        revisao_errada = []
        atualizados = 0
        
        for registro in RegistroTreinamento.objects.select_related('colaborador', 'procedimento').all():
            proc = registro.procedimento
            revisao_atual = str(proc.numero_revisao).strip() if hasattr(proc, 'numero_revisao') else 'ATUAL'
            revisao_registrada = str(registro.revisao_treinada).strip() if registro.revisao_treinada else ''
            
            # Problema 1: Sem revisão
            if not revisao_registrada:
                sem_revisao.append((registro, revisao_atual))
                if not dry_run:
                    registro.revisao_treinada = revisao_atual
                    registro.save(update_fields=['revisao_treinada'])
                    atualizados += 1
                    
            # Problema 2: Revisão diferente
            elif revisao_registrada != revisao_atual and revisao_registrada != 'PENDENTE':
                revisao_errada.append((registro, revisao_registrada, revisao_atual))
                if not dry_run and registro.data_treinamento:
                    registro.revisao_treinada = revisao_atual
                    registro.save(update_fields=['revisao_treinada'])
                    atualizados += 1
        
        # Mostrar problemas encontrados
        if sem_revisao:
            self.stdout.write(self.style.WARNING(f'\n[SEM REVISÃO] {len(sem_revisao)} registros:'))
            for reg, rev_atual in sem_revisao[:5]:  # Mostrar apenas 5
                self.stdout.write(f'  • {reg.colaborador.nome_completo} - {reg.procedimento.codigo}')
            if len(sem_revisao) > 5:
                self.stdout.write(f'  ... e mais {len(sem_revisao) - 5}')
        
        if revisao_errada:
            self.stdout.write(self.style.WARNING(f'\n[REVISÃO ERRADA] {len(revisao_errada)} registros:'))
            for reg, rev_errada, rev_atual in revisao_errada[:5]:  # Mostrar apenas 5
                self.stdout.write(f'  • {reg.colaborador.nome_completo} - {reg.procedimento.codigo}: {rev_errada} → {rev_atual}')
            if len(revisao_errada) > 5:
                self.stdout.write(f'  ... e mais {len(revisao_errada) - 5}')
        
        # Resumo
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('RESUMO'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Registros SEM revisão: {len(sem_revisao)}')
        self.stdout.write(f'Registros COM revisão errada: {len(revisao_errada)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Seriam atualizados: {len(sem_revisao) + len(revisao_errada)}'))
            self.stdout.write(self.style.WARNING('Execute SEM --dry-run para confirmar alterações'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Registros ATUALIZADOS: {atualizados}'))
            self.stdout.write(self.style.SUCCESS('✓ Campo "Vigentes" deve estar correto agora!'))
        
        self.stdout.write(self.style.SUCCESS('=' * 70))

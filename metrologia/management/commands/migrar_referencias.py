import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from metrologia.models import (
    Instrumento, InstrumentoReferencia, FaixaMedicao, FaixaMedicaoPadrao
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migra instrumentos existentes para usar o modelo de InstrumentoReferencia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Apenas valida sem fazer mudancas'
        )

    def handle(self, *args, **options):
        if options['validate_only']:
            self.validate_migration()
        else:
            self.migrate_instruments()
            self.validate_migration()

    def migrate_instruments(self):
        """Migra instrumentos para usar referencias"""
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('INICIANDO MIGRACAO DE INSTRUMENTOS PARA REFERENCIAS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        contador = {
            'referencias_criadas': 0,
            'instrumentos_vinculados': 0,
            'faixas_padrao_criadas': 0,
            'faixas_vinculadas': 0,
            'erros': 0
        }

        total = Instrumento.objects.count()
        self.stdout.write(f'\nTotal de instrumentos: {total}')

        try:
            with transaction.atomic():
                # Processar ativos
                self.stdout.write('\n--- PROCESSANDO INSTRUMENTOS ATIVOS ---')
                ativos = Instrumento.objects.filter(ativo=True).order_by('categoria', 'tag')
                self.stdout.write(f'Instrumentos ativos: {ativos.count()}')

                for instrumento in ativos:
                    self._processar_instrumento(instrumento, contador)

                # Processar inativos
                self.stdout.write('\n--- PROCESSANDO INSTRUMENTOS INATIVOS ---')
                inativos = Instrumento.objects.filter(ativo=False).order_by('categoria', 'tag')
                self.stdout.write(f'Instrumentos inativos: {inativos.count()}')

                for instrumento in inativos:
                    self._processar_instrumento(instrumento, contador)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nERRO CRITICO: {str(e)}'))
            raise

        # Resumo
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('RESUMO DA MIGRACAO'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Referencias criadas: {contador["referencias_criadas"]}')
        self.stdout.write(f'Instrumentos vinculados: {contador["instrumentos_vinculados"]}')
        self.stdout.write(f'Templates de faixa criados: {contador["faixas_padrao_criadas"]}')
        self.stdout.write(f'Faixas vinculadas: {contador["faixas_vinculadas"]}')
        self.stdout.write(f'Erros: {contador["erros"]}')

        if contador['erros'] == 0:
            self.stdout.write(self.style.SUCCESS('\nMigracao concluida com SUCESSO!'))
        else:
            self.stdout.write(self.style.WARNING(f'\nMigracao com {contador["erros"]} erro(s)'))

    def _processar_instrumento(self, instrumento, contador):
        """Processa um instrumento individual"""
        try:
            if instrumento.referencia:
                self.stdout.write(f'  {instrumento.tag}: ja tem referencia')
                return

            # Extrair o prefixo do tag para usar como base da referencia
            # Exemplo: LE-02 -> LE (Lensometro)
            prefixo = instrumento.tag.split('-')[0] if '-' in instrumento.tag else instrumento.tag[:2]
            
            # Tentar obter categoria, se nao tiver usar uma categoria generica
            categoria = instrumento.categoria
            if not categoria:
                # Criar ou obter categoria generica baseada no prefixo
                from metrologia.models import CategoriaInstrumento
                categoria, _ = CategoriaInstrumento.objects.get_or_create(
                    nome=f"Categoria {prefixo}"
                )
                instrumento.categoria = categoria
                instrumento.save()
                self.stdout.write(f'  {instrumento.tag}: categoria criada ({categoria.nome})')

            # Criar ou obter referencia
            codigo_ref = f"{prefixo}-{instrumento.tag}"
            
            referencia, criada = InstrumentoReferencia.objects.get_or_create(
                codigo_referencia=codigo_ref,
                defaults={
                    'categoria': categoria,
                    'descricao': f"Referencia para {instrumento.descricao}"
                }
            )

            if criada:
                self.stdout.write(f'  {instrumento.tag}: referencia criada ({codigo_ref})')
                contador['referencias_criadas'] += 1
            else:
                self.stdout.write(f'  {instrumento.tag}: referencia existente ({codigo_ref})')

            # Vincular instrumento
            instrumento.referencia = referencia
            instrumento.save()
            contador['instrumentos_vinculados'] += 1

            # Processar faixas
            faixas = FaixaMedicao.objects.filter(instrumento=instrumento)
            for faixa in faixas:
                faixa_padrao, created = FaixaMedicaoPadrao.objects.get_or_create(
                    referencia_instrumento=referencia,
                    unidade=faixa.unidade,
                    valor_minimo=faixa.valor_minimo,
                    valor_maximo=faixa.valor_maximo,
                    defaults={
                        'resolucao': faixa.resolucao,
                        'nominal': faixa.nominal,
                        'tolerancia_mais_menos': faixa.tolerancia_mais_menos,
                        'ativa': True
                    }
                )

                if created:
                    contador['faixas_padrao_criadas'] += 1

                if not faixa.faixa_padrao:
                    faixa.faixa_padrao = faixa_padrao
                    faixa.save()
                    contador['faixas_vinculadas'] += 1

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  {instrumento.tag}: ERRO - {str(e)}'))
            contador['erros'] += 1

    def validate_migration(self):
        """Valida a migracao"""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('VALIDANDO MIGRACAO'))
        self.stdout.write('=' * 80)

        total = Instrumento.objects.count()
        com_ref = Instrumento.objects.filter(referencia__isnull=False).count()
        sem_ref = Instrumento.objects.filter(referencia__isnull=True).count()
        total_ref = InstrumentoReferencia.objects.count()

        self.stdout.write(f'Total de instrumentos: {total}')
        self.stdout.write(f'Com referencia: {com_ref}')
        self.stdout.write(f'Sem referencia: {sem_ref}')
        self.stdout.write(f'Total de referencias: {total_ref}')

        cobertura = (com_ref / total * 100) if total > 0 else 0
        self.stdout.write(f'Cobertura: {cobertura:.1f}%')

        if sem_ref == 0:
            self.stdout.write(self.style.SUCCESS('\nVALIDACAO OK: Todos os instrumentos tem referencia!'))
        else:
            self.stdout.write(self.style.WARNING(f'\nVALIDACAO INCOMPLETA: {sem_ref} instrumento(s) sem referencia'))

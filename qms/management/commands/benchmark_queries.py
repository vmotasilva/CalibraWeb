# qms/management/commands/benchmark_queries.py
# Benchmark script para comparar performance de queries - Fase 6 Task #2

import time
from django.core.management.base import BaseCommand
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext
from django.conf import settings
from qms.models_legacy import Instrumento
from qms.utils.query_optimizer import InstrumentoQueryOptimizer


class Command(BaseCommand):
    help = 'Benchmark queries para validar otimizações'

    def add_arguments(self, parser):
        parser.add_argument(
            '--operation',
            type=str,
            default='all',
            choices=['all', 'listar', 'detalhe', 'filtros', 'exportacao'],
            help='Qual operação fazer benchmark'
        )

    def handle(self, *args, **options):
        operation = options['operation']
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('🔍 QUERY PERFORMANCE BENCHMARK - Fase 6 Task #2'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        if operation in ['all', 'listar']:
            self.benchmark_listar()
        
        if operation in ['all', 'detalhe']:
            self.benchmark_detalhe()
        
        if operation in ['all', 'filtros']:
            self.benchmark_filtros()
        
        if operation in ['all', 'exportacao']:
            self.benchmark_exportacao()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Benchmark Concluído'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def benchmark_listar(self):
        """Benchmark: Listar todos os instrumentos"""
        self.stdout.write(self.style.HTTP_INFO('\n📋 Teste 1: Listar Instrumentos'))
        self.stdout.write('-' * 70)
        
        # ANTES (sem otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_antes:
            instrumentos = Instrumento.objects.filter(ativo=True)
            for instr in instrumentos:
                _ = instr.categoria
                _ = instr.setor
                _ = instr.responsavel
        
        # DEPOIS (com otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_depois:
            instrumentos = InstrumentoQueryOptimizer.listar_basico().filter(ativo=True)
            for instr in instrumentos:
                _ = instr.categoria
                _ = instr.setor
                _ = instr.responsavel
        
        self._print_benchmark(ctx_antes, ctx_depois, 'Listar Instrumentos')

    def benchmark_detalhe(self):
        """Benchmark: Detalhe de um instrumento"""
        self.stdout.write(self.style.HTTP_INFO('\n📄 Teste 2: Detalhe de Instrumento'))
        self.stdout.write('-' * 70)
        
        # Obter um instrumento para teste
        try:
            instrumento_id = Instrumento.objects.filter(ativo=True).first().id
        except:
            self.stdout.write(self.style.WARNING('⚠️  Sem instrumentos para testar'))
            return
        
        # ANTES (sem otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_antes:
            instr = Instrumento.objects.get(id=instrumento_id)
            _ = instr.categoria.nome
            _ = instr.setor.nome
            _ = list(instr.historicos.all())
            _ = list(instr.faixas.all())
        
        # DEPOIS (com otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_depois:
            instr = (InstrumentoQueryOptimizer.listar_completo()
                .get(id=instrumento_id)
            )
            _ = instr.categoria.nome
            _ = instr.setor.nome
            _ = list(instr.historicos.all())
            _ = list(instr.faixas.all())
        
        self._print_benchmark(ctx_antes, ctx_depois, 'Detalhe Instrumento')

    def benchmark_filtros(self):
        """Benchmark: Filtros complexos"""
        self.stdout.write(self.style.HTTP_INFO('\n🔎 Teste 3: Filtros Complexos'))
        self.stdout.write('-' * 70)
        
        filtros = {
            'ativo': True,
            'vencidos': True,
        }
        
        # ANTES (sem otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_antes:
            from datetime import date
            instrumentos = Instrumento.objects.filter(
                ativo=True,
                data_proxima_calibracao__lte=date.today()
            )
            for instr in instrumentos:
                _ = instr.categoria.nome
                _ = instr.setor.nome
        
        # DEPOIS (com otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_depois:
            instrumentos = InstrumentoQueryOptimizer.por_filtros(filtros)
            for instr in instrumentos:
                _ = instr.categoria.nome
                _ = instr.setor.nome
        
        self._print_benchmark(ctx_antes, ctx_depois, 'Filtros Complexos')

    def benchmark_exportacao(self):
        """Benchmark: Exportação de dados"""
        self.stdout.write(self.style.HTTP_INFO('\n📊 Teste 4: Exportação de Dados'))
        self.stdout.write('-' * 70)
        
        # ANTES (sem otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_antes:
            instrumentos = Instrumento.objects.filter(ativo=True)
            dados = []
            for instr in instrumentos:
                dados.append({
                    'tag': instr.tag,
                    'categoria': instr.categoria.nome,
                    'setor': instr.setor.nome,
                    'ultima_calibracao': instr.historicos.first().data_calibracao if instr.historicos.exists() else None,
                })
        
        # DEPOIS (com otimização)
        reset_queries()
        with CaptureQueriesContext(connection) as ctx_depois:
            instrumentos = InstrumentoQueryOptimizer.para_exportacao().filter(ativo=True)
            dados = []
            for instr in instrumentos:
                dados.append({
                    'tag': instr.tag,
                    'categoria': instr.categoria.nome,
                    'setor': instr.setor.nome,
                    'ultima_calibracao': instr.historicos.first().data_calibracao if instr.historicos.exists() else None,
                })
        
        self._print_benchmark(ctx_antes, ctx_depois, 'Exportação')

    def _print_benchmark(self, ctx_antes, ctx_depois, operacao):
        """Imprime resultado do benchmark de forma formatada."""
        
        queries_antes = len(ctx_antes.captured_queries)
        queries_depois = len(ctx_depois.captured_queries)
        
        if queries_depois > 0:
            melhoria = queries_antes / queries_depois
        else:
            melhoria = float('inf')
        
        # Cor baseada na melhoria
        if melhoria >= 10:
            color = self.style.SUCCESS
            emoji = '⚡⚡⚡'
        elif melhoria >= 5:
            color = self.style.SUCCESS
            emoji = '⚡⚡'
        elif melhoria >= 2:
            color = self.style.SUCCESS
            emoji = '⚡'
        else:
            color = self.style.WARNING
            emoji = '→'
        
        self.stdout.write(f"\n{operacao}:")
        self.stdout.write(f"  ❌ ANTES:  {queries_antes:3d} queries {emoji}")
        self.stdout.write(color(f"  ✅ DEPOIS: {queries_depois:3d} queries"))
        
        if melhoria != float('inf'):
            self.stdout.write(color(f"  🎯 Melhoria: {melhoria:.1f}x"))
        
        # Mostrar as primeiras queries
        if queries_depois > 0:
            self.stdout.write(f"\n  Top queries DEPOIS:")
            for i, q in enumerate(ctx_depois.captured_queries[:3], 1):
                sql = q['sql'][:70].strip()
                if len(q['sql']) > 70:
                    sql += "..."
                self.stdout.write(f"    {i}. {sql}")


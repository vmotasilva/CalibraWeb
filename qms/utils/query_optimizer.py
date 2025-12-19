# qms/utils/query_optimizer.py
# Query optimization utilities - Fase 6 Task #2

from django.db.models import Prefetch, Q
from qms.models import Instrumento, HistoricoCalibracao, CategoriaInstrumento


class InstrumentoQueryOptimizer:
    """Otimiza queries de Instrumento com eager loading automático."""
    
    @staticmethod
    def listar_completo():
        """
        Retorna queryset otimizado para listagem completa.
        
        Eager loads:
        - categoria (FK)
        - setor (FK)
        - responsavel (FK)
        - historicos (Reverse FK)
        - faixas (Reverse FK)
        
        Melhoria: 1 + (N*5) queries → 5 queries
        """
        return (Instrumento.objects
            .select_related('categoria', 'setor', 'responsavel')
            .prefetch_related('historicos', 'faixas')
            .order_by('tag')
        )
    
    @staticmethod
    def listar_basico():
        """
        Retorna queryset otimizado apenas com FKs diretas.
        Menor overhead para listagens simples.
        
        Eager loads:
        - categoria (FK)
        - setor (FK)
        - responsavel (FK)
        
        Melhoria: 1 + (N*3) queries → 4 queries
        """
        return (Instrumento.objects
            .select_related('categoria', 'setor', 'responsavel')
            .order_by('tag')
        )
    
    @staticmethod
    def por_filtros(filtros_dict=None, eager_load=True):
        """
        Aplica filtros dinamicamente em query otimizada.
        
        Args:
            filtros_dict: Dict com filtros {'categoria': id, 'setor': id, ...}
            eager_load: Se False, não carrega related (mais rápido para contagem)
        
        Returns:
            QuerySet otimizado com filtros aplicados
        """
        if eager_load:
            qs = InstrumentoQueryOptimizer.listar_completo()
        else:
            qs = Instrumento.objects.only('id', 'tag', 'descricao')
        
        if not filtros_dict:
            return qs
        
        # Aplicar filtros
        if filtros_dict.get('categoria'):
            qs = qs.filter(categoria_id=filtros_dict['categoria'])
        
        if filtros_dict.get('setor'):
            qs = qs.filter(setor_id=filtros_dict['setor'])
        
        if filtros_dict.get('ativo') is not None:
            qs = qs.filter(ativo=filtros_dict['ativo'])
        
        if filtros_dict.get('responsavel'):
            qs = qs.filter(responsavel_id=filtros_dict['responsavel'])
        
        if filtros_dict.get('vencidos'):
            from datetime import date
            qs = qs.filter(
                data_proxima_calibracao__lte=date.today(),
                ativo=True
            )
        
        if filtros_dict.get('busca'):
            busca = filtros_dict['busca']
            qs = qs.filter(
                Q(tag__icontains=busca) |
                Q(descricao__icontains=busca) |
                Q(serie__icontains=busca)
            )
        
        return qs
    
    @staticmethod
    def para_exportacao():
        """
        Otimizado especificamente para exportação.
        Includes relacionamentos necessários, exclui dados extras.
        """
        return (Instrumento.objects
            .select_related('categoria', 'setor', 'responsavel')
            .prefetch_related(
                Prefetch(
                    'historicos',
                    HistoricoCalibracao.objects.order_by('-data_calibracao')
                )
            )
        )
    
    @staticmethod
    def com_ultima_calibracao():
        """
        Retorna instrumento com last histórico prefetched.
        Útil para mostrar data da última calibração.
        """
        historicos_prefetch = Prefetch(
            'historicos',
            HistoricoCalibracao.objects.order_by('-data_calibracao')[:1]
        )
        
        return (Instrumento.objects
            .select_related('categoria', 'setor', 'responsavel')
            .prefetch_related(historicos_prefetch)
        )
    
    @staticmethod
    def apenas_campos_necessarios(campos):
        """
        Retorna apenas campos especificados (para listagens compactas).
        
        Args:
            campos: List de nomes de campos
        
        Exemplo:
            InstrumentoQueryOptimizer.apenas_campos_necessarios([
                'id', 'tag', 'descricao', 'categoria__nome'
            ])
        """
        return Instrumento.objects.only(*campos)


class HistoricoCalibraoQueryOptimizer:
    """Otimiza queries de HistoricoCalibracao."""
    
    @staticmethod
    def listar_completo():
        """
        Lista históricos com todas as relacionamentos.
        """
        return (HistoricoCalibracao.objects
            .select_related('instrumento', 'instrumento__categoria')
            .prefetch_related('padroes_arquivo')
            .order_by('-data_calibracao')
        )
    
    @staticmethod
    def por_instrumento(instrumento_id):
        """
        Históricos de um instrumento específico.
        """
        return (HistoricoCalibracao.objects
            .filter(instrumento_id=instrumento_id)
            .select_related('instrumento')
            .prefetch_related('padroes_arquivo')
            .order_by('-data_calibracao')
        )
    
    @staticmethod
    def vencidos():
        """
        Históricos vencidos (próxima calibração <= hoje).
        """
        from datetime import date
        return (HistoricoCalibracao.objects
            .filter(
                proxima_calibracao__lte=date.today(),
                instrumento__ativo=True
            )
            .select_related('instrumento', 'instrumento__categoria', 'instrumento__setor')
            .order_by('proxima_calibracao')
        )


class EstatisticasQueryOptimizer:
    """Otimiza queries para estatísticas e relatórios."""
    
    @staticmethod
    def resumo_por_categoria():
        """
        Retorna estatísticas agregadas por categoria.
        Usa values() para performance máxima.
        """
        from django.db.models import Count, Q
        from datetime import date
        
        return (CategoriaInstrumento.objects
            .values('id', 'nome')
            .annotate(
                total=Count('instrumento', filter=Q(instrumento__ativo=True)),
                vencidos=Count(
                    'instrumento',
                    filter=Q(
                        instrumento__ativo=True,
                        instrumento__data_proxima_calibracao__lte=date.today()
                    )
                ),
                proximos_30=Count(
                    'instrumento',
                    filter=Q(
                        instrumento__ativo=True,
                        instrumento__data_proxima_calibracao__lte=date.today() + timedelta(days=30),
                        instrumento__data_proxima_calibracao__gt=date.today()
                    )
                )
            )
            .order_by('nome')
        )
    
    @staticmethod
    def resumo_por_setor():
        """
        Retorna estatísticas agregadas por setor.
        """
        from django.db.models import Count, Q
        from datetime import date, timedelta
        
        return (Setor.objects
            .filter(instrumento__ativo=True)
            .values('id', 'nome')
            .annotate(
                total=Count('instrumento', distinct=True),
                vencidos=Count(
                    'instrumento',
                    filter=Q(instrumento__data_proxima_calibracao__lte=date.today()),
                    distinct=True
                ),
                proximos_30=Count(
                    'instrumento',
                    filter=Q(
                        instrumento__data_proxima_calibracao__lte=date.today() + timedelta(days=30),
                        instrumento__data_proxima_calibracao__gt=date.today()
                    ),
                    distinct=True
                )
            )
            .order_by('nome')
        )


# ============================================================================
# Context Managers para Debug
# ============================================================================

class QueryCounterContext:
    """
    Context manager para contar e mostrar queries executadas.
    
    Uso:
        with QueryCounterContext("Minha operação"):
            # Seu código aqui
            pass
    """
    def __init__(self, operation_name="Query Operation"):
        self.operation_name = operation_name
        self.query_count = 0
        self.start_time = None
    
    def __enter__(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        self.ctx = CaptureQueriesContext(connection)
        self.ctx.__enter__()
        return self
    
    def __exit__(self, *args):
        self.query_count = len(self.ctx.captured_queries)
        self.ctx.__exit__(*args)
        
        print(f"\n[QUERY COUNT] {self.operation_name}")
        print(f"  Total queries: {self.query_count}")
        
        if self.query_count > 0:
            for i, q in enumerate(self.ctx.captured_queries[:5], 1):
                sql = q['sql'][:80] + "..." if len(q['sql']) > 80 else q['sql']
                print(f"  {i}. {sql}")
            if len(self.ctx.captured_queries) > 5:
                print(f"  ... and {len(self.ctx.captured_queries) - 5} more")


# ============================================================================
# Importações necessárias (descomente conforme necessário)
# ============================================================================

from datetime import timedelta
from qms.models import Setor

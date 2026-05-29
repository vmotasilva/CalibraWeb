"""
Serviço para consultar ações corretivas/preventivas no Appwrite Database.
"""
from core.appwrite_client import db, APPWRITE_DATABASE_ID
from appwrite.input_file import InputFile
from appwrite.query import Query
from django.conf import settings

def buscar_acoes_appwrite(filtros=None):
    """
    Busca ações na collection 'acoes' do Appwrite, aplicando filtros se fornecidos.
    filtros: dict com possíveis chaves (tipo_solucao, origem, responsavel_id, status, ano, busca)
    """
    import sys
    appwrite_mods = {k: str(v) for k, v in sys.modules.items() if 'appwrite' in k}
    requests_mods = {k: str(v) for k, v in sys.modules.items() if 'requests' in k}
    
    has_patched = "N/A"
    try:
        import appwrite.client
        has_patched = str(getattr(appwrite.client.requests, 'request', None))
    except Exception as e:
        has_patched = f"Err: {e}"
        
    debug_info = {
        'sys.path': sys.path,
        'appwrite_mods': appwrite_mods,
        'requests_mods': requests_mods,
        'has_patched': has_patched,
    }
    raise Exception(f"DEBUG_VERCEL_ENV: {debug_info}")
    if getattr(settings, 'TESTING', False) or not (APPWRITE_ENDPOINT and APPWRITE_PROJECT and APPWRITE_API_KEY):
        from acoes.models import AcaoCorretiva
        from django.db.models import Q
        from django.utils import timezone

        # 1. Atualizar status dinamicamente no banco SQLite de teste local
        hoje = timezone.localdate()
        AcaoCorretiva.objects.filter(data_conclusao__isnull=False).exclude(
            status='concluida'
        ).update(status='concluida')
        
        AcaoCorretiva.objects.exclude(
            Q(status='concluida') | Q(status='cancelada') | Q(status='atrasada')
        ).filter(
            data_vencimento__lt=hoje
        ).update(status='atrasada')

        # 2. Consultar registros locais
        qs = AcaoCorretiva.objects.all()

        # 3. Aplicar filtros
        if filtros:
            if filtros.get('tipo_solucao'):
                qs = qs.filter(tipo_solucao__iexact=filtros['tipo_solucao'])
            if filtros.get('origem'):
                qs = qs.filter(origem__iexact=filtros['origem'])
            if filtros.get('responsavel_id'):
                qs = qs.filter(responsavel_id=filtros['responsavel_id'])
            if filtros.get('status'):
                status_val = filtros['status']
                if status_val == 'em_progresso':
                    qs = qs.filter(Q(status='em_progresso') | Q(status='em andamento') | Q(status='em_andamento'))
                elif status_val == 'concluida':
                    qs = qs.filter(Q(status='concluida') | Q(status='concluido'))
                elif status_val == 'cancelada':
                    qs = qs.filter(Q(status='cancelada') | Q(status='cancelado'))
                else:
                    qs = qs.filter(status=status_val)
            if filtros.get('ano'):
                qs = qs.filter(ano=int(filtros['ano']))
            if filtros.get('busca'):
                busca = filtros['busca']
                qs = qs.filter(Q(numero_registro__icontains=busca) | Q(descricao__icontains=busca))

        # 4. Mapear para dicionários de mock compatíveis com dot access e subscript access
        class AppwriteMockDoc(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.__dict__ = self

        docs = []
        for acao in qs:
            doc = AppwriteMockDoc({
                '$id': f"django_{acao.id}",
                'numero_registro': acao.numero_registro or '',
                'ano': acao.ano or 0,
                'unidade': acao.unidade or '',
                'titulo': acao.titulo or '',
                'descricao': acao.descricao or '',
                'tipo': acao.tipo or 'corretiva',
                'tipo_solucao': acao.tipo_solucao or '',
                'prioridade': acao.prioridade or 'media',
                'origem': acao.origem or '',
                'causa_raiz': acao.causa_raiz or '',
                'status': acao.status or 'aberta',
                'data_abertura': str(acao.data_abertura) if acao.data_abertura else '',
                'data_vencimento': str(acao.data_vencimento) if acao.data_vencimento else '',
                'data_conclusao': str(acao.data_conclusao) if acao.data_conclusao else '',
                'criado_por': acao.criado_por.nome_completo if acao.criado_por else '',
                'responsavel': acao.responsavel.nome_completo if acao.responsavel else '',
                'responsavel_id': str(acao.responsavel.id) if acao.responsavel else '',
                'acoes_status_resumo': '',
            })
            docs.append(doc)
        return docs

    queries = []
    if filtros:
        if filtros.get('tipo_solucao'):
            queries.append(Query.equal('tipo_solucao', [filtros['tipo_solucao']]))
        if filtros.get('origem'):
            queries.append(Query.equal('origem', [filtros['origem']]))
        if filtros.get('responsavel_id'):
            queries.append(Query.equal('responsavel_id', [filtros['responsavel_id']]))
        if filtros.get('status'):
            queries.append(Query.equal('status', [filtros['status']]))
        if filtros.get('ano'):
            queries.append(Query.equal('ano', [int(filtros['ano'])]))
        if filtros.get('busca'):
            # Busca simples em numero_registro ou descricao
            busca = filtros['busca']
            queries.append(Query.or_(
                [Query.search('numero_registro', busca), Query.search('descricao', busca)]
            ))
    result = db.list_documents(
        database_id=APPWRITE_DATABASE_ID,
        collection_id='acoes',
        queries=queries
    )
    if hasattr(result, 'to_dict'):
        return result.to_dict().get('documents', [])
    return result.get('documents', [])

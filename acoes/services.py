"""
Serviços de consulta para ações corretivas e preventivas.
"""


def buscar_acoes(filtros=None):
    from acoes.models import AcaoCorretiva
    from django.db.models import Q
    from django.utils import timezone

    hoje = timezone.localdate()
    AcaoCorretiva.objects.filter(data_conclusao__isnull=False).exclude(
        status='concluida'
    ).update(status='concluida')

    AcaoCorretiva.objects.exclude(
        Q(status='concluida') | Q(status='cancelada') | Q(status='atrasada')
    ).filter(
        data_vencimento__lt=hoje
    ).update(status='atrasada')

    qs = AcaoCorretiva.objects.all()

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

    class AcaoDoc(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__dict__ = self

    docs = []
    for acao in qs:
        doc = AcaoDoc({
            '$id': f"django_{acao.id}",
            'id': acao.id,
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
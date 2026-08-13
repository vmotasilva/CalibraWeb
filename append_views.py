from django.core.signing import Signer, BadSignature

def public_calendar_view(request, token):
    signer = Signer()
    try:
        board_id = signer.unsign(token)
    except BadSignature:
        from django.http import Http404
        raise Http404("Link de calendário público inválido ou expirado.")

    board = get_object_or_404(
        Board.objects.exclude(nome="Ações Corretivas e Preventivas"), 
        id=board_id
    )
    
    todas_colunas = list(board.colunas.prefetch_related('subsecoes', 'cartoes__responsaveis', 'cartoes__etiquetas', 'cartoes__planejamentos').all())
    colunas = [col for col in todas_colunas if not col.arquivada]
    
    today = timezone.now().date()
    
    for col in colunas:
        col.subsecoes_list = list(col.subsecoes.all())
        col.cartoes_list = [c for c in col.cartoes.all()]
        
    context = {
        'board': board,
        'colunas': colunas,
        'hoje': today,
        'titulo': f"Calendário: {board.nome}",
        'base_template': 'base_public_calendar.html',
        'is_public': True,
    }
    return render(request, 'boards/board_detail.html', context)

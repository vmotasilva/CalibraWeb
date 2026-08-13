import os

views_path = r'boards\views.py'
with open(views_path, 'r', encoding='utf-8') as f:
    views_content = f.read()

# Add public_calendar_view at the end
public_calendar_func = """
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
"""

if 'def public_calendar_view' not in views_content:
    views_content += "\n" + public_calendar_func

# Modify board_detail_view to pass public_calendar_url
views_target = """    focus_column = None
    if focus_column_id:
        focus_column = get_object_or_404(BoardColumn, id=focus_column_id, quadro_id=board.id)

    context = {"""

views_replacement = """    focus_column = None
    if focus_column_id:
        focus_column = get_object_or_404(BoardColumn, id=focus_column_id, quadro_id=board.id)

    signer = Signer()
    public_token = signer.sign(str(board.id))
    public_calendar_url = request.build_absolute_uri(reverse('boards:public_calendar', args=[public_token]))

    context = {
        'public_calendar_url': public_calendar_url,"""
        
views_content = views_content.replace(views_target, views_replacement)

# Add Signer import if missing
if 'from django.core.signing import Signer' not in views_content:
    views_content = views_content.replace('from django.urls import reverse', 'from django.urls import reverse\\nfrom django.core.signing import Signer, BadSignature')


with open(views_path, 'w', encoding='utf-8') as f:
    f.write(views_content)


html_path = r'boards\templates\boards\board_detail.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Replace extends
html_content = html_content.replace('{% extends "base.html" %}', '{% extends base_template|default:"base.html" %}')

# Inject public logic at start of content block
public_logic = """{% block content %}
{% if is_public %}
<style>
    #boardTabs,
    #board-view, #metrics-view, #activities-view, #table-view,
    .btn-outline-info[title="Compartilhar calendário"] {
        display: none !important;
    }
    #calendar-view {
        display: block !important;
        opacity: 1 !important;
        visibility: visible !important;
        height: auto !important;
    }
    .add-task-btn { display: none !important; }
</style>
<script>
    window.addEventListener('DOMContentLoaded', function() {
        window.openAddCardModal = function() {};
        window.openCardDetailModal = function() {};
        // Desativar ponteiro de cursor
        const style = document.createElement('style');
        style.innerHTML = '.custom-calendar-event-item, .custom-calendar-day, .custom-calendar-week-slot-cell { cursor: default !important; pointer-events: none !important; }';
        const bView = document.getElementById('board-view'); if(bView) { bView.classList.remove('show', 'active'); }
        const cView = document.getElementById('calendar-view'); if(cView) { cView.classList.add('show', 'active'); }
        document.head.appendChild(style);
    });
</script>
{% endif %}

<div class="container-fluid py-3">"""
html_content = html_content.replace('{% block content %}\\n\\n<div class="container-fluid py-3">', public_logic)
html_content = html_content.replace('{% block content %}\\r\\n\\r\\n<div class="container-fluid py-3">', public_logic)

# Add share button
btn_target = """                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-success btn-sm" onclick="copyCalendarImage(this)" title="Copiar como imagem para colar">"""
btn_replacement = """                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-info btn-sm" onclick="navigator.clipboard.writeText('{{ public_calendar_url }}'); alert('Link de compartilhamento copiado! Qualquer pessoa com este link poderá ver o calendário.');" title="Compartilhar calendário">
                            <i class="bi bi-share"></i> Compartilhar
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="copyCalendarImage(this)" title="Copiar como imagem para colar">"""
html_content = html_content.replace(btn_target, btn_replacement)


with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Done")

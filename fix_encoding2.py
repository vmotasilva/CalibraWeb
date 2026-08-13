import codecs

with codecs.open('boards/views.py', 'r', 'utf-8') as f:
    c = f.read()

# Add imports
if 'from django.core.signing import Signer' not in c:
    c = c.replace('from django.urls import reverse', 'from django.urls import reverse\nfrom django.core.signing import Signer, BadSignature')

# Add public_calendar_view
if 'def public_calendar_view' not in c:
    c += '\n\ndef public_calendar_view(request, token):\n    signer = Signer()\n    try:\n        board_id = signer.unsign(token)\n    except BadSignature:\n        from django.http import Http404\n        raise Http404("Link de calendário público inválido ou expirado.")\n\n    board = get_object_or_404(\n        Board.objects.exclude(nome="Ações Corretivas e Preventivas"), \n        id=board_id\n    )\n    \n    todas_colunas = list(board.colunas.prefetch_related(\'subsecoes\', \'cartoes__responsaveis\', \'cartoes__etiquetas\', \'cartoes__planejamentos\').all())\n    colunas = [col for col in todas_colunas if not col.arquivada]\n    \n    today = timezone.now().date()\n    \n    for col in colunas:\n        col.subsecoes_list = list(col.subsecoes.all())\n        col.cartoes_list = [c for c in col.cartoes.all()]\n        \n    context = {\n        \'board\': board,\n        \'colunas\': colunas,\n        \'hoje\': today,\n        \'titulo\': f"Calendário: {board.nome}",\n        \'base_template\': \'base_public_calendar.html\',\n        \'is_public\': True,\n    }\n    return render(request, \'boards/board_detail.html\', context)\n'

# Modify board_detail_view to pass the URL
target = '''    focus_column = None
    if focus_column_id:
        focus_column = get_object_or_404(BoardColumn, id=focus_column_id, quadro_id=board.id)

    context = {'''

replacement = '''    focus_column = None
    if focus_column_id:
        focus_column = get_object_or_404(BoardColumn, id=focus_column_id, quadro_id=board.id)

    from django.urls import reverse
    from django.core.signing import Signer
    signer = Signer()
    public_token = signer.sign(str(board.id))
    public_calendar_url = request.build_absolute_uri(reverse('boards:public_calendar', args=[public_token]))

    context = {
        'public_calendar_url': public_calendar_url,'''

c = c.replace(target, replacement)

with codecs.open('boards/views.py', 'w', 'utf-8') as f:
    f.write(c)


# Now fix board_detail.html
with codecs.open('boards/templates/boards/board_detail.html', 'r', 'utf-8') as f:
    h = f.read()

# Make it dynamic template
h = h.replace('{% extends "base.html" %}', '{% extends base_template|default:"base.html" %}')

# Public logic injection
logic = '''{% block content %}
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
'''

if '{% if is_public %}' not in h:
    h = h.replace('{% block content %}', logic)

# Add share button with robust `prompt`
btn_target = '''                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-success btn-sm" onclick="copyCalendarImage(this)" title="Copiar como imagem para colar">'''

btn_replacement = '''                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-outline-info btn-sm" onclick="prompt('Copie o link abaixo para compartilhar este calendário publicamente:', '{{ public_calendar_url }}');" title="Compartilhar calendário">
                            <i class="bi bi-share"></i> Compartilhar
                        </button>
                        <button class="btn btn-outline-success btn-sm" onclick="copyCalendarImage(this)" title="Copiar como imagem para colar">'''

h = h.replace(btn_target, btn_replacement)

# Aumentar altura das células (this was in commit 16d67a5, but we checked out from fe47f27 so we need to add it back)
h = h.replace('min-height: 120px;', 'min-height: 160px;')

with codecs.open('boards/templates/boards/board_detail.html', 'w', 'utf-8') as f:
    f.write(h)

print("Done")

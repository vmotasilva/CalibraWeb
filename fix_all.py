import re

# 1. Fix views.py to include periodos_filtro
with open(r'metrologia\views\views.py', 'r', encoding='utf-8') as f:
    views_content = f.read()

replacement_views = '''    categorias_filtro = CategoriaInstrumento.objects.filter(
        id__in=categorias_ids
    ).order_by(Lower("nome"))

    # Periodos filtro logic
    periodos_set = set()
    for inst in instrumentos:
        if inst.data_proxima_calibracao:
            periodos_set.add(inst.data_proxima_calibracao.strftime('%Y-%m'))
    
    periodos_filtro = []
    meses_pt = {'01':'Jan', '02':'Fev', '03':'Mar', '04':'Abr', '05':'Mai', '06':'Jun', '07':'Jul', '08':'Ago', '09':'Set', '10':'Out', '11':'Nov', '12':'Dez'}
    for p in sorted(list(periodos_set)):
        ano, mes = p.split('-')
        label = f"{meses_pt.get(mes, mes)}/{ano}"
        periodos_filtro.append({'value': p, 'label': label})

    ctx = {'''

views_content = views_content.replace('''    categorias_filtro = CategoriaInstrumento.objects.filter(
        id__in=categorias_ids
    ).order_by(Lower("nome"))

    ctx = {''', replacement_views)

views_content = views_content.replace('''        "alerta_120d": alerta_120d,
        "can_edit": True,
        "historico_form": HistoricoCalibracaoForm(),
    }''', '''        "alerta_120d": alerta_120d,
        "can_edit": True,
        "historico_form": HistoricoCalibracaoForm(),
        "periodos_filtro": periodos_filtro,
    }''')

with open(r'metrologia\views\views.py', 'w', encoding='utf-8') as f:
    f.write(views_content)


# 2. Fix dashboard.html (occurrences badge and modal)
with open(r'metrologia\templates\metrologia\dashboard.html', 'r', encoding='utf-8') as f:
    dash_content = f.read()

# Replace the multiple badges with a single clickable badge
badge_orig = '''                                {% with abertas=i.ocorrencias.all|length %}
                                    {% for oc in i.ocorrencias.all %}
                                        {% if oc.status == 'ABERTA' %}
                                            <span class="badge bg-danger ms-1" title="Ocorrência Aberta: {{ oc.get_tipo_display }}">⚠️</span>
                                        {% endif %}
                                    {% endfor %}
                                {% endwith %}'''

badge_new = '''                                {% set count_abertas = 0 %}
                                {% for oc in i.ocorrencias.all %}
                                    {% if oc.status == 'ABERTA' %}
                                        {% set count_abertas = count_abertas|add:1 %}
                                    {% endif %}
                                {% endfor %}
                                <!-- using simpler logic since we cant do var sets easily inside loops -->
                                {% with abertas=i.ocorrencias.all %}
                                    {% if abertas %}
                                        <button class="btn btn-sm btn-link p-0 text-decoration-none ms-1" 
                                                onclick="abrirModalOcorrencias('{{ i.id }}', '{{ i.tag }}')" 
                                                title="Visualizar Ocorrências">
                                            <span class="badge bg-danger">⚠️ Tem Ocorrências</span>
                                        </button>
                                        <div id="ocorrencias-data-{{ i.id }}" style="display:none;">
                                            {% for oc in abertas %}
                                                {% if oc.status == 'ABERTA' %}
                                                    <div class="border-bottom pb-2 mb-2">
                                                        <strong>{{ oc.get_tipo_display }}</strong> - {{ oc.data_ocorrencia|date:"d/m/Y" }}<br>
                                                        <small>{{ oc.descricao }}</small><br>
                                                        <form method="post" action="{% url 'metrologia:encerrar_ocorrencia' oc.id %}" style="display:inline;" onsubmit="return confirm('Tem certeza que deseja encerrar esta ocorrência?');">
                                                            {% csrf_token %}
                                                            <input type="hidden" name="next" value="/metrologia/">
                                                            <button type="submit" class="btn btn-sm btn-outline-success py-0 px-2 mt-1 rounded-pill"><i class="bi bi-check-circle"></i> Encerrar</button>
                                                        </form>
                                                    </div>
                                                {% endif %}
                                            {% endfor %}
                                        </div>
                                    {% endif %}
                                {% endwith %}'''

dash_content = dash_content.replace(badge_orig, badge_new)

# Add Modal definition before body script ends
modal_html = '''
<!-- Modal Ocorrências do Dashboard -->
<div class="modal fade" id="modalDashboardOcorrencias" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title"><i class="bi bi-exclamation-triangle"></i> Ocorrências Abertas - <span id="modalOcTag"></span></h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" id="modalOcBody">
                <!-- Content injected via JS -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fechar</button>
            </div>
        </div>
    </div>
</div>

<script>
function abrirModalOcorrencias(instrumentoId, tag) {
    document.getElementById('modalOcTag').innerText = tag;
    const content = document.getElementById('ocorrencias-data-' + instrumentoId).innerHTML;
    const body = document.getElementById('modalOcBody');
    if(content.trim() === '') {
        body.innerHTML = '<div class="alert alert-info">Todas ocorrências estão encerradas.</div>';
    } else {
        body.innerHTML = content;
    }
    const modal = new bootstrap.Modal(document.getElementById('modalDashboardOcorrencias'));
    modal.show();
}
</script>
'''
dash_content = dash_content.replace('</body>', modal_html + '\n</body>')

with open(r'metrologia\templates\metrologia\dashboard.html', 'w', encoding='utf-8') as f:
    f.write(dash_content)


# 3. Fix missing closing div in instrumento_detalhe.html
with open(r'metrologia\templates\metrologia\instrumento_detalhe.html', 'r', encoding='utf-8') as f:
    det_content = f.read()

# Add a closing div before <!-- NEW: Cotações Tab - SIMPLIFICADA -->
det_content = det_content.replace('                <!-- NEW: Cotações Tab - SIMPLIFICADA -->', '                </div> <!-- FIX: Fechando tab-pane calib -->\n\n                <!-- NEW: Cotações Tab - SIMPLIFICADA -->')

with open(r'metrologia\templates\metrologia\instrumento_detalhe.html', 'w', encoding='utf-8') as f:
    f.write(det_content)

print("All fixes applied successfully!")

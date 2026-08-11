with open(r'metrologia\templates\metrologia\dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Remove anything after {% endblock %}
endblock_pos = html.index('{% endblock %}')
html = html[:endblock_pos]

# Now build the final script + modal + endblock to inject BEFORE {% endblock %}
extra_code = """
<!-- Modal Ocorrências do Dashboard -->
<div class="modal fade" id="modalDashboardOcorrencias" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title fw-bold">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Ocorrências Abertas &mdash; <span id="modalOcTag"></span>
                </h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body p-3" id="modalOcBody">
                <!-- Content injected via JS -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Fechar</button>
            </div>
        </div>
    </div>
</div>

<script>
function abrirModalOcorrencias(instrumentoId, tag) {
    document.getElementById('modalOcTag').innerText = tag;
    var dataDiv = document.getElementById('ocorrencias-data-' + instrumentoId);
    var content = dataDiv ? dataDiv.innerHTML : '';
    var body = document.getElementById('modalOcBody');
    if (!content || content.trim() === '' || !content.includes('ABERTA')) {
        body.innerHTML = '<div class="alert alert-success mb-0"><i class="bi bi-check-circle me-2"></i>Nenhuma ocorrência aberta para este instrumento.</div>';
    } else {
        body.innerHTML = content;
    }
    var modal = new bootstrap.Modal(document.getElementById('modalDashboardOcorrencias'));
    modal.show();
}

function atualizarFiltrosDisponiveis() {
    // Coleta os filtros ativos (excluindo categoria "periodo" que é o que queremos atualizar dinamicamente)
    var termoBusca = (document.getElementById('searchInput') || {value:''}).value.toLowerCase();
    var ativos = { status: [], situacao: [], categoria: [], setor: [], resultado: [], acao: [], ocorrencia: [] };
    document.querySelectorAll('.filter-checkbox').forEach(function(cb) {
        var cat = cb.dataset.category;
        if (cb.checked && cat !== 'periodo') {
            if (ativos[cat] !== undefined) ativos[cat].push(cb.value);
        }
    });

    // Descobre quais periodos estão representados pelas linhas visíveis com os outros filtros aplicados
    var periodosValidos = new Set();
    document.querySelectorAll('.instrumento-row').forEach(function(row) {
        var mostrar = true;
        if (termoBusca && !row.dataset.nome.includes(termoBusca)) mostrar = false;
        if (mostrar && ativos.status.length > 0 && !ativos.status.includes(row.dataset.status)) mostrar = false;
        if (mostrar && ativos.situacao.length > 0 && !ativos.situacao.includes(row.dataset.situacao)) mostrar = false;
        if (mostrar && ativos.categoria.length > 0 && !ativos.categoria.includes(row.dataset.categoria)) mostrar = false;
        if (mostrar && ativos.setor.length > 0 && !ativos.setor.includes(row.dataset.setor)) mostrar = false;
        if (mostrar && ativos.resultado.length > 0 && !ativos.resultado.includes(row.dataset.resultado)) mostrar = false;
        if (mostrar && ativos.acao.length > 0 && !ativos.acao.includes(row.dataset.acao)) mostrar = false;
        if (mostrar && ativos.ocorrencia.length > 0) {
            if (ativos.ocorrencia.includes('COM_ABERTA') && !row.dataset.ocorrencia.includes('COM_ABERTA')) mostrar = false;
        }
        if (mostrar && row.dataset.periodo) periodosValidos.add(row.dataset.periodo);
    });

    // Mostra/oculta os checkboxes de periodo que não têm correspondência
    document.querySelectorAll('.filter-checkbox[data-category="periodo"]').forEach(function(cb) {
        var wrap = cb.closest('.form-check');
        if (wrap) {
            if (periodosValidos.has(cb.value)) {
                wrap.style.opacity = '1';
                wrap.style.pointerEvents = 'auto';
            } else {
                wrap.style.opacity = '0.35';
                wrap.style.pointerEvents = 'none';
                cb.checked = false;  // Desmarca automaticamente se o período não tem resultados
            }
        }
    });
}

// Patch filtrar() para chamar atualizarFiltrosDisponiveis() depois
var _filtrarOriginal = filtrar;
filtrar = function() {
    _filtrarOriginal();
    atualizarFiltrosDisponiveis();
};

document.addEventListener('DOMContentLoaded', function() {
    // Exibir botões de ocorrência apenas se houver alguma em aberto
    document.querySelectorAll('[id^="ocorrencias-data-"]').forEach(function(div) {
        if (div.innerHTML.includes('ABERTA')) {
            var id = div.id.replace('ocorrencias-data-', '');
            var btn = document.querySelector('.btn-ocorrencia-' + id);
            if (btn) btn.style.display = 'inline-block';
        }
    });
    atualizarFiltrosDisponiveis();
});
</script>

{% endblock %}"""

html += extra_code

with open(r'metrologia\templates\metrologia\dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done!")

with open(r'metrologia\templates\metrologia\dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

modal_html = """
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
"""

if "function abrirModalOcorrencias" not in html:
    html += modal_html
    with open(r'metrologia\templates\metrologia\dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Modal appended!")
else:
    print("Modal already present.")

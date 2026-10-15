/* Editor de Diagramas (DOC.071) - módulo "modelos_ui"
 * Galeria de modelos (família + variações com miniatura) no modal "Modelos": aplica layout + estilo ao diagrama.
 * O catálogo e o cálculo do tema ficam em modelos_estilo.js (puro e testado em Node).
 */

function paletaDoModeloEscolhida() {
    const select = document.getElementById('modeloPaleta');
    return DiagramaModelos.paletaPorId(select ? select.value : '');
}

// Variação em uso: mesmo layout e tema criado por ela (o nome do tema guarda a variação)
function variacaoAtualDoDiagrama() {
    const nome = topologia.tema?.nome;
    if (!nome) return null;
    for (const familia of DiagramaModelos.FAMILIAS_MODELO) {
        const v = familia.variacoes.find(x => `Modelo: ${x.nome}` === nome);
        if (v && (v.layout || familia.layout) === (topologia.layout_modo || 'raias')) return v.id;
    }
    return null;
}

function renderizarGaleriaModelos() {
    const galeria = document.getElementById('galeriaModelos');
    const select = document.getElementById('modeloPaleta');
    if (!galeria || !select) return;
    if (!select.options.length) {
        select.innerHTML = DiagramaModelos.PALETAS.map(p => `<option value="${p.id}">${escapeHtml(p.nome)}</option>`).join('');
    }
    const paleta = paletaDoModeloEscolhida();
    const atual = variacaoAtualDoDiagrama();

    galeria.innerHTML = DiagramaModelos.FAMILIAS_MODELO.map(familia => `
        <div class="mb-4">
            <div class="fw-bold text-dark">${escapeHtml(familia.nome)}</div>
            <div class="text-muted small mb-2">${escapeHtml(familia.descricao)}</div>
            <div class="row g-2">
                ${familia.variacoes.map(v => `
                    <div class="col-6 col-md-3">
                        <button type="button" class="modelo-variacao w-100 p-1 border rounded-3 bg-white text-start ${atual === v.id ? 'border-primary border-2' : ''}"
                                ${IS_APPROVED ? 'disabled' : ''} onclick="aplicarModeloDeEstilo('${v.id}')" title="Aplicar: ${escapeHtml(familia.nome)} - ${escapeHtml(v.nome)}">
                            <div class="rounded-2 overflow-hidden">${DiagramaModelos.miniatura(familia, v, paleta)}</div>
                            <div class="small fw-semibold px-1 pt-1">${escapeHtml(v.nome)}${atual === v.id ? ' <i class="bi bi-check-circle-fill text-primary"></i>' : ''}</div>
                        </button>
                    </div>`).join('')}
            </div>
        </div>`).join('');
}

function aplicarModeloDeEstilo(variacaoId) {
    if (IS_APPROVED) return;
    const achado = DiagramaModelos.variacaoPorId(variacaoId);
    if (!achado) return;
    const { familia, variacao } = achado;
    if (topologia.nodes.length > 1 &&
        !confirm(`Aplicar "${familia.nome} - ${variacao.nome}"? O layout e o estilo mudam e os blocos são reposicionados. O conteúdo é mantido e você pode desfazer com Ctrl+Z.`)) return;

    if (document.getElementById('modeloLimparFormato')?.checked) {
        topologia.nodes.forEach(n => {
            if (!n.data) return;
            delete n.data.style;
            delete n.data.bgColor;
            if (n.type !== 'decision' && n.data.shape !== 'decision') delete n.data.shape;
        });
        topologia.edges.forEach(e => { delete e.style; });
    }

    topologia.layout_modo = variacao.layout || familia.layout;
    topologia.tema = DiagramaModelos.construirTema(variacao, paletaDoModeloEscolhida());
    aplicarFundoDoTema();
    aplicarLayoutArvore();          // as famílias deste catálogo usam os layouts em árvore (renderiza o canvas)
    atualizarUILayout();
    renderizarGrelha();
    renderizarOutliner();
    atualizarSelecoesVisuais();
    enquadrarVisaoCompleta();
    dispararAutoSave();

    const modalEl = document.getElementById('modalAplicarTemplate');
    const modal = modalEl && bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
}

document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('modalAplicarTemplate');
    if (modalEl) modalEl.addEventListener('show.bs.modal', renderizarGaleriaModelos);
});

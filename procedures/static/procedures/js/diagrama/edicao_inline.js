/* Editor de Diagramas (DOC.071) - módulo "edicao_inline"
 * Edição do texto direto no bloco (duplo clique ou F2), sem precisar do inspetor.
 * Enter confirma, Esc cancela, Tab confirma e cria um filho (modos em árvore). O foco sai do campo = confirma.
 */

function iniciarEdicaoNoBloco(e, node) {
    if (IS_APPROVED || e.button > 0) return;
    if (e.target.closest && e.target.closest('.handle, .handle-add, .collapse-toggle, input, textarea, button')) return;
    e.stopPropagation();
    selecionarNo(node.id);
    editarTextoDoNo(node.id);
}

function editarTextoDoNo(nodeId) {
    if (IS_APPROVED) return;
    const node = topologia.nodes.find(n => String(n.id) === String(nodeId));
    const el = document.getElementById(`node-${nodeId}`);
    if (!node || !el || el.querySelector('.edicao-inline')) return;

    // Bloco de colaborador: o nome vem do RH; o que se edita aqui é a função
    if (node.data?.colab) {
        const campoFuncao = el.querySelector('.colab-cargo-input');
        if (campoFuncao) { campoFuncao.focus(); campoFuncao.select(); }
        return;
    }

    const campo = document.createElement('textarea');
    campo.className = 'edicao-inline';
    campo.value = node.data?.label || '';
    campo.rows = 2;
    campo.maxLength = 255;
    campo.setAttribute('aria-label', 'Texto do bloco');
    el.appendChild(campo);
    campo.focus();
    campo.select();

    let encerrado = false;
    const concluir = (salvar) => {
        if (encerrado) return;
        encerrado = true;
        const novo = campo.value.replace(/\s+/g, ' ').trim();
        campo.remove();
        if (salvar && novo && novo !== (node.data?.label || '')) aplicarTextoAoNo(node, novo);
        const viewport = document.getElementById('canvasViewport');
        if (viewport) viewport.focus({ preventScroll: true }); // devolve o foco ao canvas (atalhos voltam a funcionar)
    };

    campo.addEventListener('keydown', ev => {
        ev.stopPropagation();
        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); concluir(true); }
        else if (ev.key === 'Escape') { ev.preventDefault(); concluir(false); }
        else if (ev.key === 'Tab') {
            ev.preventDefault();
            concluir(true);
            if (arvoreAtiva()) criarBlocoRapido('filho');
        }
    });
    campo.addEventListener('blur', () => concluir(true));
    ['mousedown', 'click', 'dblclick'].forEach(tipo => campo.addEventListener(tipo, ev => ev.stopPropagation()));
}

function aplicarTextoAoNo(node, texto) {
    if (!node.data) node.data = {};
    node.data.label = texto;
    sincronizarGridDoNo(node);
    if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

/* Editor de Diagramas (DOC.071) - módulo "inspetor"
 * Inspetor de blocos: subtítulos, colaborador, estilos e marcadores.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// SUBTÍTULOS E BLOCO DE COLABORADOR
// =========================================================================
const MAX_SUBTITULOS = 20;

function nomeExibicaoColab(colab) {
    const nome = (colab?.nome || '').trim();
    const partes = nome.split(/\s+/).filter(Boolean);
    if (colab?.nomeCurto && partes.length > 2) return `${partes[0]} ${partes[partes.length - 1]}`;
    return nome;
}

function fotoColabUrl(colabId) {
    return `/procedures/api/diagramas/colaboradores/${colabId}/foto/`;
}

function sincronizarGridDoNo(node) {
    const row = topologia.grid_data.find(r => r.stepId === node.id);
    if (!row) return;
    row.label = node.data.label || '';
    row.lane = node.data.lane || row.lane;
}

function noSelecionadoUnico() {
    if (!selectedNodeId) return null;
    return topologia.nodes.find(n => n.id === selectedNodeId) || null;
}

function renderizarSubtitulosInspector(node) {
    const box = document.getElementById('inspSubtitulosBox');
    const lista = document.getElementById('inspSubtitulosList');
    if (!box || !lista) return;
    // Subtítulos e colaborador valem para blocos de processo (não para início/fim/decisão)
    box.classList.toggle('d-none', node.type !== 'process');
    lista.innerHTML = '';
    (node.data?.subtitles || []).forEach((texto, i) => {
        const linha = document.createElement('div');
        linha.className = 'input-group input-group-sm';
        linha.innerHTML = `
            <input type="text" class="form-control" maxlength="300" placeholder="Subtítulo ${i + 1}" value="${escapeHtml(texto)}"
                   oninput="editarSubtitulo(${i}, this.value)">
            <button class="btn btn-outline-danger" type="button" title="Remover subtítulo" onclick="removerSubtitulo(${i})"><i class="bi bi-x-lg"></i></button>`;
        lista.appendChild(linha);
    });
}

function adicionarSubtitulo() {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node) return;
    if (!node.data) node.data = {};
    if (!Array.isArray(node.data.subtitles)) node.data.subtitles = [];
    if (node.data.subtitles.length >= MAX_SUBTITULOS) {
        alert(`Limite de ${MAX_SUBTITULOS} subtítulos por bloco.`);
        return;
    }
    node.data.subtitles.push('');
    renderizarSubtitulosInspector(node);
    const inputs = document.querySelectorAll('#inspSubtitulosList input');
    if (inputs.length) inputs[inputs.length - 1].focus();
    dispararAutoSave();
}

function editarSubtitulo(indice, valor) {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node || !Array.isArray(node.data?.subtitles)) return;
    node.data.subtitles[indice] = valor.slice(0, 300);
    renderizarCanvas();
    dispararAutoSave();
}

function removerSubtitulo(indice) {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node || !Array.isArray(node.data?.subtitles)) return;
    node.data.subtitles.splice(indice, 1);
    renderizarSubtitulosInspector(node);
    renderizarCanvas();
    dispararAutoSave();
}

function renderizarColabInspector(node) {
    const box = document.getElementById('inspColabBox');
    if (!box) return;
    box.classList.toggle('d-none', node.type !== 'process');

    const colab = node.data?.colab;
    document.getElementById('inspColabVinculado').classList.toggle('d-none', !colab);
    document.getElementById('inspColabBusca').classList.toggle('d-none', !!colab);
    document.getElementById('inspNodeLabel').disabled = !!colab;
    document.getElementById('inspColabResultados').innerHTML = '';
    document.getElementById('inspColabSearch').value = '';

    if (colab) {
        document.getElementById('inspColabNome').textContent = nomeExibicaoColab(colab);
        document.getElementById('inspColabNomeCurto').checked = !!colab.nomeCurto;
        document.getElementById('inspColabCargo').value = colab.cargo || '';
        const foto = document.getElementById('inspColabFoto');
        foto.innerHTML = colab.temFoto !== false
            ? `<img src="${fotoColabUrl(colab.id)}" alt="" onerror="this.remove()">` : '';
    }
}

let buscaColabInspectorTimer = null;
function buscarColaboradorInspector(termo) {
    clearTimeout(buscaColabInspectorTimer);
    const lista = document.getElementById('inspColabResultados');
    if (termo.trim().length < 2) {
        lista.innerHTML = '';
        return;
    }
    buscaColabInspectorTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/procedures/api/diagramas/colaboradores/?q=${encodeURIComponent(termo.trim())}`);
            if (!res.ok) throw new Error(res.status);
            const dados = await res.json();
            lista.innerHTML = '';
            if (!dados.results.length) {
                lista.innerHTML = '<div class="list-group-item small text-muted">Nenhum colaborador encontrado.</div>';
                return;
            }
            dados.results.forEach(item => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action py-1';
                btn.innerHTML = `<div class="fw-bold small">${escapeHtml(item.nome)}</div>
                                 <div class="text-muted" style="font-size:10px;">${escapeHtml(item.cargo)}${item.setor ? ' - ' + escapeHtml(item.setor) : ''}</div>`;
                btn.onclick = () => vincularColaboradorAoBloco(item);
                lista.appendChild(btn);
            });
        } catch (e) {
            lista.innerHTML = '<div class="list-group-item small text-danger">Erro ao buscar colaboradores.</div>';
        }
    }, 300);
}

function vincularColaboradorAoBloco(item) {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node) return;
    if (!node.data) node.data = {};
    node.data.colab = { id: item.id, nome: item.nome, cargo: item.cargo || '', cargoRH: item.cargo || '', nomeCurto: false, temFoto: !!item.tem_foto };
    node.data.label = nomeExibicaoColab(node.data.colab);
    sincronizarGridDoNo(node);
    const raiaSetor = raiaParaColaborador(item.setor_id);
    if (raiaSetor && (!node.data.lane || node.data.lane === 'Geral')) moverNoParaRaia(node, raiaSetor);

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

function alternarNomeCurto(ligado) {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node?.data?.colab) return;
    node.data.colab.nomeCurto = !!ligado;
    node.data.label = nomeExibicaoColab(node.data.colab);
    sincronizarGridDoNo(node);
    document.getElementById('inspColabNome').textContent = node.data.label;
    document.getElementById('inspNodeLabel').value = node.data.label;
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

// Função editada pelo painel: reconstrói o canvas (o foco continua no painel)
function editarCargoColab(valor) {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node?.data?.colab) return;
    node.data.colab.cargo = valor.slice(0, 100);
    renderizarCanvas();
    dispararAutoSave();
}

// Função editada direto no bloco: não reconstrói o canvas (preserva o foco do campo)
function editarCargoColabNo(nodeId, valor) {
    if (IS_APPROVED) return;
    const node = topologia.nodes.find(n => n.id === nodeId);
    if (!node?.data?.colab) return;
    node.data.colab.cargo = valor.slice(0, 100);
    const campoPainel = document.getElementById('inspColabCargo');
    if (campoPainel && selectedNodeId === nodeId && document.activeElement !== campoPainel) {
        campoPainel.value = node.data.colab.cargo;
    }
    dispararAutoSave();
}

function desvincularColaborador() {
    if (IS_APPROVED) return;
    const node = noSelecionadoUnico();
    if (!node?.data?.colab) return;
    delete node.data.colab; // o texto (nome) permanece como título comum do bloco
    renderizarCanvas();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

function inserirEmojiNaTag(emoji) {
    const input = document.getElementById('inspNodeCustomTag');
    input.value += emoji;
    input.focus();
}

function adicionarTagPersonalizada() {
    const input = document.getElementById('inspNodeCustomTag');
    const tag = input.value.trim();
    if (!tag || selectedNodeIds.size === 0) return;

    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (node) {
            if (!node.data) node.data = {};
            if (!node.data.customTags) node.data.customTags = [];
            if (!node.data.customTags.includes(tag)) {
                node.data.customTags.push(tag);
            }
        }
    });

    input.value = '';
    renderizarCanvas();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

function removerTagPersonalizada(tagIdStr) {
    if (!selectedNodeId) return;
    const node = topologia.nodes.find(n => n.id === selectedNodeId);
    if (node && node.data?.customTags) {
        node.data.customTags = node.data.customTags.filter(t => t !== tagIdStr);
    }
    renderizarCanvas();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

function renderizarTagsInspector(node) {
    const list = document.getElementById('customTagsList');
    if (!list) return;
    list.innerHTML = '';
    if (node.data?.customTags && Array.isArray(node.data.customTags)) {
        node.data.customTags.forEach(tag => {
            const btn = document.createElement('span');
            btn.className = 'badge bg-light text-dark border';
            btn.innerHTML = `${escapeHtml(tag)} <i class="bi bi-x-circle text-danger" style="cursor:pointer" onclick="removerTagPersonalizada('${escapeHtml(tag)}')"></i>`;
            list.appendChild(btn);
        });
    }
}

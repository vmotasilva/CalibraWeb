/* Editor de Diagramas (DOC.071) - módulo "raias_layout"
 * Raias (swimlanes) e layout automático por raias.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// AUTOMAÇÕES DE POSICIONAMENTO, CENTRALIZAÇÃO E ALINHAMENTO POR RAIAS
// =========================================================================
function posicionarAutomaticoPorRaias(centralizar = true) {
    const lanes = obterListaRaiasOrdenada();
    const nodeWidth = 190;
    const gap = 60;
    const viewport = document.getElementById('canvasViewport');
    const canvasTargetWidth = viewport ? (viewport.clientWidth / zoomLevel) : 1150;

    lanes.forEach((lane, lIdx) => {
        const yBase = 40 + lIdx * 240;
        const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);
        if (nodesInLane.length === 0) return;

        nodesInLane.sort((a, b) => {
            const numA = parseInt(a.data?.stepId || a.id, 10);
            const numB = parseInt(b.data?.stepId || b.id, 10);
            if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
            return String(a.id).localeCompare(String(b.id));
        });

        const totalWidth = nodesInLane.length * nodeWidth + (nodesInLane.length - 1) * gap;
        
        // Para garantir que a visualização não quebre caso a tela seja muito pequena
        const targetW = Math.max(canvasTargetWidth, totalWidth + 160);
        const startX = centralizar ? Math.max(80, Math.round((targetW - totalWidth) / 2)) : 80;

        nodesInLane.forEach((node, i) => {
            node.position.x = startX + i * (nodeWidth + gap);
            node.position.y = yBase + 60;
        });
    });
}

function reorganizarAutoLayout() {
    if (arvoreAtiva()) aplicarLayoutArvore();
    else {
        posicionarAutomaticoPorRaias(true);
        renderizarCanvas();
    }
    recentralizarCanvas();
    dispararAutoSave();
}

function alinharNosPorRaias() {
    // Se houver multi-seleção, alinha os blocos selecionados em relação ao primeiro selecionado
    if (selectedNodeIds.size > 1) {
        const arrIds = Array.from(selectedNodeIds);
        const refNode = topologia.nodes.find(n => n.id === arrIds[0]);
        if (refNode) {
            const alignY = refNode.position.y;
            arrIds.forEach(id => {
                const n = topologia.nodes.find(node => node.id === id);
                if (n) {
                    n.position.y = alignY; // Mantém o X (configuração) e alinha o Y
                }
            });
        }
    } else {
        // Comportamento original de alinhar todos por raia
        const lanes = obterListaRaiasOrdenada();
        
        // Calcula Y bases dinamicamente para preservar as alturas das raias
        let currentY = 40;
        const laneYBase = {};
        lanes.forEach(lane => {
            laneYBase[lane] = currentY + 60; // Margem superior
            
            const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);
            if (nodesInLane.length > 0) {
                const minPos = Math.min(...nodesInLane.map(n => n.position.y));
                const maxPos = Math.max(...nodesInLane.map(n => n.position.y));
                currentY += Math.max(220, (maxPos - minPos) + 160);
            } else {
                currentY += 220;
            }
        });

        lanes.forEach(lane => {
            const yBase = laneYBase[lane];
            const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);
            if (nodesInLane.length === 0) return;

            nodesInLane.forEach(n => {
                n.position.y = yBase;
            });

            nodesInLane.sort((a, b) => a.position.x - b.position.x);
            const startX = Math.min(...nodesInLane.map(n => n.position.x));
            const gap = 60;
            const width = 190;
            nodesInLane.forEach((n, i) => {
                n.position.x = startX + i * (width + gap);
            });
        });
    }

    renderizarCanvas();
    dispararAutoSave();
}

function centralizarEixoXDaTela() {
    if (topologia.nodes.length === 0) return;
    const viewport = document.getElementById('canvasViewport');
    const viewCenterX = viewport.scrollLeft / zoomLevel + (viewport.clientWidth / 2) / zoomLevel;
    
    // Centraliza baseado no "Ponto de Partida" (Nó Raiz / Primeiro Nó) para manter a estrutura do organograma alinhada
    const rootNode = topologia.nodes[0];
    
    // Pega a largura do elemento se renderizado, ou assume 190 (nodeWidth padrão)
    const el = document.getElementById(`node-${rootNode.id}`);
    const rootW = el ? el.offsetWidth : 190;
    
    const rootCenterX = rootNode.position.x + (rootW / 2);
    const shiftX = Math.round(viewCenterX - rootCenterX);
    
    if (shiftX !== 0) {
        topologia.nodes.forEach(n => {
            n.position.x += shiftX;
        });
        renderizarCanvas();
        dispararAutoSave();
    }
}

// =========================================================================
// GERENCIAMENTO INTERATIVO DE RAIAS
// =========================================================================
function abrirRenomearRaia(encodedLane) {
    if (IS_APPROVED) return;
    const raiaAtual = decodeURIComponent(encodedLane);
    const novoNome = prompt(`Renomear a Raia / Setor "${raiaAtual}" para:`, raiaAtual);
    if (!novoNome || !novoNome.trim() || novoNome.trim() === raiaAtual) return;
    renomearRaiaNoDiagrama(raiaAtual, novoNome.trim());
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function renomearRaiaNoDiagrama(raiaAtual, nomeLimpo) {
    fixarOrdemRaias();

    topologia.nodes.forEach(n => {
        if (n.data && (n.data.lane === raiaAtual || (!n.data.lane && raiaAtual === 'Geral'))) {
            n.data.lane = nomeLimpo;
        }
    });

    topologia.grid_data.forEach(r => {
        if (r.lane === raiaAtual || (!r.lane && raiaAtual === 'Geral')) {
            r.lane = nomeLimpo;
        }
    });

    // mantém ordem, raias fixas e cor própria com o novo nome (sem duplicar quando já existia)
    ['lanes', 'raias_fixas'].forEach(chave => {
        topologia[chave] = [...new Set((topologia[chave] || []).map(l => l === raiaAtual ? nomeLimpo : l))];
    });
    if (topologia.raias_cores && topologia.raias_cores[raiaAtual]) {
        topologia.raias_cores[nomeLimpo] = topologia.raias_cores[raiaAtual];
        delete topologia.raias_cores[raiaAtual];
    }
}

// Duplo clique no rótulo da raia: pop-up de configuração
let raiaEmConfiguracao = null;
function abrirConfigRaia(encodedLane) {
    const lane = decodeURIComponent(encodedLane);
    raiaEmConfiguracao = lane;
    const lanes = obterListaRaiasOrdenada();
    const blocos = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane).length;
    const propria = (topologia.raias_cores || {})[lane];

    document.getElementById('cfgRaiaNome').value = lane;
    document.getElementById('cfgRaiaCor').value = propria || corDaRaia(lane);
    document.getElementById('cfgRaiaCor').dataset.alterada = '';
    document.getElementById('cfgRaiaPosicao').textContent = `${lanes.indexOf(lane) + 1} de ${lanes.length}`;
    document.getElementById('cfgRaiaBlocos').textContent = blocos;
    document.getElementById('cfgRaiaRestaurarCor').style.display = propria ? '' : 'none';
    document.querySelectorAll('#modalConfigRaia [data-edicao]').forEach(el => { el.disabled = IS_APPROVED; });
    document.getElementById('cfgRaiaAcoes').style.display = IS_APPROVED ? 'none' : '';
    new bootstrap.Modal(document.getElementById('modalConfigRaia')).show();
}

function salvarConfigRaia() {
    if (IS_APPROVED || !raiaEmConfiguracao) return;
    let lane = raiaEmConfiguracao;
    const novoNome = document.getElementById('cfgRaiaNome').value.trim();
    const cor = document.getElementById('cfgRaiaCor');
    if (!novoNome) { alert('Informe o nome da raia.'); return; }
    if (novoNome !== lane) {
        if (obterListaRaiasOrdenada().some(l => l !== lane && l.toLowerCase() === novoNome.toLowerCase())) {
            alert(`A raia "${novoNome}" já existe neste diagrama.`);
            return;
        }
        renomearRaiaNoDiagrama(lane, novoNome);
        lane = novoNome;
    }
    if (cor.dataset.alterada) {
        topologia.raias_cores = { ...(topologia.raias_cores || {}), [lane]: cor.value };
    }
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function restaurarCorDaRaia() {
    if (IS_APPROVED || !raiaEmConfiguracao) return;
    if (topologia.raias_cores) delete topologia.raias_cores[raiaEmConfiguracao];
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    renderizarCanvas();
    dispararAutoSave();
}

function moverRaiaPelaConfig(direcao) {
    if (!raiaEmConfiguracao) return;
    moverRaia(encodeURIComponent(raiaEmConfiguracao), direcao);
    const lanes = obterListaRaiasOrdenada();
    document.getElementById('cfgRaiaPosicao').textContent = `${lanes.indexOf(raiaEmConfiguracao) + 1} de ${lanes.length}`;
}

function excluirRaiaPelaConfig() {
    if (!raiaEmConfiguracao) return;
    const lane = raiaEmConfiguracao;
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    excluirRaia(encodeURIComponent(lane));
}

function moverRaia(encodedLane, direcao) {
    if (IS_APPROVED) return;
    const lane = decodeURIComponent(encodedLane);
    const lanes = obterListaRaiasOrdenada();
    const curIdx = lanes.indexOf(lane);
    if (curIdx === -1) return;

    const targetIdx = curIdx + direcao;
    if (targetIdx < 0 || targetIdx >= lanes.length) return;

    const nova = [...lanes];
    nova[curIdx] = lanes[targetIdx];
    nova[targetIdx] = lane;
    aplicarNovaOrdemDeRaias(nova);

    renderizarCanvas();
    renderizarGrelha();
    dispararAutoSave();
}

function adicionarNovaRaia() {
    if (IS_APPROVED) return;
    document.getElementById('inputRaiaLivre').value = '';
    new bootstrap.Modal(document.getElementById('modalNovaRaia')).show();
}

function adicionarRaiaLivre() {
    adicionarRaiaAoDiagrama(document.getElementById('inputRaiaLivre').value);
}

// Insere a nova raia no fim do diagrama
function adicionarRaiaAoDiagrama(nome) {
    if (IS_APPROVED) return;
    const nomeLimpo = (nome || '').trim();
    if (!nomeLimpo) return;

    const lanes = obterListaRaiasOrdenada();
    if (lanes.some(l => l.toLowerCase() === nomeLimpo.toLowerCase())) {
        alert(`A raia "${nomeLimpo}" já existe neste diagrama.`);
        return;
    }

    const posicao = lanes.length;

    const nova = [...lanes];
    nova.splice(posicao, 0, nomeLimpo);
    topologia.raias_fixas = [...new Set([...(topologia.raias_fixas || []), nomeLimpo])];
    // as faixas abaixo da nova raia descem junto com seus blocos
    const antes = calcularFaixasRaias(lanes);
    topologia.lanes = nova;
    const depois = calcularFaixasRaias(nova);
    topologia.nodes.forEach(n => {
        const l = n.data?.lane || 'Geral';
        if (antes[l] && depois[l]) n.position.y = Math.round(n.position.y - antes[l].top + depois[l].top);
    });

    bootstrap.Modal.getInstance(document.getElementById('modalNovaRaia'))?.hide();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    preencherSugestoesDeRaias();
    dispararAutoSave();
}

function excluirRaia(encodedLane) {
    if (IS_APPROVED) return;
    const lane = decodeURIComponent(encodedLane);
    const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);

    if (!confirm(`Deseja realmente excluir a raia "${lane}" com ${nodesInLane.length} etapa(s)?`)) return;

    const idsToRemove = new Set(nodesInLane.map(n => n.id));

    topologia.nodes = topologia.nodes.filter(n => !idsToRemove.has(n.id));
    topologia.edges = topologia.edges.filter(e => !idsToRemove.has(e.source) && !idsToRemove.has(e.target));
    topologia.grid_data = topologia.grid_data.filter(r => !idsToRemove.has(r.stepId));
    topologia.lanes = (topologia.lanes || []).filter(l => l !== lane);
    topologia.raias_fixas = (topologia.raias_fixas || []).filter(l => l !== lane);

    posicionarAutomaticoPorRaias(true);
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

// =========================================================================
// GESTÃO DAS RAIAS DO DIAGRAMA ABERTO (lista: nome, cor, ordem, exclusão)
// =========================================================================
function abrirGerenciarRaias() {
    renderizarListaGerenciarRaias();
    document.getElementById('gerenciarRaiasNova').style.display = IS_APPROVED ? 'none' : '';
    document.getElementById('gerenciarRaiaNovaNome').value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalGerenciarRaias')).show();
}

function renderizarListaGerenciarRaias() {
    const lista = document.getElementById('listaGerenciarRaias');
    const lanes = obterListaRaiasOrdenada();
    const dis = IS_APPROVED ? 'disabled' : '';
    lista.innerHTML = '';
    if (lanes.length === 0) {
        lista.innerHTML = '<div class="list-group-item small text-muted">Este diagrama ainda não tem raias.</div>';
        return;
    }
    lanes.forEach((lane, i) => {
        const blocos = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane).length;
        const row = document.createElement('div');
        row.className = 'list-group-item d-flex align-items-center gap-2';
        row.innerHTML = `
            <input type="color" class="form-control form-control-color" value="${escapeHtml(corDaRaia(lane))}" ${dis} title="Cor da faixa">
            <input type="text" name="raia_nome_x" autocomplete="off" data-lpignore="true" data-1p-ignore class="form-control form-control-sm" maxlength="100" value="${escapeHtml(lane)}" ${dis}>
            <span class="badge bg-light text-dark border text-nowrap">${blocos} bloco${blocos === 1 ? '' : 's'}</span>
            <div class="btn-group btn-group-sm">
                <button type="button" class="btn btn-light border" ${i === 0 || IS_APPROVED ? 'disabled' : ''} data-acao="cima" title="Mover para cima"><i class="bi bi-arrow-up"></i></button>
                <button type="button" class="btn btn-light border" ${i === lanes.length - 1 || IS_APPROVED ? 'disabled' : ''} data-acao="baixo" title="Mover para baixo"><i class="bi bi-arrow-down"></i></button>
                <button type="button" class="btn btn-outline-danger" ${dis} data-acao="excluir" title="Excluir raia"><i class="bi bi-trash"></i></button>
            </div>`;
        const [cor, nome] = row.querySelectorAll('input');
        cor.onchange = () => {
            topologia.raias_cores = { ...(topologia.raias_cores || {}), [lane]: cor.value };
            renderizarCanvas();
            dispararAutoSave();
        };
        nome.onchange = () => gerenciarRaiaRenomear(lane, nome.value);
        nome.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); nome.blur(); } };
        row.querySelector('[data-acao="cima"]').onclick = () => { moverRaia(encodeURIComponent(lane), -1); renderizarListaGerenciarRaias(); };
        row.querySelector('[data-acao="baixo"]').onclick = () => { moverRaia(encodeURIComponent(lane), 1); renderizarListaGerenciarRaias(); };
        row.querySelector('[data-acao="excluir"]').onclick = () => {
            excluirRaia(encodeURIComponent(lane));
            renderizarListaGerenciarRaias();
        };
        lista.appendChild(row);
    });
}

function gerenciarRaiaRenomear(atual, valor) {
    const novo = (valor || '').trim();
    if (!novo || novo === atual) { renderizarListaGerenciarRaias(); return; }
    if (obterListaRaiasOrdenada().some(l => l !== atual && l.toLowerCase() === novo.toLowerCase())) {
        alert(`A raia "${novo}" já existe neste diagrama.`);
        renderizarListaGerenciarRaias();
        return;
    }
    renomearRaiaNoDiagrama(atual, novo);
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    preencherSugestoesDeRaias();
    dispararAutoSave();
    renderizarListaGerenciarRaias();
}

function gerenciarRaiaAdicionar() {
    if (IS_APPROVED) return;
    const nome = document.getElementById('gerenciarRaiaNovaNome').value.trim();
    const cor = document.getElementById('gerenciarRaiaNovaCor').value;
    if (!nome) return;
    const antes = obterListaRaiasOrdenada().length;
    adicionarRaiaAoDiagrama(nome);
    if (obterListaRaiasOrdenada().length > antes) {
        if (cor && cor !== '#334155') topologia.raias_cores = { ...(topologia.raias_cores || {}), [nome]: cor };
        renderizarCanvas();
        dispararAutoSave();
        document.getElementById('gerenciarRaiaNovaNome').value = '';
    }
    renderizarListaGerenciarRaias();
}

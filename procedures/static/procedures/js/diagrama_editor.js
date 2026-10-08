/* Editor de Diagramas / Fluxogramas (DOC.071)
 * Depende das constantes definidas no template: VERSAO_ID, VERSAO_REVISAO, IS_APPROVED, CSRF_TOKEN,
 * versaoAtualizadoEm e topologia (script inline em diagrama_editor.html).
 */
if (!topologia.nodes) topologia.nodes = [];
if (!topologia.edges) topologia.edges = [];
if (!topologia.grid_data) topologia.grid_data = [];
if (!topologia.estilo_linha) topologia.estilo_linha = 'ortogonal'; // Padrão 90° para fluxogramas e organogramas

let autoSaveTimer = null;
let selectedEdgeId = null; // Conexão selecionada no canvas
let isDragging = false;
let activeNode = null;
let selectedNodeId = null;
let selectedNodeIds = new Set(); // Para multi-seleção e alinhamento
let dragOffset = { x: 0, y: 0 };
let modoAtual = 'canvas';

// Variáveis de Navegação e Zoom
let zoomLevel = 1.0;
let isPanning = false;
let panStart = { x: 0, y: 0, scrollLeft: 0, scrollTop: 0 };
let isSpacePressed = false;

// =========================================================================
// INICIALIZAÇÃO E ATALHOS DE TECLADO (ENTER / TAB / DEL / ESC / ZOOM / PAN)
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    if (topologia.nodes.length === 0 && topologia.grid_data.length > 0) {
        gerarNodesPorGridData();
    } else if (topologia.grid_data.length === 0 && topologia.nodes.length > 0) {
        gerarGridDataPorNodes();
    }

    iniciarHistorico();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    setupCanvasNavigation();
    atualizarLabelEstiloLinha();

    // Enquadra suavemente a visão inicial nos blocos
    setTimeout(() => {
        enquadrarVisaoCompleta();
    }, 150);

    // Atalhos de teclado do editor (ver tratarAtalhosGlobais)
    window.addEventListener('keydown', tratarAtalhosGlobais);
});

function foraDeCampoDeEdicao() {
    const el = document.activeElement;
    if (!el) return true;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return false;
    return !el.isContentEditable;
}

function focoEmControleInterativo() {
    const el = document.activeElement;
    return !!el && ['BUTTON', 'A', 'SUMMARY'].includes(el.tagName);
}

// O foco está no canvas (ou "solto", no corpo da página)? Só nesse caso as teclas de edição de blocos valem
function focoNoCanvasOuLivre() {
    const el = document.activeElement;
    if (!el || el === document.body) return true;
    const viewport = document.getElementById('canvasViewport');
    return !!viewport && viewport.contains(el);
}

function modalAberto() {
    return !!document.querySelector('.modal.show');
}

/**
 * Atalhos de teclado globais. Regras para não atrapalhar Grelha, Outliner, janelas e a navegação por Tab:
 *  - nunca agem com uma janela (modal) aberta nem dentro de campos de texto, listas ou áreas editáveis;
 *  - zoom (Ctrl +/-/0) só no Canvas: nos demais modos o zoom do navegador continua funcionando;
 *  - Desfazer/Refazer valem em qualquer modo (a Grelha e o Outliner usam a mesma topologia);
 *  - Enter / Tab / Delete / Backspace / Esc (editar blocos) só no modo Canvas, com o foco no canvas
 *    (ou solto). Com o foco em botões ou links, o teclado mantém o comportamento nativo.
 */
function tratarAtalhosGlobais(e) {
    if (e.defaultPrevented || modalAberto() || !foraDeCampoDeEdicao()) return;

    const ctrl = e.ctrlKey || e.metaKey;

    if (ctrl && modoAtual === 'canvas') {
        if (e.key === '=' || e.key === '+') {
            e.preventDefault();
            alterarZoomRelativo(0.1);
            return;
        } else if (e.key === '-') {
            e.preventDefault();
            alterarZoomRelativo(-0.1);
            return;
        } else if (e.key === '0') {
            e.preventDefault();
            aplicarZoom(1.0);
            return;
        }
    }

    if (IS_APPROVED) return;

    if (ctrl && !e.altKey) {
        const k = e.key.toLowerCase();
        if (k === 'z') {
            e.preventDefault();
            if (e.shiftKey) refazer(); else desfazer();
            return;
        } else if (k === 'y') {
            e.preventDefault();
            refazer();
            return;
        }
    }

    if (modoAtual !== 'canvas' || focoEmControleInterativo() || !focoNoCanvasOuLivre()) return;

    if (e.key === 'Enter') {
        e.preventDefault();
        adicionarTopicoIrmao();
    } else if (e.key === 'Tab') {
        e.preventDefault();
        adicionarSubtopicoFilho();
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedEdgeId || selectedNodeId) {
            e.preventDefault();
            excluirSelecao();
        }
    } else if (e.key === 'Escape') {
        desmarcarTodosNos();
    }
}

// =========================================================================
// ALTERNAÇÃO DE MODOS (CANVAS / OUTLINER / GRELHA)
// =========================================================================
function alternarModoEditor(modo) {
    modoAtual = modo;
    const btnCanvas = document.getElementById('btnModoCanvas');
    const btnOutliner = document.getElementById('btnModoOutliner');
    const btnGrelha = document.getElementById('btnModoGrelha');

    const vCanvas = document.getElementById('viewCanvasContainer');
    const vOutliner = document.getElementById('viewOutlinerContainer');
    const vGrelha = document.getElementById('viewGrelhaContainer');

    [btnCanvas, btnOutliner, btnGrelha].forEach(b => b.classList.remove('active'));
    [vCanvas, vOutliner, vGrelha].forEach(v => v.classList.add('d-none'));

    // Fora do Canvas não há seleção ativa (evita excluir um bloco "invisível" por engano) e os controles
    // exclusivos do Canvas ficam desativados (sem foco, sem clique e sem atalhos)
    if (modo !== 'canvas') desmarcarTodosNos();
    document.getElementById('editorMainContainer')?.classList.toggle('modo-nao-canvas', modo !== 'canvas');
    document.querySelectorAll('.somente-canvas').forEach(el => { el.inert = modo !== 'canvas'; });

    if (modo === 'canvas') {
        btnCanvas.classList.add('active');
        vCanvas.classList.remove('d-none');
        renderizarCanvas();
    } else if (modo === 'outliner') {
        btnOutliner.classList.add('active');
        vOutliner.classList.remove('d-none');
        renderizarOutliner();
    } else if (modo === 'grelha') {
        btnGrelha.classList.add('active');
        vGrelha.classList.remove('d-none');
        renderizarGrelha();
    }
}

function alternarModoZen() {
    document.getElementById('editorMainContainer').classList.toggle('zen-mode');
    setTimeout(enquadrarVisaoCompleta, 200);
}

function alternarFundoCanvas() {
    document.getElementById('canvasViewport').classList.toggle('clean-bg');
}

function toggleInspectorPanel() {
    const panel = document.getElementById('inspectorPanel');
    const btn = document.getElementById('btnToggleInspector');
    panel.classList.toggle('collapsed');
    btn.classList.toggle('active');
}

// =========================================================================
// RENDERIZAÇÃO DO CANVAS INTERATIVO
// =========================================================================
function renderizarCanvas() {
    const nodesContainer = document.getElementById('nodesContainer');
    const swimlanesLayer = document.getElementById('swimlanesLayer');
    nodesContainer.innerHTML = '';
    swimlanesLayer.innerHTML = '';

    // 1. Renderiza Raias (Swimlanes) dinamicamente (Alturas ajustáveis)
    const lanes = obterListaRaiasOrdenada();
    let currentY = 40;
    
    // Calcula a altura necessária para cada raia
    const laneHeights = {};
    lanes.forEach(lane => {
        const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);
        if (nodesInLane.length > 0) {
            // Encontra a maior posição Y + altura estimada do nó (cerca de 100px)
            const minPos = Math.min(...nodesInLane.map(n => n.position.y));
            const maxPos = Math.max(...nodesInLane.map(n => n.position.y));
            laneHeights[lane] = Math.max(220, (maxPos - minPos) + 160);
        } else {
            laneHeights[lane] = 220; // altura mínima
        }
    });

    lanes.forEach((lane, idx) => {
        const yPos = currentY;
        const h = laneHeights[lane];
        const laneEl = document.createElement('div');
        laneEl.className = 'swimlane-row';
        laneEl.style.top = `${yPos}px`;
        laneEl.style.height = `${h}px`;
        laneEl.style.borderLeftColor = corDaRaia(lane);

        const safeLane = escapeHtml(lane);
        laneEl.innerHTML = `
            <div class="swimlane-header-wrapper dropdown">
                <div class="swimlane-rotator-btn" data-bs-toggle="dropdown" aria-expanded="false" title="Opções da Raia / Setor">
                    <span>${safeLane}</span>
                </div>
                <ul class="dropdown-menu shadow">
                    <li><h6 class="dropdown-header text-uppercase fw-bold text-primary">Raia: ${safeLane}</h6></li>
                    <li><a class="dropdown-item py-2" href="javascript:void(0)" onclick="abrirRenomearRaia('${encodeURIComponent(lane)}')"><i class="bi bi-pencil-square me-2 text-secondary"></i> Renomear Raia</a></li>
                    ${!IS_APPROVED ? `
                    <li><hr class="dropdown-divider"></li>
                    <li><a class="dropdown-item py-2 ${idx === 0 ? 'disabled' : ''}" href="javascript:void(0)" onclick="moverRaia('${encodeURIComponent(lane)}', -1)"><i class="bi bi-arrow-up-circle me-2 text-secondary"></i> Mover para Cima</a></li>
                    <li><a class="dropdown-item py-2 ${idx === lanes.length - 1 ? 'disabled' : ''}" href="javascript:void(0)" onclick="moverRaia('${encodeURIComponent(lane)}', 1)"><i class="bi bi-arrow-down-circle me-2 text-secondary"></i> Mover para Baixo</a></li>
                    <li><hr class="dropdown-divider"></li>
                    <li><a class="dropdown-item py-2 text-danger fw-semibold" href="javascript:void(0)" onclick="excluirRaia('${encodeURIComponent(lane)}')"><i class="bi bi-trash me-2"></i> Excluir Raia</a></li>
                    ` : ''}
                </ul>
            </div>
        `;
        swimlanesLayer.appendChild(laneEl);
        currentY += h; // Avança o Y base para a próxima raia
    });

    // 2. Renderiza Nós
    topologia.nodes.forEach(node => {
        const nodeEl = document.createElement('div');
        nodeEl.id = `node-${node.id}`;
        nodeEl.style.left = `${node.position.x}px`;
        nodeEl.style.top = `${node.position.y}px`;

        if (selectedNodeIds.has(node.id)) {
            nodeEl.classList.add('selected');
        }

        // Marcadores Personalizados (Tags / Etiquetas)
        let markersHtml = '';
        if (node.data?.customTags && Array.isArray(node.data.customTags)) {
            node.data.customTags.forEach(tag => {
                markersHtml += `<span class="node-marker-badge">${escapeHtml(tag)}</span>`;
            });
        }

        // Cores e Estilos Customizados
        if (node.data?.bgColor) {
            nodeEl.style.backgroundColor = node.data.bgColor;
            if (['#2563eb', '#334155', '#ef4444', '#8b5cf6'].includes(node.data.bgColor)) {
                nodeEl.style.color = '#ffffff';
            }
        }

        if (node.type === 'start' || node.type === 'end') {
            nodeEl.className = `flow-node node-start-end ${node.type === 'start' ? 'node-start' : 'node-end'}`;
            nodeEl.innerHTML = `
                <span>${markersHtml}${escapeHtml(node.data.label) || (node.type === 'start' ? 'INÍCIO' : 'FIM')}</span>
                ${node.type === 'start' ? '<div class="handle handle-bottom"></div>' : '<div class="handle handle-top"></div>'}
            `;
        } else if (node.type === 'decision') {
            nodeEl.className = 'flow-node node-decision';
            nodeEl.innerHTML = `
                <div class="diamond-inner">
                    <div class="diamond-content">${markersHtml}${escapeHtml(node.data.label) || 'Decisão?'}</div>
                </div>
                <div class="handle handle-top"></div>
                <div class="handle handle-bottom" title="Sim"></div>
                <div class="handle handle-right" title="Não"></div>
                <div class="handle handle-left"></div>
            `;
        } else {
            const shapeClass = node.data?.shape === 'pill' ? 'node-pill' : 
                              (node.data?.shape === 'circle' ? 'node-circle' : 
                              (node.data?.shape === 'parallelogram' ? 'node-parallelogram' : 
                              (node.data?.isCentral ? 'node-central' : '')));
                              
            const colab = node.data?.colab;
            nodeEl.className = `flow-node node-process ${shapeClass}${colab ? ' node-colab' : ''}`;

            const subsHtml = (node.data?.subtitles || [])
                .filter(t => t && t.trim())
                .map(t => `<div class="node-subtitle">${escapeHtml(t)}</div>`).join('');

            let corpoHtml;
            if (colab) {
                const foto = colab.temFoto !== false
                    ? `<img src="${fotoColabUrl(colab.id)}" alt="" onerror="this.remove()">` : '';
                const cargoHtml = IS_APPROVED
                    ? (colab.cargo ? `<div class="colab-cargo">${escapeHtml(colab.cargo)}</div>` : '')
                    : `<input type="text" class="colab-cargo-input" value="${escapeHtml(colab.cargo || '')}" placeholder="Função" maxlength="100"
                              onmousedown="event.stopPropagation()" ondblclick="event.stopPropagation()"
                              oninput="editarCargoColabNo('${escapeHtml(node.id)}', this.value)">`;
                corpoHtml = `
                    <div class="colab-card">
                        <div class="colab-foto">${foto}</div>
                        <div class="colab-info">
                            <div class="colab-nome">${markersHtml}${escapeHtml(nomeExibicaoColab(colab))}</div>
                            ${cargoHtml}
                            ${subsHtml}
                        </div>
                    </div>`;
            } else {
                corpoHtml = `
                    <div class="fw-semibold small leading-tight mt-1">${markersHtml} ${escapeHtml(node.data.label)}</div>
                    ${subsHtml}`;
            }

            nodeEl.innerHTML = `
                ${corpoHtml}
                ${node.data.documentRef ? `<span class="badge-doc">📄 ${escapeHtml(node.data.documentRef)}</span>` : ''}
                <div class="handle handle-top"></div>
                <div class="handle handle-bottom"></div>
                ${!IS_APPROVED ? `
                    <div class="handle-add handle-add-right" onclick="adicionarSubtopicoA(event, '${node.id}', 'right')" title="Adicionar à Direita">+</div>
                    <div class="handle-add handle-add-bottom" onclick="adicionarSubtopicoA(event, '${node.id}', 'bottom')" title="Adicionar Abaixo">+</div>
                    <div class="handle-add handle-add-left" onclick="adicionarSubtopicoA(event, '${node.id}', 'left')" title="Adicionar à Esquerda">+</div>
                ` : ''}
            `;
        }

        // Clique para Seleção (Com Shift para Multi-Seleção)
        nodeEl.addEventListener('click', (e) => {
            e.stopPropagation();
            if (e.shiftKey) {
                if (selectedNodeIds.has(node.id)) {
                    selectedNodeIds.delete(node.id);
                    if (selectedNodeId === node.id) selectedNodeId = Array.from(selectedNodeIds)[0] || null;
                } else {
                    selectedNodeIds.add(node.id);
                    selectedNodeId = node.id;
                }
                atualizarSelecoesVisuais();
                limparSelecaoAresta();
            } else {
                selecionarNo(node.id);
            }
        });

        // Eventos de Arrasto
        if (!IS_APPROVED) {
            nodeEl.addEventListener('mousedown', (e) => iniciarArrasto(e, node));
        }

        nodesContainer.appendChild(nodeEl);
    });

    desenharConexoes();
}

function atualizarSelecoesVisuais() {
    document.querySelectorAll('.flow-node').forEach(el => el.classList.remove('selected'));
    selectedNodeIds.forEach(id => {
        const el = document.getElementById(`node-${id}`);
        if (el) el.classList.add('selected');
    });
    
    if (selectedNodeId) {
        const node = topologia.nodes.find(n => n.id === selectedNodeId);
        if (node) {
            document.getElementById('inspectorEmptyState').classList.add('d-none');
            document.getElementById('inspectorControls').classList.remove('d-none');
            document.getElementById('inspNodeLabel').value = node.data?.label || '';
            document.getElementById('inspNodeLane').value = node.data?.lane || '';
            document.getElementById('inspNodeDocRef').value = node.data?.documentRef || '';
            renderizarTagsInspector(node);
            renderizarSubtitulosInspector(node);
            renderizarColabInspector(node);
            preencherSugestoesDeRaias();

            const panel = document.getElementById('inspectorPanel');
            if (panel.classList.contains('collapsed')) {
                toggleInspectorPanel();
            }
        }
    } else {
        document.getElementById('inspectorEmptyState').classList.remove('d-none');
        document.getElementById('inspectorControls').classList.add('d-none');
    }
}

function selecionarNo(nodeId) {
    selectedNodeIds.clear();
    selectedNodeIds.add(nodeId);
    selectedNodeId = nodeId;
    atualizarSelecoesVisuais();
    limparSelecaoAresta();
}

function desmarcarTodosNos() {
    selectedNodeId = null;
    selectedNodeIds.clear();
    atualizarSelecoesVisuais();
    limparSelecaoAresta();
}

function limparSelecaoAresta() {
    if (!selectedEdgeId) return;
    selectedEdgeId = null;
    desenharConexoes();
}

function selecionarAresta(edgeId) {
    selectedNodeId = null;
    selectedNodeIds.clear();
    atualizarSelecoesVisuais();
    selectedEdgeId = edgeId;
    desenharConexoes();
    const vp = document.getElementById('canvasViewport');
    if (vp) vp.focus({ preventScroll: true });
}

function sincronizarAposEdicaoDeAresta() {
    sincronizarEdgesComGridData();
    desenharConexoes();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function excluirArestaSelecionada() {
    if (IS_APPROVED || !selectedEdgeId) return;
    topologia.edges = topologia.edges.filter(e => e.id !== selectedEdgeId);
    selectedEdgeId = null;
    sincronizarAposEdicaoDeAresta();
}

function editarRotuloAresta(edgeId) {
    if (IS_APPROVED) return;
    const edge = topologia.edges.find(e => e.id === edgeId);
    if (!edge) return;
    const novo = prompt('Rótulo da conexão (ex.: Sim, Não, Reexecutar). Deixe vazio para remover:', edge.label || '');
    if (novo === null) return;
    const limpo = novo.trim();
    if (limpo) edge.label = limpo; else delete edge.label;
    sincronizarAposEdicaoDeAresta();
}

function excluirSelecao() {
    if (selectedEdgeId) {
        excluirArestaSelecionada();
    } else {
        excluirNoSelecionado();
    }
}

function alinharSelecionados(direcao) {
    if (selectedNodeIds.size < 2) {
        alert('Selecione pelo menos 2 blocos (Shift + Click) para alinhar.');
        return;
    }
    
    const nosSelecionados = Array.from(selectedNodeIds).map(id => topologia.nodes.find(n => n.id === id)).filter(n => n);
    
    // Pega o primeiro selecionado como referência
    const refNode = nosSelecionados[0];
    const refX = refNode.position.x;
    const refY = refNode.position.y;
    
    // Use a default size for reference if offsetWidth is 0
    const refEl = document.getElementById(`node-${refNode.id}`);
    const refW = refEl ? refEl.offsetWidth : 180;
    const refH = refEl ? refEl.offsetHeight : 70;
    
    nosSelecionados.forEach(node => {
        if (node.id === refNode.id) return;
        
        const el = document.getElementById(`node-${node.id}`);
        const w = el ? el.offsetWidth : 180;
        const h = el ? el.offsetHeight : 70;
        
        if (direcao === 'top') {
            node.position.y = refY;
        } else if (direcao === 'bottom') {
            node.position.y = refY + refH - h;
        } else if (direcao === 'left') {
            node.position.x = refX;
        } else if (direcao === 'right') {
            node.position.x = refX + refW - w;
        } else if (direcao === 'center-h') {
            node.position.x = refX + (refW / 2) - (w / 2);
        } else if (direcao === 'center-v') {
            node.position.y = refY + (refH / 2) - (h / 2);
        }
    });
    
    renderizarCanvas();
    dispararAutoSave();
}

function aplicarEstiloNoSelecionado(prop, valor) {
    if (selectedNodeIds.size === 0) return;
    
    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (!node) return;

        if (!node.data) node.data = {};
        if (prop === 'label' && node.data.colab) return; // o texto vem do colaborador (nome completo ou curto)

        if (prop === 'lane') {
            moverNoParaRaia(node, valor);
            return;
        }

        if (prop === 'shape') {
            node.data.shape = valor;
            if (valor === 'decision') node.type = 'decision';
            else if (node.type === 'decision') node.type = 'process';
        } else {
            node.data[prop] = valor;
        }

        // Sincroniza com o grid_data
        const gridRow = topologia.grid_data.find(r => r.stepId === node.id);
        if (gridRow) {
            if (prop === 'label') gridRow.label = valor;
            if (prop === 'lane') gridRow.lane = valor;
            if (prop === 'documentRef') gridRow.documentRef = valor;
        }
    });

    renderizarCanvas();
    dispararAutoSave();
}

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
    node.data.colab = { id: item.id, nome: item.nome, cargo: item.cargo || '', nomeCurto: false, temFoto: !!item.tem_foto };
    node.data.label = nomeExibicaoColab(node.data.colab);
    sincronizarGridDoNo(node);
    const raiaSetor = raiaParaColaborador(item.setor_id, item.setor);
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

// =========================================================================
// ARRASTO DE NÓS (DRAG & DROP COM SUPORTE A ZOOM)
// =========================================================================
function iniciarArrasto(e, node) {
    if (e.target.classList.contains('handle')) return;
    if (isSpacePressed || e.button === 1) return; // Não arrasta se estiver em modo pan
    isDragging = true;
    activeNode = node;
    
    // Se não for multi-seleção e o nó não estiver selecionado, seleciona ele
    if (!e.shiftKey && !selectedNodeIds.has(node.id)) {
        selecionarNo(node.id);
    }

    const canvasViewport = document.getElementById('canvasViewport');
    const canvasRect = canvasViewport.getBoundingClientRect();

    const mouseCanvasX = (e.clientX - canvasRect.left + canvasViewport.scrollLeft) / zoomLevel;
    const mouseCanvasY = (e.clientY - canvasRect.top + canvasViewport.scrollTop) / zoomLevel;

    dragOffset.x = mouseCanvasX - node.position.x;
    dragOffset.y = mouseCanvasY - node.position.y;

    window.addEventListener('mousemove', onArrasto);
    window.addEventListener('mouseup', pararArrasto);
}

function onArrasto(e) {
    if (!isDragging || !activeNode) return;

    const canvasViewport = document.getElementById('canvasViewport');
    const canvasRect = canvasViewport.getBoundingClientRect();

    const mouseCanvasX = (e.clientX - canvasRect.left + canvasViewport.scrollLeft) / zoomLevel;
    const mouseCanvasY = (e.clientY - canvasRect.top + canvasViewport.scrollTop) / zoomLevel;

    const x = Math.max(20, Math.round(mouseCanvasX - dragOffset.x));
    const y = Math.max(20, Math.round(mouseCanvasY - dragOffset.y));

    const dx = x - activeNode.position.x;
    const dy = y - activeNode.position.y;

    // Se múltiplos selecionados, move todos juntos
    if (selectedNodeIds.size > 1 && selectedNodeIds.has(activeNode.id)) {
        selectedNodeIds.forEach(id => {
            const n = topologia.nodes.find(nd => nd.id === id);
            if (n) {
                n.position.x += dx;
                n.position.y += dy;
                const nodeEl = document.getElementById(`node-${n.id}`);
                if (nodeEl) {
                    nodeEl.style.left = `${n.position.x}px`;
                    nodeEl.style.top = `${n.position.y}px`;
                }
            }
        });
    } else {
        activeNode.position.x = x;
        activeNode.position.y = y;
        const nodeEl = document.getElementById(`node-${activeNode.id}`);
        if (nodeEl) {
            nodeEl.style.left = `${x}px`;
            nodeEl.style.top = `${y}px`;
        }
    }

    desenharConexoes();
    dispararAutoSave();
}

function pararArrasto() {
    isDragging = false;
    activeNode = null;
    window.removeEventListener('mousemove', onArrasto);
    window.removeEventListener('mouseup', pararArrasto);
}

// =========================================================================
// CONFIGURAÇÃO E DESENHO DE ARESTAS SVG (LINHAS ORTOGONAIS 90° E CURVAS)
// =========================================================================
function alterarEstiloLinha(estilo) {
    topologia.estilo_linha = estilo;
    atualizarLabelEstiloLinha();
    desenharConexoes();
    dispararAutoSave();
}

function atualizarLabelEstiloLinha() {
    const label = document.getElementById('labelEstiloLinha');
    if (!label) return;
    const estilo = topologia.estilo_linha || 'ortogonal';
    if (estilo === 'ortogonal') {
        label.textContent = 'Linhas 90° (Ortogonal)';
    } else if (estilo === 'curva') {
        label.textContent = 'Curvas Suaves';
    } else if (estilo === 'reta') {
        label.textContent = 'Linhas Retas';
    }
}

function gerarCaminhoConexao(sourceNode, targetNode, sourceEl, targetEl, edge, estilo = 'ortogonal') {
    const sW = sourceEl.offsetWidth || 180;
    const sH = sourceEl.offsetHeight || 70;
    const tW = targetEl.offsetWidth || 180;
    const tH = targetEl.offsetHeight || 70;

    const sLeft = sourceNode.position.x;
    const sTop = sourceNode.position.y;
    const sRight = sLeft + sW;
    const sBottom = sTop + sH;
    const sMidX = sLeft + sW / 2;
    const sMidY = sTop + sH / 2;

    const tLeft = targetNode.position.x;
    const tTop = targetNode.position.y;
    const tRight = tLeft + tW;
    const tBottom = tTop + tH;
    const tMidX = tLeft + tW / 2;
    const tMidY = tTop + tH / 2;

    let startX, startY, endX, endY;
    let flowType = 'vertical';

    // Determinação inteligente dos pontos de ancoragem
    if (edge.sourceHandle === 'right' || (sourceNode.type === 'decision' && edge.label?.toLowerCase() === 'não')) {
        startX = sRight;
        startY = sMidY;
        endX = tLeft;
        endY = tMidY;
        flowType = 'horizontal';
    } else if (tTop >= sBottom - 10) {
        // Fluxo padrão hierárquico (Pai acima de Filho)
        startX = sMidX;
        startY = sBottom;
        endX = tMidX;
        endY = tTop;
        flowType = 'vertical';
    } else if (tBottom <= sTop + 10) {
        // Loopback / Retorno para etapa anterior acima
        startX = sRight;
        startY = sMidY;
        endX = tRight;
        endY = tMidY;
        flowType = 'loopback';
    } else {
        // Mesma linha horizontal / lateral
        if (tLeft >= sRight) {
            startX = sRight;
            startY = sMidY;
            endX = tLeft;
            endY = tMidY;
        } else {
            startX = sLeft;
            startY = sMidY;
            endX = tRight;
            endY = tMidY;
        }
        flowType = 'horizontal';
    }

    // Estilo 1: Curva Suave Bézier
    if (estilo === 'curva') {
        const deltaX = (endX - startX) * 0.5;
        const deltaY = (endY - startY) * 0.5;
        return {
            pathData: `M ${startX} ${startY} C ${startX + deltaX} ${startY}, ${endX - deltaX} ${endY}, ${endX} ${endY}`,
            labelPos: { x: (startX + endX) / 2, y: (startY + endY) / 2 }
        };
    }

    // Estilo 2: Reta Direta
    if (estilo === 'reta') {
        return {
            pathData: `M ${startX} ${startY} L ${endX} ${endY}`,
            labelPos: { x: (startX + endX) / 2, y: (startY + endY) / 2 }
        };
    }

    // Estilo 3 (Padrão): Ortogonal com quebras perpendiculares a 90° e cantos arredondados elegantes
    const r = 6;

    if (flowType === 'vertical') {
        if (Math.abs(startX - endX) < 4) {
            return {
                pathData: `M ${startX} ${startY} L ${endX} ${endY}`,
                labelPos: { x: startX + 16, y: (startY + endY) / 2 }
            };
        }

        const midY = Math.round(startY + (endY - startY) / 2);
        const dirX = endX > startX ? 1 : -1;
        const rad = Math.min(r, Math.abs(endX - startX) / 2, Math.abs(midY - startY), Math.abs(endY - midY));

        const pathData = [
            `M ${startX} ${startY}`,
            `L ${startX} ${midY - rad}`,
            `Q ${startX} ${midY} ${startX + rad * dirX} ${midY}`,
            `L ${endX - rad * dirX} ${midY}`,
            `Q ${endX} ${midY} ${endX} ${midY + rad}`,
            `L ${endX} ${endY}`
        ].join(' ');

        return {
            pathData: pathData,
            labelPos: { x: (startX + endX) / 2, y: midY - 6 }
        };
    } else if (flowType === 'horizontal') {
        if (Math.abs(startY - endY) < 4) {
            return {
                pathData: `M ${startX} ${startY} L ${endX} ${endY}`,
                labelPos: { x: (startX + endX) / 2, y: startY - 8 }
            };
        }

        const midX = Math.round(startX + (endX - startX) / 2);
        const dirY = endY > startY ? 1 : -1;
        const dirX = endX > startX ? 1 : -1;
        const rad = Math.min(r, Math.abs(midX - startX), Math.abs(endY - startY) / 2);

        const pathData = [
            `M ${startX} ${startY}`,
            `L ${midX - rad * dirX} ${startY}`,
            `Q ${midX} ${startY} ${midX} ${startY + rad * dirY}`,
            `L ${midX} ${endY - rad * dirY}`,
            `Q ${midX} ${endY} ${midX + rad * dirX} ${endY}`,
            `L ${endX} ${endY}`
        ].join(' ');

        return {
            pathData: pathData,
            labelPos: { x: midX + 10, y: (startY + endY) / 2 }
        };
    } else {
        // Loopback (Retorno superior)
        const loopX = Math.max(sRight, tRight) + 40;
        const pathData = [
            `M ${startX} ${startY}`,
            `L ${loopX - r} ${startY}`,
            `Q ${loopX} ${startY} ${loopX} ${startY - r}`,
            `L ${loopX} ${tMidY + r}`,
            `Q ${loopX} ${tMidY} ${loopX - r} ${tMidY}`,
            `L ${endX} ${endY}`
        ].join(' ');

        return {
            pathData: pathData,
            labelPos: { x: loopX + 12, y: (startY + tMidY) / 2 }
        };
    }
}

function desenharConexoes() {
    const svg = document.getElementById('connectionsLayer');
    const defs = svg.querySelector('defs');
    svg.innerHTML = '';
    svg.appendChild(defs);

    const estilo = topologia.estilo_linha || 'ortogonal';

    topologia.edges.forEach(edge => {
        const sourceNode = topologia.nodes.find(n => n.id === edge.source);
        const targetNode = topologia.nodes.find(n => n.id === edge.target);
        if (!sourceNode || !targetNode) return;

        const sourceEl = document.getElementById(`node-${sourceNode.id}`);
        const targetEl = document.getElementById(`node-${targetNode.id}`);
        if (!sourceEl || !targetEl) return;

        let marker = 'url(#arrowhead)';
        let strokeColor = '#475569';

        if (edge.label?.toLowerCase() === 'sim') {
            marker = 'url(#arrowhead-green)';
            strokeColor = '#10b981';
        } else if (edge.label?.toLowerCase() === 'não') {
            marker = 'url(#arrowhead-red)';
            strokeColor = '#ef4444';
        }

        const { pathData, labelPos } = gerarCaminhoConexao(sourceNode, targetNode, sourceEl, targetEl, edge, estilo);

        const selecionada = edge.id === selectedEdgeId;
        if (selecionada) {
            strokeColor = '#2563eb';
            marker = 'url(#arrowhead)';
        }

        // Área de clique ampliada (traço invisível mais largo) para selecionar / editar a conexão
        const hit = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        hit.setAttribute('d', pathData);
        hit.setAttribute('fill', 'none');
        hit.setAttribute('stroke', 'transparent');
        hit.setAttribute('stroke-width', '14');
        hit.setAttribute('class', 'edge-hit');
        hit.addEventListener('mousedown', (ev) => ev.stopPropagation());
        hit.addEventListener('click', (ev) => { ev.stopPropagation(); selecionarAresta(edge.id); });
        hit.addEventListener('dblclick', (ev) => { ev.stopPropagation(); editarRotuloAresta(edge.id); });
        svg.appendChild(hit);

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', pathData);
        path.setAttribute('fill', 'none');
        path.setAttribute('pointer-events', 'none');
        path.setAttribute('stroke', strokeColor);
        path.setAttribute('stroke-width', selecionada ? '3.6' : '2.2');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        path.setAttribute('marker-end', marker);
        svg.appendChild(path);

        if (edge.label) {
            const textGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            textGroup.setAttribute('class', 'edge-label-group');
            textGroup.addEventListener('mousedown', (ev) => ev.stopPropagation());
            textGroup.addEventListener('click', (ev) => { ev.stopPropagation(); selecionarAresta(edge.id); });
            textGroup.addEventListener('dblclick', (ev) => { ev.stopPropagation(); editarRotuloAresta(edge.id); });

            const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            const textLen = Math.max(26, edge.label.length * 8 + 12);
            labelBg.setAttribute('x', labelPos.x - textLen / 2);
            labelBg.setAttribute('y', labelPos.y - 8);
            labelBg.setAttribute('width', textLen);
            labelBg.setAttribute('height', 16);
            labelBg.setAttribute('rx', 4);
            labelBg.setAttribute('fill', '#ffffff');
            labelBg.setAttribute('stroke', strokeColor);
            labelBg.setAttribute('stroke-width', '1');

            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', labelPos.x);
            text.setAttribute('y', labelPos.y + 3.5);
            text.setAttribute('fill', strokeColor);
            text.setAttribute('font-size', '10px');
            text.setAttribute('font-weight', 'bold');
            text.setAttribute('text-anchor', 'middle');
            text.textContent = edge.label;

            textGroup.appendChild(labelBg);
            textGroup.appendChild(text);
            svg.appendChild(textGroup);
        }
    });
}

// =========================================================================
// CRIAÇÃO RÁPIDA DE TÓPICOS (ATALHOS ENTER E TAB) E MODAL ORGANOGRAMA
// =========================================================================
let ctxNovoBloco = null;

function abrirModalNovoBloco(ctx) {
    if (IS_APPROVED) return;
    ctxNovoBloco = ctx;
    document.getElementById('inputNomeNovoBloco').value = 'Nova Etapa';
    document.getElementById('inputBuscaColab').value = '';
    document.getElementById('listaColaboradoresBusca').innerHTML = '';
    if(ctxNovoBloco.colabSelecionado) delete ctxNovoBloco.colabSelecionado;
    setModoNovoBloco('generico');
    const modalEl = document.getElementById('modalNovoBloco');
    if(!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

function setModoNovoBloco(modo) {
    if (modo === 'generico') {
        document.getElementById('btnModoGenerico').classList.add('active', 'btn-primary');
        document.getElementById('btnModoGenerico').classList.remove('btn-outline-secondary');
        document.getElementById('btnModoColab').classList.remove('active', 'btn-primary');
        document.getElementById('btnModoColab').classList.add('btn-outline-secondary');
        document.getElementById('containerBlocoGenerico').classList.remove('d-none');
        document.getElementById('containerBlocoColab').classList.add('d-none');
    } else {
        document.getElementById('btnModoColab').classList.add('active', 'btn-primary');
        document.getElementById('btnModoColab').classList.remove('btn-outline-secondary');
        document.getElementById('btnModoGenerico').classList.remove('active', 'btn-primary');
        document.getElementById('btnModoGenerico').classList.add('btn-outline-secondary');
        document.getElementById('containerBlocoGenerico').classList.add('d-none');
        document.getElementById('containerBlocoColab').classList.remove('d-none');
        document.getElementById('inputBuscaColab').focus();
    }
}

let searchColabTimeout = null;
let resultadosBuscaColab = [];

// Escolher um colaborador na busca já cria o bloco completo (nome, função, foto e raia do setor)
function escolherColaboradorParaBloco(colab) {
    ctxNovoBloco.colabSelecionado = {
        id: colab.id,
        setorId: colab.setor_id,
        temFoto: !!colab.tem_foto,
        nome: colab.nome_completo || colab.nome,
        cargo: colab.cargo_nome || colab.cargo || '',
        setor: colab.setor_nome || colab.setor || ''
    };
    confirmarAdicionarBloco();
}

function buscarColaboradoresParaBloco(termo) {
    const lista = document.getElementById('listaColaboradoresBusca');
    clearTimeout(searchColabTimeout);
    resultadosBuscaColab = [];
    if (ctxNovoBloco) delete ctxNovoBloco.colabSelecionado;

    if (termo.trim().length < 2) {
        lista.innerHTML = '';
        return;
    }
    lista.innerHTML = '<div class="list-group-item small text-muted border-0"><span class="spinner-border spinner-border-sm me-1"></span> Buscando...</div>';

    searchColabTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`/procedures/api/diagramas/colaboradores/?q=${encodeURIComponent(termo.trim())}`);
            if (!res.ok) throw new Error(res.status);
            const data = await res.json();
            const items = Array.isArray(data.results) ? data.results : [];
            resultadosBuscaColab = items;
            lista.innerHTML = '';

            if (items.length === 0) {
                lista.innerHTML = '<div class="list-group-item small text-muted border-0">Nenhum colaborador encontrado.</div>';
                return;
            }
            items.forEach(colab => {
                const cargoDesc = colab.cargo || '';
                const setorDesc = colab.setor || '';
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action py-1';
                btn.innerHTML = `<div class="fw-bold small">${escapeHtml(colab.nome)}</div>
                                 <div class="text-muted" style="font-size:10px;">${escapeHtml(cargoDesc)}${setorDesc ? ' - ' + escapeHtml(setorDesc) : ''}</div>`;
                btn.onclick = () => escolherColaboradorParaBloco(colab);
                lista.appendChild(btn);
            });
        } catch (e) {
            console.error('Erro na busca de colaboradores', e);
            lista.innerHTML = '<div class="list-group-item small text-danger border-0">Não foi possível buscar colaboradores. Tente novamente.</div>';
        }
    }, 300);
}

// Enter na busca escolhe o primeiro resultado
function teclaBuscaColaborador(e) {
    if (e.key === 'Enter' && resultadosBuscaColab.length > 0) {
        e.preventDefault();
        escolherColaboradorParaBloco(resultadosBuscaColab[0]);
    }
}

// =========================================================================
// POSICIONAMENTO AUTOMÁTICO DE DESCENDENTES (lado a lado, centralizados sob o pai)
// =========================================================================
const GAP_VERTICAL_FILHOS = 90;
const GAP_HORIZONTAL_FILHOS = 40;

function larguraDoNo(node) {
    const el = document.getElementById(`node-${node.id}`);
    if (el && el.offsetWidth) return el.offsetWidth;
    if (node.type === 'start' || node.type === 'end') return 140;
    if (node.type === 'decision') return 110;
    return node.data?.colab ? 200 : 180;
}

function alturaDoNo(node) {
    const el = document.getElementById(`node-${node.id}`);
    if (el && el.offsetHeight) return el.offsetHeight;
    return node.type === 'decision' ? 110 : (node.type === 'start' || node.type === 'end' ? 48 : 64);
}

function filhosDoNo(parentId) {
    const vistos = new Set();
    return topologia.edges
        .filter(e => e.source === parentId)
        .map(e => topologia.nodes.find(n => n.id === e.target))
        .filter(n => n && !vistos.has(n.id) && vistos.add(n.id));
}

// Distribui os filhos em linha, centralizados sob o pai (o bloco novo entra por último)
function alinharFilhosDe(parentId, novoId = null) {
    const parent = topologia.nodes.find(n => n.id === parentId);
    if (!parent) return;
    const filhos = filhosDoNo(parentId);
    if (filhos.length === 0) return;

    filhos.sort((a, b) => ((a.id === novoId) - (b.id === novoId)) || (a.position.x - b.position.x));
    const larguras = filhos.map(larguraDoNo);
    const total = larguras.reduce((soma, w) => soma + w, 0) + GAP_HORIZONTAL_FILHOS * (filhos.length - 1);
    const centroDoPai = parent.position.x + larguraDoNo(parent) / 2;

    let x = Math.max(80, Math.round(centroDoPai - total / 2));
    filhos.forEach((filho, i) => {
        filho.position.x = x;
        x += larguras[i] + GAP_HORIZONTAL_FILHOS;
    });
}

// Coloca um bloco recém-criado como filho de `parent`: mesma linha dos irmãos da mesma raia, abaixo do pai
// (ou dentro da faixa da própria raia) e acomoda as faixas que cresceram (as de baixo descem com seus blocos).
// `faixasAntes` = calcularFaixasRaias(...) obtido ANTES de inserir o bloco.
function inserirFilhoNoLayout(parent, novo, faixasAntes) {
    const lane = novo.data?.lane || 'Geral';
    const laneDoPai = parent.data?.lane || 'Geral';
    const irmaoNaRaia = filhosDoNo(parent.id).find(n => n.id !== novo.id && (n.data?.lane || 'Geral') === lane);

    if (irmaoNaRaia) {
        novo.position.y = irmaoNaRaia.position.y;
    } else if (lane === laneDoPai || !faixasAntes[lane]) {
        novo.position.y = parent.position.y + alturaDoNo(parent) + GAP_VERTICAL_FILHOS;
    } else {
        novo.position.y = Math.round(faixasAntes[lane].top + faixasAntes[lane].height / 2 - 32);
    }

    alinharFilhosDe(parent.id, novo.id);

    // faixas que cresceram empurram as de baixo, junto com os blocos delas
    const depois = calcularFaixasRaias(obterListaRaiasOrdenada());
    topologia.nodes.forEach(n => {
        const l = n.data?.lane || 'Geral';
        if (faixasAntes[l] && depois[l]) n.position.y += depois[l].top - faixasAntes[l].top;
    });
    if (!faixasAntes[lane] && lane !== laneDoPai && !irmaoNaRaia && depois[lane]) {
        novo.position.y = Math.round(depois[lane].top + depois[lane].height / 2 - 32);
    }
}

function ligarFilhoAoPai(parent, novoId) {
    topologia.edges.push({
        id: `e-${parent.id}-${novoId}`,
        source: parent.id,
        target: novoId,
        sourceHandle: 'bottom',
        targetHandle: 'top'
    });
    const parentGrid = topologia.grid_data.find(r => r.stepId === parent.id);
    if (parentGrid) {
        if (!parentGrid.next) parentGrid.next = [];
        parentGrid.next.push({ targetId: novoId });
    }
}

function confirmarAdicionarBloco() {
    const modo = document.getElementById('btnModoGenerico').classList.contains('active') ? 'generico' : 'colab';
    let labelText = 'Nova Etapa';
    let laneText = null;
    let colabData = null;

    if (modo === 'generico') {
        labelText = document.getElementById('inputNomeNovoBloco').value.trim() || 'Nova Etapa';
    } else {
        if (!ctxNovoBloco.colabSelecionado) {
            alert('Selecione um colaborador da lista primeiro.');
            return;
        }
        labelText = ctxNovoBloco.colabSelecionado.nome;
        laneText = raiaParaColaborador(ctxNovoBloco.colabSelecionado.setorId, ctxNovoBloco.colabSelecionado.setor);
        const sel = ctxNovoBloco.colabSelecionado;
        colabData = { id: sel.id, nome: sel.nome, cargo: sel.cargo || '', nomeCurto: false, temFoto: !!sel.temFoto };
    }

    const nextId = gerarProximoNodeId();
    const faixasAntes = calcularFaixasRaias(obterListaRaiasOrdenada());

    if (ctxNovoBloco.type === 'irmao') {
        const refNode = topologia.nodes.find(n => n.id === selectedNodeId) || topologia.nodes[topologia.nodes.length - 1];
        const lane = laneText || refNode?.data?.lane || 'Geral';
        const arestaDoPai = refNode ? topologia.edges.find(e => e.target === refNode.id) : null;
        const pai = arestaDoPai ? topologia.nodes.find(n => n.id === arestaDoPai.source) : null;

        if (pai) {
            // irmão = outro filho do mesmo pai: entra na mesma linha, lado a lado e centralizado sob o pai
            _pushNodeAndGrid(nextId, refNode.position.x + 220, refNode.position.y, lane, labelText, colabData);
            ligarFilhoAoPai(pai, nextId);
            inserirFilhoNoLayout(pai, topologia.nodes.find(n => n.id === nextId), faixasAntes);
        } else {
            // sem pai (bloco raiz): fica à direita, na mesma linha
            const posX = refNode ? refNode.position.x + 220 : 100;
            const posY = refNode ? refNode.position.y : 100;
            _pushNodeAndGrid(nextId, posX, posY, lane, labelText, colabData);
        }
    } else if (ctxNovoBloco.type === 'filho') {
        const parentNode = topologia.nodes.find(n => n.id === selectedNodeId) || topologia.nodes[0];
        if (!parentNode) return;
        const lane = laneText || parentNode.data?.lane || 'Geral';

        _pushNodeAndGrid(nextId, parentNode.position.x, parentNode.position.y + 160, lane, labelText, colabData);
        ligarFilhoAoPai(parentNode, nextId);
        inserirFilhoNoLayout(parentNode, topologia.nodes.find(n => n.id === nextId), faixasAntes);
    } else if (ctxNovoBloco.type === 'adjacente') {
        const parentNode = topologia.nodes.find(n => n.id === ctxNovoBloco.sourceId);
        if (!parentNode) return;
        let posX = parentNode.position.x;
        let posY = parentNode.position.y;
        const dir = ctxNovoBloco.dir;
        
        if (dir === 'right') posX += 220;
        if (dir === 'bottom') posY += 120;
        if (dir === 'left') posX -= 220;

        const lane = laneText || parentNode.data?.lane || 'Geral';
        _pushNodeAndGrid(nextId, posX, posY, lane, labelText, colabData);

        if (dir === 'bottom') {
            // "+" de baixo é um filho: alinhado lado a lado com os demais filhos do bloco
            ligarFilhoAoPai(parentNode, nextId);
            inserirFilhoNoLayout(parentNode, topologia.nodes.find(n => n.id === nextId), faixasAntes);
            renderizarCanvas();
            selecionarNo(nextId);
            dispararAutoSave();
            const modalBaixo = bootstrap.Modal.getInstance(document.getElementById('modalNovoBloco'));
            if (modalBaixo) modalBaixo.hide();
            return;
        }

        topologia.edges.push({
            id: `e-${parentNode.id}-${nextId}`,
            source: parentNode.id,
            target: nextId,
            sourceHandle: dir === 'bottom' ? 'bottom' : (dir === 'left' ? 'left' : 'right'),
            targetHandle: dir === 'bottom' ? 'top' : (dir === 'left' ? 'right' : 'left')
        });

        const parentGrid = topologia.grid_data.find(r => r.stepId === parentNode.id);
        if (parentGrid) {
            if (!parentGrid.next) parentGrid.next = [];
            parentGrid.next.push({ targetId: nextId });
        }
    }

    renderizarCanvas();
    selecionarNo(nextId);
    dispararAutoSave();

    const modalEl = document.getElementById('modalNovoBloco');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
}

function _pushNodeAndGrid(id, x, y, lane, label, colabData) {
    const data = { stepId: id, lane: lane, label: label, customTags: [] };
    if (colabData) data.colab = colabData;
    topologia.nodes.push({
        id: id,
        type: 'process',
        position: { x: x, y: y },
        data: data
    });
    topologia.grid_data.push({
        stepId: id,
        lane: lane,
        type: 'process',
        label: label,
        next: []
    });
}

function adicionarTopicoIrmao() {
    if (IS_APPROVED) return;
    abrirModalNovoBloco({ type: 'irmao' });
}

function adicionarSubtopicoFilho() {
    if (IS_APPROVED) return;
    if (!selectedNodeId || !topologia.nodes.length) {
        adicionarTopicoIrmao();
        return;
    }
    abrirModalNovoBloco({ type: 'filho' });
}

function conectarNosSelecionados() {
    if (IS_APPROVED) return;
    let sourceId = null;
    let targetId = null;
    const ids = [...selectedNodeIds];

    if (ids.length === 2) {
        // Seleção múltipla (Shift + clique): o primeiro selecionado é a origem, o segundo o destino
        [sourceId, targetId] = ids;
    } else if (selectedNodeId) {
        const digitado = prompt(`Conectar nó #${selectedNodeId} ao nó de ID (dica: selecione 2 blocos com Shift + clique):`);
        if (!digitado) return;
        sourceId = selectedNodeId;
        targetId = digitado.trim();
    } else {
        alert("Selecione 2 blocos (Shift + clique): o primeiro é a origem e o segundo o destino.");
        return;
    }

    const targetNode = topologia.nodes.find(n => n.id === targetId);
    if (!targetNode || targetId === sourceId) {
        alert(`Nó #${targetId} não encontrado ou inválido.`);
        return;
    }
    if (topologia.edges.some(e => e.source === sourceId && e.target === targetId)) {
        alert("Esses blocos já estão conectados nesse sentido.");
        return;
    }

    topologia.edges.push({
        id: `e-${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        sourceHandle: 'bottom',
        targetHandle: 'top'
    });

    sincronizarEdgesComGridData();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function excluirNoSelecionado() {
    if (IS_APPROVED || selectedNodeIds.size === 0) return;
    
    selectedNodeIds.forEach(id => {
        topologia.nodes = topologia.nodes.filter(n => n.id !== id);
        topologia.edges = topologia.edges.filter(e => e.source !== id && e.target !== id);
        topologia.grid_data = topologia.grid_data.filter(r => r.stepId !== id);
    });

    desmarcarTodosNos();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function adicionarSubtopicoA(e, sourceId, dir) {
    if (IS_APPROVED) return;
    e.stopPropagation();
    abrirModalNovoBloco({ type: 'adjacente', sourceId: sourceId, dir: dir });
}

// =========================================================================
// MODO OUTLINER (MOTOR HIERÁRQUICO 100% ORIENTADO A DIGITAÇÃO E TABULAÇÕES)
// =========================================================================

/**
 * Calcula a lista linear ordenada da árvore hierárquica (Nós Raízes -> Filhos em profundidade).
 */
function obterEstruturaOutliner() {
    const childrenMap = new Map();
    const parentMap = new Map();
    const inDegree = new Map();

    (topologia.nodes || []).forEach(n => {
        childrenMap.set(n.id, []);
        inDegree.set(n.id, 0);
    });

    (topologia.edges || []).forEach(e => {
        if (childrenMap.has(e.source) && inDegree.has(e.target)) {
            if (!childrenMap.get(e.source).includes(e.target)) {
                childrenMap.get(e.source).push(e.target);
                parentMap.set(e.target, e.source);
                inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
            }
        }
    });

    const items = [];
    const visited = new Set();

    function traverse(nodeId, level) {
        if (visited.has(nodeId)) return;
        visited.add(nodeId);
        const node = topologia.nodes.find(n => n.id === nodeId);
        if (node) {
            items.push({
                node: node,
                id: node.id,
                level: level,
                parentId: parentMap.get(nodeId) || null
            });
            const children = childrenMap.get(nodeId) || [];
            children.forEach(childId => traverse(childId, level + 1));
        }
    }

    // Percorre nós de primeiro nível (sem pai) na ordem definida
    (topologia.nodes || []).forEach(n => {
        if ((inDegree.get(n.id) || 0) === 0) {
            traverse(n.id, 0);
        }
    });

    // Caso haja nós soltos ou loops, inclui no nível raiz
    (topologia.nodes || []).forEach(n => {
        if (!visited.has(n.id)) {
            traverse(n.id, 0);
        }
    });

    return items;
}

/**
 * Renderiza a lista interativa de tópicos com recuos, guias de alinhamento e badges de raia.
 */
function renderizarOutliner(focusNodeId = null, cursorPosition = null) {
    const listEl = document.getElementById('outlinerList');
    if (!listEl) return;
    listEl.innerHTML = '';

    const items = obterEstruturaOutliner();
    const lanes = obterListaRaiasOrdenada();

    if (items.length === 0) {
        listEl.innerHTML = `
            <div class="text-center py-5 text-muted border rounded-3 bg-light">
                <i class="bi bi-list-task fs-1 d-block mb-2 text-primary opacity-50"></i>
                <p class="mb-2 fw-semibold">Nenhum tópico no diagrama ainda.</p>
                <button type="button" class="btn btn-sm btn-primary" onclick="criarProximoItemOutliner(null)">
                    <i class="bi bi-plus-lg me-1"></i> Adicionar Primeiro Tópico
                </button>
            </div>
        `;
        return;
    }

    items.forEach((item, idx) => {
        const node = item.node;
        const level = item.level;
        const safeLabel = escapeHtml(node.data?.label || '');
        const currentLane = node.data?.lane || (lanes[0] || 'Geral');

        const itemEl = document.createElement('div');
        itemEl.className = `outliner-item outliner-level-${Math.min(level, 6)}`;
        itemEl.id = `outliner-row-${node.id}`;
        itemEl.style.paddingLeft = `${level * 28 + 8}px`;

        // Linhas guia de hierarquia para níveis indentados
        let guideLinesHtml = '';
        for (let l = 0; l < level; l++) {
            guideLinesHtml += `<span class="outliner-guide-line" style="left: ${l * 28 + 16}px;"></span>`;
        }

        itemEl.innerHTML = `
            ${guideLinesHtml}
            <div class="outliner-bullet ${level > 0 ? 'sub-bullet' : ''}" title="Nível ${level + 1} (${currentLane})" onclick="selecionarNo('${node.id}')"></div>
            <input type="text" 
                id="outliner-input-${node.id}" 
                class="form-control form-control-sm outliner-input flex-grow-1 ${level === 0 ? 'fw-bold text-dark' : 'fw-medium text-secondary-emphasis'}" 
                value="${safeLabel}" 
                placeholder="Digite o nome do tópico / etapa..."
                ${IS_APPROVED ? 'disabled' : ''}
                oninput="onOutlinerInput('${node.id}', this.value)"
                onkeydown="onOutlinerKeydown(event, '${node.id}', ${idx})"
                onclick="selecionarNo('${node.id}')"
            >
            <div class="dropdown">
                <button class="btn btn-sm btn-light border py-0 px-2 outliner-lane-badge dropdown-toggle" type="button" data-bs-toggle="dropdown" ${IS_APPROVED ? 'disabled' : ''} title="Raia / Setor Responsável">
                    ${escapeHtml(currentLane)}
                </button>
                <ul class="dropdown-menu dropdown-menu-end shadow-sm">
                    <li><h6 class="dropdown-header small text-uppercase">Raia / Setor</h6></li>
                    ${lanes.map(l => `
                        <li>
                            <a class="dropdown-item small d-flex align-items-center justify-content-between ${l === currentLane ? 'active fw-bold' : ''}" href="javascript:void(0)" onclick="alterarRaiaNo('${node.id}', '${escapeHtml(l)}')">
                                ${escapeHtml(l)}
                                ${l === currentLane ? '<i class="bi bi-check2"></i>' : ''}
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </div>
            ${!IS_APPROVED ? `
                <button type="button" class="btn btn-sm btn-link text-danger p-0 outliner-del-btn" onclick="excluirItemOutlinerETrazerFocoAnterior('${node.id}')" title="Excluir este item">
                    <i class="bi bi-x-circle"></i>
                </button>
            ` : ''}
        `;
        listEl.appendChild(itemEl);
    });

    // Restauração de foco e posição de cursor sem interrupção da digitação
    if (focusNodeId) {
        setTimeout(() => {
            const targetInput = document.getElementById(`outliner-input-${focusNodeId}`);
            if (targetInput) {
                targetInput.focus();
                if (cursorPosition !== null && typeof cursorPosition === 'number') {
                    try {
                        targetInput.setSelectionRange(cursorPosition, cursorPosition);
                    } catch (e) {}
                }
            }
        }, 10);
    }
}

/**
 * Atualização em tempo real conforme o usuário digita (sem perda de foco ou delay).
 */
function onOutlinerInput(nodeId, novoTexto) {
    const node = topologia.nodes.find(n => n.id === nodeId);
    if (node) {
        if (!node.data) node.data = {};
        node.data.label = novoTexto;

        // Atualiza visualmente o nó no Canvas se renderizado
        const nodeEl = document.getElementById(`node-${nodeId}`);
        if (nodeEl) {
            const contentEl = nodeEl.querySelector('.fw-semibold') || nodeEl.querySelector('.diamond-content') || nodeEl.querySelector('span');
            if (contentEl) contentEl.textContent = novoTexto || 'Novo Tópico';
        }
    }

    const gridRow = topologia.grid_data.find(r => r.stepId === nodeId);
    if (gridRow) {
        gridRow.label = novoTexto;
    }

    // Verifica autocompletar de colaborador (comando @)
    const inputEl = document.getElementById(`outliner-input-${nodeId}`);
    if (inputEl) {
        checkOutlinerMention(nodeId, novoTexto, inputEl);
    }

    dispararAutoSave();
}

// --- Sistema de Autocompletar Colaboradores via Comando @ ---
let outlinerMentionTimeout = null;
let outlinerMentionNodeId = null;

function checkOutlinerMention(nodeId, text, inputEl) {
    const lastAt = text.lastIndexOf('@');
    if (lastAt >= 0) {
        const termo = text.substring(lastAt + 1);
        if (termo.length >= 2 && !termo.includes(',') && !termo.includes(';')) {
            outlinerMentionNodeId = nodeId;
            clearTimeout(outlinerMentionTimeout);
            outlinerMentionTimeout = setTimeout(async () => {
                try {
                    const res = await fetch(`/procedures/api/diagramas/colaboradores/?q=${encodeURIComponent(termo)}`);
                    if (res.ok) {
                        const data = await res.json();
                        const items = data.results || data;
                        renderizarDropdownMentionOutliner(inputEl, items, text, lastAt);
                    }
                } catch (e) {}
            }, 400);
            return;
        }
    }
    esconderDropdownMentionOutliner();
}

function renderizarDropdownMentionOutliner(inputEl, items, fullText, atIndex) {
    let dropdown = document.getElementById('outlinerMentionDropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'outlinerMentionDropdown';
        dropdown.className = 'list-group shadow-lg position-absolute bg-white rounded-3 border';
        dropdown.style.zIndex = '9999';
        dropdown.style.maxHeight = '240px';
        dropdown.style.overflowY = 'auto';
        dropdown.style.minWidth = '300px';
        document.body.appendChild(dropdown);
        
        document.addEventListener('click', (e) => {
            if (dropdown && !dropdown.contains(e.target) && !e.target.classList.contains('outliner-input')) {
                esconderDropdownMentionOutliner();
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') esconderDropdownMentionOutliner();
        });
    }
    
    dropdown.innerHTML = '';
    if (!items || items.length === 0) {
        esconderDropdownMentionOutliner();
        return;
    }

    dropdown.innerHTML = `<div class="bg-light px-3 py-2 small fw-bold text-muted border-bottom"><i class="bi bi-people-fill me-1"></i> Sugestões de Colaboradores</div>`;

    items.slice(0, 6).forEach(colab => {
        const btn = document.createElement('button');
        btn.className = 'list-group-item list-group-item-action py-2 px-3 border-0 border-bottom';
        const cargoDesc = colab.cargo_nome || colab.cargo || '';
        const setorDesc = colab.setor_nome || colab.setor || '';
        const nome = colab.nome_completo || colab.nome || '';
        
        btn.innerHTML = `<div class="fw-bold text-primary mb-1">${escapeHtml(nome)}</div><div class="text-muted lh-1" style="font-size:11px;">${escapeHtml(cargoDesc)} &bull; ${escapeHtml(setorDesc)}</div>`;
        
        btn.onmousedown = (e) => { // onmousedown dispara antes do blur do input
            e.preventDefault();
            aplicarColaboradorNoOutliner(outlinerMentionNodeId, colab, fullText, atIndex);
        };
        dropdown.appendChild(btn);
    });

    const rect = inputEl.getBoundingClientRect();
    dropdown.style.top = `${rect.bottom + window.scrollY + 4}px`;
    dropdown.style.left = `${rect.left + window.scrollX}px`;
    dropdown.style.width = `${Math.max(300, rect.width)}px`;
    dropdown.classList.remove('d-none');
}

function esconderDropdownMentionOutliner() {
    const d = document.getElementById('outlinerMentionDropdown');
    if (d) d.classList.add('d-none');
}

function aplicarColaboradorNoOutliner(nodeId, colab, fullText, atIndex) {
    esconderDropdownMentionOutliner();
    const node = topologia.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    const cargoDesc = colab.cargo_nome || colab.cargo || '';
    const setorDesc = raiaParaColaborador(colab.setor_id, colab.setor_nome || colab.setor || '') || '';
    const nome = colab.nome_completo || colab.nome;
    
    // Substitui o comando @nome pelo nome real do colaborador
    const novoTexto = fullText.substring(0, atIndex) + nome;
    
    node.data.label = novoTexto;
    
    // Vincula o colaborador ao bloco (nome, função editável e foto)
    node.data.colab = { id: colab.id, nome: nome, cargo: cargoDesc, nomeCurto: false, temFoto: colab.tem_foto !== false };
    
    // Se a raia for Geral ou inexistente, joga para a raia do setor do colaborador
    if (setorDesc && (!node.data.lane || node.data.lane === 'Geral')) {
        node.data.lane = setorDesc;
        const gridRow = topologia.grid_data.find(r => r.stepId === nodeId);
        if (gridRow) gridRow.lane = setorDesc;
    }
    
    // Atualiza no canvas e no próprio input para refletir a tag e o nome
    const inputEl = document.getElementById(`outliner-input-${nodeId}`);
    if (inputEl) inputEl.value = novoTexto;
    
    onOutlinerInput(nodeId, novoTexto); 
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(nodeId, novoTexto.length);
    dispararAutoSave();
}
// --- Fim Sistema de Autocompletar Colaboradores ---

/**
 * Interceptador de teclado para navegação, recuos por Tab e criação ágil de tópicos.
 */
function onOutlinerKeydown(e, nodeId, idx) {
    const input = e.target;
    const cursorPos = input.selectionStart;

    if (e.key === 'Tab') {
        e.preventDefault();
        e.stopPropagation();
        if (e.shiftKey) {
            desrecuarItemOutliner(nodeId, cursorPos);
        } else {
            recuarItemOutliner(nodeId, cursorPos);
        }
    } else if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        criarProximoItemOutliner(nodeId);
    } else if (e.key === 'Backspace') {
        const items = obterEstruturaOutliner();
        const curItem = items.find(it => it.id === nodeId);
        if (cursorPos === 0 && input.selectionEnd === 0) {
            if (curItem && curItem.level > 0) {
                // Se estiver indentado, o primeiro Backspace no início da linha desrecua
                e.preventDefault();
                e.stopPropagation();
                desrecuarItemOutliner(nodeId, 0);
            } else if (!input.value.trim() && items.length > 1) {
                // Se o item estiver vazio no nível raiz, exclui e move o cursor para o anterior
                e.preventDefault();
                e.stopPropagation();
                excluirItemOutlinerETrazerFocoAnterior(nodeId);
            }
        }
    } else if (e.key === 'ArrowUp') {
        if (cursorPos === 0 || e.ctrlKey || e.altKey) {
            e.preventDefault();
            focarItemOutlinerVizinho(nodeId, -1);
        }
    } else if (e.key === 'ArrowDown') {
        if (cursorPos === input.value.length || e.ctrlKey || e.altKey) {
            e.preventDefault();
            focarItemOutlinerVizinho(nodeId, 1);
        }
    }
}

/**
 * Recua o item (aumenta o nível de hierarquia / torna subtópico do item imediatamente anterior).
 */
function recuarItemOutliner(nodeId, cursorPos = null) {
    if (IS_APPROVED) return;
    const items = obterEstruturaOutliner();
    const curIdx = items.findIndex(it => it.id === nodeId);
    if (curIdx <= 0) return; // O primeiro item da lista não pode ser recuado

    const prevItem = items[curIdx - 1];
    const prevNodeId = prevItem.id;

    // Remove conexões de entrada existentes
    topologia.edges = (topologia.edges || []).filter(e => e.target !== nodeId);

    // Cria nova aresta pai -> filho
    topologia.edges.push({
        id: `e-${prevNodeId}-${nodeId}`,
        source: prevNodeId,
        target: nodeId,
        sourceHandle: 'right',
        targetHandle: 'left'
    });

    // Sincroniza topologia e reorganiza canvas
    sincronizarEdgesComGridData();
    recalcularPosicoesCanvasHierarquico();

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(nodeId, cursorPos);
    dispararAutoSave();
}

/**
 * Desrecua o item (diminui o nível de hierarquia / sobe um nível).
 */
function desrecuarItemOutliner(nodeId, cursorPos = null) {
    if (IS_APPROVED) return;
    const items = obterEstruturaOutliner();
    const curItem = items.find(it => it.id === nodeId);
    if (!curItem || curItem.level === 0) return; // Já está na raiz

    const parentId = curItem.parentId;
    const parentItem = items.find(it => it.id === parentId);
    const grandParentId = parentItem ? parentItem.parentId : null;

    // Remove conexão pai -> nó atual
    topologia.edges = (topologia.edges || []).filter(e => e.target !== nodeId);

    if (grandParentId) {
        // Liga ao avô
        topologia.edges.push({
            id: `e-${grandParentId}-${nodeId}`,
            source: grandParentId,
            target: nodeId,
            sourceHandle: 'right',
            targetHandle: 'left'
        });
    }

    sincronizarEdgesComGridData();
    recalcularPosicoesCanvasHierarquico();

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(nodeId, cursorPos);
    dispararAutoSave();
}

/**
 * Cria um novo item logo abaixo do nó de referência (ao pressionar Enter).
 */
function criarProximoItemOutliner(refNodeId = null) {
    if (IS_APPROVED) return;
    const items = obterEstruturaOutliner();
    let parentId = null;
    let lane = 'Geral';
    let insertIndexInNodes = topologia.nodes.length;

    if (refNodeId) {
        const curItem = items.find(it => it.id === refNodeId);
        if (curItem) {
            parentId = curItem.parentId;
            lane = curItem.node.data?.lane || 'Geral';
            const nodeIdx = topologia.nodes.findIndex(n => n.id === refNodeId);
            if (nodeIdx !== -1) insertIndexInNodes = nodeIdx + 1;
        }
    } else if (items.length > 0) {
        const lastItem = items[items.length - 1];
        parentId = lastItem.parentId;
        lane = lastItem.node.data?.lane || 'Geral';
    }

    const nextId = gerarProximoNodeId();
    const newNode = {
        id: nextId,
        type: 'process',
        position: { x: 100, y: 100 },
        data: { stepId: nextId, lane: lane, label: '' }
    };

    topologia.nodes.splice(insertIndexInNodes, 0, newNode);

    if (parentId) {
        topologia.edges.push({
            id: `e-${parentId}-${nextId}`,
            source: parentId,
            target: nextId,
            sourceHandle: 'right',
            targetHandle: 'left'
        });
    }

    sincronizarEdgesComGridData();
    recalcularPosicoesCanvasHierarquico();

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(nextId, 0);
    dispararAutoSave();
}

/**
 * Exclui um item e move o foco para o item anterior.
 */
function excluirItemOutlinerETrazerFocoAnterior(nodeId) {
    if (IS_APPROVED) return;
    const items = obterEstruturaOutliner();
    const curIdx = items.findIndex(it => it.id === nodeId);
    const prevNodeId = curIdx > 0 ? items[curIdx - 1].id : (items[curIdx + 1]?.id || null);

    topologia.nodes = (topologia.nodes || []).filter(n => n.id !== nodeId);
    topologia.edges = (topologia.edges || []).filter(e => e.source !== nodeId && e.target !== nodeId);
    topologia.grid_data = (topologia.grid_data || []).filter(r => r.stepId !== nodeId);

    sincronizarEdgesComGridData();
    recalcularPosicoesCanvasHierarquico();

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(prevNodeId, 9999);
    dispararAutoSave();
}

/**
 * Move o foco do teclado para o item acima (-1) ou abaixo (+1).
 */
function focarItemOutlinerVizinho(nodeId, offset) {
    const items = obterEstruturaOutliner();
    const curIdx = items.findIndex(it => it.id === nodeId);
    if (curIdx === -1) return;

    const targetIdx = curIdx + offset;
    if (targetIdx >= 0 && targetIdx < items.length) {
        const targetId = items[targetIdx].id;
        const targetInput = document.getElementById(`outliner-input-${targetId}`);
        if (targetInput) {
            targetInput.focus();
            const len = targetInput.value.length;
            targetInput.setSelectionRange(len, len);
        }
    }
}

function indentOutlinerItem() {
    if (selectedNodeId) {
        recuarItemOutliner(selectedNodeId);
    } else {
        const items = obterEstruturaOutliner();
        if (items.length > 1) {
            recuarItemOutliner(items[items.length - 1].id);
        }
    }
}

function outdentOutlinerItem() {
    if (selectedNodeId) {
        desrecuarItemOutliner(selectedNodeId);
    } else {
        const items = obterEstruturaOutliner();
        if (items.length > 1) {
            desrecuarItemOutliner(items[items.length - 1].id);
        }
    }
}

function alterarRaiaNo(nodeId, novaRaia) {
    if (IS_APPROVED) return;
    const node = topologia.nodes.find(n => n.id === nodeId);
    if (node) {
        if (!node.data) node.data = {};
        node.data.lane = novaRaia;
    }
    const gridRow = topologia.grid_data.find(r => r.stepId === nodeId);
    if (gridRow) {
        gridRow.lane = novaRaia;
    }
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner(nodeId);
    dispararAutoSave();
}

function gerarProximoNodeId() {
    // Considera nós e linhas da grelha para nunca reutilizar um ID existente (mesmo após exclusões)
    const usados = new Set();
    let maxId = 0;
    [...(topologia.nodes || []).map(n => n.id), ...(topologia.grid_data || []).map(r => r.stepId)].forEach(id => {
        if (id === undefined || id === null) return;
        usados.add(String(id));
        const num = parseInt(id, 10);
        if (!isNaN(num) && num > maxId) maxId = num;
    });
    let candidato = maxId + 1;
    while (usados.has(String(candidato))) candidato++;
    return String(candidato);
}

function sincronizarEdgesComGridData() {
    gerarGridDataPorNodes();
}

function recalcularPosicoesCanvasHierarquico() {
    const items = obterEstruturaOutliner();
    const lanes = obterListaRaiasOrdenada();
    const laneYMap = new Map();
    lanes.forEach((l, idx) => laneYMap.set(l, 40 + idx * 240 + 60));

    items.forEach((it, idx) => {
        const lane = it.node.data?.lane || (lanes[0] || 'Geral');
        const baseY = laneYMap.get(lane) || (100 + idx * 70);
        it.node.position.x = 100 + it.level * 220;
        it.node.position.y = baseY;
    });
}

// =========================================================================
// VISÃO ALTERNATIVA EM TEXTO BRUTO (BULK TEXT COM TABULAÇÕES)
// =========================================================================
function alternarVisualizacaoOutliner(modoVisao) {
    const listContainer = document.getElementById('outlinerListWrapper');
    const textContainer = document.getElementById('outlinerTextWrapper');
    const btnLista = document.getElementById('btnOutlinerVisaoLista');
    const btnTexto = document.getElementById('btnOutlinerVisaoTexto');

    if (modoVisao === 'texto') {
        btnLista.classList.remove('active', 'btn-white');
        btnLista.classList.add('btn-light', 'text-secondary');
        btnTexto.classList.remove('btn-light', 'text-secondary');
        btnTexto.classList.add('active', 'btn-white');

        listContainer.classList.add('d-none');
        textContainer.classList.remove('d-none');
        exportarOutlinerParaTexto();
        setupOutlinerRawTextarea();
    } else {
        btnTexto.classList.remove('active', 'btn-white');
        btnTexto.classList.add('btn-light', 'text-secondary');
        btnLista.classList.remove('btn-light', 'text-secondary');
        btnLista.classList.add('active', 'btn-white');

        textContainer.classList.add('d-none');
        listContainer.classList.remove('d-none');
        renderizarOutliner();
    }
}

function exportarOutlinerParaTexto() {
    const items = obterEstruturaOutliner();
    const lines = items.map(it => {
        const tabs = '\t'.repeat(it.level);
        return `${tabs}${it.node.data?.label || ''}`;
    });
    const textarea = document.getElementById('outlinerRawTextarea');
    if (textarea) {
        textarea.value = lines.join('\n');
    }
}

function importarTextoParaOutliner() {
    if (IS_APPROVED) return;
    const textarea = document.getElementById('outlinerRawTextarea');
    if (!textarea) return;
    const text = textarea.value;
    const rawLines = text.split('\n');

    const lines = [];
    rawLines.forEach(l => {
        if (!l.trim()) return;
        let indent = 0;
        if (l.startsWith('\t')) {
            indent = (l.match(/^\t+/) || [''])[0].length;
        } else if (l.startsWith('    ')) {
            indent = Math.floor((l.match(/^ +/) || [''])[0].length / 4);
        } else if (l.startsWith('  ')) {
            indent = Math.floor((l.match(/^ +/) || [''])[0].length / 2);
        }
        lines.push({ indent: indent, content: l.trim() });
    });

    if (lines.length === 0) return;

    const lanes = obterListaRaiasOrdenada();
    const defaultLane = lanes[0] || 'Geral';

    const newNodes = [];
    const newEdges = [];
    const stack = []; // pilha de { id, level }

    lines.forEach((line, idx) => {
        const nodeId = String(idx + 1);
        const node = {
            id: nodeId,
            type: 'process',
            position: { x: 100 + line.indent * 220, y: 100 + idx * 70 },
            data: { stepId: nodeId, lane: defaultLane, label: line.content }
        };
        newNodes.push(node);

        while (stack.length > 0 && stack[stack.length - 1].level >= line.indent) {
            stack.pop();
        }

        if (stack.length > 0) {
            const parent = stack[stack.length - 1];
            newEdges.push({
                id: `e-${parent.id}-${nodeId}`,
                source: parent.id,
                target: nodeId,
                sourceHandle: 'right',
                targetHandle: 'left'
            });
        }

        stack.push({ id: nodeId, level: line.indent });
    });

    topologia.nodes = newNodes;
    topologia.edges = newEdges;
    sincronizarEdgesComGridData();
    recalcularPosicoesCanvasHierarquico();

    renderizarCanvas();
    renderizarGrelha();
    alternarVisualizacaoOutliner('lista');
    dispararAutoSave();
}

let outlinerTextareaInitialized = false;
function setupOutlinerRawTextarea() {
    const textarea = document.getElementById('outlinerRawTextarea');
    if (!textarea || outlinerTextareaInitialized) return;
    outlinerTextareaInitialized = true;

    textarea.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;

            if (!e.shiftKey) {
                this.value = this.value.substring(0, start) + "\t" + this.value.substring(end);
                this.selectionStart = this.selectionEnd = start + 1;
            } else {
                const before = this.value.substring(0, start);
                const lastBreak = before.lastIndexOf('\n');
                const lineStart = lastBreak === -1 ? 0 : lastBreak + 1;
                if (this.value[lineStart] === '\t') {
                    this.value = this.value.substring(0, lineStart) + this.value.substring(lineStart + 1);
                    this.selectionStart = this.selectionEnd = Math.max(lineStart, start - 1);
                }
            }
        }
    });
}

// =========================================================================
// MODO GRELHA (TABULAR)
// =========================================================================
function renderizarGrelha() {
    const corpo = document.getElementById('corpoTabelaGrelha');
    corpo.innerHTML = '';

    topologia.grid_data.forEach((row, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="text-center font-monospace fw-bold">${row.stepId}</td>
            <td>
                <input type="text" class="form-control form-control-sm" value="${row.lane || ''}" 
                    ${IS_APPROVED ? 'disabled' : ''} onchange="atualizarGrelha(${idx}, 'lane', this.value)">
            </td>
            <td>
                <select class="form-select form-select-sm" ${IS_APPROVED ? 'disabled' : ''} onchange="atualizarGrelha(${idx}, 'type', this.value)">
                    <option value="start" ${row.type === 'start' ? 'selected' : ''}>Início</option>
                    <option value="process" ${row.type === 'process' ? 'selected' : ''}>Processo Padrão</option>
                    <option value="critical_process" ${row.type === 'critical_process' ? 'selected' : ''}>Processo Crítico</option>
                    <option value="decision" ${row.type === 'decision' ? 'selected' : ''}>Decisão</option>
                    <option value="end" ${row.type === 'end' ? 'selected' : ''}>Fim</option>
                </select>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm" value="${row.label || ''}" 
                    ${IS_APPROVED ? 'disabled' : ''} onchange="atualizarGrelha(${idx}, 'label', this.value)">
            </td>
            <td>
                <input type="text" class="form-control form-control-sm font-monospace" value="${row.documentRef || ''}" 
                    placeholder="Ex: FOR.143" ${IS_APPROVED ? 'disabled' : ''} onchange="atualizarGrelha(${idx}, 'documentRef', this.value)">
            </td>
            <td class="text-center">
                <input type="text" class="form-control form-control-sm text-center font-monospace" value="${row.next?.[0]?.targetId || ''}" 
                    placeholder="Ex: 2" ${IS_APPROVED ? 'disabled' : ''} onchange="atualizarConexaoGrelha(${idx}, this.value)">
            </td>
            <td class="text-center">
                ${!IS_APPROVED ? `
                    <button type="button" class="btn btn-outline-danger btn-sm p-1" onclick="removerLinhaGrelha(${idx})">
                        <i class="bi bi-trash"></i>
                    </button>
                ` : '-'}
            </td>
        `;
        corpo.appendChild(tr);
    });
}

function atualizarGrelha(idx, campo, valor) {
    topologia.grid_data[idx][campo] = valor;
    dispararAutoSave();
}

function atualizarConexaoGrelha(idx, targetId) {
    topologia.grid_data[idx].next = targetId ? [{ targetId }] : [];
    dispararAutoSave();
}

function adicionarLinhaGrelha() {
    const nextId = gerarProximoNodeId();
    topologia.grid_data.push({
        stepId: nextId,
        lane: topologia.grid_data[topologia.grid_data.length - 1]?.lane || 'Geral',
        type: 'process',
        label: 'Nova Atividade',
        next: []
    });
    renderizarGrelha();
    dispararAutoSave();

    // o foco vai direto para a descrição da nova etapa (sem o foco "solto" que acionava atalhos globais)
    const campos = document.querySelectorAll('#corpoTabelaGrelha tr:last-child input[type="text"]');
    if (campos.length > 1) { campos[1].focus(); campos[1].select(); }
}

function removerLinhaGrelha(idx) {
    topologia.grid_data.splice(idx, 1);
    renderizarGrelha();
    dispararAutoSave();
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Catálogo global de raias (cor, ordem padrão e setor do RH), vindo do servidor
const RAIAS_CATALOGO = (() => {
    try { return JSON.parse(document.getElementById('raiasCatalogoData').textContent) || []; }
    catch (e) { return []; }
})();

function raiaCatalogoPorNome(nome) {
    const n = (nome || '').trim().toLowerCase();
    return RAIAS_CATALOGO.find(r => r.nome.toLowerCase() === n) || null;
}

function corDaRaia(nome) {
    return raiaCatalogoPorNome(nome)?.cor || '#334155';
}

// Raia do catálogo mapeada ao setor do colaborador; sem mapeamento usa o nome do setor
function raiaParaColaborador(setorId, setorNome) {
    const mapeada = setorId ? RAIAS_CATALOGO.find(r => r.setor_id === setorId) : null;
    return mapeada ? mapeada.nome : (setorNome || null);
}

// Ordem explícita: topologia.lanes (nomes em ordem) + topologia.raias_fixas (raias sem blocos que continuam visíveis).
// Uma raia aparece se tiver blocos ou for fixa. Diagramas antigos (sem "lanes") seguem a ordem de aparição dos blocos.
function obterListaRaiasOrdenada() {
    const usadas = [
        ...(topologia.nodes || []).map(n => n.data?.lane || 'Geral'),
        ...(topologia.grid_data || []).map(r => r.lane || 'Geral')
    ].filter(Boolean);
    const fixas = (topologia.raias_fixas || []).filter(Boolean);
    const visiveis = new Set([...usadas, ...fixas]);
    const lista = [];
    (topologia.lanes || []).forEach(l => { if (l && visiveis.has(l) && !lista.includes(l)) lista.push(l); });
    usadas.forEach(l => { if (!lista.includes(l)) lista.push(l); });
    fixas.forEach(l => { if (!lista.includes(l)) lista.push(l); });
    return lista.length > 0 ? lista : ['Geral'];
}

function fixarOrdemRaias() {
    topologia.lanes = obterListaRaiasOrdenada();
}

// Faixas (top/height) de cada raia, com a mesma regra usada para desenhar o canvas
function calcularFaixasRaias(lanes) {
    const faixas = {};
    let top = 40;
    lanes.forEach(lane => {
        const nodes = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);
        let altura = 220;
        if (nodes.length > 0) {
            const ys = nodes.map(n => n.position.y);
            altura = Math.max(220, (Math.max(...ys) - Math.min(...ys)) + 160);
        }
        faixas[lane] = { top, height: altura };
        top += altura;
    });
    return faixas;
}

// Aplica uma nova ordem de raias mantendo cada bloco dentro da sua faixa (preserva o deslocamento interno)
function aplicarNovaOrdemDeRaias(novaLista) {
    const antes = calcularFaixasRaias(obterListaRaiasOrdenada());
    const depois = calcularFaixasRaias(novaLista);
    topologia.nodes.forEach(n => {
        const l = n.data?.lane || 'Geral';
        if (antes[l] && depois[l]) n.position.y = Math.round(n.position.y - antes[l].top + depois[l].top);
    });
    topologia.lanes = novaLista;
}

// Move um bloco para outra raia: atualiza lane (bloco e grelha), mantém a raia de origem visível se ficar vazia
// e posiciona o bloco dentro da faixa de destino
function moverNoParaRaia(node, nomeRaia) {
    const destino = (nomeRaia || '').trim() || 'Geral';
    const origem = node.data?.lane || 'Geral';
    if (!node.data) node.data = {};
    if (origem === destino) return;

    fixarOrdemRaias();
    const listaAntes = obterListaRaiasOrdenada();
    const faixasAntes = calcularFaixasRaias(listaAntes);

    node.data.lane = destino;
    const row = topologia.grid_data.find(r => r.stepId === node.id);
    if (row) row.lane = destino;

    const origemVazia = !topologia.nodes.some(n => (n.data?.lane || 'Geral') === origem);
    if (origemVazia && origem !== 'Geral') {
        // raias nomeadas continuam visíveis mesmo vazias
        topologia.raias_fixas = [...new Set([...(topologia.raias_fixas || []), origem])];
    }

    const listaDepois = obterListaRaiasOrdenada();
    if (origemVazia && origem === 'Geral') {
        // a raia padrão vazia desaparece: as faixas abaixo sobem junto com seus blocos
        const faixasDepois = calcularFaixasRaias(listaDepois);
        topologia.nodes.forEach(n => {
            const l = n.data?.lane || 'Geral';
            if (n !== node && faixasAntes[l] && faixasDepois[l]) {
                n.position.y = Math.round(n.position.y - faixasAntes[l].top + faixasDepois[l].top);
            }
        });
        topologia.lanes = listaDepois;
    }
    const faixas = calcularFaixasRaias(listaDepois);
    if (faixas[destino]) node.position.y = Math.round(faixas[destino].top + faixas[destino].height / 2 - 32);
}

function preencherSugestoesDeRaias() {
    const lista = document.getElementById('raiasDatalist');
    if (!lista) return;
    const nomes = [...new Set([...RAIAS_CATALOGO.map(r => r.nome), ...obterListaRaiasOrdenada()])];
    lista.innerHTML = nomes.map(n => `<option value="${escapeHtml(n)}"></option>`).join('');
}

function aplicarGrelhaParaCanvas() {
    gerarNodesPorGridData();
    posicionarAutomaticoPorRaias(true);
    renderizarCanvas();
    alternarModoEditor('canvas');
    dispararAutoSave();
}

function gerarNodesPorGridData() {
    const existingMap = new Map();
    topologia.nodes.forEach(n => existingMap.set(n.id, n));
    const oldEdges = topologia.edges || [];

    const lanes = obterListaRaiasOrdenada();

    topologia.nodes = topologia.grid_data.map(r => {
        const existing = existingMap.get(r.stepId);
        return {
            ...(existing || {}),
            id: r.stepId,
            type: r.type,
            position: existing ? { ...existing.position } : { x: 100, y: 100 },
            // Preserva estilo/marcadores (bgColor, customTags, etc.) e sobrescreve só o que a grelha controla
            data: {
                ...(existing?.data || {}),
                stepId: r.stepId,
                lane: r.lane || (lanes[0] || 'Geral'),
                label: r.label,
                documentRef: r.documentRef
            }
        };
    });

    // Reaproveita arestas existentes (id, handles, rótulo) e cria apenas as novas conexões
    const novasEdges = [];
    topologia.grid_data.forEach(r => {
        (r.next || []).forEach((conn, cIdx) => {
            if (!conn.targetId) return;
            const antiga = oldEdges.find(e => e.source === r.stepId && e.target === conn.targetId);
            if (antiga) {
                novasEdges.push({ ...antiga, label: conn.condition !== undefined ? (conn.condition || '') : (antiga.label || '') });
            } else {
                novasEdges.push({
                    id: `e-${r.stepId}-${conn.targetId}-${cIdx}`,
                    source: r.stepId,
                    target: conn.targetId,
                    sourceHandle: r.type === 'decision' && conn.condition?.toLowerCase() === 'não' ? 'right' : 'bottom',
                    targetHandle: 'top',
                    label: conn.condition || ''
                });
            }
        });
    });
    topologia.edges = novasEdges;
}

function gerarGridDataPorNodes() {
    topologia.grid_data = topologia.nodes.map(n => {
        const outEdges = topologia.edges.filter(e => e.source === n.id);
        return {
            stepId: n.id,
            lane: n.data?.lane || 'Geral',
            type: n.type || 'process',
            label: n.data?.label || '',
            documentRef: n.data?.documentRef,
            next: outEdges.map(e => ({ targetId: e.target, condition: e.label }))
        };
    });
}

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
    posicionarAutomaticoPorRaias(true);
    renderizarCanvas();
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
// NAVEGAÇÃO FLUIDA: PAN (ARRASTAR FUNDO/ESPAÇO) E ZOOM INTELIGENTE
// =========================================================================
function setupCanvasNavigation() {
    const viewport = document.getElementById('canvasViewport');
    if (!viewport) return;

    // Início do Pan (Arrasto livre no fundo do Canvas)
    viewport.addEventListener('mousedown', (e) => {
        const isMiddleClick = e.button === 1;
        const isLeftClick = e.button === 0;
        if (!isLeftClick && !isMiddleClick) return;

        const target = e.target;
        const isNode = target.closest('.flow-node');
        const isSwimlaneHeader = target.closest('.swimlane-header-container');

        if (isSwimlaneHeader && !isSpacePressed && !isMiddleClick) {
            return;
        }

        if (isNode && !isSpacePressed && !isMiddleClick) {
            return; // Deixa o arrasto do nó agir
        }

        limparSelecaoAresta();

        // Inicia Panning livre
        isPanning = true;
        panStart = {
            x: e.clientX,
            y: e.clientY,
            scrollLeft: viewport.scrollLeft,
            scrollTop: viewport.scrollTop
        };
        viewport.classList.add('is-panning');
        e.preventDefault();
    });

    // Movimentação durante Pan
    window.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        const dx = e.clientX - panStart.x;
        const dy = e.clientY - panStart.y;
        viewport.scrollLeft = panStart.scrollLeft - dx;
        viewport.scrollTop = panStart.scrollTop - dy;
    });

    // Fim do Pan
    window.addEventListener('mouseup', (e) => {
        if (isPanning) {
            isPanning = false;
            viewport.classList.remove('is-panning');
        }
    });

    // Zoom com Roda do Mouse (Ctrl + Roda ou Pinch Trackpad)
    viewport.addEventListener('wheel', (e) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            const delta = e.deltaY < 0 ? 0.08 : -0.08;
            const newZoom = Math.min(2.0, Math.max(0.25, Math.round((zoomLevel + delta) * 100) / 100));
            if (newZoom !== zoomLevel) {
                aplicarZoom(newZoom, e.clientX, e.clientY);
            }
        }
    }, { passive: false });

    // Atalho de Tecla Espaço (Spacebar Pan)
    window.addEventListener('keydown', (e) => {
        if (modoAtual !== 'canvas' || modalAberto() || !foraDeCampoDeEdicao()) return;
        if (e.code === 'Space' && !isSpacePressed) {
            isSpacePressed = true;
            viewport.classList.add('is-space-held');
        }
    });

    window.addEventListener('keyup', (e) => {
        if (e.code === 'Space') {
            isSpacePressed = false;
            viewport.classList.remove('is-space-held');
        }
    });
}

function aplicarZoom(newZoom, clientX, clientY) {
    const viewport = document.getElementById('canvasViewport');
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();

    const mouseX = (clientX !== undefined ? clientX : rect.left + rect.width / 2) - rect.left + viewport.scrollLeft;
    const mouseY = (clientY !== undefined ? clientY : rect.top + rect.height / 2) - rect.top + viewport.scrollTop;

    const contentX = mouseX / zoomLevel;
    const contentY = mouseY / zoomLevel;

    zoomLevel = Math.max(0.25, Math.min(2.0, Math.round(newZoom * 100) / 100));

    const canvasContent = document.getElementById('canvasContent');
    const canvasSizer = document.getElementById('canvasSizer');
    if (canvasContent) canvasContent.style.transform = `scale(${zoomLevel})`;
    if (canvasSizer) {
        canvasSizer.style.width = `${5000 * zoomLevel}px`;
        canvasSizer.style.height = `${5000 * zoomLevel}px`;
    }

    const newScrollLeft = contentX * zoomLevel - (clientX !== undefined ? clientX - rect.left : rect.width / 2);
    const newScrollTop = contentY * zoomLevel - (clientY !== undefined ? clientY - rect.top : rect.height / 2);
    viewport.scrollLeft = Math.max(0, newScrollLeft);
    viewport.scrollTop = Math.max(0, newScrollTop);

    atualizarIndicadorZoom();
}

function alterarZoomRelativo(delta) {
    const newZoom = Math.min(2.0, Math.max(0.25, Math.round((zoomLevel + delta) * 10) / 10));
    aplicarZoom(newZoom);
}

function atualizarIndicadorZoom() {
    const btn = document.getElementById('btnZoomLabel');
    if (btn) {
        btn.textContent = `${Math.round(zoomLevel * 100)}%`;
    }
}

function enquadrarVisaoCompleta() {
    const viewport = document.getElementById('canvasViewport');
    if (!viewport || topologia.nodes.length === 0) {
        aplicarZoom(1.0);
        viewport?.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
        return;
    }

    const xs = topologia.nodes.map(n => n.position.x);
    const ys = topologia.nodes.map(n => n.position.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs) + 200;
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys) + 120;

    const diagramWidth = Math.max(400, maxX - minX + 120);
    const diagramHeight = Math.max(300, maxY - minY + 120);

    const availableWidth = viewport.clientWidth - 40;
    const availableHeight = viewport.clientHeight - 40;

    const scaleX = availableWidth / diagramWidth;
    const scaleY = availableHeight / diagramHeight;
    let targetZoom = Math.min(1.0, Math.min(scaleX, scaleY));
    targetZoom = Math.max(0.35, Math.min(1.2, Math.round(targetZoom * 20) / 20));

    aplicarZoom(targetZoom);

    setTimeout(() => {
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        const scrollX = Math.max(0, centerX * zoomLevel - viewport.clientWidth / 2);
        const scrollY = Math.max(0, centerY * zoomLevel - viewport.clientHeight / 2);
        viewport.scrollTo({ left: scrollX, top: scrollY, behavior: 'smooth' });
    }, 40);
}

function recentralizarCanvas() {
    const viewport = document.getElementById('canvasViewport');
    if (!viewport || topologia.nodes.length === 0) {
        viewport?.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
        return;
    }

    const xs = topologia.nodes.map(n => n.position.x);
    const ys = topologia.nodes.map(n => n.position.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs) + 200;
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys) + 120;

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const scrollX = Math.max(0, centerX * zoomLevel - viewport.clientWidth / 2);
    const scrollY = Math.max(0, centerY * zoomLevel - viewport.clientHeight / 2);

    viewport.scrollTo({ left: scrollX, top: scrollY, behavior: 'smooth' });
}

// =========================================================================
// GERENCIAMENTO INTERATIVO DE RAIAS
// =========================================================================
function abrirRenomearRaia(encodedLane) {
    if (IS_APPROVED) return;
    const raiaAtual = decodeURIComponent(encodedLane);
    const novoNome = prompt(`Renomear a Raia / Setor "${raiaAtual}" para:`, raiaAtual);
    if (!novoNome || !novoNome.trim() || novoNome.trim() === raiaAtual) return;

    const nomeLimpo = novoNome.trim();
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

    // mantém ordem e raias fixas com o novo nome (sem duplicar quando já existia)
    ['lanes', 'raias_fixas'].forEach(chave => {
        topologia[chave] = [...new Set((topologia[chave] || []).map(l => l === raiaAtual ? nomeLimpo : l))];
    });

    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
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
    const jaNoDiagrama = new Set(obterListaRaiasOrdenada().map(l => l.toLowerCase()));
    const lista = document.getElementById('listaRaiasCatalogo');
    lista.innerHTML = '';

    const disponiveis = RAIAS_CATALOGO.filter(r => !jaNoDiagrama.has(r.nome.toLowerCase()));
    if (disponiveis.length === 0) {
        lista.innerHTML = '<div class="list-group-item small text-muted">Nenhuma raia do catálogo disponível (todas já estão no diagrama ou o catálogo está vazio).</div>';
    }
    disponiveis.forEach(r => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'list-group-item list-group-item-action d-flex align-items-center gap-2';
        btn.innerHTML = `<span style="width:12px;height:22px;border-radius:3px;background:${escapeHtml(r.cor)};flex:0 0 12px;"></span>
                         <span class="fw-semibold">${escapeHtml(r.nome)}</span>
                         ${r.setor_nome ? `<span class="badge bg-light text-dark border ms-auto">${escapeHtml(r.setor_nome)}</span>` : ''}`;
        btn.onclick = () => adicionarRaiaAoDiagrama(r.nome);
        lista.appendChild(btn);
    });

    document.getElementById('inputRaiaLivre').value = '';
    new bootstrap.Modal(document.getElementById('modalNovaRaia')).show();
}

function adicionarRaiaLivre() {
    adicionarRaiaAoDiagrama(document.getElementById('inputRaiaLivre').value);
}

// Insere a raia na posição definida pela ordem padrão do catálogo (raias livres ficam sempre no fim)
function adicionarRaiaAoDiagrama(nome) {
    if (IS_APPROVED) return;
    const nomeLimpo = (nome || '').trim();
    if (!nomeLimpo) return;

    const lanes = obterListaRaiasOrdenada();
    if (lanes.some(l => l.toLowerCase() === nomeLimpo.toLowerCase())) {
        alert(`A raia "${nomeLimpo}" já existe neste diagrama.`);
        return;
    }

    let posicao = lanes.length;
    const cat = raiaCatalogoPorNome(nomeLimpo);
    if (cat) {
        const idx = lanes.findIndex(l => {
            const c = raiaCatalogoPorNome(l);
            return c && c.ordem > cat.ordem;
        });
        if (idx !== -1) posicao = idx;
    }

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
// AUTO-SAVE DE ALTA FREQUÊNCIA (DEBOUNCE 800ms)
// =========================================================================
// =========================================================================
// HISTÓRICO (DESFAZER / REFAZER) - snapshots da topologia, agrupados em janelas de 500 ms
// =========================================================================
const HISTORICO_MAX = 50;
let historicoUndo = [];
let historicoRedo = [];
let historicoBase = null;
let historicoTimer = null;

function iniciarHistorico() {
    historicoBase = JSON.stringify(topologia);
    atualizarBotoesHistorico();
}

function atualizarBotoesHistorico() {
    const u = document.getElementById('btnDesfazer');
    const r = document.getElementById('btnRefazer');
    if (u) u.disabled = historicoUndo.length === 0;
    if (r) r.disabled = historicoRedo.length === 0;
}

function registrarHistorico() {
    clearTimeout(historicoTimer);
    historicoTimer = null;
    if (historicoBase === null) return;
    const atual = JSON.stringify(topologia);
    if (atual === historicoBase) return;
    historicoUndo.push(historicoBase);
    if (historicoUndo.length > HISTORICO_MAX) historicoUndo.shift();
    historicoBase = atual;
    historicoRedo = [];
    atualizarBotoesHistorico();
}

function agendarHistorico() {
    clearTimeout(historicoTimer);
    historicoTimer = setTimeout(registrarHistorico, 500);
}

function restaurarSnapshot(snapshot) {
    topologia = JSON.parse(snapshot);
    if (!topologia.nodes) topologia.nodes = [];
    if (!topologia.edges) topologia.edges = [];
    if (!topologia.grid_data) topologia.grid_data = [];
    if (!topologia.estilo_linha) topologia.estilo_linha = 'ortogonal';
    historicoBase = JSON.stringify(topologia); // após normalizar, para a próxima comparação não gerar passo falso
    selectedNodeId = null;
    selectedNodeIds.clear();
    selectedEdgeId = null;
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    atualizarLabelEstiloLinha();
    atualizarSelecoesVisuais();
    atualizarBotoesHistorico();
    dispararAutoSave();
}

function desfazer() {
    if (IS_APPROVED) return;
    registrarHistorico(); // fecha alterações pendentes antes de voltar
    if (historicoUndo.length === 0) return;
    historicoRedo.push(JSON.stringify(topologia));
    restaurarSnapshot(historicoUndo.pop());
}

function refazer() {
    if (IS_APPROVED) return;
    registrarHistorico();
    if (historicoRedo.length === 0) return;
    historicoUndo.push(JSON.stringify(topologia));
    restaurarSnapshot(historicoRedo.pop());
}

function dispararAutoSave() {
    if (IS_APPROVED || autoSaveConflito) return;
    agendarHistorico();

    const indicator = document.getElementById('saveIndicator');
    indicator.innerHTML = '<span class="text-warning"><i class="bi bi-arrow-repeat spin"></i> Salvando...</span>';

    if (autoSaveTimer) clearTimeout(autoSaveTimer);

    autoSaveTimer = setTimeout(async () => {
        try {
            const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/auto-save/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ dados_topologia: topologia, base_atualizado_em: versaoAtualizadoEm })
            });

            if (resp.ok) {
                const resultado = await resp.json();
                if (resultado.atualizado_em) versaoAtualizadoEm = resultado.atualizado_em;
                indicator.innerHTML = '<span class="text-success"><i class="bi bi-check2-circle"></i> Sincronizado</span>';
            } else if (resp.status === 409) {
                autoSaveConflito = true;
                indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-octagon-fill"></i> Conflito de edição</span>';
                alert("Este diagrama foi alterado em outra aba ou por outro usuário. Para não sobrescrever aquelas alterações, o salvamento foi pausado. Recarregue a página para continuar.");
            } else if (resp.status === 423) {
                indicator.innerHTML = '<span class="text-secondary"><i class="bi bi-lock-fill"></i> Bloqueado (Aprovado)</span>';
            } else {
                indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Erro ao salvar</span>';
            }
        } catch (err) {
            indicator.innerHTML = '<span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Erro de rede</span>';
        }
    }, 800);
}

// =========================================================================
// AÇÕES QMS (SUBMETER, APROVAR, NOVA REVISÃO, EXPORTAR PDF, TEMPLATES)
// =========================================================================
async function submeterParaAprovacao() {
    if (!confirm("Deseja submeter este fluxograma para aprovação formal de qualidade?")) return;

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/submeter/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF_TOKEN }
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível submeter."));
    }
}

async function aprovarVersao() {
    if (!confirm("Atenção: A aprovação tornará esta versão IMUTÁVEL e oficial no QMS. Deseja confirmar?")) return;

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/aprovar/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF_TOKEN }
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível aprovar."));
    }
}

async function devolverParaAjustes() {
    const motivo = prompt("Informe o motivo da devolução ao elaborador (obrigatório):");
    if (motivo === null) return;
    if (motivo.trim().length < 5) {
        alert("Informe um motivo com pelo menos 5 caracteres.");
        return;
    }

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/devolver/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ motivo: motivo.trim() })
    });

    if (resp.ok) {
        location.reload();
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Não foi possível devolver."));
    }
}

function modalNovaRevisao() {
    const modal = new bootstrap.Modal(document.getElementById('modalNovaRevisao'));
    modal.show();
}

async function confirmarNovaRevisao() {
    const motivo = document.getElementById('motivoNovaRevisao').value.trim();
    if (!motivo) {
        alert("Por favor, preencha o motivo da nova revisão.");
        return;
    }

    const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/criar-nova-revisao/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ motivo_revisao: motivo })
    });

    if (resp.ok) {
        const novaVersao = await resp.json();
        window.location.href = `/procedures/diagramas/editor/${novaVersao.id}/`;
    } else {
        const data = await resp.json();
        alert("Erro: " + (data.error || "Falha ao criar nova revisão."));
    }
}

async function exportarPDFDoc071() {
    const btn = event.currentTarget;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Gerando PDF...';
    btn.disabled = true;

    try {
        const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/exportar-pdf-doc071/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({ image_base64: null })
        });

        if (resp.ok) {
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const cd = resp.headers.get('Content-Disposition') || '';
            const m = cd.match(/filename="([^"]+)"/);
            a.download = m ? m[1] : `DOC.071_Rev${String(VERSAO_REVISAO).padStart(2, "0")}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        } else {
            let msg = "Erro ao gerar PDF.";
            try { msg = (await resp.json()).error || msg; } catch (e) {}
            alert(msg);
        }
    } catch (err) {
        alert("Erro de comunicação ao gerar o relatório.");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

async function aplicarTemplateSelecionado(templateId) {
    if (!confirm("Deseja aplicar esta estrutura ao diagrama? A topologia atual não salva será substituída pelo modelo.")) return;

    try {
        const resp = await fetch(`/procedures/api/diagramas-versoes/${VERSAO_ID}/aplicar-template/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ template_id: templateId })
        });

        if (resp.ok) {
            const versaoAtualizada = await resp.json();
            topologia = versaoAtualizada.dados_topologia || { nodes: [], edges: [], grid_data: [] };
            if (versaoAtualizada.atualizado_em) versaoAtualizadoEm = versaoAtualizada.atualizado_em;
            registrarHistorico(); // aplicar modelo também pode ser desfeito
            renderizarCanvas();
            renderizarGrelha();
            renderizarOutliner();
            const modalEl = document.getElementById('modalAplicarTemplate');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        } else {
            const data = await resp.json();
            alert("Erro ao aplicar modelo: " + (data.error || "Tente novamente."));
        }
    } catch (e) {
        alert("Erro de conexão ao carregar modelo.");
    }
}

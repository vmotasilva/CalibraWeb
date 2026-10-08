/* Editor de Diagramas (DOC.071) - módulo "outliner_grelha"
 * Modos Outliner (texto hierárquico) e Grelha DOC.071 (tabela).
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

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
    const setorDesc = raiaParaColaborador(colab.setor_id) || '';
    const nome = colab.nome_completo || colab.nome;
    
    // Substitui o comando @nome pelo nome real do colaborador
    const novoTexto = fullText.substring(0, atIndex) + nome;
    
    node.data.label = novoTexto;
    
    // Vincula o colaborador ao bloco (nome, função editável e foto)
    node.data.colab = { id: colab.id, nome: nome, cargo: cargoDesc, cargoRH: cargoDesc, nomeCurto: false, temFoto: colab.tem_foto !== false };
    
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
    return (topologia.raias_cores || {})[nome] || raiaCatalogoPorNome(nome)?.cor || '#334155';
}

// Raia do catálogo mapeada (por você, na tela de gestão de raias) ao setor do colaborador.
// Sem mapeamento NÃO se inventa uma raia com o nome do setor: o bloco permanece na raia em que estiver.
function raiaParaColaborador(setorId) {
    const mapeada = setorId ? RAIAS_CATALOGO.find(r => r.setor_id === setorId) : null;
    return mapeada ? mapeada.nome : null;
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

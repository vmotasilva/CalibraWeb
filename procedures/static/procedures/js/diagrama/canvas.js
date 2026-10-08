/* Editor de Diagramas (DOC.071) - módulo "canvas"
 * Canvas: renderização dos blocos, arrasto, conexões (SVG), pan e zoom.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// RENDERIZAÇÃO DO CANVAS INTERATIVO
// =========================================================================
function renderizarCanvas() {
    const nodesContainer = document.getElementById('nodesContainer');
    const swimlanesLayer = document.getElementById('swimlanesLayer');
    nodesContainer.innerHTML = '';
    swimlanesLayer.innerHTML = '';

    // 1. Renderiza Raias (Swimlanes) dinamicamente (Alturas ajustáveis)
    const lanes = arvoreAtiva() ? [] : obterListaRaiasOrdenada(); // os modos em árvore não usam raias
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

    // 2. Renderiza Nós (blocos de ramos recolhidos não são desenhados)
    arvoreCache = arvoreAtiva() ? arvoreAtual() : null;
    contextoEstiloCache = DiagramaEstilo.contextoDosNos(arvoreCache || arvoreAtual());
    const escondidos = nosOcultos();
    topologia.nodes.forEach(node => {
        if (escondidos.has(String(node.id))) return;
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
                <span class="rotulo-bloco">${markersHtml}${escapeHtml(node.data.label) || (node.type === 'start' ? 'INÍCIO' : 'FIM')}</span>
                ${node.type === 'start' ? '<div class="handle handle-bottom"></div>' : '<div class="handle handle-top"></div>'}
            `;
        } else if (node.type === 'decision') {
            nodeEl.className = 'flow-node node-decision';
            nodeEl.innerHTML = `
                <div class="diamond-inner">
                    <div class="diamond-content rotulo-bloco">${markersHtml}${escapeHtml(node.data.label) || 'Decisão?'}</div>
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
                            <div class="colab-nome rotulo-bloco">${markersHtml}${escapeHtml(nomeExibicaoColab(colab))}</div>
                            ${cargoHtml}
                            ${subsHtml}
                        </div>
                    </div>`;
            } else {
                corpoHtml = `
                    <div class="fw-semibold small leading-tight mt-1 rotulo-bloco">${markersHtml} ${escapeHtml(node.data.label)}</div>
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

        aplicarEstiloVisualAoNo(nodeEl, node);
        nodeEl.insertAdjacentHTML('beforeend', htmlAlternadorRecolhimento(node));
        nodeEl.addEventListener('dblclick', (e) => iniciarEdicaoNoBloco(e, node));

        nodesContainer.appendChild(nodeEl);
    });

    dimensionarCanvas();
    aplicarFundoDoTema();
    desenharConexoes();
}

// A área do canvas cresce com o diagrama (organogramas grandes passam de 5000 px)
function dimensionarCanvas() {
    let maxX = 0, maxY = 0;
    topologia.nodes.forEach(n => { maxX = Math.max(maxX, n.position.x + 400); maxY = Math.max(maxY, n.position.y + 400); });
    canvasLargura = Math.max(5000, Math.ceil(maxX));
    canvasAltura = Math.max(5000, Math.ceil(maxY));
    ['canvasContent', 'nodesContainer', 'swimlanesLayer', 'connectionsLayer'].forEach(id => {
        const el = document.getElementById(id);
        if (el) { el.style.width = `${canvasLargura}px`; el.style.height = `${canvasAltura}px`; }
    });
    const sizer = document.getElementById('canvasSizer');
    if (sizer) { sizer.style.width = `${canvasLargura * zoomLevel}px`; sizer.style.height = `${canvasAltura * zoomLevel}px`; }
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
            atualizarPainelAparencia(node);

            const panel = document.getElementById('inspectorPanel');
            if (panel.classList.contains('collapsed')) {
                toggleInspectorPanel();
            }
        }
    } else {
        document.getElementById('inspectorEmptyState').classList.remove('d-none');
        document.getElementById('inspectorControls').classList.add('d-none');
        atualizarPainelAparencia(null);
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
// ARRASTO DE NÓS (DRAG & DROP COM SUPORTE A ZOOM)
// =========================================================================
function iniciarArrasto(e, node) {
    if (e.target.classList.contains('handle')) return;
    if (isSpacePressed || e.button === 1) return; // Não arrasta se estiver em modo pan
    isDragging = true;
    activeNode = node;
    arrastoMoveu = false;
    arrastoInicio = { x: e.clientX, y: e.clientY };
    
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

    // nos modos em árvore o clique simples não move o bloco: só um arrasto de verdade (limiar de 5 px)
    if (arvoreAtiva() && !arrastoMoveu) {
        if (Math.hypot(e.clientX - arrastoInicio.x, e.clientY - arrastoInicio.y) < 5) return;
        arrastoMoveu = true;
    }

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
    if (arvoreAtiva()) arvoreAoArrastar(e); // destaca onde o bloco será encaixado (filho / antes / depois)
    else dispararAutoSave();
}

function pararArrasto(e) {
    const arrastado = activeNode;
    const moveu = arrastoMoveu;
    isDragging = false;
    activeNode = null;
    window.removeEventListener('mousemove', onArrasto);
    window.removeEventListener('mouseup', pararArrasto);
    // modos em árvore: soltar sobre outro bloco troca o pai ou reordena os irmãos
    if (arvoreAtiva() && arrastado && moveu && e && e.clientX !== undefined) arvoreAoSoltar(e, arrastado);
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

    // Modo "Árvore (lista)": tronco vertical saindo da base do pai e cotovelo até a lateral do filho
    if (modoLayout() === 'arvore' && (edge.kind || 'hierarquia') === 'hierarquia' && edge.sourceHandle === 'bottom' && edge.targetHandle === 'left') {
        const troncoX = sLeft + 20;
        const raio = Math.max(0, Math.min(6, Math.abs(tMidY - sBottom) / 2, Math.abs(tLeft - troncoX) / 2));
        return {
            pathData: `M ${troncoX} ${sBottom} L ${troncoX} ${tMidY - raio} Q ${troncoX} ${tMidY} ${troncoX + raio} ${tMidY} L ${tLeft} ${tMidY}`,
            labelPos: { x: (troncoX + tLeft) / 2, y: tMidY - 8 }
        };
    }

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
        // fluxo vertical (organogramas): a curva sai e chega na vertical; nos demais casos, na horizontal
        const controles = flowType === 'vertical'
            ? `${startX} ${startY + deltaY}, ${endX} ${endY - deltaY}`
            : `${startX + deltaX} ${startY}, ${endX - deltaX} ${endY}`;
        return {
            pathData: `M ${startX} ${startY} C ${controles}, ${endX} ${endY}`,
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

        // Estilo da linha: o da própria conexão vence o tema; Sim/Não mantêm verde/vermelho (a menos que a cor seja explícita)
        const estCx = estiloEfetivoDaConexao(edge);
        const rotuloSemantico = ['sim', 'não'].includes((edge.label || '').toLowerCase());
        if (estCx.color && (edge.style?.color || !rotuloSemantico)) {
            strokeColor = estCx.color;
            marker = marcadorParaCor(svg, estCx.color, estCx.width);
        }
        const larguraLinha = estCx.width || 2.2;

        const { pathData, labelPos } = gerarCaminhoConexao(sourceNode, targetNode, sourceEl, targetEl, edge, edge.kind === 'relacao' ? 'curva' : (estCx.shape || estilo));

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
        path.setAttribute('stroke-width', String(selecionada ? larguraLinha + 1.4 : larguraLinha));
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        path.setAttribute('marker-end', marker);
        const tracado = estCx.dash ? DiagramaEstilo.dashArray(estCx.dash, larguraLinha) : (edge.kind === 'relacao' ? '7 5' : null); // ligação livre = tracejada
        if (tracado) path.setAttribute('stroke-dasharray', tracado);
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
            const newZoom = Math.min(2.0, Math.max(0.1, Math.round((zoomLevel + delta) * 100) / 100));
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

    zoomLevel = Math.max(0.1, Math.min(2.0, Math.round(newZoom * 100) / 100));

    const canvasContent = document.getElementById('canvasContent');
    const canvasSizer = document.getElementById('canvasSizer');
    if (canvasContent) canvasContent.style.transform = `scale(${zoomLevel})`;
    if (canvasSizer) {
        canvasSizer.style.width = `${canvasLargura * zoomLevel}px`;
        canvasSizer.style.height = `${canvasAltura * zoomLevel}px`;
    }

    const newScrollLeft = contentX * zoomLevel - (clientX !== undefined ? clientX - rect.left : rect.width / 2);
    const newScrollTop = contentY * zoomLevel - (clientY !== undefined ? clientY - rect.top : rect.height / 2);
    viewport.scrollLeft = Math.max(0, newScrollLeft);
    viewport.scrollTop = Math.max(0, newScrollTop);

    atualizarIndicadorZoom();
}

function alterarZoomRelativo(delta) {
    const newZoom = Math.min(2.0, Math.max(0.1, Math.round((zoomLevel + delta) * 10) / 10));
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
    targetZoom = Math.max(0.1, Math.min(1.2, Math.round(targetZoom * 20) / 20));

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

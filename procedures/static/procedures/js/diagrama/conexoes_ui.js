/* Editor de Diagramas - módulo "conexoes_ui"
 * Criar conexões arrastando de um ponto (handle) do bloco até outro bloco e religar as pontas da conexão selecionada.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em EDITOR_JS_MODULOS).
 */

const LADOS = ['top', 'right', 'bottom', 'left'];
let arrastoConexao = null;   // { modo: 'nova' | 'ponta', origemId, ladoOrigem, edge?, ponta?, fixoId? }

function pontoNoCanvas(e) {
    const vp = document.getElementById('canvasViewport');
    const r = vp.getBoundingClientRect();
    return { x: (e.clientX - r.left + vp.scrollLeft) / zoomLevel, y: (e.clientY - r.top + vp.scrollTop) / zoomLevel };
}

// Ponto de ancoragem de um lado do bloco (coordenadas do canvas)
function pontoDoLado(node, lado) {
    const el = document.getElementById(`node-${node.id}`);
    const w = el ? el.offsetWidth : 180;
    const h = el ? el.offsetHeight : 70;
    const { x, y } = node.position;
    return { top: { x: x + w / 2, y }, bottom: { x: x + w / 2, y: y + h }, left: { x, y: y + h / 2 }, right: { x: x + w, y: y + h / 2 } }[lado];
}

function ladoDoHandle(handleEl) {
    return LADOS.find(l => handleEl.classList.contains(`handle-${l}`)) || 'bottom';
}

// Lado do bloco mais próximo do ponto solto
function ladoMaisProximo(node, ponto) {
    let melhor = 'top', menor = Infinity;
    LADOS.forEach(l => {
        const p = pontoDoLado(node, l);
        const d = Math.hypot(p.x - ponto.x, p.y - ponto.y);
        if (d < menor) { menor = d; melhor = l; }
    });
    return melhor;
}

function blocoSobOPonteiro(e) {
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const alvo = el && el.closest ? el.closest('.flow-node') : null;
    return alvo ? topologia.nodes.find(n => `node-${n.id}` === alvo.id) || null : null;
}

function limparDestaqueDeAlvo() {
    document.querySelectorAll('.flow-node.alvo-conexao').forEach(el => el.classList.remove('alvo-conexao'));
}

function desenharLinhaTemporaria(de, para) {
    const svg = document.getElementById('connectionsLayer');
    let linha = document.getElementById('conexaoTemporaria');
    if (!linha) {
        linha = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        linha.id = 'conexaoTemporaria';
        linha.setAttribute('fill', 'none');
        linha.setAttribute('stroke', '#2563eb');
        linha.setAttribute('stroke-width', '2.5');
        linha.setAttribute('stroke-dasharray', '6 4');
        linha.setAttribute('pointer-events', 'none');
        svg.appendChild(linha);
    }
    linha.setAttribute('d', `M ${de.x} ${de.y} L ${para.x} ${para.y}`);
}

// --- criar uma conexão arrastando de um ponto do bloco ------------------------------------------
function iniciarConexaoPorArrasto(e, node, handleEl) {
    if (IS_APPROVED || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    arrastoConexao = { modo: 'nova', origemId: node.id, ladoOrigem: ladoDoHandle(handleEl) };
    comecarArrastoDeConexao(e, pontoDoLado(node, arrastoConexao.ladoOrigem));
}

// --- religar uma ponta da conexão selecionada ---------------------------------------------------
function iniciarReligacaoDaPonta(e, edge, ponta) {
    if (IS_APPROVED || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const fixoId = ponta === 'destino' ? edge.source : edge.target;
    const fixo = topologia.nodes.find(n => n.id === fixoId);
    if (!fixo) return;
    arrastoConexao = { modo: 'ponta', edge, ponta, fixoId };
    const ladoFixo = (ponta === 'destino' ? edge.sourceHandle : edge.targetHandle) || (ponta === 'destino' ? 'bottom' : 'top');
    comecarArrastoDeConexao(e, pontoDoLado(fixo, LADOS.includes(ladoFixo) ? ladoFixo : 'bottom'));
}

function comecarArrastoDeConexao(e, pontoInicial) {
    arrastoConexao.inicio = pontoInicial;
    document.getElementById('canvasViewport').classList.add('conectando');
    desenharLinhaTemporaria(pontoInicial, pontoNoCanvas(e));
    window.addEventListener('mousemove', moverArrastoDeConexao);
    window.addEventListener('mouseup', soltarArrastoDeConexao);
    window.addEventListener('keydown', cancelarArrastoDeConexao, true);
}

function moverArrastoDeConexao(e) {
    if (!arrastoConexao) return;
    desenharLinhaTemporaria(arrastoConexao.inicio, pontoNoCanvas(e));
    limparDestaqueDeAlvo();
    const alvo = blocoSobOPonteiro(e);
    const fixoOuOrigem = arrastoConexao.modo === 'nova' ? arrastoConexao.origemId : arrastoConexao.fixoId;
    if (alvo && alvo.id !== fixoOuOrigem) document.getElementById(`node-${alvo.id}`)?.classList.add('alvo-conexao');
}

function encerrarArrastoDeConexao() {
    window.removeEventListener('mousemove', moverArrastoDeConexao);
    window.removeEventListener('mouseup', soltarArrastoDeConexao);
    window.removeEventListener('keydown', cancelarArrastoDeConexao, true);
    document.getElementById('conexaoTemporaria')?.remove();
    document.getElementById('canvasViewport')?.classList.remove('conectando');
    limparDestaqueDeAlvo();
}

function cancelarArrastoDeConexao(e) {
    if (e.key !== 'Escape' || !arrastoConexao) return;
    e.preventDefault();
    e.stopPropagation();
    arrastoConexao = null;
    encerrarArrastoDeConexao();
}

function soltarArrastoDeConexao(e) {
    const estado = arrastoConexao;
    arrastoConexao = null;
    encerrarArrastoDeConexao();
    if (!estado) return;
    const alvo = blocoSobOPonteiro(e);
    if (!alvo) return;
    const lado = ladoMaisProximo(alvo, pontoNoCanvas(e));
    if (estado.modo === 'nova') criarConexaoEntre(estado.origemId, alvo.id, estado.ladoOrigem, lado);
    else religarPontaDaConexao(estado.edge, estado.ponta, alvo, lado);
}

function atualizarAposMudarConexoes(edgeId, mudouHierarquia) {
    sincronizarEdgesComGridData();
    if (mudouHierarquia && arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    if (edgeId) selecionarAresta(edgeId);
    dispararAutoSave();
}

function criarConexaoEntre(origemId, destinoId, ladoOrigem, ladoDestino) {
    if (IS_APPROVED || origemId === destinoId) return;
    if (topologia.edges.some(e => e.source === origemId && e.target === destinoId)) {
        mostrarAvisoNoEditor('Esses blocos já estão conectados nesse sentido.');
        return;
    }
    let id = `e-${origemId}-${destinoId}`;
    while (topologia.edges.some(e => e.id === id)) id += '-n';
    topologia.edges.push({
        id,
        kind: arvoreAtiva() ? 'relacao' : undefined,   // nos modos em árvore, ligações livres não alteram a hierarquia
        source: origemId,
        target: destinoId,
        sourceHandle: ladoOrigem,
        targetHandle: ladoDestino,
    });
    atualizarAposMudarConexoes(id, false);
}

function religarPontaDaConexao(edge, ponta, alvo, lado) {
    const origem = ponta === 'origem' ? alvo.id : edge.source;
    const destino = ponta === 'destino' ? alvo.id : edge.target;
    if (origem === destino) return;
    if (topologia.edges.some(e => e !== edge && e.source === origem && e.target === destino)) {
        mostrarAvisoNoEditor('Esses blocos já estão conectados nesse sentido.');
        return;
    }
    if (ponta === 'origem') { edge.source = alvo.id; edge.sourceHandle = lado; }
    else { edge.target = alvo.id; edge.targetHandle = lado; }
    atualizarAposMudarConexoes(edge.id, (edge.kind || 'hierarquia') === 'hierarquia');
}

// Pontas da conexão selecionada: círculos arrastáveis (chamado por desenharConexoes)
function desenharPontasDaConexao(svg, edge, pathData) {
    if (IS_APPROVED) return;
    const numeros = (pathData.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
    if (numeros.length < 4) return;
    [['origem', numeros[0], numeros[1]], ['destino', numeros[numeros.length - 2], numeros[numeros.length - 1]]].forEach(([ponta, x, y]) => {
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', x);
        c.setAttribute('cy', y);
        c.setAttribute('r', '7');
        c.setAttribute('class', 'ponta-conexao');
        c.setAttribute('pointer-events', 'all');
        const dica = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        dica.textContent = ponta === 'origem' ? 'Arraste para outro bloco para mudar a origem' : 'Arraste para outro bloco para mudar o destino';
        c.appendChild(dica);
        c.addEventListener('mousedown', ev => iniciarReligacaoDaPonta(ev, edge, ponta));
        svg.appendChild(c);
    });
}

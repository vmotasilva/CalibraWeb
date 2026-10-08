/* Editor de Diagramas (DOC.071) - módulo "blocos"
 * Criação de blocos (modal) e posicionamento automático de descendentes.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// CRIAÇÃO RÁPIDA DE TÓPICOS (ATALHOS ENTER E TAB) E MODAL ORGANOGRAMA
// =========================================================================
let ctxNovoBloco = null;

let raiaNovoBlocoManual = false; // o usuário mexeu no campo de raia da janela?

// Raia do bloco de referência (onde o novo bloco ficaria sem perguntar)
function raiaDeReferenciaDoNovoBloco(ctx) {
    let ref = null;
    if (ctx.type === 'adjacente') ref = topologia.nodes.find(n => n.id === ctx.sourceId);
    else ref = topologia.nodes.find(n => n.id === selectedNodeId) || topologia.nodes[ctx.type === 'filho' ? 0 : topologia.nodes.length - 1];
    return ref?.data?.lane || obterListaRaiasOrdenada()[0] || 'Geral';
}

// Monta o seletor: raias deste diagrama, raias do catálogo ainda não usadas e "nova raia"
function prepararSeletorRaiaNovoBloco(ctx) {
    const bloco = document.getElementById('blocoRaiaNovoBloco');
    const select = document.getElementById('selectRaiaNovoBloco');
    if (!bloco || !select) return;

    const emArvore = typeof arvoreAtiva === 'function' && arvoreAtiva();
    bloco.classList.toggle('d-none', emArvore); // os modos em árvore não usam raias
    raiaNovoBlocoManual = false;
    document.getElementById('inputRaiaNovoBloco').classList.add('d-none');
    document.getElementById('inputRaiaNovoBloco').value = '';
    if (emArvore) return;

    const noDiagrama = obterListaRaiasOrdenada();
    const doCatalogo = RAIAS_CATALOGO.map(r => r.nome).filter(n => !noDiagrama.some(l => l.toLowerCase() === n.toLowerCase()));

    select.innerHTML = '';
    const grupo = (titulo, nomes) => {
        if (nomes.length === 0) return;
        const g = document.createElement('optgroup');
        g.label = titulo;
        nomes.forEach(nome => { const o = document.createElement('option'); o.value = nome; o.textContent = nome; g.appendChild(o); });
        select.appendChild(g);
    };
    grupo('Neste diagrama', noDiagrama);
    grupo('Do catálogo de raias', doCatalogo);
    const nova = document.createElement('option');
    nova.value = '__nova__';
    nova.textContent = 'Nova raia (digitar)...';
    select.appendChild(nova);

    select.value = raiaDeReferenciaDoNovoBloco(ctx);
    if (select.value !== raiaDeReferenciaDoNovoBloco(ctx)) select.selectedIndex = 0;
}

function aoEscolherRaiaNovoBloco() {
    raiaNovoBlocoManual = true;
    const nova = document.getElementById('selectRaiaNovoBloco').value === '__nova__';
    const campo = document.getElementById('inputRaiaNovoBloco');
    campo.classList.toggle('d-none', !nova);
    if (nova) campo.focus();
}

// Raia final do bloco: o que o usuário escolheu na janela; sem escolha manual, a raia mapeada ao setor do
// colaborador (se houver); por fim a raia de referência (valor inicial do campo)
function raiaEscolhidaNoModal(raiaMapeada) {
    const bloco = document.getElementById('blocoRaiaNovoBloco');
    if (!bloco || bloco.classList.contains('d-none')) return raiaMapeada;
    const select = document.getElementById('selectRaiaNovoBloco');
    const valor = select.value === '__nova__' ? document.getElementById('inputRaiaNovoBloco').value.trim() : select.value;
    if (!raiaNovoBlocoManual && raiaMapeada) return raiaMapeada;
    return valor || raiaMapeada || null;
}

// Bloco sem pai/irmão posicionado por regra própria: leva o bloco para dentro da faixa da raia escolhida
function ajustarYNaRaia(node, raiaReferencia) {
    const lane = node.data?.lane || 'Geral';
    if (lane === raiaReferencia) return;
    const faixas = calcularFaixasRaias(obterListaRaiasOrdenada());
    if (faixas[lane]) node.position.y = Math.round(faixas[lane].top + faixas[lane].height / 2 - 32);
}

function abrirModalNovoBloco(ctx) {
    if (IS_APPROVED) return;
    ctxNovoBloco = ctx;
    document.getElementById('inputNomeNovoBloco').value = 'Nova Etapa';
    document.getElementById('inputBuscaColab').value = '';
    document.getElementById('listaColaboradoresBusca').innerHTML = '';
    if(ctxNovoBloco.colabSelecionado) delete ctxNovoBloco.colabSelecionado;
    setModoNovoBloco('generico');
    prepararSeletorRaiaNovoBloco(ctx);
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
        laneText = raiaParaColaborador(ctxNovoBloco.colabSelecionado.setorId);
        const sel = ctxNovoBloco.colabSelecionado;
        colabData = { id: sel.id, nome: sel.nome, cargo: sel.cargo || '', nomeCurto: false, temFoto: !!sel.temFoto };
    }

    laneText = raiaEscolhidaNoModal(laneText); // a janela pergunta em qual raia o bloco ficará

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
            if (refNode) ajustarYNaRaia(topologia.nodes.find(n => n.id === nextId), refNode.data?.lane || 'Geral');
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

        if (dir !== 'bottom') ajustarYNaRaia(topologia.nodes.find(n => n.id === nextId), parentNode.data?.lane || 'Geral');

        if (dir === 'bottom') {
            // "+" de baixo é um filho: alinhado lado a lado com os demais filhos do bloco
            ligarFilhoAoPai(parentNode, nextId);
            inserirFilhoNoLayout(parentNode, topologia.nodes.find(n => n.id === nextId), faixasAntes);
            selecionarNo(nextId);
            if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
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

    if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
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
        kind: arvoreAtiva() ? 'relacao' : undefined, // nos modos em árvore, "Conexão" cria uma ligação livre (fora da hierarquia)
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

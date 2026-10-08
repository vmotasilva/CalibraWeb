/* Editor de Diagramas (DOC.071) - módulo "arvore"
 * Interface dos modos em árvore (Organograma, Lógico e Lista): layout automático, recolher/expandir ramos,
 * arrastar para trocar o pai ou reordenar irmãos, criação rápida de blocos, navegação por setas e copiar/colar de ramos.
 * O cálculo de layout fica em layout_arvore.js (puro e testado em Node); aqui há apenas a ligação com o DOM.
 */

const MODOS_ARVORE = ['organograma', 'logico', 'arvore'];
const ROTULOS_LAYOUT = {
    raias: 'Por raias (fluxograma)',
    organograma: 'Organograma (de cima para baixo)',
    logico: 'Lógico (da esquerda para a direita)',
    arvore: 'Árvore (lista com recuo)',
};

function modoLayout() {
    return topologia.layout_modo || 'raias';
}

function arvoreAtiva() {
    return MODOS_ARVORE.includes(modoLayout());
}

function arvoreAtual() {
    return DiagramaArvore.montarArvore(topologia.nodes, topologia.edges);
}

function nosOcultos() {
    if (!arvoreAtiva()) return new Set();
    return DiagramaArvore.ocultos(topologia.nodes, arvoreCache || arvoreAtual());
}

// Estado visual dos controles de layout (menu, faixas e botões que só valem em um dos modos)
function atualizarUILayout() {
    const modo = modoLayout();
    const container = document.getElementById('editorMainContainer');
    if (container) {
        container.classList.toggle('modo-arvore', arvoreAtiva());
        MODOS_ARVORE.concat('raias').forEach(m => container.classList.toggle(`layout-${m}`, m === modo));
    }
    document.querySelectorAll('[data-layout-modo]').forEach(el => {
        const ativo = el.dataset.layoutModo === modo;
        el.classList.toggle('active', ativo);
        const marca = el.querySelector('.layout-check');
        if (marca) marca.classList.toggle('invisible', !ativo);
    });
    const rotulo = document.getElementById('labelLayoutAtual');
    if (rotulo) rotulo.textContent = ROTULOS_LAYOUT[modo] || modo;
}

// Mede os blocos visíveis no DOM e aplica o layout em árvore (posições e pontos de ligação das conexões)
function aplicarLayoutArvore() {
    if (!arvoreAtiva()) return;
    renderizarCanvas(); // garante o DOM atual para medir

    const tamanhos = {};
    topologia.nodes.forEach(n => {
        const el = document.getElementById(`node-${n.id}`);
        if (el) tamanhos[String(n.id)] = { w: el.offsetWidth, h: el.offsetHeight };
    });

    const resultado = DiagramaArvore.calcularLayout(topologia.nodes, topologia.edges, modoLayout(), tamanhos);
    topologia.nodes.forEach(n => {
        const p = resultado.posicoes[String(n.id)];
        if (p) n.position = { x: p.x, y: p.y };
    });
    topologia.edges.forEach(e => {
        const h = resultado.handles[e.id];
        if (h) { e.sourceHandle = h[0]; e.targetHandle = h[1]; }
    });
    renderizarCanvas();
}

function definirModoLayout(modo) {
    if (IS_APPROVED || !ROTULOS_LAYOUT[modo] || modo === modoLayout()) return;
    if (topologia.nodes.length > 1 &&
        !confirm(`Mudar o layout para "${ROTULOS_LAYOUT[modo]}" reposiciona todos os blocos. Você pode desfazer com Ctrl+Z. Continuar?`)) return;

    topologia.layout_modo = modo;
    if (modo === 'raias') {
        posicionarAutomaticoPorRaias(true);
        renderizarCanvas();
    } else {
        aplicarLayoutArvore();
    }
    atualizarUILayout();
    renderizarGrelha();
    enquadrarVisaoCompleta();
    dispararAutoSave();
}

function reaplicarLayoutDoModo() {
    if (arvoreAtiva()) aplicarLayoutArvore();
    else { renderizarCanvas(); }
}

// ------------------------------------------------------------------ recolher / expandir
function htmlAlternadorRecolhimento(node) {
    if (!arvoreAtiva() || !arvoreCache) return '';
    const filhos = arvoreCache.filhos.get(String(node.id)) || [];
    if (filhos.length === 0) return '';
    const recolhido = !!node.data?.collapsed;
    const escondidos = recolhido ? DiagramaArvore.descendentes(arvoreCache, String(node.id)).size : 0;
    const titulo = recolhido ? `Expandir (${escondidos} bloco(s) ocultos)` : 'Recolher ramo';
    return `<button type="button" class="collapse-toggle ${recolhido ? 'recolhido' : ''}" title="${titulo}"
                    onmousedown="event.stopPropagation()" ondblclick="event.stopPropagation()"
                    onclick="alternarRecolhimento('${escapeHtml(node.id)}', event)">${recolhido ? '+' + escondidos : '&minus;'}</button>`;
}

function alternarRecolhimento(nodeId, ev) {
    if (ev) { ev.stopPropagation(); ev.preventDefault(); }
    const node = topologia.nodes.find(n => String(n.id) === String(nodeId));
    if (!node) return;
    if (!node.data) node.data = {};
    node.data.collapsed = !node.data.collapsed;
    if (node.data.collapsed) {
        // a seleção não pode ficar em um bloco que acabou de ficar oculto
        const ocultosAgora = DiagramaArvore.descendentes(arvoreAtual(), String(node.id));
        if ([...selectedNodeIds].some(id => ocultosAgora.has(String(id)))) selecionarNo(node.id);
    }
    aplicarLayoutArvore();
    dispararAutoSave();
}

function definirRecolhimentoDeTodos(recolher, nivelMinimo) {
    if (!arvoreAtiva()) return;
    const arv = arvoreAtual();
    topologia.nodes.forEach(n => {
        const tem = (arv.filhos.get(String(n.id)) || []).length > 0;
        if (!n.data) n.data = {};
        const nivel = DiagramaArvore.profundidade(arv, String(n.id));
        if (!tem) { delete n.data.collapsed; return; }
        n.data.collapsed = recolher && nivel >= nivelMinimo;
        if (!n.data.collapsed) delete n.data.collapsed;
    });
    desmarcarTodosNos();
    aplicarLayoutArvore();
    enquadrarVisaoCompleta();
    dispararAutoSave();
}

function recolherTodos() { definirRecolhimentoDeTodos(true, 0); }
function expandirTodos() { definirRecolhimentoDeTodos(false, 0); }
function recolherAteNivel(nivel) { definirRecolhimentoDeTodos(true, nivel); }

// ------------------------------------------------------------------ arrastar para reparentar / reordenar
function limparDestaquesDeDrop() {
    document.querySelectorAll('.drop-filho, .drop-antes, .drop-depois').forEach(el => {
        el.classList.remove('drop-filho', 'drop-antes', 'drop-depois');
    });
    ultimoAlvoDrop = null;
}

// Bloco sob o ponteiro (ignorando o arrastado e seus descendentes) e a zona: filho, antes ou depois
function arvoreAlvoDoPonteiro(e, arrastado) {
    const idArrastado = String(arrastado.id);
    const proibidos = DiagramaArvore.descendentes(arvoreAtual(), idArrastado);
    proibidos.add(idArrastado);

    for (const el of document.elementsFromPoint(e.clientX, e.clientY)) {
        const noEl = el.closest ? el.closest('.flow-node') : null;
        if (!noEl) continue;
        const id = noEl.id.replace('node-', '');
        if (proibidos.has(id)) continue;
        const r = noEl.getBoundingClientRect();
        const horizontal = modoLayout() === 'organograma';
        const fracao = horizontal ? (e.clientX - r.left) / r.width : (e.clientY - r.top) / r.height;
        const zona = fracao < 0.25 ? 'antes' : (fracao > 0.75 ? 'depois' : 'filho');
        return { id, zona, el: noEl };
    }
    return null;
}

function arvoreAoArrastar(e) {
    if (!activeNode) return;
    const alvo = arvoreAlvoDoPonteiro(e, activeNode);
    const chave = alvo ? `${alvo.id}:${alvo.zona}` : null;
    if (chave === ultimoAlvoDrop) return;
    limparDestaquesDeDrop();
    if (alvo) {
        alvo.el.classList.add(`drop-${alvo.zona}`);
        ultimoAlvoDrop = chave;
    }
}

function arvoreAoSoltar(e, arrastado) {
    limparDestaquesDeDrop();
    const idArrastado = String(arrastado.id);
    const alvo = arvoreAlvoDoPonteiro(e, arrastado);

    if (alvo) {
        const arv = arvoreAtual();
        const paiDoAlvo = arv.pai.get(alvo.id);
        const irmaosDoAlvo = DiagramaArvore.irmaos(arv, alvo.id);
        let novoPai = alvo.id;
        let antesDe = null;

        if (alvo.zona !== 'filho') {
            novoPai = paiDoAlvo === undefined ? null : paiDoAlvo;
            const idx = irmaosDoAlvo.indexOf(alvo.id);
            antesDe = alvo.zona === 'antes' ? alvo.id : (irmaosDoAlvo[idx + 1] || null);
            if (antesDe === idArrastado) antesDe = irmaosDoAlvo[irmaosDoAlvo.indexOf(idArrastado) + 1] || null;
        }

        const resultado = DiagramaArvore.moverNaArvore(topologia.nodes, topologia.edges, idArrastado, novoPai, antesDe);
        if (resultado.ok) {
            topologia.edges = resultado.arestas;
            if (novoPai === null && alvo.zona !== 'filho') {
                // entre raízes: a ordem das raízes é a ordem dos blocos
                const lista = topologia.nodes;
                const origem = lista.findIndex(n => String(n.id) === idArrastado);
                const [item] = lista.splice(origem, 1);
                const posAlvo = lista.findIndex(n => String(n.id) === alvo.id);
                lista.splice(alvo.zona === 'antes' ? posAlvo : posAlvo + 1, 0, item);
            }
            const alvoNo = topologia.nodes.find(n => String(n.id) === novoPai);
            if (alvoNo && alvoNo.data && alvoNo.data.collapsed) alvoNo.data.collapsed = false; // mostra o recém-chegado
            sincronizarEdgesComGridData();
        }
    }
    // com ou sem mudança de pai, o layout é a fonte da verdade: o bloco volta/encaixa no lugar
    aplicarLayoutArvore();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

// ------------------------------------------------------------------ criação rápida (Enter / Tab nos modos em árvore)
function criarBlocoRapido(tipo) {
    if (IS_APPROVED) return;
    const referencia = noSelecionadoUnico() || topologia.nodes[0] || null;
    const arv = arvoreAtual();

    let pai = null;
    let antesDe = null;
    if (referencia) {
        if (tipo === 'filho') {
            pai = referencia;
        } else {
            const idPai = arv.pai.get(String(referencia.id));
            pai = idPai === undefined ? null : topologia.nodes.find(n => String(n.id) === idPai);
            if (pai) {
                const irmaos = arv.filhos.get(String(pai.id));
                antesDe = irmaos[irmaos.indexOf(String(referencia.id)) + 1] || null; // logo depois do bloco de referência
            }
        }
    }

    const id = gerarProximoNodeId();
    const lane = referencia?.data?.lane || 'Geral';
    _pushNodeAndGrid(id, (referencia?.position.x || 80) + 40, (referencia?.position.y || 60) + 120, lane, 'Novo tópico', null);

    if (pai) {
        if (!pai.data) pai.data = {};
        pai.data.collapsed = false;
        const r = DiagramaArvore.moverNaArvore(topologia.nodes, topologia.edges, id, pai.id, antesDe);
        if (r.ok) topologia.edges = r.arestas;
    }
    sincronizarEdgesComGridData();
    aplicarLayoutArvore();
    renderizarGrelha();
    renderizarOutliner();
    selecionarNo(id);
    dispararAutoSave();
    editarTextoDoNo(id);
}

// ------------------------------------------------------------------ navegação por setas
function navegarSelecao(tecla) {
    const atual = noSelecionadoUnico();
    if (!atual) return false;
    const id = String(atual.id);
    const modo = modoLayout();
    const arv = arvoreAtual();
    const ocultos = nosOcultos();
    const visiveis = lista => (lista || []).filter(i => !ocultos.has(i));
    const irmaos = visiveis(DiagramaArvore.irmaos(arv, id));
    const idx = irmaos.indexOf(id);
    let destino = null;

    if (arvoreAtiva()) {
        const filhos = visiveis(arv.filhos.get(id));
        const pai = arv.pai.get(id);
        const acima = pai === undefined ? null : pai;
        // setas "principais" (nível) e "cruzadas" (irmãos) dependem da direção do layout
        const mapa = {
            organograma: { ArrowDown: filhos[0], ArrowUp: acima, ArrowLeft: irmaos[idx - 1], ArrowRight: irmaos[idx + 1] },
            logico: { ArrowRight: filhos[0], ArrowLeft: acima, ArrowUp: irmaos[idx - 1], ArrowDown: irmaos[idx + 1] },
            arvore: { ArrowRight: filhos[0], ArrowLeft: acima, ArrowUp: anteriorNaLista(arv, id, ocultos), ArrowDown: proximoNaLista(arv, id, ocultos) },
        }[modo];
        destino = mapa ? mapa[tecla] : null;
    }
    if (!destino) destino = vizinhoGeometrico(atual, tecla, ocultos);
    if (!destino) return false;

    selecionarNo(String(destino));
    garantirBlocoVisivel(String(destino));
    return true;
}

function ordemDeLeitura(arv, ocultos) {
    const ordem = [];
    const visitar = i => { if (ocultos.has(i)) return; ordem.push(i); (arv.filhos.get(i) || []).forEach(visitar); };
    arv.raizes.forEach(visitar);
    return ordem;
}
function proximoNaLista(arv, id, ocultos) { const o = ordemDeLeitura(arv, ocultos); return o[o.indexOf(id) + 1] || null; }
function anteriorNaLista(arv, id, ocultos) { const o = ordemDeLeitura(arv, ocultos); const i = o.indexOf(id); return i > 0 ? o[i - 1] : null; }

// Vizinho mais próximo na direção da seta (usado quando não há hierarquia, como nos fluxogramas por raias)
function vizinhoGeometrico(atual, tecla, ocultos) {
    const centro = n => ({ x: n.position.x + larguraDoNo(n) / 2, y: n.position.y + alturaDoNo(n) / 2 });
    const c0 = centro(atual);
    const dir = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] }[tecla];
    if (!dir) return null;
    let melhor = null;
    let melhorDist = Infinity;
    topologia.nodes.forEach(n => {
        if (n.id === atual.id || ocultos.has(String(n.id))) return;
        const c = centro(n);
        const dx = c.x - c0.x, dy = c.y - c0.y;
        const principal = dx * dir[0] + dy * dir[1];
        if (principal <= 0) return;
        const lateral = Math.abs(dx * dir[1] - dy * dir[0]);
        if (lateral > principal * 1.2) return; // fora do cone de ~50°
        const dist = principal + lateral * 2;
        if (dist < melhorDist) { melhorDist = dist; melhor = n.id; }
    });
    return melhor;
}

function garantirBlocoVisivel(nodeId) {
    const viewport = document.getElementById('canvasViewport');
    const el = document.getElementById(`node-${nodeId}`);
    if (!viewport || !el) return;
    const vr = viewport.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    const margem = 60;
    if (er.left < vr.left + margem) viewport.scrollLeft -= (vr.left + margem - er.left);
    else if (er.right > vr.right - margem) viewport.scrollLeft += (er.right - (vr.right - margem));
    if (er.top < vr.top + margem) viewport.scrollTop -= (vr.top + margem - er.top);
    else if (er.bottom > vr.bottom - margem) viewport.scrollTop += (er.bottom - (vr.bottom - margem));
}

function alternarRecolhimentoDaSelecao() {
    const node = noSelecionadoUnico();
    if (!node || !arvoreAtiva()) return;
    if ((arvoreAtual().filhos.get(String(node.id)) || []).length === 0) return;
    alternarRecolhimento(node.id);
}

// ------------------------------------------------------------------ copiar / colar ramo
const CHAVE_AREA_DE_TRANSFERENCIA = 'diagrama_ramo_copiado_v1';
let ramoCopiadoEmMemoria = null;

function copiarRamoSelecionado() {
    const node = noSelecionadoUnico();
    if (!node) return false;
    const arv = arvoreAtual();
    const grupo = new Set([String(node.id), ...DiagramaArvore.descendentes(arv, String(node.id))]);
    const dados = {
        raizId: String(node.id),
        origem: VERSAO_ID,
        nos: JSON.parse(JSON.stringify(topologia.nodes.filter(n => grupo.has(String(n.id))))),
        arestas: JSON.parse(JSON.stringify(topologia.edges.filter(e => grupo.has(String(e.source)) && grupo.has(String(e.target))))),
    };
    ramoCopiadoEmMemoria = dados;
    try { localStorage.setItem(CHAVE_AREA_DE_TRANSFERENCIA, JSON.stringify(dados)); } catch (e) { /* sem armazenamento: usa a memória */ }
    mostrarAvisoNoEditor(`Ramo copiado (${dados.nos.length} bloco${dados.nos.length > 1 ? 's' : ''}). Use Ctrl+V para colar.`);
    return true;
}

function lerRamoCopiado() {
    try {
        const bruto = localStorage.getItem(CHAVE_AREA_DE_TRANSFERENCIA);
        if (bruto) return JSON.parse(bruto);
    } catch (e) { /* ignora */ }
    return ramoCopiadoEmMemoria;
}

function idsEmUso() {
    const usados = new Set();
    topologia.nodes.forEach(n => usados.add(String(n.id)));
    topologia.grid_data.forEach(r => usados.add(String(r.stepId)));
    return usados;
}

// modo: 'filho' (cola dentro do bloco selecionado) ou 'irmao' (cola ao lado dele)
function colarRamo(modo = 'filho') {
    if (IS_APPROVED) return;
    const ramo = lerRamoCopiado();
    if (!ramo || !ramo.nos || ramo.nos.length === 0) {
        mostrarAvisoNoEditor('Nada copiado. Selecione um bloco e use Ctrl+C.');
        return;
    }

    const usados = idsEmUso();
    let contador = 0;
    usados.forEach(id => { const n = parseInt(id, 10); if (!isNaN(n) && n > contador) contador = n; });
    const gerarId = () => { do { contador++; } while (usados.has(String(contador))); usados.add(String(contador)); return String(contador); };

    const clone = DiagramaArvore.clonarRamo(ramo.nos, ramo.arestas, ramo.raizId, gerarId);

    const referencia = noSelecionadoUnico();
    let pai = null;
    let antesDe = null;
    if (referencia) {
        if (modo === 'filho') {
            pai = referencia;
        } else {
            const arv = arvoreAtual();
            const idPai = arv.pai.get(String(referencia.id));
            pai = idPai === undefined ? null : topologia.nodes.find(n => String(n.id) === idPai);
            if (pai) {
                const irmaos = arv.filhos.get(String(pai.id));
                antesDe = irmaos[irmaos.indexOf(String(referencia.id)) + 1] || null;
            }
        }
    }

    // fora dos modos em árvore as cópias ficam deslocadas para não cobrir o original
    const deslocamento = arvoreAtiva() ? 0 : 40;
    clone.nos.forEach(n => {
        n.position = { x: n.position.x + deslocamento, y: n.position.y + deslocamento };
        if (n.data && n.data.lane == null) n.data.lane = 'Geral';
        topologia.nodes.push(n);
    });
    clone.arestas.forEach(a => topologia.edges.push(a));

    if (pai) {
        if (!pai.data) pai.data = {};
        pai.data.collapsed = false;
        const r = DiagramaArvore.moverNaArvore(topologia.nodes, topologia.edges, clone.raizId, pai.id, antesDe);
        if (r.ok) topologia.edges = r.arestas;
    }

    sincronizarEdgesComGridData();
    reaplicarLayoutDoModo();
    renderizarGrelha();
    renderizarOutliner();
    selecionarNo(clone.raizId);
    dispararAutoSave();
    mostrarAvisoNoEditor(`Ramo colado (${clone.nos.length} bloco${clone.nos.length > 1 ? 's' : ''}).`);
}

function duplicarRamoSelecionado() {
    if (IS_APPROVED || !copiarRamoSelecionado()) return;
    colarRamo('irmao');
}

// ------------------------------------------------------------------ aviso discreto (sem alert)
function mostrarAvisoNoEditor(texto) {
    let aviso = document.getElementById('avisoEditor');
    if (!aviso) {
        aviso = document.createElement('div');
        aviso.id = 'avisoEditor';
        aviso.className = 'aviso-editor';
        document.body.appendChild(aviso);
    }
    aviso.textContent = texto;
    aviso.classList.add('visivel');
    clearTimeout(aviso._timer);
    aviso._timer = setTimeout(() => aviso.classList.remove('visivel'), 2600);
}

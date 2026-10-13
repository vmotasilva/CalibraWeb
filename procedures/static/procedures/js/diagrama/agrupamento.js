/* Editor de Diagramas - módulo "agrupamento"
 * Grupos (boundary): moldura com título e cor em volta de um conjunto de blocos, com quadro de resumo opcional.
 * Dados em topologia.grupos = [{ id, titulo, cor, resumo, nos: [ids] }]. A geometria vem de DiagramaGrupos (grupos.js).
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em EDITOR_JS_MODULOS).
 */

const CORES_GRUPO = ['#2563eb', '#059669', '#d97706', '#7c3aed', '#dc2626', '#0891b2'];
let grupoEmEdicao = null;

function hexParaRgba(hex, alfa) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return `rgba(37, 99, 235, ${alfa})`;
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
}

function caixasDosBlocos() {
    const caixas = {};
    topologia.nodes.forEach(n => {
        const el = document.getElementById(`node-${n.id}`);
        if (el) caixas[String(n.id)] = { x: n.position.x, y: n.position.y, w: el.offsetWidth, h: el.offsetHeight };
    });
    return caixas;
}

// Remove de cada grupo os blocos que não existem mais e descarta grupos vazios
function limparGrupos() {
    if (!Array.isArray(topologia.grupos)) return;
    const existentes = new Set(topologia.nodes.map(n => String(n.id)));
    topologia.grupos = topologia.grupos
        .map(g => ({ ...g, nos: (g.nos || []).filter(id => existentes.has(String(id))) }))
        .filter(g => g.nos.length > 0);
}

function grupoPorId(id) {
    return (topologia.grupos || []).find(g => g.id === id) || null;
}

function desenharGrupos() {
    const camada = document.getElementById('gruposLayer');
    if (!camada) return;
    camada.innerHTML = '';
    limparGrupos();
    const grupos = topologia.grupos || [];
    if (grupos.length === 0 || modoAtual !== 'canvas') return;

    const caixas = caixasDosBlocos();
    grupos.forEach((g, i) => {
        const caixa = DiagramaGrupos.caixaDoGrupo(g, caixas, DiagramaGrupos.nivelDeAninhamento(grupos, i, caixas));
        if (!caixa) return;
        const cor = g.cor || CORES_GRUPO[0];
        const contraste = DiagramaEstilo.corDeTextoParaFundo(cor);

        const el = document.createElement('div');
        el.className = 'grupo-boundary';
        el.dataset.grupo = g.id;
        el.style.cssText = `left:${caixa.x}px;top:${caixa.y}px;width:${caixa.w}px;height:${caixa.h}px;` +
            `border-color:${cor};background:${hexParaRgba(cor, 0.07)};`;

        const titulo = document.createElement('div');
        titulo.className = 'grupo-titulo';
        titulo.style.cssText = `background:${cor};color:${contraste};`;
        titulo.textContent = g.titulo || 'Grupo';
        titulo.title = IS_APPROVED ? 'Duplo clique: ver grupo' : 'Clique: selecionar blocos | Arraste: mover o grupo | Duplo clique: configurar';
        titulo.addEventListener('click', e => { e.stopPropagation(); selecionarBlocosDoGrupo(g.id); });
        titulo.addEventListener('dblclick', e => { e.stopPropagation(); abrirModalGrupo(g.id); });
        if (!IS_APPROVED) titulo.addEventListener('mousedown', e => iniciarArrastoGrupo(e, g.id));
        el.appendChild(titulo);
        camada.appendChild(el);

        if ((g.resumo || '').trim()) {
            const r = document.createElement('div');
            r.className = 'grupo-resumo';
            r.style.cssText = `left:${caixa.x + caixa.w + DiagramaGrupos.RESUMO_GAP}px;top:${caixa.y}px;` +
                `width:${DiagramaGrupos.RESUMO_W}px;border-left-color:${cor};`;
            r.textContent = g.resumo;
            r.title = 'Resumo do grupo (duplo clique para editar)';
            r.addEventListener('dblclick', e => { e.stopPropagation(); abrirModalGrupo(g.id); });
            camada.appendChild(r);
        }
    });
}

function selecionarBlocosDoGrupo(id) {
    const g = grupoPorId(id);
    if (!g) return;
    const ids = g.nos.filter(n => topologia.nodes.some(x => x.id === n));
    selectedNodeIds = new Set(ids);
    selectedNodeId = ids[0] || null;
    atualizarSelecoesVisuais();
}

// --- criar / configurar / desfazer ------------------------------------------------
function agruparSelecao() {
    if (IS_APPROVED || modoAtual !== 'canvas') return;
    let ids = Array.from(selectedNodeIds);
    if (ids.length === 1) {
        // um bloco com subordinados: agrupa o ramo inteiro
        const desc = DiagramaArvore.descendentes(arvoreAtual(), String(ids[0]));
        const todos = new Set([String(ids[0]), ...desc]);
        ids = topologia.nodes.filter(n => todos.has(String(n.id))).map(n => n.id);
    }
    if (ids.length < 2) {
        alert('Selecione dois ou mais blocos (Shift + clique) ou um bloco que tenha subordinados para agrupar.');
        return;
    }
    if (!Array.isArray(topologia.grupos)) topologia.grupos = [];
    if (topologia.grupos.length >= 50) { alert('Limite de 50 grupos por diagrama.'); return; }

    let n = topologia.grupos.length + 1;
    while (topologia.grupos.some(g => g.id === `g${n}`)) n++;
    const grupo = {
        id: `g${n}`,
        titulo: `Grupo ${topologia.grupos.length + 1}`,
        cor: CORES_GRUPO[topologia.grupos.length % CORES_GRUPO.length],
        resumo: '',
        nos: ids,
    };
    topologia.grupos.push(grupo);
    desenharGrupos();
    dispararAutoSave();
    abrirModalGrupo(grupo.id);
}

function abrirModalGrupo(id) {
    const g = grupoPorId(id);
    if (!g) return;
    grupoEmEdicao = id;
    document.getElementById('grupoTitulo').value = g.titulo || '';
    document.getElementById('grupoCor').value = g.cor || CORES_GRUPO[0];
    document.getElementById('grupoResumo').value = g.resumo || '';
    document.getElementById('grupoQtd').textContent = g.nos.length;
    document.querySelectorAll('#modalGrupo [data-edicao]').forEach(el => { el.disabled = IS_APPROVED; });
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalGrupo')).show();
}

function salvarGrupo() {
    const g = grupoPorId(grupoEmEdicao);
    if (!g || IS_APPROVED) return;
    g.titulo = document.getElementById('grupoTitulo').value.trim().slice(0, 100) || 'Grupo';
    g.cor = document.getElementById('grupoCor').value;
    g.resumo = document.getElementById('grupoResumo').value.trim().slice(0, 1000);
    bootstrap.Modal.getInstance(document.getElementById('modalGrupo'))?.hide();
    desenharGrupos();
    dispararAutoSave();
}

// Substitui os blocos do grupo pela seleção atual
function usarSelecaoNoGrupo() {
    const g = grupoPorId(grupoEmEdicao);
    if (!g || IS_APPROVED) return;
    if (selectedNodeIds.size < 2) { alert('Selecione dois ou mais blocos no canvas para usar como membros do grupo.'); return; }
    g.nos = Array.from(selectedNodeIds);
    document.getElementById('grupoQtd').textContent = g.nos.length;
    desenharGrupos();
    dispararAutoSave();
}

function desagruparGrupo() {
    const g = grupoPorId(grupoEmEdicao);
    if (!g || IS_APPROVED) return;
    if (!confirm(`Desfazer o grupo "${g.titulo}"? Os blocos permanecem no diagrama.`)) return;
    topologia.grupos = topologia.grupos.filter(x => x.id !== g.id);
    bootstrap.Modal.getInstance(document.getElementById('modalGrupo'))?.hide();
    desenharGrupos();
    dispararAutoSave();
}

// --- mover o grupo inteiro (arrasto pelo título) -----------------------------------
let arrastoGrupo = null;

function iniciarArrastoGrupo(e, id) {
    if (e.button !== 0) return;
    const g = grupoPorId(id);
    if (!g) return;
    const vp = document.getElementById('canvasViewport');
    const r = vp.getBoundingClientRect();
    const membros = topologia.nodes.filter(n => g.nos.includes(n.id));
    arrastoGrupo = {
        membros,
        inicio: { x: e.clientX, y: e.clientY },
        origem: membros.map(n => ({ x: n.position.x, y: n.position.y })),
        moveu: false,
        zoom: zoomLevel,
        rect: r,
    };
    window.addEventListener('mousemove', arrastarGrupo);
    window.addEventListener('mouseup', soltarGrupo);
}

function arrastarGrupo(e) {
    if (!arrastoGrupo) return;
    const a = arrastoGrupo;
    const dx = (e.clientX - a.inicio.x) / a.zoom;
    const dy = (e.clientY - a.inicio.y) / a.zoom;
    if (!a.moveu && Math.hypot(dx, dy) * a.zoom < 5) return;
    if (!a.moveu) { a.moveu = true; limparSelecaoAresta(); }
    const minX = Math.min(...a.origem.map(p => p.x));
    const minY = Math.min(...a.origem.map(p => p.y));
    const ajusteX = Math.max(dx, 20 - minX);
    const ajusteY = Math.max(dy, 20 - minY);
    a.membros.forEach((n, i) => {
        n.position.x = Math.round(a.origem[i].x + ajusteX);
        n.position.y = Math.round(a.origem[i].y + ajusteY);
        const el = document.getElementById(`node-${n.id}`);
        if (el) { el.style.left = `${n.position.x}px`; el.style.top = `${n.position.y}px`; }
    });
    desenharConexoes();
}

function soltarGrupo() {
    window.removeEventListener('mousemove', arrastarGrupo);
    window.removeEventListener('mouseup', soltarGrupo);
    const moveu = arrastoGrupo && arrastoGrupo.moveu;
    arrastoGrupo = null;
    if (moveu) dispararAutoSave();
}

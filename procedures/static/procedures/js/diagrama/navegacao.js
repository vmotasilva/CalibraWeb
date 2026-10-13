/* Editor de Diagramas - módulo "navegacao"
 * Minimapa, barra de status, vistas salvas e modo apresentação (Pitch).
 * Vistas ficam em topologia.vistas = [{ id, nome, zoom, cx, cy }] (centro em coordenadas do canvas).
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em EDITOR_JS_MODULOS).
 */

const MINIMAPA_W = 210;
const MINIMAPA_H = 140;
let minimapaVisivel = true;
let navegacaoAgendada = false;
let apresentacao = null; // { passos, i }

try { minimapaVisivel = localStorage.getItem('diagramaMinimapa') !== '0'; } catch (e) { /* navegador sem storage */ }

// --- atualização agendada (no máximo uma por quadro) -------------------------------
function agendarNavegacao() {
    if (navegacaoAgendada) return;
    navegacaoAgendada = true;
    requestAnimationFrame(() => {
        navegacaoAgendada = false;
        desenharMinimapa();
        atualizarBarraStatus();
    });
}

function centrarVistaEm(cx, cy, suave) {
    const vp = document.getElementById('canvasViewport');
    if (!vp) return;
    vp.scrollTo({
        left: Math.max(0, cx * zoomLevel - vp.clientWidth / 2),
        top: Math.max(0, cy * zoomLevel - vp.clientHeight / 2),
        behavior: suave ? 'smooth' : 'auto',
    });
}

// --- minimapa ---------------------------------------------------------------------
function alternarMinimapa() {
    minimapaVisivel = !minimapaVisivel;
    try { localStorage.setItem('diagramaMinimapa', minimapaVisivel ? '1' : '0'); } catch (e) { /* ignora */ }
    desenharMinimapa();
}

function limitesDoDiagrama(caixas) {
    const retangulos = Object.values(caixas);
    const grupos = topologia.grupos || [];
    grupos.forEach((g, i) => {
        const c = DiagramaGrupos.caixaDoGrupo(g, caixas, DiagramaGrupos.nivelDeAninhamento(grupos, i, caixas));
        if (c) retangulos.push(c);
    });
    if (retangulos.length === 0) return null;
    const x0 = Math.min(...retangulos.map(r => r.x)) - 30;
    const y0 = Math.min(...retangulos.map(r => r.y)) - 30;
    const x1 = Math.max(...retangulos.map(r => r.x + r.w)) + 30;
    const y1 = Math.max(...retangulos.map(r => r.y + r.h)) + 30;
    return { x0, y0, w: x1 - x0, h: y1 - y0 };
}

function desenharMinimapa() {
    const caixaEl = document.getElementById('minimapa');
    const cv = document.getElementById('minimapaCanvas');
    if (!caixaEl || !cv) return;
    const caixas = caixasDosBlocos();
    const lim = limitesDoDiagrama(caixas);
    const visivel = minimapaVisivel && modoAtual === 'canvas' && !apresentacao && lim;
    caixaEl.classList.toggle('d-none', !visivel);
    const menu = document.getElementById('checkMinimapa');
    if (menu) menu.classList.toggle('invisible', !minimapaVisivel);
    if (!visivel) return;

    const dpr = window.devicePixelRatio || 1;
    if (cv.width !== MINIMAPA_W * dpr) { cv.width = MINIMAPA_W * dpr; cv.height = MINIMAPA_H * dpr; }
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, MINIMAPA_W, MINIMAPA_H);

    const s = Math.min(MINIMAPA_W / lim.w, MINIMAPA_H / lim.h);
    const ox = (MINIMAPA_W - lim.w * s) / 2 - lim.x0 * s;
    const oy = (MINIMAPA_H - lim.h * s) / 2 - lim.y0 * s;
    cv._t = { s, ox, oy };

    const grupos = topologia.grupos || [];
    grupos.forEach((g, i) => {
        const c = DiagramaGrupos.caixaDoGrupo(g, caixas, DiagramaGrupos.nivelDeAninhamento(grupos, i, caixas));
        if (!c) return;
        ctx.fillStyle = hexParaRgba(g.cor, 0.12);
        ctx.strokeStyle = g.cor || '#2563eb';
        ctx.lineWidth = 1;
        ctx.fillRect(c.x * s + ox, c.y * s + oy, c.w * s, c.h * s);
        ctx.strokeRect(c.x * s + ox, c.y * s + oy, c.w * s, c.h * s);
    });
    topologia.nodes.forEach(n => {
        const c = caixas[String(n.id)];
        if (!c) return;
        ctx.fillStyle = selectedNodeIds.has(n.id) ? '#2563eb' : '#64748b';
        ctx.fillRect(c.x * s + ox, c.y * s + oy, Math.max(2, c.w * s), Math.max(2, c.h * s));
    });

    const vp = document.getElementById('canvasViewport');
    if (vp) {
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 1.5;
        ctx.fillStyle = 'rgba(239, 68, 68, 0.08)';
        const vx = (vp.scrollLeft / zoomLevel) * s + ox;
        const vy = (vp.scrollTop / zoomLevel) * s + oy;
        const vw = (vp.clientWidth / zoomLevel) * s;
        const vh = (vp.clientHeight / zoomLevel) * s;
        ctx.fillRect(vx, vy, vw, vh);
        ctx.strokeRect(vx, vy, vw, vh);
    }
}

function iniciarMinimapa() {
    const cv = document.getElementById('minimapaCanvas');
    if (!cv) return;
    const irPara = e => {
        const t = cv._t;
        if (!t) return;
        const r = cv.getBoundingClientRect();
        const x = (e.clientX - r.left) * (MINIMAPA_W / r.width);
        const y = (e.clientY - r.top) * (MINIMAPA_H / r.height);
        centrarVistaEm((x - t.ox) / t.s, (y - t.oy) / t.s, false);
    };
    let arrastando = false;
    cv.addEventListener('mousedown', e => { arrastando = true; irPara(e); e.preventDefault(); });
    window.addEventListener('mousemove', e => { if (arrastando) irPara(e); });
    window.addEventListener('mouseup', () => { arrastando = false; });

    const vp = document.getElementById('canvasViewport');
    if (vp) vp.addEventListener('scroll', agendarNavegacao, { passive: true });
    window.addEventListener('resize', agendarNavegacao);
}

// --- barra de status --------------------------------------------------------------
function atualizarBarraStatus() {
    const barra = document.getElementById('barraStatus');
    if (!barra) return;
    const emArvore = typeof arvoreAtiva === 'function' && arvoreAtiva();
    const partes = [
        `<span><i class="bi bi-diagram-3"></i> ${topologia.nodes.length} bloco${topologia.nodes.length === 1 ? '' : 's'}</span>`,
        `<span><i class="bi bi-share"></i> ${topologia.edges.length} conexõe${topologia.edges.length === 1 ? '' : 's'}</span>`,
    ];
    if (!emArvore) partes.push(`<span><i class="bi bi-layout-three-columns"></i> ${obterListaRaiasOrdenada().length} raia(s)</span>`);
    const grupos = (topologia.grupos || []).length;
    if (grupos) partes.push(`<span><i class="bi bi-bounding-box"></i> ${grupos} grupo${grupos === 1 ? '' : 's'}</span>`);
    if (selectedNodeIds.size) partes.push(`<span class="text-primary fw-semibold"><i class="bi bi-cursor"></i> ${selectedNodeIds.size} selecionado${selectedNodeIds.size === 1 ? '' : 's'}</span>`);
    partes.push(`<span class="ms-auto"><i class="bi bi-layout-wtf"></i> ${escapeHtml(ROTULOS_LAYOUT[modoLayout()] || '')}</span>`);
    partes.push(`<span><i class="bi bi-zoom-in"></i> ${Math.round(zoomLevel * 100)}%</span>`);
    barra.innerHTML = partes.join('');
}

// --- vistas salvas ----------------------------------------------------------------
function renderizarMenuVistas() {
    const lista = document.getElementById('listaVistas');
    if (!lista) return;
    const vistas = topologia.vistas || [];
    lista.innerHTML = '';
    if (vistas.length === 0) {
        lista.innerHTML = '<div class="px-3 py-1 small text-muted">Nenhuma vista salva.</div>';
        return;
    }
    vistas.forEach(v => {
        const linha = document.createElement('div');
        linha.className = 'dropdown-item d-flex align-items-center gap-2 py-1';
        linha.innerHTML = `<a href="javascript:void(0)" class="flex-grow-1 text-decoration-none text-reset"><i class="bi bi-camera-video me-2"></i>${escapeHtml(v.nome)}</a>` +
            (IS_APPROVED ? '' : '<button type="button" class="btn btn-sm btn-link text-danger p-0" title="Excluir vista"><i class="bi bi-trash"></i></button>');
        linha.querySelector('a').onclick = () => irParaVista(v.id);
        const lixo = linha.querySelector('button');
        if (lixo) lixo.onclick = e => { e.stopPropagation(); excluirVista(v.id); };
        lista.appendChild(linha);
    });
}

function salvarVistaAtual() {
    if (IS_APPROVED) return;
    const vp = document.getElementById('canvasViewport');
    if (!vp) return;
    if (!Array.isArray(topologia.vistas)) topologia.vistas = [];
    if (topologia.vistas.length >= 20) { alert('Limite de 20 vistas por diagrama.'); return; }
    const nome = (prompt('Nome da vista:', `Vista ${topologia.vistas.length + 1}`) || '').trim().slice(0, 60);
    if (!nome) return;
    let n = topologia.vistas.length + 1;
    while (topologia.vistas.some(v => v.id === `v${n}`)) n++;
    topologia.vistas.push({
        id: `v${n}`,
        nome,
        zoom: zoomLevel,
        cx: Math.round((vp.scrollLeft + vp.clientWidth / 2) / zoomLevel),
        cy: Math.round((vp.scrollTop + vp.clientHeight / 2) / zoomLevel),
    });
    renderizarMenuVistas();
    dispararAutoSave();
}

function irParaVista(id) {
    const v = (topologia.vistas || []).find(x => x.id === id);
    if (!v) return;
    aplicarZoom(v.zoom);
    setTimeout(() => centrarVistaEm(v.cx, v.cy, true), 30);
}

function excluirVista(id) {
    if (IS_APPROVED) return;
    topologia.vistas = (topologia.vistas || []).filter(v => v.id !== id);
    renderizarMenuVistas();
    dispararAutoSave();
}

// --- apresentação (Pitch) ---------------------------------------------------------
function rotuloDoBloco(id) {
    const n = topologia.nodes.find(x => String(x.id) === String(id));
    if (!n) return '';
    return (n.data?.colab ? nomeExibicaoColab(n.data.colab) : n.data?.label) || String(n.id);
}

function iniciarApresentacao() {
    if (modoAtual !== 'canvas' || apresentacao) return;
    const vistas = topologia.vistas || [];
    let passos;
    if (vistas.length > 0) {
        passos = vistas.map(v => ({ vista: v, rotulo: v.nome }));
    } else {
        const arvore = DiagramaArvore.aplicarOrdemManual(DiagramaArvore.montarArvore(topologia.nodes, topologia.edges), topologia.nodes);
        passos = DiagramaGrupos.sequenciaDeApresentacao(arvore, nosOcultos())
            .map(id => ({ id, filhos: arvore.filhos.get(id) || [], rotulo: rotuloDoBloco(id) }));
    }
    if (passos.length === 0) return;

    apresentacao = { passos, i: 0 };
    desmarcarTodosNos();
    const container = document.getElementById('viewCanvasContainer');
    container.classList.add('pitch-ativo');
    document.getElementById('pitchBarra').classList.remove('d-none');
    document.addEventListener('keydown', teclasApresentacao, true);
    document.addEventListener('fullscreenchange', aoMudarTelaCheia);
    if (container.requestFullscreen) container.requestFullscreen().catch(() => { /* segue sem tela cheia */ });
    desenharMinimapa();
    irParaPasso(0);
}

function irParaPasso(i) {
    if (!apresentacao) return;
    const total = apresentacao.passos.length;
    apresentacao.i = Math.max(0, Math.min(total - 1, i));
    const passo = apresentacao.passos[apresentacao.i];
    document.getElementById('pitchContador').textContent = `${apresentacao.i + 1} / ${total}`;
    document.getElementById('pitchRotulo').textContent = passo.rotulo || '';

    document.querySelectorAll('.flow-node').forEach(el => el.classList.remove('pitch-dim', 'pitch-foco', 'pitch-filho'));
    if (passo.vista) {
        aplicarZoom(passo.vista.zoom);
        setTimeout(() => centrarVistaEm(passo.vista.cx, passo.vista.cy, true), 30);
        return;
    }

    const foco = [String(passo.id), ...passo.filhos.map(String)];
    const caixas = caixasDosBlocos();
    const alvo = foco.map(id => caixas[id]).filter(Boolean);
    if (alvo.length === 0) return;
    const x0 = Math.min(...alvo.map(c => c.x)), y0 = Math.min(...alvo.map(c => c.y));
    const x1 = Math.max(...alvo.map(c => c.x + c.w)), y1 = Math.max(...alvo.map(c => c.y + c.h));
    const vp = document.getElementById('canvasViewport');
    const zoom = Math.max(0.3, Math.min(1.3,
        Math.min((vp.clientWidth - 160) / (x1 - x0), (vp.clientHeight - 200) / (y1 - y0))));
    aplicarZoom(Math.round(zoom * 20) / 20);
    setTimeout(() => centrarVistaEm((x0 + x1) / 2, (y0 + y1) / 2, true), 30);

    document.querySelectorAll('.flow-node').forEach(el => {
        const id = el.id.replace('node-', '');
        if (foco.includes(id)) el.classList.add(id === String(passo.id) ? 'pitch-foco' : 'pitch-filho');
        else el.classList.add('pitch-dim');
    });
}

function teclasApresentacao(e) {
    if (!apresentacao) return;
    const proximo = ['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'];
    const anterior = ['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'];
    if (proximo.includes(e.key)) irParaPasso(apresentacao.i + 1);
    else if (anterior.includes(e.key)) irParaPasso(apresentacao.i - 1);
    else if (e.key === 'Home') irParaPasso(0);
    else if (e.key === 'End') irParaPasso(apresentacao.passos.length - 1);
    else if (e.key === 'Escape') { encerrarApresentacao(); }
    else return;
    e.preventDefault();
    e.stopPropagation();
}

function aoMudarTelaCheia() {
    if (!apresentacao) return;
    if (!document.fullscreenElement) { encerrarApresentacao(true); return; }
    setTimeout(() => irParaPasso(apresentacao.i), 250); // a área mudou de tamanho
}

function encerrarApresentacao(jaSaiuDaTelaCheia) {
    if (!apresentacao) return;
    apresentacao = null;
    document.removeEventListener('keydown', teclasApresentacao, true);
    document.removeEventListener('fullscreenchange', aoMudarTelaCheia);
    document.getElementById('viewCanvasContainer').classList.remove('pitch-ativo');
    document.getElementById('pitchBarra').classList.add('d-none');
    document.querySelectorAll('.flow-node').forEach(el => el.classList.remove('pitch-dim', 'pitch-foco', 'pitch-filho'));
    if (!jaSaiuDaTelaCheia && document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {});
    agendarNavegacao();
}

iniciarMinimapa();
renderizarMenuVistas();
agendarNavegacao();

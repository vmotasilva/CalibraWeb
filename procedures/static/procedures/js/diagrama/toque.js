// =========================================================================
// TOQUE (CELULAR/TABLET): arrastar blocos e alças com um dedo, pinça para o zoom e painel como gaveta.
// O fundo do canvas rola nativamente com um dedo; aqui só traduzimos o que o editor já faz com o mouse.
// =========================================================================
const TOQUE_LIMIAR_ARRASTO = 8; // px antes de tratar o toque como arrasto (abaixo disso é um toque/clique)

function ehTelaEstreita() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function setupToqueNoCanvas() {
    const viewport = document.getElementById('canvasViewport');
    if (!viewport) return;

    let arrasto = null;   // { alvo, x, y, iniciado }
    let pinca = null;     // { distancia, zoom }

    const distancia = (a, b) => Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    const dispararMouse = (tipo, alvo, toque) => {
        (tipo === 'mousedown' ? alvo : window).dispatchEvent(new MouseEvent(tipo, {
            bubbles: true, cancelable: true, view: window, button: 0, buttons: tipo === 'mouseup' ? 0 : 1,
            clientX: toque.clientX, clientY: toque.clientY,
        }));
    };
    const emCampo = (el) => !!el.closest('input, textarea, select, button, a, [contenteditable="true"]');

    viewport.addEventListener('touchstart', (e) => {
        if (e.touches.length === 2) {
            if (arrasto && arrasto.iniciado) dispararMouse('mouseup', null, arrasto);
            arrasto = null;
            pinca = { distancia: distancia(e.touches[0], e.touches[1]), zoom: zoomLevel };
            return;
        }
        if (e.touches.length !== 1) return;
        const alvo = e.target;
        // blocos e alças de conexão são arrastáveis; o resto do canvas rola sozinho
        if (!alvo.closest('.flow-node') || emCampo(alvo) || modoAtual !== 'canvas') { arrasto = null; return; }
        const t = e.touches[0];
        arrasto = { alvo, x: t.clientX, y: t.clientY, clientX: t.clientX, clientY: t.clientY, iniciado: false };
    }, { passive: true });

    viewport.addEventListener('touchmove', (e) => {
        if (pinca && e.touches.length === 2) {
            e.preventDefault();
            const d = distancia(e.touches[0], e.touches[1]);
            const novo = Math.min(2.0, Math.max(0.1, Math.round(pinca.zoom * (d / pinca.distancia) * 100) / 100));
            if (novo !== zoomLevel) {
                aplicarZoom(novo, (e.touches[0].clientX + e.touches[1].clientX) / 2, (e.touches[0].clientY + e.touches[1].clientY) / 2);
            }
            return;
        }
        if (!arrasto || e.touches.length !== 1) return;
        const t = e.touches[0];
        if (!arrasto.iniciado) {
            if (Math.hypot(t.clientX - arrasto.x, t.clientY - arrasto.y) < TOQUE_LIMIAR_ARRASTO) return;
            arrasto.iniciado = true;
            dispararMouse('mousedown', arrasto.alvo, { clientX: arrasto.x, clientY: arrasto.y });
        }
        e.preventDefault();
        arrasto.clientX = t.clientX;
        arrasto.clientY = t.clientY;
        dispararMouse('mousemove', null, t);
    }, { passive: false });

    const terminar = (e) => {
        if (pinca && e.touches.length < 2) pinca = null;
        if (arrasto && e.touches.length === 0) {
            if (arrasto.iniciado) {
                dispararMouse('mouseup', null, arrasto);
                e.preventDefault(); // não deixa o navegador gerar um clique depois do arrasto
            }
            arrasto = null;
        }
    };
    viewport.addEventListener('touchend', terminar, { passive: false });
    viewport.addEventListener('touchcancel', terminar, { passive: false });
}

// No celular o painel lateral começa fechado (ele cobre o canvas quando aberto)
function recolherInspetorNoCelular() {
    const painel = document.getElementById('inspectorPanel');
    if (painel && ehTelaEstreita() && !painel.classList.contains('collapsed')) toggleInspectorPanel();
}

document.addEventListener('DOMContentLoaded', () => {
    setupToqueNoCanvas();
    recolherInspetorNoCelular();
});

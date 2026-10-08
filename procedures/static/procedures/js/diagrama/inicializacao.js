/* Editor de Diagramas (DOC.071) - módulo "inicializacao"
 * Inicialização, atalhos de teclado e alternância de modos (Canvas / Outliner / Grelha).
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

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
    atualizarUILayout();
    atualizarMarcasDeMenuConteudo();

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
    const noCanvasComFoco = modoAtual === 'canvas' && !focoEmControleInterativo() && focoNoCanvasOuLivre();

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

    // Percorrer o diagrama (setas), recolher/expandir ("/") e copiar (Ctrl+C) valem também em revisões bloqueadas
    if (noCanvasComFoco && selectedNodeId && !e.altKey) {
        if (!ctrl && e.key.startsWith('Arrow')) {
            if (navegarSelecao(e.key)) e.preventDefault();
            return;
        }
        if (!ctrl && e.key === '/') {
            e.preventDefault();
            alternarRecolhimentoDaSelecao();
            return;
        }
        if (ctrl && e.key.toLowerCase() === 'c') {
            e.preventDefault();
            copiarRamoSelecionado();
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
        } else if (noCanvasComFoco && k === 'v') {
            e.preventDefault();
            colarRamo(e.shiftKey ? 'irmao' : 'filho');
            return;
        } else if (noCanvasComFoco && k === 'd' && selectedNodeId) {
            e.preventDefault();
            duplicarRamoSelecionado();
            return;
        }
    }

    if (!noCanvasComFoco) return;

    if (e.key === 'F2') {
        e.preventDefault();
        if (selectedNodeId) editarTextoDoNo(selectedNodeId);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (arvoreAtiva()) criarBlocoRapido('irmao'); else adicionarTopicoIrmao();
    } else if (e.key === 'Tab') {
        e.preventDefault();
        if (arvoreAtiva()) criarBlocoRapido('filho'); else adicionarSubtopicoFilho();
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

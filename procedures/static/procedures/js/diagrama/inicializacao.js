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
    montarMenuDeEstrutura();
    atualizarMarcaLigacaoPadrao();

    // Diagrama importado (XMind/OPML/Markdown): as posições vêm do auto-layout da primeira abertura
    if (topologia.precisa_layout) {
        delete topologia.precisa_layout;
        if (arvoreAtiva()) aplicarLayoutArvore();
        dispararAutoSave();
    }

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

    if (ctrl && !e.altKey && noCanvasComFoco && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        agruparSelecao();
        return;
    }

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

// Modo foco (ZEN): esconde cabeçalho, barra de ferramentas e avisos; o conteúdo ocupa a tela toda
// e só ficam os controles flutuantes (sair, zoom e enquadrar). Vale para Canvas, Outliner e Grelha.
function alternarModoZen(forcar) {
    const container = document.getElementById('editorMainContainer');
    const ativo = container.classList.toggle('zen-mode', forcar);
    document.body.classList.toggle('editor-foco-ativo', ativo);
    if (ativo) {
        document.getElementById('inspectorPanel')?.classList.add('collapsed');
        document.getElementById('btnToggleInspector')?.classList.remove('active');
    }
    setTimeout(() => { if (modoAtual === 'canvas') enquadrarVisaoCompleta(); }, 200);
}

// Esc sai do modo foco (sem atrapalhar a edição de texto nem janelas abertas)
document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (!document.getElementById('editorMainContainer')?.classList.contains('zen-mode')) return;
    if (document.querySelector('.modal.show, .dropdown-menu.show')) return;
    const alvo = e.target;
    if (alvo && (alvo.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(alvo.tagName))) return;
    alternarModoZen(false);
});

function alternarFundoCanvas() {
    document.getElementById('canvasViewport').classList.toggle('clean-bg');
}

function toggleInspectorPanel() {
    const panel = document.getElementById('inspectorPanel');
    const btn = document.getElementById('btnToggleInspector');
    panel.classList.toggle('collapsed');
    btn.classList.toggle('active');
    atualizarBarraInspetor();
}

// Celular: o painel do bloco não abre sozinho ao selecionar; aparece uma barra com o nome do bloco que o expande
function atualizarBarraInspetor() {
    const barra = document.getElementById('inspetorBarra');
    if (!barra) return;
    const painelRecolhido = document.getElementById('inspectorPanel')?.classList.contains('collapsed');
    let texto = '';
    if (selectedNodeId && typeof topologia !== 'undefined') {
        const no = topologia.nodes.find(n => n.id === selectedNodeId);
        texto = (no?.data?.label || '').replace(/\s+/g, ' ').trim() || 'Bloco selecionado';
    }
    document.getElementById('inspetorBarraTexto').textContent = texto;
    barra.classList.toggle('visivel', !!texto && painelRecolhido);
}

// Celular: abre / fecha o bloco com as demais ferramentas do editor
function alternarFerramentasMobile() {
    const ribbon = document.querySelector('.editor-ribbon');
    const aberto = ribbon.classList.toggle('ribbon-aberto');
    document.getElementById('btnFerramentasMobile')?.setAttribute('aria-expanded', aberto ? 'true' : 'false');
}

// Menus suspensos com posição fixa: não são cortados pela rolagem/overflow da barra de ferramentas
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.editor-header [data-bs-toggle="dropdown"], .editor-ribbon [data-bs-toggle="dropdown"]').forEach(botao => {
        bootstrap.Dropdown.getOrCreateInstance(botao, { popperConfig: padrao => ({ ...padrao, strategy: 'fixed' }) });
    });
});

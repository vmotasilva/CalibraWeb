/* Editor de Diagramas (DOC.071) - módulo "estilo"
 * Aparência dos blocos e das conexões: formatação de texto, borda, preenchimento, formas extras e TEMAS.
 * Código PURO (sem DOM), testado em Node (procedures/tests/js/estilo.test.js). O PDF aplica a mesma regra em
 * Python (procedures/services/diagram_estilo.py) e um teste compara as duas implementações.
 *
 * Precedência para cada propriedade de um bloco:
 *   1) estilo explícito do bloco (data.style; data.bgColor legado = preenchimento)  >
 *   2) tema do diagrama para o nível do bloco na hierarquia (tema.niveis)           >
 *   3) aparência padrão (propriedade ausente = o CSS/PDF mantêm o visual de sempre).
 * O token "branch" numa cor do tema vira a cor do ramo (paleta) quando o tema usa "multiRamo".
 */
(function (raiz) {
    'use strict';

    const FAMILIAS = ['sans', 'serif', 'mono'];
    const CSS_FAMILIAS = {
        sans: 'inherit',
        serif: 'Georgia, "Times New Roman", serif',
        mono: '"Courier New", Consolas, monospace',
    };
    const BORDAS = ['solid', 'dashed', 'dotted', 'none'];
    const TRACADOS = ['solid', 'dashed', 'dotted'];
    const FORMATOS_LINHA = ['ortogonal', 'curva', 'reta'];
    const ALINHAMENTOS = ['left', 'center', 'right'];
    const FORMAS_EXTRAS = ['brackets', 'underline', 'plain'];
    const COR = /^#[0-9a-fA-F]{6}$/;

    const PRESETS = {
        padrao: { nome: 'Padrão (sem tema)', fundo: null, multiRamo: false, paleta: [], linha: {}, niveis: [] },
        corporativo: {
            nome: 'Corporativo azul', fundo: '#f8fafc', multiRamo: false, paleta: [],
            linha: { cor: '#1e3a8a', largura: 2 },
            niveis: [
                { fill: '#1e3a8a', texto: '#ffffff', borda: '#1e3a8a', negrito: true, tamanho: 14 },
                { fill: '#2563eb', texto: '#ffffff', borda: '#1d4ed8', negrito: true, tamanho: 12 },
                { fill: '#dbeafe', texto: '#1e3a8a', borda: '#93c5fd', tamanho: 12 },
                { fill: '#ffffff', texto: '#0f172a', borda: '#cbd5e1', tamanho: 11 },
            ],
        },
        vibrante: {
            nome: 'Vibrante (uma cor por ramo)', fundo: '#ffffff', multiRamo: true,
            paleta: ['#2563eb', '#16a34a', '#ea580c', '#9333ea', '#dc2626', '#0891b2'],
            linha: { cor: 'branch', largura: 2 },
            niveis: [
                { fill: '#0f172a', texto: '#ffffff', borda: '#0f172a', negrito: true, tamanho: 14 },
                { fill: 'branch', texto: '#ffffff', borda: 'branch', negrito: true, tamanho: 12 },
                { fill: '#ffffff', texto: '#0f172a', borda: 'branch', tamanho: 12 },
                { fill: '#ffffff', texto: '#334155', borda: 'branch', tamanho: 11 },
            ],
        },
        grafite: {
            nome: 'Monocromático grafite', fundo: '#f1f5f9', multiRamo: false, paleta: [],
            linha: { cor: '#475569', largura: 2 },
            niveis: [
                { fill: '#1e293b', texto: '#ffffff', borda: '#0f172a', negrito: true, tamanho: 14 },
                { fill: '#475569', texto: '#ffffff', borda: '#334155', negrito: true, tamanho: 12 },
                { fill: '#e2e8f0', texto: '#0f172a', borda: '#94a3b8', tamanho: 12 },
                { fill: '#ffffff', texto: '#334155', borda: '#cbd5e1', tamanho: 11 },
            ],
        },
        impressao: {
            nome: 'Alto contraste (impressão P&B)', fundo: '#ffffff', multiRamo: false, paleta: [],
            linha: { cor: '#000000', largura: 2 },
            niveis: [
                { fill: '#000000', texto: '#ffffff', borda: '#000000', negrito: true, tamanho: 14 },
                { fill: '#ffffff', texto: '#000000', borda: '#000000', larguraBorda: 3, negrito: true, tamanho: 12 },
                { fill: '#ffffff', texto: '#000000', borda: '#000000', tamanho: 12 },
                { fill: '#ffffff', texto: '#000000', borda: '#000000', larguraBorda: 1, tamanho: 11 },
            ],
        },
    };

    // Luminância relativa (WCAG) e cor de texto legível sobre um fundo #RRGGBB
    function luminancia(hex) {
        const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
            .map(v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }

    function corDeTextoParaFundo(hex) {
        return luminancia(hex) < 0.4 ? '#ffffff' : '#0f172a';
    }

    function limpar(objeto) {
        const r = {};
        Object.keys(objeto).forEach(k => { if (objeto[k] !== undefined && objeto[k] !== null) r[k] = objeto[k]; });
        return r;
    }

    // "branch" -> cor do ramo; sem ramo/paleta, a propriedade fica sem valor (volta ao padrão)
    function corDoRamo(tema, ramo) {
        if (!tema || !tema.multiRamo || !tema.paleta || tema.paleta.length === 0 || ramo === undefined || ramo < 0) return undefined;
        return tema.paleta[ramo % tema.paleta.length];
    }

    function resolverToken(valor, tema, ramo) {
        return valor === 'branch' ? corDoRamo(tema, ramo) : valor;
    }

    /**
     * Estilo efetivo do bloco. ctx = { tema, profundidade, ramo }.
     * Retorna só as propriedades definidas: fill, noFill, color, fontFamily, fontSize, bold, italic, strike, align,
     * borderStyle, borderColor, borderWidth.
     */
    function resolverEstiloNo(no, ctx) {
        ctx = ctx || {};
        const dados = (no && no.data) || {};
        let base = {};

        const tema = ctx.tema;
        const tipo = (no && no.type) || 'process';
        if (tema && tema.niveis && tema.niveis.length > 0 && tipo !== 'start' && tipo !== 'end' && tipo !== 'decision') {
            const nivel = tema.niveis[Math.min(ctx.profundidade || 0, tema.niveis.length - 1)] || {};
            base = limpar({
                fill: resolverToken(nivel.fill, tema, ctx.ramo),
                color: resolverToken(nivel.texto, tema, ctx.ramo),
                borderColor: resolverToken(nivel.borda, tema, ctx.ramo),
                borderWidth: nivel.larguraBorda,
                fontSize: nivel.tamanho,
                bold: nivel.negrito,
                italic: nivel.italico,
                fontFamily: nivel.familia,
            });
        }

        // Formas sem caixa (colchetes, sublinhado, só texto) nunca herdam o preenchimento do tema
        const especial = FORMAS_EXTRAS.includes(dados.shape);
        const fillExplicito = !!((dados.style && dados.style.fill) || dados.bgColor);
        if (especial && !fillExplicito) delete base.fill;

        const explicito = limpar(Object.assign({}, dados.bgColor ? { fill: dados.bgColor } : {}, dados.style || {}));
        const efetivo = Object.assign({}, base, explicito);
        if (efetivo.noFill) delete efetivo.fill;
        // Preenchimento escolhido no bloco sem cor de texto própria: o texto se ajusta ao fundo (legível)
        if (efetivo.fill && dados.style && dados.style.fill && dados.style.color === undefined && COR.test(efetivo.fill)) {
            efetivo.color = corDeTextoParaFundo(efetivo.fill);
        }
        // Sem preenchimento (ou forma sem caixa) o texto cai sobre o fundo do diagrama: usa a cor legível sobre ele
        const semFundo = !!efetivo.noFill || (especial && !efetivo.fill);
        if (semFundo && !(dados.style && dados.style.color)) {
            const fundoDoDiagrama = (tema && tema.fundo && COR.test(tema.fundo)) ? tema.fundo : '#ffffff';
            efetivo.color = corDeTextoParaFundo(fundoDoDiagrama);
        }
        return efetivo;
    }

    /** Estilo efetivo da conexão. ctx = { tema, ramo } (ramo do bloco de destino). */
    function resolverEstiloConexao(aresta, ctx) {
        ctx = ctx || {};
        const tema = ctx.tema;
        const linha = (tema && tema.linha) || {};
        const base = limpar({
            color: resolverToken(linha.cor, tema, ctx.ramo),
            width: linha.largura,
            dash: linha.tracejado,
            shape: linha.formato,
        });
        return Object.assign({}, base, limpar((aresta && aresta.style) || {}));
    }

    /** Profundidade e ramo (índice do filho da raiz) de cada bloco, a partir da árvore de layout_arvore.js. */
    function contextoDosNos(arvore) {
        const contexto = {};
        const nivel = id => {
            let n = 0, atual = arvore.pai.get(id);
            while (atual !== undefined) { n++; atual = arvore.pai.get(atual); }
            return n;
        };
        arvore.filhos.forEach((_, id) => {
            const profundidade = nivel(id);
            let ramo = -1;
            if (profundidade >= 1) {
                let atual = id;
                while (arvore.pai.get(atual) !== undefined && nivel(atual) > 1) atual = arvore.pai.get(atual);
                const raizDoRamo = arvore.pai.get(atual);
                ramo = (arvore.filhos.get(raizDoRamo) || []).indexOf(atual);
            }
            contexto[id] = { profundidade, ramo };
        });
        return contexto;
    }

    // ------------------------------------------------------------------ sanitização (entradas da interface)
    function numeroEntre(valor, min, max) {
        const n = Number(valor);
        if (!isFinite(n)) return undefined;
        return Math.max(min, Math.min(max, Math.round(n)));
    }

    function normalizarEstiloNo(entrada) {
        const e = entrada || {};
        const r = {};
        if (FAMILIAS.includes(e.fontFamily)) r.fontFamily = e.fontFamily;
        const tam = numeroEntre(e.fontSize, 8, 40);
        if (tam !== undefined && e.fontSize !== '' && e.fontSize !== null) r.fontSize = tam;
        ['bold', 'italic', 'strike', 'noFill'].forEach(k => { if (typeof e[k] === 'boolean') r[k] = e[k]; });
        if (ALINHAMENTOS.includes(e.align)) r.align = e.align;
        ['color', 'fill', 'borderColor'].forEach(k => { if (typeof e[k] === 'string' && COR.test(e[k])) r[k] = e[k].toLowerCase(); });
        if (BORDAS.includes(e.borderStyle)) r.borderStyle = e.borderStyle;
        const larg = numeroEntre(e.borderWidth, 0, 8);
        if (larg !== undefined && e.borderWidth !== '' && e.borderWidth !== null) r.borderWidth = larg;
        return r;
    }

    function normalizarEstiloConexao(entrada) {
        const e = entrada || {};
        const r = {};
        if (typeof e.color === 'string' && COR.test(e.color)) r.color = e.color.toLowerCase();
        const larg = numeroEntre(e.width, 1, 8);
        if (larg !== undefined && e.width !== '' && e.width !== null) r.width = larg;
        if (TRACADOS.includes(e.dash)) r.dash = e.dash;
        if (FORMATOS_LINHA.includes(e.shape)) r.shape = e.shape;
        return r;
    }

    function dashArray(tracado, largura) {
        const w = largura || 2;
        if (tracado === 'dashed') return `${w * 4} ${w * 2.5}`;
        if (tracado === 'dotted') return `${w} ${w * 2}`;
        return null;
    }

    const api = {
        FAMILIAS, CSS_FAMILIAS, BORDAS, TRACADOS, FORMATOS_LINHA, ALINHAMENTOS, FORMAS_EXTRAS, PRESETS,
        resolverEstiloNo, resolverEstiloConexao, contextoDosNos, corDoRamo, corDeTextoParaFundo, luminancia,
        normalizarEstiloNo, normalizarEstiloConexao, dashArray,
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaEstilo = api;
})(typeof window !== 'undefined' ? window : globalThis);

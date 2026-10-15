/* Editor de Diagramas (DOC.071) - módulo "modelos_estilo"
 * Catálogo de MODELOS = layout (geometria da família) + estilo visual (tema com forma por nível e formato da linha).
 * Cada família tem variações (como nos modelos do XMind); aplicar uma variação grava layout_modo e tema no diagrama,
 * então o canvas e o PDF desenham o mesmo resultado. Código PURO (sem DOM), testado em Node
 * (procedures/tests/js/modelos_estilo.test.js). A interface fica em modelos_ui.js.
 *
 * Especificação de nível (central, tópico principal, subtópico, demais):
 *   forma:   rect | pill | underline | plain (sem caixa) | brackets
 *   preench: 'principal' (cor da paleta) | 'clara' | 'branco' | null (sem caixa)
 *   borda:   'principal' | 'cinza' | 'escuro' | null
 *   texto:   'branco' | 'escuro' | 'principal'  (padrão: legível sobre o preenchimento)
 */
(function (raiz) {
    'use strict';

    const PALETAS = [
        { id: 'indigo', nome: 'Índigo e creme', principal: '#3f51b5', clara: '#e8eaf6', fundo: '#fff1d9', destaque: '#f59e0b' },
        { id: 'grafite', nome: 'Grafite', principal: '#334155', clara: '#e2e8f0', fundo: '#f8fafc', destaque: '#64748b' },
        { id: 'verde', nome: 'Verde', principal: '#15803d', clara: '#dcfce7', fundo: '#f0fdf4', destaque: '#ca8a04' },
        { id: 'laranja', nome: 'Laranja', principal: '#c2410c', clara: '#ffedd5', fundo: '#fffbeb', destaque: '#1d4ed8' },
        { id: 'branco', nome: 'Fundo branco', principal: '#1e3a8a', clara: '#dbeafe', fundo: null, destaque: '#2563eb' },
    ];

    const ESCURO = '#0f172a';
    const CINZA = '#cbd5e1';

    // nível: [forma, preenchimento, borda, texto, negrito, tamanho, familia]
    const n = (forma, preench, borda, texto, negrito, tamanho, familia) => ({ forma, preench, borda, texto, negrito, tamanho, familia });

    const FAMILIAS_MODELO = [
        {
            id: 'organograma', nome: 'Organograma', layout: 'organograma',
            descricao: 'De cima para baixo: o tópico central no topo e os subordinados abaixo.',
            variacoes: [
                { id: 'org-texto', nome: 'Texto com linhas retas', linha: { formato: 'reta', largura: 1 }, niveis: [
                    n('plain', null, null, 'escuro', true, 16), n('plain', null, null, 'escuro', true, 13), n('plain', null, null, 'escuro', false, 11), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'org-caixas', nome: 'Caixas com serifa', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 16, 'serif'), n('rect', 'branco', 'cinza', 'escuro', true, 12, 'serif'), n('rect', 'branco', 'cinza', 'escuro', false, 11, 'serif'), n('rect', 'branco', 'cinza', 'escuro', false, 10, 'serif')] },
                { id: 'org-destaque', nome: 'Destaque e pílulas', linha: { formato: 'reta', largura: 1 }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('pill', 'branco', 'cinza', 'escuro', true, 12), n('plain', null, null, 'escuro', false, 11), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'org-sublinhado', nome: 'Sublinhado', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('underline', null, 'escuro', 'escuro', true, 16), n('underline', null, 'escuro', 'escuro', true, 13), n('underline', null, 'cinza', 'escuro', false, 11), n('underline', null, 'cinza', 'escuro', false, 10)] },
            ],
        },
        {
            id: 'logico', nome: 'Lógico', layout: 'logico',
            descricao: 'Da esquerda para a direita: o tópico central à esquerda e os desdobramentos à direita.',
            variacoes: [
                { id: 'log-destaque-curva', nome: 'Destaque com curvas', linha: { formato: 'curva', largura: 1 }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'log-destaque-cotovelo', nome: 'Destaque com cotovelos', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('plain', null, null, 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'log-pilulas', nome: 'Pílulas', linha: { formato: 'curva', largura: 1 }, niveis: [
                    n('pill', 'principal', 'principal', 'branco', true, 15), n('pill', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'log-sublinhado', nome: 'Sublinhado', linha: { formato: 'curva', largura: 1 }, niveis: [
                    n('underline', null, 'escuro', 'escuro', true, 16), n('underline', null, 'escuro', 'escuro', true, 12), n('underline', null, 'cinza', 'escuro', false, 10), n('underline', null, 'cinza', 'escuro', false, 10)] },
            ],
        },
        {
            id: 'arvore', nome: 'Árvore', layout: 'arvore',
            descricao: 'Lista com recuo: cada nível aparece abaixo do anterior, deslocado para a direita.',
            variacoes: [
                { id: 'arv-contorno', nome: 'Contorno', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', false, 15), n('rect', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'arv-negrito', nome: 'Texto em negrito', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('plain', null, null, 'escuro', true, 15), n('plain', null, null, 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'arv-destaque', nome: 'Destaque', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'principal', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'arv-pilulas', nome: 'Pílulas', linha: { formato: 'ortogonal', largura: 1 }, niveis: [
                    n('pill', 'principal', 'principal', 'branco', true, 15), n('pill', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
            ],
        },
    ];

    function paletaPorId(id) {
        return PALETAS.find(p => p.id === id) || PALETAS[0];
    }

    function variacaoPorId(id) {
        for (const f of FAMILIAS_MODELO) {
            const v = f.variacoes.find(x => x.id === id);
            if (v) return { familia: f, variacao: v };
        }
        return null;
    }

    function cor(token, paleta, padrao) {
        if (token === 'principal') return paleta.principal;
        if (token === 'clara') return paleta.clara;
        if (token === 'branco') return '#ffffff';
        if (token === 'escuro') return ESCURO;
        if (token === 'cinza') return CINZA;
        return padrao;
    }

    /** Nível do tema (formato de estilo.js) a partir da especificação do nível e da paleta. */
    function construirNivel(spec, paleta) {
        const nivel = { forma: spec.forma, tamanho: spec.tamanho };
        if (spec.preench) nivel.fill = cor(spec.preench, paleta);
        if (spec.borda) nivel.borda = cor(spec.borda, paleta);
        nivel.texto = spec.texto === 'branco' ? '#ffffff' : (spec.texto === 'principal' ? paleta.principal : ESCURO);
        if (spec.negrito) nivel.negrito = true;
        if (spec.familia) nivel.familia = spec.familia;
        return nivel;
    }

    /** Tema completo (válido para topologia.tema) de uma variação com a paleta escolhida. */
    function construirTema(variacao, paleta) {
        paleta = paleta || PALETAS[0];
        return {
            nome: `Modelo: ${variacao.nome}`,
            fundo: paleta.fundo,
            multiRamo: false,
            paleta: [],
            linha: { cor: ESCURO, largura: variacao.linha.largura, formato: variacao.linha.formato },
            niveis: variacao.niveis.map(spec => construirNivel(spec, paleta)),
        };
    }

    // ------------------------------------------------------------------ miniatura (SVG) de uma variação
    const L = 220, A = 124;

    function caixa(cx, cy, w, h, spec, paleta) {
        const x = cx - w / 2, y = cy - h / 2;
        const preench = spec.preench ? cor(spec.preench, paleta) : 'none';
        const borda = spec.borda ? cor(spec.borda, paleta) : 'none';
        const textoCor = spec.preench === 'principal' ? '#ffffff' : '#475569';
        const raio = spec.forma === 'pill' ? h / 2 : 2;
        const barra = `<rect x="${(cx - w * 0.3).toFixed(1)}" y="${(cy - 1).toFixed(1)}" width="${(w * 0.6).toFixed(1)}" height="2" rx="1" fill="${textoCor}" opacity="${spec.negrito ? 0.9 : 0.55}"/>`;
        if (spec.forma === 'underline') {
            return `<line x1="${x}" y1="${y + h}" x2="${x + w}" y2="${y + h}" stroke="${borda === 'none' ? '#64748b' : borda}" stroke-width="1"/>${barra}`;
        }
        if (spec.forma === 'plain') return barra;
        return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${raio}" fill="${preench}" stroke="${borda}" stroke-width="1"/>${barra}`;
    }

    function ligacao(formato, x1, y1, x2, y2, horizontal) {
        const c = 'stroke="#64748b" stroke-width="1" fill="none"';
        if (formato === 'reta') return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${c}/>`;
        if (formato === 'curva') {
            return horizontal
                ? `<path d="M${x1} ${y1} C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}" ${c}/>`
                : `<path d="M${x1} ${y1} C${x1} ${(y1 + y2) / 2} ${x2} ${(y1 + y2) / 2} ${x2} ${y2}" ${c}/>`;
        }
        return horizontal
            ? `<path d="M${x1} ${y1} H${(x1 + x2) / 2} V${y2} H${x2}" ${c}/>`
            : `<path d="M${x1} ${y1} V${(y1 + y2) / 2} H${x2} V${y2}" ${c}/>`;
    }

    function miniatura(familia, variacao, paleta) {
        paleta = paleta || PALETAS[0];
        const f = variacao.linha.formato;
        const [s0, s1, s2] = variacao.niveis;
        let corpo = '';
        if (familia.layout === 'organograma') {
            const centro = [L / 2, 20], pais = [[L * 0.28, 62], [L * 0.72, 62]];
            pais.forEach(([px, py]) => {
                corpo += ligacao(f, centro[0], centro[1] + 7, px, py - 7, false);
                [-1, 0, 1].forEach(d => {
                    const sx = px + d * 30, sy = 104;
                    corpo += ligacao(f, px, py + 7, sx, sy - 5, false) + caixa(sx, sy, 26, 9, s2, paleta);
                });
            });
            pais.forEach(([px, py]) => { corpo += caixa(px, py, 46, 14, s1, paleta); });
            corpo += caixa(centro[0], centro[1], 66, 16, s0, paleta);
        } else if (familia.layout === 'logico') {
            const centro = [36, A / 2], pais = [26, 62, 98];
            pais.forEach((py, i) => {
                corpo += ligacao(f, centro[0] + 28, centro[1], 98, py, true);
                [-1, 1].forEach(d => {
                    const sy = py + d * 8;
                    corpo += ligacao(f, 98 + 22, py, 170, sy, true) + caixa(186, sy, 30, 8, s2, paleta);
                });
            });
            pais.forEach(py => { corpo += caixa(98, py, 44, 13, s1, paleta); });
            corpo += caixa(centro[0], centro[1], 54, 18, s0, paleta);
        } else {
            // árvore: lista com recuo
            const linhas = [[24, 16, s0, 66, 16], [24 + 18, 40, s1, 52, 13], [24 + 36, 56, s2, 36, 8], [24 + 36, 70, s2, 36, 8], [24 + 18, 90, s1, 52, 13], [24 + 36, 106, s2, 36, 8]];
            const pos = linhas.map(([x, y, spec, w, h]) => [x, y, spec, w, h]);
            const pai = [null, 0, 1, 1, 0, 4];
            pos.forEach((p, i) => {
                if (pai[i] === null) return;
                const q = pos[pai[i]];
                corpo += `<path d="M${q[0] + 8} ${q[1] + q[4] / 2} V${p[1]} H${p[0]}" stroke="#64748b" stroke-width="1" fill="none"/>`;
            });
            pos.forEach(([x, y, spec, w, h]) => { corpo += caixa(x + w / 2, y, w, h, spec, paleta); });
        }
        const fundo = paleta.fundo || '#ffffff';
        return `<svg viewBox="0 0 ${L} ${A}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${variacao.nome}">`
            + `<rect width="${L}" height="${A}" fill="${fundo}"/>${corpo}</svg>`;
    }

    const api = { PALETAS, FAMILIAS_MODELO, paletaPorId, variacaoPorId, construirTema, construirNivel, miniatura };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaModelos = api;
})(typeof window !== 'undefined' ? window : globalThis);

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
        {
            id: 'mapa', nome: 'Mapa mental', layout: 'mapa',
            descricao: 'Tópico central no meio e os ramos principais distribuídos dos dois lados, sem setas.',
            variacoes: [
                { id: 'map-destaque', nome: 'Destaque e caixas', linha: { formato: 'curva', largura: 1, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'map-sublinhado', nome: 'Texto sobre linhas', linha: { formato: 'curva', largura: 1, seta: false }, niveis: [
                    n('plain', null, null, 'escuro', true, 16), n('underline', null, 'escuro', 'escuro', true, 12), n('underline', null, 'cinza', 'escuro', false, 10), n('underline', null, 'cinza', 'escuro', false, 10)] },
                { id: 'map-pilulas', nome: 'Pílulas', linha: { formato: 'curva', largura: 1, seta: false }, niveis: [
                    n('pill', 'principal', 'principal', 'branco', true, 15), n('pill', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'map-serifa', nome: 'Texto com serifa', linha: { formato: 'ortogonal', largura: 1, seta: false }, niveis: [
                    n('plain', null, null, 'escuro', true, 18, 'serif'), n('plain', null, null, 'escuro', true, 13, 'serif'), n('plain', null, null, 'escuro', false, 11, 'serif'), n('plain', null, null, 'escuro', false, 10, 'serif')] },
            ],
        },
        {
            id: 'chave', nome: 'Mapa de chaves', layout: 'logico',
            descricao: 'Da esquerda para a direita, com chaves { } agrupando os desdobramentos de cada tópico.',
            variacoes: [
                { id: 'chv-texto', nome: 'Texto e chaves', linha: { formato: 'chave', largura: 1, seta: false }, niveis: [
                    n('plain', null, null, 'escuro', true, 15), n('plain', null, null, 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'chv-caixas', nome: 'Caixas e chaves', linha: { formato: 'chave', largura: 1, seta: false }, niveis: [
                    n('rect', 'branco', 'cinza', 'escuro', false, 15), n('rect', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'chv-contorno', nome: 'Contorno escuro', linha: { formato: 'chave', largura: 1, seta: false }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 15), n('rect', 'branco', 'escuro', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'chv-destaque', nome: 'Destaque', linha: { formato: 'chave', largura: 1, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
            ],
        },
        {
            id: 'linha_tempo', nome: 'Linha do tempo', layout: 'linha_tempo',
            descricao: 'O tópico central à esquerda e uma linha com os ramos principais, alternando acima e abaixo.',
            variacoes: [
                { id: 'tl-destaque', nome: 'Destaque e caixas', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'tl-sublinhado', nome: 'Texto sublinhado', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('plain', null, null, 'escuro', true, 16), n('underline', null, 'escuro', 'escuro', true, 12), n('underline', null, 'cinza', 'escuro', false, 10), n('underline', null, 'cinza', 'escuro', false, 10)] },
                { id: 'tl-pilulas', nome: 'Pílulas', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('pill', 'principal', 'principal', 'branco', true, 15), n('pill', 'branco', 'cinza', 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'tl-contorno', nome: 'Contorno escuro', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 15), n('rect', 'branco', 'escuro', 'escuro', false, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
            ],
        },
        {
            id: 'espinha', nome: 'Espinha de peixe', layout: 'espinha',
            descricao: 'Causa e efeito: a cabeça à direita, a espinha e os ossos inclinados com as causas de cada ramo.',
            variacoes: [
                { id: 'fsh-destaque', nome: 'Destaque', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
                { id: 'fsh-contorno', nome: 'Contorno e sublinhado', linha: { formato: 'ortogonal', largura: 2, seta: false }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 15), n('underline', null, 'escuro', 'escuro', true, 12), n('plain', null, null, 'escuro', false, 10), n('plain', null, null, 'escuro', false, 10)] },
            ],
        },
        {
            id: 'tabela', nome: 'Tabela em árvore', layout: 'tabela',
            descricao: 'Cada bloco vira uma célula de tabela, com os níveis em colunas.',
            variacoes: [
                { id: 'tab-cabecalho', nome: 'Cabeçalho em destaque', layout: 'tabela_topo', linha: { formato: 'ortogonal', largura: 1, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'branco', 'cinza', 'escuro', true, 12), n('rect', 'branco', 'cinza', 'escuro', false, 11), n('rect', 'branco', 'cinza', 'escuro', false, 10)] },
                { id: 'tab-lateral', nome: 'Tópico central na lateral', linha: { formato: 'ortogonal', largura: 1, seta: false }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 15), n('rect', 'branco', 'cinza', 'escuro', true, 12), n('rect', 'branco', 'cinza', 'escuro', false, 11), n('rect', 'branco', 'cinza', 'escuro', false, 10)] },
            ],
        },
        {
            id: 'matriz', nome: 'Matriz', layout: 'matriz',
            descricao: 'Os níveis em linhas e os ramos em colunas, no formato de matriz.',
            variacoes: [
                { id: 'mtz-destaque', nome: 'Cabeçalho em destaque', linha: { formato: 'ortogonal', largura: 1, seta: false }, niveis: [
                    n('rect', 'principal', 'principal', 'branco', true, 15), n('rect', 'clara', 'cinza', 'escuro', true, 12), n('rect', 'branco', 'cinza', 'escuro', false, 11), n('rect', 'branco', 'cinza', 'escuro', false, 10)] },
                { id: 'mtz-contorno', nome: 'Contorno', linha: { formato: 'ortogonal', largura: 1, seta: false }, niveis: [
                    n('rect', 'branco', 'escuro', 'escuro', true, 15), n('rect', 'branco', 'escuro', 'escuro', true, 12), n('rect', 'branco', 'cinza', 'escuro', false, 11), n('rect', 'branco', 'cinza', 'escuro', false, 10)] },
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
            linha: Object.assign({ cor: ESCURO, largura: variacao.linha.largura, formato: variacao.linha.formato }, variacao.linha.seta === false ? { seta: false } : {}),
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
        if (formato === 'chave') {
            const dx = x2 >= x1 ? 1 : -1, dy = y2 >= y1 ? 1 : -1;
            if (Math.abs(y1 - y2) < 1) return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${c}/>`;
            if (!horizontal) return `<path d="M${x1} ${y1} V${(y1 + y2) / 2} H${x2} V${y2}" ${c}/>`;
            const m = x1 + dx * Math.min(10, Math.abs(x2 - x1) / 2), r = Math.min(4, Math.abs(y2 - y1) / 2);
            return `<path d="M${x1} ${y1} H${m - r * dx} Q${m} ${y1} ${m} ${y1 + r * dy} V${y2 - r * dy} Q${m} ${y2} ${m + r * dx} ${y2} H${x2}" ${c}/>`;
        }
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
        const layout = variacao.layout || familia.layout;
        let corpo = '';
        if (layout === 'organograma') {
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
        } else if (layout === 'mapa') {
            const cx = L / 2, cy = A / 2;
            [[1, 34], [1, 62], [1, 90], [-1, 34], [-1, 62], [-1, 90]].forEach(([lado, py]) => {
                const px = cx + lado * 56;
                corpo += ligacao(f, cx + lado * 26, cy, px - lado * 20, py, true);
                [-1, 1].forEach(d => {
                    const sx = cx + lado * 98, sy = py + d * 7;
                    corpo += ligacao(f, px + lado * 20, py, sx - lado * 14, sy, true) + caixa(sx, sy, 24, 7, s2, paleta);
                });
            });
            [34, 62, 90].forEach(py => { corpo += caixa(cx + 56, py, 38, 12, s1, paleta) + caixa(cx - 56, py, 38, 12, s1, paleta); });
            corpo += caixa(cx, cy, 50, 18, s0, paleta);
        } else if (layout === 'tabela_topo' || layout === 'tabela' || layout === 'matriz') {
            const cel = (x, y, w, h, spec) => {
                const c = caixa(x + w / 2, y + h / 2, w, h, Object.assign({}, spec, { forma: spec.forma === 'pill' ? 'rect' : spec.forma }), paleta);
                return c;
            };
            if (layout === 'tabela_topo') {
                corpo += cel(30, 14, 160, 20, s0);
                [0, 1].forEach(i => { corpo += cel(30, 34 + i * 40, 52, 40, s1); [0, 1].forEach(j => { corpo += cel(82, 34 + i * 40 + j * 20, 108, 20, s2); }); });
            } else if (layout === 'tabela') {
                corpo += cel(20, 14, 50, 96, s0);
                [0, 1].forEach(i => { corpo += cel(70, 14 + i * 48, 50, 48, s1); [0, 1].forEach(j => { corpo += cel(120, 14 + i * 48 + j * 24, 80, 24, s2); }); });
            } else {
                corpo += cel(30, 14, 160, 22, s0);
                [0, 1].forEach(i => { corpo += cel(30 + i * 80, 36, 80, 22, s1); [0, 1].forEach(j => { corpo += cel(30 + i * 80, 58 + j * 24, 80, 24, s2); }); });
            }
        } else if (layout === 'linha_tempo') {
            const y0 = 62, x0 = 46;
            corpo += `<line x1="${x0}" y1="${y0}" x2="${L - 8}" y2="${y0}" stroke="#334155" stroke-width="2"/>`;
            [[78, -1], [128, 1], [178, -1]].forEach(([xc, lado]) => {
                const yb = y0 + lado * 30;
                corpo += `<line x1="${xc}" y1="${y0}" x2="${xc}" y2="${yb}" stroke="#334155" stroke-width="1.5"/>`;
                corpo += caixa(xc, yb + lado * 7, 32, 13, s1, paleta);
                [-1, 1].forEach(d => { corpo += caixa(xc + 34, yb + lado * 7 + d * 6, 20, 6, s2, paleta); });
            });
            corpo += caixa(22, y0, 38, 18, s0, paleta);
        } else if (layout === 'espinha') {
            const y0 = 62;
            corpo += `<line x1="8" y1="${y0}" x2="${L - 62}" y2="${y0}" stroke="#334155" stroke-width="2"/>`;
            [[60, -1], [110, -1], [60, 1], [110, 1]].forEach(([xc, lado]) => {
                const ym = y0 + lado * 46;
                corpo += `<line x1="${xc}" y1="${ym - lado * 6}" x2="${xc + 22}" y2="${y0}" stroke="#334155" stroke-width="1.5"/>`;
                [0.4, 0.75].forEach(t => {
                    const yy = ym - lado * 6 + (y0 - (ym - lado * 6)) * t;
                    const xx = xc + 22 * t;
                    corpo += `<line x1="${xx - 14}" y1="${yy}" x2="${xx}" y2="${yy}" stroke="#334155" stroke-width="1"/>${caixa(xx - 24, yy, 18, 6, s2, paleta)}`;
                });
                corpo += caixa(xc, ym, 34, 12, s1, paleta);
            });
            corpo += caixa(L - 32, y0, 52, 20, s0, paleta);
        } else if (layout === 'logico') {
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

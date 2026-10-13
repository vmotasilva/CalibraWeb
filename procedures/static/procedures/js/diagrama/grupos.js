/* Editor de Diagramas - módulo "grupos"
 * Geometria PURA dos grupos (boundary): caixa que envolve os blocos do grupo, aninhamento e ordem de apresentação.
 * Sem DOM; testado em Node (procedures/tests/js/grupos.test.js). O PDF aplica a mesma regra em Python
 * (procedures/services/diagram_grupos.py) e um teste compara as duas implementações.
 *
 * Grupo: { id, titulo, cor, resumo, nos: [ids] }.   Caixa de um bloco: { x, y, w, h } (coordenadas do canvas).
 */
(function (raiz) {
    'use strict';

    const PAD_BASE = 22;     // folga entre os blocos e a borda do grupo
    const PAD_NIVEL = 10;    // cada grupo que contém este adiciona esta folga (grupos aninhados não se sobrepõem)
    const TITULO_H = 24;     // faixa do título no topo
    const RESUMO_W = 220;    // largura do quadro de resumo ao lado do grupo
    const RESUMO_GAP = 12;

    const visiveis = (grupo, caixas) => (grupo.nos || []).map(String).filter(id => caixas[id]);

    // Quantos outros grupos contêm (por inteiro) os blocos visíveis deste grupo
    function nivelDeAninhamento(grupos, indice, caixas) {
        const meus = visiveis(grupos[indice], caixas);
        if (meus.length === 0) return 0;
        let nivel = 0;
        grupos.forEach((outro, j) => {
            if (j === indice) return;
            const deles = new Set(visiveis(outro, caixas));
            if (!meus.every(id => deles.has(id))) return;
            if (deles.size > meus.length || (deles.size === meus.length && j < indice)) nivel++;
        });
        return nivel;
    }

    function caixaDoGrupo(grupo, caixas, nivel) {
        const ids = visiveis(grupo, caixas);
        if (ids.length === 0) return null;
        const pad = PAD_BASE + PAD_NIVEL * (nivel || 0);
        const x0 = Math.min(...ids.map(id => caixas[id].x));
        const y0 = Math.min(...ids.map(id => caixas[id].y));
        const x1 = Math.max(...ids.map(id => caixas[id].x + caixas[id].w));
        const y1 = Math.max(...ids.map(id => caixas[id].y + caixas[id].h));
        const x = Math.max(2, x0 - pad), y = Math.max(2, y0 - pad - TITULO_H);
        return { x, y, w: (x1 + pad) - x, h: (y1 + pad) - y };
    }

    // Ordem de apresentação: percurso em profundidade da hierarquia ({ filhos: Map, raizes: [] }), só blocos visíveis
    function sequenciaDeApresentacao(arvore, ocultos) {
        const fora = ocultos || new Set();
        const saida = [];
        const visitar = id => {
            if (fora.has(id)) return;
            saida.push(id);
            (arvore.filhos.get(id) || []).forEach(visitar);
        };
        arvore.raizes.forEach(visitar);
        return saida;
    }

    const api = { PAD_BASE, PAD_NIVEL, TITULO_H, RESUMO_W, RESUMO_GAP, nivelDeAninhamento, caixaDoGrupo, sequenciaDeApresentacao };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaGrupos = api;
})(typeof window !== 'undefined' ? window : globalThis);

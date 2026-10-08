/* Editor de Diagramas (DOC.071) - módulo "layout_arvore"
 * Motor de layout em árvore e operações sobre a hierarquia. Código PURO (sem DOM e sem variáveis globais do
 * editor), para ser testado em Node (procedures/tests/js/layout_arvore.test.js).
 *
 * Modelo: a hierarquia é formada pelas conexões com kind "hierarquia" (padrão quando kind não existe).
 * Conexões com kind "relacao" são ligações livres e não participam da árvore.
 * A ordem dos filhos é a ordem das conexões no vetor `edges` (reordenar irmãos = reordenar conexões).
 */
(function (raiz) {
    'use strict';

    const MODOS = {
        // direcao: eixo dos níveis | gapCruz: espaço entre irmãos | gapNivel: espaço entre níveis
        organograma: { direcao: 'baixo', gapCruz: 40, gapNivel: 90, handles: ['bottom', 'top'] },
        logico: { direcao: 'direita', gapCruz: 24, gapNivel: 80, handles: ['right', 'left'] },
        arvore: { direcao: 'lista', gapCruz: 16, gapNivel: 40, handles: ['bottom', 'left'] },
    };

    const MARGEM_X = 80;
    const MARGEM_Y = 60;

    function ehHierarquia(aresta) {
        return (aresta.kind || 'hierarquia') === 'hierarquia';
    }

    function estimarTamanho(no) {
        if (no.type === 'start' || no.type === 'end') return { w: 140, h: 48 };
        if (no.type === 'decision') return { w: 110, h: 110 };
        const dados = no.data || {};
        const base = dados.colab ? { w: 200, h: 64 } : { w: 180, h: 64 };
        const subs = (dados.subtitles || []).filter(t => t && String(t).trim()).length;
        return { w: base.w, h: base.h + 14 * subs };
    }

    /**
     * Monta a árvore a partir das conexões de hierarquia.
     * Cada bloco tem no máximo um pai (a primeira conexão de entrada vence); ciclos e auto-referências são ignorados.
     * Retorna { filhos: Map(id -> [ids na ordem das conexões]), pai: Map(id -> id), raizes: [ids] }.
     */
    function montarArvore(nos, arestas) {
        const ids = new Set(nos.map(n => String(n.id)));
        const filhos = new Map();
        const pai = new Map();
        ids.forEach(id => filhos.set(id, []));

        arestas.filter(ehHierarquia).forEach(a => {
            const origem = String(a.source);
            const destino = String(a.target);
            if (!ids.has(origem) || !ids.has(destino) || origem === destino) return;
            if (pai.has(destino)) return;                 // um pai só
            if (ehAncestral(pai, destino, origem)) return; // evitaria ciclo
            pai.set(destino, origem);
            filhos.get(origem).push(destino);
        });

        const raizes = nos.map(n => String(n.id)).filter(id => !pai.has(id));
        return { filhos, pai, raizes };
    }

    // `candidato` é ancestral de `no` (ou o próprio)? Usa o mapa de pais.
    function ehAncestral(pai, candidato, no) {
        let atual = no;
        const visitados = new Set();
        while (atual !== undefined && !visitados.has(atual)) {
            if (atual === candidato) return true;
            visitados.add(atual);
            atual = pai.get(atual);
        }
        return false;
    }

    function descendentes(arvore, id) {
        const resultado = new Set();
        const pilha = [...(arvore.filhos.get(id) || [])];
        while (pilha.length) {
            const atual = pilha.pop();
            if (resultado.has(atual)) continue;
            resultado.add(atual);
            (arvore.filhos.get(atual) || []).forEach(f => pilha.push(f));
        }
        return resultado;
    }

    // Blocos ocultos: todos os descendentes de um bloco recolhido (o bloco recolhido continua visível)
    function ocultos(nos, arvore) {
        const escondidos = new Set();
        nos.forEach(n => {
            if (n.data && n.data.collapsed) descendentes(arvore, String(n.id)).forEach(d => escondidos.add(d));
        });
        return escondidos;
    }

    function profundidade(arvore, id) {
        let nivel = 0;
        let atual = arvore.pai.get(id);
        while (atual !== undefined) { nivel++; atual = arvore.pai.get(atual); }
        return nivel;
    }

    /**
     * Calcula as posições. `tamanhos` = { id: {w, h} } (medidos no DOM; usa estimativa quando faltar).
     * Retorna { posicoes: { id: {x, y} }, handles: { idConexao: [sourceHandle, targetHandle] }, ocultos: Set }.
     */
    function calcularLayout(nos, arestas, modo, tamanhos, opcoes) {
        const cfg = MODOS[modo];
        if (!cfg) throw new Error('Modo de layout desconhecido: ' + modo);
        const opt = Object.assign({ x0: MARGEM_X, y0: MARGEM_Y }, opcoes || {});

        const arvore = montarArvore(nos, arestas);
        const escondidos = ocultos(nos, arvore);
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const tam = id => (tamanhos && tamanhos[id]) || estimarTamanho(porId.get(id));
        const visiveis = id => (arvore.filhos.get(id) || []).filter(f => !escondidos.has(f));

        const posicoes = {};
        if (cfg.direcao === 'lista') {
            // Lista com recuo: cada bloco abaixo do anterior (percurso em profundidade), recuado em relação ao pai
            let y = opt.y0;
            const recuo = 40;
            const percorrer = (id, x) => {
                const t = tam(id);
                posicoes[id] = { x, y };
                y += t.h + cfg.gapCruz;
                visiveis(id).forEach(f => percorrer(f, x + recuo));
            };
            let xRaiz = opt.x0;
            arvore.raizes.filter(r => !escondidos.has(r)).forEach(r => {
                percorrer(r, xRaiz);
                y += cfg.gapCruz;
            });
        } else {
            // Eixo "cruzado" = onde os irmãos se alinham (x no organograma, y no lógico); eixo "nível" = profundidade
            const cruz = cfg.direcao === 'baixo' ? t => t.w : t => t.h;
            const nivel = cfg.direcao === 'baixo' ? t => t.h : t => t.w;
            const raizesVisiveis = arvore.raizes.filter(r => !escondidos.has(r));

            // 1) extensão de cada subárvore no eixo cruzado
            const extensao = new Map();
            const medir = id => {
                const proprio = cruz(tam(id));
                const kids = visiveis(id);
                let soma = 0;
                kids.forEach((f, i) => { soma += medir(f) + (i > 0 ? cfg.gapCruz : 0); });
                const e = Math.max(proprio, soma);
                extensao.set(id, e);
                return e;
            };
            raizesVisiveis.forEach(medir);

            // 2) espessura de cada nível (maior bloco do nível)
            const espessura = [];
            const medirNiveis = (id, d) => {
                espessura[d] = Math.max(espessura[d] || 0, nivel(tam(id)));
                visiveis(id).forEach(f => medirNiveis(f, d + 1));
            };
            raizesVisiveis.forEach(r => medirNiveis(r, 0));
            const inicioNivel = [];
            let acumulado = 0;
            espessura.forEach((e, d) => { inicioNivel[d] = acumulado; acumulado += e + cfg.gapNivel; });

            // 3) posicionamento: centro de cada bloco no eixo cruzado
            const centro = new Map();
            const colocar = (id, inicio, d) => {
                const kids = visiveis(id);
                const proprio = cruz(tam(id));
                const total = extensao.get(id);
                let c;
                if (kids.length === 0) {
                    c = inicio + total / 2;
                } else {
                    let somaFilhos = 0;
                    kids.forEach((f, i) => { somaFilhos += extensao.get(f) + (i > 0 ? cfg.gapCruz : 0); });
                    let cursor = inicio + (total - somaFilhos) / 2;
                    const centros = [];
                    kids.forEach(f => {
                        colocar(f, cursor, d + 1);
                        centros.push(centro.get(f));
                        cursor += extensao.get(f) + cfg.gapCruz;
                    });
                    c = (centros[0] + centros[centros.length - 1]) / 2;
                    if (proprio > somaFilhos) c = inicio + total / 2;
                }
                centro.set(id, c);
                const t = tam(id);
                const pos = nivel(t) < espessura[d] ? (espessura[d] - nivel(t)) / 2 : 0; // centraliza no nível
                if (cfg.direcao === 'baixo') posicoes[id] = { x: c - t.w / 2, y: inicioNivel[d] + pos };
                else posicoes[id] = { x: inicioNivel[d] + pos, y: c - t.h / 2 };
            };

            let cursorRaiz = 0;
            raizesVisiveis.forEach(r => {
                colocar(r, cursorRaiz, 0);
                cursorRaiz += extensao.get(r) + cfg.gapCruz * 2;
            });

            // 4) desloca para a origem desejada
            const minX = Math.min(...Object.values(posicoes).map(p => p.x));
            const minY = Math.min(...Object.values(posicoes).map(p => p.y));
            Object.values(posicoes).forEach(p => {
                p.x = p.x - minX + opt.x0;
                p.y = p.y - minY + opt.y0;
            });
        }

        Object.values(posicoes).forEach(p => { p.x = Math.round(p.x); p.y = Math.round(p.y); });

        const handles = {};
        arestas.filter(ehHierarquia).forEach(a => {
            const o = String(a.source);
            const d = String(a.target);
            if (arvore.pai.get(d) === o && posicoes[o] && posicoes[d]) handles[a.id] = cfg.handles;
        });

        return { posicoes, handles, ocultos: escondidos };
    }

    /**
     * Move `filhoId` para ser filho de `novoPaiId`, inserido antes de `antesDeId` (ou no fim dos irmãos).
     * Retorna { arestas, ok, motivo }. Não altera o vetor original. Recusa ciclos e auto-referência.
     */
    function moverNaArvore(nos, arestas, filhoId, novoPaiId, antesDeId) {
        filhoId = String(filhoId);
        novoPaiId = novoPaiId === null || novoPaiId === undefined ? null : String(novoPaiId);
        const arvore = montarArvore(nos, arestas);
        if (novoPaiId !== null) {
            if (novoPaiId === filhoId) return { arestas, ok: false, motivo: 'um bloco não pode ser filho de si mesmo' };
            if (descendentes(arvore, filhoId).has(novoPaiId)) return { arestas, ok: false, motivo: 'o destino é descendente do bloco movido' };
        }

        // remove a conexão de hierarquia que chega ao bloco
        let existente = null;
        const restantes = arestas.filter(a => {
            if (ehHierarquia(a) && String(a.target) === filhoId) { existente = existente || a; return false; }
            return true;
        });
        if (novoPaiId === null) return { arestas: restantes, ok: true };

        const nova = Object.assign({}, existente || {}, {
            id: `e-${novoPaiId}-${filhoId}`,
            source: novoPaiId,
            target: filhoId,
            kind: 'hierarquia',
        });
        if (!existente) { nova.sourceHandle = 'bottom'; nova.targetHandle = 'top'; }

        let indice = -1;
        if (antesDeId !== null && antesDeId !== undefined) {
            indice = restantes.findIndex(a => ehHierarquia(a) && String(a.source) === novoPaiId && String(a.target) === String(antesDeId));
        }
        if (indice === -1) {
            // depois da última conexão de hierarquia do novo pai (ou no fim do vetor)
            for (let i = restantes.length - 1; i >= 0; i--) {
                if (ehHierarquia(restantes[i]) && String(restantes[i].source) === novoPaiId) { indice = i + 1; break; }
            }
            if (indice === -1) indice = restantes.length;
        }
        const resultado = restantes.slice();
        resultado.splice(indice, 0, nova);
        return { arestas: resultado, ok: true };
    }

    /**
     * Copia o ramo (bloco + descendentes + conexões internas) com novos IDs.
     * `gerarId()` deve devolver IDs ainda não usados. Retorna { nos, arestas, raizId }.
     */
    function clonarRamo(nos, arestas, raizId, gerarId) {
        raizId = String(raizId);
        const arvore = montarArvore(nos, arestas);
        const grupo = new Set([raizId, ...descendentes(arvore, raizId)]);
        const mapa = new Map();
        const novosNos = [];
        nos.filter(n => grupo.has(String(n.id))).forEach(n => {
            const novoId = String(gerarId());
            mapa.set(String(n.id), novoId);
            const copia = JSON.parse(JSON.stringify(n));
            copia.id = novoId;
            if (copia.data) copia.data.stepId = novoId;
            novosNos.push(copia);
        });
        const novasArestas = arestas
            .filter(a => grupo.has(String(a.source)) && grupo.has(String(a.target)))
            .map(a => {
                const copia = JSON.parse(JSON.stringify(a));
                copia.source = mapa.get(String(a.source));
                copia.target = mapa.get(String(a.target));
                copia.id = `e-${copia.source}-${copia.target}`;
                return copia;
            });
        return { nos: novosNos, arestas: novasArestas, raizId: mapa.get(raizId) };
    }

    // Vizinho na árvore para navegação por setas
    function irmaos(arvore, id) {
        const pai = arvore.pai.get(id);
        return pai === undefined ? arvore.raizes : arvore.filhos.get(pai);
    }

    const api = {
        MODOS, ehHierarquia, estimarTamanho, montarArvore, descendentes, ocultos, profundidade,
        calcularLayout, moverNaArvore, clonarRamo, irmaos, ehAncestral,
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaArvore = api;
})(typeof window !== 'undefined' ? window : globalThis);

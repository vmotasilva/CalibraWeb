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
        organograma: { direcao: 'baixo', gapCruz: 40, gapNivel: 90, handles: ['bottom', 'top'], empilharFolhas: true },
        logico: { direcao: 'direita', gapCruz: 24, gapNivel: 80, handles: ['right', 'left'] },
        arvore: { direcao: 'lista', gapCruz: 16, gapNivel: 40, handles: ['bottom', 'left'] },
        // mapa mental: topico central no meio e ramos principais nos dois lados (cada lado e um layout logico)
        mapa: { direcao: 'dois-lados', gapCruz: 24, gapNivel: 80, handles: ['right', 'left'] },
        // tabelas: cada bloco vira uma célula; linha do tempo e espinha de peixe têm linhas-guia próprias
        tabela: { direcao: 'tabela', eixo: 'colunas', handles: ['right', 'left'] },
        tabela_topo: { direcao: 'tabela', eixo: 'colunas', cabecalho: true, handles: ['right', 'left'] },
        matriz: { direcao: 'tabela', eixo: 'linhas', handles: ['bottom', 'top'] },
        linha_tempo: { direcao: 'linha-tempo', handles: ['right', 'left'] },
        espinha: { direcao: 'espinha', handles: ['right', 'left'] },
    };

    const MARGEM_X = 80;
    const MARGEM_Y = 60;
    // Estrutura de um ramo (data.estrutura): como os filhos de um bloco são dispostos no organograma
    const ESTRUTURAS = ['organograma', 'arvore'];
    const RECUO_PILHA = 28;   // organograma: folhas empilhadas ficam recuadas à direita do eixo do pai
    const GAP_PILHA = 14;     // espaço vertical entre folhas empilhadas

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
    // Ordem manual (data.ordem, número) = POSIÇÃO do bloco entre os seus pares (1 = primeiro). Os pares são os irmãos (blocos
    // ligados ao mesmo pai) e, quando `chaveDoGrupo` é informada, só os irmãos do mesmo grupo (por exemplo, a mesma raia e o
    // mesmo nível): cada grupo tem a sua contagem isolada. Blocos sem número ocupam as posições que sobram, na ordem das
    // conexões. Só vale para o layout (não altera as conexões).
    function ordenarPorPosicao(ids, ordemDe) {
        const n = ids.length;
        const resultado = new Array(n).fill(null);
        const numerados = ids.map((id, i) => ({ id, i, o: ordemDe(id) })).filter(x => x.o !== null)
            .sort((x, y) => x.o - y.o || x.i - y.i);
        numerados.forEach(x => {
            const alvo = Math.max(0, Math.min(n - 1, Math.round(x.o) - 1));
            let d = alvo;
            while (d < n && resultado[d] !== null) d++;                       // posição ocupada: próxima livre à direita
            if (d >= n) { d = alvo; while (d >= 0 && resultado[d] !== null) d--; }   // sem espaço à direita: à esquerda
            resultado[d] = x.id;
        });
        const usados = new Set(numerados.map(x => x.id));
        const livres = ids.filter(id => !usados.has(id));
        let k = 0;
        for (let p = 0; p < n; p++) if (resultado[p] === null) resultado[p] = livres[k++];
        return resultado;
    }

    function aplicarOrdemManual(arvore, nos, chaveDoGrupo) {
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const ordemDe = id => {
            const v = porId.get(id)?.data?.ordem;
            return typeof v === 'number' && isFinite(v) ? v : null;
        };
        const ordenar = lista => {
            const grupos = new Map();   // chave do grupo -> membros com a posição (vaga) que ocupam na lista
            lista.forEach((id, vaga) => {
                const chave = chaveDoGrupo ? chaveDoGrupo(porId.get(id)) : '';
                if (!grupos.has(chave)) grupos.set(chave, []);
                grupos.get(chave).push({ id, vaga });
            });
            const saida = lista.slice();
            grupos.forEach(membros => {
                const novos = ordenarPorPosicao(membros.map(m => m.id), ordemDe);
                membros.forEach((m, i) => { saida[m.vaga] = novos[i]; });
            });
            return saida;
        };
        arvore.filhos.forEach((lista, id) => arvore.filhos.set(id, ordenar(lista)));
        arvore.raizes = ordenar(arvore.raizes);
        return arvore;
    }

    /**
     * Mapa mental: para cada raiz, os ramos principais sao divididos em dois grupos contiguos de peso parecido (numero de
     * blocos): os primeiros ficam a direita (de cima para baixo) e os demais a esquerda (de baixo para cima, sentido horario
     * como no XMind). Cada lado usa o layout "logico"; o lado esquerdo e espelhado em torno do centro do topico central.
     */
    function calcularMapa(nos, arestas, tamanhos, opt) {
        const arvore = aplicarOrdemManual(montarArvore(nos, arestas), nos);
        const escondidos = ocultos(nos, arvore);
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const tam = id => (tamanhos && tamanhos[id]) || estimarTamanho(porId.get(id));
        const arestaDe = new Map();
        arestas.filter(ehHierarquia).forEach(a => { if (!arestaDe.has(`${a.source}|${a.target}`)) arestaDe.set(`${a.source}|${a.target}`, a); });
        const visiveis = id => (arvore.filhos.get(id) || []).filter(f => !escondidos.has(f));
        const peso = id => 1 + visiveis(id).reduce((s, f) => s + peso(f), 0);

        const posicoes = {};
        const handles = {};
        let yBase = opt.y0;

        arvore.raizes.filter(r => !escondidos.has(r)).forEach(raiz => {
            const kids = visiveis(raiz);
            let corte = kids.length;
            if (kids.length > 1) {
                const pesos = kids.map(peso);
                const total = pesos.reduce((a, b) => a + b, 0);
                let acumulado = 0, menor = Infinity;
                corte = 1;
                for (let k = 1; k <= kids.length; k++) {
                    acumulado += pesos[k - 1];
                    const diferenca = Math.abs(2 * acumulado - total);
                    if (diferenca <= menor) { menor = diferenca; corte = k; }
                }
                if (corte >= kids.length) corte = Math.max(1, kids.length - 1);
            }
            const direita = kids.slice(0, corte);
            const esquerda = kids.slice(corte).reverse();
            const t0 = tam(raiz);

            const lado = (filhosDoLado) => {
                const conjunto = new Set([raiz]);
                filhosDoLado.forEach(f => { conjunto.add(f); descendentes(arvore, f).forEach(d => conjunto.add(d)); });
                const nosLado = nos.filter(n => conjunto.has(String(n.id)));
                const arestasLado = [];
                const adicionar = (pai, lista) => lista.forEach(f => {
                    const original = arestaDe.get(`${pai}|${f}`);
                    if (original) arestasLado.push({ id: original.id, source: pai, target: f, kind: 'hierarquia' });
                    adicionar(f, arvore.filhos.get(f) || []);
                });
                adicionar(raiz, filhosDoLado);
                const r = calcularLayout(nosLado, arestasLado, 'logico', tamanhos, { x0: 0, y0: 0 });
                const dy = -(r.posicoes[raiz].y + t0.h / 2);   // centro do topico central na altura 0
                return { r, dy };
            };

            const parte = {};
            const direitaCalc = lado(direita);
            Object.entries(direitaCalc.r.posicoes).forEach(([id, p]) => { parte[id] = { x: p.x, y: p.y + direitaCalc.dy }; });
            Object.keys(direitaCalc.r.handles).forEach(id => { handles[id] = ['right', 'left']; });
            if (esquerda.length > 0) {
                const esquerdaCalc = lado(esquerda);
                Object.entries(esquerdaCalc.r.posicoes).forEach(([id, p]) => {
                    if (id === raiz) return;
                    parte[id] = { x: t0.w - (p.x + tam(id).w), y: p.y + esquerdaCalc.dy };
                });
                Object.keys(esquerdaCalc.r.handles).forEach(id => { handles[id] = ['left', 'right']; });
            }

            const faixas = Object.entries(parte).map(([id, p]) => [p.y, p.y + tam(id).h]);
            const minX = Math.min(...Object.values(parte).map(p => p.x));
            const minY = Math.min(...faixas.map(v => v[0]));
            const maxY = Math.max(...faixas.map(v => v[1]));
            Object.entries(parte).forEach(([id, p]) => { posicoes[id] = { x: p.x - minX + opt.x0, y: p.y - minY + yBase }; });
            yBase += maxY - minY + 80;
        });

        Object.values(posicoes).forEach(p => { p.x = Math.round(p.x); p.y = Math.round(p.y); });
        return { posicoes, handles, ocultos: escondidos };
    }

    // ------------------------------------------------------------------ layouts especiais: tabela, matriz, linha do tempo, espinha
    // Além de posicoes/handles, devolvem: celulas (tamanho de cada bloco-célula), arestasOcultas (ids de conexões que o
    // próprio desenho substitui) e guias (linhas extras: a espinha da linha do tempo, os ossos do peixe).
    function prepararLayout(nos, arestas, tamanhos) {
        const arvore = aplicarOrdemManual(montarArvore(nos, arestas), nos);
        const escondidos = ocultos(nos, arvore);
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const tam = id => (tamanhos && tamanhos[id]) || estimarTamanho(porId.get(id));
        const arestaDe = new Map();
        arestas.filter(ehHierarquia).forEach(a => { const k = `${a.source}|${a.target}`; if (!arestaDe.has(k)) arestaDe.set(k, a); });
        const visiveis = id => (arvore.filhos.get(id) || []).filter(f => !escondidos.has(f));
        return { arvore, escondidos, porId, tam, arestaDe, visiveis, raizes: arvore.raizes.filter(r => !escondidos.has(r)) };
    }

    // Layout "lógico" de um ramo (bloco + descendentes), com o bloco na origem
    function layoutDoRamo(P, nos, ramoId, tamanhos) {
        const conjunto = new Set([ramoId]);
        descendentes(P.arvore, ramoId).forEach(d => conjunto.add(d));
        const arestasRamo = [];
        const adicionar = pai => (P.arvore.filhos.get(pai) || []).forEach(f => {
            const o = P.arestaDe.get(`${pai}|${f}`);
            if (o) arestasRamo.push({ id: o.id, source: pai, target: f, kind: 'hierarquia' });
            adicionar(f);
        });
        adicionar(ramoId);
        return calcularLayout(nos.filter(n => conjunto.has(String(n.id))), arestasRamo, 'logico', tamanhos, { x0: 0, y0: 0 });
    }

    const CELULA_MIN = { w: 150, h: 56 };

    /**
     * Tabela em árvore (eixo "colunas": cada nível é uma coluna) e matriz (eixo "linhas": cada nível é uma linha).
     * Cada bloco vira uma célula que ocupa a faixa das suas folhas; com `cabecalho` o tópico central é uma faixa no topo.
     */
    function calcularTabela(cfg, nos, arestas, tamanhos, opt) {
        const P = prepararLayout(nos, arestas, tamanhos);
        const colunas = cfg.eixo === 'colunas';
        const posicoes = {}, celulas = {}, arestasOcultas = [];
        let deslocamento = 0;

        P.raizes.forEach(raiz => {
            const nivelDe = new Map(), faixa = new Map();
            let folhas = 0;
            const percorrer = (id, d) => {
                nivelDe.set(id, d);
                const kids = P.visiveis(id);
                if (kids.length === 0) { faixa.set(id, [folhas, folhas]); folhas++; return; }
                kids.forEach(k => percorrer(k, d + 1));
                faixa.set(id, [faixa.get(kids[0])[0], faixa.get(kids[kids.length - 1])[1]]);
            };
            percorrer(raiz, 0);

            const dimNivel = id => (colunas ? P.tam(id).w : P.tam(id).h);
            const dimCruz = id => (colunas ? P.tam(id).h : P.tam(id).w);
            const nivel = [];                                   // tamanho de cada nível (coluna ou linha)
            let unidade = colunas ? CELULA_MIN.h : CELULA_MIN.w;   // tamanho de cada folha
            nivelDe.forEach((d, id) => {
                nivel[d] = Math.max(nivel[d] || (colunas ? CELULA_MIN.w : CELULA_MIN.h), dimNivel(id));
                if (P.visiveis(id).length === 0) unidade = Math.max(unidade, dimCruz(id));
            });
            const d0 = cfg.cabecalho ? 1 : 0;
            const inicio = [];
            let acumulado = 0;
            for (let d = d0; d < nivel.length; d++) { inicio[d] = acumulado; acumulado += nivel[d]; }
            const alturaCab = cfg.cabecalho ? Math.max(P.tam(raiz).h, CELULA_MIN.h) : 0;
            const larguraNiveis = acumulado;
            const cruzTotal = folhas * unidade;

            nivelDe.forEach((d, id) => {
                if (cfg.cabecalho && d === 0) {
                    posicoes[id] = { x: opt.x0, y: opt.y0 + deslocamento };
                    celulas[id] = { w: larguraNiveis, h: alturaCab };
                    return;
                }
                const [a0, a1] = faixa.get(id);
                const cruzInicio = a0 * unidade, cruzTam = (a1 - a0 + 1) * unidade;
                if (colunas) {
                    posicoes[id] = { x: opt.x0 + inicio[d], y: opt.y0 + deslocamento + alturaCab + cruzInicio };
                    celulas[id] = { w: nivel[d], h: cruzTam };
                } else {
                    posicoes[id] = { x: opt.x0 + deslocamento + cruzInicio, y: opt.y0 + inicio[d] };
                    celulas[id] = { w: cruzTam, h: nivel[d] };
                }
            });
            P.arvore.filhos.forEach((lista, pai) => {
                if (!nivelDe.has(pai)) return;
                lista.forEach(f => { const o = P.arestaDe.get(`${pai}|${f}`); if (o) arestasOcultas.push(o.id); });
            });
            deslocamento += (colunas ? alturaCab + cruzTotal : cruzTotal) + 60;
        });
        return { posicoes, handles: {}, ocultos: P.escondidos, celulas, arestasOcultas, guias: [] };
    }

    /**
     * Linha do tempo: o tópico central à esquerda, uma espinha horizontal e os ramos principais ao longo dela,
     * alternando acima e abaixo; os desdobramentos de cada ramo seguem para a direita (layout "lógico").
     */
    function calcularLinhaTempo(cfg, nos, arestas, tamanhos, opt) {
        const P = prepararLayout(nos, arestas, tamanhos);
        const posicoes = {}, handles = {}, arestasOcultas = [], guias = [];
        const FOLGA_ESPINHA = 36, FOLGA_COLUNA = 40;
        let yBase = opt.y0;

        P.raizes.forEach(raiz => {
            const mains = P.visiveis(raiz);
            const tr = P.tam(raiz);
            const rel = {}, guiasRaiz = [];
            const fim = { cima: 0, baixo: 0 };
            let colunaMinima = tr.w + 60, xMax = tr.w;
            mains.forEach((m, i) => {
                const lado = i % 2 === 0 ? 'cima' : 'baixo';
                const r = layoutDoRamo(P, nos, m, tamanhos);
                const h = Math.max(...Object.entries(r.posicoes).map(([id, p]) => p.y + P.tam(id).h));
                const w = Math.max(...Object.entries(r.posicoes).map(([id, p]) => p.x + P.tam(id).w));
                const xm = Math.max(colunaMinima, fim[lado]);
                const yOff = lado === 'cima' ? -FOLGA_ESPINHA - h : FOLGA_ESPINHA;
                Object.entries(r.posicoes).forEach(([id, p]) => { rel[id] = { x: xm + p.x, y: yOff + p.y }; });
                Object.keys(r.handles).forEach(id => { handles[id] = ['right', 'left']; });
                const tm = P.tam(m), pm = rel[m], xc = pm.x + tm.w / 2;
                guiasRaiz.push({ x1: xc, y1: 0, x2: xc, y2: lado === 'cima' ? pm.y + tm.h : pm.y });
                const o = P.arestaDe.get(`${raiz}|${m}`);
                if (o) arestasOcultas.push(o.id);
                fim[lado] = xm + w + FOLGA_COLUNA;
                colunaMinima = xm + tm.w + 20;
                xMax = Math.max(xMax, xm + tm.w);
            });
            rel[raiz] = { x: 0, y: -tr.h / 2 };
            if (mains.length > 0) guiasRaiz.push({ x1: tr.w, y1: 0, x2: xMax + 30, y2: 0 });

            const ys = Object.entries(rel).map(([id, p]) => [p.y, p.y + P.tam(id).h]);
            const minY = Math.min(...ys.map(v => v[0])), maxY = Math.max(...ys.map(v => v[1]));
            Object.entries(rel).forEach(([id, p]) => { posicoes[id] = { x: p.x + opt.x0, y: p.y - minY + yBase }; });
            guiasRaiz.forEach(g => guias.push({ x1: g.x1 + opt.x0, y1: g.y1 - minY + yBase, x2: g.x2 + opt.x0, y2: g.y2 - minY + yBase }));
            yBase += maxY - minY + 80;
        });
        Object.values(posicoes).forEach(p => { p.x = Math.round(p.x); p.y = Math.round(p.y); });
        guias.forEach(g => { g.x1 = Math.round(g.x1); g.y1 = Math.round(g.y1); g.x2 = Math.round(g.x2); g.y2 = Math.round(g.y2); });
        return { posicoes, handles, ocultos: P.escondidos, celulas: {}, arestasOcultas, guias };
    }

    /**
     * Espinha de peixe: a "cabeça" (tópico central) à direita, a espinha horizontal e os ramos principais como ossos
     * inclinados acima e abaixo dela. As causas (filhos do ramo) ficam encostadas no osso, ligadas por linhas horizontais;
     * os níveis seguintes ficam em lista recuada sob cada causa.
     */
    function calcularEspinha(cfg, nos, arestas, tamanhos, opt) {
        const P = prepararLayout(nos, arestas, tamanhos);
        const posicoes = {}, handles = {}, arestasOcultas = [], guias = [];
        const FOLGA_ESPINHA = 24, FOLGA_PILHA = 14, RECUO = 28, GAP_LINHA = 10, FOLGA_OSSO = 12;
        let yBase = opt.y0;

        P.raizes.forEach(raiz => {
            const mains = P.visiveis(raiz);
            const tr = P.tam(raiz);
            const rel = {}, guiasRaiz = [];
            rel[raiz] = { x: 0, y: -tr.h / 2 };
            const limite = { cima: -30, baixo: -30 };
            let xsAnterior = -20, xMin = 0;

            mains.forEach((m, i) => {
                const lado = i % 2 === 0 ? 'cima' : 'baixo';
                const tm = P.tam(m);
                // linhas da pilha: cada causa seguida dos seus descendentes (lista recuada)
                const grupos = [];
                P.visiveis(m).forEach(c => {
                    const linhas = [{ id: c, nivel: 0 }];
                    const descer = (pid, n) => P.visiveis(pid).forEach(f => { linhas.push({ id: f, nivel: n }); descer(f, n + 1); });
                    descer(c, 1);
                    grupos.push(linhas);
                });
                const alturaGrupo = linhas => linhas.reduce((s, l) => s + P.tam(l.id).h + GAP_LINHA, 0);
                const larguraGrupo = linhas => Math.max(...linhas.map(l => l.nivel * RECUO + P.tam(l.id).w));
                const pilha = grupos.reduce((s, g) => s + alturaGrupo(g), 0);
                const larguraMax = grupos.length ? Math.max(...grupos.map(larguraGrupo)) : 0;
                const comprimento = FOLGA_ESPINHA + pilha + FOLGA_PILHA;
                const inclinacao = Math.max(50, (pilha + 38) * 0.5);
                const esq = Math.max(FOLGA_OSSO + larguraMax, tm.w / 2);
                const dir = Math.max(inclinacao, tm.w / 2);
                const xc = Math.min(limite[lado] - dir, xsAnterior - 40 - inclinacao);
                const xs = xc + inclinacao;
                limite[lado] = xc - esq - 24;
                xsAnterior = xs;
                xMin = Math.min(xMin, xc - esq);

                // geometria do osso: do centro do bloco principal até a espinha (y = 0)
                const yMain = lado === 'cima' ? -(comprimento + tm.h) : comprimento;
                const yPontaOsso = lado === 'cima' ? yMain + tm.h : yMain;
                rel[m] = { x: xc - tm.w / 2, y: yMain };
                guiasRaiz.push({ x1: xc, y1: yPontaOsso, x2: xs, y2: 0 });
                const xOsso = y => xc + inclinacao * (y - yPontaOsso) / (0 - yPontaOsso);
                const oRaiz = P.arestaDe.get(`${raiz}|${m}`);
                if (oRaiz) arestasOcultas.push(oRaiz.id);

                let y = lado === 'cima' ? yPontaOsso + FOLGA_PILHA : FOLGA_ESPINHA;
                grupos.forEach(linhas => {
                    const causa = linhas[0];
                    const tc = P.tam(causa.id);
                    const yMeio = y + tc.h / 2;
                    const direita = xOsso(yMeio) - FOLGA_OSSO;
                    const xCausa = direita - larguraGrupo(linhas);
                    linhas.forEach(l => {
                        rel[l.id] = { x: xCausa + l.nivel * RECUO, y };
                        y += P.tam(l.id).h + GAP_LINHA;
                    });
                    guiasRaiz.push({ x1: xCausa + tc.w, y1: yMeio, x2: xOsso(yMeio), y2: yMeio });
                    const oc = P.arestaDe.get(`${m}|${causa.id}`);
                    if (oc) arestasOcultas.push(oc.id);
                    linhas.slice(1).forEach(l => {
                        const pai = P.arvore.pai.get(l.id);
                        const o = P.arestaDe.get(`${pai}|${l.id}`);
                        if (o) handles[o.id] = ['bottom', 'left'];
                    });
                });
            });
            if (mains.length > 0) guiasRaiz.push({ x1: xMin - 30, y1: 0, x2: 0, y2: 0 });

            const ys = Object.entries(rel).map(([id, p]) => [p.y, p.y + P.tam(id).h]);
            const minY = Math.min(...ys.map(v => v[0])), maxY = Math.max(...ys.map(v => v[1]));
            const minX = Math.min(...Object.values(rel).map(p => p.x), ...guiasRaiz.map(g => Math.min(g.x1, g.x2)));
            Object.entries(rel).forEach(([id, p]) => { posicoes[id] = { x: p.x - minX + opt.x0, y: p.y - minY + yBase }; });
            guiasRaiz.forEach(g => guias.push({ x1: g.x1 - minX + opt.x0, y1: g.y1 - minY + yBase, x2: g.x2 - minX + opt.x0, y2: g.y2 - minY + yBase }));
            yBase += maxY - minY + 80;
        });
        Object.values(posicoes).forEach(p => { p.x = Math.round(p.x); p.y = Math.round(p.y); });
        guias.forEach(g => { g.x1 = Math.round(g.x1); g.y1 = Math.round(g.y1); g.x2 = Math.round(g.x2); g.y2 = Math.round(g.y2); });
        return { posicoes, handles, ocultos: P.escondidos, celulas: {}, arestasOcultas, guias };
    }

    function calcularLayout(nos, arestas, modo, tamanhos, opcoes) {
        const cfg = MODOS[modo];
        if (!cfg) throw new Error('Modo de layout desconhecido: ' + modo);
        const opt = Object.assign({ x0: MARGEM_X, y0: MARGEM_Y }, opcoes || {});
        if (cfg.direcao === 'dois-lados') return calcularMapa(nos, arestas, tamanhos, opt);
        if (cfg.direcao === 'tabela') return calcularTabela(cfg, nos, arestas, tamanhos, opt);
        if (cfg.direcao === 'linha-tempo') return calcularLinhaTempo(cfg, nos, arestas, tamanhos, opt);
        if (cfg.direcao === 'espinha') return calcularEspinha(cfg, nos, arestas, tamanhos, opt);

        const arvore = aplicarOrdemManual(montarArvore(nos, arestas), nos);
        const escondidos = ocultos(nos, arvore);
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const tam = id => (tamanhos && tamanhos[id]) || estimarTamanho(porId.get(id));
        const visiveis = id => (arvore.filhos.get(id) || []).filter(f => !escondidos.has(f));
        // Organograma compacto: quando todos os filhos de um bloco são folhas (2 ou mais), eles são empilhados na vertical
        const empilhar = opt.empilharFolhas !== undefined ? !!opt.empilharFolhas : !!cfg.empilharFolhas;
        const empilhados = new Set();

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

            // Estrutura efetiva de cada bloco: a do próprio (data.estrutura) ou a herdada do pai ("seguir a estrutura do pai")
            const estrutura = new Map();
            const resolver = (id, herdada) => {
                const proprio = porId.get(id)?.data?.estrutura;
                const efetiva = ESTRUTURAS.includes(proprio) ? proprio : herdada;
                estrutura.set(id, efetiva);
                visiveis(id).forEach(f => resolver(f, efetiva));
            };
            raizesVisiveis.forEach(r => resolver(r, 'organograma'));

            // Pilha: linhas {id, nivel} dispostas na vertical sob um bloco (estrutura "árvore": todo o ramo, recuado por nível;
            // organograma compacto: filhos que são só folhas). null quando o bloco não usa pilha.
            const pilhas = new Map();
            const linhasDaPilha = id => {
                if (pilhas.has(id)) return pilhas.get(id);
                let linhas = null;
                const kids = visiveis(id);
                if (cfg.direcao === 'baixo' && kids.length > 0) {
                    if (estrutura.get(id) === 'arvore') {
                        linhas = [];
                        const descer = (pid, n) => visiveis(pid).forEach(f => { linhas.push({ id: f, nivel: n }); descer(f, n + 1); });
                        descer(id, 1);
                    } else if (empilhar && kids.length >= 2 && kids.every(f => visiveis(f).length === 0)) {
                        linhas = kids.map(f => ({ id: f, nivel: 1 }));
                    }
                }
                pilhas.set(id, linhas);
                return linhas;
            };

            // 1) extensão de cada subárvore no eixo cruzado
            const extensao = new Map();
            const medir = id => {
                const proprio = cruz(tam(id));
                const kids = visiveis(id);
                const linhas = linhasDaPilha(id);
                if (linhas) {
                    const alcance = Math.max(...linhas.map(l => l.nivel * RECUO_PILHA + cruz(tam(l.id))));
                    const e = Math.max(proprio, proprio / 2 + alcance);
                    extensao.set(id, e);
                    return e;
                }
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
                if (linhasDaPilha(id)) return;   // as linhas da pilha não formam uma linha própria do organograma
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
                if (kids.length === 0 || linhasDaPilha(id)) {
                    c = inicio + (linhasDaPilha(id) ? proprio : total) / 2;
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
                const linhas = linhasDaPilha(id);
                if (linhas) {
                    let y = posicoes[id].y + t.h + cfg.gapNivel / 2;
                    linhas.forEach(l => {
                        const tf = tam(l.id);
                        posicoes[l.id] = { x: c + l.nivel * RECUO_PILHA, y };
                        centro.set(l.id, c + l.nivel * RECUO_PILHA + tf.w / 2);
                        empilhados.add(l.id);
                        y += tf.h + GAP_PILHA;
                    });
                }
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
            if (arvore.pai.get(d) === o && posicoes[o] && posicoes[d]) handles[a.id] = empilhados.has(d) ? ['bottom', 'left'] : cfg.handles;
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
        MODOS, ESTRUTURAS, ehHierarquia, estimarTamanho, montarArvore, aplicarOrdemManual, ordenarPorPosicao, descendentes, ocultos, profundidade,
        calcularLayout, moverNaArvore, clonarRamo, irmaos, ehAncestral,
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaArvore = api;
})(typeof window !== 'undefined' ? window : globalThis);

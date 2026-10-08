/* Editor de Diagramas (DOC.071) - módulo "conteudo"
 * Conteúdo dos blocos: marcadores (prioridade, progresso, bandeira, estrela, pessoa), notas, links, vagas e
 * contagem de efetivo por ramo, além da comparação com o cadastro do RH.
 * Código PURO (sem DOM), testado em Node (procedures/tests/js/conteudo.test.js). O PDF usa o espelho em Python
 * (procedures/services/diagram_conteudo.py) e um teste compara as duas implementações.
 */
(function (raiz) {
    'use strict';

    const CORES = {
        vermelho: '#ef4444', laranja: '#f59e0b', azul: '#3b82f6', roxo: '#8b5cf6',
        verde: '#22c55e', ciano: '#06b6d4', cinza: '#94a3b8',
    };
    const CORES_DOS_GRUPOS = ['vermelho', 'laranja', 'azul', 'roxo', 'verde', 'cinza'];
    const NOMES_DAS_CORES = { vermelho: 'vermelha', laranja: 'laranja', azul: 'azul', roxo: 'roxa', verde: 'verde', cinza: 'cinza' };

    const GRUPOS = [
        {
            id: 'prioridade', nome: 'Prioridade',
            itens: [1, 2, 3, 4, 5, 6, 7].map(n => ({
                id: `prio-${n}`, tipo: 'numero', valor: n, rotulo: `Prioridade ${n}`,
                cor: CORES[n === 1 ? 'vermelho' : n === 2 ? 'laranja' : n === 3 ? 'azul' : 'cinza'],
            })),
        },
        {
            id: 'progresso', nome: 'Progresso',
            itens: [0, 25, 50, 75, 100].map(p => ({ id: `prog-${p}`, tipo: 'progresso', valor: p, rotulo: `${p}% concluído`, cor: CORES.verde })),
        },
        {
            id: 'bandeira', nome: 'Bandeira',
            itens: CORES_DOS_GRUPOS.map(c => ({ id: `band-${c}`, tipo: 'bandeira', valor: c, rotulo: `Bandeira ${NOMES_DAS_CORES[c]}`, cor: CORES[c] })),
        },
        {
            id: 'estrela', nome: 'Estrela',
            itens: CORES_DOS_GRUPOS.map(c => ({ id: `estr-${c}`, tipo: 'estrela', valor: c, rotulo: `Estrela ${NOMES_DAS_CORES[c]}`, cor: CORES[c] })),
        },
        {
            id: 'pessoa', nome: 'Pessoa',
            itens: CORES_DOS_GRUPOS.map(c => ({ id: `pess-${c}`, tipo: 'pessoa', valor: c, rotulo: `Pessoa ${NOMES_DAS_CORES[c]}`, cor: CORES[c] })),
        },
    ];

    const POR_ID = {};
    const ORDEM = [];
    GRUPOS.forEach(g => g.itens.forEach(m => { POR_ID[m.id] = m; ORDEM.push(m.id); }));

    const MAX_MARCADORES = 8;
    const MAX_LINKS = 5;
    const MAX_NOTA = 2000;

    function marcadorPorId(id) { return POR_ID[id] || null; }
    function marcadorValido(id) { return Object.prototype.hasOwnProperty.call(POR_ID, id); }

    // Marcadores em uso no diagrama, na ordem do catálogo (base da legenda)
    function marcadoresEmUso(nos) {
        const usados = new Set();
        nos.forEach(n => ((n.data && n.data.markers) || []).forEach(m => { if (marcadorValido(m)) usados.add(m); }));
        return ORDEM.filter(id => usados.has(id));
    }

    function ehVaga(no) { return !!(no.data && no.data.vaga === true); }
    function ehPessoa(no) { return !ehVaga(no) && !!(no.data && no.data.colab); }

    /**
     * Efetivo de cada bloco: pessoas (blocos com colaborador) e vagas (blocos marcados como vago) na subárvore,
     * contando o próprio bloco. `arvore` = montarArvore de layout_arvore.js.
     */
    function contagemEfetivo(nos, arvore) {
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const memo = new Map();
        const contar = (id, pilha) => {
            if (memo.has(id)) return memo.get(id);
            const no = porId.get(id);
            const total = { pessoas: ehPessoa(no) ? 1 : 0, vagas: ehVaga(no) ? 1 : 0 };
            if (pilha.has(id)) return total;
            pilha.add(id);
            (arvore.filhos.get(id) || []).forEach(f => { const c = contar(f, pilha); total.pessoas += c.pessoas; total.vagas += c.vagas; });
            pilha.delete(id);
            memo.set(id, total);
            return total;
        };
        const resultado = {};
        nos.forEach(n => { resultado[String(n.id)] = contar(String(n.id), new Set()); });
        return resultado;
    }

    /** Resumo por ramo: uma linha por bloco do 1º nível (filhos das raízes) e o total geral. */
    function resumoPorRamo(nos, arvore) {
        const efetivo = contagemEfetivo(nos, arvore);
        const porId = new Map(nos.map(n => [String(n.id), n]));
        const linhas = [];
        arvore.filhos.forEach((filhos, id) => {
            if (arvore.pai.has(id)) return;                      // só raízes
            filhos.forEach(f => linhas.push(linhaDeResumo(porId.get(f), efetivo[f])));
        });
        const total = { pessoas: 0, vagas: 0 };
        arvore.filhos.forEach((_, id) => {
            if (arvore.pai.has(id)) return;
            total.pessoas += efetivo[id].pessoas;
            total.vagas += efetivo[id].vagas;
        });
        return { linhas, total: Object.assign(total, { total: total.pessoas + total.vagas, ocupacao: ocupacao(total) }) };
    }

    function ocupacao(c) {
        const quadro = c.pessoas + c.vagas;
        return quadro === 0 ? null : Math.round((c.pessoas / quadro) * 1000) / 10;
    }

    function linhaDeResumo(no, c) {
        const dados = no.data || {};
        const nome = dados.colab ? (dados.colab.nome || dados.label) : dados.label;
        return { id: String(no.id), nome: nome || `Bloco ${no.id}`, pessoas: c.pessoas, vagas: c.vagas, total: c.pessoas + c.vagas, ocupacao: ocupacao(c) };
    }

    /**
     * Compara os blocos de colaborador com o cadastro atual do RH.
     * `atuais`: { [colabId]: { existe, nome, cargo, tem_foto } }. Retorna a lista de diferenças (sem alterar nada).
     * A função só é atualizada quando não foi personalizada no diagrama (igual à última lida do RH: cargoRH).
     */
    function diferencasRH(nos, atuais) {
        const diferencas = [];
        nos.forEach(n => {
            const colab = n.data && n.data.colab;
            if (!colab) return;
            const atual = atuais[colab.id];
            const rotulo = colab.nome || (n.data && n.data.label) || `Bloco ${n.id}`;
            if (!atual || atual.existe === false) {
                if (!colab.removido) diferencas.push({ id: String(n.id), rotulo, removido: true });
                return;
            }
            const d = { id: String(n.id), rotulo };
            if ((atual.nome || '') !== (colab.nome || '')) d.nome = { de: colab.nome || '', para: atual.nome || '' };
            const cargoAtual = atual.cargo || '';
            const cargoDoBloco = colab.cargo || '';
            if (cargoAtual !== cargoDoBloco) {
                if (colab.cargoRH !== undefined && cargoDoBloco === colab.cargoRH) d.cargo = { de: cargoDoBloco, para: cargoAtual };
                else d.cargoPersonalizado = { bloco: cargoDoBloco, rh: cargoAtual };   // mantido como está
            }
            if (!!atual.tem_foto !== (colab.temFoto !== false)) d.temFoto = { de: colab.temFoto !== false, para: !!atual.tem_foto };
            if (colab.removido) d.reencontrado = true;
            if (d.nome || d.cargo || d.temFoto || d.reencontrado || d.cargoPersonalizado) diferencas.push(d);
        });
        return diferencas;
    }

    function urlValida(url) {
        return typeof url === 'string' && /^https?:\/\/[^\s]+$/i.test(url) && url.length <= 500;
    }

    function linkValido(link) {
        if (!link || typeof link !== 'object') return false;
        if (link.tipo === 'url') return urlValida(link.url);
        if (link.tipo === 'procedimento') return Number.isInteger(link.id);
        if (link.tipo === 'diagrama') return typeof link.id === 'string' && link.id.length > 0 && link.id.length <= 64;
        return false;
    }

    function normalizarLinks(lista) {
        return (Array.isArray(lista) ? lista : []).filter(linkValido).slice(0, MAX_LINKS)
            .map(l => Object.assign({}, l, { rotulo: String(l.rotulo || '').slice(0, 120) }));
    }

    const api = {
        CORES, GRUPOS, ORDEM, POR_ID, MAX_MARCADORES, MAX_LINKS, MAX_NOTA,
        marcadorPorId, marcadorValido, marcadoresEmUso, ehVaga, ehPessoa,
        contagemEfetivo, resumoPorRamo, diferencasRH, urlValida, linkValido, normalizarLinks,
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.DiagramaConteudo = api;
})(typeof window !== 'undefined' ? window : globalThis);

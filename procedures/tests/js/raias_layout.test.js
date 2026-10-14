/* Testes do auto-layout por raias (Node, sem dependências). Executar: node procedures/tests/js/raias_layout.test.js
 * O módulo raias_layout.js é um script clássico (usa globais do editor): aqui os globais necessários são simulados. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const pasta = path.join(__dirname, '..', '..', 'static', 'procedures', 'js', 'diagrama');
global.DiagramaArvore = require(path.join(pasta, 'layout_arvore.js'));
global.zoomLevel = 1;
global.document = { getElementById: () => null };
global.topologia = { nodes: [], edges: [], lanes: [] };
global.ALTURA_RAIA_RECOLHIDA = 64;
global.PADDING_RAIA = 30;
global.ALTURA_NIVEL_NA_RAIA = 65;
global.ALTURA_MINIMA_RAIA = 130;
global.alturaDoBlocoNoCanvas = () => 70;
global.nosOcultos = () => new Set();
global.raiaRecolhida = lane => (topologia.raias_recolhidas || []).includes(lane);
global.obterListaRaiasOrdenada = () => topologia.lanes;
global.noEntreRaias = (n, lanes) => {
    const abaixo = n.data && n.data.laneAbaixo;
    if (!abaixo) return false;
    const i = lanes.indexOf(n.data.lane);
    return i !== -1 && lanes[i + 1] === abaixo;
};
const fonte = fs.readFileSync(path.join(pasta, 'raias_layout.js'), 'utf8');
const inicio = fonte.indexOf('const ALTURA_LINHA_NA_RAIA');
const fim = fonte.indexOf('function reorganizarAutoLayout');
eval(fonte.slice(inicio, fim) + ';global.posicionarAutomaticoPorRaias = posicionarAutomaticoPorRaias; global.ALTURA_LINHA_NA_RAIA = ALTURA_LINHA_NA_RAIA;');

let total = 0;
function teste(nome, fn) {
    try { fn(); total++; console.log('OK    ' + nome); }
    catch (e) { console.log('FALHA ' + nome + '\n      ' + e.message); process.exitCode = 1; }
}

function montar(lanes, blocos, ligacoes) {
    topologia.lanes = lanes;
    topologia.raias_recolhidas = [];
    topologia.nodes = blocos.map(([id, lane, dados]) => ({ id, position: { x: 0, y: 0 }, data: Object.assign({ lane }, dados || {}) }));
    topologia.edges = ligacoes.map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    posicionarAutomaticoPorRaias(true);
    return Object.fromEntries(topologia.nodes.map(n => [n.id, n.position]));
}

function semSobreposicao(P) {
    const ids = Object.keys(P);
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const a = P[ids[i]], b = P[ids[j]];
        const separados = a.x + 190 <= b.x || b.x + 190 <= a.x || a.y + 70 <= b.y || b.y + 70 <= a.y;
        assert.ok(separados, `${ids[i]} e ${ids[j]} se sobrepõem`);
    }
}

teste('filho na mesma raia do pai fica abaixo dele, sem sobreposição', () => {
    const P = montar(['Gerência', 'Supervisão'],
        [['g', 'Gerência'], ['s', 'Supervisão'], ['s1', 'Supervisão'], ['s2', 'Supervisão'], ['s3', 'Supervisão']],
        [['g', 's'], ['s', 's1'], ['s', 's2'], ['s', 's3']]);
    assert.ok(P.s1.y > P.s.y && P.s2.y > P.s.y && P.s3.y > P.s.y);
    assert.strictEqual(P.s1.y - P.s.y, ALTURA_LINHA_NA_RAIA);
    semSobreposicao(P);
});

teste('a raia cresce para caber as linhas e a seguinte desce junto', () => {
    const P = montar(['A', 'B'],
        [['a', 'A'], ['a1', 'A'], ['a2', 'A'], ['b', 'B']],
        [['a', 'a1'], ['a1', 'a2'], ['a2', 'b']]);
    assert.strictEqual(P.a1.y - P.a.y, ALTURA_LINHA_NA_RAIA);
    assert.strictEqual(P.a2.y - P.a1.y, ALTURA_LINHA_NA_RAIA);
    // a raia A tem 3 linhas (altura = 30 + 2 * 130 + 70 + 30 = 390); B começa depois dela
    assert.strictEqual(P.b.y, 40 + 390 + 30);
    semSobreposicao(P);
});

teste('pai e neto na mesma raia (com um filho de outra raia no meio) não ficam um sobre o outro', () => {
    const P = montar(['A', 'B'],
        [['p', 'A'], ['c', 'B'], ['g', 'A']],
        [['p', 'c'], ['c', 'g']]);
    semSobreposicao(P);
    assert.notStrictEqual(P.p.y, P.g.y);
});

teste('blocos de raias diferentes continuam cada um na sua raia', () => {
    const P = montar(['A', 'B', 'C'], [['a', 'A'], ['b', 'B'], ['c', 'C']], [['a', 'b'], ['b', 'c']]);
    assert.ok(P.a.y < P.b.y && P.b.y < P.c.y);
    assert.strictEqual(P.a.x, P.b.x);
});

teste('estrutura "arvore" no bloco: filhos na mesma coluna, recuados por nível, descendo na raia', () => {
    const P = montar(['A'],
        [['r', 'A', { estrutura: 'arvore' }], ['f1', 'A'], ['f2', 'A'], ['n1', 'A']],
        [['r', 'f1'], ['r', 'f2'], ['f1', 'n1']]);
    assert.ok(P.f1.x > P.r.x && P.f1.x - P.r.x < 100);        // recuo, não uma coluna nova
    assert.ok(P.n1.x > P.f1.x);                                 // neto recuado mais um nível
    assert.ok(P.f1.y > P.r.y && P.f2.y > P.f1.y || P.n1.y > P.f1.y);
    semSobreposicao(P);
});

teste('estrutura padrão (organograma) mantém os filhos lado a lado', () => {
    const P = montar(['A', 'B'], [['r', 'A'], ['f1', 'B'], ['f2', 'B']], [['r', 'f1'], ['r', 'f2']]);
    assert.strictEqual(P.f1.y, P.f2.y);
    assert.ok(P.f2.x > P.f1.x);
    semSobreposicao(P);
});

teste('raia recolhida usa altura fixa e bloco entre raias fica sobre a divisa', () => {
    topologia.lanes = ['A', 'B', 'C'];
    topologia.raias_recolhidas = ['B'];
    topologia.nodes = [
        { id: 'a', position: { x: 0, y: 0 }, data: { lane: 'A' } },
        { id: 'm', position: { x: 0, y: 0 }, data: { lane: 'A', laneAbaixo: 'B' } },
        { id: 'c', position: { x: 0, y: 0 }, data: { lane: 'C' } },
    ];
    topologia.edges = [];
    posicionarAutomaticoPorRaias(true);
    const P = Object.fromEntries(topologia.nodes.map(n => [n.id, n.position]));
    assert.strictEqual(P.a.y, 40 + 30);
    assert.strictEqual(P.m.y, 40 + 130 - 35);                  // divisa A/B (meia altura do bloco)
    assert.strictEqual(P.c.y, 40 + 130 + 64 + 30);             // A: 130 px (mínima); B recolhida: 64 px
});

teste('altura da raia acompanha o conteúdo: raia com uma linha é compacta', () => {
    const P = montar(['A', 'B'], [['a', 'A'], ['b', 'B']], [['a', 'b']]);
    assert.strictEqual(P.b.y - P.a.y, 130);                     // altura mínima (130), sem os 220 antigos
});

teste('nível escolhido na raia: coordenada predefinida de altura (65 px por nível) com prioridade sobre o automático', () => {
    const P = montar(['A', 'B'],
        [['a', 'A'], ['b', 'B', { nivelRaia: 1 }], ['c', 'B', { nivelRaia: 3 }], ['d', 'B']],
        [['a', 'b'], ['a', 'c'], ['a', 'd']]);
    const topoB = 40 + 130;
    assert.strictEqual(P.b.y, topoB + 30);                  // nível 1 = topo útil da raia
    assert.strictEqual(P.c.y, topoB + 30 + 2 * 65);         // nível 3 = 130 px abaixo do nível 1
    semSobreposicao(P);
});

teste('a raia cresce para caber um nível mais baixo', () => {
    const P = montar(['A', 'B'], [['a', 'A', { nivelRaia: 4 }], ['b', 'B']], [['a', 'b']]);
    // A: 30 + 3 * 65 + 70 + 30 = 325 (maior que a altura mínima de 130)
    assert.strictEqual(P.b.y, 40 + 325 + 30);
});

teste('bloco automático não cai sobre um bloco de nível fixo na mesma coluna', () => {
    const P = montar(['A'], [['p', 'A', { nivelRaia: 1 }], ['q', 'A']], [['p', 'q']]);
    assert.ok(P.q.y - P.p.y >= 100);
});

teste('lista recuada com vários níveis não invade a coluna do bloco vizinho', () => {
    const P = montar(['A', 'B'],
        [['r', 'A'], ['h1', 'A', { estrutura: 'arvore' }], ['h2', 'A'],
         ['a1', 'B'], ['a2', 'B'], ['a3', 'B'], ['a4', 'B'], ['a5', 'B'], ['b1', 'B']],
        [['r', 'h1'], ['r', 'h2'], ['h1', 'a1'], ['h1', 'a2'], ['a2', 'a3'], ['a3', 'a4'], ['a4', 'a5'], ['h2', 'b1']]);
    semSobreposicao(P);
});

teste('lista recuada: a raia se estende e os filhos descem sem se sobrepor', () => {
    const P = montar(['G', 'L'],
        [['g', 'G', { estrutura: 'arvore' }], ['f1', 'L'], ['f2', 'L'], ['f3', 'L'], ['f4', 'L'], ['outro', 'G']],
        [['g', 'f1'], ['g', 'f2'], ['g', 'f3'], ['g', 'f4']]);
    semSobreposicao(P);
    assert.ok(P.f2.y > P.f1.y && P.f3.y > P.f2.y && P.f4.y > P.f3.y);
    // a raia L cresceu: 4 linhas de 130 px
    assert.ok(P.f4.y - P.f1.y >= 3 * 100);
});

teste('filho do bloco vizinho não é empurrado para baixo pela lista recuada ao lado', () => {
    const P = montar(['S', 'L'],
        [['r', 'S'], ['e', 'S', { estrutura: 'arvore' }], ['m', 'S'], ['k1', 'L'], ['k2', 'L'], ['k3', 'L'], ['n', 'L']],
        [['r', 'e'], ['r', 'm'], ['e', 'k1'], ['e', 'k2'], ['e', 'k3'], ['m', 'n']]);
    semSobreposicao(P);
    assert.strictEqual(P.n.y, P.k1.y);                       // o vizinho fica na primeira linha da raia
    assert.ok(P.k3.y > P.k1.y);
});

teste('lista recuada: as ligações dos filhos entram pela lateral e voltam ao padrão sem a estrutura', () => {
    montar(['S', 'L'], [['e', 'S', { estrutura: 'arvore' }], ['k1', 'L'], ['k2', 'L']], [['e', 'k1'], ['e', 'k2']]);
    assert.deepStrictEqual(topologia.edges.map(x => [x.sourceHandle, x.targetHandle]), [['bottom', 'left'], ['bottom', 'left']]);
    delete topologia.nodes[0].data.estrutura;                  // volta a "seguir o pai" (organograma)
    posicionarAutomaticoPorRaias(false);
    assert.deepStrictEqual(topologia.edges.map(x => [x.sourceHandle, x.targetHandle]), [['bottom', 'top'], ['bottom', 'top']]);
});

console.log(process.exitCode ? 'COM FALHAS' : `TODOS OS ${total} TESTES OK`);

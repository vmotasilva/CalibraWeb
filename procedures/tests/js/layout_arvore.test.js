/* Testes do motor de layout em árvore (Node, sem dependências).
 * Executar: node procedures/tests/js/layout_arvore.test.js   (também roda via test_diagram_qms.py)
 */
const assert = require('assert');
const path = require('path');
const A = require(path.join(__dirname, '..', '..', 'static', 'procedures', 'js', 'diagrama', 'layout_arvore.js'));

let total = 0;
function teste(nome, fn) {
    try { fn(); total++; console.log('OK    ' + nome); }
    catch (e) { console.log('FALHA ' + nome + '\n      ' + e.message); process.exitCode = 1; }
}

const no = (id, extra = {}) => Object.assign({ id: String(id), type: 'process', position: { x: 0, y: 0 }, data: { label: 'B' + id } }, extra);
const lig = (a, b, extra = {}) => Object.assign({ id: `e-${a}-${b}`, source: String(a), target: String(b) }, extra);
const T = { w: 180, h: 64 };
const tamanhos = ids => Object.fromEntries(ids.map(i => [String(i), T]));

function semSobreposicao(posicoes, tam = T) {
    const itens = Object.entries(posicoes);
    for (let i = 0; i < itens.length; i++) for (let j = i + 1; j < itens.length; j++) {
        const [, a] = itens[i], [, b] = itens[j];
        if (a.x < b.x + tam.w && b.x < a.x + tam.w && a.y < b.y + tam.h && b.y < a.y + tam.h) return false;
    }
    return true;
}

// --------------------------------------------------------------------------- organograma
teste('organograma: filhos lado a lado, centralizados sob o pai', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(1, 3), lig(1, 4)];
    const r = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4]), { empilharFolhas: false });
    const p = r.posicoes;
    assert.strictEqual(new Set([p[2].y, p[3].y, p[4].y]).size, 1, 'filhos na mesma linha');
    assert.ok(p[2].x < p[3].x && p[3].x < p[4].x, 'ordem das conexões = ordem na tela');
    assert.strictEqual(p[3].x - p[2].x, 180 + 40, 'espaçamento horizontal');
    assert.ok(Math.abs((p[2].x + p[4].x + 180) / 2 - (p[1].x + 90)) <= 1, 'pai centralizado sobre os filhos');
    assert.strictEqual(p[2].y - p[1].y, 64 + 90, 'espaço vertical entre níveis');
    assert.ok(semSobreposicao(p));
});

teste('organograma: subárvores largas empurram os irmãos (sem sobreposição)', () => {
    const nos = [1, 2, 3, 4, 5, 6, 7].map(no);
    const arestas = [lig(1, 2), lig(1, 3), lig(2, 4), lig(2, 5), lig(2, 6), lig(3, 7)];
    const r = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4, 5, 6, 7]), { empilharFolhas: false });
    assert.ok(semSobreposicao(r.posicoes));
    assert.ok(r.posicoes[3].x > r.posicoes[6].x, 'o irmão 3 fica depois de toda a subárvore do 2');
    ['bottom'].forEach(h => assert.strictEqual(r.handles['e-1-2'][0], h));
    assert.strictEqual(r.handles['e-1-2'][1], 'top');
});

teste('organograma: várias raízes ficam lado a lado', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(3, 4)];
    const p = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4]), { empilharFolhas: false }).posicoes;
    assert.strictEqual(p[1].y, p[3].y);
    assert.ok(p[3].x > p[2].x, 'segunda árvore à direita da primeira');
    assert.ok(semSobreposicao(p));
});

teste('organograma: blocos de alturas diferentes não colidem entre níveis', () => {
    const nos = [1, 2, 3].map(no);
    const tam = { 1: { w: 180, h: 64 }, 2: { w: 200, h: 120 }, 3: { w: 180, h: 64 } };
    const p = A.calcularLayout(nos, [lig(1, 2), lig(1, 3)], 'organograma', tam, { empilharFolhas: false }).posicoes;
    assert.strictEqual(p[3].y - p[2].y, (120 - 64) / 2, 'bloco mais baixo centralizado na espessura do nível');
    assert.ok(p[2].y >= p[1].y + 64 + 90, 'nível abaixo respeita a altura do nível acima');
});

// --------------------------------------------------------------------------- lógico e lista
teste('lógico: níveis para a direita e irmãos empilhados', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(1, 3), lig(2, 4)];
    const r = A.calcularLayout(nos, arestas, 'logico', tamanhos([1, 2, 3, 4]));
    const p = r.posicoes;
    assert.ok(p[2].x > p[1].x + 180, 'filhos à direita do pai');
    assert.strictEqual(p[2].x, p[3].x);
    assert.ok(p[3].y > p[2].y, 'irmãos empilhados na ordem das conexões');
    assert.ok(semSobreposicao(p));
    assert.deepStrictEqual(r.handles['e-1-2'], ['right', 'left']);
});

teste('árvore (lista): cada bloco abaixo do anterior, recuado em relação ao pai', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(2, 3), lig(1, 4)];
    const r = A.calcularLayout(nos, arestas, 'arvore', tamanhos([1, 2, 3, 4]));
    const p = r.posicoes;
    assert.ok(p[2].y > p[1].y && p[3].y > p[2].y && p[4].y > p[3].y, 'ordem de leitura (profundidade)');
    assert.ok(p[2].x > p[1].x && p[3].x > p[2].x, 'recuo por nível');
    assert.strictEqual(p[4].x, p[2].x, 'irmãos no mesmo recuo');
    assert.deepStrictEqual(r.handles['e-1-2'], ['bottom', 'left']);
    assert.ok(semSobreposicao(p));
});

// --------------------------------------------------------------------------- recolher
teste('recolher: descendentes saem do layout e o pai se recentraliza', () => {
    const nos = [1, 2, 3, 4, 5].map(no);
    const arestas = [lig(1, 2), lig(1, 3), lig(2, 4), lig(2, 5)];
    const antes = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4, 5]), { empilharFolhas: false });
    nos[1].data.collapsed = true;            // recolhe o bloco 2
    const depois = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4, 5]), { empilharFolhas: false });
    assert.deepStrictEqual([...depois.ocultos].sort(), ['4', '5']);
    assert.strictEqual(depois.posicoes['4'], undefined);
    assert.ok(depois.posicoes[3].x - depois.posicoes[2].x < antes.posicoes[3].x - antes.posicoes[2].x, 'ramo recolhido ocupa menos espaço');
    assert.ok(Math.abs((depois.posicoes[2].x + depois.posicoes[3].x + 180) / 2 - (depois.posicoes[1].x + 90)) <= 1);
});

teste('recolher em cascata oculta todos os níveis abaixo', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(2, 3), lig(3, 4)];
    nos[0].data.collapsed = true;
    const r = A.calcularLayout(nos, arestas, 'organograma', tamanhos([1, 2, 3, 4]), { empilharFolhas: false });
    assert.deepStrictEqual([...r.ocultos].sort(), ['2', '3', '4']);
    assert.deepStrictEqual(Object.keys(r.posicoes), ['1']);
});

// --------------------------------------------------------------------------- estrutura da árvore
teste('conexões "relacao" não entram na árvore', () => {
    const nos = [1, 2, 3].map(no);
    const arvore = A.montarArvore(nos, [lig(1, 2), lig(1, 3, { kind: 'relacao' }), lig(2, 3, { kind: 'relacao' })]);
    assert.deepStrictEqual(arvore.filhos.get('1'), ['2']);
    assert.deepStrictEqual(arvore.raizes.sort(), ['1', '3']);
});

teste('um pai só e ciclos são ignorados (não trava)', () => {
    const nos = [1, 2, 3].map(no);
    const arvore = A.montarArvore(nos, [lig(1, 2), lig(3, 2), lig(2, 3), lig(3, 1)]);
    assert.strictEqual(arvore.pai.get('2'), '1');
    assert.strictEqual(arvore.pai.get('3'), '2');
    assert.ok(!arvore.pai.has('1'), 'a conexão que fecharia o ciclo é descartada');
    A.calcularLayout(nos, [lig(1, 2), lig(2, 3), lig(3, 1)], 'organograma', tamanhos([1, 2, 3]));
});

teste('ordem dos filhos = ordem das conexões', () => {
    const nos = [1, 2, 3, 4].map(no);
    assert.deepStrictEqual(A.montarArvore(nos, [lig(1, 4), lig(1, 2), lig(1, 3)]).filhos.get('1'), ['4', '2', '3']);
});

// --------------------------------------------------------------------------- mover / reordenar
teste('mover: troca de pai e reordena irmãos', () => {
    const nos = [1, 2, 3, 4, 5].map(no);
    const arestas = [lig(1, 2), lig(1, 3), lig(1, 4), lig(2, 5)];
    // 4 passa a ser filho de 2, antes do 5
    let r = A.moverNaArvore(nos, arestas, 4, 2, 5);
    assert.ok(r.ok);
    assert.deepStrictEqual(A.montarArvore(nos, r.arestas).filhos.get('2'), ['4', '5']);
    assert.deepStrictEqual(A.montarArvore(nos, r.arestas).filhos.get('1'), ['2', '3']);
    // reordenar: 4 vira o primeiro filho de 1
    r = A.moverNaArvore(nos, arestas, 4, 1, 2);
    assert.deepStrictEqual(A.montarArvore(nos, r.arestas).filhos.get('1'), ['4', '2', '3']);
    // sem "antesDe" vai para o fim
    r = A.moverNaArvore(nos, arestas, 2, 1, null);
    assert.deepStrictEqual(A.montarArvore(nos, r.arestas).filhos.get('1'), ['3', '4', '2']);
    assert.strictEqual(arestas.length, 4, 'o vetor original não é alterado');
});

teste('mover: recusa ciclo e auto-referência', () => {
    const nos = [1, 2, 3].map(no), arestas = [lig(1, 2), lig(2, 3)];
    assert.strictEqual(A.moverNaArvore(nos, arestas, 1, 3, null).ok, false);
    assert.strictEqual(A.moverNaArvore(nos, arestas, 2, 2, null).ok, false);
    assert.strictEqual(A.moverNaArvore(nos, arestas, 2, 3, null).ok, false);
});

teste('mover para "sem pai" torna o bloco uma raiz', () => {
    const nos = [1, 2].map(no);
    const r = A.moverNaArvore(nos, [lig(1, 2)], 2, null, null);
    assert.ok(r.ok);
    assert.deepStrictEqual(A.montarArvore(nos, r.arestas).raizes.sort(), ['1', '2']);
});

teste('mover preserva o estilo da conexão existente', () => {
    const nos = [1, 2, 3].map(no);
    const r = A.moverNaArvore(nos, [lig(1, 2, { label: 'Sim', sourceHandle: 'right' }), lig(1, 3)], 2, 3, null);
    const e = r.arestas.find(a => a.target === '2');
    assert.strictEqual(e.label, 'Sim');
    assert.strictEqual(e.source, '3');
});

// --------------------------------------------------------------------------- clonar ramo
teste('clonar ramo: novos IDs, conexões internas e dados preservados', () => {
    const nos = [1, 2, 3, 4].map(no);
    nos[1].data.colab = { id: 7, nome: 'Maria' };
    const arestas = [lig(1, 2), lig(2, 3), lig(1, 4)];
    let proximo = 10;
    const c = A.clonarRamo(nos, arestas, 2, () => proximo++);
    assert.deepStrictEqual(c.nos.map(n => n.id).sort(), ['10', '11']);
    assert.strictEqual(c.raizId, '10');
    assert.strictEqual(c.nos.find(n => n.id === '10').data.colab.nome, 'Maria');
    assert.strictEqual(c.nos.find(n => n.id === '10').data.stepId, '10');
    assert.deepStrictEqual(c.arestas.map(a => [a.source, a.target]), [['10', '11']]);
    c.nos[0].data.label = 'alterado';
    assert.strictEqual(nos[1].data.label, 'B2', 'cópia independente do original');
});

// --------------------------------------------------------------------------- utilidades
teste('descendentes, profundidade e irmãos', () => {
    const nos = [1, 2, 3, 4].map(no), arestas = [lig(1, 2), lig(2, 3), lig(1, 4)];
    const arv = A.montarArvore(nos, arestas);
    assert.deepStrictEqual([...A.descendentes(arv, '1')].sort(), ['2', '3', '4']);
    assert.strictEqual(A.profundidade(arv, '3'), 2);
    assert.deepStrictEqual(A.irmaos(arv, '2'), ['2', '4']);
    assert.deepStrictEqual(A.irmaos(arv, '1'), ['1']);
});

teste('desempenho: 600 blocos em menos de 200 ms', () => {
    const nos = [], arestas = [];
    for (let i = 1; i <= 600; i++) { nos.push(no(i)); if (i > 1) arestas.push(lig(Math.ceil((i - 1) / 4), i)); }
    const t0 = Date.now();
    const r = A.calcularLayout(nos, arestas, 'organograma', {});
    assert.ok(Date.now() - t0 < 200, 'demorou ' + (Date.now() - t0) + ' ms');
    assert.strictEqual(Object.keys(r.posicoes).length, 600);
});

teste('ordem manual reordena irmaos e raizes sem alterar as conexoes', () => {
    const nos = ['r', 'a', 'b', 'c'].map(id => ({ id, position: { x: 0, y: 0 }, data: {} }));
    nos[1].data.ordem = 3; nos[2].data.ordem = 1;   // b (1) vem antes de a (3); c sem ordem fica por ultimo
    const arestas = [['r', 'a'], ['r', 'b'], ['r', 'c']].map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    const arv = A.aplicarOrdemManual(A.montarArvore(nos, arestas), nos);
    assert.deepStrictEqual(arv.filhos.get('r'), ['b', 'a', 'c']);
    assert.deepStrictEqual(A.montarArvore(nos, arestas).filhos.get('r'), ['a', 'b', 'c']);
    const r = A.calcularLayout(nos, arestas, 'organograma', {}, { empilharFolhas: false });
    assert.ok(r.posicoes.b.x < r.posicoes.a.x && r.posicoes.a.x < r.posicoes.c.x);
    const p = A.calcularLayout(nos, arestas, 'organograma', {});   // empilhado: a ordem vira vertical
    assert.ok(p.posicoes.b.y < p.posicoes.a.y && p.posicoes.a.y < p.posicoes.c.y);
});

teste('organograma empilha folhas na vertical e economiza largura', () => {
    const mk = id => ({ id, position: { x: 0, y: 0 }, data: {} });
    const nos = ['r', 'g1', 'g2', 'a', 'b', 'c', 'd', 'e'].map(mk);
    const liga = [['r', 'g1'], ['r', 'g2'], ['g1', 'a'], ['g1', 'b'], ['g1', 'c'], ['g2', 'd'], ['g2', 'e']];
    const arestas = liga.map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    const compacto = A.calcularLayout(nos, arestas, 'organograma', {});
    const largo = A.calcularLayout(nos, arestas, 'organograma', {}, { empilharFolhas: false });
    const largura = r => Math.max(...Object.values(r.posicoes).map(p => p.x)) - Math.min(...Object.values(r.posicoes).map(p => p.x));
    assert.ok(largura(compacto) < largura(largo));
    const P = compacto.posicoes;
    // folhas de g1: mesma coluna (à direita do eixo do pai), uma abaixo da outra e abaixo do pai
    assert.strictEqual(P.a.x, P.b.x);
    assert.strictEqual(P.b.x, P.c.x);
    assert.ok(P.a.y > P.g1.y && P.b.y > P.a.y && P.c.y > P.b.y);
    assert.ok(P.a.x > P.g1.x);
    // conexões das folhas empilhadas saem de baixo do pai e entram pela esquerda
    const idDe = alvo => arestas.find(e => e.target === alvo).id;
    assert.deepStrictEqual(compacto.handles[idDe('a')], ['bottom', 'left']);
    assert.deepStrictEqual(compacto.handles[idDe('g1')], ['bottom', 'top']);
    // sem sobreposição entre os blocos
    const ids = Object.keys(P);
    const caixa = id => ({ x: P[id].x, y: P[id].y, w: 180, h: 64 });
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const u = caixa(ids[i]), v = caixa(ids[j]);
        assert.ok(u.x + u.w <= v.x || v.x + v.w <= u.x || u.y + u.h <= v.y || v.y + v.h <= u.y, ids[i] + ' x ' + ids[j]);
    }
});

teste('com um filho só, ou filhos que têm subordinados, não empilha', () => {
    const mk = id => ({ id, position: { x: 0, y: 0 }, data: {} });
    const nos = ['r', 'a', 'b', 'a1'].map(mk);
    const arestas = [['r', 'a'], ['r', 'b'], ['a', 'a1']].map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    const P = A.calcularLayout(nos, arestas, 'organograma', {}).posicoes;
    assert.strictEqual(P.a.y, P.b.y);   // irmãos lado a lado (a não é folha)
});

teste('estrutura "arvore" num ramo: todo o ramo vira lista recuada sob o bloco', () => {
    const mk = (id, estrutura) => ({ id, position: { x: 0, y: 0 }, data: estrutura ? { estrutura } : {} });
    const nos = [mk('r'), mk('g', 'arvore'), mk('h'), mk('g1'), mk('g2'), mk('g21'), mk('h1'), mk('h2')];
    const liga = [['r', 'g'], ['r', 'h'], ['g', 'g1'], ['g', 'g2'], ['g2', 'g21'], ['h', 'h1'], ['h', 'h2']];
    const arestas = liga.map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    const r = A.calcularLayout(nos, arestas, 'organograma', {}, { empilharFolhas: false });
    const P = r.posicoes;
    // ramo g: lista abaixo de g, recuada por nível (g1 e g2 no nível 1, g21 no nível 2)
    assert.ok(P.g1.y > P.g.y && P.g2.y > P.g1.y && P.g21.y > P.g2.y);
    assert.strictEqual(P.g1.x, P.g2.x);
    assert.ok(P.g21.x > P.g2.x);
    assert.deepStrictEqual(r.handles[arestas[3].id], ['bottom', 'left']);   // g -> g2
    assert.deepStrictEqual(r.handles[arestas[4].id], ['bottom', 'left']);   // g2 -> g21
    // ramo h (organograma): filhos lado a lado; a ligação r -> g segue o padrão
    assert.strictEqual(P.h1.y, P.h2.y);
    assert.deepStrictEqual(r.handles[arestas[0].id], ['bottom', 'top']);
    // g e h na mesma linha, sem sobreposição
    assert.strictEqual(P.g.y, P.h.y);
    assert.ok(P.g.x + 180 <= P.h.x || P.h.x + 180 <= P.g.x);
});

teste('a estrutura é herdada pelo ramo e o filho pode voltar ao organograma', () => {
    const mk = (id, estrutura) => ({ id, position: { x: 0, y: 0 }, data: estrutura ? { estrutura } : {} });
    const nos = [mk('r', 'arvore'), mk('a'), mk('b'), mk('a1')];
    const arestas = [['r', 'a'], ['r', 'b'], ['a', 'a1']].map(([s, t], i) => ({ id: 'e' + i, source: s, target: t }));
    const P = A.calcularLayout(nos, arestas, 'organograma', {}).posicoes;
    assert.ok(P.a.y < P.a1.y && P.a1.y < P.b.y);   // tudo em lista, em pré-ordem
    assert.ok(P.a1.x > P.a.x);
    // estrutura desconhecida é ignorada (segue o padrão do organograma)
    const nos2 = [mk('r', 'xyz'), mk('a'), mk('b')];
    const P2 = A.calcularLayout(nos2, [{ id: 'e0', source: 'r', target: 'a' }, { id: 'e1', source: 'r', target: 'b' }], 'organograma', {}, { empilharFolhas: false }).posicoes;
    assert.strictEqual(P2.a.y, P2.b.y);
});

console.log(process.exitCode ? 'COM FALHAS' : `TODOS OS ${total} TESTES OK`);

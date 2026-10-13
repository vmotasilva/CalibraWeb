/* Testes da geometria dos grupos (Node, sem dependências). Executar: node procedures/tests/js/grupos.test.js */
const assert = require('assert');
const path = require('path');
const G = require(path.join(__dirname, '..', '..', 'static', 'procedures', 'js', 'diagrama', 'grupos.js'));

let total = 0;
function teste(nome, fn) {
    try { fn(); total++; console.log('OK    ' + nome); }
    catch (e) { console.log('FALHA ' + nome + '\n      ' + e.message); process.exitCode = 1; }
}

const caixas = {
    a: { x: 200, y: 200, w: 160, h: 60 },
    b: { x: 400, y: 300, w: 160, h: 60 },
    c: { x: 700, y: 200, w: 160, h: 60 },
};

teste('caixa envolve os blocos com folga e faixa de título', () => {
    const c = G.caixaDoGrupo({ nos: ['a', 'b'] }, caixas, 0);
    assert.deepStrictEqual(c, { x: 178, y: 154, w: 404, h: 228 });
});

teste('blocos inexistentes são ignorados e grupo vazio não tem caixa', () => {
    assert.strictEqual(G.caixaDoGrupo({ nos: ['x'] }, caixas, 0), null);
    const c = G.caixaDoGrupo({ nos: ['a', 'x'] }, caixas, 0);
    assert.strictEqual(c.w, 160 + 44);
});

teste('caixa não passa de x/y = 2 (borda do canvas)', () => {
    const c = G.caixaDoGrupo({ nos: ['p'] }, { p: { x: 20, y: 20, w: 100, h: 50 } }, 0);
    assert.strictEqual(c.x, 2);
    assert.strictEqual(c.y, 2);
});

teste('grupo aninhado: o de fora ganha folga extra', () => {
    const grupos = [{ nos: ['a', 'b', 'c'] }, { nos: ['a', 'b'] }];
    assert.strictEqual(G.nivelDeAninhamento(grupos, 0, caixas), 0);
    assert.strictEqual(G.nivelDeAninhamento(grupos, 1, caixas), 1);
    const interno = G.caixaDoGrupo(grupos[1], caixas, 1);
    assert.strictEqual(interno.x, 200 - 32);
});

teste('grupos com os mesmos blocos: só o primeiro é o externo', () => {
    const grupos = [{ nos: ['a', 'b'] }, { nos: ['a', 'b'] }];
    assert.strictEqual(G.nivelDeAninhamento(grupos, 0, caixas), 0);
    assert.strictEqual(G.nivelDeAninhamento(grupos, 1, caixas), 1);
});

teste('sequência de apresentação: profundidade, pulando ocultos', () => {
    const arvore = { raizes: ['r'], filhos: new Map([['r', ['a', 'b']], ['a', ['a1']], ['b', []], ['a1', []]]) };
    assert.deepStrictEqual(G.sequenciaDeApresentacao(arvore), ['r', 'a', 'a1', 'b']);
    assert.deepStrictEqual(G.sequenciaDeApresentacao(arvore, new Set(['a1'])), ['r', 'a', 'b']);
});

console.log(process.exitCode ? 'COM FALHAS' : `TODOS OS ${total} TESTES OK`);

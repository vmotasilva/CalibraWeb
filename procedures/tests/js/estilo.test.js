/* Testes do resolvedor de estilos e temas (Node, sem dependências).
 * Executar: node procedures/tests/js/estilo.test.js   (também roda via test_diagram_qms.py)
 */
const assert = require('assert');
const path = require('path');
const base = path.join(__dirname, '..', '..', 'static', 'procedures', 'js', 'diagrama');
const E = require(path.join(base, 'estilo.js'));
const A = require(path.join(base, 'layout_arvore.js'));

let total = 0;
function teste(nome, fn) {
    try { fn(); total++; console.log('OK    ' + nome); }
    catch (e) { console.log('FALHA ' + nome + '\n      ' + e.message); process.exitCode = 1; }
}

const no = (id, data = {}, type = 'process') => ({ id: String(id), type, position: { x: 0, y: 0 }, data: Object.assign({ label: 'B' + id }, data) });
const lig = (a, b, extra = {}) => Object.assign({ id: `e-${a}-${b}`, source: String(a), target: String(b) }, extra);

teste('sem tema e sem estilo: nada é sobrescrito (visual de sempre)', () => {
    assert.deepStrictEqual(E.resolverEstiloNo(no(1), {}), {});
    assert.deepStrictEqual(E.resolverEstiloNo(no(1), { tema: E.PRESETS.padrao, profundidade: 2 }), {});
});

teste('estilo explícito do bloco', () => {
    const r = E.resolverEstiloNo(no(1, { style: { bold: true, fontSize: 16, color: '#112233', borderStyle: 'dashed' } }), {});
    assert.deepStrictEqual(r, { bold: true, fontSize: 16, color: '#112233', borderStyle: 'dashed' });
});

teste('bgColor legado vale como preenchimento explícito', () => {
    assert.strictEqual(E.resolverEstiloNo(no(1, { bgColor: '#ef4444' }), {}).fill, '#ef4444');
});

teste('tema por nível: raiz, 1º nível e folhas recebem estilos diferentes', () => {
    const tema = E.PRESETS.corporativo;
    const raiz = E.resolverEstiloNo(no(1), { tema, profundidade: 0 });
    const filho = E.resolverEstiloNo(no(2), { tema, profundidade: 1 });
    const folha = E.resolverEstiloNo(no(3), { tema, profundidade: 7 });   // além do último nível: repete o último
    assert.strictEqual(raiz.fill, '#1e3a8a'); assert.strictEqual(raiz.bold, true); assert.strictEqual(raiz.fontSize, 14);
    assert.strictEqual(filho.fill, '#2563eb');
    assert.strictEqual(folha.fill, '#ffffff'); assert.strictEqual(folha.fontSize, 11);
});

teste('o estilo do bloco vence o tema, propriedade por propriedade', () => {
    const tema = E.PRESETS.corporativo;
    const r = E.resolverEstiloNo(no(2, { style: { fill: '#00ff00' }, bgColor: '#ff0000' }), { tema, profundidade: 1 });
    assert.strictEqual(r.fill, '#00ff00', 'style.fill > bgColor > tema');
    assert.strictEqual(r.color, '#0f172a', 'fundo claro escolhido no bloco: texto escuro (contraste automático)');
    assert.strictEqual(r.bold, true, 'o resto vem do tema');
    const semBgColor = E.resolverEstiloNo(no(2, { bgColor: '#ff0000' }), { tema, profundidade: 1 });
    assert.strictEqual(semBgColor.fill, '#ff0000');
});

teste('contraste automático: texto claro em fundo escuro e vice-versa', () => {
    assert.strictEqual(E.corDeTextoParaFundo('#000000'), '#ffffff');
    assert.strictEqual(E.corDeTextoParaFundo('#1e3a8a'), '#ffffff');
    assert.strictEqual(E.corDeTextoParaFundo('#ffffff'), '#0f172a');
    assert.strictEqual(E.corDeTextoParaFundo('#fde68a'), '#0f172a');
    assert.strictEqual(E.resolverEstiloNo(no(1, { style: { fill: '#0f172a' } }), {}).color, '#ffffff');
    assert.strictEqual(E.resolverEstiloNo(no(1, { style: { fill: '#0f172a', color: '#ff0000' } }), {}).color, '#ff0000', 'cor de texto explícita vence');
    assert.strictEqual(E.resolverEstiloNo(no(1, { bgColor: '#0f172a' }), {}).color, undefined, 'bgColor legado não muda o texto (visual de sempre)');
});

teste('"sem preenchimento" remove o preenchimento do tema', () => {
    const r = E.resolverEstiloNo(no(2, { style: { noFill: true } }), { tema: E.PRESETS.corporativo, profundidade: 1 });
    assert.strictEqual(r.fill, undefined);
    assert.strictEqual(r.noFill, true);
});

teste('sem fundo o texto continua legível (tema com texto branco não some no fundo claro)', () => {
    const tema = E.PRESETS.vibrante;   // nível 1: texto branco; fundo do diagrama branco
    const semFill = E.resolverEstiloNo(no(2, { style: { noFill: true } }), { tema, profundidade: 1, ramo: 0 });
    assert.strictEqual(semFill.color, '#0f172a');
    assert.strictEqual(semFill.fill, undefined);
    // texto explícito é respeitado
    assert.strictEqual(E.resolverEstiloNo(no(2, { style: { noFill: true, color: '#ff0000' } }), { tema, profundidade: 1, ramo: 0 }).color, '#ff0000');
    // sobre um fundo de diagrama escuro, o texto fica claro
    const escuro = Object.assign({}, tema, { fundo: '#0f172a' });
    assert.strictEqual(E.resolverEstiloNo(no(2, { style: { noFill: true } }), { tema: escuro, profundidade: 1, ramo: 0 }).color, '#ffffff');
});

teste('formas sem caixa não herdam o preenchimento do tema e mantêm o texto legível', () => {
    const tema = E.PRESETS.vibrante;
    ['brackets', 'underline', 'plain'].forEach(forma => {
        const r = E.resolverEstiloNo(no(2, { shape: forma }), { tema, profundidade: 1, ramo: 0 });
        assert.strictEqual(r.fill, undefined, forma);
        assert.strictEqual(r.color, '#0f172a', forma);
        assert.strictEqual(r.borderColor, '#2563eb', forma + ': a borda do ramo continua');
    });
    const comFundo = E.resolverEstiloNo(no(2, { shape: 'plain', style: { fill: '#fde68a' } }), { tema, profundidade: 1, ramo: 0 });
    assert.strictEqual(comFundo.fill, '#fde68a');
    assert.strictEqual(comFundo.color, '#0f172a', 'contraste sobre o preenchimento escolhido');
});

teste('tema não pinta início, fim e decisão (cores semânticas)', () => {
    ['start', 'end', 'decision'].forEach(t => assert.deepStrictEqual(E.resolverEstiloNo(no(1, {}, t), { tema: E.PRESETS.corporativo, profundidade: 1 }), {}));
});

teste('multi-ramo: cada ramo ganha uma cor da paleta e o token "branch" é resolvido', () => {
    const tema = E.PRESETS.vibrante;
    const a = E.resolverEstiloNo(no(2), { tema, profundidade: 1, ramo: 0 });
    const b = E.resolverEstiloNo(no(3), { tema, profundidade: 1, ramo: 1 });
    const volta = E.resolverEstiloNo(no(4), { tema, profundidade: 1, ramo: 6 });   // dá a volta na paleta
    assert.strictEqual(a.fill, '#2563eb'); assert.strictEqual(b.fill, '#16a34a'); assert.strictEqual(volta.fill, '#2563eb');
    const folha = E.resolverEstiloNo(no(5), { tema, profundidade: 2, ramo: 2 });
    assert.strictEqual(folha.borderColor, '#ea580c');
    const semRamo = E.resolverEstiloNo(no(1), { tema, profundidade: 1, ramo: -1 });
    assert.strictEqual(semRamo.fill, undefined, 'sem ramo o token "branch" some');
    assert.ok(Object.values(a).every(v => v !== 'branch'));
});

teste('contexto dos blocos: profundidade e índice do ramo', () => {
    const nos = [1, 2, 3, 4, 5, 6].map(i => no(i));
    const arv = A.montarArvore(nos, [lig(1, 2), lig(1, 3), lig(2, 4), lig(3, 5), lig(5, 6)]);
    const c = E.contextoDosNos(arv);
    assert.deepStrictEqual(c['1'], { profundidade: 0, ramo: -1 });
    assert.deepStrictEqual(c['2'], { profundidade: 1, ramo: 0 });
    assert.deepStrictEqual(c['3'], { profundidade: 1, ramo: 1 });
    assert.deepStrictEqual(c['4'], { profundidade: 2, ramo: 0 });
    assert.deepStrictEqual(c['6'], { profundidade: 3, ramo: 1 });
});

teste('conexão: tema, multi-ramo e estilo próprio', () => {
    const tema = E.PRESETS.vibrante;
    assert.deepStrictEqual(E.resolverEstiloConexao(lig(1, 2), { tema, ramo: 1 }), { color: '#16a34a', width: 2 });
    assert.deepStrictEqual(E.resolverEstiloConexao(lig(1, 2), {}), {});
    const propria = E.resolverEstiloConexao(lig(1, 2, { style: { color: '#000000', dash: 'dashed', shape: 'curva' } }), { tema, ramo: 1 });
    assert.deepStrictEqual(propria, { color: '#000000', width: 2, dash: 'dashed', shape: 'curva' });
    assert.strictEqual(E.resolverEstiloConexao(lig(1, 2), { tema: E.PRESETS.corporativo }).color, '#1e3a8a');
});

teste('normalização: valores inválidos são descartados e números limitados', () => {
    const r = E.normalizarEstiloNo({ fontFamily: 'comic', fontSize: 500, bold: 'sim', align: 'justify', color: 'vermelho', fill: '#ABCDEF', borderStyle: 'wavy', borderWidth: -3 });
    assert.deepStrictEqual(r, { fontSize: 40, fill: '#abcdef', borderWidth: 0 });
    assert.deepStrictEqual(E.normalizarEstiloNo({ fontFamily: 'serif', fontSize: '', borderWidth: '' }), { fontFamily: 'serif' });
    assert.deepStrictEqual(E.normalizarEstiloConexao({ color: '#00FF00', width: 99, dash: 'zigzag', shape: 'curva' }), { color: '#00ff00', width: 8, shape: 'curva' });
});

teste('traçado: padrões de tracejado proporcionais à espessura', () => {
    assert.strictEqual(E.dashArray('solid', 2), null);
    assert.strictEqual(E.dashArray('dashed', 2), '8 5');
    assert.strictEqual(E.dashArray('dotted', 2), '2 4');
});

teste('todos os temas prontos são válidos (cores #RRGGBB, níveis e paleta)', () => {
    Object.entries(E.PRESETS).forEach(([id, t]) => {
        assert.ok(t.nome, id);
        (t.paleta || []).forEach(c => assert.match(c, /^#[0-9a-f]{6}$/i, id));
        (t.niveis || []).forEach(n => ['fill', 'texto', 'borda'].forEach(k => { if (n[k] && n[k] !== 'branch') assert.match(n[k], /^#[0-9a-f]{6}$/i, `${id}.${k}`); }));
        if (t.fundo) assert.match(t.fundo, /^#[0-9a-f]{6}$/i, id);
        if (JSON.stringify(t).includes('"branch"')) assert.ok(t.multiRamo && t.paleta.length > 0, `${id}: branch exige multiRamo e paleta`);
    });
});

console.log(process.exitCode ? 'COM FALHAS' : `TODOS OS ${total} TESTES OK`);

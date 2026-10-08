/* Testes do conteúdo dos blocos: marcadores, efetivo/vagas e comparação com o RH (Node, sem dependências).
 * Executar: node procedures/tests/js/conteudo.test.js   (também roda via test_diagram_qms.py)
 */
const assert = require('assert');
const path = require('path');
const base = path.join(__dirname, '..', '..', 'static', 'procedures', 'js', 'diagrama');
const C = require(path.join(base, 'conteudo.js'));
const A = require(path.join(base, 'layout_arvore.js'));

let total = 0;
function teste(nome, fn) {
    try { fn(); total++; console.log('OK    ' + nome); }
    catch (e) { console.log('FALHA ' + nome + '\n      ' + e.message); process.exitCode = 1; }
}

const no = (id, data = {}) => ({ id: String(id), type: 'process', position: { x: 0, y: 0 }, data: Object.assign({ label: 'B' + id }, data) });
const lig = (a, b) => ({ id: `e-${a}-${b}`, source: String(a), target: String(b) });
const colab = (id, extra = {}) => Object.assign({ id, nome: 'Pessoa ' + id, cargo: 'Analista', cargoRH: 'Analista', temFoto: true }, extra);

teste('catálogo: 30 marcadores únicos em 5 grupos', () => {
    assert.strictEqual(C.GRUPOS.length, 5);
    assert.strictEqual(C.ORDEM.length, 7 + 5 + 6 + 6 + 6);
    assert.strictEqual(new Set(C.ORDEM).size, C.ORDEM.length);
    assert.ok(C.marcadorValido('prio-1') && C.marcadorValido('band-verde') && C.marcadorValido('prog-100'));
    assert.ok(!C.marcadorValido('prio-9') && !C.marcadorValido('__proto__') && !C.marcadorValido('toString'));
    C.ORDEM.forEach(id => { const m = C.marcadorPorId(id); assert.match(m.cor, /^#[0-9a-f]{6}$/i); assert.ok(m.rotulo); });
});

teste('marcadores em uso seguem a ordem do catálogo e ignoram ids inválidos', () => {
    const nos = [no(1, { markers: ['estr-azul', 'prio-1', 'invalido'] }), no(2, { markers: ['prio-1', 'prog-50'] }), no(3)];
    assert.deepStrictEqual(C.marcadoresEmUso(nos), ['prio-1', 'prog-50', 'estr-azul']);
    assert.deepStrictEqual(C.marcadoresEmUso([no(1)]), []);
});

teste('efetivo: pessoas e vagas por subárvore (inclui o próprio bloco)', () => {
    const nos = [no(1, { colab: colab(1) }), no(2, { colab: colab(2) }), no(3, { vaga: true }), no(4, { colab: colab(4) }), no(5, { vaga: true }), no(6)];
    const arv = A.montarArvore(nos, [lig(1, 2), lig(1, 3), lig(2, 4), lig(2, 5), lig(3, 6)]);
    const e = C.contagemEfetivo(nos, arv);
    assert.deepStrictEqual(e['1'], { pessoas: 3, vagas: 2 });
    assert.deepStrictEqual(e['2'], { pessoas: 2, vagas: 1 });
    assert.deepStrictEqual(e['3'], { pessoas: 0, vagas: 1 });
    assert.deepStrictEqual(e['6'], { pessoas: 0, vagas: 0 });
});

teste('vaga vence: bloco marcado como vago com colaborador conta como vaga, não como pessoa', () => {
    const nos = [no(1, { vaga: true, colab: colab(1) })];
    const e = C.contagemEfetivo(nos, A.montarArvore(nos, []));
    assert.deepStrictEqual(e['1'], { pessoas: 0, vagas: 1 });
});

teste('resumo por ramo: linhas do 1º nível, total e taxa de ocupação', () => {
    const nos = [no(1, { colab: colab(1) }), no(2, { label: 'Produção' }), no(3, { label: 'Qualidade' }),
                 no(4, { colab: colab(4) }), no(5, { vaga: true }), no(6, { colab: colab(6) }), no(7, { colab: colab(7, { nome: 'Ana Souza' }) })];
    const arv = A.montarArvore(nos, [lig(1, 2), lig(1, 3), lig(2, 4), lig(2, 5), lig(3, 6), lig(3, 7)]);
    const r = C.resumoPorRamo(nos, arv);
    assert.deepStrictEqual(r.linhas.map(l => [l.nome, l.pessoas, l.vagas, l.total, l.ocupacao]), [['Produção', 1, 1, 2, 50], ['Qualidade', 2, 0, 2, 100]]);
    assert.deepStrictEqual(r.total, { pessoas: 4, vagas: 1, total: 5, ocupacao: 80 });
    assert.strictEqual(C.resumoPorRamo([no(1)], A.montarArvore([no(1)], [])).total.ocupacao, null, 'sem quadro: ocupação indefinida');
});

teste('resumo com várias raízes soma todas as árvores', () => {
    const nos = [no(1, { colab: colab(1) }), no(2, { vaga: true }), no(3, { colab: colab(3) }), no(4, { colab: colab(4) })];
    const r = C.resumoPorRamo(nos, A.montarArvore(nos, [lig(1, 2), lig(3, 4)]));
    assert.deepStrictEqual([r.total.pessoas, r.total.vagas], [3, 1]);
});

teste('RH: detecta nome alterado, função e colaborador removido', () => {
    const nos = [no(1, { colab: colab(10) }), no(2, { colab: colab(11) }), no(3, { colab: colab(12) }), no(4)];
    const atuais = {
        10: { existe: true, nome: 'Pessoa 10 Silva', cargo: 'Analista', tem_foto: true },
        11: { existe: true, nome: 'Pessoa 11', cargo: 'Coordenador', tem_foto: false },
    };
    const d = C.diferencasRH(nos, atuais);
    assert.strictEqual(d.length, 3);
    assert.deepStrictEqual(d.find(x => x.id === '1').nome, { de: 'Pessoa 10', para: 'Pessoa 10 Silva' });
    const d2 = d.find(x => x.id === '2');
    assert.deepStrictEqual(d2.cargo, { de: 'Analista', para: 'Coordenador' });
    assert.deepStrictEqual(d2.temFoto, { de: true, para: false });
    assert.strictEqual(d.find(x => x.id === '3').removido, true);
});

teste('RH: função personalizada no diagrama é preservada e apenas sinalizada', () => {
    const nos = [no(1, { colab: colab(10, { cargo: 'Gerente interino', cargoRH: 'Analista' }) })];
    const d = C.diferencasRH(nos, { 10: { existe: true, nome: 'Pessoa 10', cargo: 'Coordenador', tem_foto: true } });
    assert.strictEqual(d.length, 1);
    assert.strictEqual(d[0].cargo, undefined);
    assert.deepStrictEqual(d[0].cargoPersonalizado, { bloco: 'Gerente interino', rh: 'Coordenador' });
});

teste('RH: bloco sem diferenças não aparece; reencontrado volta a ser sinalizado', () => {
    const nos = [no(1, { colab: colab(10) }), no(2, { colab: colab(11, { removido: true }) })];
    const atuais = { 10: { existe: true, nome: 'Pessoa 10', cargo: 'Analista', tem_foto: true }, 11: { existe: true, nome: 'Pessoa 11', cargo: 'Analista', tem_foto: true } };
    const d = C.diferencasRH(nos, atuais);
    assert.deepStrictEqual(d.map(x => x.id), ['2']);
    assert.strictEqual(d[0].reencontrado, true);
    assert.strictEqual(C.diferencasRH([no(1, { colab: colab(11, { removido: true }) })], {}).length, 0, 'já sinalizado como removido');
});

teste('links: validação e limite', () => {
    assert.ok(C.urlValida('https://exemplo.com/a?b=1') && C.urlValida('http://x.y'));
    assert.ok(!C.urlValida('javascript:alert(1)') && !C.urlValida('ftp://x') && !C.urlValida('https://a b') && !C.urlValida(null));
    const bons = [{ tipo: 'url', url: 'https://x.com', rotulo: 'Site' }, { tipo: 'procedimento', id: 7, rotulo: 'POP-1' }, { tipo: 'diagrama', id: 'abc-123', rotulo: '#002' }];
    const ruins = [{ tipo: 'url', url: 'javascript:1' }, { tipo: 'procedimento', id: 'x' }, { tipo: 'outro' }, null, 'texto'];
    assert.strictEqual(C.normalizarLinks([...bons, ...ruins]).length, 3);
    assert.strictEqual(C.normalizarLinks(new Array(20).fill(bons[0])).length, C.MAX_LINKS);
    assert.strictEqual(C.normalizarLinks([{ tipo: 'url', url: 'https://x.com', rotulo: 'a'.repeat(500) }])[0].rotulo.length, 120);
    assert.deepStrictEqual(C.normalizarLinks(undefined), []);
});

console.log(process.exitCode ? 'COM FALHAS' : `TODOS OS ${total} TESTES OK`);

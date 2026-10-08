/* Editor de Diagramas (DOC.071) - módulo "aparencia"
 * Ligação do estilo (estilo.js) com o DOM: formatação do bloco (texto, borda, preenchimento, formas), linha até o
 * bloco (cor, espessura, traçado, formato, ramo inteiro), copiar/colar formato e TEMAS do diagrama
 * (temas prontos, personalização, catálogo de temas salvos).
 */

// ------------------------------------------------------------------ aplicação visual no canvas
function contextoEstiloDoNo(node) {
    return Object.assign({ tema: topologia.tema || null }, (contextoEstiloCache || {})[String(node.id)] || {});
}

function estiloEfetivoDoNo(node) {
    return DiagramaEstilo.resolverEstiloNo(node, contextoEstiloDoNo(node));
}

function arestaDeEntrada(node) {
    return topologia.edges.find(e => String(e.target) === String(node.id) && (e.kind || 'hierarquia') === 'hierarquia') || null;
}

function estiloEfetivoDaConexao(edge) {
    const ctx = { tema: topologia.tema || null, ramo: ((contextoEstiloCache || {})[String(edge.target)] || {}).ramo };
    return DiagramaEstilo.resolverEstiloConexao(edge, ctx);
}

// Aplica ao elemento do bloco o estilo resolvido (explícito > tema > padrão). Sem estilo, não mexe em nada.
function aplicarEstiloVisualAoNo(nodeEl, node) {
    const st = estiloEfetivoDoNo(node);
    const forma = node.data?.shape;
    const especial = DiagramaEstilo.FORMAS_EXTRAS.includes(forma);

    if (especial) {
        nodeEl.classList.add(`node-shape-${forma}`);
        if (forma === 'brackets') {
            ['tl', 'tr', 'bl', 'br'].forEach(canto => nodeEl.insertAdjacentHTML('beforeend', `<i class="colchete ${canto}"></i>`));
        }
    }
    if (Object.keys(st).length === 0) return;

    const caixa = nodeEl.querySelector('.diamond-inner') || nodeEl; // a decisão desenha a caixa no losango
    if (st.noFill) caixa.style.setProperty('background-color', 'transparent', 'important');
    else if (st.fill) caixa.style.setProperty('background-color', st.fill, 'important');

    if (especial) {
        // formas sem caixa desenham a linha por CSS (variáveis)
        if (st.borderColor) nodeEl.style.setProperty('--borda-no', st.borderColor);
        if (st.borderWidth !== undefined) nodeEl.style.setProperty('--borda-larg', `${st.borderWidth}px`);
        if (st.borderStyle) nodeEl.style.setProperty('--borda-estilo', st.borderStyle === 'none' ? 'hidden' : st.borderStyle);
    } else {
        if (st.borderStyle) caixa.style.borderStyle = st.borderStyle;
        if (st.borderColor) caixa.style.borderColor = st.borderColor;
        if (st.borderWidth !== undefined) caixa.style.borderWidth = `${st.borderWidth}px`;
    }

    if (st.color) nodeEl.style.color = st.color;
    // "important": utilitários do Bootstrap (fw-semibold, small...) também usam !important e venceriam o estilo inline
    const definir = (el, propriedade, valor) => el.style.setProperty(propriedade, valor, 'important');
    nodeEl.querySelectorAll('.rotulo-bloco').forEach(el => {
        if (st.color) definir(el, 'color', st.color);
        if (st.fontFamily) definir(el, 'font-family', DiagramaEstilo.CSS_FAMILIAS[st.fontFamily]);
        if (st.fontSize) definir(el, 'font-size', `${st.fontSize}px`);
        if (st.bold !== undefined) definir(el, 'font-weight', st.bold ? '700' : '400');
        if (st.italic !== undefined) definir(el, 'font-style', st.italic ? 'italic' : 'normal');
        if (st.strike) definir(el, 'text-decoration', 'line-through');
        if (st.align) definir(el, 'text-align', st.align);
    });
}

// Seta (marcador SVG) na cor da linha, criada sob demanda. Tamanho em unidades fixas (não escala com a espessura
// como o marcador padrão); linhas muito grossas ganham uma seta um pouco maior.
function marcadorParaCor(svg, cor, largura) {
    const w = largura || 2.2;
    const escala = w <= 2.2 ? 2.2 : 2.2 + (w - 2.2) * 0.5;
    const id = `seta-${cor.replace('#', '')}-${String(escala).replace('.', '_')}`;
    const defs = svg.querySelector('defs');
    if (defs && !svg.querySelector(`#${id}`)) {
        const largMarcador = 10 * escala, altMarcador = 7 * escala;
        defs.insertAdjacentHTML('beforeend',
            `<marker id="${id}" markerUnits="userSpaceOnUse" markerWidth="${largMarcador}" markerHeight="${altMarcador}" refX="${9 * escala}" refY="${altMarcador / 2}" orient="auto">
                <polygon points="0 0, ${largMarcador} ${altMarcador / 2}, 0 ${altMarcador}" fill="${cor}"/></marker>`);
    }
    return `url(#${id})`;
}

function aplicarFundoDoTema() {
    const viewport = document.getElementById('canvasViewport');
    if (viewport) viewport.style.backgroundColor = topologia.tema?.fundo || '';
}

// ------------------------------------------------------------------ painel "Aparência" do bloco
function noPrincipalDaSelecao() {
    return topologia.nodes.find(n => n.id === selectedNodeId) || null;
}

function definirValor(id, valor) {
    const el = document.getElementById(id);
    if (el) el.value = valor === undefined || valor === null ? '' : valor;
}

function marcarBotao(id, ativo) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', !!ativo);
}

function atualizarPainelAparencia(node) {
    const vazio = document.getElementById('aparenciaVazio');
    const controles = document.getElementById('aparenciaControles');
    if (!vazio || !controles) return;
    vazio.classList.toggle('d-none', !!node);
    controles.classList.toggle('d-none', !node);
    if (!node) return;

    const explicito = node.data?.style || {};
    const efetivo = estiloEfetivoDoNo(node);
    definirValor('apFonte', explicito.fontFamily || '');
    definirValor('apTamanho', explicito.fontSize);
    marcarBotao('apNegrito', efetivo.bold !== undefined ? efetivo.bold : true);
    marcarBotao('apItalico', efetivo.italic);
    marcarBotao('apTachado', efetivo.strike);
    ['left', 'center', 'right'].forEach(a => marcarBotao(`apAlinhar-${a}`, (efetivo.align || 'center') === a));
    definirValor('apCorTexto', efetivo.color || '#0f172a');
    document.getElementById('apSemFundo').checked = !!explicito.noFill;
    definirValor('apCorFundo', efetivo.fill || '#ffffff');
    definirValor('apBordaEstilo', explicito.borderStyle || '');
    definirValor('apBordaLargura', explicito.borderWidth);
    definirValor('apBordaCor', efetivo.borderColor || '#94a3b8');

    const entrada = arestaDeEntrada(node);
    const linha = entrada ? Object.assign({}, estiloEfetivoDaConexao(entrada)) : {};
    const propria = entrada?.style || {};
    definirValor('apLinhaCor', linha.color || '#475569');
    definirValor('apLinhaLargura', propria.width);
    definirValor('apLinhaTracado', propria.dash || '');
    definirValor('apLinhaFormato', propria.shape || '');
    const forma = node.data?.shape || '';
    document.querySelectorAll('[data-forma]').forEach(b => b.classList.toggle('active', b.dataset.forma === forma));
}

function reaplicarAparencia() {
    if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

// Altera uma propriedade do estilo de todos os blocos selecionados (valor vazio/nulo = volta ao padrão)
function aplicarAparencia(prop, valor) {
    if (IS_APPROVED || selectedNodeIds.size === 0) return;
    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (!node) return;
        if (!node.data) node.data = {};
        const atual = Object.assign({}, node.data.style || {});
        if (valor === null || valor === undefined || valor === '' || valor === false) delete atual[prop];
        else atual[prop] = valor;
        const limpo = DiagramaEstilo.normalizarEstiloNo(atual);
        if (Object.keys(limpo).length) node.data.style = limpo; else delete node.data.style;
    });
    reaplicarAparencia();
}

// Negrito, itálico e tachado alternam em relação ao valor efetivo (o negrito é o padrão dos blocos)
function alternarAparencia(prop) {
    if (IS_APPROVED || selectedNodeIds.size === 0) return;
    const principal = noPrincipalDaSelecao();
    const efetivo = principal ? estiloEfetivoDoNo(principal) : {};
    const atual = efetivo[prop] !== undefined ? efetivo[prop] : (prop === 'bold');
    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (!node) return;
        if (!node.data) node.data = {};
        node.data.style = DiagramaEstilo.normalizarEstiloNo(Object.assign({}, node.data.style || {}, { [prop]: !atual }));
    });
    reaplicarAparencia();
}

function copiarFormato() {
    const node = noPrincipalDaSelecao();
    if (!node) return;
    formatoCopiado = JSON.parse(JSON.stringify({ style: node.data?.style || {}, shape: node.data?.shape || null, bgColor: node.data?.bgColor || null }));
    mostrarAvisoNoEditor('Formato copiado. Selecione outro bloco e use "Colar formato".');
}

function colarFormato() {
    if (IS_APPROVED || !formatoCopiado || selectedNodeIds.size === 0) {
        if (!formatoCopiado) mostrarAvisoNoEditor('Nada copiado. Use "Copiar formato" em um bloco.');
        return;
    }
    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (!node) return;
        if (!node.data) node.data = {};
        if (Object.keys(formatoCopiado.style).length) node.data.style = Object.assign({}, formatoCopiado.style); else delete node.data.style;
        if (formatoCopiado.bgColor) node.data.bgColor = formatoCopiado.bgColor; else delete node.data.bgColor;
        if (node.type !== 'decision') {
            if (formatoCopiado.shape && formatoCopiado.shape !== 'decision') node.data.shape = formatoCopiado.shape; else delete node.data.shape;
        }
    });
    reaplicarAparencia();
}

function limparFormatacao() {
    if (IS_APPROVED || selectedNodeIds.size === 0) return;
    selectedNodeIds.forEach(id => {
        const node = topologia.nodes.find(n => n.id === id);
        if (!node || !node.data) return;
        delete node.data.style;
        delete node.data.bgColor;
        if (node.type !== 'decision') delete node.data.shape;
    });
    reaplicarAparencia();
}

// ------------------------------------------------------------------ linha até o bloco (e ramo inteiro)
function aplicarAparenciaConexao(prop, valor) {
    if (IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node) return;
    const entrada = arestaDeEntrada(node);
    const alvos = new Set();
    if (entrada) alvos.add(entrada);
    if (document.getElementById('apLinhaRamo')?.checked) {
        const abaixo = DiagramaArvore.descendentes(arvoreAtual(), String(node.id));
        topologia.edges.forEach(e => {
            if ((e.kind || 'hierarquia') === 'hierarquia' && abaixo.has(String(e.target))) alvos.add(e);
        });
    }
    if (alvos.size === 0) {
        mostrarAvisoNoEditor('Este bloco não tem linha de entrada (é a raiz). Marque "todo o ramo" para estilizar as linhas abaixo dele.');
        return;
    }
    alvos.forEach(edge => {
        if (prop === null) { delete edge.style; return; }
        const atual = Object.assign({}, edge.style || {});
        if (valor === null || valor === undefined || valor === '') delete atual[prop]; else atual[prop] = valor;
        const limpo = DiagramaEstilo.normalizarEstiloConexao(atual);
        if (Object.keys(limpo).length) edge.style = limpo; else delete edge.style;
    });
    reaplicarAparencia();
}

// ------------------------------------------------------------------ temas
function lerJsonDaPagina(id, padrao) {
    try { return JSON.parse(document.getElementById(id).textContent) || padrao; } catch (e) { return padrao; }
}

let temasSalvos = lerJsonDaPagina('temasSalvosData', []);

function corDeAmostra(def, token, i) {
    if (token === 'branch') return (def.paleta || [])[i % Math.max(1, (def.paleta || []).length)] || '#94a3b8';
    return token || '#ffffff';
}

function htmlAmostraDoTema(def) {
    const niveis = (def.niveis || []).slice(0, 4);
    if (niveis.length === 0) return '<span class="tema-amostra" style="background:#fff;border:1px solid #cbd5e1"></span>';
    return niveis.map((n, i) => `<span class="tema-amostra" style="background:${escapeHtml(corDeAmostra(def, n.fill, i))};border:2px solid ${escapeHtml(corDeAmostra(def, n.borda, i))}"></span>`).join('')
        + (def.multiRamo ? (def.paleta || []).slice(0, 6).map(c => `<span class="tema-ponto" style="background:${escapeHtml(c)}"></span>`).join('') : '');
}

function nomeDoTemaAtual() {
    return topologia.tema ? (topologia.tema.nome || 'Personalizado') : DiagramaEstilo.PRESETS.padrao.nome;
}

function renderizarModalTema() {
    const prontos = document.getElementById('listaTemasProntos');
    const salvos = document.getElementById('listaTemasSalvos');
    if (!prontos || !salvos) return;
    const ativo = nomeDoTemaAtual();

    prontos.innerHTML = '';
    Object.entries(DiagramaEstilo.PRESETS).forEach(([id, def]) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = `list-group-item list-group-item-action d-flex align-items-center gap-2 ${def.nome === ativo ? 'active' : ''}`;
        item.innerHTML = `<span class="d-flex gap-1 align-items-center">${htmlAmostraDoTema(def)}</span><span class="fw-semibold small">${escapeHtml(def.nome)}</span>`;
        item.onclick = () => aplicarTema(id === 'padrao' ? null : def);
        prontos.appendChild(item);
    });

    salvos.innerHTML = '';
    if (temasSalvos.length === 0) {
        salvos.innerHTML = '<div class="list-group-item small text-muted">Nenhum tema salvo ainda. Personalize um tema e use "Salvar no catálogo".</div>';
    }
    temasSalvos.forEach(t => {
        const linha = document.createElement('div');
        linha.className = `list-group-item d-flex align-items-center gap-2 ${t.nome === ativo ? 'active' : ''}`;
        linha.innerHTML = `<button type="button" class="btn btn-link text-start p-0 flex-grow-1 text-decoration-none d-flex align-items-center gap-2" style="color:inherit">
                <span class="d-flex gap-1 align-items-center">${htmlAmostraDoTema(t.definicao)}</span>
                <span class="small"><span class="fw-semibold">${escapeHtml(t.nome)}</span>${t.criado_por_nome ? ` <span class="opacity-75">- ${escapeHtml(t.criado_por_nome)}</span>` : ''}</span>
            </button>
            ${t.pode_excluir ? `<button type="button" class="btn btn-sm btn-outline-danger" title="Excluir tema do catálogo"><i class="bi bi-trash"></i></button>` : ''}`;
        linha.querySelector('button').onclick = () => aplicarTema(t.definicao);
        const excluir = linha.querySelectorAll('button')[1];
        if (excluir) excluir.onclick = () => excluirTemaSalvo(t.id, t.nome);
        salvos.appendChild(linha);
    });

    // personalização
    const tema = topologia.tema;
    definirValor('temaFundo', tema?.fundo || '#ffffff');
    document.getElementById('temaSemFundo').checked = !tema?.fundo;
    document.getElementById('temaMultiRamo').checked = !!tema?.multiRamo;
    const paleta = document.getElementById('temaPaleta');
    paleta.innerHTML = '';
    paleta.classList.toggle('d-none', !tema?.multiRamo);
    (tema?.paleta || []).forEach((cor, i) => {
        paleta.insertAdjacentHTML('beforeend', `<input type="color" class="form-control form-control-color p-0" value="${escapeHtml(cor)}" title="Cor do ramo ${i + 1}" onchange="editarCorDaPaleta(${i}, this.value)">`);
    });
    document.getElementById('temaAtualNome').textContent = ativo;
}

function abrirModalTema() {
    if (IS_APPROVED) return;
    renderizarModalTema();
    new bootstrap.Modal(document.getElementById('modalTema')).show();
}

function reaplicarTema() {
    aplicarFundoDoTema();
    if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
    atualizarSelecoesVisuais();
    renderizarModalTema();
    dispararAutoSave();
}

function aplicarTema(definicao) {
    if (IS_APPROVED) return;
    topologia.tema = definicao ? JSON.parse(JSON.stringify(definicao)) : null;
    if (!topologia.tema) delete topologia.tema;
    reaplicarTema();
}

function temaParaEdicao() {
    if (!topologia.tema) topologia.tema = { nome: 'Personalizado', fundo: null, multiRamo: false, paleta: [], linha: {}, niveis: [] };
    if (topologia.tema.nome && DiagramaEstilo.PRESETS && Object.values(DiagramaEstilo.PRESETS).some(p => p.nome === topologia.tema.nome)) {
        topologia.tema.nome = `${topologia.tema.nome} (personalizado)`;
    }
    return topologia.tema;
}

function definirFundoDoTema(cor) {
    if (IS_APPROVED) return;
    const tema = temaParaEdicao();
    tema.fundo = cor || null;
    reaplicarTema();
}

function alternarMultiRamo(ligado) {
    if (IS_APPROVED) return;
    const tema = temaParaEdicao();
    tema.multiRamo = !!ligado;
    if (ligado && (!tema.paleta || tema.paleta.length === 0)) tema.paleta = DiagramaEstilo.PRESETS.vibrante.paleta.slice();
    reaplicarTema();
}

function editarCorDaPaleta(indice, cor) {
    if (IS_APPROVED || !topologia.tema?.paleta) return;
    topologia.tema.paleta[indice] = cor;
    reaplicarTema();
}

async function salvarTemaNoCatalogo() {
    if (!topologia.tema) {
        alert('Escolha ou personalize um tema antes de salvar no catálogo.');
        return;
    }
    const nome = prompt('Nome do tema no catálogo:', topologia.tema.nome || 'Meu tema');
    if (nome === null || !nome.trim()) return;
    try {
        const resp = await fetch('/procedures/api/diagramas/temas/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
            body: JSON.stringify({ nome: nome.trim(), definicao: topologia.tema })
        });
        const dados = await resp.json();
        if (!resp.ok) { alert(dados.error || 'Não foi possível salvar o tema.'); return; }
        temasSalvos = dados.results;
        topologia.tema.nome = nome.trim();
        renderizarModalTema();
        mostrarAvisoNoEditor(`Tema "${nome.trim()}" salvo no catálogo.`);
        dispararAutoSave();
    } catch (e) {
        alert('Erro de conexão ao salvar o tema.');
    }
}

async function excluirTemaSalvo(id, nome) {
    if (!confirm(`Excluir o tema "${nome}" do catálogo? Os diagramas que já o usam não mudam.`)) return;
    try {
        const resp = await fetch(`/procedures/api/diagramas/temas/${id}/`, { method: 'DELETE', headers: { 'X-CSRFToken': CSRF_TOKEN } });
        const dados = await resp.json();
        if (!resp.ok) { alert(dados.error || 'Não foi possível excluir o tema.'); return; }
        temasSalvos = dados.results;
        renderizarModalTema();
    } catch (e) {
        alert('Erro de conexão ao excluir o tema.');
    }
}

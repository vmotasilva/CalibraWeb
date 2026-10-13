/* Editor de Diagramas (DOC.071) - módulo "raias_layout"
 * Raias (swimlanes) e layout automático por raias.
 * Script clássico: compartilha o escopo global com os demais módulos (ver ordem em diagrama_editor.html).
 */

// =========================================================================
// AUTOMAÇÕES DE POSICIONAMENTO, CENTRALIZAÇÃO E ALINHAMENTO POR RAIAS
// =========================================================================
// Auto-layout nas raias: o Y vem da raia de cada bloco; o X segue a hierarquia (subordinados distribuídos
// lado a lado e centralizados sob o bloco ao qual estão ligados, sem sobreposição).
const ALTURA_LINHA_NA_RAIA = 130;   // distância vertical entre blocos pai e filho que ficam na mesma raia

function posicionarAutomaticoPorRaias(centralizar = true) {
    const lanes = obterListaRaiasOrdenada();
    const nodeWidth = 190;
    const gap = 60;
    const passo = nodeWidth + gap;
    const viewport = document.getElementById('canvasViewport');
    const canvasTargetWidth = viewport ? (viewport.clientWidth / zoomLevel) : 1150;

    const noLane = n => n.data?.lane || 'Geral';
    const posicionaveis = topologia.nodes.filter(n => lanes.includes(noLane(n)));
    if (posicionaveis.length === 0) return;

    const porId = new Map(posicionaveis.map(n => [String(n.id), n]));
    const arvore = DiagramaArvore.aplicarOrdemManual(DiagramaArvore.montarArvore(posicionaveis, topologia.edges), posicionaveis);
    const ordemNumerica = n => {
        const v = parseInt(n.data?.stepId || n.id, 10);
        return isNaN(v) ? Infinity : v;
    };
    // raízes: ordem manual (já aplicada) e, sem ela, a sequência de etapas
    const temOrdem = id => typeof porId.get(id).data?.ordem === 'number';
    const raizes = arvore.raizes.slice().sort((x, y) => (temOrdem(x) || temOrdem(y)) ? 0 : ordemNumerica(porId.get(x)) - ordemNumerica(porId.get(y)));

    // Estrutura do ramo (data.estrutura): herdada do pai; "arvore" = o ramo vira uma lista recuada sob o bloco
    const estrutura = new Map();
    const resolverEstrutura = (id, herdada) => {
        const propria = porId.get(id)?.data?.estrutura;
        const efetiva = DiagramaArvore.ESTRUTURAS.includes(propria) ? propria : herdada;
        estrutura.set(id, efetiva);
        (arvore.filhos.get(id) || []).forEach(f => resolverEstrutura(f, efetiva));
    };
    raizes.forEach(r => resolverEstrutura(r, 'organograma'));

    // X em "colunas": folha = próxima coluna livre; pai = centro dos filhos
    const colunas = new Map();
    const recuoPx = new Map();            // blocos de uma lista recuada: deslocamento em px dentro da coluna
    const RECUO_NA_RAIA = 40;
    let proxima = 0;
    const visitar = id => {
        const filhos = arvore.filhos.get(id) || [];
        if (estrutura.get(id) === 'arvore' && filhos.length > 0) {
            // cabeça de lista: ocupa uma coluna; os descendentes ficam na mesma coluna, recuados por nível
            colunas.set(id, proxima);
            let maiorNivel = 0;
            const descer = (pid, nivel) => (arvore.filhos.get(pid) || []).forEach(f => {
                colunas.set(f, proxima);
                recuoPx.set(f, nivel * RECUO_NA_RAIA);
                maiorNivel = Math.max(maiorNivel, nivel);
                descer(f, nivel + 1);
            });
            descer(id, 1);
            proxima += 1 + Math.floor((maiorNivel * RECUO_NA_RAIA + 20) / passo);   // largura consumida pelo recuo
            return;
        }
        if (filhos.length === 0) {
            colunas.set(id, proxima++);
            return;
        }
        filhos.forEach(visitar);
        colunas.set(id, (colunas.get(filhos[0]) + colunas.get(filhos[filhos.length - 1])) / 2);
    };
    raizes.forEach(visitar);

    const larguraTotal = Math.max(0, (proxima - 1)) * passo + nodeWidth;
    const targetW = Math.max(canvasTargetWidth, larguraTotal + 160);
    const startX = centralizar ? Math.max(80, Math.round((targetW - larguraTotal) / 2)) : 80;

    const xDoBloco = id => Math.round(startX + colunas.get(id) * passo + (recuoPx.get(id) || 0));

    // Linhas dentro da raia: um bloco ligado a um pai da MESMA raia fica sempre abaixo dele; blocos da mesma raia que
    // cairiam um sobre o outro (mesma coluna) também descem uma linha. A faixa da raia cresce conforme as linhas.
    const ordemPre = [];
    const preOrdem = id => { ordemPre.push(id); (arvore.filhos.get(id) || []).forEach(preOrdem); };
    raizes.forEach(preOrdem);
    // Níveis de altura dentro da raia (data.nivelRaia, 1 = topo): coordenadas predefinidas de Y, de 65 px em 65 px, para
    // deixar um bloco um pouco acima ou abaixo dos vizinhos. Os níveis escolhidos têm prioridade e reservam o lugar.
    const ALTURA_NIVEL = ALTURA_NIVEL_NA_RAIA;
    const yRelativo = new Map();            // bloco -> deslocamento (px) a partir do topo útil da raia
    const ocupacao = {};                    // raia -> [{ x, y }] (lugares já usados)
    const nivelManual = n => (Number.isInteger(n.data?.nivelRaia) && n.data.nivelRaia >= 1 ? n.data.nivelRaia : null);
    const ocupado = (lista, x, y) => lista.some(o => Math.abs(o.x - x) < nodeWidth + 30 && Math.abs(o.y - y) < ALTURA_LINHA_NA_RAIA - 30);
    ordemPre.forEach(id => {
        const n = porId.get(id);
        const nivel = nivelManual(n);
        if (nivel === null || noEntreRaias(n, lanes)) return;
        const y = (nivel - 1) * ALTURA_NIVEL;
        yRelativo.set(id, y);
        (ocupacao[noLane(n)] = ocupacao[noLane(n)] || []).push({ x: xDoBloco(id), y });
    });
    // demais blocos: abaixo do pai da MESMA raia e sem cair sobre outro bloco (descem uma linha)
    ordemPre.forEach(id => {
        if (yRelativo.has(id)) return;
        const n = porId.get(id);
        const lane = noLane(n);
        if (noEntreRaias(n, lanes)) { yRelativo.set(id, 0); return; }   // fica sobre a divisa das raias
        const paiId = arvore.pai.get(id);
        const pai = paiId !== undefined ? porId.get(paiId) : null;
        let y = pai && noLane(pai) === lane && !noEntreRaias(pai, lanes) ? (yRelativo.get(paiId) || 0) + ALTURA_LINHA_NA_RAIA : 0;
        const x = xDoBloco(id);
        const lista = ocupacao[lane] = ocupacao[lane] || [];
        while (ocupado(lista, x, y)) y += ALTURA_LINHA_NA_RAIA;
        lista.push({ x, y });
        yRelativo.set(id, y);
    });

    // topo e Y de cada raia (a mesma altura automática das faixas desenhadas: calcularFaixasRaias)
    const ocultos = typeof nosOcultos === 'function' ? nosOcultos() : new Set();
    const fundoRelativo = {};       // raia -> maior (deslocamento + altura do bloco) entre os blocos visíveis
    posicionaveis.forEach(n => {
        const id = String(n.id);
        if (noEntreRaias(n, lanes) || ocultos.has(id)) return;
        const lane = noLane(n);
        fundoRelativo[lane] = Math.max(fundoRelativo[lane] || 0, (yRelativo.get(id) || 0) + alturaDoBlocoNoCanvas(n));
    });
    const yDaRaia = {};
    const topoDaRaia = {};
    let acumulado = 40;
    lanes.forEach(lane => {
        topoDaRaia[lane] = acumulado;
        yDaRaia[lane] = acumulado + PADDING_RAIA;
        acumulado += raiaRecolhida(lane)
            ? ALTURA_RAIA_RECOLHIDA
            : Math.max(ALTURA_MINIMA_RAIA, PADDING_RAIA + (fundoRelativo[lane] || 0) + PADDING_RAIA);
    });

    posicionaveis.forEach(n => {
        const id = String(n.id);
        n.position.x = xDoBloco(id);
        // bloco entre raias: sobre a divisa com a raia de baixo
        n.position.y = noEntreRaias(n, lanes)
            ? topoDaRaia[n.data.laneAbaixo] - alturaDoBlocoNoCanvas(n) / 2
            : yDaRaia[noLane(n)] + (yRelativo.get(id) || 0);
    });
}

function reorganizarAutoLayout() {
    if (arvoreAtiva()) aplicarLayoutArvore();
    else {
        posicionarAutomaticoPorRaias(true);
        renderizarCanvas();
    }
    recentralizarCanvas();
    dispararAutoSave();
}

function alinharNosPorRaias() {
    // Se houver multi-seleção, alinha os blocos selecionados em relação ao primeiro selecionado
    if (selectedNodeIds.size > 1) {
        const arrIds = Array.from(selectedNodeIds);
        const refNode = topologia.nodes.find(n => n.id === arrIds[0]);
        if (refNode) {
            const alignY = refNode.position.y;
            arrIds.forEach(id => {
                const n = topologia.nodes.find(node => node.id === id);
                if (n) {
                    n.position.y = alignY; // Mantém o X (configuração) e alinha o Y
                }
            });
        }
    } else {
        // Comportamento original de alinhar todos por raia
        const lanes = obterListaRaiasOrdenada();
        
        // Calcula Y bases dinamicamente para preservar as alturas das raias
        let currentY = 40;
        const laneYBase = {};
        lanes.forEach(lane => {
            laneYBase[lane] = currentY + PADDING_RAIA;

            // todos os blocos da raia ficam numa só linha: altura = bloco mais alto + folgas
            const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane && !noEntreRaias(n, lanes));
            const maisAlto = nodesInLane.length ? Math.max(...nodesInLane.map(alturaDoBlocoNoCanvas)) : 0;
            currentY += raiaRecolhida(lane) ? ALTURA_RAIA_RECOLHIDA : Math.max(ALTURA_MINIMA_RAIA, maisAlto + 2 * PADDING_RAIA);
        });

        lanes.forEach(lane => {
            const yBase = laneYBase[lane];
            const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane && !noEntreRaias(n, lanes));
            if (nodesInLane.length === 0) return;

            nodesInLane.forEach(n => {
                n.position.y = yBase;
            });

            nodesInLane.sort((a, b) => a.position.x - b.position.x);
            const startX = Math.min(...nodesInLane.map(n => n.position.x));
            const gap = 60;
            const width = 190;
            nodesInLane.forEach((n, i) => {
                n.position.x = startX + i * (width + gap);
            });
        });
    }

    renderizarCanvas();
    dispararAutoSave();
}

function centralizarEixoXDaTela() {
    if (topologia.nodes.length === 0) return;
    const viewport = document.getElementById('canvasViewport');
    const viewCenterX = viewport.scrollLeft / zoomLevel + (viewport.clientWidth / 2) / zoomLevel;
    
    // Centraliza baseado no "Ponto de Partida" (Nó Raiz / Primeiro Nó) para manter a estrutura do organograma alinhada
    const rootNode = topologia.nodes[0];
    
    // Pega a largura do elemento se renderizado, ou assume 190 (nodeWidth padrão)
    const el = document.getElementById(`node-${rootNode.id}`);
    const rootW = el ? el.offsetWidth : 190;
    
    const rootCenterX = rootNode.position.x + (rootW / 2);
    const shiftX = Math.round(viewCenterX - rootCenterX);
    
    if (shiftX !== 0) {
        topologia.nodes.forEach(n => {
            n.position.x += shiftX;
        });
        renderizarCanvas();
        dispararAutoSave();
    }
}

// =========================================================================
// GERENCIAMENTO INTERATIVO DE RAIAS
// =========================================================================
function abrirRenomearRaia(encodedLane) {
    if (IS_APPROVED) return;
    const raiaAtual = decodeURIComponent(encodedLane);
    const novoNome = prompt(`Renomear a Raia / Setor "${raiaAtual}" para:`, raiaAtual);
    if (!novoNome || !novoNome.trim() || novoNome.trim() === raiaAtual) return;
    renomearRaiaNoDiagrama(raiaAtual, novoNome.trim());
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function renomearRaiaNoDiagrama(raiaAtual, nomeLimpo) {
    fixarOrdemRaias();

    topologia.nodes.forEach(n => {
        if (n.data && (n.data.lane === raiaAtual || (!n.data.lane && raiaAtual === 'Geral'))) {
            n.data.lane = nomeLimpo;
        }
        if (n.data && n.data.laneAbaixo === raiaAtual) n.data.laneAbaixo = nomeLimpo;
    });
    topologia.raias_recolhidas = [...new Set((topologia.raias_recolhidas || []).map(l => l === raiaAtual ? nomeLimpo : l))];

    topologia.grid_data.forEach(r => {
        if (r.lane === raiaAtual || (!r.lane && raiaAtual === 'Geral')) {
            r.lane = nomeLimpo;
        }
    });

    // mantém ordem, raias fixas e cor própria com o novo nome (sem duplicar quando já existia)
    ['lanes', 'raias_fixas'].forEach(chave => {
        topologia[chave] = [...new Set((topologia[chave] || []).map(l => l === raiaAtual ? nomeLimpo : l))];
    });
    if (topologia.raias_cores && topologia.raias_cores[raiaAtual]) {
        topologia.raias_cores[nomeLimpo] = topologia.raias_cores[raiaAtual];
        delete topologia.raias_cores[raiaAtual];
    }
}

// Duplo clique no rótulo da raia: pop-up de configuração
let raiaEmConfiguracao = null;
function abrirConfigRaia(encodedLane) {
    const lane = decodeURIComponent(encodedLane);
    raiaEmConfiguracao = lane;
    const lanes = obterListaRaiasOrdenada();
    const blocos = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane).length;
    const propria = (topologia.raias_cores || {})[lane];

    document.getElementById('cfgRaiaNome').value = lane;
    document.getElementById('cfgRaiaCor').value = propria || corDaRaia(lane);
    document.getElementById('cfgRaiaCor').dataset.alterada = '';
    document.getElementById('cfgRaiaPosicao').textContent = `${lanes.indexOf(lane) + 1} de ${lanes.length}`;
    document.getElementById('cfgRaiaBlocos').textContent = blocos;
    document.getElementById('cfgRaiaRestaurarCor').style.display = propria ? '' : 'none';
    document.querySelectorAll('#modalConfigRaia [data-edicao]').forEach(el => { el.disabled = IS_APPROVED; });
    document.getElementById('cfgRaiaAcoes').style.display = IS_APPROVED ? 'none' : '';
    new bootstrap.Modal(document.getElementById('modalConfigRaia')).show();
}

function salvarConfigRaia() {
    if (IS_APPROVED || !raiaEmConfiguracao) return;
    let lane = raiaEmConfiguracao;
    const novoNome = document.getElementById('cfgRaiaNome').value.trim();
    const cor = document.getElementById('cfgRaiaCor');
    if (!novoNome) { alert('Informe o nome da raia.'); return; }
    if (novoNome !== lane) {
        if (obterListaRaiasOrdenada().some(l => l !== lane && l.toLowerCase() === novoNome.toLowerCase())) {
            alert(`A raia "${novoNome}" já existe neste diagrama.`);
            return;
        }
        renomearRaiaNoDiagrama(lane, novoNome);
        lane = novoNome;
    }
    if (cor.dataset.alterada) {
        topologia.raias_cores = { ...(topologia.raias_cores || {}), [lane]: cor.value };
    }
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

function restaurarCorDaRaia() {
    if (IS_APPROVED || !raiaEmConfiguracao) return;
    if (topologia.raias_cores) delete topologia.raias_cores[raiaEmConfiguracao];
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    renderizarCanvas();
    dispararAutoSave();
}

function moverRaiaPelaConfig(direcao) {
    if (!raiaEmConfiguracao) return;
    moverRaia(encodeURIComponent(raiaEmConfiguracao), direcao);
    const lanes = obterListaRaiasOrdenada();
    document.getElementById('cfgRaiaPosicao').textContent = `${lanes.indexOf(raiaEmConfiguracao) + 1} de ${lanes.length}`;
}

function excluirRaiaPelaConfig() {
    if (!raiaEmConfiguracao) return;
    const lane = raiaEmConfiguracao;
    bootstrap.Modal.getInstance(document.getElementById('modalConfigRaia'))?.hide();
    excluirRaia(encodeURIComponent(lane));
}

function moverRaia(encodedLane, direcao) {
    if (IS_APPROVED) return;
    const lane = decodeURIComponent(encodedLane);
    const lanes = obterListaRaiasOrdenada();
    const curIdx = lanes.indexOf(lane);
    if (curIdx === -1) return;

    const targetIdx = curIdx + direcao;
    if (targetIdx < 0 || targetIdx >= lanes.length) return;

    const nova = [...lanes];
    nova[curIdx] = lanes[targetIdx];
    nova[targetIdx] = lane;
    aplicarNovaOrdemDeRaias(nova);

    renderizarCanvas();
    renderizarGrelha();
    dispararAutoSave();
}

function adicionarNovaRaia() {
    if (IS_APPROVED) return;
    document.getElementById('inputRaiaLivre').value = '';
    new bootstrap.Modal(document.getElementById('modalNovaRaia')).show();
}

function adicionarRaiaLivre() {
    adicionarRaiaAoDiagrama(document.getElementById('inputRaiaLivre').value);
}

// Insere a nova raia no fim do diagrama
function adicionarRaiaAoDiagrama(nome) {
    if (IS_APPROVED) return;
    const nomeLimpo = (nome || '').trim();
    if (!nomeLimpo) return;

    const lanes = obterListaRaiasOrdenada();
    if (lanes.some(l => l.toLowerCase() === nomeLimpo.toLowerCase())) {
        alert(`A raia "${nomeLimpo}" já existe neste diagrama.`);
        return;
    }

    const posicao = lanes.length;

    const nova = [...lanes];
    nova.splice(posicao, 0, nomeLimpo);
    topologia.raias_fixas = [...new Set([...(topologia.raias_fixas || []), nomeLimpo])];
    // as faixas abaixo da nova raia descem junto com seus blocos
    const antes = calcularFaixasRaias(lanes);
    topologia.lanes = nova;
    const depois = calcularFaixasRaias(nova);
    topologia.nodes.forEach(n => {
        const l = n.data?.lane || 'Geral';
        if (antes[l] && depois[l]) n.position.y = Math.round(n.position.y - antes[l].top + depois[l].top);
    });

    bootstrap.Modal.getInstance(document.getElementById('modalNovaRaia'))?.hide();
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    preencherSugestoesDeRaias();
    dispararAutoSave();
}

function excluirRaia(encodedLane) {
    if (IS_APPROVED) return;
    const lane = decodeURIComponent(encodedLane);
    const nodesInLane = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane);

    if (!confirm(`Deseja realmente excluir a raia "${lane}" com ${nodesInLane.length} etapa(s)?`)) return;

    const idsToRemove = new Set(nodesInLane.map(n => n.id));

    topologia.nodes = topologia.nodes.filter(n => !idsToRemove.has(n.id));
    topologia.edges = topologia.edges.filter(e => !idsToRemove.has(e.source) && !idsToRemove.has(e.target));
    topologia.grid_data = topologia.grid_data.filter(r => !idsToRemove.has(r.stepId));
    topologia.lanes = (topologia.lanes || []).filter(l => l !== lane);
    topologia.raias_fixas = (topologia.raias_fixas || []).filter(l => l !== lane);
    topologia.raias_recolhidas = (topologia.raias_recolhidas || []).filter(l => l !== lane);
    topologia.nodes.forEach(n => { if (n.data && n.data.laneAbaixo === lane) delete n.data.laneAbaixo; });

    posicionarAutomaticoPorRaias(true);
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    dispararAutoSave();
}

// =========================================================================
// GESTÃO DAS RAIAS DO DIAGRAMA ABERTO (lista: nome, cor, ordem, exclusão)
// =========================================================================
function abrirGerenciarRaias() {
    renderizarListaGerenciarRaias();
    document.getElementById('gerenciarRaiasNova').style.display = IS_APPROVED ? 'none' : '';
    document.getElementById('gerenciarRaiaNovaNome').value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalGerenciarRaias')).show();
}

function renderizarListaGerenciarRaias() {
    const lista = document.getElementById('listaGerenciarRaias');
    const lanes = obterListaRaiasOrdenada();
    const dis = IS_APPROVED ? 'disabled' : '';
    lista.innerHTML = '';
    if (lanes.length === 0) {
        lista.innerHTML = '<div class="list-group-item small text-muted">Este diagrama ainda não tem raias.</div>';
        return;
    }
    lanes.forEach((lane, i) => {
        const blocos = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === lane).length;
        const row = document.createElement('div');
        row.className = 'list-group-item d-flex align-items-center gap-2';
        row.innerHTML = `
            <input type="color" class="form-control form-control-color" value="${escapeHtml(corDaRaia(lane))}" ${dis} title="Cor da faixa">
            <input type="text" name="raia_nome_x" autocomplete="off" data-lpignore="true" data-1p-ignore class="form-control form-control-sm" maxlength="100" value="${escapeHtml(lane)}" ${dis}>
            <span class="badge bg-light text-dark border text-nowrap">${blocos} bloco${blocos === 1 ? '' : 's'}</span>
            <div class="btn-group btn-group-sm">
                <button type="button" class="btn btn-light border" ${i === 0 || IS_APPROVED ? 'disabled' : ''} data-acao="cima" title="Mover para cima"><i class="bi bi-arrow-up"></i></button>
                <button type="button" class="btn btn-light border" ${i === lanes.length - 1 || IS_APPROVED ? 'disabled' : ''} data-acao="baixo" title="Mover para baixo"><i class="bi bi-arrow-down"></i></button>
                <button type="button" class="btn btn-outline-danger" ${dis} data-acao="excluir" title="Excluir raia"><i class="bi bi-trash"></i></button>
            </div>`;
        const [cor, nome] = row.querySelectorAll('input');
        cor.onchange = () => {
            topologia.raias_cores = { ...(topologia.raias_cores || {}), [lane]: cor.value };
            renderizarCanvas();
            dispararAutoSave();
        };
        nome.onchange = () => gerenciarRaiaRenomear(lane, nome.value);
        nome.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); nome.blur(); } };
        row.querySelector('[data-acao="cima"]').onclick = () => { moverRaia(encodeURIComponent(lane), -1); renderizarListaGerenciarRaias(); };
        row.querySelector('[data-acao="baixo"]').onclick = () => { moverRaia(encodeURIComponent(lane), 1); renderizarListaGerenciarRaias(); };
        row.querySelector('[data-acao="excluir"]').onclick = () => {
            excluirRaia(encodeURIComponent(lane));
            renderizarListaGerenciarRaias();
        };
        lista.appendChild(row);
    });
}

function gerenciarRaiaRenomear(atual, valor) {
    const novo = (valor || '').trim();
    if (!novo || novo === atual) { renderizarListaGerenciarRaias(); return; }
    if (obterListaRaiasOrdenada().some(l => l !== atual && l.toLowerCase() === novo.toLowerCase())) {
        alert(`A raia "${novo}" já existe neste diagrama.`);
        renderizarListaGerenciarRaias();
        return;
    }
    renomearRaiaNoDiagrama(atual, novo);
    renderizarCanvas();
    renderizarGrelha();
    renderizarOutliner();
    preencherSugestoesDeRaias();
    dispararAutoSave();
    renderizarListaGerenciarRaias();
}

function gerenciarRaiaAdicionar() {
    if (IS_APPROVED) return;
    const nome = document.getElementById('gerenciarRaiaNovaNome').value.trim();
    const cor = document.getElementById('gerenciarRaiaNovaCor').value;
    if (!nome) return;
    const antes = obterListaRaiasOrdenada().length;
    adicionarRaiaAoDiagrama(nome);
    if (obterListaRaiasOrdenada().length > antes) {
        if (cor && cor !== '#334155') topologia.raias_cores = { ...(topologia.raias_cores || {}), [nome]: cor };
        renderizarCanvas();
        dispararAutoSave();
        document.getElementById('gerenciarRaiaNovaNome').value = '';
    }
    renderizarListaGerenciarRaias();
}

// =========================================================================
// BUSCA DE RAIAS (campo "Raia" do inspetor e coluna "Raia / Setor" da Grelha)
// Lista flutuante com as raias deste diagrama; permite criar uma nova quando não há correspondência.
// =========================================================================
let buscaRaia = { input: null, atual: () => '', aoEscolher: null, ativo: -1, filtrar: false };

function semAcento(texto) {
    return String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function listaFlutuanteDeRaias() {
    let lista = document.getElementById('buscaRaiaFlutuante');
    if (!lista) {
        lista = document.createElement('div');
        lista.id = 'buscaRaiaFlutuante';
        lista.className = 'list-group shadow busca-raia-lista d-none';
        lista.setAttribute('role', 'listbox');
        // mousedown (antes do blur do campo) para o clique não se perder
        lista.addEventListener('mousedown', e => {
            const item = e.target.closest('[data-raia],[data-nova]');
            e.preventDefault();
            if (item) escolherRaiaNaBusca(item.dataset.raia || item.dataset.nova);
        });
        document.body.appendChild(lista);
    }
    return lista;
}

function renderizarBuscaDeRaia() {
    const entrada = buscaRaia.input;
    if (!entrada) return;
    const lista = listaFlutuanteDeRaias();
    const termo = buscaRaia.filtrar ? semAcento(entrada.value.trim()) : ''; // ao abrir, mostra todas as raias
    const atual = buscaRaia.atual();
    const todas = obterListaRaiasOrdenada();
    const filtradas = todas.filter(r => !termo || semAcento(r).includes(termo));
    const exata = todas.some(r => semAcento(r) === termo);

    lista.innerHTML = '';
    filtradas.forEach(nome => {
        const blocos = topologia.nodes.filter(n => (n.data?.lane || 'Geral') === nome).length;
        const item = document.createElement('div');
        item.className = 'list-group-item d-flex align-items-center gap-2' + (nome === atual ? ' fw-semibold' : '');
        item.setAttribute('role', 'option');
        item.dataset.raia = nome;
        item.innerHTML = `<span style="width:10px;height:18px;border-radius:3px;flex:0 0 10px;background:${escapeHtml(corDaRaia(nome))};"></span>
            <span class="flex-grow-1 text-truncate">${escapeHtml(nome)}</span>
            ${nome === atual ? '<i class="bi bi-check2 text-primary"></i>' : ''}
            <span class="badge bg-light text-dark border">${blocos}</span>`;
        lista.appendChild(item);
    });
    if (termo && !exata && !IS_APPROVED) {
        const novo = document.createElement('div');
        novo.className = 'list-group-item text-primary';
        novo.setAttribute('role', 'option');
        novo.dataset.nova = entrada.value.trim();
        novo.innerHTML = `<i class="bi bi-plus-circle me-1"></i> Criar raia "${escapeHtml(entrada.value.trim())}"`;
        lista.appendChild(novo);
    }
    if (!lista.children.length) {
        lista.innerHTML = '<div class="list-group-item small text-muted">Nenhuma raia encontrada.</div>';
    }
    buscaRaia.ativo = lista.querySelector('[data-raia],[data-nova]') ? 0 : -1;
    posicionarBuscaDeRaia();
    marcarItemDaBusca();
    entrada.setAttribute('aria-expanded', 'true');
}

function posicionarBuscaDeRaia() {
    const lista = listaFlutuanteDeRaias();
    const r = buscaRaia.input.getBoundingClientRect();
    lista.classList.remove('d-none');
    lista.style.width = `${Math.max(r.width, 200)}px`;
    lista.style.left = `${Math.min(r.left, window.innerWidth - lista.offsetWidth - 8)}px`;
    const abaixo = window.innerHeight - r.bottom;
    if (abaixo < Math.min(lista.scrollHeight, 230) + 8 && r.top > abaixo) {   // sem espaço embaixo: abre para cima
        lista.style.top = 'auto';
        lista.style.bottom = `${window.innerHeight - r.top + 2}px`;
    } else {
        lista.style.bottom = 'auto';
        lista.style.top = `${r.bottom + 2}px`;
    }
}

function marcarItemDaBusca() {
    const itens = [...document.querySelectorAll('#buscaRaiaFlutuante [data-raia], #buscaRaiaFlutuante [data-nova]')];
    itens.forEach((el, i) => el.classList.toggle('ativo', i === buscaRaia.ativo));
    if (itens[buscaRaia.ativo]) itens[buscaRaia.ativo].scrollIntoView({ block: 'nearest' });
}

function fecharBuscaDeRaia(restaurar) {
    const lista = document.getElementById('buscaRaiaFlutuante');
    if (lista) lista.classList.add('d-none');
    const entrada = buscaRaia.input;
    if (entrada) {
        entrada.setAttribute('aria-expanded', 'false');
        if (restaurar) entrada.value = buscaRaia.atual();
    }
    buscaRaia.input = null;
}

function escolherRaiaNaBusca(nome) {
    const entrada = buscaRaia.input;
    const aoEscolher = buscaRaia.aoEscolher;
    if (IS_APPROVED || !nome || !entrada) { fecharBuscaDeRaia(true); return; }
    entrada.value = nome;
    fecharBuscaDeRaia(false);
    aoEscolher(nome);
}

// Liga o comportamento de busca a um campo de texto. `atual()` devolve a raia vigente; `aoEscolher(nome)` aplica a escolha.
function ligarBuscaDeRaia(entrada, atual, aoEscolher) {
    if (!entrada) return;
    entrada.setAttribute('role', 'combobox');
    entrada.setAttribute('autocomplete', 'off');
    const abrir = () => { buscaRaia = { input: entrada, atual, aoEscolher, ativo: -1, filtrar: false }; renderizarBuscaDeRaia(); };
    entrada.addEventListener('focus', () => { entrada.select(); abrir(); });
    entrada.addEventListener('input', () => { if (buscaRaia.input !== entrada) abrir(); buscaRaia.filtrar = true; renderizarBuscaDeRaia(); });
    entrada.addEventListener('blur', () => setTimeout(() => { if (buscaRaia.input === entrada) fecharBuscaDeRaia(true); }, 120));
    entrada.addEventListener('keydown', e => {
        if (buscaRaia.input !== entrada && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { e.preventDefault(); abrir(); return; }
        if (buscaRaia.input !== entrada) return;
        const itens = [...listaFlutuanteDeRaias().querySelectorAll('[data-raia],[data-nova]')];
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (itens.length) {
                buscaRaia.ativo = (buscaRaia.ativo + (e.key === 'ArrowDown' ? 1 : -1) + itens.length) % itens.length;
                marcarItemDaBusca();
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            const item = itens[buscaRaia.ativo];
            if (item) escolherRaiaNaBusca(item.dataset.raia || item.dataset.nova);
        } else if (e.key === 'Escape') {
            e.stopPropagation();
            fecharBuscaDeRaia(true);
            entrada.blur();
        }
    });
}

// rolagem ou redimensionamento fora da lista: fecha (a lista é "fixa" na tela)
window.addEventListener('scroll', e => {
    if (buscaRaia.input && !(e.target.closest && e.target.closest('#buscaRaiaFlutuante'))) fecharBuscaDeRaia(true);
}, true);
window.addEventListener('resize', () => { if (buscaRaia.input) fecharBuscaDeRaia(true); });

function iniciarBuscaDeRaiaDoInspetor() {
    ligarBuscaDeRaia(
        document.getElementById('inspNodeLane'),
        () => {
            const node = topologia.nodes.find(n => n.id === selectedNodeId);
            return node ? (node.data?.lane || 'Geral') : '';
        },
        nome => aplicarEstiloNoSelecionado('lane', nome)
    );
}

iniciarBuscaDeRaiaDoInspetor();

// =========================================================================
// RECOLHER / EXPANDIR RAIAS (esconde os blocos da raia e reduz a faixa; os blocos de baixo sobem junto)
// =========================================================================
function mudarFaixasDasRaias(mutar) {
    const lanes = obterListaRaiasOrdenada();
    const antes = calcularFaixasRaias(lanes);
    mutar();
    const depois = calcularFaixasRaias(lanes);
    topologia.nodes.forEach(n => {
        const l = n.data?.lane || 'Geral';
        if (noEntreRaias(n, lanes)) return;   // reposicionados abaixo, sobre a divisa
        if (antes[l] && depois[l]) n.position.y = Math.round(n.position.y - antes[l].top + depois[l].top);
    });
    topologia.nodes.forEach(n => { if (noEntreRaias(n, lanes)) posicionarNoEmRelacaoAsRaias(n); });
    const recolhidas = new Set(topologia.raias_recolhidas || []);
    if ([...selectedNodeIds].some(id => recolhidas.has(topologia.nodes.find(n => n.id === id)?.data?.lane || 'Geral'))) desmarcarTodosNos();
}

function alternarRaiaRecolhida(encodedLane) {
    const lane = decodeURIComponent(encodedLane);
    mudarFaixasDasRaias(() => {
        const conjunto = new Set(topologia.raias_recolhidas || []);
        if (conjunto.has(lane)) conjunto.delete(lane); else conjunto.add(lane);
        topologia.raias_recolhidas = [...conjunto];
    });
    renderizarCanvas();
    renderizarOutliner();
    dispararAutoSave();
}

function definirTodasRaiasRecolhidas(recolher) {
    mudarFaixasDasRaias(() => { topologia.raias_recolhidas = recolher ? obterListaRaiasOrdenada() : []; });
    renderizarCanvas();
    renderizarOutliner();
    dispararAutoSave();
}

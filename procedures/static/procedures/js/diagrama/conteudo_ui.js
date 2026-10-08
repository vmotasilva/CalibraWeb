/* Editor de Diagramas (DOC.071) - módulo "conteudo_ui"
 * Ligação do conteúdo (conteudo.js) com o DOM: marcadores, notas, links, imagem, vaga, indicadores no bloco,
 * efetivo por ramo, legenda dos marcadores e "Atualizar do RH".
 */

const URLS_CONTEUDO = lerJsonDaPagina('conteudoUrlsData', { procedimento: '/procedures/procedimentos/0/', diagramaAbrir: '/procedures/diagramas/00000000-0000-0000-0000-000000000000/abrir/' });
const ID_ZERO = '00000000-0000-0000-0000-000000000000';

// ------------------------------------------------------------------ ícones dos marcadores (SVG 16x16)
function svgMarcador(m, tamanho = 14) {
    const cor = m.cor;
    let miolo = '';
    if (m.tipo === 'numero') {
        miolo = `<circle cx="8" cy="8" r="7.5" fill="${cor}"/><text x="8" y="11.6" text-anchor="middle" font-size="10" font-weight="700" fill="#fff" font-family="Arial,sans-serif">${m.valor}</text>`;
    } else if (m.tipo === 'progresso') {
        if (m.valor === 100) {
            miolo = `<circle cx="8" cy="8" r="7.5" fill="${cor}"/><path d="M4.4 8.4l2.4 2.4 4.8-5" stroke="#fff" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
        } else {
            const ang = (m.valor / 100) * 2 * Math.PI;
            const x = 8 + 6 * Math.sin(ang), y = 8 - 6 * Math.cos(ang);
            const fatia = m.valor === 0 ? '' : `<path d="M8 8 L8 2 A6 6 0 ${m.valor > 50 ? 1 : 0} 1 ${x.toFixed(2)} ${y.toFixed(2)} Z" fill="${cor}"/>`;
            miolo = `<circle cx="8" cy="8" r="7" fill="#fff" stroke="${cor}" stroke-width="1.5"/>${fatia}`;
        }
    } else if (m.tipo === 'bandeira') {
        miolo = `<path d="M3.5 1.5v13" stroke="${cor}" stroke-width="1.6" stroke-linecap="round"/><path d="M4.3 2.5h8.2l-2.2 3.2 2.2 3.2H4.3z" fill="${cor}"/>`;
    } else if (m.tipo === 'estrela') {
        miolo = `<path d="M8 1.2l2.1 4.5 4.9.6-3.6 3.4.9 4.9L8 12.3l-4.3 2.3.9-4.9L1 6.3l4.9-.6z" fill="${cor}"/>`;
    } else if (m.tipo === 'pessoa') {
        miolo = `<circle cx="8" cy="5" r="3.2" fill="${cor}"/><path d="M1.8 15c0-3.5 2.8-5.7 6.2-5.7s6.2 2.2 6.2 5.7z" fill="${cor}"/>`;
    }
    return `<svg class="marcador-svg" width="${tamanho}" height="${tamanho}" viewBox="0 0 16 16" aria-label="${escapeHtml(m.rotulo)}"><title>${escapeHtml(m.rotulo)}</title>${miolo}</svg>`;
}

function rotuloDoMarcadorNaLegenda(id) {
    const personalizado = topologia.legenda?.rotulos?.[id];
    return personalizado || DiagramaConteudo.marcadorPorId(id).rotulo;
}

function htmlMarcadoresDoBloco(node) {
    const lista = (node.data?.markers || []).filter(id => DiagramaConteudo.marcadorValido(id));
    if (lista.length === 0) return '';
    return `<span class="marcadores-bloco">${lista.map(id => {
        const m = DiagramaConteudo.marcadorPorId(id);
        return svgMarcador(Object.assign({}, m, { rotulo: rotuloDoMarcadorNaLegenda(id) }));
    }).join('')}</span>`;
}

// ------------------------------------------------------------------ conteúdo visual no bloco
function urlDoLink(link) {
    if (link.tipo === 'url') return link.url;
    if (link.tipo === 'procedimento') return URLS_CONTEUDO.procedimento.replace('/0/', `/${link.id}/`);
    if (link.tipo === 'diagrama') return URLS_CONTEUDO.diagramaAbrir.replace(ID_ZERO, link.id);
    return '#';
}

function iconeDoLink(link) {
    return { url: 'bi-globe2', procedimento: 'bi-file-earmark-text', diagrama: 'bi-diagram-3' }[link.tipo] || 'bi-link-45deg';
}

function aplicarConteudoVisualAoNo(nodeEl, node) {
    const dados = node.data || {};

    if (dados.vaga === true) {
        nodeEl.classList.add('node-vaga');
        const alvo = nodeEl.querySelector('.rotulo-bloco');
        if (alvo) alvo.insertAdjacentHTML('beforeend', ' <span class="selo-vago">VAGO</span>');
    }

    if (dados.imagem && dados.imagem.id && !dados.colab && node.type === 'process') {
        nodeEl.classList.add('node-com-imagem');
        nodeEl.insertAdjacentHTML('afterbegin', `<img class="bloco-imagem" src="/procedures/api/diagramas/imagens/${dados.imagem.id}/" alt="" onerror="this.remove()">`);
    }

    // Indicadores no canto: nota, links e aviso de colaborador não encontrado no RH
    const indicadores = [];
    if (dados.colab && dados.colab.removido) {
        indicadores.push(`<span class="indicador indicador-alerta" title="Colaborador não encontrado no RH (use Exibir &gt; Atualizar colaboradores pelo RH)"><i class="bi bi-exclamation-triangle-fill"></i></span>`);
    }
    if (dados.nota && dados.nota.trim()) {
        indicadores.push(`<button type="button" class="indicador" data-acao="nota" title="${escapeHtml(dados.nota.slice(0, 300))}"><i class="bi bi-sticky-fill"></i></button>`);
    }
    (dados.links || []).forEach((link, i) => {
        indicadores.push(`<button type="button" class="indicador" data-acao="link" data-indice="${i}" title="${escapeHtml(link.rotulo || urlDoLink(link))}"><i class="bi ${iconeDoLink(link)}"></i></button>`);
    });
    if (indicadores.length) {
        nodeEl.insertAdjacentHTML('beforeend', `<div class="indicadores-bloco">${indicadores.join('')}</div>`);
        nodeEl.querySelectorAll('.indicadores-bloco .indicador').forEach(btn => {
            ['mousedown', 'dblclick'].forEach(t => btn.addEventListener(t, ev => ev.stopPropagation()));
            btn.addEventListener('click', ev => {
                ev.stopPropagation();
                if (btn.dataset.acao === 'nota') { selecionarNo(node.id); abrirAbaConteudo(); return; }
                if (btn.dataset.acao === 'link') {
                    const link = (node.data.links || [])[Number(btn.dataset.indice)];
                    if (link) window.open(urlDoLink(link), '_blank', 'noopener');
                }
            });
        });
    }

    // Efetivo do ramo (pessoas e vagas abaixo do bloco)
    if (efetivoCache && arvoreEfetivo && (arvoreEfetivo.filhos.get(String(node.id)) || []).length > 0) {
        const c = efetivoCache[String(node.id)];
        if (c && (c.pessoas > 0 || c.vagas > 0)) {
            nodeEl.insertAdjacentHTML('beforeend',
                `<span class="badge-efetivo" title="Pessoas e vagas neste ramo (inclui este bloco)"><i class="bi bi-people-fill"></i> ${c.pessoas}${c.vagas ? ` &middot; ${c.vagas} vaga${c.vagas > 1 ? 's' : ''}` : ''}</span>`);
        }
    }
}

function abrirAbaConteudo() {
    const aba = document.querySelector('[data-bs-target="#inspTabConteudo"]');
    if (aba) bootstrap.Tab.getOrCreateInstance(aba).show();
}

// ------------------------------------------------------------------ painel "Conteúdo" do bloco
function atualizarPainelConteudo(node) {
    const vazio = document.getElementById('conteudoVazio');
    const controles = document.getElementById('conteudoControles');
    if (!vazio || !controles) return;
    vazio.classList.toggle('d-none', !!node);
    controles.classList.toggle('d-none', !node);
    if (!node) return;
    const dados = node.data || {};

    document.getElementById('cdVaga').checked = dados.vaga === true;
    document.getElementById('cdBlocoRH').classList.toggle('d-none', !dados.colab);

    // paleta de marcadores
    const emUso = new Set(dados.markers || []);
    const paleta = document.getElementById('cdPaleta');
    if (!paleta.dataset.montada) {
        paleta.innerHTML = DiagramaConteudo.GRUPOS.map(g => `
            <div class="mb-1"><div class="small text-muted">${g.nome}</div>
            <div class="d-flex flex-wrap gap-1">${g.itens.map(m => `<button type="button" class="marcador-opcao" data-marcador="${m.id}" title="${escapeHtml(m.rotulo)}" onclick="alternarMarcador('${m.id}')">${svgMarcador(m, 18)}</button>`).join('')}</div></div>`).join('');
        paleta.dataset.montada = '1';
    }
    paleta.querySelectorAll('[data-marcador]').forEach(b => b.classList.toggle('ativo', emUso.has(b.dataset.marcador)));
    document.getElementById('cdContadorMarcadores').textContent = `${emUso.size}/${DiagramaConteudo.MAX_MARCADORES}`;

    // nota
    const nota = document.getElementById('cdNota');
    if (document.activeElement !== nota) nota.value = dados.nota || '';
    document.getElementById('cdContadorNota').textContent = `${(dados.nota || '').length}/${DiagramaConteudo.MAX_NOTA}`;

    // links
    const lista = document.getElementById('cdLinks');
    lista.innerHTML = '';
    (dados.links || []).forEach((link, i) => {
        const li = document.createElement('div');
        li.className = 'd-flex align-items-center gap-2 small border rounded px-2 py-1 mb-1';
        li.innerHTML = `<i class="bi ${iconeDoLink(link)}"></i><span class="flex-grow-1 text-truncate" title="${escapeHtml(urlDoLink(link))}">${escapeHtml(link.rotulo || urlDoLink(link))}</span>
            <a href="${escapeHtml(urlDoLink(link))}" target="_blank" rel="noopener" class="text-decoration-none" title="Abrir"><i class="bi bi-box-arrow-up-right"></i></a>
            <button type="button" class="btn btn-link btn-sm text-danger p-0" title="Remover link" onclick="removerLink(${i})"><i class="bi bi-x-lg"></i></button>`;
        lista.appendChild(li);
    });

    // imagem
    const previa = document.getElementById('cdImagemPrevia');
    const temImagem = !!(dados.imagem && dados.imagem.id) && !dados.colab;
    previa.classList.toggle('d-none', !temImagem);
    if (temImagem) previa.querySelector('img').src = `/procedures/api/diagramas/imagens/${dados.imagem.id}/`;
    document.getElementById('cdAvisoImagemColab').classList.toggle('d-none', !dados.colab);
    document.getElementById('cdArquivoImagem').disabled = !!dados.colab;
}

function reaplicarConteudo() {
    if (arvoreAtiva()) aplicarLayoutArvore(); else renderizarCanvas();
    atualizarSelecoesVisuais();
    dispararAutoSave();
}

function nosDaSelecao() {
    return [...selectedNodeIds].map(id => topologia.nodes.find(n => n.id === id)).filter(Boolean);
}

// ------------------------------------------------------------------ marcadores
function alternarMarcador(marcadorId) {
    if (IS_APPROVED || !DiagramaConteudo.marcadorValido(marcadorId)) return;
    const alvos = nosDaSelecao();
    if (alvos.length === 0) return;
    const principal = noPrincipalDaSelecao() || alvos[0];
    const adicionar = !(principal.data?.markers || []).includes(marcadorId);
    let atingiuLimite = false;
    alvos.forEach(node => {
        if (!node.data) node.data = {};
        let lista = (node.data.markers || []).slice();
        if (adicionar) {
            // prioridade e progresso são exclusivos dentro do grupo (só um valor por bloco)
            const grupo = marcadorId.split('-')[0];
            if (grupo === 'prio' || grupo === 'prog') lista = lista.filter(m => !m.startsWith(grupo + '-'));
            if (!lista.includes(marcadorId)) {
                if (lista.length >= DiagramaConteudo.MAX_MARCADORES) { atingiuLimite = true; return; }
                lista.push(marcadorId);
            }
        } else {
            lista = lista.filter(m => m !== marcadorId);
        }
        if (lista.length) node.data.markers = lista; else delete node.data.markers;
    });
    if (atingiuLimite) mostrarAvisoNoEditor(`Limite de ${DiagramaConteudo.MAX_MARCADORES} marcadores por bloco.`);
    reaplicarConteudo();
}

function removerTodosMarcadores() {
    if (IS_APPROVED) return;
    nosDaSelecao().forEach(node => { if (node.data) delete node.data.markers; });
    reaplicarConteudo();
}

// ------------------------------------------------------------------ nota
let notaTimer = null;
function editarNota(texto) {
    if (IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node) return;
    if (!node.data) node.data = {};
    const limpo = texto.slice(0, DiagramaConteudo.MAX_NOTA);
    if (limpo.trim()) node.data.nota = limpo; else delete node.data.nota;
    document.getElementById('cdContadorNota').textContent = `${limpo.length}/${DiagramaConteudo.MAX_NOTA}`;
    clearTimeout(notaTimer);
    notaTimer = setTimeout(() => { // redesenha só depois de parar de digitar (preserva o foco do campo)
        renderizarCanvas();
        dispararAutoSave();
    }, 500);
}

// ------------------------------------------------------------------ links
function aoMudarTipoDeLink() {
    const tipo = document.getElementById('cdTipoLink').value;
    const campo = document.getElementById('cdBuscaLink');
    campo.placeholder = tipo === 'url' ? 'https://...' : (tipo === 'procedimento' ? 'Código ou nome do procedimento' : 'Número ou título do diagrama');
    campo.value = '';
    document.getElementById('cdResultadosLink').innerHTML = '';
    document.getElementById('cdRotuloLinkBox').classList.toggle('d-none', tipo !== 'url');
}

let buscaLinkTimer = null;
function buscarParaLink(termo) {
    clearTimeout(buscaLinkTimer);
    const tipo = document.getElementById('cdTipoLink').value;
    const lista = document.getElementById('cdResultadosLink');
    lista.innerHTML = '';
    if (tipo === 'url' || termo.trim().length < (tipo === 'diagrama' ? 1 : 2)) return;
    buscaLinkTimer = setTimeout(async () => {
        try {
            const url = tipo === 'procedimento' ? '/procedures/api/diagramas/procedimentos/' : '/procedures/api/diagramas/buscar/';
            const resp = await fetch(`${url}?q=${encodeURIComponent(termo.trim())}`);
            if (!resp.ok) throw new Error(resp.status);
            const dados = await resp.json();
            if (dados.results.length === 0) { lista.innerHTML = '<div class="list-group-item small text-muted">Nada encontrado.</div>'; return; }
            dados.results.forEach(r => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action py-1 small';
                const rotulo = tipo === 'procedimento' ? `${r.codigo} - ${r.nome}` : `${r.identificador} - ${r.titulo}`;
                btn.textContent = rotulo;
                btn.onclick = () => adicionarLink(tipo === 'procedimento'
                    ? { tipo, id: r.id, rotulo: rotulo.slice(0, 120) }
                    : { tipo, id: r.id, rotulo: rotulo.slice(0, 120) });
                lista.appendChild(btn);
            });
        } catch (e) {
            lista.innerHTML = '<div class="list-group-item small text-danger">Erro na busca.</div>';
        }
    }, 300);
}

function adicionarLinkWeb() {
    const url = document.getElementById('cdBuscaLink').value.trim();
    if (!DiagramaConteudo.urlValida(url)) {
        mostrarAvisoNoEditor('Informe um endereço completo, começando com http:// ou https://');
        return;
    }
    const rotulo = document.getElementById('cdRotuloLink').value.trim();
    adicionarLink({ tipo: 'url', url, rotulo: rotulo || url });
}

function adicionarLink(link) {
    if (IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node) return;
    if (!node.data) node.data = {};
    const atuais = (node.data.links || []).slice();
    if (atuais.length >= DiagramaConteudo.MAX_LINKS) { mostrarAvisoNoEditor(`Limite de ${DiagramaConteudo.MAX_LINKS} links por bloco.`); return; }
    if (atuais.some(l => l.tipo === link.tipo && String(l.id) === String(link.id) && l.url === link.url)) { mostrarAvisoNoEditor('Esse link já está no bloco.'); return; }
    atuais.push(link);
    node.data.links = DiagramaConteudo.normalizarLinks(atuais);
    document.getElementById('cdBuscaLink').value = '';
    document.getElementById('cdRotuloLink').value = '';
    document.getElementById('cdResultadosLink').innerHTML = '';
    reaplicarConteudo();
}

function removerLink(indice) {
    if (IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node?.data?.links) return;
    node.data.links.splice(indice, 1);
    if (!node.data.links.length) delete node.data.links;
    reaplicarConteudo();
}

// ------------------------------------------------------------------ imagem
async function enviarImagemDoBloco(input) {
    const arquivo = input.files && input.files[0];
    input.value = '';
    if (!arquivo || IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node) return;
    const formulario = new FormData();
    formulario.append('arquivo', arquivo);
    try {
        const resp = await fetch('/procedures/api/diagramas/imagens/', { method: 'POST', headers: { 'X-CSRFToken': CSRF_TOKEN }, body: formulario });
        const dados = await resp.json();
        if (!resp.ok) { alert(dados.error || 'Não foi possível enviar a imagem.'); return; }
        if (!node.data) node.data = {};
        node.data.imagem = { id: dados.id };
        reaplicarConteudo();
    } catch (e) {
        alert('Erro de conexão ao enviar a imagem.');
    }
}

function removerImagemDoBloco() {
    if (IS_APPROVED) return;
    const node = noPrincipalDaSelecao();
    if (!node?.data) return;
    delete node.data.imagem;
    reaplicarConteudo();
}

// ------------------------------------------------------------------ vaga
function definirVaga(ligado) {
    if (IS_APPROVED) return;
    nosDaSelecao().forEach(node => {
        if (!node.data) node.data = {};
        if (ligado) {
            if (node.data.colab) {
                const cargo = node.data.colab.cargo || '';
                if (!confirm(`Marcar "${node.data.colab.nome}" como vaga desvincula o colaborador deste bloco (nome e foto). O bloco passará a mostrar a função${cargo ? ` "${cargo}"` : ''}. Continuar?`)) return;
                node.data.label = cargo || 'Vaga';
                delete node.data.colab;
                sincronizarGridDoNo(node);
            }
            node.data.vaga = true;
        } else {
            delete node.data.vaga;
        }
    });
    reaplicarConteudo();
}

// ------------------------------------------------------------------ efetivo
function alternarEfetivo() {
    if (IS_APPROVED) return;
    topologia.mostrar_efetivo = !topologia.mostrar_efetivo;
    if (!topologia.mostrar_efetivo) delete topologia.mostrar_efetivo;
    atualizarMarcasDeMenuConteudo();
    renderizarCanvas();
    dispararAutoSave();
}

function atualizarMarcasDeMenuConteudo() {
    const marca = document.getElementById('menuEfetivoCheck');
    if (marca) marca.classList.toggle('invisible', !topologia.mostrar_efetivo);
}

function abrirResumoEfetivo() {
    const resumo = DiagramaConteudo.resumoPorRamo(topologia.nodes, arvoreAtual());
    const corpo = document.getElementById('corpoResumoEfetivo');
    const fmt = v => (v === null ? '-' : `${String(v).replace('.', ',')}%`);
    corpo.innerHTML = resumo.linhas.length === 0
        ? '<tr><td colspan="5" class="text-center text-muted py-3">Sem ramos para resumir. Ligue blocos em hierarquia e vincule colaboradores ou vagas.</td></tr>'
        : resumo.linhas.map(l => `<tr><td>${escapeHtml(l.nome)}</td><td class="text-end">${l.pessoas}</td><td class="text-end">${l.vagas}</td><td class="text-end">${l.total}</td><td class="text-end">${fmt(l.ocupacao)}</td></tr>`).join('');
    const t = resumo.total;
    document.getElementById('rodapeResumoEfetivo').innerHTML = `<td class="fw-bold">Total do diagrama</td><td class="text-end fw-bold">${t.pessoas}</td><td class="text-end fw-bold">${t.vagas}</td><td class="text-end fw-bold">${t.total}</td><td class="text-end fw-bold">${fmt(t.ocupacao)}</td>`;
    new bootstrap.Modal(document.getElementById('modalEfetivo')).show();
}

// ------------------------------------------------------------------ legenda dos marcadores
function abrirLegenda() {
    const emUso = DiagramaConteudo.marcadoresEmUso(topologia.nodes);
    const lista = document.getElementById('listaLegenda');
    document.getElementById('legendaMostrar').checked = !!topologia.legenda?.mostrar;
    if (emUso.length === 0) {
        lista.innerHTML = '<div class="text-muted small">Nenhum marcador em uso. Selecione um bloco e escolha marcadores na aba Conteúdo.</div>';
    } else {
        lista.innerHTML = emUso.map(id => {
            const m = DiagramaConteudo.marcadorPorId(id);
            return `<div class="d-flex align-items-center gap-2 mb-2">${svgMarcador(m, 20)}
                <input type="text" class="form-control form-control-sm" maxlength="60" data-legenda="${id}" placeholder="${escapeHtml(m.rotulo)}" value="${escapeHtml(topologia.legenda?.rotulos?.[id] || '')}"></div>`;
        }).join('');
    }
    new bootstrap.Modal(document.getElementById('modalLegenda')).show();
}

function salvarLegenda() {
    if (IS_APPROVED) return;
    const rotulos = {};
    document.querySelectorAll('#listaLegenda [data-legenda]').forEach(campo => {
        const texto = campo.value.trim().slice(0, 60);
        if (texto) rotulos[campo.dataset.legenda] = texto;
    });
    const mostrar = document.getElementById('legendaMostrar').checked;
    if (mostrar || Object.keys(rotulos).length) topologia.legenda = { mostrar, rotulos }; else delete topologia.legenda;
    bootstrap.Modal.getInstance(document.getElementById('modalLegenda'))?.hide();
    renderizarCanvas();
    dispararAutoSave();
}

function atualizarLegendaVisual() {
    let caixa = document.getElementById('legendaMarcadores');
    const container = document.getElementById('viewCanvasContainer');
    if (!container) return;
    if (!caixa) {
        caixa = document.createElement('div');
        caixa.id = 'legendaMarcadores';
        caixa.className = 'legenda-marcadores';
        container.appendChild(caixa);
    }
    const emUso = DiagramaConteudo.marcadoresEmUso(topologia.nodes);
    if (!topologia.legenda?.mostrar || emUso.length === 0) { caixa.classList.add('d-none'); return; }
    caixa.classList.remove('d-none');
    caixa.innerHTML = `<div class="fw-bold small mb-1">Legenda</div>` + emUso.map(id => {
        const m = DiagramaConteudo.marcadorPorId(id);
        return `<div class="d-flex align-items-center gap-2 small">${svgMarcador(m, 14)}<span>${escapeHtml(rotuloDoMarcadorNaLegenda(id))}</span></div>`;
    }).join('');
}

// ------------------------------------------------------------------ atualizar do RH
let diferencasRHPendentes = [];
let atuaisRHPendentes = {};

async function consultarRH(ids) {
    const resp = await fetch('/procedures/api/diagramas/colaboradores/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
        body: JSON.stringify({ ids })
    });
    if (!resp.ok) throw new Error((await resp.json()).error || resp.status);
    const dados = (await resp.json()).results;
    const atuais = {};
    Object.keys(dados).forEach(k => { atuais[Number(k)] = dados[k]; });
    return atuais;
}

async function atualizarColaboradoresPeloRH(somenteSelecionados) {
    if (IS_APPROVED) return;
    const blocos = (somenteSelecionados ? nosDaSelecao() : topologia.nodes).filter(n => n.data?.colab);
    if (blocos.length === 0) { mostrarAvisoNoEditor('Não há blocos de colaborador para atualizar.'); return; }
    try {
        atuaisRHPendentes = await consultarRH([...new Set(blocos.map(n => n.data.colab.id))]);
    } catch (e) {
        alert('Não foi possível consultar o RH agora: ' + e.message);
        return;
    }
    diferencasRHPendentes = DiagramaConteudo.diferencasRH(blocos, atuaisRHPendentes);
    const corpo = document.getElementById('corpoAtualizacaoRH');
    const aplicaveis = diferencasRHPendentes.filter(d => d.nome || d.cargo || d.temFoto || d.removido || d.reencontrado);
    if (diferencasRHPendentes.length === 0) {
        corpo.innerHTML = `<div class="alert alert-success mb-0"><i class="bi bi-check-circle"></i> ${blocos.length} colaborador(es) conferidos: tudo está igual ao RH.</div>`;
    } else {
        corpo.innerHTML = `<p class="small text-muted">${blocos.length} colaborador(es) conferidos. Veja o que mudou no RH:</p><ul class="list-group">` + diferencasRHPendentes.map(d => {
            const itens = [];
            if (d.removido) itens.push('<span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> não encontrado no RH (o bloco será sinalizado, sem apagar nada)</span>');
            if (d.reencontrado) itens.push('<span class="text-success">voltou a existir no RH (o sinal de alerta será retirado)</span>');
            if (d.nome) itens.push(`nome: <s>${escapeHtml(d.nome.de)}</s> &rarr; <strong>${escapeHtml(d.nome.para)}</strong>`);
            if (d.cargo) itens.push(`função: <s>${escapeHtml(d.cargo.de || '(vazia)')}</s> &rarr; <strong>${escapeHtml(d.cargo.para || '(vazia)')}</strong>`);
            if (d.cargoPersonalizado) itens.push(`função <em>personalizada</em> mantida ("${escapeHtml(d.cargoPersonalizado.bloco)}"); no RH é "${escapeHtml(d.cargoPersonalizado.rh)}"`);
            if (d.temFoto) itens.push(d.temFoto.para ? 'agora tem foto no RH' : 'a foto foi removida do RH');
            return `<li class="list-group-item small"><div class="fw-semibold">${escapeHtml(d.rotulo)}</div>${itens.map(i => `<div>${i}</div>`).join('')}</li>`;
        }).join('') + '</ul>';
    }
    document.getElementById('btnAplicarRH').classList.toggle('d-none', aplicaveis.length === 0);
    new bootstrap.Modal(document.getElementById('modalRH')).show();
}

function aplicarAtualizacoesDoRH() {
    if (IS_APPROVED) return;
    diferencasRHPendentes.forEach(d => {
        const node = topologia.nodes.find(n => String(n.id) === d.id);
        if (!node?.data?.colab) return;
        const colab = node.data.colab;
        if (d.removido) colab.removido = true;
        if (d.reencontrado) delete colab.removido;
        if (d.nome) colab.nome = d.nome.para;
        if (d.cargo) colab.cargo = d.cargo.para;
        if (d.temFoto) colab.temFoto = d.temFoto.para;
        node.data.label = nomeExibicaoColab(colab);
        sincronizarGridDoNo(node);
    });
    // anota a última função lida do RH nos blocos que não foram personalizados (base das próximas comparações)
    topologia.nodes.forEach(n => {
        const colab = n.data?.colab;
        const atual = colab && atuaisRHPendentes[colab.id];
        if (atual && atual.existe !== false && (colab.cargo || '') === (atual.cargo || '')) colab.cargoRH = atual.cargo || '';
    });
    bootstrap.Modal.getInstance(document.getElementById('modalRH'))?.hide();
    reaplicarConteudo();
    mostrarAvisoNoEditor('Colaboradores atualizados pelo RH.');
}

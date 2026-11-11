/* Editor visual das apresentações (telao_editor.html). Tudo fica em `estado` até clicar em Salvar.
   Slide automático: {origem:"auto", provedor, filtros, duracao} (ou assunto). Slide manual: {origem:"manual", titulo, itens:[{card_id, pos, visual, params, filtros}]}.
   Campos que começam com "_" são só do editor (não são enviados). */
(function () {
  var D = JSON.parse(document.getElementById("edDados").textContent);
  var $ = function (id) { return document.getElementById(id); };
  var el = TelaoCards.el;
  var COL = D.grade.colunas, LIN = D.grade.linhas;
  var seq = 0;
  function novoId(p) { return (p || "i") + (++seq); }

  var cardInfo = {};   // id -> {card, secao, modulo}
  D.catalogo.forEach(function (m) { m.secoes.forEach(function (s) { s.cards.forEach(function (c) { cardInfo[c.id] = { card: c, secao: s, modulo: m }; }); }); });

  var estado = { modelo: D.modelo, slides: [], sel: 0, itemSel: null, sujo: false };
  var grade = null, reqPrevia = 0, instCache = {}, autoIdx = 0, temporizador = null;

  function prep(s) {
    s = JSON.parse(JSON.stringify(s)); s._uid = novoId("s");
    (s.itens || []).forEach(function (i) { i._id = novoId(); i.visual = i.visual || { titulo: true, max_itens: null }; });
    return s;
  }
  estado.slides = D.slides.map(prep);
  if (!estado.slides.length) estado.slides.push(novoManual());

  function novoManual() { return prep({ origem: "manual", titulo: "Novo slide", duracao: null, layout: { modo: "grade", colunas: COL, linhas: LIN }, itens: [] }); }
  function atual() { return estado.slides[estado.sel]; }
  function sujar() { estado.sujo = true; }
  function limpo(o) { return JSON.parse(JSON.stringify(o, function (k, v) { return k.charAt(0) === "_" ? undefined : v; })); }
  function csrf() { var i = document.querySelector("#edCsrf input[name=csrfmiddlewaretoken]"); return i ? i.value : ""; }
  function post(url, corpo) {
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify(corpo) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, dados: j }; }); });
  }
  function alerta(msg, tipo) {
    var a = $("edAlerta"); a.innerHTML = "";
    if (!msg) return;
    var d = el("div", "alert alert-" + (tipo || "danger") + " py-2 mb-2"); (Array.isArray(msg) ? msg : [msg]).forEach(function (m) { d.appendChild(el("div", null, m)); }); a.appendChild(d);
    if (tipo === "success") setTimeout(function () { if (a.firstChild === d) a.innerHTML = ""; }, 4000);
  }

  // ---------------------------------------------------------------- configurações
  function lerConfig() {
    var m = estado.modelo;
    $("edNome").value = m.nome || ""; $("edDescricao").value = m.descricao || ""; $("edIcone").value = m.icone || "";
    $("edDuracao").value = m.duracao_padrao || 15; $("edResumo").checked = !!m.resumo; $("edCompartilhada").checked = !!m.compartilhada; $("edAtivo").checked = m.ativo !== false;
    link();
  }
  function link() { var b = $("edApresentar"); if (estado.modelo.id) { b.href = D.urls.player + "?p=m" + estado.modelo.id + "#cheia"; b.classList.remove("d-none"); } }
  [["edNome", "nome"], ["edDescricao", "descricao"], ["edIcone", "icone"], ["edDuracao", "duracao_padrao"]].forEach(function (p) {
    $(p[0]).addEventListener("input", function () { estado.modelo[p[1]] = this.value; sujar(); });
  });
  [["edResumo", "resumo"], ["edCompartilhada", "compartilhada"], ["edAtivo", "ativo"]].forEach(function (p) {
    $(p[0]).addEventListener("change", function () { estado.modelo[p[1]] = this.checked; sujar(); if (p[1] === "resumo") atualizarPrevia(); });
  });

  // ---------------------------------------------------------------- lista de slides
  function rotuloSlide(s) {
    if (s.origem === "manual") return s.titulo || "Slide";
    if (s.tipo === "assunto") return s.titulo || "Assunto";
    return (D.rotulos[s.provedor] || [s.provedor])[0];
  }
  function iconeSlide(s) { return s.origem === "manual" ? "bi-layout-wtf" : s.tipo === "assunto" ? "bi-layout-text-window" : (D.rotulos[s.provedor] || [0, "bi-display"])[1]; }
  function btn(ic, titulo, fn, cls) {
    var b = el("button", "btn btn-sm btn-link text-secondary " + (cls || "")); b.type = "button"; b.title = titulo; b.innerHTML = '<i class="bi ' + ic + '"></i>';
    b.addEventListener("click", function (e) { e.stopPropagation(); fn(); }); return b;
  }
  function renderLista() {
    var ul = $("edLista"); ul.innerHTML = "";
    estado.slides.forEach(function (s, i) {
      var li = el("li", "ed-slide" + (i === estado.sel ? " ativo" : ""));
      li.appendChild(el("div", "n", String(i + 1)));
      var ti = el("div", "ti"), t = el("b", null, rotuloSlide(s)); ti.appendChild(t);
      var sub = s.origem === "manual" ? ((s.itens || []).length + " card(s) · manual") : "automático";
      ti.appendChild(el("small", null, sub)); li.appendChild(ti);
      var ac = el("div", "ac");
      ac.appendChild(btn("bi-arrow-up", "Subir", function () { mover(i, -1); })); ac.appendChild(btn("bi-arrow-down", "Descer", function () { mover(i, 1); }));
      ac.appendChild(btn("bi-files", "Duplicar", function () { duplicar(i); })); ac.appendChild(btn("bi-trash", "Excluir", function () { excluir(i); }, "text-danger"));
      li.appendChild(ac);
      li.addEventListener("click", function () { selecionar(i); });
      ul.appendChild(li);
    });
  }
  function selecionar(i) { estado.sel = i; estado.itemSel = null; autoIdx = 0; render(); }
  function mover(i, d) {
    var j = i + d; if (j < 0 || j >= estado.slides.length) return;
    var t = estado.slides[i]; estado.slides[i] = estado.slides[j]; estado.slides[j] = t;
    if (estado.sel === i) estado.sel = j; else if (estado.sel === j) estado.sel = i;
    sujar(); renderLista();
  }
  function duplicar(i) { var c = prep(limpo(estado.slides[i])); estado.slides.splice(i + 1, 0, c); sujar(); selecionar(i + 1); }
  function excluir(i) {
    if (!confirm("Excluir este slide?")) return;
    estado.slides.splice(i, 1); if (!estado.slides.length) estado.slides.push(novoManual());
    sujar(); selecionar(Math.min(estado.sel, estado.slides.length - 1));
  }
  $("edNovoManual").addEventListener("click", function () { estado.slides.push(novoManual()); sujar(); selecionar(estado.slides.length - 1); });
  Object.keys(D.rotulos).forEach(function (k) {
    var li = el("li"), a = el("a", "dropdown-item"); a.href = "#"; a.innerHTML = '<i class="bi ' + D.rotulos[k][1] + ' me-2"></i>' + D.rotulos[k][0];
    a.addEventListener("click", function (e) { e.preventDefault(); estado.slides.push(prep({ origem: "auto", provedor: k, filtros: {} })); sujar(); selecionar(estado.slides.length - 1); });
    li.appendChild(a); $("edMenuAuto").appendChild(li);
  });

  // ---------------------------------------------------------------- formulário de filtros (gerado dos campos do módulo)
  function campoEl(c, filtros, onChange) {
    var w = el("div", "ed-camp"), v = filtros[c.nome];
    if (c.tipo === "bool") {
      var f = el("div", "form-check"), i = el("input", "form-check-input"); i.type = "checkbox"; i.checked = v === true;
      i.addEventListener("change", function () { if (i.checked) filtros[c.nome] = true; else delete filtros[c.nome]; onChange(); });
      f.appendChild(i); f.appendChild(el("label", "form-check-label small", c.rotulo)); w.appendChild(f);
    } else if (c.tipo === "select") {
      w.appendChild(el("label", "form-label small fw-bold mb-1", c.rotulo));
      var s = el("select", "form-select form-select-sm"); s.appendChild(new Option("Padrão", ""));
      c.opcoes.forEach(function (o) { if (o[0]) s.appendChild(new Option(o[1], o[0])); });
      s.value = v || ""; s.addEventListener("change", function () { if (s.value) filtros[c.nome] = s.value; else delete filtros[c.nome]; onChange(); });
      w.appendChild(s);
    } else {
      w.appendChild(el("div", "small fw-bold mb-1", c.rotulo));
      var box = el("div", "multi"), marcados = v || [];
      c.opcoes.forEach(function (o) {
        var f = el("div", "form-check"), i = el("input", "form-check-input"); i.type = "checkbox"; i.checked = marcados.indexOf(o[0]) >= 0;
        i.addEventListener("change", function () {
          var cur = (filtros[c.nome] || []).filter(function (x) { return x !== o[0]; }); if (i.checked) cur.push(o[0]);
          if (cur.length) filtros[c.nome] = cur; else delete filtros[c.nome]; onChange();
        });
        f.appendChild(i); f.appendChild(el("label", "form-check-label small", o[1])); box.appendChild(f);
      });
      if (!c.opcoes.length) box.appendChild(el("span", "text-muted small", "Nenhuma opção disponível."));
      w.appendChild(box); if (c.ajuda) w.appendChild(el("div", "form-text", c.ajuda));
    }
    return w;
  }
  function formFiltros(provedor, filtros, excluir, onChange) {
    var f = el("div");
    (D.campos[provedor] || []).forEach(function (c) { if (excluir.indexOf(c.nome) < 0) f.appendChild(campoEl(c, filtros, onChange)); });
    return f;
  }
  function depois(fn, ms) { clearTimeout(temporizador); temporizador = setTimeout(fn, ms || 350); }

  // ---------------------------------------------------------------- centro
  function render() { renderLista(); renderCentro(); renderDireita(); }
  function barraSlide(s) {
    var b = el("div", "ed-tools");
    if (s.origem === "manual") {
      var g = el("div", "flex-grow-1"); g.appendChild(el("label", "form-label small fw-bold mb-1", "Título do slide"));
      var t = el("input", "form-control form-control-sm"); t.value = s.titulo || ""; t.maxLength = 100;
      t.addEventListener("input", function () { s.titulo = t.value; sujar(); renderLista(); }); g.appendChild(t); b.appendChild(g);
    } else if (s.tipo === "assunto") {
      var g2 = el("div", "flex-grow-1"); g2.appendChild(el("label", "form-label small fw-bold mb-1", "Título do assunto"));
      var t2 = el("input", "form-control form-control-sm"); t2.value = s.titulo || ""; t2.addEventListener("input", function () { s.titulo = t2.value; sujar(); renderLista(); }); g2.appendChild(t2); b.appendChild(g2);
    } else b.appendChild(Object.assign(el("div", "flex-grow-1 fw-semibold"), { innerHTML: '<i class="bi ' + iconeSlide(s) + ' me-2"></i>' + rotuloSlide(s) + ' <span class="badge text-bg-secondary ms-1">automático</span>' }));
    var d = el("div"); d.appendChild(el("label", "form-label small fw-bold mb-1", "Segundos"));
    var di = el("input", "form-control form-control-sm"); di.type = "number"; di.min = 5; di.max = 120; di.style.width = "90px"; di.placeholder = "padrão"; di.value = s.duracao || "";
    di.addEventListener("input", function () { s.duracao = di.value ? parseInt(di.value, 10) : null; sujar(); }); d.appendChild(di); b.appendChild(d);
    if (s.origem === "manual") {
      var m = el("div"); m.appendChild(el("label", "form-label small fw-bold mb-1", "Posicionamento"));
      var sel = el("select", "form-select form-select-sm"); sel.appendChild(new Option("Grade (encaixa)", "grade"));
      var lv = new Option("Livre (em breve)", "livre"); lv.disabled = true; sel.appendChild(lv); sel.value = "grade"; m.appendChild(sel); b.appendChild(m);
    } else {
      var p = el("button", "btn btn-primary btn-sm"); p.type = "button"; p.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Personalizar';
      p.title = "Transforma em slide manual, com os cards na disposição atual, para você ajustar"; p.addEventListener("click", personalizar); b.appendChild(p);
    }
    if (s._grupo) {
      var v = el("button", "btn btn-outline-secondary btn-sm"); v.type = "button"; v.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i>Voltar ao automático';
      v.addEventListener("click", voltarAuto); b.appendChild(v);
    }
    return b;
  }
  function destruirGrade() { if (grade) { try { grade.destroy(false); } catch (e) {} grade = null; } TelaoCards.destruir(); }

  function renderCentro() {
    var c = $("edCentro"), s = atual(); destruirGrade(); c.innerHTML = "";
    c.appendChild(barraSlide(s));
    if (s.origem === "manual") renderManual(c, s); else renderAuto(c, s);
  }

  // --- manual: grade
  function placeholder(it, msg) {
    var info = cardInfo[it.card_id], rot = info ? info.card.rotulo : it.card_id;
    return TelaoCards.painel({ titulo: rot, icone: "bi-hourglass-split", kind: "vazio", subtitulo: msg }, true);
  }
  function preencher(it) {
    if (!it._el) return;
    it._el.innerHTML = "";
    it._el.appendChild(it._conteudo ? TelaoCards.painel(it._conteudo, it.visual.titulo !== false) : placeholder(it, it._carregando ? "Carregando…" : "Sem dados no momento"));
  }
  function renderManual(c, s) {
    var frame = el("div", "tl tl-frame ed-frame"), g = el("div", "grid-stack"); frame.appendChild(g);
    s.itens.forEach(function (it) {
      var w = el("div", "grid-stack-item"), conteudo = el("div", "grid-stack-item-content"), info = cardInfo[it.card_id];
      w.setAttribute("gs-id", it._id); w.setAttribute("gs-x", it.pos.x); w.setAttribute("gs-y", it.pos.y); w.setAttribute("gs-w", it.pos.w); w.setAttribute("gs-h", it.pos.h);
      if (info) { w.setAttribute("gs-min-w", info.card.tam_min[0]); w.setAttribute("gs-min-h", info.card.tam_min[1]); }
      if (it._id === estado.itemSel) w.classList.add("sel");
      w.appendChild(conteudo); it._el = conteudo; g.appendChild(w);
    });
    c.appendChild(frame);
    if (!s.itens.length) {
      var v = el("div", "text-center text-muted small mt-2", "Slide vazio: escolha cards na paleta à direita (Módulo → Seção → Card), depois arraste e redimensione aqui.");
      c.appendChild(v);
    }
    var opcoes = { column: COL, maxRow: LIN, cellHeight: 60, margin: 3, float: true, animate: false, disableOneColumnMode: true, resizable: { handles: "e,se,s,sw,w" } };
    try { grade = GridStack.init(opcoes, g); }
    catch (e) { delete opcoes.maxRow; grade = GridStack.init(opcoes, g); }   // slide salvo com cards sobrepostos: abre mesmo assim
    var ajustar = function () { if (grade) grade.cellHeight(Math.max(20, Math.floor(frame.clientHeight / LIN))); };
    ajustar(); if (window.ResizeObserver) new ResizeObserver(ajustar).observe(frame);
    grade.on("change", function () {
      grade.engine.nodes.forEach(function (n) {
        var it = s.itens.filter(function (x) { return x._id === n.id; })[0]; if (it) it.pos = { x: n.x, y: n.y, w: n.w, h: n.h };
      }); sujar();
    });
    g.addEventListener("mousedown", function (e) { var w = e.target.closest(".grid-stack-item"); selecionarItem(w ? w.getAttribute("gs-id") : null); });
    s.itens.forEach(preencher);
    atualizarPrevia();
  }
  function selecionarItem(id) {
    if (estado.itemSel === id) return;
    estado.itemSel = id;
    document.querySelectorAll("#edCentro .grid-stack-item").forEach(function (w) { w.classList.toggle("sel", w.getAttribute("gs-id") === id); });
    renderDireita();
  }
  function atualizarPrevia() {
    var s = atual(), meu = ++reqPrevia;
    if (s.origem === "manual") {
      if (!s.itens.length) return;
      s.itens.forEach(function (i) { i._carregando = true; });
      post(D.urls.previa, { slide: limpo(s), resumo: !!estado.modelo.resumo }).then(function (r) {
        if (meu !== reqPrevia || !r.ok) return;
        TelaoCards.destruir();
        s.itens.forEach(function (it, k) { it._carregando = false; it._conteudo = (r.dados.itens || [])[k] || null; preencher(it); });
      });
    } else {
      s._carregando = true; post(D.urls.previa, { slide: limpo(s), resumo: !!estado.modelo.resumo }).then(function (r) {
        if (meu !== reqPrevia) return;
        s._carregando = false; s._previa = r.ok ? (r.dados.slides || []) : []; renderPreviaAuto();
      });
    }
  }
  function adicionarCard(id) {
    var s = atual(), info = cardInfo[id]; if (s.origem !== "manual" || !info) return;
    var vaga = acharVaga(s, info.card.tam_padrao, info.card.tam_min);
    if (!vaga) { alerta("Não há espaço livre neste slide para esse card. Reduza ou remova algum card, ou use outro slide.", "warning"); return; }
    alerta(null);
    var it = { _id: novoId(), card_id: id, pos: vaga, visual: { titulo: true, max_itens: null } };
    s.itens.push(it); estado.itemSel = it._id; sujar(); renderLista(); renderCentro(); renderDireita();
  }
  // Procura um espaço livre para o card, do tamanho padrão e, se não couber, encolhendo até o tamanho mínimo.
  function acharVaga(s, padrao, minimo) {
    function livre(x, y, w, h) {
      return !s.itens.some(function (i) { var p = i.pos; return x < p.x + p.w && x + w > p.x && y < p.y + p.h && y + h > p.y; });
    }
    for (var h = padrao[1]; h >= minimo[1]; h--) for (var w = padrao[0]; w >= minimo[0]; w--)
      for (var y = 0; y + h <= LIN; y++) for (var x = 0; x + w <= COL; x++) if (livre(x, y, w, h)) return { x: x, y: y, w: w, h: h };
    return null;
  }
  function removerItem(id) {
    var s = atual(); s.itens = s.itens.filter(function (i) { return i._id !== id; }); estado.itemSel = null; sujar(); renderLista(); renderCentro(); renderDireita();
  }

  // --- automático: prévia
  function renderAuto(c, s) {
    var frame = el("div", "tl tl-frame ed-frame ed-auto"), dentro = el("div", "ed-auto-in"); frame.appendChild(dentro); c.appendChild(frame);
    var legenda = el("div", "text-center text-muted small mt-2"); legenda.id = "edLegendaAuto"; c.appendChild(legenda);
    if (s.tipo === "assunto") c.appendChild(el("div", "alert alert-light border small mt-2 mb-0", "Assunto com itens de vários módulos. Use Personalizar para posicionar os cards livremente."));
    s._dentro = dentro; renderPreviaAuto(); if (!s._previa) atualizarPrevia();
  }
  function renderPreviaAuto() {
    var s = atual(); if (s.origem === "manual" || !s._dentro || !s._dentro.isConnected) return;
    TelaoCards.destruir(); s._dentro.innerHTML = "";
    var leg = $("edLegendaAuto"); leg.innerHTML = "";
    if (s._carregando && !s._previa) { s._dentro.appendChild(el("div", "vazio", "Carregando…")); return; }
    var lista = s._previa || [];
    if (!lista.length) { s._dentro.appendChild(el("div", "vazio", "Sem dados para este slide agora.")); return; }
    autoIdx = Math.min(autoIdx, lista.length - 1); var p = lista[autoIdx];
    s._dentro.appendChild(el("div", "ed-auto-t", p.titulo + (p.subtitulo ? " · " + p.subtitulo : "")));
    var corpo = el("div", "slide"); corpo.style.cssText = "flex:1;min-height:0;display:flex;flex-direction:column;position:relative"; corpo.appendChild(TelaoCards.slide(p)); s._dentro.appendChild(corpo);
    leg.appendChild(document.createTextNode("Gera " + lista.length + " slide(s) na apresentação · mostrando o " + (autoIdx + 1) + "º "));
    if (lista.length > 1) {
      var a = btn("bi-chevron-left", "Anterior", function () { autoIdx = (autoIdx + lista.length - 1) % lista.length; renderPreviaAuto(); });
      var b = btn("bi-chevron-right", "Próximo", function () { autoIdx = (autoIdx + 1) % lista.length; renderPreviaAuto(); }); leg.appendChild(a); leg.appendChild(b);
    }
  }
  function personalizar() {
    var s = atual(); alerta(null);
    post(D.urls.personalizar, { slide: limpo(s), resumo: !!estado.modelo.resumo }).then(function (r) {
      if (!r.ok) { alerta(r.dados.erro || "Não foi possível personalizar."); return; }
      var grupo = novoId("g"), novos = r.dados.slides.map(function (x) { var p = prep(x); p._grupo = grupo; p._auto = limpo(s); return p; });
      Array.prototype.splice.apply(estado.slides, [estado.sel, 1].concat(novos)); sujar(); selecionar(estado.sel);
    });
  }
  function voltarAuto() {
    var s = atual(), g = s._grupo, orig = s._auto; if (!g || !orig) return;
    var pos = estado.slides.map(function (x) { return x._grupo; }).indexOf(g);
    estado.slides = estado.slides.filter(function (x) { return x._grupo !== g; });
    estado.slides.splice(pos, 0, prep(orig)); sujar(); selecionar(pos);
  }

  // ---------------------------------------------------------------- direita
  function renderDireita() {
    var d = $("edDireita"); d.innerHTML = ""; var s = atual();
    if (s.origem === "manual") {
      var it = s.itens.filter(function (i) { return i._id === estado.itemSel; })[0];
      if (it) d.appendChild(propriedades(s, it));
      d.appendChild(paleta());
    } else if (s.tipo === "assunto") {
      d.appendChild(el("div", "text-muted small", "Os filtros dos blocos do assunto são mantidos. Para ajustar cards e posições, use Personalizar."));
    } else {
      var card = el("div", "card shadow-sm"), body = el("div", "card-body");
      body.appendChild(el("div", "small fw-bold text-uppercase text-muted mb-2", "Regras do módulo"));
      s.filtros = s.filtros || {};
      body.appendChild(formFiltros(s.provedor, s.filtros, [], function () { sujar(); s._previa = null; autoIdx = 0; depois(atualizarPrevia); }));
      card.appendChild(body); d.appendChild(card);
    }
  }
  function propriedades(s, it) {
    var info = cardInfo[it.card_id], card = el("div", "card shadow-sm mb-3 border-primary"), b = el("div", "card-body");
    b.appendChild(el("div", "small text-muted", info ? info.modulo.rotulo + " › " + info.secao.rotulo : ""));
    b.appendChild(el("div", "fw-bold mb-2", info ? info.card.rotulo : it.card_id));
    var f = el("div", "form-check mb-2"), t = el("input", "form-check-input"); t.type = "checkbox"; t.id = "edVisTit"; t.checked = it.visual.titulo !== false;
    t.addEventListener("change", function () { it.visual.titulo = t.checked; sujar(); preencher(it); });
    f.appendChild(t); f.appendChild(Object.assign(el("label", "form-check-label small", "Mostrar o título do card"), { htmlFor: "edVisTit" })); b.appendChild(f);
    if (info && ["tiles", "cards", "bars"].indexOf(info.card.forma) >= 0) {
      var g = el("div", "mb-2"); g.appendChild(el("label", "form-label small fw-bold mb-1", "Máximo de itens"));
      var n = el("input", "form-control form-control-sm"); n.type = "number"; n.min = 1; n.max = 50; n.placeholder = "todos"; n.value = it.visual.max_itens || "";
      n.addEventListener("input", function () { it.visual.max_itens = n.value ? parseInt(n.value, 10) : null; sujar(); depois(atualizarPrevia, 300); }); g.appendChild(n); b.appendChild(g);
    }
    if (info && info.card.instancia) {
      var gi = el("div", "mb-2"); gi.appendChild(el("label", "form-label small fw-bold mb-1", "Qual " + info.card.instancia + "?"));
      var sel = el("select", "form-select form-select-sm"); sel.appendChild(new Option("Carregando…", "")); gi.appendChild(sel); b.appendChild(gi);
      instancias(it).then(function (lista) {
        sel.innerHTML = ""; sel.appendChild(new Option("Primeiro disponível", ""));
        lista.forEach(function (x) { sel.appendChild(new Option(x, x)); });
        var ref = (it.params || {}).ref || ""; if (ref && lista.indexOf(ref) < 0) sel.appendChild(new Option(ref + " (indisponível agora)", ref)); sel.value = ref;
      });
      sel.addEventListener("change", function () { if (sel.value) it.params = { ref: sel.value }; else delete it.params; sujar(); atualizarPrevia(); });
    }
    var prov = it.card_id.split(".")[0], campos = (D.campos[prov] || []).filter(function (c) { return c.nome !== "cards" && c.nome !== "layout"; });
    if (campos.length) {
      var det = el("details", "mb-2"); det.appendChild(el("summary", "small fw-bold", "Filtros do módulo"));
      it.filtros = it.filtros || {};
      var fm = formFiltros(prov, it.filtros, ["cards", "layout"], function () { sujar(); delete instCache[it.card_id]; depois(atualizarPrevia); }); fm.className = "mt-2"; det.appendChild(fm); b.appendChild(det);
    }
    var rm = el("button", "btn btn-outline-danger btn-sm w-100"); rm.type = "button"; rm.innerHTML = '<i class="bi bi-trash me-1"></i>Remover card do slide';
    rm.addEventListener("click", function () { removerItem(it._id); }); b.appendChild(rm);
    card.appendChild(b); return card;
  }
  function instancias(it) {
    var chave = it.card_id; if (instCache[chave]) return instCache[chave];
    return instCache[chave] = fetch(D.urls.instancias + "?card_id=" + encodeURIComponent(it.card_id), { credentials: "same-origin" })
      .then(function (r) { return r.json(); }).then(function (j) { return j.instancias || []; }).catch(function () { return []; });
  }
  function paleta() {
    var card = el("div", "card shadow-sm ed-pal"), b = el("div", "card-body");
    b.appendChild(el("div", "small fw-bold text-uppercase text-muted mb-2", "Adicionar card ao slide"));
    D.catalogo.forEach(function (m) {
      var det = el("details", "mb-1"); var sm = el("summary"); sm.innerHTML = '<i class="bi ' + m.icone + ' me-2 text-primary"></i>' + m.rotulo; det.appendChild(sm);
      m.secoes.forEach(function (sec) {
        det.appendChild(el("div", "sec", sec.rotulo));
        sec.cards.forEach(function (c) {
          var bt = el("button", "btn btn-outline-secondary btn-card"); bt.type = "button";
          bt.innerHTML = '<i class="bi bi-plus-lg me-1"></i>' + c.rotulo + (c.instancia ? ' <span class="badge text-bg-light border">por ' + c.instancia + "</span>" : "");
          bt.addEventListener("click", function () { adicionarCard(c.id); }); det.appendChild(bt);
        });
      });
      b.appendChild(det);
    });
    card.appendChild(b); return card;
  }

  // ---------------------------------------------------------------- salvar
  function salvar() {
    alerta(null); var m = estado.modelo, bt = $("edSalvar"); bt.disabled = true;
    post(D.urls.salvar, { id: m.id, nome: m.nome, descricao: m.descricao, icone: m.icone, duracao_padrao: m.duracao_padrao, resumo: m.resumo,
                          compartilhada: m.compartilhada, ativo: m.ativo !== false, slides: limpo(estado.slides) }).then(function (r) {
      bt.disabled = false;
      if (!r.ok) { alerta(r.dados.erros || r.dados.erro || "Não foi possível salvar."); return; }
      var novo = !m.id; m.id = r.dados.id; estado.sujo = false; link(); alerta("Apresentação salva.", "success");
      if (novo && history.replaceState) history.replaceState(null, "", r.dados.url);
    }).catch(function () { bt.disabled = false; alerta("Falha de conexão ao salvar."); });
  }
  $("edSalvar").addEventListener("click", salvar);
  window.addEventListener("beforeunload", function (e) { if (estado.sujo) { e.preventDefault(); e.returnValue = ""; } });
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); salvar(); }
    else if (e.key === "Delete" && estado.itemSel && !/INPUT|SELECT|TEXTAREA/.test((e.target || {}).tagName || "")) removerItem(estado.itemSel);
  });

  lerConfig(); render();
})();

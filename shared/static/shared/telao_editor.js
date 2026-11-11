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
  function cols(s) { return (s.layout && s.layout.colunas) || COL; }
  function lins(s) { return (s.layout && s.layout.linhas) || LIN; }
  function esc(s, t) { return [Math.max(1, Math.round(t[0] * cols(s) / COL)), Math.max(1, Math.round(t[1] * lins(s) / LIN))]; }   // tamanho do card em células desta grade
  // Histórico (desfazer/refazer): foto do conjunto de slides depois de cada mudança (agrupa mudanças em sequência).
  var hist = [], hi = -1, tHist = null, restaurando = false;
  var SO_EDITOR = { _id: 1, _el: 1, _box: 1, _conteudo: 1, _carregando: 1, _previa: 1, _dentro: 1, _uid: 1 };
  function foto() { return JSON.stringify(estado.slides, function (k, v) { return SO_EDITOR[k] ? undefined : v; }); }
  function gravarFoto() {
    clearTimeout(tHist); tHist = null; var f = foto(); if (hist[hi] === f) return;
    hist = hist.slice(0, hi + 1); hist.push(f); if (hist.length > 60) hist.shift(); hi = hist.length - 1; botoesHist();
  }
  function sujar() { estado.sujo = true; if (restaurando) return; clearTimeout(tHist); tHist = setTimeout(gravarFoto, 400); }
  function botoesHist() { var u = $("edDesfazer"), r = $("edRefazer"); if (u) u.disabled = hi <= 0 && !tHist; if (r) r.disabled = hi >= hist.length - 1; }
  function irHist(d) {
    if (tHist) gravarFoto();
    var j = hi + d; if (j < 0 || j >= hist.length) return;
    hi = j; restaurando = true; estado.slides = JSON.parse(hist[hi]).map(prep);
    if (!estado.slides.length) estado.slides.push(novoManual());
    estado.sel = Math.min(estado.sel, estado.slides.length - 1); estado.itemSel = null; estado.sujo = true; restaurando = false;
    botoesHist(); render();
  }
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
  // grupo: "config" (como o card é mostrado), "filtro" (quais dados entram) ou ausente (todos). cardId limita as configurações ao card.
  function formFiltros(provedor, filtros, excluir, onChange, grupo, cardId) {
    var f = el("div");
    (D.campos[provedor] || []).forEach(function (c) {
      if (excluir.indexOf(c.nome) >= 0) return;
      if (grupo === "config" && (!c.config || (cardId && c.cards.indexOf(cardId) < 0))) return;
      if (grupo === "filtro" && c.config) return;
      f.appendChild(campoEl(c, filtros, onChange));
    });
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
      sel.appendChild(new Option("Livre (qualquer posição)", "livre")); sel.value = modo(s); sel.addEventListener("change", function () { converter(s, sel.value); });
      m.appendChild(sel); b.appendChild(m);
      if (modo(s) === "grade") {   // a grade pode ser redefinida: quantidade de caixas na horizontal e na vertical
        [["Colunas", "colunas", 24], ["Linhas", "linhas", 16]].forEach(function (k) {
          var g = el("div"); g.appendChild(el("label", "form-label small fw-bold mb-1", k[0]));
          var n = el("input", "form-control form-control-sm"); n.type = "number"; n.min = 1; n.max = k[2]; n.style.width = "75px"; n.value = k[1] === "colunas" ? cols(s) : lins(s);
          n.title = "Quantidade de caixas da grade na " + (k[1] === "colunas" ? "horizontal" : "vertical") + " (1 a " + k[2] + ")";
          n.addEventListener("change", function () {
            var v = Math.min(k[2], Math.max(1, parseInt(n.value, 10) || 1)); n.value = v;
            redefinirGrade(s, k[1] === "colunas" ? v : cols(s), k[1] === "linhas" ? v : lins(s));
          });
          g.appendChild(n); b.appendChild(g);
        });
      }
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
  function modo(s) { return (s.layout && s.layout.modo === "livre") ? "livre" : "grade"; }
  // O GridStack só traz CSS pronto para 12 colunas (e 2 a 11 no extra): para qualquer outra quantidade, gera as regras aqui.
  function cssColunas(n) {
    var st = $("edGsCss"); if (!st) { st = el("style"); st.id = "edGsCss"; document.head.appendChild(st); }
    if (n === 12) { st.textContent = ""; return; }
    var pc = function (v) { return (Math.round(v * 1000) / 1000) + "%"; }, r = ".gs-" + n + ">.grid-stack-item", css = r + "{width:" + pc(100 / n) + "}";
    for (var i = 1; i < n; i++) css += r + '[gs-x="' + i + '"]{left:' + pc(100 * i / n) + "}";
    for (var j = 2; j <= n; j++) css += r + '[gs-w="' + j + '"]{width:' + pc(100 * j / n) + "}";
    st.textContent = css;
  }
  // Muda a quantidade de colunas/linhas da grade: os cards mantêm a posição e o tamanho proporcionais.
  function redefinirGrade(s, c, l) {
    var oc = cols(s), ol = lins(s); if (c === oc && l === ol) return;
    s.layout = s.layout || { modo: "grade" }; s.layout.colunas = c; s.layout.linhas = l;
    s.itens.forEach(function (i) {
      var p = i.pos, x = Math.min(c - 1, Math.round(p.x * c / oc)), y = Math.min(l - 1, Math.round(p.y * l / ol));
      i.pos = { x: x, y: y, w: Math.min(c - x, Math.max(1, Math.round(p.w * c / oc))), h: Math.min(l - y, Math.max(1, Math.round(p.h * l / ol))) };
    });
    sujar(); renderCentro(); renderDireita();
  }
  function arred(v) { return Math.round(v * 100) / 100; }
  function converter(s, novo) {
    if (modo(s) === novo) return;
    if (!confirm(novo === "livre" ? "Passar para posicionamento livre? Os cards mantêm o lugar atual e passam a poder ficar em qualquer posição (e sobrepostos)."
                                  : "Passar para a grade? As posições serão arredondadas para as células e podem se sobrepor.")) { renderCentro(); return; }
    s.layout = s.layout || { colunas: COL, linhas: LIN }; var C = cols(s), L = lins(s); s.layout.modo = novo;
    s.itens.forEach(function (i) {
      var p = i.pos;
      if (novo === "livre") i.pos = { x: arred(p.x / C * 100), y: arred(p.y / L * 100), w: arred(p.w / C * 100), h: arred(p.h / L * 100) };
      else {
        var x = Math.min(C - 1, Math.max(0, Math.round(p.x / 100 * C))), y = Math.min(L - 1, Math.max(0, Math.round(p.y / 100 * L)));
        i.pos = { x: x, y: y, w: Math.min(C - x, Math.max(1, Math.round(p.w / 100 * C))), h: Math.min(L - y, Math.max(1, Math.round(p.h / 100 * L))) };
      }
    });
    sujar(); renderCentro(); renderDireita();
  }
  function destruirGrade() { if (grade) { try { grade.destroy(false); } catch (e) {} grade = null; } TelaoCards.destruir(); }

  function renderCentro() {
    var c = $("edCentro"), s = atual(); destruirGrade(); c.innerHTML = "";
    c.appendChild(barraSlide(s));
    if (s.origem === "manual") { if (modo(s) === "livre") renderLivre(c, s); else renderManual(c, s); } else renderAuto(c, s);
  }

  // --- manual: posição livre (arrastar e redimensionar em % do slide, com ímã de 1%; Alt desliga o ímã)
  var ALCAS = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
  function estilo(it) {
    var b = it._box, p = it.pos; if (!b) return;
    b.style.left = p.x + "%"; b.style.top = p.y + "%"; b.style.width = p.w + "%"; b.style.height = p.h + "%";
  }
  function minimoPct(it) { var i = cardInfo[it.card_id], m = i ? i.card.tam_min : [2, 1]; return { w: m[0] / COL * 100, h: m[1] / LIN * 100 }; }
  function renderLivre(c, s) {
    var frame = el("div", "tl tl-frame ed-frame ed-livre");
    s.itens.forEach(function (it) {
      var box = el("div", "ed-livre-item" + (it._id === estado.itemSel ? " sel" : "")), conteudo = el("div", "ed-livre-content");
      box.setAttribute("gs-id", it._id); box.appendChild(conteudo);
      ALCAS.forEach(function (a) { var h = el("div", "ed-h ed-h-" + a); h.setAttribute("data-h", a); box.appendChild(h); });
      it._box = box; it._el = conteudo; estilo(it); frame.appendChild(box);
      box.addEventListener("pointerdown", function (e) { iniciarArraste(e, s, it, frame); });
    });
    frame.addEventListener("pointerdown", function (e) { if (e.target === frame) selecionarItem(null); });
    c.appendChild(frame);
    c.appendChild(el("div", "text-center text-muted small mt-2", s.itens.length
      ? "Arraste para mover, use as alças para redimensionar (Alt = sem ímã). Os cards mais abaixo na lista ficam por cima."
      : "Slide vazio: escolha cards na paleta à direita e posicione onde quiser."));
    s.itens.forEach(preencher); atualizarPrevia();
  }
  function alvosEixo(s, it, eixo) {
    var a = [0, 50, 100];
    s.itens.forEach(function (o) {
      if (o === it) return; var p = o.pos;
      if (eixo === "x") a.push(p.x, p.x + p.w, p.x + p.w / 2); else a.push(p.y, p.y + p.h, p.y + p.h / 2);
    });
    return a;
  }
  function ima(vals, alvos, lim) {
    var best = null;
    vals.forEach(function (v) { alvos.forEach(function (a) { var d = a - v; if (Math.abs(d) <= lim && (!best || Math.abs(d) < Math.abs(best.d))) best = { d: d, g: a }; }); });
    return best;
  }
  function iniciarArraste(e, s, it, frame) {
    if (e.button !== 0) return;
    var alca = e.target.getAttribute && e.target.getAttribute("data-h");
    selecionarItem(it._id);
    var r = frame.getBoundingClientRect(), p0 = { x: it.pos.x, y: it.pos.y, w: it.pos.w, h: it.pos.h }, x0 = e.clientX, y0 = e.clientY, mn = minimoPct(it), moveu = false;
    var box = it._box; try { box.setPointerCapture(e.pointerId); } catch (x) {}
    var gv = el("div", "ed-guia ed-guia-v"), gh = el("div", "ed-guia ed-guia-h"), AX = alvosEixo(s, it, "x"), AY = alvosEixo(s, it, "y"), LIM = 1.2;
    frame.appendChild(gv); frame.appendChild(gh);
    function passo(v, alt) { return alt ? arred(v) : Math.round(v); }
    function mover(ev) {
      var dx = (ev.clientX - x0) / r.width * 100, dy = (ev.clientY - y0) / r.height * 100, a = ev.altKey, n = { x: p0.x, y: p0.y, w: p0.w, h: p0.h };
      if (!alca) { n.x = Math.min(100 - p0.w, Math.max(0, passo(p0.x + dx, a))); n.y = Math.min(100 - p0.h, Math.max(0, passo(p0.y + dy, a))); }
      else {
        var dE = alca.indexOf("e") >= 0, dW = alca.indexOf("w") >= 0, dN = alca.indexOf("n") >= 0, dS = alca.indexOf("s") >= 0;
        if (dE) n.w = Math.min(100 - p0.x, Math.max(mn.w, passo(p0.x + p0.w + dx, a) - p0.x));
        if (dW) { var nx = Math.min(p0.x + p0.w - mn.w, Math.max(0, passo(p0.x + dx, a))); n.x = nx; n.w = p0.x + p0.w - nx; }
        if (dS) n.h = Math.min(100 - p0.y, Math.max(mn.h, passo(p0.y + p0.h + dy, a) - p0.y));
        if (dN) { var ny = Math.min(p0.y + p0.h - mn.h, Math.max(0, passo(p0.y + dy, a))); n.y = ny; n.h = p0.y + p0.h - ny; }
      }
      var guiaX = null, guiaY = null;
      if (!a) {   // ímã nas bordas/centro dos outros cards e do slide
        if (!alca) {
          var mx = ima([n.x, n.x + n.w, n.x + n.w / 2], AX, LIM), my = ima([n.y, n.y + n.h, n.y + n.h / 2], AY, LIM);
          if (mx) { n.x = Math.min(100 - n.w, Math.max(0, n.x + mx.d)); guiaX = mx.g; }
          if (my) { n.y = Math.min(100 - n.h, Math.max(0, n.y + my.d)); guiaY = my.g; }
        } else {
          if (alca.indexOf("e") >= 0) { var ie = ima([n.x + n.w], AX, LIM); if (ie) { n.w = Math.min(100 - n.x, Math.max(mn.w, n.w + ie.d)); guiaX = ie.g; } }
          if (alca.indexOf("w") >= 0) { var iw = ima([n.x], AX, LIM); if (iw) { var nx2 = Math.min(p0.x + p0.w - mn.w, Math.max(0, n.x + iw.d)); n.w += n.x - nx2; n.x = nx2; guiaX = iw.g; } }
          if (alca.indexOf("s") >= 0) { var is = ima([n.y + n.h], AY, LIM); if (is) { n.h = Math.min(100 - n.y, Math.max(mn.h, n.h + is.d)); guiaY = is.g; } }
          if (alca.indexOf("n") >= 0) { var inn = ima([n.y], AY, LIM); if (inn) { var ny2 = Math.min(p0.y + p0.h - mn.h, Math.max(0, n.y + inn.d)); n.h += n.y - ny2; n.y = ny2; guiaY = inn.g; } }
        }
      }
      gv.style.display = guiaX === null ? "none" : "block"; if (guiaX !== null) gv.style.left = guiaX + "%";
      gh.style.display = guiaY === null ? "none" : "block"; if (guiaY !== null) gh.style.top = guiaY + "%";
      n.x = arred(n.x); n.y = arred(n.y); n.w = arred(n.w); n.h = arred(n.h);
      if (n.x !== it.pos.x || n.y !== it.pos.y || n.w !== it.pos.w || n.h !== it.pos.h) { it.pos = n; moveu = true; estilo(it); }
    }
    function fim() {
      box.removeEventListener("pointermove", mover); box.removeEventListener("pointerup", fim); box.removeEventListener("pointercancel", fim);
      gv.remove(); gh.remove();
      if (moveu) { sujar(); renderDireita(); }
    }
    box.addEventListener("pointermove", mover); box.addEventListener("pointerup", fim); box.addEventListener("pointercancel", fim);
    e.preventDefault();
  }

  // --- manual: grade
  function placeholder(it, msg) {
    var info = cardInfo[it.card_id], rot = info ? info.card.rotulo : it.card_id;
    return TelaoCards.painel({ titulo: rot, icone: "bi-hourglass-split", kind: "vazio", subtitulo: msg }, true);
  }
  function preencher(it) {
    if (!it._el) return;
    it._el.innerHTML = "";
    it._el.appendChild(it._conteudo ? TelaoCards.painel(it._conteudo, it.visual.titulo !== false, it.visual.moldura === "sem", it.visual.subtitulo !== false) : placeholder(it, it._carregando ? "Carregando…" : "Sem dados no momento"));
  }
  function renderManual(c, s) {
    var frame = el("div", "tl tl-frame ed-frame"), g = el("div", "grid-stack"); frame.appendChild(g);
    s.itens.forEach(function (it) {
      var w = el("div", "grid-stack-item"), conteudo = el("div", "grid-stack-item-content"), info = cardInfo[it.card_id];
      w.setAttribute("gs-id", it._id); w.setAttribute("gs-x", it.pos.x); w.setAttribute("gs-y", it.pos.y); w.setAttribute("gs-w", it.pos.w); w.setAttribute("gs-h", it.pos.h);
      if (info) { var mn = esc(s, info.card.tam_min); w.setAttribute("gs-min-w", mn[0]); w.setAttribute("gs-min-h", mn[1]); }
      if (it._id === estado.itemSel) w.classList.add("sel");
      w.appendChild(conteudo); it._el = conteudo; g.appendChild(w);
    });
    c.appendChild(frame);
    if (!s.itens.length) {
      var v = el("div", "text-center text-muted small mt-2", "Slide vazio: escolha cards na paleta à direita (Módulo → Seção → Card), depois arraste e redimensione aqui.");
      c.appendChild(v);
    }
    frame.style.backgroundSize = "calc(100% / " + cols(s) + ") calc(100% / " + lins(s) + ")";
    cssColunas(cols(s));
    var opcoes = { column: cols(s), maxRow: lins(s), cellHeight: 60, margin: 3, float: true, animate: false, disableOneColumnMode: true, resizable: { handles: "e,se,s,sw,w" } };
    try { grade = GridStack.init(opcoes, g); }
    catch (e) { delete opcoes.maxRow; grade = GridStack.init(opcoes, g); }   // slide salvo com cards sobrepostos: abre mesmo assim
    var ajustar = function () { if (grade) grade.cellHeight(Math.max(10, Math.floor(frame.clientHeight / lins(s)))); };
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
    document.querySelectorAll("#edCentro .grid-stack-item, #edCentro .ed-livre-item").forEach(function (w) { w.classList.toggle("sel", w.getAttribute("gs-id") === id); });
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
    var livre = modo(s) === "livre", vaga = livre ? acharVagaLivre(s, info.card.tam_padrao, info.card.tam_min) : acharVaga(s, info.card.tam_padrao, info.card.tam_min);
    if (!vaga) { alerta("Não há espaço livre neste slide para esse card. Reduza ou remova algum card, ou use outro slide.", "warning"); return; }
    alerta(null);
    var it = { _id: novoId(), card_id: id, pos: vaga, visual: { titulo: true, max_itens: null } };
    s.itens.push(it); estado.itemSel = it._id; sujar(); renderLista(); renderCentro(); renderDireita();
  }
  // Procura um espaço livre para o card, do tamanho padrão e, se não couber, encolhendo até o tamanho mínimo.
  function acharVaga(s, padrao, minimo) {
    padrao = esc(s, padrao); minimo = esc(s, minimo); minimo = [Math.min(minimo[0], padrao[0]), Math.min(minimo[1], padrao[1])];
    var C = cols(s), L = lins(s);
    padrao = [Math.min(padrao[0], C), Math.min(padrao[1], L)]; minimo = [Math.min(minimo[0], C), Math.min(minimo[1], L)];
    function livre(x, y, w, h) {
      return !s.itens.some(function (i) { var p = i.pos; return x < p.x + p.w && x + w > p.x && y < p.y + p.h && y + h > p.y; });
    }
    for (var h = padrao[1]; h >= minimo[1]; h--) for (var w = padrao[0]; w >= minimo[0]; w--)
      for (var y = 0; y + h <= L; y++) for (var x = 0; x + w <= C; x++) if (livre(x, y, w, h)) return { x: x, y: y, w: w, h: h };
    return null;
  }
  // Posição livre: procura um lugar vazio (passos de 2,5%); se não houver, cascateia sobre os cards existentes.
  function acharVagaLivre(s, padrao, minimo) {
    function livre(x, y, w, h) {
      return !s.itens.some(function (i) { var p = i.pos; return x < p.x + p.w - .01 && x + w > p.x + .01 && y < p.y + p.h - .01 && y + h > p.y + .01; });
    }
    for (var h = padrao[1]; h >= minimo[1]; h--) for (var w = padrao[0]; w >= minimo[0]; w--) {
      var pw = w / COL * 100, ph = h / LIN * 100;
      for (var y = 0; y + ph <= 100.01; y += 2.5) for (var x = 0; x + pw <= 100.01; x += 2.5) if (livre(x, y, pw, ph)) return { x: arred(x), y: arred(y), w: arred(pw), h: arred(ph) };
    }
    var d = (s.itens.length * 3) % 30, w2 = padrao[0] / COL * 100, h2 = padrao[1] / LIN * 100;
    return { x: arred(Math.min(d, 100 - w2)), y: arred(Math.min(d, 100 - h2)), w: arred(w2), h: arred(h2) };
  }
  function removerItem(id) {
    var s = atual(); s.itens = s.itens.filter(function (i) { return i._id !== id; }); estado.itemSel = null; sujar(); renderLista(); renderCentro(); renderDireita();
  }

  // --- automático: prévia
  function renderAuto(c, s) {
    var frame = el("div", "tl tl-frame ed-frame ed-auto"), dentro = el("div", "ed-auto-in"); frame.appendChild(dentro); c.appendChild(frame);
    var legenda = el("div", "text-center text-muted small mt-2"); legenda.id = "edLegendaAuto"; c.appendChild(legenda);
    if (s.tipo === "assunto") c.appendChild(el("div", "alert alert-light border small mt-2 mb-0", "Assunto com blocos de vários módulos: ajuste os blocos à direita. Use Personalizar para posicionar os cards livremente."));
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
      d.appendChild(blocosAssunto(s));
    } else {
      var card = el("div", "card shadow-sm"), body = el("div", "card-body");
      body.appendChild(el("div", "small fw-bold text-uppercase text-muted mb-2", "Regras do módulo"));
      s.filtros = s.filtros || {};
      var mudou = function () { sujar(); s._previa = null; autoIdx = 0; depois(atualizarPrevia); };
      var cfg = formFiltros(s.provedor, s.filtros, [], mudou, "config");
      if (cfg.children.length) { body.appendChild(el("div", "small fw-bold mb-1", "Configurações de exibição")); body.appendChild(cfg); }
      var flt = formFiltros(s.provedor, s.filtros, [], mudou, "filtro");
      if (flt.children.length) { body.appendChild(el("div", "small fw-bold mt-3 mb-1", "Filtros dos dados")); body.appendChild(flt); }
      card.appendChild(body); d.appendChild(card);
    }
  }
  function blocosAssunto(s) {
    var card = el("div", "card shadow-sm"), body = el("div", "card-body");
    body.appendChild(el("div", "small fw-bold text-uppercase text-muted mb-2", "Blocos do assunto"));
    s.blocos = s.blocos || [];
    function mudou() { sujar(); s._previa = null; autoIdx = 0; depois(atualizarPrevia); }
    s.blocos.forEach(function (bl, i) {
      var linha = el("div", "border rounded p-2 mb-2"), topo = el("div", "d-flex align-items-center gap-1");
      topo.appendChild(Object.assign(el("div", "flex-grow-1 fw-semibold small"), { innerHTML: '<i class="bi ' + (D.rotulos[bl.provedor] || [0, "bi-display"])[1] + ' me-1"></i>' + (D.rotulos[bl.provedor] || [bl.provedor])[0] }));
      topo.appendChild(btn("bi-arrow-up", "Subir", function () { if (i > 0) { s.blocos.splice(i - 1, 0, s.blocos.splice(i, 1)[0]); mudou(); renderDireita(); } }));
      topo.appendChild(btn("bi-arrow-down", "Descer", function () { if (i < s.blocos.length - 1) { s.blocos.splice(i + 1, 0, s.blocos.splice(i, 1)[0]); mudou(); renderDireita(); } }));
      topo.appendChild(btn("bi-trash", "Remover bloco", function () { if (s.blocos.length < 2) { alerta("O assunto precisa de ao menos um bloco.", "warning"); return; } s.blocos.splice(i, 1); mudou(); renderDireita(); }, "text-danger"));
      linha.appendChild(topo);
      if ((D.campos[bl.provedor] || []).length) {
        var det = el("details", "mt-1"); det.appendChild(el("summary", "small", "Filtros")); bl.filtros = bl.filtros || {};
        var f = formFiltros(bl.provedor, bl.filtros, ["layout"], mudou); f.className = "mt-2"; det.appendChild(f); linha.appendChild(det);
      }
      body.appendChild(linha);
    });
    var add = el("select", "form-select form-select-sm"); add.appendChild(new Option("+ Adicionar bloco…", ""));
    Object.keys(D.rotulos).forEach(function (k) { add.appendChild(new Option(D.rotulos[k][0], k)); });
    add.addEventListener("change", function () { if (!add.value) return; s.blocos.push({ provedor: add.value, filtros: {} }); mudou(); renderDireita(); });
    body.appendChild(add); card.appendChild(body); return card;
  }
  function propriedades(s, it) {
    var info = cardInfo[it.card_id], card = el("div", "card shadow-sm mb-3 border-primary"), b = el("div", "card-body");
    b.appendChild(el("div", "small text-muted", info ? info.modulo.rotulo + " › " + info.secao.rotulo : ""));
    b.appendChild(el("div", "fw-bold mb-2", info ? info.card.rotulo : it.card_id));
    var f = el("div", "form-check mb-2"), t = el("input", "form-check-input"); t.type = "checkbox"; t.id = "edVisTit"; t.checked = it.visual.titulo !== false;
    t.addEventListener("change", function () { it.visual.titulo = t.checked; sujar(); preencher(it); });
    f.appendChild(t); f.appendChild(Object.assign(el("label", "form-check-label small", "Mostrar o título do card"), { htmlFor: "edVisTit" })); b.appendChild(f);
    var fs = el("div", "form-check mb-2"), ts = el("input", "form-check-input"); ts.type = "checkbox"; ts.id = "edVisSub"; ts.checked = it.visual.subtitulo !== false;
    ts.addEventListener("change", function () { if (ts.checked) delete it.visual.subtitulo; else it.visual.subtitulo = false; sujar(); preencher(it); });
    fs.appendChild(ts); fs.appendChild(Object.assign(el("label", "form-check-label small", "Mostrar o subtítulo do card"), { htmlFor: "edVisSub" })); b.appendChild(fs);
    var fm0 = el("div", "form-check mb-2"), mo = el("input", "form-check-input"); mo.type = "checkbox"; mo.id = "edVisMol"; mo.checked = it.visual.moldura !== "sem";
    mo.addEventListener("change", function () { if (mo.checked) delete it.visual.moldura; else it.visual.moldura = "sem"; sujar(); preencher(it); });
    fm0.appendChild(mo); fm0.appendChild(Object.assign(el("label", "form-check-label small", "Mostrar a moldura (fundo e borda do card)"), { htmlFor: "edVisMol" })); b.appendChild(fm0);
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
    var prov = it.card_id.split(".")[0]; it.filtros = it.filtros || {};
    var aoMudar = function () { sujar(); delete instCache[it.card_id]; depois(atualizarPrevia); };
    var cfg = formFiltros(prov, it.filtros, ["cards", "layout"], aoMudar, "config", it.card_id);
    if (cfg.children.length) {   // como o card é mostrado: período, tipo de gráfico, o que exibir
      var dc = el("details", "mb-2"); dc.open = true; dc.appendChild(el("summary", "small fw-bold", "Configurações do card")); cfg.className = "mt-2"; dc.appendChild(cfg); b.appendChild(dc);
    }
    var flt = formFiltros(prov, it.filtros, ["cards", "layout"], aoMudar, "filtro", it.card_id);
    if (flt.children.length) {   // quais dados entram: indicadores, setores...
      var df = el("details", "mb-2"); df.appendChild(el("summary", "small fw-bold", "Filtros dos dados")); flt.className = "mt-2"; df.appendChild(flt); b.appendChild(df);
    }
    if (modo(s) === "livre") {
      var gp = el("div", "mb-2"); gp.appendChild(el("div", "small fw-bold mb-1", "Posição e tamanho (% do slide)"));
      var lin = el("div", "d-flex gap-1");
      [["x", "X"], ["y", "Y"], ["w", "Larg."], ["h", "Alt."]].forEach(function (k) {
        var col = el("div", "flex-fill"), rt = el("div", "text-muted", k[1]); rt.style.fontSize = ".7rem"; col.appendChild(rt);
        var n = el("input", "form-control form-control-sm px-1"); n.type = "number"; n.step = "0.5"; n.min = 0; n.max = 100; n.value = it.pos[k[0]]; n.setAttribute("data-k", k[0]);
        n.addEventListener("input", function () {
          var v = parseFloat(n.value); if (isNaN(v)) return; var p = it.pos, mn = minimoPct(it);
          if (k[0] === "x") p.x = Math.min(Math.max(v, 0), 100 - p.w); else if (k[0] === "y") p.y = Math.min(Math.max(v, 0), 100 - p.h);
          else if (k[0] === "w") p.w = Math.min(Math.max(v, mn.w), 100 - p.x); else p.h = Math.min(Math.max(v, mn.h), 100 - p.y);
          estilo(it); sujar();
        });
        col.appendChild(n); lin.appendChild(col);
      });
      gp.appendChild(lin);
      var cam = el("div", "d-flex gap-1 mt-2");
      var fr = el("button", "btn btn-outline-secondary btn-sm flex-fill"); fr.type = "button"; fr.innerHTML = '<i class="bi bi-layer-forward me-1"></i>Para frente';
      var tr = el("button", "btn btn-outline-secondary btn-sm flex-fill"); tr.type = "button"; tr.innerHTML = '<i class="bi bi-layer-backward me-1"></i>Para trás';
      fr.addEventListener("click", function () { camada(s, it, 1); }); tr.addEventListener("click", function () { camada(s, it, -1); });
      cam.appendChild(fr); cam.appendChild(tr); gp.appendChild(cam); b.appendChild(gp);
    }
    var rm = el("button", "btn btn-outline-danger btn-sm w-100"); rm.type = "button"; rm.innerHTML = '<i class="bi bi-trash me-1"></i>Remover card do slide';
    rm.addEventListener("click", function () { removerItem(it._id); }); b.appendChild(rm);
    card.appendChild(b); return card;
  }
  function camada(s, it, d) {
    var i = s.itens.indexOf(it), j = i + d; if (j < 0 || j >= s.itens.length) return;
    s.itens.splice(i, 1); s.itens.splice(j, 0, it); sujar(); renderCentro(); renderDireita();
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
    var campo = /INPUT|SELECT|TEXTAREA/.test((e.target || {}).tagName || "");
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); salvar(); }
    else if ((e.ctrlKey || e.metaKey) && !campo && (e.key === "z" || e.key === "Z")) { e.preventDefault(); irHist(e.shiftKey ? 1 : -1); }
    else if ((e.ctrlKey || e.metaKey) && !campo && (e.key === "y" || e.key === "Y")) { e.preventDefault(); irHist(1); }
    else if (e.key === "Delete" && estado.itemSel && !/INPUT|SELECT|TEXTAREA/.test((e.target || {}).tagName || "")) removerItem(estado.itemSel);
  });

  lerConfig(); render(); gravarFoto(); botoesHist();
  $("edDesfazer").addEventListener("click", function () { irHist(-1); });
  $("edRefazer").addEventListener("click", function () { irHist(1); });
})();

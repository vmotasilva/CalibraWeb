/* Renderer dos cards do Modo Apresentação (player e editor). Requer Chart.js e telao_cards.css; o container pai deve ter a classe .tl.
   TelaoCards.slide(s) devolve o elemento do slide (tiles/cards/bars/chart/pagina/layout/vazio); TelaoCards.destruir() libera os gráficos. */
window.TelaoCards = (function () {
  var charts = [], paginados = [];   // api.pagMs: quanto cada página fica na tela (o player usa a duração do slide)
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function tom(t) { return t || "neutro"; }

  // Lista de cards que não cabe na altura: tenta reduzir a fonte (até 70%) e, se ainda assim sobrar, divide em páginas
  // que se alternam dentro do card (cada página com o máximo de cards que cabe), com o indicador "pág. 1/N".
  function encaixar(g, auto) {
    var timer = null;
    function paginas(cx, itens, k) {   // quantos cards cabem por página, em ordem
      g.style.fontSize = k + "em";
      var pgs = [], i = 0;
      while (i < itens.length) {
        itens.forEach(function (c) { c.style.display = "none"; });
        var n = 0;
        while (i + n < itens.length) {
          itens[i + n].style.display = "";
          if (g.offsetHeight > cx.clientHeight + 1 && n > 0) { itens[i + n].style.display = "none"; break; }
          n++;
        }
        pgs.push(itens.slice(i, i + n)); i += n;
      }
      return pgs;
    }
    function colunas(c) { g.classList.toggle("multi", c > 1); g.style.setProperty("--nc", c); }
    function ajustar() {
      var cx = g.closest(".cx"); if (!cx || !g.isConnected) return;
      clearTimeout(timer);
      var itens = [].slice.call(g.children), old = cx.querySelector(".tpag"); if (old) old.remove();
      var pgs = null, usado = 1, nc = [1];
      if (auto) nc = [1, 2, 3, 4];   // automático: o menor número de colunas que cabe na maior fonte; senão, o que gera menos páginas
      var melhor = null;
      [1, .85, .7].some(function (k) {
        return nc.some(function (c) {
          colunas(c); var p = paginas(cx, itens, k);
          if (!melhor || p.length < melhor.p.length) melhor = { p: p, k: k, c: c };
          return p.length === 1;
        });
      });
      pgs = melhor.p; usado = melhor.k; colunas(melhor.c);
      g._pgs = pgs.length; if (paginados.indexOf(g) < 0) paginados.push(g);
      g.style.fontSize = usado + "em";
      if (pgs.length <= 1) { itens.forEach(function (c) { c.style.display = ""; }); return; }
      var ind = el("div", "tpag"), atual = 0;
      cx.appendChild(ind);
      function mostrar() {
        itens.forEach(function (c) { c.style.display = "none"; });
        pgs[atual].forEach(function (c) { c.style.display = ""; });
        ind.textContent = "pág. " + (atual + 1) + "/" + pgs.length;
      }
      mostrar();
      (function tique() {
        timer = setTimeout(function () {
          if (!g.isConnected) return;
          if (!api.manual) { atual = (atual + 1) % pgs.length; mostrar(); }   // no manual, quem passa as páginas é o usuário
          tique();
        }, api.pagMs);
      })();
      g._mover = function (d) { var n = atual + d; if (n < 0 || n >= pgs.length) return false; atual = n; mostrar(); return true; };
    }
    setTimeout(function () {
      if (!g.isConnected) return;
      ajustar();
      var cx = g.closest(".cx"); if (cx && window.ResizeObserver) new ResizeObserver(ajustar).observe(cx);
    }, 30);
  }

  // Barras em colunas automáticas: o menor número de colunas (1 a 4) em que todas as linhas cabem na altura do card.
  function barrasAuto(g, n) {
    function ajustar() {
      if (!g.isConnected) return;
      for (var c = 1; c <= 4; c++) {
        g.classList.toggle("multi", c > 1); g.style.setProperty("--nc", c); g.style.setProperty("--nl", Math.ceil(n / c));
        if (g.scrollHeight <= g.clientHeight + 1) break;
      }
    }
    setTimeout(function () {
      ajustar(); var cx = g.closest(".cx"); if (cx && window.ResizeObserver) new ResizeObserver(ajustar).observe(cx);
    }, 30);
  }

  var desenho = {
    tiles: function (s) {
      var g = el("div", "tiles" + (s.itens.length > 8 ? " compacto" : ""));
      var anterior = null;
      s.itens.forEach(function (i) {
        if (anterior && i.grupo && i.grupo !== anterior) g.appendChild(el("div", "tsep"));   // quebra entre a situação geral e os indicadores
        if (i.grupo) anterior = i.grupo;
        var t = el("div", "tile " + tom(i.tom));
        t.appendChild(el("div", "v", i.valor)); t.appendChild(el("div", "r", i.rotulo));
        if (i.nota) t.appendChild(el("div", "n", i.nota));
        g.appendChild(t);
      });
      return g;
    },
    cards: function (s) {
      var auto = s.colunas === "auto", g = el("div", "tcards" + (s.colunas > 1 ? " multi" : ""));
      if (s.colunas > 1) g.style.setProperty("--nc", s.colunas);
      s.itens.forEach(function (i) {
        var c = el("div", "tcard " + tom(i.tom)); c.appendChild(el("h3", null, i.titulo));
        if (i.texto) c.appendChild(el("div", "tx", i.texto));
        var tg = el("div", "ttags"); (i.tags || []).forEach(function (x) { if (x) tg.appendChild(el("span", "ttag", x)); });
        c.appendChild(tg);
        (i.comentarios || []).forEach(function (m) {
          var q = el("div", "cm"); q.appendChild(el("b", null, m.autor + " · " + m.quando)); q.appendChild(el("span", null, " " + m.texto)); c.appendChild(q);
        });
        g.appendChild(c);
      });
      encaixar(g, auto);
      return g;
    },
    bars: function (s) {
      var g = el("div", "bars" + (s.sem_barra ? " sem-barra" : "") + (s.texto_prioritario ? " texto-prio" : "") + (s.colunas > 1 ? " multi" : ""));
      if (s.colunas === "auto") barrasAuto(g, s.itens.length);
      if (s.colunas > 1) { g.style.setProperty("--nc", s.colunas); g.style.setProperty("--nl", Math.ceil(s.itens.length / s.colunas)); }
      s.itens.forEach(function (i) {
        var r = el("div", "brow " + tom(i.tom)); var l = el("div", "l", i.rotulo); if (i.sub) l.appendChild(el("small", "sub", i.sub)); r.appendChild(l);
        if (!s.sem_barra) { var t = el("div", "t"), b = el("span"); b.style.width = Math.max(2, Math.min(100, i.pct)) + "%"; t.appendChild(b); r.appendChild(t); }
        r.appendChild(el("div", "p", i.txt)); g.appendChild(r);
      });
      return g;
    },
    chart: function (s) {
      var w = el("div", "grafico"), cv = el("canvas"); w.appendChild(cv);
      setTimeout(function () {
        if (!cv.isConnected) return;   // o slide já foi trocado
        var u = s.unidade || "";
        var fmt = function (v) { return Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + u; };
        // Rótulos de valor em cada ponto (e o valor da meta na ponta da linha tracejada).
        var cs = getComputedStyle(w), V = function (n, d) { return (cs.getPropertyValue(n) || "").trim() || d; };   // cores do tema (escuro/claro)
        var base = function () { return parseFloat(getComputedStyle(w).fontSize) || 18; };   // fonte base do container (.cxi)
        var tf = Math.round(base() * .65), ating = s.atingiu || null, VERDE = "#22c55e", VERM = "#ef4444";
        var rotulos = { id: "rotulos", afterDatasetsDraw: function (c) {
          var x = c.ctx; x.save(); x.textAlign = "center"; x.font = "700 " + Math.round(base() * .75) + "px Inter, sans-serif";
          c.data.datasets.forEach(function (ds, di) {
            if (ds.empilhada) return;                                         // fatias empilhadas: valores só na dica
            var meta = c.getDatasetMeta(di), ehMeta = !!ds.ehMeta;
            meta.data.forEach(function (pt, i) {
              if (ehMeta && i !== meta.data.length - 1) return;               // meta: só no último ponto
              var v = ds.data[i]; if (v == null) return;
              var abaixo = ehMeta || pt.y < c.chartArea.top + 34;
              x.fillStyle = ehMeta ? V("--metac", "#cbd5e1") : V("--rotulo", "#ffffff");
              if (!ehMeta && ating) x.fillStyle = ating[i] ? V("--okt", "#4ade80") : V("--crit-t", "#f87171");
              x.textBaseline = abaixo ? "top" : "bottom";
              var tx = (ehMeta ? "Meta " : "") + fmt(v);
              var px = Math.min(Math.max(pt.x, c.chartArea.left + 30), c.chartArea.right - 40);
              x.lineWidth = 5; x.strokeStyle = V("--card", "#131c31"); x.strokeText(tx, px, pt.y + (abaixo ? 12 : -12));
              x.fillText(tx, px, pt.y + (abaixo ? 12 : -12));
            });
          });
          x.restore();
        } };
        var tipo = s.tipo || "linha", PALETA = ["#60a5fa", "#f59e0b", "#a78bfa", "#2dd4bf", "#f472b6", "#84cc16", "#fb923c", "#38bdf8"], datasets;
        var linhaMeta = { type: "line", label: "Meta", data: s.labels.map(function () { return s.meta; }), borderColor: V("--metac", "#cbd5e1"), borderDash: [10, 8], borderWidth: 3, pointRadius: 0, fill: false, ehMeta: true, order: 0 };
        if (tipo === "empilhadas" && s.series) {
          datasets = s.series.map(function (se, k) { return { type: "bar", label: se.nome, data: se.valores, backgroundColor: PALETA[k % PALETA.length], empilhada: true, stack: "s", order: 1 }; });
        } else if (tipo === "barras") {
          datasets = [{ type: "bar", label: "Resultado", data: s.valores, order: 1, borderRadius: 4,
            backgroundColor: ating ? ating.map(function (a) { return a ? VERDE : VERM; }) : "#60a5fa" }];
        } else {
          datasets = [{ label: "Resultado", data: s.valores, borderColor: "#60a5fa", backgroundColor: ating ? "#ffffff0d" : "#60a5fa33", fill: true, tension: .25, borderWidth: 4, pointRadius: 7,
            pointBackgroundColor: ating ? ating.map(function (a) { return a ? VERDE : VERM; }) : "#60a5fa",
            segment: ating ? { borderColor: function (c) { return ating[c.p1DataIndex] ? VERDE : VERM; } } : {} }];
        }
        datasets.push(linhaMeta);
        var empil = tipo === "empilhadas" && !!s.series;
        var grafico = new Chart(cv, {
          type: tipo === "linha" ? "line" : "bar", plugins: [rotulos],
          data: { labels: s.labels, datasets: datasets },
          options: { maintainAspectRatio: false, animation: { duration: 900 }, layout: { padding: { top: 24, right: 16 } },
            plugins: { legend: { display: !ating || empil, labels: { color: V("--txt2", "#c4cee3"), font: { size: tf } } },
              tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + c.parsed.y + u; } } } },
            scales: { x: { stacked: empil, ticks: { color: V("--txt2", "#c4cee3"), font: { size: tf } }, grid: { color: V("--grade", "#ffffff12") } },
                      y: { stacked: empil, ticks: { color: V("--txt2", "#c4cee3"), font: { size: tf }, callback: function (v) { return Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + u; } }, grid: { color: V("--grade", "#ffffff12") } } } }
        });
        charts.push(grafico);
        // se o card mudar de tamanho (ex.: editor), as fontes acompanham
        if (window.ResizeObserver) new ResizeObserver(function () {
          var o = grafico.options, f = Math.round(base() * .65);
          o.plugins.legend.labels.font.size = f; o.scales.x.ticks.font.size = f; o.scales.y.ticks.font.size = f; grafico.update("none");
        }).observe(w);
      }, 30);
      return w;
    },
    pagina: function (s) {
      var g = el("div", "pagina n" + s.paineis.length);
      s.paineis.forEach(function (p) { g.appendChild(painel(p, true)); });
      return g;
    },
    // Vários cards posicionados: na grade a posição é em células (x/colunas...), na livre já é em % do slide.
    layout: function (s) {
      var L = s.layout || {}, cols = L.colunas || 12, rows = L.linhas || 8, livre = L.modo === "livre";
      var g = el("div", "grade-slide");
      s.itens.forEach(function (i) {
        var p = i.pos || {}, caixa = el("div", "gi");
        caixa.style.left = (livre ? p.x : p.x / cols * 100) + "%"; caixa.style.top = (livre ? p.y : p.y / rows * 100) + "%";
        caixa.style.width = (livre ? p.w : p.w / cols * 100) + "%"; caixa.style.height = (livre ? p.h : p.h / rows * 100) + "%";
        caixa.appendChild(painel(i.conteudo, !i.visual || i.visual.titulo !== false, !!i.visual && i.visual.moldura === "sem", !i.visual || i.visual.subtitulo !== false)); g.appendChild(caixa);
      });
      return g;
    },
    vazio: function (s) { return el("div", "vazio", s.mensagem || s.subtitulo); }
  };

  // Um card = o desenho da sua forma (tiles/cards/bars/chart) dentro de um container que dá a escala (fonte base) a todo o conteúdo.
  // Elemento solto do slide: título, subtítulo, texto ou imagem (sem dados; fonte em % da largura do slide).
  function elemento(p) {
    var q = el("section", "painel elemento" + (p.moldura ? "" : " sem-moldura")), imagem = p.tipo === "imagem";
    var d = el("div", "elem al-" + (p.alinhar || "esq") + " v-" + (p.vertical || "meio") + " c-" + (p.cor || "padrao") + (p.negrito ? " neg" : "") + (imagem ? " img" : "") + (p.ajuste === "cobre" ? " cobre" : ""));
    d.style.setProperty("--tam", p.tam || 2);
    if (imagem) {
      if (/^(https:\/\/|data:image\/(png|jpeg|webp|gif);base64,)/.test(p.url || "")) { var im = el("img"); im.src = p.url; im.alt = p.alt || ""; d.appendChild(im); }
      else d.appendChild(el("div", "sem-img", "Imagem não escolhida"));
    } else d.appendChild(el("div", "t", p.texto || ""));
    q.appendChild(d); return q;
  }

  function painel(p, comTitulo, semMoldura, comSubtitulo) {   // título e subtítulo se ocultam separadamente
    if (p.kind === "elemento") return elemento(p);
    var q = el("section", "painel" + (semMoldura ? " sem-moldura" : ""));
    var mostraT = comTitulo !== false, mostraS = comSubtitulo !== false && !!p.subtitulo;
    if (mostraT || mostraS) {
      var h = el("div", "ph"), t = el("div");
      h.appendChild(el("i", "bi " + (p.icone || "bi-display")));
      if (mostraT) t.appendChild(el("h2", null, p.titulo));
      if (mostraS) t.appendChild(el("p", null, p.subtitulo));
      h.appendChild(t); q.appendChild(h);
    }
    q.appendChild(card(p));
    return q;
  }

  function card(s) {
    var cx = el("div", "cx"), cxi = el("div", "cxi");
    cxi.appendChild((desenho[s.kind] || desenho.vazio)(s)); cx.appendChild(cxi);
    return cx;
  }


  function slide(s) {
    return s.kind === "pagina" || s.kind === "layout" || s.kind === "vazio" ? desenho[s.kind](s) : card(s);
  }
  // Tempo para passar por todas as páginas dos cards do slide atual (0 se nenhum card está paginado): o player não troca o slide antes.
  function tempoPaginas() {
    return paginados.reduce(function (m, g) { return g.isConnected && g._pgs > 1 ? Math.max(m, g._pgs * api.pagMs) : m; }, 0);
  }
  function moverPagina(d) {   // modo manual: avança/volta uma página de algum card paginado; false se não há mais páginas
    return paginados.some(function (g) { return g.isConnected && g._pgs > 1 && g._mover && g._mover(d); });
  }
  function destruir() { paginados = []; charts.forEach(function (c) { try { c.destroy(); } catch (e) {} }); charts = []; }
  var api = { manual: false, pagMs: 8000, slide: slide, moverPagina: moverPagina, card: card, painel: painel, tempoPaginas: tempoPaginas, destruir: destruir, el: el };
  return api;
})();

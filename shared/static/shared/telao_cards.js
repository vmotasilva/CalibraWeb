/* Renderer dos cards do Modo Apresentação (player e editor). Requer Chart.js e telao_cards.css; o container pai deve ter a classe .tl.
   TelaoCards.slide(s) devolve o elemento do slide (tiles/cards/bars/chart/pagina/layout/vazio); TelaoCards.destruir() libera os gráficos. */
window.TelaoCards = (function () {
  var charts = [];
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function tom(t) { return t || "neutro"; }

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
      var g = el("div", "tcards");
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
      return g;
    },
    bars: function (s) {
      var g = el("div", "bars");
      s.itens.forEach(function (i) {
        var r = el("div", "brow " + tom(i.tom)); r.appendChild(el("div", "l", i.rotulo));
        var t = el("div", "t"), b = el("span"); b.style.width = Math.max(2, Math.min(100, i.pct)) + "%"; t.appendChild(b);
        r.appendChild(t); r.appendChild(el("div", "p", i.txt)); g.appendChild(r);
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
        var base = function () { return parseFloat(getComputedStyle(w).fontSize) || 18; };   // fonte base do container (.cxi)
        var tf = Math.round(base() * .65), ating = s.atingiu || null, VERDE = "#22c55e", VERM = "#ef4444";
        var rotulos = { id: "rotulos", afterDatasetsDraw: function (c) {
          var x = c.ctx; x.save(); x.textAlign = "center"; x.font = "700 " + Math.round(base() * .75) + "px Inter, sans-serif";
          c.data.datasets.forEach(function (ds, di) {
            var meta = c.getDatasetMeta(di);
            meta.data.forEach(function (pt, i) {
              if (di === 1 && i !== meta.data.length - 1) return;           // meta: só no último ponto
              var v = ds.data[i]; if (v == null) return;
              var abaixo = di === 1 || pt.y < c.chartArea.top + 34;
              x.fillStyle = di === 1 ? "#cbd5e1" : "#ffffff";
              if (di === 0 && ating) x.fillStyle = ating[i] ? "#4ade80" : "#f87171";
              x.textBaseline = abaixo ? "top" : "bottom";
              var tx = (di === 1 ? "Meta " : "") + fmt(v);
              var px = Math.min(Math.max(pt.x, c.chartArea.left + 30), c.chartArea.right - 40);
              x.lineWidth = 5; x.strokeStyle = "#131c31"; x.strokeText(tx, px, pt.y + (abaixo ? 12 : -12));
              x.fillText(tx, px, pt.y + (abaixo ? 12 : -12));
            });
          });
          x.restore();
        } };
        var grafico = new Chart(cv, {
          type: "line", plugins: [rotulos],
          data: { labels: s.labels, datasets: [
            { label: "Resultado", data: s.valores, borderColor: "#60a5fa", backgroundColor: ating ? "#ffffff0d" : "#60a5fa33", fill: true, tension: .25, borderWidth: 4, pointRadius: 7,
              pointBackgroundColor: ating ? ating.map(function (a) { return a ? VERDE : VERM; }) : "#60a5fa",
              segment: ating ? { borderColor: function (c) { return ating[c.p1DataIndex] ? VERDE : VERM; } } : {} },
            { label: "Meta", data: s.labels.map(function () { return s.meta; }), borderColor: "#cbd5e1", borderDash: [10, 8], borderWidth: 3, pointRadius: 0, fill: false }
          ] },
          options: { maintainAspectRatio: false, animation: { duration: 900 }, layout: { padding: { top: 24, right: 16 } },
            plugins: { legend: { display: !ating, labels: { color: "#c4cee3", font: { size: tf } } },
              tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + c.parsed.y + u; } } } },
            scales: { x: { ticks: { color: "#c4cee3", font: { size: tf } }, grid: { color: "#ffffff12" } },
                      y: { ticks: { color: "#c4cee3", font: { size: tf }, callback: function (v) { return Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + u; } }, grid: { color: "#ffffff12" } } } }
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
        caixa.appendChild(painel(i.conteudo, !i.visual || i.visual.titulo !== false, !!i.visual && i.visual.moldura === "sem")); g.appendChild(caixa);
      });
      return g;
    },
    vazio: function (s) { return el("div", "vazio", s.subtitulo); }
  };

  // Um card = o desenho da sua forma (tiles/cards/bars/chart) dentro de um container que dá a escala (fonte base) a todo o conteúdo.
  function painel(p, comTitulo, semMoldura) {
    var q = el("section", "painel" + (semMoldura ? " sem-moldura" : ""));
    if (comTitulo) {
      var h = el("div", "ph"), t = el("div");
      h.appendChild(el("i", "bi " + (p.icone || "bi-display"))); t.appendChild(el("h2", null, p.titulo));
      if (p.subtitulo) t.appendChild(el("p", null, p.subtitulo));
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
  function destruir() { charts.forEach(function (c) { try { c.destroy(); } catch (e) {} }); charts = []; }
  return { slide: slide, card: card, painel: painel, destruir: destruir, el: el };
})();

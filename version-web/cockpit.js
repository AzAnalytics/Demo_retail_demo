/* ------------------------------------------------------------------
   Le Cockpit — demonstrateur web (Maison Lauret)
   Reprend les calculs de app.py (Streamlit) cote navigateur.
   Aucune dependance externe : graphiques dessines en SVG.
   ------------------------------------------------------------------ */
(function () {
  "use strict";

  var ROOT = document.getElementById("cockpit");
  if (!ROOT) return;

  var EN = (document.documentElement.getAttribute("lang") || "fr").toLowerCase().indexOf("en") === 0;

  var T = {
    fr: {
      filters: "Filtres", store: "Magasin", cat: "Catégorie", period: "Période",
      reset: "Tout réafficher", from: "du", to: "au",
      kpiTitle: function (a, b) { return "Indicateurs : " + a + " comparé à " + b; },
      caption: function (m, d1, d2, n, how, mc, nc) {
        return "Mois analysé : " + m + " (" + d1 + " au " + d2 + ", " + n + " ventes). Comparé " + how + " : " + mc + " (" + nc + " ventes).";
      },
      prevYear: "au même mois un an avant", prevMonth: "au mois précédent disponible",
      vsYear: "vs même mois un an avant", vsMonth: "vs mois précédent disponible",
      ca: "Chiffre d'affaires", marge: "Marge", taux: "Taux de marge", panier: "Panier moyen",
      pts: " pts", alerts: "Alertes",
      stable: "Rien à signaler ce mois-ci, tout est stable.",
      down: function (c, v, how) { return c + " recule de " + v + " % " + how + ". À regarder de près."; },
      up: function (c, v) { return c + " progresse de +" + v + " %. Capitalise dessus."; },
      tabs: ["Évolution", "Magasins", "Produits", "Habitudes", "Objectif", "Prévisions"],
      evoTitle: "Chiffre d'affaires mensuel par magasin",
      caByStore: "Chiffre d'affaires par magasin", margeByStore: "Marge par magasin",
      mix: "Répartition du CA par catégorie et par magasin",
      top: "Top 10 produits (CA)", flop: "Flop 10 produits (CA)",
      margeCat: "Contribution à la marge par catégorie",
      byDay: "Chiffre d'affaires moyen par jour de la semaine",
      bestDay: function (d) { return "Jour le plus fort : " + d + ". Idéal pour renforcer les équipes et les opérations commerciales."; },
      objTitle: function (m, p) { return m + " : réel vs objectif (objectif = " + p + " +8 %)"; },
      objectif: "Objectif du mois", atteinte: "Taux d'atteinte", real: "Réel", target: "Objectif",
      vsObj: " pts vs objectif",
      noObj: "Pas assez d'historique pour calculer un objectif sur cette sélection.",
      prevIntro: "Le Cockpit teste plusieurs modèles (saisonnier ajusté, régression Ridge + Fourier, tendance × saisonnalité) et retient le plus fiable sur l'historique récent. Prévision sur 12 mois, basée sur tout l'historique disponible.",
      level: "Niveau d'analyse", global: "Global", byStore: "Par magasin", byCat: "Par catégorie",
      allShops: "toutes boutiques",
      fcCa: "CA prévu · 12 prochains mois", fcVs: " % vs 12 derniers mois",
      fcRel: "Fiabilité (erreur test)", fcModel: "Modèle retenu",
      fcTitle: function (l) { return "Chiffre d'affaires — " + l + " : historique et prévision 12 mois"; },
      history: "Historique", forecast: "Prévision", band: "Incertitude (95 %)",
      fcDown: function (g, l) { return "Tendance à la baisse anticipée : " + g + " % sur 12 mois pour « " + l + " ». À anticiper dès maintenant."; },
      fcUp: function (g, l) { return "Croissance anticipée : " + g + " % sur 12 mois pour « " + l + " ». Sécurise les stocks et les équipes des mois forts."; },
      fcFlat: function (g, l) { return "Activité stable anticipée pour « " + l + " » (" + g + " % sur 12 mois)."; },
      recap: function (v) { return "Récapitulatif — " + v.toLowerCase(); },
      colCa: "CA prévu 12 mois", colGrowth: "Croissance", colModel: "Modèle retenu", colMape: "Fiabilité (MAPE)",
      dl: "Télécharger les données filtrées (CSV)",
      empty: "Aucune vente ne correspond aux filtres choisis. Ouvrez « Filtres » et élargissez la sélection.",
      foot: "Données de démonstration. Votre futur tableau de bord sera connecté à vos propres chiffres.",
      months: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
      mshort: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
      days: ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    },
    en: {
      filters: "Filters", store: "Store", cat: "Category", period: "Period",
      reset: "Show everything again", from: "from", to: "to",
      kpiTitle: function (a, b) { return "Indicators: " + a + " compared with " + b; },
      caption: function (m, d1, d2, n, how, mc, nc) {
        return "Month analysed: " + m + " (" + d1 + " to " + d2 + ", " + n + " sales). Compared " + how + ": " + mc + " (" + nc + " sales).";
      },
      prevYear: "with the same month a year earlier", prevMonth: "with the previous month available",
      vsYear: "vs the same month a year earlier", vsMonth: "vs the previous month available",
      ca: "Revenue", marge: "Margin", taux: "Margin rate", panier: "Average basket",
      pts: " pts", alerts: "Alerts",
      stable: "Nothing to report this month, everything is stable.",
      down: function (c, v, how) { return c + " is down " + v + " % " + how + ". Worth a closer look."; },
      up: function (c, v) { return c + " is up +" + v + " %. Build on it."; },
      tabs: ["Trend", "Stores", "Products", "Patterns", "Target", "Forecast"],
      evoTitle: "Monthly revenue by store",
      caByStore: "Revenue by store", margeByStore: "Margin by store",
      mix: "Revenue split by category and store",
      top: "Top 10 products (revenue)", flop: "Bottom 10 products (revenue)",
      margeCat: "Margin contribution by category",
      byDay: "Average revenue by day of the week",
      bestDay: function (d) { return "Strongest day: " + d + ". Ideal for reinforcing teams and running promotions."; },
      objTitle: function (m, p) { return m + ": actual vs target (target = " + p + " +8 %)"; },
      objectif: "Target for the month", atteinte: "Achievement rate", real: "Actual", target: "Target",
      vsObj: " pts vs target",
      noObj: "Not enough history to compute a target for this selection.",
      prevIntro: "Le Cockpit tests several models (adjusted seasonal, Ridge regression + Fourier, trend × seasonality) and keeps the most reliable one on recent history. Forecast over 12 months, based on all available history.",
      level: "Level of analysis", global: "Overall", byStore: "By store", byCat: "By category",
      allShops: "all stores",
      fcCa: "Forecast revenue · next 12 months", fcVs: " % vs last 12 months",
      fcRel: "Reliability (test error)", fcModel: "Model selected",
      fcTitle: function (l) { return "Revenue — " + l + ": history and 12-month forecast"; },
      history: "History", forecast: "Forecast", band: "Uncertainty (95 %)",
      fcDown: function (g, l) { return "Downward trend expected: " + g + " % over 12 months for “" + l + "”. Worth anticipating now."; },
      fcUp: function (g, l) { return "Growth expected: " + g + " % over 12 months for “" + l + "”. Secure stock and staffing for the strong months."; },
      fcFlat: function (g, l) { return "Stable activity expected for “" + l + "” (" + g + " % over 12 months)."; },
      recap: function (v) { return "Summary — " + v.toLowerCase(); },
      colCa: "Forecast revenue 12 months", colGrowth: "Growth", colModel: "Model", colMape: "Reliability (MAPE)",
      dl: "Download the filtered data (CSV)",
      empty: "No sales match the selected filters. Open “Filters” and widen the selection.",
      foot: "Demo data. Your own dashboard will be connected to your own figures.",
      months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
      mshort: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
      days: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    }
  }[EN ? "en" : "fr"];

  var C = {
    vert: "#1C2420", or: "#B8913A", orClair: "#D8B463", bleu: "#3E6D9C",
    vertPos: "#2E8B6A", rouge: "#C0392B", gris: "#5A6478", trait: "#E3DED2",
    creme: "#F7F3EA", pale: "#C9C2B4"
  };
  var SERIE = [C.vert, C.or, C.bleu, "#8A6D3B", "#5C7A99", "#2E8B6A", "#B08D57", "#8892A6"];

  /* ---------------- formatage ---------------- */
  function groupNum(n) {
    var s = String(Math.abs(Math.round(n))), out = "", k = 0;
    for (var i = s.length - 1; i >= 0; i--) { out = s[i] + out; if (++k % 3 === 0 && i > 0) out = (EN ? "," : " ") + out; }
    return (n < 0 ? "-" : "") + out;
  }
  function eur(n) { return EN ? "€" + groupNum(n) : groupNum(n) + " €"; }
  function eur2(n) {
    var v = (Math.round(n * 100) / 100).toFixed(2);
    var p = v.split("."), e = groupNum(parseFloat(p[0])) + (EN ? "." : ",") + p[1];
    return EN ? "€" + e : e + " €";
  }
  function pct(n, d) { var v = (n).toFixed(d === undefined ? 1 : d).replace(".", EN ? "." : ","); return v; }
  function signed(n, d) { return (n >= 0 ? "+" : "") + pct(n, d); }
  function monthLabel(ym) { var p = ym.split("-"); return T.months[+p[1] - 1] + " " + p[0]; }
  function monthShort(ym) { var p = ym.split("-"); return T.mshort[+p[1] - 1] + " " + p[0].slice(2); }
  function dateLabel(dt) {
    var dd = String(dt.getUTCDate()).padStart(2, "0"), mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
    return EN ? dd + "/" + mm + "/" + dt.getUTCFullYear() : dd + "/" + mm + "/" + dt.getUTCFullYear();
  }
  function iso(dt) { return dt.toISOString().slice(0, 10); }

  /* ---------------- SVG ---------------- */
  var NS = "http://www.w3.org/2000/svg";
  function el(name, attrs) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    return e;
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    var exp = Math.pow(10, Math.floor(Math.log10(v))), f = v / exp;
    var step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
    return step * exp;
  }
  function yTicks(max, n) {
    var m = niceMax(max), out = [];
    for (var i = 0; i <= n; i++) out.push(m * i / n);
    return out;
  }
  function shortEur(v) {
    if (Math.abs(v) >= 1000000) return groupNum(v / 1000000) + " M" + (EN ? "" : " ") + "€";
    if (Math.abs(v) >= 1000) return groupNum(v / 1000) + " k" + (EN ? "" : " ") + "€";
    return eur(v);
  }

  /* chaque graphique est redessine quand la largeur change */
  var charts = [];
  function mount(host, draw) {
    var tip = host.querySelector(".ck-tip");
    if (!tip) { tip = document.createElement("div"); tip.className = "ck-tip"; host.appendChild(tip); }
    var spec = { host: host, draw: draw, tip: tip, w: 0 };
    charts.push(spec);
    render(spec);
  }
  function render(spec) {
    var w = Math.max(260, Math.round(spec.host.clientWidth - 24));
    spec.w = w;
    var old = spec.host.querySelector("svg");
    if (old) old.remove();
    var svg = spec.draw(w, spec.tip);
    spec.host.insertBefore(svg, spec.tip);
  }
  function clearCharts() { charts = []; }
  var rt;
  window.addEventListener("resize", function () {
    clearTimeout(rt);
    rt = setTimeout(function () {
      charts.forEach(function (s) { if (Math.abs(s.host.clientWidth - 24 - s.w) > 12) render(s); });
    }, 160);
  });

  function showTip(tip, host, x, y, html) {
    tip.innerHTML = html;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
    tip.classList.add("on");
  }
  function hideTip(tip) { tip.classList.remove("on"); }

  /* --- graphique en lignes (plusieurs series) --- */
  function lineChart(host, o) {
    mount(host, function (w, tip) {
      var h = o.height || 320, pad = { t: 14, r: 14, b: 34, l: 62 };
      var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      var max = 0;
      o.series.forEach(function (s) { s.values.forEach(function (v) { if (v > max) max = v; }); });
      var ticks = yTicks(max, 4), top = ticks[ticks.length - 1] || 1;
      var svg = el("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h, role: "img" });
      var X = function (i) { return pad.l + (o.labels.length < 2 ? iw / 2 : iw * i / (o.labels.length - 1)); };
      var Y = function (v) { return pad.t + ih - ih * (v / top); };
      ticks.forEach(function (t) {
        svg.appendChild(el("line", { class: "ck-grid", x1: pad.l, x2: w - pad.r, y1: Y(t), y2: Y(t) }));
        var tx = el("text", { class: "ck-tick", x: pad.l - 8, y: Y(t) + 4, "text-anchor": "end" });
        tx.textContent = shortEur(t); svg.appendChild(tx);
      });
      var every = Math.ceil(o.labels.length / Math.max(3, Math.floor(iw / 68)));
      o.labels.forEach(function (lb, i) {
        if (i % every !== 0 && i !== o.labels.length - 1) return;
        var tx = el("text", { class: "ck-tick", x: X(i), y: h - 12, "text-anchor": "middle" });
        tx.textContent = lb; svg.appendChild(tx);
      });
      svg.appendChild(el("line", { class: "ck-axis", x1: pad.l, x2: w - pad.r, y1: Y(0), y2: Y(0) }));
      o.series.forEach(function (s) {
        var dd = s.values.map(function (v, i) { return (i ? "L" : "M") + X(i) + " " + Y(v); }).join(" ");
        svg.appendChild(el("path", { d: dd, fill: "none", stroke: s.color, "stroke-width": 2.4, "stroke-linejoin": "round" }));
        s.values.forEach(function (v, i) { svg.appendChild(el("circle", { cx: X(i), cy: Y(v), r: 3.2, fill: s.color })); });
      });
      o.labels.forEach(function (lb, i) {
        var hit = el("rect", { class: "ck-hit", x: X(i) - iw / (2 * Math.max(1, o.labels.length - 1)), y: pad.t, width: Math.max(14, iw / Math.max(1, o.labels.length - 1)), height: ih });
        hit.addEventListener("mouseenter", function () {
          var rows = o.series.map(function (s) {
            return '<span style="color:' + s.color + '">●</span> ' + s.name + " : " + eur(s.values[i]);
          }).join("<br>");
          showTip(tip, host, X(i) + 12, pad.t + 20, "<b>" + (o.full ? o.full[i] : lb) + "</b><br>" + rows);
        });
        hit.addEventListener("mouseleave", function () { hideTip(tip); });
        svg.appendChild(hit);
      });
      return svg;
    });
  }

  /* --- barres verticales --- */
  function barChart(host, o) {
    mount(host, function (w, tip) {
      var h = o.height || 300, pad = { t: 14, r: 14, b: 38, l: 62 };
      var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      var max = Math.max.apply(null, o.values.concat([0]));
      var ticks = yTicks(max, 4), top = ticks[ticks.length - 1] || 1;
      var svg = el("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h });
      var n = o.values.length, bw = iw / n * 0.6;
      var X = function (i) { return pad.l + iw * (i + 0.5) / n; };
      var Y = function (v) { return pad.t + ih - ih * (v / top); };
      ticks.forEach(function (t) {
        svg.appendChild(el("line", { class: "ck-grid", x1: pad.l, x2: w - pad.r, y1: Y(t), y2: Y(t) }));
        var tx = el("text", { class: "ck-tick", x: pad.l - 8, y: Y(t) + 4, "text-anchor": "end" });
        tx.textContent = shortEur(t); svg.appendChild(tx);
      });
      o.values.forEach(function (v, i) {
        var r = el("rect", { x: X(i) - bw / 2, y: Y(v), width: bw, height: Math.max(1, Y(0) - Y(v)), fill: o.colors ? o.colors[i] : C.or, rx: 3 });
        r.addEventListener("mouseenter", function () { showTip(tip, host, X(i), Y(v), "<b>" + o.labels[i] + "</b><br>" + eur(v)); });
        r.addEventListener("mouseleave", function () { hideTip(tip); });
        svg.appendChild(r);
        var tx = el("text", { class: "ck-tick", x: X(i), y: h - 14, "text-anchor": "middle" });
        tx.textContent = o.labels[i]; svg.appendChild(tx);
      });
      svg.appendChild(el("line", { class: "ck-axis", x1: pad.l, x2: w - pad.r, y1: Y(0), y2: Y(0) }));
      return svg;
    });
  }

  /* --- barres horizontales --- */
  function hBarChart(host, o) {
    mount(host, function (w, tip) {
      var n = o.values.length, rowH = o.rowH || 30;
      var pad = { t: 10, r: 60, b: 24, l: Math.min(170, Math.max(80, w * 0.34)) };
      var h = pad.t + pad.b + n * rowH;
      var iw = w - pad.l - pad.r;
      var max = Math.max.apply(null, o.values.concat([0])) || 1;
      var svg = el("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h });
      o.values.forEach(function (v, i) {
        var y = pad.t + i * rowH, bh = rowH * 0.62;
        var bw = Math.max(1, iw * (v / max));
        var r = el("rect", { x: pad.l, y: y + (rowH - bh) / 2, width: bw, height: bh, fill: o.colors ? o.colors[i] : C.or, rx: 3 });
        r.addEventListener("mouseenter", function () { showTip(tip, host, pad.l + bw, y + rowH / 2, "<b>" + o.labels[i] + "</b><br>" + (o.tip ? o.tip(i) : eur(v))); });
        r.addEventListener("mouseleave", function () { hideTip(tip); });
        svg.appendChild(r);
        var lb = el("text", { class: "ck-tick", x: pad.l - 8, y: y + rowH / 2 + 4, "text-anchor": "end" });
        lb.textContent = o.labels[i]; svg.appendChild(lb);
        var vt = el("text", { class: "ck-tick", x: pad.l + bw + 7, y: y + rowH / 2 + 4 });
        vt.textContent = shortEur(v); svg.appendChild(vt);
      });
      return svg;
    });
  }

  /* --- barres empilees --- */
  function stackedChart(host, o) {
    mount(host, function (w, tip) {
      var h = o.height || 330, pad = { t: 14, r: 14, b: 38, l: 62 };
      var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      var totals = o.labels.map(function (_, i) {
        return o.groups.reduce(function (a, g) { return a + g.values[i]; }, 0);
      });
      var ticks = yTicks(Math.max.apply(null, totals.concat([0])), 4), top = ticks[ticks.length - 1] || 1;
      var svg = el("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h });
      var n = o.labels.length, bw = iw / n * 0.5;
      var X = function (i) { return pad.l + iw * (i + 0.5) / n; };
      var Y = function (v) { return pad.t + ih - ih * (v / top); };
      ticks.forEach(function (t) {
        svg.appendChild(el("line", { class: "ck-grid", x1: pad.l, x2: w - pad.r, y1: Y(t), y2: Y(t) }));
        var tx = el("text", { class: "ck-tick", x: pad.l - 8, y: Y(t) + 4, "text-anchor": "end" });
        tx.textContent = shortEur(t); svg.appendChild(tx);
      });
      o.labels.forEach(function (lb, i) {
        var acc = 0;
        o.groups.forEach(function (g) {
          var v = g.values[i]; if (v <= 0) { acc += v; return; }
          var y0 = Y(acc + v), y1 = Y(acc);
          var r = el("rect", { x: X(i) - bw / 2, y: y0, width: bw, height: Math.max(1, y1 - y0), fill: g.color });
          r.addEventListener("mouseenter", function () { showTip(tip, host, X(i), y0, "<b>" + lb + "</b><br>" + g.name + " : " + eur(v)); });
          r.addEventListener("mouseleave", function () { hideTip(tip); });
          svg.appendChild(r); acc += v;
        });
        var tx = el("text", { class: "ck-tick", x: X(i), y: h - 14, "text-anchor": "middle" });
        tx.textContent = lb; svg.appendChild(tx);
      });
      svg.appendChild(el("line", { class: "ck-axis", x1: pad.l, x2: w - pad.r, y1: Y(0), y2: Y(0) }));
      return svg;
    });
  }

  /* --- historique + prevision + bande --- */
  function forecastChart(host, o) {
    mount(host, function (w, tip) {
      var h = 400, pad = { t: 14, r: 14, b: 34, l: 62 };
      var iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
      var labels = o.histX.concat(o.fcX);
      var max = Math.max.apply(null, o.histY.concat(o.hi));
      var ticks = yTicks(max, 4), top = ticks[ticks.length - 1] || 1;
      var svg = el("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h });
      var X = function (i) { return pad.l + iw * i / (labels.length - 1); };
      var Y = function (v) { return pad.t + ih - ih * (v / top); };
      ticks.forEach(function (t) {
        svg.appendChild(el("line", { class: "ck-grid", x1: pad.l, x2: w - pad.r, y1: Y(t), y2: Y(t) }));
        var tx = el("text", { class: "ck-tick", x: pad.l - 8, y: Y(t) + 4, "text-anchor": "end" });
        tx.textContent = shortEur(t); svg.appendChild(tx);
      });
      var off = o.histX.length;
      var up = o.hi.map(function (v, i) { return X(off + i) + " " + Y(v); });
      var lo = o.lo.map(function (v, i) { return X(off + i) + " " + Y(v); }).reverse();
      svg.appendChild(el("path", { d: "M" + up.join(" L") + " L" + lo.join(" L") + " Z", fill: "rgba(184,145,58,.18)", stroke: "none" }));
      var dh = o.histY.map(function (v, i) { return (i ? "L" : "M") + X(i) + " " + Y(v); }).join(" ");
      svg.appendChild(el("path", { d: dh, fill: "none", stroke: C.vert, "stroke-width": 2.5 }));
      var df = "M" + X(off - 1) + " " + Y(o.histY[off - 1]) + " " + o.fcY.map(function (v, i) { return "L" + X(off + i) + " " + Y(v); }).join(" ");
      svg.appendChild(el("path", { d: df, fill: "none", stroke: C.or, "stroke-width": 2.5, "stroke-dasharray": "5 4" }));
      o.histY.forEach(function (v, i) { svg.appendChild(el("circle", { cx: X(i), cy: Y(v), r: 3, fill: C.vert })); });
      o.fcY.forEach(function (v, i) { svg.appendChild(el("rect", { x: X(off + i) - 3, y: Y(v) - 3, width: 6, height: 6, fill: C.or, transform: "rotate(45 " + X(off + i) + " " + Y(v) + ")" })); });
      var every = Math.ceil(labels.length / Math.max(3, Math.floor(iw / 64)));
      labels.forEach(function (lb, i) {
        if (i % every !== 0 && i !== labels.length - 1) return;
        var tx = el("text", { class: "ck-tick", x: X(i), y: h - 12, "text-anchor": "middle" });
        tx.textContent = monthShort(lb); svg.appendChild(tx);
      });
      labels.forEach(function (lb, i) {
        var hit = el("rect", { class: "ck-hit", x: X(i) - iw / (2 * (labels.length - 1)), y: pad.t, width: Math.max(12, iw / (labels.length - 1)), height: ih });
        var isF = i >= off;
        var v = isF ? o.fcY[i - off] : o.histY[i];
        hit.addEventListener("mouseenter", function () {
          showTip(tip, host, X(i) + 10, pad.t + 20, "<b>" + monthLabel(lb) + "</b><br>" + eur(v) + (isF ? " (" + T.forecast.toLowerCase() + ")" : ""));
        });
        hit.addEventListener("mouseleave", function () { hideTip(tip); });
        svg.appendChild(hit);
      });
      return svg;
    });
  }

  function legend(items) {
    var d = document.createElement("div");
    d.className = "ck-legend";
    d.innerHTML = items.map(function (i) { return '<span><i style="background:' + i.color + '"></i>' + i.name + "</span>"; }).join("");
    return d;
  }

  /* ---------------- donnees ---------------- */
  var D = null, F = null;

  function dayToDate(d) { return new Date(D.day0 + d * 86400000); }
  function ymOf(d) { var dt = dayToDate(d); return dt.getUTCFullYear() + "-" + String(dt.getUTCMonth() + 1).padStart(2, "0"); }
  function addYears(ym, n) { var p = ym.split("-"); return (+p[0] + n) + "-" + p[1]; }

  function boot(raw) {
    D = {
      meta: raw.meta, c: raw.cols, fc: raw.forecast, recap: raw.recap,
      day0: Date.parse(raw.meta.day0 + "T00:00:00Z"),
      ym: null
    };
    D.ym = D.c.d.map(ymOf);
    F = {
      stores: D.meta.stores.map(function (_, i) { return i; }),
      cats: D.meta.cats.map(function (_, i) { return i; }),
      from: 0, to: D.meta.ndays
    };
    buildFilters();
    buildTabs();
    update();
  }

  function filtered() {
    var c = D.c, idx = [];
    var sOK = {}, cOK = {};
    F.stores.forEach(function (i) { sOK[i] = 1; });
    F.cats.forEach(function (i) { cOK[i] = 1; });
    for (var i = 0; i < c.d.length; i++) {
      if (c.d[i] < F.from || c.d[i] > F.to) continue;
      if (!sOK[c.m[i]] || !cOK[c.c[i]]) continue;
      idx.push(i);
    }
    return idx;
  }

  function sumBy(idx, keyFn, valFn) {
    var out = {};
    for (var j = 0; j < idx.length; j++) {
      var i = idx[j], k = keyFn(i);
      out[k] = (out[k] || 0) + valFn(i);
    }
    return out;
  }
  var CA = function (i) { return D.c.ca[i] / 100; };
  var MG = function (i) { return D.c.mg[i] / 100; };

  /* ---------------- interface ---------------- */
  function chips(host, names, selected, onChange) {
    host.innerHTML = "";
    names.forEach(function (n, i) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "ck-chip"; b.textContent = n;
      b.setAttribute("aria-pressed", selected.indexOf(i) >= 0 ? "true" : "false");
      b.addEventListener("click", function () {
        var k = selected.indexOf(i);
        if (k >= 0) { if (selected.length > 1) selected.splice(k, 1); }
        else selected.push(i);
        b.setAttribute("aria-pressed", selected.indexOf(i) >= 0 ? "true" : "false");
        onChange();
      });
      host.appendChild(b);
    });
  }

  function buildFilters() {
    ROOT.querySelector("[data-f=stores-label]").textContent = T.store;
    ROOT.querySelector("[data-f=cats-label]").textContent = T.cat;
    ROOT.querySelector("[data-f=period-label]").textContent = T.period;
    ROOT.querySelector("[data-f=summary]").textContent = T.filters;
    ROOT.querySelector("[data-f=from-label]").textContent = T.from;
    ROOT.querySelector("[data-f=to-label]").textContent = T.to;
    var reset = ROOT.querySelector("[data-f=reset]");
    reset.textContent = T.reset;
    chips(ROOT.querySelector("[data-f=stores]"), D.meta.stores, F.stores, update);
    chips(ROOT.querySelector("[data-f=cats]"), D.meta.cats, F.cats, update);
    var f = ROOT.querySelector("[data-f=from]"), t = ROOT.querySelector("[data-f=to]");
    var d0 = iso(dayToDate(0)), d1 = iso(dayToDate(D.meta.ndays));
    f.min = t.min = d0; f.max = t.max = d1; f.value = d0; t.value = d1;
    function onDate() {
      var a = Math.round((Date.parse(f.value + "T00:00:00Z") - D.day0) / 86400000);
      var b = Math.round((Date.parse(t.value + "T00:00:00Z") - D.day0) / 86400000);
      if (isNaN(a) || isNaN(b)) return;
      F.from = Math.max(0, Math.min(a, b)); F.to = Math.min(D.meta.ndays, Math.max(a, b));
      update();
    }
    f.addEventListener("change", onDate); t.addEventListener("change", onDate);
    reset.addEventListener("click", function () {
      F.stores.length = 0; D.meta.stores.forEach(function (_, i) { F.stores.push(i); });
      F.cats.length = 0; D.meta.cats.forEach(function (_, i) { F.cats.push(i); });
      F.from = 0; F.to = D.meta.ndays; f.value = d0; t.value = d1;
      chips(ROOT.querySelector("[data-f=stores]"), D.meta.stores, F.stores, update);
      chips(ROOT.querySelector("[data-f=cats]"), D.meta.cats, F.cats, update);
      update();
    });
  }

  var TABS = [];
  function buildTabs() {
    var bar = ROOT.querySelector("[data-f=tabs]");
    bar.innerHTML = "";
    T.tabs.forEach(function (name, i) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "ck-tab"; b.textContent = name;
      b.setAttribute("aria-selected", i === 0 ? "true" : "false");
      b.addEventListener("click", function () { select(i); });
      bar.appendChild(b); TABS.push(b);
    });
    ROOT.querySelector("[data-f=dl]").textContent = "↓ " + T.dl;
    ROOT.querySelector("[data-f=foot]").textContent = T.foot;
    ROOT.querySelector("[data-f=dl]").addEventListener("click", download);
  }
  var current = 0;
  /* affiche ou masque un element : on agit sur l'attribut ET sur le style en ligne,
     car le balisage de la page peut porter un style="display:none" que `hidden` ne leve pas. */
  function show(el, on) {
    if (!el) return;
    el.hidden = !on;
    el.style.display = on ? "" : "none";
  }
  function select(i) {
    current = i;
    TABS.forEach(function (b, k) { b.setAttribute("aria-selected", k === i ? "true" : "false"); });
    ROOT.querySelectorAll(".ck-panel").forEach(function (p, k) { show(p, k === i); });
    charts.forEach(function (s) { if (s.host.offsetParent !== null && Math.abs(s.host.clientWidth - 24 - s.w) > 12) render(s); });
  }

  /* ---------------- mise a jour ---------------- */
  function update() {
    clearCharts();
    var idx = filtered();
    var zone = ROOT.querySelector("[data-f=content]");
    var empty = ROOT.querySelector("[data-f=empty]");
    if (!idx.length) { show(zone, false); show(empty, true); empty.textContent = T.empty; return; }
    show(zone, true); show(empty, false);

    var months = {};
    idx.forEach(function (i) { months[D.ym[i]] = 1; });
    var mList = Object.keys(months).sort();
    var mRef = mList[mList.length - 1];
    var mCmp = addYears(mRef, -1), how = T.prevYear, howShort = T.vsYear;
    if (months[mCmp] !== 1) {
      var prev = mList.filter(function (m) { return m < mRef; });
      mCmp = prev.length ? prev[prev.length - 1] : null;
      how = T.prevMonth; howShort = T.vsMonth;
    }
    var cur = idx.filter(function (i) { return D.ym[i] === mRef; });
    var cmp = mCmp ? idx.filter(function (i) { return D.ym[i] === mCmp; }) : [];

    kpis(cur, cmp, mRef, mCmp, how);
    alerts(cur, cmp, howShort);
    tabEvolution(idx);
    tabStores(idx);
    tabProducts(idx);
    tabPatterns(idx);
    tabTarget(cur, cmp, mRef, mCmp);
    tabForecast();
    window.__ckExport = idx;
  }

  function agg(list) {
    var ca = 0, mg = 0;
    list.forEach(function (i) { ca += CA(i); mg += MG(i); });
    return { ca: ca, mg: mg, taux: ca ? mg / ca * 100 : 0, panier: list.length ? ca / list.length : 0, n: list.length };
  }

  function deltaHtml(c, p, digits) {
    if (!p) return '<div class="ck-kpi-d flat">—</div>';
    var v = (c - p) / p * 100;
    return '<div class="ck-kpi-d ' + (v > 0 ? "up" : v < 0 ? "down" : "flat") + '">' + (v > 0 ? "↑ " : v < 0 ? "↓ " : "") + signed(v, digits === undefined ? 1 : digits) + " %</div>";
  }

  function kpis(cur, cmp, mRef, mCmp, how) {
    var a = agg(cur), b = agg(cmp);
    ROOT.querySelector("[data-f=kpi-title]").textContent = T.kpiTitle(monthLabel(mRef), mCmp ? monthLabel(mCmp) : "—");
    var dates = cur.map(function (i) { return D.c.d[i]; });
    var d1 = dateLabel(dayToDate(Math.min.apply(null, dates))), d2 = dateLabel(dayToDate(Math.max.apply(null, dates)));
    ROOT.querySelector("[data-f=caption]").textContent = T.caption(monthLabel(mRef), d1, d2, a.n, how, mCmp ? monthLabel(mCmp) : "—", b.n);
    var tauxD = b.taux ? '<div class="ck-kpi-d ' + (a.taux > b.taux ? "up" : a.taux < b.taux ? "down" : "flat") + '">' + signed(a.taux - b.taux, 1) + T.pts + "</div>" : '<div class="ck-kpi-d flat">—</div>';
    ROOT.querySelector("[data-f=kpis]").innerHTML =
      kpiCard(T.ca, eur(a.ca), deltaHtml(a.ca, b.ca)) +
      kpiCard(T.marge, eur(a.mg), deltaHtml(a.mg, b.mg)) +
      kpiCard(T.taux, pct(a.taux, 1) + " %", tauxD) +
      kpiCard(T.panier, eur2(a.panier), deltaHtml(a.panier, b.panier));
  }
  function kpiCard(label, value, delta) {
    return '<div class="ck-kpi"><div class="ck-kpi-l">' + label + '</div><div class="ck-kpi-v">' + value + "</div>" + delta + "</div>";
  }

  function alerts(cur, cmp, howShort) {
    var cc = sumBy(cur, function (i) { return D.c.c[i]; }, CA);
    var cp = sumBy(cmp, function (i) { return D.c.c[i]; }, CA);
    var bad = [], good = [];
    Object.keys(cc).forEach(function (k) {
      var p = cp[k] || 0; if (p <= 0) return;
      var v = (cc[k] - p) / p * 100;
      if (v <= -D.meta.seuil) bad.push([D.meta.cats[k], v]);
      else if (v >= D.meta.seuil) good.push([D.meta.cats[k], v]);
    });
    bad.sort(function (a, b) { return a[1] - b[1]; });
    good.sort(function (a, b) { return b[1] - a[1]; });
    var html = "";
    if (!bad.length && !good.length) html = '<div class="ck-alert info">' + T.stable + "</div>";
    bad.forEach(function (x) { html += '<div class="ck-alert bad">⚠ ' + T.down("<b>" + x[0] + "</b>", pct(Math.abs(x[1]), 1), howShort) + "</div>"; });
    good.forEach(function (x) { html += '<div class="ck-alert good">↗ ' + T.up("<b>" + x[0] + "</b>", pct(x[1], 1)) + "</div>"; });
    ROOT.querySelector("[data-f=alerts-title]").textContent = T.alerts;
    ROOT.querySelector("[data-f=alerts]").innerHTML = html;
  }

  function panel(i) { return ROOT.querySelectorAll(".ck-panel")[i]; }

  function tabEvolution(idx) {
    var p = panel(0);
    p.innerHTML = '<h4 class="ck-sub">' + T.evoTitle + '</h4><div class="ck-chart"></div>';
    var months = {}; idx.forEach(function (i) { months[D.ym[i]] = 1; });
    var mx = Object.keys(months).sort();
    var series = F.stores.map(function (s, k) {
      var sums = {};
      idx.forEach(function (i) { if (D.c.m[i] === s) sums[D.ym[i]] = (sums[D.ym[i]] || 0) + CA(i); });
      return { name: D.meta.stores[s], color: SERIE[k % SERIE.length], values: mx.map(function (m) { return sums[m] || 0; }) };
    });
    p.insertBefore(legend(series), p.querySelector(".ck-chart"));
    lineChart(p.querySelector(".ck-chart"), { labels: mx.map(monthShort), full: mx.map(monthLabel), series: series, height: 330 });
  }

  function tabStores(idx) {
    var p = panel(1);
    p.innerHTML = '<div class="ck-two">' +
      '<div><h4 class="ck-sub">' + T.caByStore + '</h4><div class="ck-chart" data-c=ca></div></div>' +
      '<div><h4 class="ck-sub">' + T.margeByStore + '</h4><div class="ck-chart" data-c=mg></div></div></div>' +
      '<h4 class="ck-sub">' + T.mix + '</h4><div class="ck-legend" data-c=lg></div><div class="ck-chart" data-c=mix></div>';
    var names = F.stores.map(function (s) { return D.meta.stores[s]; });
    var cols = F.stores.map(function (_, k) { return SERIE[k % SERIE.length]; });
    var ca = F.stores.map(function (s) { var t = 0; idx.forEach(function (i) { if (D.c.m[i] === s) t += CA(i); }); return t; });
    var mg = F.stores.map(function (s) { var t = 0; idx.forEach(function (i) { if (D.c.m[i] === s) t += MG(i); }); return t; });
    barChart(p.querySelector("[data-c=ca]"), { labels: names, values: ca, colors: cols, height: 300 });
    barChart(p.querySelector("[data-c=mg]"), { labels: names, values: mg, colors: cols, height: 300 });
    var groups = F.cats.map(function (c, k) {
      return {
        name: D.meta.cats[c], color: SERIE[k % SERIE.length],
        values: F.stores.map(function (s) { var t = 0; idx.forEach(function (i) { if (D.c.m[i] === s && D.c.c[i] === c) t += CA(i); }); return t; })
      };
    });
    p.querySelector("[data-c=lg]").innerHTML = groups.map(function (g) { return '<span><i style="background:' + g.color + '"></i>' + g.name + "</span>"; }).join("");
    stackedChart(p.querySelector("[data-c=mix]"), { labels: names, groups: groups, height: 330 });
  }

  function tabProducts(idx) {
    var p = panel(2);
    p.innerHTML = '<div class="ck-two">' +
      '<div><h4 class="ck-sub">' + T.top + '</h4><div class="ck-chart" data-c=top></div></div>' +
      '<div><h4 class="ck-sub">' + T.flop + '</h4><div class="ck-chart" data-c=flop></div></div></div>' +
      '<h4 class="ck-sub">' + T.margeCat + '</h4><div class="ck-chart" data-c=mcat></div>';
    var byProd = {};
    idx.forEach(function (i) {
      var k = D.c.p[i];
      if (!byProd[k]) byProd[k] = { ca: 0, q: 0, mg: 0 };
      byProd[k].ca += CA(i); byProd[k].q += D.c.q[i]; byProd[k].mg += MG(i);
    });
    var list = Object.keys(byProd).map(function (k) { return { n: D.meta.prods[k], v: byProd[k] }; });
    list.sort(function (a, b) { return b.v.ca - a.v.ca; });
    var top = list.slice(0, 10), flop = list.slice().reverse().slice(0, 10);
    hBarChart(p.querySelector("[data-c=top]"), {
      labels: top.map(function (x) { return x.n; }), values: top.map(function (x) { return x.v.ca; }),
      colors: top.map(function () { return C.vertPos; }),
      tip: function (i) { return eur(top[i].v.ca) + "<br>" + groupNum(top[i].v.q) + (EN ? " units" : " unités"); }
    });
    hBarChart(p.querySelector("[data-c=flop]"), {
      labels: flop.map(function (x) { return x.n; }), values: flop.map(function (x) { return x.v.ca; }),
      colors: flop.map(function () { return C.rouge; }),
      tip: function (i) { return eur(flop[i].v.ca) + "<br>" + groupNum(flop[i].v.q) + (EN ? " units" : " unités"); }
    });
    var byCat = F.cats.map(function (c) {
      var ca = 0, mg = 0;
      idx.forEach(function (i) { if (D.c.c[i] === c) { ca += CA(i); mg += MG(i); } });
      return { n: D.meta.cats[c], ca: ca, mg: mg, taux: ca ? mg / ca * 100 : 0 };
    }).sort(function (a, b) { return b.mg - a.mg; });
    var tmin = Math.min.apply(null, byCat.map(function (x) { return x.taux; }));
    var tmax = Math.max.apply(null, byCat.map(function (x) { return x.taux; }));
    hBarChart(p.querySelector("[data-c=mcat]"), {
      labels: byCat.map(function (x) { return x.n; }), values: byCat.map(function (x) { return x.mg; }),
      colors: byCat.map(function (x) { return mixColor(tmax === tmin ? 1 : (x.taux - tmin) / (tmax - tmin)); }),
      tip: function (i) { return eur(byCat[i].mg) + "<br>" + T.taux + " : " + pct(byCat[i].taux, 1) + " %"; }
    });
  }
  function mixColor(t) {
    var a = [227, 222, 210], b = [184, 145, 58], c = [28, 36, 32];
    var from = t < 0.5 ? a : b, to = t < 0.5 ? b : c, k = t < 0.5 ? t * 2 : (t - 0.5) * 2;
    return "rgb(" + from.map(function (v, i) { return Math.round(v + (to[i] - v) * k); }).join(",") + ")";
  }

  function tabPatterns(idx) {
    var p = panel(3);
    p.innerHTML = '<h4 class="ck-sub">' + T.byDay + '</h4><div class="ck-chart"></div><div class="ck-alert info" data-c=note></div>';
    var sums = [0, 0, 0, 0, 0, 0, 0];
    idx.forEach(function (i) { var dt = dayToDate(D.c.d[i]); sums[(dt.getUTCDay() + 6) % 7] += CA(i); });
    barChart(p.querySelector(".ck-chart"), {
      labels: T.days.map(function (d) { return d.slice(0, 3); }), values: sums,
      colors: sums.map(function () { return C.bleu; }), height: 320
    });
    var best = sums.indexOf(Math.max.apply(null, sums));
    p.querySelector("[data-c=note]").innerHTML = T.bestDay("<b>" + T.days[best] + "</b>");
  }

  function tabTarget(cur, cmp, mRef, mCmp) {
    var p = panel(4);
    var a = agg(cur), b = agg(cmp);
    if (!b.ca) { p.innerHTML = '<div class="ck-alert info">' + T.noObj + "</div>"; return; }
    var obj = b.ca * D.meta.objectif, att = a.ca / obj * 100;
    p.innerHTML = '<h4 class="ck-sub">' + T.objTitle(monthLabel(mRef), monthLabel(mCmp)) + '</h4>' +
      '<div class="ck-chart" data-c=obj></div><div class="ck-kpis" style="margin-top:14px">' +
      kpiCard(T.objectif, eur(obj), "") +
      kpiCard(T.atteinte, Math.round(att) + " %", '<div class="ck-kpi-d ' + (att >= 100 ? "up" : "down") + '">' + signed(att - 100, 0) + T.vsObj + "</div>") +
      "</div>";
    hBarChart(p.querySelector("[data-c=obj]"), {
      labels: [T.target, T.real], values: [obj, a.ca], colors: [C.pale, C.vert], rowH: 46
    });
  }

  function tabForecast() {
    var p = panel(5);
    if (p.dataset.built !== "1") {
      p.innerHTML = '<p class="ck-caption">' + T.prevIntro + '</p>' +
        '<div class="ck-field" style="margin-bottom:12px"><span>' + T.level + '</span><div class="ck-chips" data-c=lvl></div></div>' +
        '<div class="ck-field" data-c=entwrap style="margin-bottom:12px" hidden><span data-c=entlabel></span><div class="ck-chips" data-c=ent></div></div>' +
        '<div data-c=body></div>';
      p.dataset.built = "1";
      var lvls = [T.global, T.byStore, T.byCat];
      var sel = [0];
      chips(p.querySelector("[data-c=lvl]"), lvls, sel, function () {
        if (sel.length > 1) sel.splice(0, sel.length - 1);
        p.dataset.lvl = sel[0]; p.dataset.ent = "0"; drawForecast(p);
      });
      p.dataset.lvl = "0"; p.dataset.ent = "0";
    }
    drawForecast(p);
  }

  function drawForecast(p) {
    var lvl = +(p.dataset.lvl || 0), entIdx = +(p.dataset.ent || 0);
    var wrap = p.querySelector("[data-c=entwrap]"), body = p.querySelector("[data-c=body]");
    var r, label, col = null;
    if (lvl === 0) { show(wrap, false); r = D.fc.global; label = T.allShops; }
    else {
      show(wrap, true);
      col = lvl === 1 ? "magasin" : "categorie";
      var names = lvl === 1 ? D.meta.stores : D.meta.cats;
      p.querySelector("[data-c=entlabel]").textContent = lvl === 1 ? T.store : T.cat;
      if (entIdx >= names.length) entIdx = 0;
      var selE = [entIdx];
      chips(p.querySelector("[data-c=ent]"), names, selE, function () {
        if (selE.length > 1) selE.splice(0, selE.length - 1);
        p.dataset.ent = selE[0]; drawForecast(p);
      });
      label = names[entIdx]; r = D.fc[col][label];
    }
    body.innerHTML = '<div class="ck-kpis">' +
      kpiCard(T.fcCa, eur(r.total_next), '<div class="ck-kpi-d ' + (r.growth > 0 ? "up" : r.growth < 0 ? "down" : "flat") + '">' + signed(r.growth, 1) + T.fcVs + "</div>") +
      kpiCard(T.fcRel, r.mape === null ? "—" : "± " + pct(r.mape, 1) + " %", "") +
      kpiCard(T.fcModel, r.model, "") +
      '</div><h4 class="ck-sub">' + T.fcTitle(label) + "</h4>" +
      '<div class="ck-legend"><span><i style="background:' + C.vert + '"></i>' + T.history + '</span>' +
      '<span><i style="background:' + C.or + '"></i>' + T.forecast + '</span>' +
      '<span><i style="background:rgba(184,145,58,.35)"></i>' + T.band + "</span></div>" +
      '<div class="ck-chart" data-c=fc></div>' +
      '<div class="ck-alert ' + (r.growth <= -2 ? "bad" : r.growth >= 2 ? "good" : "info") + '" style="margin-top:12px">' +
      (r.growth <= -2 ? T.fcDown(signed(r.growth, 1), label) : r.growth >= 2 ? T.fcUp(signed(r.growth, 1), label) : T.fcFlat(signed(r.growth, 1), label)) +
      "</div>";
    forecastChart(body.querySelector("[data-c=fc]"), {
      histX: r.hist.x, histY: r.hist.y, fcX: r.fc.x, fcY: r.fc.y, lo: r.lo, hi: r.hi
    });
    if (lvl > 0) {
      var rows = D.recap[col];
      var html = '<h4 class="ck-sub">' + T.recap(lvl === 1 ? T.byStore : T.byCat) + '</h4><div class="ck-table-wrap"><table class="ck-table"><thead><tr>' +
        "<th>" + (lvl === 1 ? T.store : T.cat) + '</th><th class="num">' + T.colCa + '</th><th class="num">' + T.colGrowth + "</th><th>" + T.colModel + '</th><th class="num">' + T.colMape + "</th></tr></thead><tbody>";
      rows.forEach(function (x) {
        html += "<tr><td>" + x.nom + '</td><td class="num">' + eur(x.ca) + '</td><td class="num ' + (x.croissance > 0 ? "up" : x.croissance < 0 ? "down" : "") + '">' + signed(x.croissance, 1) + ' %</td><td>' + x.modele + '</td><td class="num">' + (x.mape === null ? "—" : "± " + pct(x.mape, 1) + " %") + "</td></tr>";
      });
      body.insertAdjacentHTML("beforeend", html + "</tbody></table></div>");
    }
  }

  function download() {
    var idx = window.__ckExport || [];
    var head = EN ? "date,store,category,product,quantity,revenue,margin" : "date,magasin,categorie,produit,quantite,ca_ttc,marge";
    var lines = [head];
    idx.forEach(function (i) {
      lines.push([iso(dayToDate(D.c.d[i])), D.meta.stores[D.c.m[i]], D.meta.cats[D.c.c[i]],
        D.meta.prods[D.c.p[i]], D.c.q[i], (D.c.ca[i] / 100).toFixed(2), (D.c.mg[i] / 100).toFixed(2)].join(","));
    });
    var blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "export_maison_lauret.csv";
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  /* ---------------- demarrage ---------------- */
  var src = ROOT.getAttribute("data-src");
  fetch(src, { credentials: "omit" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(boot)
    .catch(function (e) {
      show(ROOT.querySelector("[data-f=empty]"), true);
      ROOT.querySelector("[data-f=empty]").textContent = (EN ? "The demo data could not be loaded." : "Les données de la démonstration n'ont pas pu être chargées.") + " (" + e.message + ")";
    });
})();

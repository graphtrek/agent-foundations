/* Shared UI-language support for the static pages (catalog.html, eval.html).
 *
 * The pages are written in Hungarian; English comes from a phrase map each
 * page registers. The setting (auto | hu | en) is stored under the same
 * localStorage key as the chat page, so one choice applies to every page.
 * "auto" follows the browser language.
 *
 *   UILang.register({ "Hungarian phrase": "English", ... }, [[/regex/, "repl $1"]]);
 *   UILang.tr("Hungarian phrase")   -> text in the current UI language
 *   UILang.mark(root, selector, "text"|"menu")  -> translate those elements now and on every change
 *   UILang.mount(parent)            -> adds the language selector
 *   UILang.onChange(fn)             -> called after the language changed
 */
(function () {
  "use strict";
  var KEY = "bankOfficerLang";
  var phrases = {}, patterns = [], listeners = [], marked = [];
  var setting = "auto";
  try { var s = localStorage.getItem(KEY); if (s === "hu" || s === "en") setting = s; } catch (e) { /* ignore */ }

  function browserLang() { return (navigator.language || "hu").slice(0, 2) === "hu" ? "hu" : "en"; }
  function lang() { return setting === "auto" ? browserLang() : setting; }

  function tr(text) {
    if (lang() === "hu" || typeof text !== "string") return text;
    if (Object.prototype.hasOwnProperty.call(phrases, text)) return phrases[text];
    for (var i = 0; i < patterns.length; i++) {
      if (patterns[i][0].test(text)) return text.replace(patterns[i][0], patterns[i][1]);
    }
    return text;
  }

  /* "A > B > C" menu paths are translated segment by segment. */
  function trMenu(text) { return text.split(" > ").map(tr).join(" > "); }

  function apply() {
    document.documentElement.lang = lang();
    marked.forEach(function (m) {
      m.nodes.forEach(function (n) {
        if (m.kind === "html") {
          if (n.dataset.hu === undefined) n.dataset.hu = n.innerHTML.replace(/\s+/g, " ").trim();
          n.innerHTML = tr(n.dataset.hu);  /* trusted, static markup from the page's own map */
          return;
        }
        if (n.dataset.hu === undefined) n.dataset.hu = n.textContent;
        n.textContent = m.kind === "menu" ? trMenu(n.dataset.hu) : tr(n.dataset.hu);
      });
    });
    var title = document.querySelector("title");
    if (title) {
      if (title.dataset.hu === undefined) title.dataset.hu = title.textContent;
      title.textContent = tr(title.dataset.hu);
    }
    var sel = document.getElementById("ui-lang");
    if (sel) {
      sel.value = lang();
      sel.previousSibling && (sel.previousSibling.textContent = tr("Nyelv") + " ");
    }
    listeners.forEach(function (fn) { fn(lang()); });
  }

  window.UILang = {
    tr: tr,
    trMenu: trMenu,
    lang: lang,
    register: function (map, pats) {
      Object.keys(map).forEach(function (k) { phrases[k] = map[k]; });
      (pats || []).forEach(function (p) { patterns.push(p); });
    },
    mark: function (root, selector, kind) {
      marked.push({ nodes: Array.prototype.slice.call(root.querySelectorAll(selector)), kind: kind || "text" });
    },
    onChange: function (fn) { listeners.push(fn); },
    mount: function (parent) {
      var css = document.createElement("style");
      css.textContent = ".ui-lang{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted,#5b6472);margin-left:auto}" +
        ".ui-lang select{font:inherit;font-size:.85rem;padding:5px 8px;border-radius:8px;border:1px solid var(--border,#e1e4e9);background:var(--panel,#fff);color:var(--text,#1b1f24)}";
      document.head.appendChild(css);
      var label = document.createElement("label");
      label.className = "ui-lang";
      label.appendChild(document.createTextNode(""));
      var sel = document.createElement("select");
      sel.id = "ui-lang";
      [["en", "English"], ["hu", "Magyar"]].forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o[0];
        opt.textContent = o[1];
        sel.appendChild(opt);
      });
      sel.addEventListener("change", function () {
        setting = sel.value;
        try { localStorage.setItem(KEY, setting); } catch (e) { /* ignore */ }
        apply();
      });
      label.appendChild(sel);
      parent.appendChild(label);
    },
    apply: apply
  };
})();

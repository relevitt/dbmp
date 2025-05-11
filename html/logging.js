"use strict";
W.logging = {};

W.logging.keyboard_listener_id = undefined;
W.logging.displaying = undefined;

W.logging.set_visibility = function (v) {
  const container = document.querySelector("#logs-container");
  W.css.removeClasses(container, "logging_visible", "hidden");
  if (v == "visible") W.css.addClasses(container, "logging_visible");
  else W.css.addClasses(container, "hidden");
};

W.logging.show = function () {
  if (W.logging.visible) return;
  W.search_top.close();
  W.import.close();
  W.quarantine.close();
  W.qedit.close();
  W.logging.visible = true;
  W.logging.set_visibility("visible");
  let listener_id = W.keyboard.set_listener(W.logging.keyboard);
  W.logging.keyboard_listener_id = listener_id;
};

W.logging.close = function () {
  if (!W.logging.visible) return;
  W.logging.visible = false;
  W.logging.set_visibility("hidden");
  let listener_id = W.logging.keyboard_listener_id;
  W.keyboard.restore_previous_listener(listener_id);
};

W.logging.keyboard = function (e) {
  if (e.keyCode == 27) W.logging.close(); //escape
};

W.logging.build = function () {
  W.util.stripChildren(W.logging.LogsParent);
  W.data.logs.data.forEach(W.logging.add_log);
  W.logging.paginate();
};

W.logging.paginate = function () {
  W.paginate({
    parent: document.querySelector("#logs-paginator"),
    dataObject: W.data.logs,
    dragover: false,
    now: false,
  });
};

W.logging.filter = function (e) {
  document
    .querySelectorAll("#logs-buttons > button")
    .forEach((bn) => W.css.removeClasses(bn, "button_focus"));
  W.css.addClasses(e.target, "button_focus");
  W.data.logs.get(1000000, e.target.dataset.source);
};

W.logging.get_source = function () {
  return document.querySelector("#logs-buttons > button." + W.css.button_focus)
    .dataset.source;
};

W.logging.add_log = function (log) {
  let el = W.logging.LogTemplate.cloneNode(true);
  ["timestamp", "level", "name", "message"].forEach((field) => {
    let span = el.querySelector("." + field);
    span.textContent = log[field];
    if (field == "level") {
      W.css.addClasses(span, "logging_color_" + log.level_color);
    }
    if (field == "message") {
      W.css.addClasses(span, "logging_color_" + log.color);
      span.textContent = W.util.formatBreakableText(log[field]);
      return;
    }
    span.textContent = log[field];
  });
  W.logging.LogsParent.appendChild(el);
};

W.logging.repeating_log = function (log) {
  let el = W.logging.LogsParent.lastChild;
  if (!el) return;
  ["timestamp", "message"].forEach((field) => {
    let span = el.querySelector("." + field);
    if (span) {
      span.textContent = log[field];
    }
  });
};

W.util.ready(function () {
  W.logging.LogsParent = document.querySelector("#logs");
  // element for cloning
  W.logging.LogTemplate = document.querySelector(".log-entry");
  // now that we have it, remove it from document.body
  W.logging.LogsParent.removeChild(W.logging.LogTemplate);
  // initialisation continues ...
  document.getElementById("logs-close").onclick = W.logging.close;
  document
    .querySelectorAll("#logs-buttons > button")
    .forEach((bn) => (bn.onclick = W.logging.filter));
  W.css.addClasses(
    document.querySelector("#logs-buttons > button"),
    "button_focus",
  );
  let logs = document.getElementById("logs-container");
  logs.appendChild(document.querySelector(".mobile-nav-bar").cloneNode(true));
});

"use strict";
W.quarantine = {};

W.quarantine.keyboard_listener_ids = [];

W.quarantine.getRowAtIndex = function (n) {
  return document.getElementById("quarantine-listing").childNodes[n];
};

W.quarantine.populateRow = function (li, index) {
  li.querySelector(".f1").innerHTML = W.data.quarantine.data[index].artist;
  li.querySelector(".f2").innerHTML = W.data.quarantine.data[index].album;
};

W.quarantine.addListeners = function (el) {
  el.addEventListener("click", W.util.selectThis, false);
  el.querySelector(".f3").addEventListener("click", W.quarantine.onedit, false);
  el.querySelector(".f4").addEventListener(
    "click",
    W.quarantine.ondelete,
    false,
  );
  el.addEventListener("mousedown", W.quarantine.onmousedown, false); //To stop default selection behaviour
};

W.quarantine.build = function () {
  var ul = document.getElementById("quarantine-listing");
  var cln;
  while (ul.firstChild) {
    ul.removeChild(ul.firstChild);
  }
  for (var i = 0; i < W.data.quarantine.getViewportLength(); i++) {
    cln = W.quarantine.rowTemplate.cloneNode(true);
    W.quarantine.populateRow(cln, i);
    W.quarantine.addListeners(cln);
    ul.appendChild(cln);
  }
  W.quarantine.paginate();
};

W.quarantine.onedit = function (event) {
  event.stopPropagation();
  var target = event.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  var index = W.util.getLiIndex(target);
  W.qedit.show(W.data.quarantine.data[index].id);
};

W.quarantine.ondelete = function (event) {
  if (W.data.quarantine.cacheUpdating) {
    return;
  }
  event.stopPropagation();
  var target = event.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  var index = W.util.getLiIndex(target);
  var deletion = W.data.quarantine.data[index].id;
  var selected = document
    .querySelector("#quarantine-listing")
    .getElementsByClassName("selected");
  var selected_indices = [];
  var n;
  for (var i = 0; i < selected.length; i++) {
    n = W.util.getLiIndex(selected[i]);
    if (n != index) {
      if (index < n) {
        n--;
      }
      selected_indices.push(n);
    }
  }
  W.data.quarantine.delete_rows([index], [deletion]);
  W.quarantine.build();
  for (var i = 0; i < selected_indices.length; i++) {
    W.quarantine.getRowAtIndex(selected_indices[i]).classList.add("selected");
  }
};

W.quarantine.ondelete_selected = function (event) {
  if (W.data.quarantine.cacheUpdating) {
    return;
  }
  var selected = document.querySelectorAll("#quarantine-listing .selected");
  if (!selected.length) {
    return;
  }
  var index;
  var indices = [];
  var deletions = [];
  for (var i = selected.length - 1; i >= 0; i--) {
    index = W.util.getLiIndex(selected[i]);
    indices.push(index);
    deletions.push(W.data.quarantine.data[index].id);
  }
  W.data.quarantine.delete_rows(indices, deletions);
  W.quarantine.build();
};

W.quarantine.onmousedown = function (event) {
  event.preventDefault();
};

W.quarantine.set_visibility = function (v) {
  const container = document.querySelector("#quarantine-container");
  W.css.removeClasses(container, "quarantine_visible", "hidden");
  if (v == "visible") W.css.addClasses(container, "quarantine_visible");
  else W.css.addClasses(container, "hidden");
};

W.quarantine.show = function (get) {
  if (W.quarantine.visible) return;
  W.quarantine.visible = true;
  W.import.close();
  W.qedit.close();
  W.quarantine.set_visibility("visible");
  let listener_id = W.keyboard.set_listener(W.quarantine.escape);
  W.quarantine.keyboard_listener_ids.push(listener_id);
  get && W.data.quarantine.get(0);
};

W.quarantine.close = function () {
  if (!W.quarantine.visible) return;
  W.quarantine.visible = false;
  W.quarantine.set_visibility("hidden");
  let listener_id = W.quarantine.keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  W.util.Popup.empty();
};

W.quarantine.escape = function (e) {
  if (e.keyCode == 27) {
    W.import.show();
  }
};

W.quarantine.paginate = function () {
  W.paginate({
    parent: document.querySelector("#quarantine-paginator"),
    dataObject: W.data.quarantine,
    dragover: false,
    now: false,
  });
};

W.quarantine.duplicates = function () {
  var jsonStr = W.system.get_jsonStr("qimport.duplicates");
  var cb = function (o) {
    W.data.quarantine.get(0);
  };
  W.util.JSONpost("/json", jsonStr, cb);
};

W.quarantine.clear = function () {
  var jsonStr = W.system.get_jsonStr("qimport.clear");
  var cb = function (o) {
    W.import.show();
  };
  W.util.JSONpost("/json", jsonStr, cb);
};

W.util.ready(function () {
  document.getElementById("quarantine-close").onclick = W.quarantine.close;
  document.getElementById("quarantine-directories").onclick = W.import.show;
  document.getElementById("quarantine-clear").onclick = W.quarantine.clear;
  document.getElementById("quarantine-duplicates").onclick =
    W.quarantine.duplicates;
  document.getElementById("quarantine-delete").onclick =
    W.quarantine.ondelete_selected;
  W.quarantine.rowTemplate = document
    .querySelector("#quarantine-listing li")
    .cloneNode(true);
  const container = document.getElementById("quarantine-container");
  container.appendChild(
    document.querySelector(".mobile-nav-bar").cloneNode(true),
  );
});

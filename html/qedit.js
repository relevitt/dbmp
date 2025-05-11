"use strict";
W.qedit = {};

W.qedit.keyboard_listener_ids = [];

W.qedit.getRowAtIndex = function (n) {
  return document.getElementById("qedit-listing").childNodes[n];
};

W.qedit.populateArtistRow = function (li) {
  li.querySelector(".f1").innerHTML = "Artist";
  li.querySelector(".f2 input").value = W.data.qedit.artist;
};

W.qedit.populateAlbumRow = function (li) {
  li.querySelector(".f1").innerHTML = "Album";
  li.querySelector(".f2 input").value = W.data.qedit.album;
};

W.qedit.populateRow = function (li, index) {
  li.querySelector(".f1").innerHTML = index + 1;
  li.querySelector(".f2 input").value = W.data.qedit.data[index].title;
};

W.qedit.dragInit = function (el) {
  el.setAttribute("draggable", false);
  W.qedit.addDrag(el, true);
};

W.qedit.addDrag = function (el, yes) {
  if (yes && el.getAttribute("draggable") == "false") {
    el.setAttribute("draggable", true);
    el.addEventListener("dragstart", W.qedit.ondragstart, false);
    el.addEventListener("dragover", W.util.ondragover, false);
    el.addEventListener("dragenter", W.util.ondragenter, false);
    el.addEventListener("dragleave", W.util.ondragleave, false);
    el.addEventListener("drop", W.util.ondrop, false);
    el.addEventListener("dragend", W.util.ondragend, false);
  }
  if (!yes && el.getAttribute("draggable") == "true") {
    el.setAttribute("draggable", false);
    el.removeEventListener("dragstart", W.qedit.ondragstart);
    el.removeEventListener("dragover", W.util.ondragover);
    el.removeEventListener("dragenter", W.util.ondragenter);
    el.removeEventListener("dragleave", W.util.ondragleave);
    el.removeEventListener("drop", W.util.ondrop);
    el.removeEventListener("dragend", W.util.ondragend);
  }
};

W.qedit.addListenersArtist = function (el) {
  el.querySelector("input").addEventListener("change", function (e) {
    W.data.qedit.artist = e.target.value;
  });
};

W.qedit.addListenersAlbum = function (el) {
  el.querySelector("input").addEventListener("change", function (e) {
    W.data.qedit.album = e.target.value;
  });
};

W.qedit.addListeners = function (el) {
  var input = el.querySelector("input");
  el.addEventListener("click", W.util.selectThis, false);
  W.qedit.dragInit(el);
  input.addEventListener("focus", function (e) {
    var li = e.target;
    while (li.nodeName != "LI") {
      li = li.parentNode;
    }
    W.qedit.addDrag(li, false);
  });
  input.addEventListener("blur", function (e) {
    var li = e.target;
    while (li.nodeName != "LI") {
      li = li.parentNode;
    }
    W.qedit.addDrag(li, true);
  });
  input.addEventListener("select", function (e) {
    var sel = e.target.value.substr(
      e.target.selectionStart,
      e.target.selectionEnd,
    );
    document.querySelector("#qedit-txtinput").value = sel;
  });
  input.addEventListener("change", function (e) {
    var li = e.target;
    while (li.nodeName != "LI") {
      li = li.parentNode;
    }
    var index = W.util.getLiIndex(li);
    W.data.qedit.data[index].title = e.target.value;
  });
  el.querySelector(".f3").addEventListener(
    "click",
    function (e) {
      e.stopPropagation();
      var li = e.target;
      while (li.nodeName != "LI") {
        li = li.parentNode;
      }
      W.data.qedit.data.splice(W.util.getLiIndex(li), 1);
      W.qedit.rebuild();
    },
    false,
  );
};

W.qedit.addListenersEnd = function (el) {
  el.addEventListener("dragover", W.util.ondragover, false);
  el.addEventListener("dragenter", W.util.ondragenter, false);
  el.addEventListener("dragleave", W.util.ondragleave, false);
  el.addEventListener("drop", W.util.ondrop, false);
  el.addEventListener("dragend", W.util.ondragend, false);
};

W.qedit.rebuild = function () {
  var selected = document.querySelectorAll("#qedit-listing li.selected");
  var indices = [];
  for (var i = 0; i < selected.length; i++) {
    indices.push(W.util.getLiIndex(selected[i]));
  }
  W.qedit.build({
    selected: indices,
  });
};

W.qedit.build = function (args) {
  // args:
  // - selected

  if (args == undefined) args = {};
  var ul = document.getElementById("qedit-artist-album");
  var cln;
  while (ul.firstChild) {
    ul.removeChild(ul.firstChild);
  }
  cln = W.qedit.rowTemplateArtistAlbum.cloneNode(true);
  W.qedit.populateArtistRow(cln);
  W.qedit.addListenersArtist(cln);
  ul.appendChild(cln);
  cln = W.qedit.rowTemplateArtistAlbum.cloneNode(true);
  W.qedit.populateAlbumRow(cln);
  W.qedit.addListenersAlbum(cln);
  ul.appendChild(cln);
  ul = document.getElementById("qedit-listing");
  while (ul.firstChild) {
    ul.removeChild(ul.firstChild);
  }
  for (var i = 0; i < W.data.qedit.data.length; i++) {
    cln = W.qedit.rowTemplateSong.cloneNode(true);
    W.qedit.populateRow(cln, i);
    W.qedit.addListeners(cln);
    ul.appendChild(cln);
  }
  cln = W.qedit.lastRowTemplate.cloneNode(true);
  ul.appendChild(cln);
  W.qedit.addListenersEnd(cln);
  if (args.selected) {
    for (var i = 0; i < args.selected.length; i++) {
      W.qedit.getRowAtIndex(args.selected[i]).classList.add("selected");
    }
  }
};

W.qedit.ondragstart = function (event) {
  var nodes = [];
  var nodelist = document.querySelectorAll("#qedit-artist-album span");
  for (var i = 0; i < nodelist.length; i++) {
    nodes.push(nodelist[i]);
  }
  nodes.push(document.querySelector("#qedit-heading"));

  W.util.ondragstart({
    event: event,
    draggingclass: "qedit_dragging",
    dragoverclass: "qedit_dragover",
    dragtemplate: W.qedit.rowTemplateSong,
    dataObject: W.data.qedit,
    rowpopulate: W.qedit.populateRow,
    dragframe: document.querySelector("#qedit-container"),
    dragframeElements: nodes,
  });
};

W.qedit.ltrim = function (str, charlist) {
  charlist = !charlist
    ? " \s\xA0"
    : (charlist + "").replace(/([\[\]\(\)\.\?\/\*\{\}\+\$\^\:])/g, "\$1");
  var re = new RegExp("^[" + charlist + "]+", "g");
  return (str + "").replace(re, "");
};

W.qedit.str_replace = function (search, replace, subject) {
  var f = search,
    r = replace,
    s = subject,
    j;
  var ra = r instanceof Array,
    sa = s instanceof Array,
    f = [].concat(f),
    r = [].concat(r),
    i = (s = [].concat(s)).length;
  while (((j = 0), i--)) {
    if (s[i]) {
      while (
        ((s[i] = (s[i] + "").split(f[j]).join(ra ? r[j] || "" : r[0])),
        ++j in f)
      ) {}
    }
  }
  return sa ? s : s[0];
};

W.qedit.onStripNumbers = function () {
  var t;
  for (var i = 0; i < W.data.qedit.data.length; i++) {
    t = W.data.qedit.data[i].title;
    t = W.qedit.ltrim(t, "0123456789");
    t = W.qedit.ltrim(t);
    t = W.qedit.ltrim(t, "-");
    t = W.qedit.ltrim(t, ".");
    t = W.qedit.ltrim(t);
    W.data.qedit.data[i].title = t;
  }
  W.qedit.rebuild();
};

W.qedit.onStripText = function () {
  var t;
  for (var i = 0; i < W.data.qedit.data.length; i++) {
    t = W.data.qedit.data[i].title;
    t = W.qedit.str_replace(
      document.querySelector("#qedit-txtinput").value,
      "",
      t,
    );
    W.data.qedit.data[i].title = t;
  }
  document.querySelector("#qedit-txtinput").value = "";
  W.qedit.rebuild();
};

W.qedit.ondelete_selected = function (event) {
  var selected = document.querySelectorAll("#qedit-listing .selected");
  if (!selected.length) {
    return;
  }
  for (var i = selected.length - 1; i >= 0; i--) {
    W.data.qedit.data.splice(W.util.getLiIndex(selected[i]), 1);
  }
  W.qedit.build();
};

W.qedit.onUpdate = function (e) {
  function success(o) {
    W.data.qedit.get(o.results);
  }
  var jsonStr = W.system.get_jsonStr("qimport.update");
  jsonStr.args.artist = W.data.qedit.artist;
  jsonStr.args.album = W.data.qedit.album;
  jsonStr.args.songs = W.data.qedit.data;
  W.util.JSONpost("/json", jsonStr, success);
};

W.qedit.onImport = function (e) {
  function success(o) {
    var items = o.results;
    if (items.artist) {
      var msg = "Imported following album:\n\n";
      msg += "Artist: " + items.artist + "\n";
      msg += "Disc: " + items.album + "\n\n";
      for (var i = 0; i < items.songs.length; i++) {
        msg += i + 1 + ". " + items.songs[i] + "\n";
      }
      alert(msg);
      W.quarantine.show(true);
    } else {
      alert("Import Problem?");
    }
  }
  var jsonStr = W.system.get_jsonStr("qimport.qimport");
  jsonStr.args.artist = W.data.qedit.artist;
  jsonStr.args.album = W.data.qedit.album;
  jsonStr.args.songs = W.data.qedit.data;
  W.util.JSONpost("/json", jsonStr, success);
};

W.qedit.set_visibility = function (v) {
  const container = document.querySelector("#qedit-container");
  W.css.removeClasses(container, "qedit_visible", "hidden");
  if (v == "visible") W.css.addClasses(container, "qedit_visible");
  else W.css.addClasses(container, "hidden");
};

W.qedit.show = function (id) {
  if (W.qedit.visible) return;
  W.qedit.visible = true;
  W.quarantine.close();
  W.qedit.set_visibility("visible");
  let listener_id = W.keyboard.set_listener(W.qedit.escape);
  W.qedit.keyboard_listener_ids.push(listener_id);
  W.data.qedit.get(id);
};

W.qedit.close = function () {
  if (!W.qedit.visible) return;
  W.qedit.visible = false;
  W.util.Popup.close();
  W.qedit.set_visibility("hidden");
  let listener_id = W.qedit.keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  W.util.Popup.empty();
};

W.qedit.escape = function (e) {
  if (e.keyCode == 27) {
    W.quarantine.show();
  }
};

W.util.ready(function () {
  document.getElementById("qedit-close").onclick = W.qedit.close;
  document.getElementById("qedit-directories").onclick = W.import.show;
  document.getElementById("qedit-quarantine").onclick = W.quarantine.show;
  document.getElementById("qedit-strip").onclick = W.qedit.onStripNumbers;
  document.getElementById("qedit-striptxt").onclick = W.qedit.onStripText;
  document.getElementById("qedit-open").onclick = W.qfile.onOpenTextFile;
  document.getElementById("qedit-unlist").onclick = W.qedit.ondelete_selected;
  document.getElementById("qedit-update").onclick = W.qedit.onUpdate;
  document.getElementById("qedit-import").onclick = W.qedit.onImport;
  W.qedit.rowTemplateArtistAlbum = document
    .querySelector("#qedit-artist-album li")
    .cloneNode(true);
  W.qedit.rowTemplateSong = document
    .querySelector("#qedit-listing li")
    .cloneNode(true);
  W.qedit.lastRowTemplate = document
    .querySelectorAll("#qedit-listing li")[1]
    .cloneNode(true);
  const container = document.getElementById("qedit-container");
  container.appendChild(
    document.querySelector(".mobile-nav-bar").cloneNode(true),
  );
});

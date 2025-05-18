"use strict";
W.search_top = {};

W.searchVisible = false;
W.search_top.stored_settings = {};
W.search_top.stored_settings.is_set = false;

W.search_top.set_visibility = function (v) {
  const search = document.getElementById("search");
  W.css.removeClasses(search, "search_visible", "hidden");
  if (v == "visible") W.css.addClasses(search, "search_visible");
  else W.css.addClasses(search, "hidden");
};

W.search_top.show = function (ignore_stored_settings) {
  // NB the first parameter may be an event object,
  // in which case we're not interested in it.
  // We're interested in first parameter only if it's a
  // variable which has been set to be true

  if (W.searchVisible) return;
  W.import.close();
  W.logging.close();
  W.quarantine.close();
  W.qedit.close();
  W.searchVisible = true;
  W.search_top.set_visibility("visible");
  W.search.progress("hidden");
  window.addEventListener("resize", W.search_top.resize_fn);
  W.search.search_history = [];
  // This is used for setting/unsetting value of W.search_top.TxtInput
  W.search_top.first_search = true;
  // We store settings here if ignore_stored_settings==true.
  if (ignore_stored_settings == true) {
    W.search_top.stored_settings.object = W.search_top.object;
    W.search_top.stored_settings.category = W.search.category;
    W.search_top.stored_settings.is_set = true;
    W.search.category = "artists";
    W.search.set_search_module(W.search_top.object, true);
    W.search.set_category_buttons(W.search.category);
    return;
  }
  W.search.set_search_module(W.search_top.object);
  if (W.util.isDesktop()) W.search_top.TxtInput.focus();
};

W.search_top.close = function () {
  if (!W.searchVisible) return;
  W.search.close();
  window.removeEventListener("resize", W.search_top.resize_fn);
  if (W.search_top.stored_settings.is_set) {
    W.search.category = W.search_top.stored_settings.category;
    W.search_top.init(W.search_top.stored_settings.object);
    localStorage.setItem("search", W.search_top.stored_settings.object);
    W.search_top.stored_settings.is_set = false;
  }
  W.searchVisible = false;
  W.search_top.TxtInput.value = "";
  W.search_top.set_visibility("hidden");
};

W.search_top.cmd = function (cmd) {
  switch (W.search_top.object) {
    case "database":
      return "search." + cmd;
    case "spotify":
      return "spotify.search_" + cmd;
  }
};

W.search_top.jsonStr = function (module, cmd, args) {
  var jsonStr = W.system.get_jsonStr(module + "." + cmd, args);
  if (module == "sonos") {
    if (W.system.object == "sonos") jsonStr.args.uid = W.data.status.queue.id;
    else jsonStr.args.uid = "";
  }
  return jsonStr;
};

W.search_top.change = function (s, no_search) {
  if (W.search_top.object != s) {
    var search_term = "";
    W.search.close();
    W.search_top.init(s);
    W.search.set_search_module(s);
    localStorage.setItem("search", s);
    if (W.util.isDesktop()) W.search_top.TxtInput.focus();
    no_search || W.search.onTxtInputChanged();
  }
};

W.search_top.init = function (s) {
  W.search_top.object = s;
  var parent = document.querySelector("#search-container");
  var button_database = document.querySelector("#search-database");
  var button_spotify = document.querySelector("#search-spotify");

  [button_database, button_spotify].forEach((bn) => {
    W.css.removeClasses(bn, "st_selected");
  });

  switch (s) {
    case "database":
      W.css.addClasses(button_database, "st_selected");
      break;
    case "spotify":
      W.css.addClasses(button_spotify, "st_selected");
      break;
  }
};

W.search_top.TxtInputLastValue = "";

W.search_top.TxtInputToggle = function (state) {
  if (W.search_top.TxtInputState == state) return;
  W.search_top.TxtInputState = state;
  if (state == "on") {
    W.search_top.TxtInput.addEventListener("input", W.search_top.onTxtInput);
    if (!W.search_top.first_search)
      W.search_top.TxtInput.value = W.search_top.TxtInputLastValue;
    W.search_top.first_search = false;
    W.search_top.TxtInput.style.visibility = "visible";
  } else {
    W.search_top.TxtInput.removeEventListener("input", W.search_top.onTxtInput);
    W.search_top.TxtInputLastValue = W.search_top.TxtInput.value;
    W.search_top.TxtInput.style.visibility = "hidden";
  }
};

W.util.ready(function () {
  var s = localStorage.getItem("search");
  if (!s) s = "database";
  W.search_top.init(s);
  document.getElementById("search-escape").onclick =
    W.keyboard.simulateEscapeKey;
  document.getElementById("search-database").onclick = function () {
    W.search_top.change("database");
  };
  document.getElementById("search-spotify").onclick = function () {
    W.search_top.change("spotify");
  };
  W.search_top.TxtInput = document.getElementById("search-text");
  W.search_top.onTxtInput = W.util.debounce(W.search.onTxtInputChanged, 500);
  document.querySelectorAll(".queue-search").forEach((el) => {
    el.onclick = W.search_top.show;
  });
  document.getElementById("search-close").onclick = W.search_top.close;
  W.search_top.resize_fn = W.util.debounce(W.search.updateGridColumns, 100);
});

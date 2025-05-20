"use strict";

//We should separate the 'system' elements from the 'queue_selecter' elements in
//index.html and queue_selecter.css

W.system = {};

W.system.get_jsonStr = function (cmd, args) {
  //	This is the kitchen sink approach. Not all these arguments are
  //	required all the time, so there is redunancy, but it seems to add
  //	little in the way of overhead
  var jsonStr = {};
  jsonStr.cmd = cmd;
  jsonStr.args = args == undefined ? {} : args;
  jsonStr.args.client_id = W.system.client_id;
  jsonStr.args.sid = W.data.status.sid;
  return jsonStr;
};

W.system.create_cmd_and_get_jsonStr = function (cmd, args) {
  var jsonStr = W.system.get_jsonStr(W.system.server_module + "." + cmd, args);
  if (W.system.object == "sonos") {
    jsonStr.args.uid = jsonStr.args.id
      ? jsonStr.args.id
      : W.data.status.queue.id;
    // args.id should be redundant, if we're adding args.uid.
    // Commands that use both args.id and args.uid (see search.js and queue.js)
    // aren't being created by W.system.create_cmd_and_get_jsonStr.
    delete jsonStr.args.id;
  }
  return jsonStr;
};

W.system.change = function (s) {
  if (W.system.object != s) {
    W.system.init(s);
    localStorage.setItem("system", s)
    W.data.WS_onopen();
  }
};

W.system.relaunch_server = function () {
  var jsonStr = W.system.get_jsonStr("system.relaunch");
  W.util.JSONpost("/json", jsonStr);
};

W.system.init = function (s) {
  switch (s) {
    case "dbmp":
      W.css.removeClasses(
        document.querySelector("#system-sonos"),
        "system_selected",
      );
      W.css.addClasses(
        document.querySelector("#system-player"),
        "system_selected",
      );
      W.system.object = "dbmp";
      W.system.server_module = "db_player";
      break;
    case "sonos":
      W.css.removeClasses(
        document.querySelector("#system-player"),
        "system_selected",
      );
      W.css.addClasses(
        document.querySelector("#system-sonos"),
        "system_selected",
      );
      W.system.object = "sonos";
      W.system.server_module = "sonos";
      break;
  }
};

W.system.sectionIDs = ["queue-selecter-top", "queue-div-frame", "player"];

W.system.showSection = function (sectionId) {
  // Hide all sections
  W.system.sectionIDs.forEach((ID) => {
    const section = document.getElementById(ID);
    section.classList.add("hidden");
    section.classList.add("lg:flex");
  });
  W.search_top.close();
  W.logging.close();
  W.import.close();
  W.quarantine.close();
  W.qedit.close();
  // Show the selected section
  const section = document.getElementById(sectionId);
  section.classList.remove("hidden");
  section.classList.remove("lg:flex");
  section.classList.add("flex");
};

W.util.ready(function () {
  let s = localStorage.getItem("system");
  if (!s) s = "dbmp";
  W.system.init(s);
  let client_id = localStorage.getItem("client_id");
  if (!client_id) {
    client_id = W.util.getUUID();
    localStorage.setItem("client_id", client_id);
  }
  W.system.client_id = client_id;
  var el = document.querySelector("#system-player");
  el.onclick = function () {
    W.system.change("dbmp");
  };
  W.util.dragclick(el, 500);
  el = document.querySelector("#system-sonos");
  el.onclick = function () {
    W.system.change("sonos");
  };
  W.util.dragclick(el, 500);
});

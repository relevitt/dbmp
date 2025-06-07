"use strict";
W.queue_commands = {};

W.queue_commands.rename = function (queue, el, popup) {
  if (queue.locked || queue.system) return;
  var args = {};
  args.id = queue.id;
  if (popup) {
    W.util.getInput({
      title: "Enter new queue name:",
      cmd: "db_player.rename_queue",
      args: args,
      el: el,
    });
  } else {
    const children = [...el.children];
    el.innerHTML = "";
    W.util.input({
      el: el,
      cmd: "db_player.rename_queue",
      args: args,
      cleanup: () => {
        el.innerHTML = "";
        children.forEach(el.appendChild.bind(el));
      },
      placeholder: children[0].textContent,
    });
    el.appendChild(children[1]);
  }
};

W.queue_commands.del = function (queue) {
  if (queue.locked || queue.system) return;
  var jsonStr = W.system.get_jsonStr("db_player.delete_queue");
  jsonStr.args.id = queue.id;
  W.util.JSONpost("/json", jsonStr);
};
W.queue_commands.clear = function (queue) {
  if (queue.locked) return;
  var jsonStr;
  var args = {};
  args.id = queue.id;
  jsonStr = W.system.create_cmd_and_get_jsonStr("queue_clear", args);
  W.util.JSONpost("/json", jsonStr);
};

W.queue_commands.copySelected = function () {
  W.queue_commands.copyIndices(W.queue.getSelected(true));
};

W.queue_commands.copyIndices = function (indices) {
  if (!indices) {
    W.util.toast("No tracks were selected");
    return;
  }
  var jsonStr;
  var args = {};
  args.id = W.data.queue.id;
  args.indices = indices;
  if (args.indices.length) {
    jsonStr = W.system.create_cmd_and_get_jsonStr("copy_to_clipboard", args);
    W.util.JSONpost("/json", jsonStr);
  }
  W.util.toast("Tracks copied");
};

W.queue_commands.paste = function (queue, dest) {
  if (queue.locked) return;
  var jsonStr;
  var args = {};
  args.id = queue.id;
  args.dest = dest;
  args.snapshot_id = W.data.queue.snapshot_id;
  jsonStr = W.system.create_cmd_and_get_jsonStr("paste_from_clipboard", args);
  W.util.JSONpost("/json", jsonStr);
};

W.queue_commands.addAll = function (queue) {
  if (queue.locked) return;
  var jsonStr;
  var args = {};
  args.id = queue.id;
  jsonStr = W.system.create_cmd_and_get_jsonStr("add_all_to_queue", args);
  W.util.JSONpost("/json", jsonStr);
};

W.queue_commands.shuffle = function (queue) {
  if (queue.locked) return;
  var jsonStr;
  var args = {};
  args.id = queue.id;
  jsonStr = W.system.create_cmd_and_get_jsonStr("queue_shuffle", args);
  W.util.JSONpost("/json", jsonStr);
};

W.queue_commands.lock = function (queue, el) {
  if (queue.system) return;
  var jsonStr = W.system.get_jsonStr("db_player.lock_queue");
  jsonStr.args.id = queue.id;
  if (queue.locked) jsonStr.args.locked = 0;
  else jsonStr.args.locked = 1;
  W.util.JSONpost("/json", jsonStr);
};

W.queue_commands.detach_zone = function (queue, el) {
  var uid = queue.id;
  var zones = queue.zones;
  var items = [];
  var click = function (e) {
    var jsonStr = W.system.get_jsonStr("sonos.detach_zone");
    var index = W.util.Popup.show_options_get_index(e);
    jsonStr.args.uid = uid;
    jsonStr.args.zone = zones[index];
    W.util.Popup.close();
    W.util.JSONpost("/json", jsonStr);
  };
  for (var i = 0; i < zones.length; i++) {
    items.push({
      label: zones[i],
      click: click,
    });
  }
  W.util.Popup.show_options({
    bar: "Select zone to be detached",
    title: "Group: " + queue.name,
    items: items,
  });
  W.util.Popup.modal(true);
  W.util.Popup.move_over_element(el);
};

W.queue_commands.add_zone = function (queue, el) {
  var uid = queue.id;
  var zones = [];
  var items = [];

  // Filter zones based on system_version
  for (var i = 0; i < W.data.status.queues.length; i++) {
    if (
      queue.id != W.data.status.queues[i].id && // Exclude the current group
      queue.system_version === W.data.status.queues[i].system_version // Match system version
    ) {
      zones.push(W.data.status.queues[i]);
    }
  }

  // Create items for the popup
  for (i = 0; i < zones.length; i++) {
    items.push({
      label: zones[i].name,
      click: function (e) {
        var jsonStr = W.system.get_jsonStr("sonos.add_zone");
        var index = W.util.Popup.show_options_get_index(e);
        jsonStr.args.uid = uid;
        jsonStr.args.zone = zones[index].id;
        W.util.Popup.close();
        W.util.JSONpost("/json", jsonStr);
      },
    });
  }

  // Display the popup
  W.util.Popup.show_options({
    bar: "Select zone to be added",
    title: "Group: " + queue.name,
    items: items,
  });
  W.util.Popup.modal(true);
  W.util.Popup.move_over_element(el);
};

W.queue_commands.add_tracks = function (cb, menu_object, indices) {
  W.search_menus.submenu_one_variables.afterwards = () =>
    W.util.toast("Track(s) added");
  W.search_menus.submenu_one_variables.args = {};
  if (indices != undefined) {
    W.search_menus.submenu_one_variables.args.indices = indices;
  }
  if (W.system.object == "dbmp") {
    W.search_menus.submenu_one_variables.args.container_id =
      W.data.status.queues[W.queue_selecter.selectedIndex].id;
    W.search_menus.submenu_one_variables.args.data_source = "database";
    W.search_menus.submenu_one_variables.args.data_type = "queue";
    W.search_menus.submenu_one_variables.mode = "dbmp_queue";
    W.search_menus.create_submenu_one(cb, menu_object, "dbmp");
  } else {
    W.search_menus.submenu_one_variables.args.sonos_uid =
      W.data.status.queues[W.queue_selecter.selectedIndex].id;
    W.search_menus.submenu_one_variables.mode = "sonos_queue";
    W.search_menus.create_submenu_one(cb, menu_object, "sonos");
  }
};

W.queue_commands.transfer_queue = function (cb, menu_object) {
  W.search_menus.submenu_one_variables.afterwards = () => {
    W.util.toast("Queue transferred");
    W.data.WS_change_sonos_group(W.search_menu_utilities.last_dest_id);
  };
  W.search_menus.submenu_one_variables.args = {};
  W.search_menus.submenu_one_variables.args.sonos_uid =
    W.data.status.queues[W.queue_selecter.selectedIndex].id;
  W.search_menus.submenu_one_variables.mode = "sonos_queue";
  // W.search_menus.create_submenu_one(cb, menu_object, "sonos");
  W.search_menus.submenu_one_onclick(cb, menu_object);
};

W.queue_commands.import_artist_ids = function () {
  const popup = W.util.Popup;
  popup.empty();
  popup.cleanup = function () {
    W.css.removeClasses(this.bar, "popup_alertbar");
    this.empty();
  }.bind(popup);
  popup.bar.innerHTML = "Import Artist IDs";
  W.css.addClasses(popup.bar, "popup_alertbar");
  const div = W.popup.PopupAlert.cloneNode(true);
  let el = div.querySelector(".W-popup-alert-title");
  el.innerHTML =
    "Please select a text file containing Spotify artist IDs (one per line).";
  el = div.querySelector(".W-popup-alert-button");
  el.appendChild(
    W.button(
      "OK",
      function () {
        this.close();

        let input = document.createElement("input");
        input.type = "file";
        input.accept = ".txt";

        input.onchange = function (event) {
          const file = event.target.files[0];
          if (!file) return;

          const reader = new FileReader();
          reader.onload = function (e) {
            const text = e.target.result;
            const artist_ids = text
              .split("\n")
              .map((line) => line.trim())
              .filter((line) => line.length > 0);

            W.util.getInput({
              title: "Please enter playlist title",
              fn: (title) => {
                const args = {
                  artist_ids: artist_ids,
                  title: title,
                };
                const jsonStr = W.system.get_jsonStr(
                  "playlists.generate_playlist_from_artist_ids",
                  args,
                );
                W.util.JSONpost("/json", jsonStr);
                W.util.toast(
                  "Your playlist should appear as a new Database playlist.<BR>This may take a few minutes.",
                  5000,
                );
              },
            });
          };

          reader.readAsText(file);
        };
        input.click();
      }.bind(popup),
    ),
  );
  popup.content.appendChild(div);
  popup.show();
  popup.center();
};

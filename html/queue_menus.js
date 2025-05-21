"use strict";
W.queue_menus = {};

W.queue_menus.init = function () {
  if (W.queue.topMenu && W.queue.topMenu.system_object != W.system.object) {
    W.queue.topMenu.remove();
    delete W.queue.topMenu;
  }
  if (W.queue.topMenu == undefined) {
    var span = document.querySelector("#queue-span-name");
    if (W.data.status.queues.length) {
      W.queue.topMenu = new W.menu(W.queue_menus.getTopMenuParams());
      W.queue.topMenu.system_object = W.system.object;
      W.queue.topMenu.add(span);
      W.css.addClasses(span, "queue_top_menu");
    } else W.css.removeClasses(span, "queue_top_menu");
  }
};

W.queue_menus.getTopMenuParams = function () {
  var args = {
    showingClass: "",
    menuDirection: "bottom",
    init: W.queue_menus.topMenuInit,
  };

  args.items = [];
  if (W.system.object == "dbmp") {
    args.items.push(
      {
        onclick: W.queue.rename,
        label: "Rename",
      },
      {
        onclick: W.queue.del,
        label: "Delete",
      },
    );
  }
  args.items.push(
    {
      label: "Clear all tracks",
      onclick: W.queue.ondelete_all,
    },
    {
      label: "Clear selected tracks",
      onclick: W.queue.ondelete_selected,
    },
    {
      label: "Copy selected tracks",
      onclick: W.queue_commands.copySelected,
    },
    {
      label: "Cut selected tracks",
      onclick: function () {
        W.queue_commands.copySelected();
        W.queue.ondelete_selected();
      },
    },
    {
      label: "Paste",
      init: W.queue_menus.pasteInit,
      submenu: [
        {
          onclick: W.queue.pasteBeginning,
          label: "at beginning",
        },
        {
          onclick: W.queue.pasteTopPage,
          label: "at top of page",
        },
        {
          onclick: W.queue.pasteBeforeSelected,
          label: "before selection",
        },
        {
          onclick: W.queue.pasteEnd,
          label: "at end",
        },
      ],
    },
  );
  if (W.system.object == "dbmp") {
    args.items.push({
      label: "Add all tracks",
      onclick: W.queue.addAll,
    });
  }
  args.items.push({
    label: "Shuffle",
    onclick: W.queue.shuffle,
  });
  if (W.system.object == "sonos") {
    args.items.push(
      {
        onclick: W.queue.detach_zone,
        label: "Detach zone from group",
      },
      {
        onclick: W.queue.add_zone,
        label: "Add zone to group",
      },
    );
  }
  args.items.push(
    {
      label: "Add all tracks to",
      create_items_fn: function (cb, menu_object) {
        W.queue_commands.add_tracks(cb, menu_object);
      },
      submenu: [],
    },
    {
      label: "Add selected tracks to",
      create_items_fn: function (cb, menu_object) {
        W.queue_commands.add_tracks(cb, menu_object, W.queue.getSelected(true));
      },
      submenu: [],
    },
  );
  if (W.system.object == "sonos") {
    args.items.push(
      {
        label: "Transfer queue to",
        create_items_fn: function (cb, menu_object) {
          W.queue_commands.transfer_queue(cb, menu_object);
        },
        submenu: [],
      },
      {
        onclick: W.queue.add_local_stream,
        label: "Add local stream",
      },
    );
  }
  if (W.system.object == "dbmp") {
    args.items.push({
      onclick: W.queue.lock,
      label: "Unlock",
    });
  }
  args.items.push({
    onclick: (e) => {
      let Q = document.querySelector("#queue");
      if (Q.dataset.selectMultiple == "true") {
        Q.dataset.selectMultiple = "false";
        e.target.innerHTML = "Select multiple";
      } else {
        Q.dataset.selectMultiple = "true";
        e.target.innerHTML = "Select multiple &check;";
      }
    },
    label: "Select multiple",
  });
  return args;
};

W.queue_menus.topMenuInit = function (index, e) {
  var queue = W.data.status.queues[W.queue_selecter.selectedIndex];
  W.queue.topMenu.lockedItems = [];
  if (W.system.object == "dbmp") {
    var unlock = W.queue.topMenu.container.children.length - 2;
    var unlockText = "Lock";
    if (queue.locked) {
      W.queue.topMenu.lockedItems = [0, 1, 2, 3, 5, 6, 7, 8];
      unlockText = "Unlock";
    } else if (queue.system) {
      W.queue.topMenu.lockedItems = [0, 1, unlock];
      unlockText = "Unlock";
    }
    if (!W.queue.getSelected().length)
      W.queue.topMenu.lockedItems.push(3, 4, 5, 10);
    if (false) W.queue.topMenu.lockedItems.push(5); //TODO check whether clipboard has content
    W.queue.topMenu.container.children[unlock].innerHTML = unlockText;
  } else {
    if (!W.queue.getSelected().length)
      W.queue.topMenu.lockedItems.push(1, 2, 3, 9);
    if (false) W.queue.topMenu.lockedItems.push(3); //TODO check whether clipboard has content
    if (queue.zones.length < 2) W.queue.topMenu.lockedItems.push(6);
    if (W.data.status.queues.length < 2) W.queue.topMenu.lockedItems.push(7);
  }
};

W.queue_menus.pasteInit = function (submenu) {
  submenu.lockedItems = [];
  if (
    W.data.queue.totalRecords <= W.data.queue.pageLength ||
    W.data.queue.startIndex < W.data.queue.pageLength
  )
    submenu.lockedItems.push(1);
  if (!W.queue.getSelected().length) submenu.lockedItems.push(2);
};

W.queue_menus.trackMenu_show = function (e) {
  e.preventDefault();
  W.menus.forEach((menu) => {
    menu.hide();
  });
  if (W.queue.trackMenu.targetElement == e.target) {
    W.queue.trackMenu.targetElement = undefined;
    return;
  }
  W.queue.trackMenu.show(e);
  W.queue.trackMenu.shift(e.clientX);
};

W.queue_menus.trackMenu_click = function (e) {
  var index = W.util.getLiIndex(W.queue.trackMenu.targetElement);
  var adjusted_index = W.data.queue.startIndex + index;
  switch (e.target.innerHTML) {
    case "View artist":
    case "View album":
    case "Track recommendations":
      var o = {};
      o.target = W.queue.trackMenu.targetElement;
      W.search_top.show(true);
      if (e.target.innerHTML.indexOf("artist") !== -1)
        W.search.new_search(o, { bespoke_search: "view_artist" });
      else if (e.target.innerHTML.indexOf("recommendations") !== -1)
        W.search.new_search(o, { bespoke_search: "recommendations_track" });
      else W.search.new_search(o);
      break;
    case "Remove artist from queue":
    case "Remove album from queue":
      var jsonStr;
      var args = {};
      args.track_index = adjusted_index;
      args.remove_artist =
        e.target.innerHTML.indexOf("artist") !== -1 ? true : false;
      args.id = W.data.queue.id;
      jsonStr = W.system.create_cmd_and_get_jsonStr(
        "remove_artist_or_album_from_queue",
        args,
      );
      W.util.JSONpost("/json", jsonStr);
      break;
    case "Clear track":
      W.queue.delete_row(index);
      break;
    case "Copy track":
      W.queue_commands.copyIndices([adjusted_index]);
      break;
    case "Cut track":
      W.queue_commands.copyIndices([adjusted_index]);
      W.queue.delete_row(index);
      break;
    case "Paste before track":
      W.queue.paste(adjusted_index);
      break;
    case "Paste after track":
      W.queue.paste(adjusted_index + 1);
      break;
    default:
      break;
  }
  W.queue.trackMenu.targetElement = undefined;
};

W.queue_menus.trackMenuInit = function (index, e) {
  var queue = W.data.status.queues[W.queue_selecter.selectedIndex];
  W.queue.trackMenu.lockedItems = [];
  if (W.system.object == "dbmp") {
    if (queue.locked) {
      W.queue.trackMenu.lockedItems = [3, 4, 5, 7, 8, 10, 11, 12];
    }
  }
  if (!W.queue.getSelected().length)
    W.queue.trackMenu.lockedItems.push(8, 9, 10, 14);
  var parent = e.target;
  while (parent.nodeName != "DIV") parent = parent.parentElement;
  W.css.addClasses(parent, "queue_menu_showing");
};

W.queue_menus.trackMenuTidyUp = () => {
  var parent = W.queue.trackMenu.targetElement;
  if (!parent) return;
  while (parent.nodeName != "DIV") parent = parent.parentElement;
  W.css.removeClasses(parent, "queue_menu_showing");
};

W.util.ready(function () {
  W.queue.systemMenu = new W.menu({
    items: [
      {
        label: "Import files to database",
        onclick: W.import.filebrowser,
      },
      {
        label: "Logging",
        onclick: W.logging.show,
      },
      {
        label: "Relaunch server",
        onclick: W.system.relaunch_server,
      },
      {
        label: "Connect a Spotify Account",
        onclick: W.spotify.auth,
      },
      {
        label: "Set system password",
        onclick: W.util.setPassword,
      },
      {
        label: "Download root certificate",
        onclick: W.system.download_root_certificate,
      },
    ],
    init: () => {
      let label = W.data.password_set
        ? "Change system password"
        : "Set system password";
      let div = W.queue.systemMenu.menu_objects[4].div;
      div.innerHTML = label;
      if (!W.data.root_cert_available) W.queue.systemMenu.lockedItems = [5];
    },
    check_auth: true,
  });

  const system_buttons = document.querySelectorAll(".queue-system-menu");
  W.queue.systemMenu.add(system_buttons[0]);

  const menu_config = function () {
    if (W.queue.trackMenu && W.queue.trackMenu.showing) {
      var index = W.util.getLiIndex(W.queue.trackMenu.targetElement);
      index = index + W.data.queue.startIndex;
      W.queue.scroll_to(index);
    }
    var system_button = system_buttons[0];
    let sys_menu_showing = W.queue.systemMenu.showing;
    sys_menu_showing && W.queue.systemMenu.hide();
    if (W.util.isDesktop()) {
      W.queue.systemMenu.menuDirection = "bottom";
      W.queue.systemMenu.showingClass = "menu_selected";
      if (W.queue.trackMenu && W.queue.trackMenu.showing) {
        var parent = W.queue.trackMenu.targetElement;
        if (!parent) return;
        while (parent.nodeName != "DIV") parent = parent.parentElement;
        let rect = parent.getBoundingClientRect();
        let x = Math.floor(rect.left + rect.width / 4);
        W.queue.trackMenu.shift(x);
      }
    } else {
      system_button = system_buttons[1];
      W.queue.systemMenu.menuDirection = "topleft";
      W.queue.systemMenu.showingClass = "";
    }
    W.queue.systemMenu.parentElement = system_button;
    sys_menu_showing && W.queue.systemMenu.show({ target: system_button });
  };
  menu_config();
  W.util.mediaQuery.addEventListener("change", menu_config);

  W.queue.trackMenu = new W.menu({
    items: [
      {
        label: "View artist",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "View album",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Track recommendations",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Remove artist from queue",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Remove album from queue",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Clear track",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Copy track",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Cut track",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Clear selected tracks",
        onclick: W.queue.ondelete_selected,
      },
      {
        label: "Copy selected tracks",
        onclick: W.queue_commands.copySelected,
      },
      {
        label: "Cut selected tracks",
        onclick: function () {
          W.queue_commands.copySelected();
          W.queue.ondelete_selected();
        },
      },
      {
        label: "Paste before track",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Paste after track",
        onclick: W.queue_menus.trackMenu_click,
      },
      {
        label: "Add track to",
        create_items_fn: function (cb, menu_object) {
          W.queue_commands.add_tracks(cb, menu_object, [
            W.util.getLiIndex(W.queue.trackMenu.targetElement) +
              W.data.queue.startIndex,
          ]);
        },
        submenu: [],
      },
      {
        label: "Add selected tracks to",
        create_items_fn: function (cb, menu_object) {
          W.queue_commands.add_tracks(
            cb,
            menu_object,
            W.queue.getSelected(true),
          );
        },
        submenu: [],
      },
    ],
    init: W.queue_menus.trackMenuInit,
    showingClass: "",
    hide: W.queue_menus.trackMenuTidyUp,
    before_click: W.queue_menus.trackMenuTidyUp,
  });
});

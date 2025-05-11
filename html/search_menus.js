"use strict";
//Clean up W.search_menu.dataObject.metadata when a menu closes

W.search_menus = {};

W.search_menus.create_submenu_one = function (cb, menu_object, mode) {
  var items = [];
  const onhide = function () {
    W.search_menus.submenu_one_variables = {};
  };
  switch (mode ? mode : W.search_top.object) {
    case "sonos": //Queue menu and system object is sonos
      items.push(
        {
          label: "Sonos component",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Spotify playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Database playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
      );
      break;
    case "dbmp": //Queue menu and system object is dbmp
      items.push(
        {
          label: "Player queue",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Sonos component",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Database playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
      );
      break;
    case "database":
      items.push(
        {
          label: "Player queue",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Sonos component",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
      );
      W.search.is_it_a_playlist() &&
        items.push({
          label: "Spotify playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        });
      items.push({
        label: "Database playlist",
        create_items_fn: W.search_menus.submenu_one_onclick,
        submenu: [],
      });
      break;
    case "spotify":
      items.push(
        {
          label: "Sonos component",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Spotify playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
        {
          label: "Database playlist",
          create_items_fn: W.search_menus.submenu_one_onclick,
          submenu: [],
        },
      );
      break;
  }
  cb(items, undefined, onhide);
};

W.search_menus.submenu_one_variables = {};

W.search_menus.submenu_one_onclick = function (cb, menu_object) {
  var get_cmd;
  var create_new_item = false;
  var create_new_item_type = "";
  var jsonStr;
  var args;
  var mode = W.search_menus.submenu_one_variables.mode;
  var afterwards = W.search_menus.submenu_one_variables.afterwards;
  args = W.search_menus.submenu_one_variables.args
    ? W.search_menus.submenu_one_variables.args
    : {};
  args.clear = false;
  if (
    menu_object.menu.parentDiv &&
    menu_object.menu.parentDiv.innerHTML == "Replace"
  )
    args.clear = true;
  switch (menu_object.div.innerHTML) {
    case "Player queue":
      get_cmd = "db_player.search_queues";
      jsonStr = W.system.get_jsonStr("db_player.add_container", args);
      args.clear || (create_new_item = true);
      create_new_item_type = "queue";
      W.search_menus.last_search_dest_object = undefined;
      switch (mode) {
        case "dbmp_queue":
          break;
        default:
          jsonStr.args = W.search_menus.get_args(jsonStr.args);
          break;
      }
      break;
    case "Transfer queue to":
      get_cmd = "sonos.search_groups";
      jsonStr = W.system.get_jsonStr("sonos.transfer_queue_to_group", args);
      create_new_item = false;
      W.search_menus.last_search_dest_object = undefined;
      switch (mode) {
        case "dbmp_queue":
        case "sonos_queue":
          break;
        default:
          jsonStr.args = W.search_menus.get_args(jsonStr.args);
          break;
      }
      break;
    case "Sonos component":
      get_cmd = "sonos.search_groups";
      jsonStr = W.system.get_jsonStr("sonos.add_container_to_group", args);
      create_new_item = false;
      W.search_menus.last_search_dest_object = undefined;
      switch (mode) {
        case "dbmp_queue":
        case "sonos_queue":
          break;
        default:
          jsonStr.args = W.search_menus.get_args(jsonStr.args);
          break;
      }
      break;
    case "Spotify playlist":
      get_cmd = "spotify.search_my_playlists_editable";
      args.clear || (create_new_item = true);
      create_new_item_type = "playlist";
      switch (mode) {
        case "sonos_queue":
          jsonStr = W.system.get_jsonStr(
            "spotify.add_sonos_queue_to_playlist",
            args,
          );
          break;
        default:
          jsonStr = W.system.get_jsonStr("spotify.add_to_playlist", args);
          jsonStr.args = W.search_menus.get_args(jsonStr.args);
          W.search_menus.last_search_dest_object = "spotify";
          break;
      }
      break;
    case "Database playlist":
      get_cmd = "search.search_playlists";
      args.clear || (create_new_item = true);
      create_new_item_type = "playlist";
      switch (mode) {
        case "sonos_queue":
          jsonStr = W.system.get_jsonStr(
            "playlists.add_sonos_queue_to_playlist",
            args,
          );
          break;
        case "dbmp_queue":
          jsonStr = W.system.get_jsonStr("playlists.add_to_playlist", args);
          break;
        default:
          jsonStr = W.system.get_jsonStr("playlists.add_to_playlist", args);
          jsonStr.args = W.search_menus.get_args(jsonStr.args);
          W.search_menus.last_search_dest_object = "database";
          break;
      }
      break;
    default:
      break;
  }
  get_cmd &&
    W.search_menu_utilities.submenu_get_items(
      cb,
      menu_object,
      get_cmd,
      jsonStr,
      create_new_item,
      create_new_item_type,
      afterwards,
    );
};

W.search_menus.get_args = function (args) {
  //	This is the kitchen sink approach. Not all these arguments are
  //	required all the time, so there is redunancy, but it seems to add
  //	little in the way of overhead
  args = args == undefined ? {} : args;
  args.data_source = W.search_top.object;
  args.data_type = W.search.is_it_a_playlist() ? "playlist" : "album";
  args.container_id = W.search.dataObject.metadata.albumid;
  return args;
};

W.search_menus.after_adding = function (o) {
  //This will work for now, but once we start adding database albums, we will need to distinguish albums and playlist
  if (
    W.search_menu_utilities.last_dest_id == W.search.dataObject.metadata.albumid
  ) {
    W.search_edit.reload_data(o);
  } else if (W.search_menus.last_search_dest_object == W.search_top.object)
    W.search.refresh_data();
  W.util.toast("Track(s) added");
};

W.search_menus.track_menu_show = function (e) {
  e.preventDefault();
  W.menus.forEach((menu) => {
    menu.hide();
  });
  if (W.search_menus.track_menu.targetElement == e.target) {
    W.search_menus.track_menu.targetElement = undefined;
    return;
  }
  W.search_menus.track_menu.show(e);
  if (W.util.isDesktop()) {
    let width = W.search_menus.track_menu.frame.getBoundingClientRect().width;
    let x = Math.min(e.clientX, window.innerWidth - (width + 17) * 3);
    W.search_menus.track_menu.shift(x);
  }
};

W.search_menus.track_menu_init = function (index, e) {
  if (W.search.dataObject.metadata.highlit) {
    let LI =
      W.search.resultsUL.children[W.search.dataObject.metadata.highlit - 1];
    W.css.removeClasses(LI, "search_track_highlight");
  }
  let parent = e.target;
  while (parent.nodeName != "LI") parent = parent.parentElement;
  W.css.addClasses(parent, "search_menu_showing");
};

W.search_menus.track_menu_tidyup = () => {
  var parent = W.search_menus.track_menu.targetElement;
  if (!parent) return;
  while (parent.nodeName != "LI") parent = parent.parentElement;
  W.css.removeClasses(parent, "search_menu_showing");
  if (W.search.dataObject.metadata.highlit) {
    let LI =
      W.search.resultsUL.children[W.search.dataObject.metadata.highlit - 1];
    W.css.addClasses(LI, "search_track_highlight");
  }
};

W.search_menus.track_menu_onclick = (e) => {
  let index = W.util.getLiIndex(W.search_menus.track_menu.targetElement);
  let track = W.search.dataObject.data[index].itemid;
  let params = {};
  switch (e.target.innerHTML) {
    case "Play track now":
      params.play_now = true;
      if (W.search_top.object === "database") params.indices = [index];
      else params.tracks = [track];
      W.search.add_album(params);
      break;
    case "Play track next":
      params.play_next = true;
      if (W.search_top.object === "database") params.indices = [index];
      else params.tracks = [track];
      W.search.add_album(params);
      break;
    case "Track recommendations":
      W.search_menus.track_menu.hide();
      W.search.new_search(undefined, {
        bespoke_search: "recommendations_track",
        item_ids: [track],
      });
      break;
    case "Copy track":
      let jsonStr = W.system.get_jsonStr(
        W.search_edit.cmd("copy_to_clipboard"),
        W.search_menus.get_args(),
      );
      if (W.search_top.object == "database") jsonStr.args.indices = [index];
      else jsonStr.args.tracks = [track];
      W.util.JSONpost("/json", jsonStr);
      W.util.toast("Tracks copied");
      break;
  }
};

W.search_menus.add_track = function (cb, menu_object, index) {
  W.search_menus.submenu_one_variables.afterwards = () =>
    W.util.toast("Track added");
  W.search_menus.submenu_one_variables.args = {};
  if (index != undefined) {
    W.search_menus.submenu_one_variables.args.indices = [index];
  }
  W.search_menus.create_submenu_one(cb, menu_object);
};

W.util.ready(function () {
  W.search_menus.track_menu = new W.menu({
    showingClass: "",
    items: [
      {
        label: "Play track now",
        onclick: W.search_menus.track_menu_onclick,
      },
      {
        label: "Play track next",
        onclick: W.search_menus.track_menu_onclick,
      },
      {
        label: "Track recommendations",
        onclick: W.search_menus.track_menu_onclick,
      },
      {
        label: "Copy track",
        onclick: W.search_menus.track_menu_onclick,
      },
      {
        label: "Add track to",
        create_items_fn: function (cb, menu_object) {
          W.search_menus.add_track(
            cb,
            menu_object,
            W.util.getLiIndex(W.search_menus.track_menu.targetElement),
          );
        },
        submenu: [],
      },
    ],
    init: W.search_menus.track_menu_init,
    hide: W.search_menus.track_menu_tidyup,
    before_click: W.search_menus.track_menu_tidyup,
  });

  W.search_menus.album_menu = new W.menu({
    showingClass: "",
    items: [
      {
        label: "Play now",
        onclick: function () {
          W.search.add_album({ play_now: true });
        },
      },
      {
        label: "Play next",
        onclick: function () {
          W.search.add_album({ play_next: true });
        },
      },
      {
        label: "Add to",
        create_items_fn: function (cb) {
          W.search_menus.submenu_one_variables.afterwards =
            W.search_menus.after_adding;
          W.search_menus.create_submenu_one(cb);
        },
        submenu: [],
      },
      {
        label: "Replace",
        create_items_fn: function (cb) {
          W.search_menus.submenu_one_variables.afterwards =
            W.search_menus.after_adding;
          W.search_menus.create_submenu_one(cb);
        },
        submenu: [],
      },
    ],
  });
});

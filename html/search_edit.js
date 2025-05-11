"use strict";
W.search_edit = {};

W.search_edit.merge_albums_keyboard_listener_ids = [];
W.search_edit.move_tracks_keyboard_listener_ids = [];

W.search_edit.cmd = function (cmd) {
  switch (W.search_top.object) {
    case "database":
      return (W.search.is_it_a_playlist() ? "playlists." : "albums.") + cmd;
    case "spotify":
      return "spotify." + cmd;
  }
};

W.search_edit.init = function () {
  if (W.search.edit_mode) return;
  var el, menu_items, items, item, i;
  W.css.addClasses(W.search.resultsUL, "se_non_text_select");

  ["#search-artist-details", "#search-artist-album-details"].forEach((id) => {
    let shield = W.search_edit.Shield.cloneNode();
    document.querySelector(id).appendChild(shield);
  });

  var add_selected_submenu = {
    label: "Add selected to",
    create_items_fn: function (cb) {
      W.search_edit.exit_special_modes();
      W.search_menus.submenu_one_variables.args = {};
      W.search_menus.submenu_one_variables.afterwards =
        W.search_menus.after_adding;
      W.search_edit.get_selected_tracks(
        W.search_menus.submenu_one_variables.args,
      );
      W.search_menus.create_submenu_one(cb);
    },
    submenu: [],
  };
  var add_all_submenu = {
    label: "Add all to",
    create_items_fn: function (cb) {
      W.search_edit.exit_special_modes();
      W.search_menus.submenu_one_variables.afterwards =
        W.search_menus.after_adding;
      W.search_menus.create_submenu_one(cb);
    },
    submenu: [],
  };
  if (W.search.dataObject.metadata.editable) {
    W.search.dataObject.delete_cmd = W.search_edit.cmd(
      "delete_tracks_from_container",
    );
    W.search.dataObject.move_cmd = W.search_edit.cmd(
      "move_tracks_in_container",
    );
    //Editable playlist
    if (W.search.is_it_a_playlist()) {
      menu_items = [
        "Delete all tracks",
        "Delete selected tracks (Delete)",
        "Select all tracks (Ctrl-A)",
        "Cut selected tracks (Ctrl-X)",
        "Copy selected tracks (Ctrl-C)",
        {
          label: "Paste",
          init: function () {},
          submenu: [
            {
              onclick: W.search_edit.paste,
              label: "at beginning",
            },
            {
              onclick: W.search_edit.paste,
              label: "before selection",
            },
            {
              onclick: W.search_edit.paste,
              label: "at end",
            },
          ],
        },
        "Recommendations from selected tracks",
        "Recommendations from first five tracks",
        "Shuffle",
        "Rename",
      ];
      if (W.search_top.object == "spotify")
        menu_items.push(
          W.search.dataObject.metadata.pubic == false
            ? "Make public"
            : "Make secret",
          "Unfollow",
        );
      else menu_items.push("Delete playlist");
      menu_items.push(add_selected_submenu, add_all_submenu, "Exit");
    }
    //Editable album
    else {
      menu_items = [
        {
          label: "Change artist",
          init: W.search_edit.exit_special_modes,
          submenu: [
            {
              onclick: W.search_edit.create_artist,
              label: "Create new artist",
            },
            {
              onclick: W.search_edit.rename_artist,
              label: "Rename artist",
            },
            {
              onclick: W.search_edit.change_artist,
              label: "Search for artist",
            },
          ],
        },
        "Rename album",
        "Rename tracks",
        "Merge albums",
        {
          label: "Move selected tracks to",
          init: W.search_edit.exit_special_modes,
          submenu: [
            {
              onclick: W.search_edit.create_album,
              label: "Create new album",
            },
            {
              onclick: W.search_edit.move_tracks,
              label: "Choose album",
            },
          ],
        },
        "Delete album from database",
        "Delete selected tracks from database",
        "Select all tracks (Ctrl-A)",
        "Copy selected tracks (Ctrl-C)",
        "Recommendations from selected tracks",
        "Recommendations from first five tracks",
        add_selected_submenu,
        add_all_submenu,
        "Exit",
      ];
    }
  }
  //Not editable
  else {
    menu_items = [
      "Select all tracks (Ctrl-A)",
      "Copy selected tracks (Ctrl-C)",
      "Recommendations from selected tracks",
      "Recommendations from first five tracks",
    ];
    W.search_top.object == "spotify" &&
      W.search.is_it_a_playlist() &&
      menu_items.push(
        W.search.dataObject.metadata.followed ? "Unfollow" : "Follow",
      );
    W.search_top.object == "spotify" &&
      W.search.is_it_a_playlist() &&
      menu_items.push(
        W.search.dataObject.metadata.pubic == false
          ? "Make public"
          : "Make secret",
        "Unfollow",
      );
    menu_items.push(add_selected_submenu, add_all_submenu, "Exit");
  }
  menu_items.unshift({
    onclick: (e) => {
      let S = document.querySelector("#search-container");
      if (S.dataset.selectMultiple == "true") {
        S.dataset.selectMultiple = "false";
        e.target.innerHTML = "Select multiple";
      } else {
        S.dataset.selectMultiple = "true";
        e.target.innerHTML = "Select multiple &check;";
      }
      W.search.resultsUL.dataset.selectMultiple = S.dataset.selectMultiple;
    },
    label: "Select multiple",
  });
  W.search.edit_mode = true;
  W.search.dataObject.loadAll = true;
  W.search.dataObject.loadAllfn = W.search_edit.init_after_build;
  W.search.dataObject.loadedAll = false;
  W.search.dataObject.get_more(null, W.search.dataObject.pageLength);
  items = [];
  for (i = 0; i < menu_items.length; i++) {
    item = menu_items[i].label
      ? menu_items[i]
      : {
          label: menu_items[i],
          onclick: W.search_edit.menu_click,
        };
    items.push(item);
  }
  W.search_edit.menu = new W.menu({
    showingClass: "",
    menuDirection: "over",
    sticky: true,
    locationElement: document.querySelector("#search-artist-details-image"),
    close: W.search_edit.exit,
    items: items,
  });
  const classlist = W.search_edit.menu.innerframe.className;
  const classes = classlist.split(" ");
  const max_height = classes.filter(
    (cls) => /^max-h-\[.*\]$/.test(cls) && !/^lg:max-h-\[.*\]$/.test(cls),
  );
  W.search_edit.menu.innerframe.classList.remove(max_height);
  W.css.addClasses(W.search_edit.menu.innerframe, "se_max_height");
  W.search_edit.menu.show();
  W.search.resultsUL.dataset.selectMultiple =
    document.querySelector("#search-container").dataset.selectMultiple;
  W.util.Popup.empty();
};

W.search_edit.init_after_build = function (selected) {
  W.search.resultsUL
    .querySelectorAll(".search-track-number")
    .forEach((span) => {
      W.css.removeClasses(span, "search_track_hover_play");
    });
  if (W.search.dataObject.metadata.highlit) {
    let LI =
      W.search.resultsUL.children[W.search.dataObject.metadata.highlit - 1];
    W.css.removeClasses(LI, "search_track_highlight");
  }
  if (W.search.dataObject.metadata.editable) {
    W.search_edit.init_rows_drag();
  }
  if (selected) {
    for (var i = 0; i < selected.length; i++) {
      W.search.resultsUL.children[selected[i]].classList.add("selected");
    }
  }
  W.search.dataObject.metadata.scrollTopEdit &&
    (W.search.resultsUL.scrollTop = W.search.dataObject.metadata.scrollTopEdit);
  W.search.dataObject.metadata.scrollTopEdit = undefined;
};

W.search_edit.init_rows_drag = function () {
  var el;
  for (var i = 0; i < W.search.resultsUL.children.length; i++) {
    el = W.search.resultsUL.children[i];
    el.setAttribute("draggable", true);
    el.addEventListener("dragstart", W.search_edit.ondragstart, false);
    el.addEventListener("dragover", W.util.ondragover, false);
    el.addEventListener("dragenter", W.util.ondragenter, false);
    el.addEventListener("dragleave", W.util.ondragleave, false);
    el.addEventListener("drop", W.search_edit.ondrop, false);
    el.addEventListener("dragend", W.search_edit.ondragend, false);
  }
  el = W.search.RowBlankTrack.cloneNode(true);
  W.search.resultsUL.appendChild(el);
  el.addEventListener("dragover", W.util.ondragover, false);
  el.addEventListener("dragenter", W.util.ondragenter, false);
  el.addEventListener("dragleave", W.util.ondragleave, false);
  el.addEventListener("drop", W.search_edit.ondrop, false);
  el.addEventListener("dragend", W.search_edit.ondragend, false);
};

W.search_edit.exit_rows_drag = function () {
  var el;
  W.search.resultsUL.lastChild &&
    W.search.resultsUL.removeChild(W.search.resultsUL.lastChild);
  for (var i = 0; i < W.search.resultsUL.children.length; i++) {
    el = W.search.resultsUL.children[i];
    el.removeEventListener("dragstart", W.search_edit.ondragstart);
    el.removeEventListener("dragover", W.util.ondragover);
    el.removeEventListener("dragenter", W.util.ondragenter);
    el.removeEventListener("dragleave", W.util.ondragleave);
    el.removeEventListener("drop", W.search_edit.ondrop);
    el.removeEventListener("dragend", W.search_edit.ondragend);
    el.setAttribute("draggable", false);
  }
};

W.search_edit.exit = function (from_escape = false) {
  if (from_escape) {
    if (W.search_edit.rename_tracks_mode) {
      W.search_edit.exit_rename_tracks();
      return;
    }
  }
  var el;
  W.search_edit.exit_special_modes();
  if (W.search.dataObject.metadata.editable) {
    W.search_edit.exit_rows_drag();
  }
  W.search_edit.deselect_all();
  W.search.resultsUL
    .querySelectorAll(".search-track-number")
    .forEach((span) => {
      W.css.addClasses(span, "search_track_hover_play");
    });
  W.search.dataObject.loadAll = false;
  W.search.dataObject.loadAllfn = undefined;
  W.search.edit_mode = false;
  W.search_edit.menu.hide_now();
  W.search_edit.menu.remove();
  delete W.search_edit.menu;

  document.querySelectorAll(".search-edit-shield").forEach((shield) => {
    shield.parentNode.removeChild(shield);
  });

  if (W.search.dataObject.metadata.highlit) {
    let LI =
      W.search.resultsUL.children[W.search.dataObject.metadata.highlit - 1];
    W.css.addClasses(LI, "search_track_highlight");
  }
};

W.search_edit.select_all = function () {
  var rows = W.search.resultsUL.children;
  var drag_target_row = W.search.dataObject.metadata.editable ? 1 : 0;
  for (var i = 0; i < rows.length - drag_target_row; i++) {
    rows[i].classList.add("selected");
  }
};

W.search_edit.deselect_all = function () {
  var rows = W.search.resultsUL.getElementsByClassName("selected");
  while (rows.length) rows[0].classList.remove("selected");
};

W.search_edit.get_selected = function () {
  var indices = [];
  var selected = W.search.resultsUL.querySelectorAll(".selected");
  for (var i = 0; i < selected.length; i++) {
    indices.push(W.util.getLiIndex(selected[i]));
  }
  return indices;
};

W.search_edit.get_selected_tracks = function (args) {
  if (W.search_top.object == "database") {
    args.indices = W.search_edit.get_selected();
    return;
  }
  args.tracks = [];
  var selected = W.search_edit.get_selected();
  for (var i = 0; i < selected.length; i++) {
    args.tracks.push(W.search.dataObject.data[selected[i]].itemid);
  }
};

W.search_edit.populateRow = function (LI, index) {
  var dataRow = W.search.dataObject.data[index];
  if (W.search.is_it_a_playlist()) {
    LI.querySelector(".search-track-artist").innerHTML = dataRow.artist;
    LI.querySelector(".search-track-album").innerHTML = dataRow.album;
    LI.querySelector(".search-track-title").innerHTML = dataRow.title;
    LI.querySelector("img").src = dataRow.artURI;
  } else {
    LI.children[1].innerHTML = dataRow.title;
  }
};

W.search_edit.ondragstart = function (event) {
  W.util.ondragstart({
    event: event,
    draggingclass: "se_dragging",
    dragoverclass: "se_dragover",
    dragtemplate: W.search.is_it_a_playlist()
      ? W.search.RowArtistRecommendationsTrack
      : W.search.RowArtistAlbumTrack,
    dataObject: W.search.dataObject,
    rowpopulate: W.search_edit.populateRow,
    dragframe: document.getElementById("search-artist-right-results"),
    dragexitElements: [
      document.querySelector("#search-artist-album-details"),
      document.querySelector("#search-artist-right-subcontainer-two"),
    ],
  });
};

W.search_edit.ondrop = function (event) {
  W.util.ondrop(event, 0);
};

W.search_edit.ondragend = function (event) {
  W.util.ondragend(event);
};

W.search_edit.menu_click = function (e) {
  var cmd = e.target.innerHTML.split("(")[0].split(" ");
  cmd = cmd.length < 2 ? cmd[0] : cmd[0] + " " + cmd[1];
  cmd = cmd.toLowerCase();
  var jsonStr;
  var cb = function () {};
  var i;
  W.search_edit.exit_special_modes();
  switch (cmd) {
    case "delete all":
      jsonStr = W.system.get_jsonStr(
        W.search_edit.cmd("clear_playlist"),
        W.search_menus.get_args(),
      );
      cb = W.search_edit.reload_data;
      break;
    case "delete selected":
      W.search_edit.delete_selected();
      break;
    case "select all":
      W.search_edit.select_all();
      break;
    case "cut selected":
      W.search_edit.cut_selected();
      break;
    case "copy selected":
      W.search_edit.copy_selected();
      break;
    case "paste":
      break;
    case "recommendations from":
      var tracks = [];
      if (e.target.innerHTML.indexOf("selected") > -1) {
        var selected = W.search_edit.get_selected();
        for (i = 0; i < selected.length; i++) {
          tracks.push(W.search.dataObject.data[selected[i]].itemid);
        }
      } else {
        var len = Math.min(5, W.search.dataObject.data.length);
        for (i = 0; i < len; i++) {
          tracks.push(W.search.dataObject.data[i].itemid);
        }
      }
      if (!tracks.length) break;
      W.search_edit.exit();
      W.search.new_search(undefined, {
        bespoke_search: "recommendations_track",
        item_ids: tracks,
      });
      break;
    case "shuffle":
      jsonStr = W.system.get_jsonStr(
        W.search_edit.cmd("playlist_shuffle"),
        W.search_menus.get_args(),
      );
      jsonStr.args.len = W.search.dataObject.data.length;
      cb = W.search_edit.reload_data;
      W.search.refresh_data();
      break;
    case "rename":
    case "rename album":
      var args = W.search_menus.get_args();
      W.util.getInput({
        title:
          "Enter new " +
          (W.search.is_it_a_playlist() ? "playlist" : "album") +
          " name:",
        cmd: W.search_edit.cmd("rename_container"),
        args: args,
        el: e.target,
        cb: function (o) {
          if (o.results == undefined || o.results == "UNAUTHORISED") return;
          W.search.dataObject.metadata.album = o.results;
          document.querySelector(
            "#search-artist-album-details-name",
          ).innerHTML = o.results;
        },
      });
      W.util.Input.value = W.search.dataObject.metadata.album;
      W.search.refresh_data();
      break;
    case "rename tracks":
      W.search_edit.rename_tracks();
      break;
    case "merge albums":
      W.search_edit.merge_albums(e);
      break;
    case "make secret":
      var pubic = false;
    case "make public":
      if (pubic == undefined) var pubic = true;
      jsonStr = W.system.get_jsonStr("spotify.playlist_public");
      jsonStr.args.pubic = pubic;
      jsonStr.args.playlist_id = W.search.dataObject.metadata.albumid;
      cb = function () {
        W.search.dataObject.metadata.pubic = jsonStr.args.pubic;
        var old_dataObject =
          W.search.search_history[W.search.search_history.length - 1];
        for (i = 0; i < old_dataObject.data.length; i++) {
          if (
            old_dataObject.data[i].itemid ==
            W.search.dataObject.metadata.albumid
          ) {
            old_dataObject.data[i].pubic = jsonStr.args.pubic;
          }
        }
        for (i = 0; i < W.search_edit.menu.container.children.length; i++) {
          if (
            W.search_edit.menu.container.children[i].innerHTML == "Make public"
          ) {
            W.search_edit.menu.container.children[i].innerHTML = "Make secret";
          } else if (
            W.search_edit.menu.container.children[i].innerHTML == "Make secret"
          ) {
            W.search_edit.menu.container.children[i].innerHTML = "Make public";
          }
        }
      };
      break;
    case "follow":
      var follow = true;
    case "unfollow":
      if (follow == undefined) var follow = false;
      jsonStr = W.system.get_jsonStr("spotify.playlist_follow");
      jsonStr.args.follow = follow;
      jsonStr.args.playlist_id = W.search.dataObject.metadata.albumid;
      cb = function () {
        var old_dataObject =
          W.search.search_history[W.search.search_history.length - 1];
        if (W.search.dataObject.metadata.editable) {
          if (!jsonStr.args.follow) {
            for (i = 0; i < old_dataObject.data.length; i++) {
              if (
                old_dataObject.data[i].itemid ==
                W.search.dataObject.metadata.albumid
              ) {
                old_dataObject.data.splice(i, 1);
                old_dataObject.totalRecords--;
              }
            }
          } else {
            old_dataObject.data.push([
              W.search.dataObject.metadata.album,
              W.search.dataObject.metadata.albumid,
              W.search.dataObject.metadata.snapshot_id,
              W.search.dataObject.metadata.pubic,
              W.search.dataObject.metadata.albumArtURI,
            ]);
            old_dataObject.totalRecords++;
          }
        } else {
          W.search.dataObject.metadata.followed = jsonStr.args.follow;
          for (i = 0; i < old_dataObject.data.length; i++) {
            if (
              old_dataObject.data[i].itemid ==
              W.search.dataObject.metadata.albumid
            ) {
              old_dataObject.data[i].pubic = jsonStr.args.follow;
            }
          }
        }
        for (i = 0; i < W.search_edit.menu.container.children.length; i++) {
          if (W.search_edit.menu.container.children[i].innerHTML == "Follow") {
            W.search_edit.menu.container.children[i].innerHTML = "Unfollow";
          } else if (
            W.search_edit.menu.container.children[i].innerHTML == "Unfollow"
          ) {
            W.search_edit.menu.container.children[i].innerHTML = "Follow";
          }
        }
      };
      break;
    case "delete playlist":
    case "delete album":
      jsonStr = W.system.get_jsonStr(
        W.search_edit.cmd("delete_container"),
        W.search_menus.get_args(),
      );
      cb = function (o) {
        if (o.results && o.results == "UNAUTHORISED") return;
        W.search.refresh_data(W.search.is_it_a_playlist() ? undefined : o);
        W.search_edit.exit();
        W.search.escape();
      };
      break;
    case "exit":
      W.search_edit.exit();
      break;
    default:
      break;
  }
  jsonStr != undefined && W.util.JSONpost("/json", jsonStr, cb);
};

W.search_edit.delete_song = function (e) {
  W.search.refresh_data();
  W.search.dataObject.delete_rows([W.util.getLiIndex(e.target)]);
};

W.search_edit.delete_selected = function () {
  if (!W.search.dataObject.metadata.editable) return;
  W.search.refresh_data();
  W.search.dataObject.delete_rows(W.search_edit.get_selected().reverse());
};

W.search_edit.reload_data = function (o) {
  if (!o.results || o.results.status == "ERROR") return;
  W.search.refresh_data();
  W.search.dataObject.metadata.scrollTopEdit = W.search.resultsUL.scrollTop;
  W.search.dataObject.metadata.snapshot_id = o.results.snapshot_id;
  W.search.dataObject.empty();
  W.search.dataObject.get();
};

W.search_edit.copy_selected = function () {
  var jsonStr = W.system.get_jsonStr(
    W.search_edit.cmd("copy_to_clipboard"),
    W.search_menus.get_args(),
  );
  W.search_edit.get_selected_tracks(jsonStr.args);
  if (
    (jsonStr.args.tracks && !jsonStr.args.tracks.length) ||
    (jsonStr.args.indices && !jsonStr.args.indices.length)
  ) {
    W.util.toast("No tracks were selected");
    return;
  }
  W.util.JSONpost("/json", jsonStr);
  W.util.toast("Tracks copied");
};

W.search_edit.cut_selected = function () {
  if (!W.search.dataObject.metadata.editable || !W.search.is_it_a_playlist())
    return;
  W.search_edit.copy_selected();
  W.search_edit.delete_selected();
};

W.search_edit.paste = function (e, cmd) {
  if (!W.search.dataObject.metadata.editable || !W.search.is_it_a_playlist())
    return;
  if (!cmd) {
    cmd = e.target.innerHTML.split("(")[0].split(" ");
    cmd = cmd.length < 2 ? cmd[0] : cmd[0] + " " + cmd[1];
    cmd = cmd.toLowerCase();
  }
  var jsonStr = W.system.get_jsonStr(
    W.search_edit.cmd("paste_from_clipboard"),
    W.search_menus.get_args(),
  );
  jsonStr.args.snapshot_id = W.search.dataObject.metadata.snapshot_id;
  switch (cmd) {
    case "at beginning":
      jsonStr.args.dest = 0;
      break;
    case "before selection":
      var selected = W.search_edit.get_selected();
      jsonStr.args.dest = selected.length ? selected[0] : 0;
      break;
    case "at end":
      jsonStr.args.dest = W.search.dataObject.data.length;
      break;
  }
  W.util.JSONpost("/json", jsonStr, W.search_edit.reload_data);
};
W.search_edit.create_artist = function (e) {
  var args = W.search_menus.get_args();
  W.util.getInput({
    title: "Enter name of new artist:",
    cmd: W.search_edit.cmd("create_artist"),
    args: args,
    el: e.target,
    cb: function (o) {
      if (o.results == undefined || o.results == "UNAUTHORISED") return;
      W.search.dataObject.metadata.artist = o.results.artist;
      W.search.dataObject.metadata.artistid = o.results.artistid;
      W.search.dataObject.metadata.artistArtURI = o.results.artistArtURI;
      document.querySelector("#search-artist-details-name").innerHTML =
        o.results.artist;
      document.querySelector("#search-artist-details-image img").src =
        o.results.artistArtURI;
      W.search.refresh_data(o);
    },
  });
};
W.search_edit.rename_artist = function (e) {
  var args = W.search_menus.get_args();
  args.artistid = W.search.dataObject.metadata.artistid;
  W.util.getInput({
    title: "Enter new name of artist:",
    cmd: W.search_edit.cmd("rename_artist"),
    args: args,
    el: e.target,
    cb: function (o) {
      if (o.results == undefined || o.results == "UNAUTHORISED") return;
      W.search.dataObject.metadata.artist = o.results.artist;
      document.querySelector("#search-artist-details-name").innerHTML =
        o.results.artist;
      W.search.refresh_data(o);
    },
  });
  W.util.Input.value = W.search.dataObject.metadata.artist;
};

W.search_edit.change_artist = function (e) {
  W.search_edit.search_for_artist({
    element: e.target,
    on_select: W.search_edit.change_artist_save,
  });
};

W.search_edit.change_artist_save = function (artistid) {
  var jsonStr = W.system.get_jsonStr(
    W.search_edit.cmd("change_artist"),
    W.search_menus.get_args(),
  );
  jsonStr.args.artistid = artistid;
  W.util.JSONpost("/json", jsonStr, function (o) {
    if (o.results == undefined || o.results == "UNAUTHORISED") return;
    W.search.dataObject.metadata.artist = o.results.artist;
    W.search.dataObject.metadata.artistid = o.results.artistid;
    W.search.dataObject.metadata.artistArtURI = o.results.artistArtURI;
    document.querySelector("#search-artist-details-name").innerHTML =
      o.results.artist;
    document.querySelector("#search-artist-details-image img").src =
      o.results.artistArtURI;
    W.search.refresh_data(o);
  });
};

W.search_edit.search_for_artist = function (args) {
  /*
        args.element:               Element over which the popup should be
                                    positioned

        args.on_select:             Function to be called when artist is
                                    selected. It is called with the artistid
                                    and name of the selected artist

		args.cleanup:				Function to be called upon exit
    */

  var counter, artistids;
  var auto_complete = new autoComplete({
    selector: W.util.Input,
    minChars: 1,
    delay: 250,
    source: function (term, suggest) {
      var jsonStr = W.system.get_jsonStr(
        W.search_edit.cmd("search_artist"),
        W.search_menus.get_args(),
      );
      jsonStr.args.term = term.toLowerCase();
      counter = 0;
      W.util.JSONpost("/json", jsonStr, (o) => {
        artistids = o.results.artistids;
        suggest(o.results.artists);
      });
    },
    renderItem: function (item, search) {
      search = search.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
      var re = new RegExp("(" + search.split(" ").join("|") + ")", "gi");
      var div =
        '<div class="autocomplete-suggestion" data-val="' +
        item +
        '" W-index=' +
        counter++ +
        ">" +
        item.replace(re, "<b>$1</b>") +
        "</div>";
      return div;
    },
    onSelect: function (event, term, item) {
      var index = parseInt(item.getAttribute("W-index"));
      args.on_select(artistids[index], term);
      W.util.Popup.close();
    },
  });
  W.util.getInput({
    title: "Search for artist:",
    el: args.element,
    cleanup: function () {
      auto_complete.destroy;
      if (args.cleanup) args.cleanup();
    },
  });
};
W.search_edit.rename_tracks = function () {
  if (W.search_edit.rename_tracks_mode) return;
  W.search_edit.rename_tracks_mode = true;
  W.search_edit.exit_rows_drag();
  W.search_edit.rename_span_items = [];
  for (let element of W.search.resultsUL.childNodes) {
    var span = element.children[1];
    W.search_edit.rename_span_items.push(span);
    var input = document.createElement("input");
    input.value = span.innerHTML;
    element.replaceChild(input, span);
  }
  W.css.addClasses(W.search.resultsUL, "se_rename_tracks");
  var save, cancel, results_rect, input_rect, p_rect, x, y;
  W.util.Popup.bar.innerHTML = "Rename Tracks";
  save = W.button("Save (Ctrl-S)", function () {
    W.search_edit.exit_rename_tracks(true);
  });
  cancel = W.button("Cancel (Esc)", W.search_edit.exit_rename_tracks);
  W.util.Popup.content.appendChild(save);
  W.util.Popup.content.appendChild(cancel);
  W.util.Popup.cleanup = W.search_edit.exit_rename_tracks;
  W.util.Popup.resize();
  results_rect = W.search.resultsUL.getBoundingClientRect();
  p_rect = W.util.Popup.frame.getBoundingClientRect();
  x = results_rect.left;
  y = results_rect.top / 2 - (p_rect.bottom - p_rect.top) / 2;
  W.util.Popup.move(x, y);
  W.util.Popup.show();
};
W.search_edit.exit_rename_tracks = function (save = false) {
  if (!W.search_edit.rename_tracks_mode) return;
  W.search_edit.rename_tracks_mode = false;
  if (save) {
    var jsonStr = W.system.get_jsonStr(
      W.search_edit.cmd("rename_tracks"),
      W.search_menus.get_args(),
    );
    jsonStr.args.track_names = [];
  }
  for (let [index, element] of W.search.resultsUL.childNodes.entries()) {
    var input = element.children[1];
    var span = W.search_edit.rename_span_items.shift();
    if (save) jsonStr.args.track_names.push(input.value);
    span.innerHTML = W.search.dataObject.data[index].title;
    element.replaceChild(span, input);
  }
  W.css.removeClasses(W.search.resultsUL, "se_rename_tracks");
  W.search_edit.init_rows_drag();
  W.util.Popup.empty();
  W.util.Popup.close();
  if (save) {
    W.util.JSONpost("/json", jsonStr, function (o) {
      if (o.results == undefined || o.results == "UNAUTHORISED") return;
      for (let [index, track_name] of o.results.entries()) {
        W.search.dataObject.data[index].title = track_name;
        W.search.resultsUL.childNodes[index].children[1].innerHTML = track_name;
      }
    });
  }
};
W.search_edit.merge_albums = function (e) {
  if (W.search_edit.merge_albums_mode) return;
  W.search_edit.merge_albums_mode = true;
  var jsonStr = W.system.get_jsonStr(
    W.search_edit.cmd("search_artist_albums"),
    W.search_menus.get_args(),
  );
  jsonStr.args.artistid = W.search.dataObject.metadata.artistid;
  W.util.JSONpost("/json", jsonStr, (o) => {
    if (!o.results.albumids.length) {
      W.search_edit.merge_albums_mode = false;
      W.util.Popup.alert({
        title: "There are no other albums for this artist",
      });
    } else {
      W.search_edit.merge_albums_albumids = [
        W.search.dataObject.metadata.albumid,
      ].concat(o.results.albumids);
      display_albums(
        [W.search.dataObject.metadata.album].concat(o.results.albums),
      );
    }
  });
  var display_albums = function (albums) {
    var radio_counter,
      top_div,
      div,
      span,
      inputs,
      buttons,
      results_rect,
      popup_rect,
      popup_height,
      viewport_height,
      x,
      y;
    W.util.Popup.bar.innerHTML = "Choose albums to merge:";
    top_div = W.search_edit.MergeContainer.cloneNode(true);
    W.util.Popup.content.appendChild(top_div);
    radio_counter = 0;
    var sync_check_to_radio = function (e) {
      var div, radio_button, checkbox;
      div = e.target;
      while (div.nodeName != "DIV") {
        div = div.parentNode;
      }
      radio_button = div.querySelectorAll("input")[0];
      checkbox = div.querySelectorAll("input")[1];
      radio_button.checked && (checkbox.checked = true);
    };
    albums.forEach(function (album, index) {
      div = W.search_edit.MergeAlbums.cloneNode(true);
      span = div.querySelector("span");
      span.innerHTML = album;
      inputs = div.querySelectorAll("input");
      inputs[0].id = "W_merge_albums_radio_button_" + radio_counter++;
      !index && (inputs[0].checked = true);
      inputs[0].onclick = sync_check_to_radio;
      inputs[1].id = "W_merge_albums_checkbox_" + radio_counter++;
      !index && (inputs[1].checked = true);
      inputs[1].onclick = sync_check_to_radio;
      top_div.appendChild(div);
    });
    let listener_id = W.keyboard.set_listener(function (e) {
      if (e.keyCode == 27) W.search_edit.merge_albums_exit(); //escape
      if (e.ctrlKey && e.keyCode == 83) {
        e.preventDefault();
        W.search_edit.merge_albums_exit(true); //Ctrl-S
      }
    });
    W.search_edit.merge_albums_keyboard_listener_ids.push(listener_id);
    W.util.Popup.cleanup = W.search_edit.merge_albums_exit;
    div = W.search_edit.MergeButtons.cloneNode(true);
    buttons = div.querySelectorAll(".W-button");
    buttons[0].onclick = function () {
      W.search_edit.merge_albums_exit(true);
    };
    buttons[1].onclick = function () {
      W.search_edit.merge_albums_exit(false);
    };
    top_div.appendChild(div);
    W.util.Popup.resize();
    results_rect = W.search.resultsUL.getBoundingClientRect();
    popup_rect = W.util.Popup.frame.getBoundingClientRect();
    popup_height = popup_rect.bottom - popup_rect.top;
    viewport_height = Math.max(
      document.documentElement.clientHeight,
      window.innerHeight || 0,
    );
    x = results_rect.left;
    y = Math.min(results_rect.top, viewport_height / 2 - popup_height / 2);
    W.util.Popup.move(x, y);
    W.util.Popup.show();
  };
};

W.search_edit.merge_albums_exit = function (save = false) {
  if (!W.search_edit.merge_albums_mode) return;
  if (save) {
    var merge_to;
    var merge_from = [];
    W.util.Popup.content
      .querySelectorAll(".search-edit-merge-albums")
      .forEach(function (div, index) {
        if (div.querySelectorAll("input")[0].checked)
          merge_to = W.search_edit.merge_albums_albumids[index];
        else if (div.querySelectorAll("input")[1].checked)
          merge_from.push(W.search_edit.merge_albums_albumids[index]);
      });
    var jsonStr = W.system.get_jsonStr(
      W.search_edit.cmd("merge_albums"),
      W.search_menus.get_args(),
    );
    jsonStr.args.snapshot_id = W.search.dataObject.metadata.snapshot_id;
    jsonStr.args.merge_to = merge_to;
    jsonStr.args.merge_from = merge_from;
  }
  W.search_edit.merge_albums_albumids = undefined;
  W.search_edit.merge_albums_mode = false;
  W.util.Popup.empty();
  W.util.Popup.content.classList.remove("search-edit-merge-container");
  W.util.Popup.close();
  let listener_id = W.search_edit.merge_albums_keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  save &&
    W.util.JSONpost("/json", jsonStr, function (o) {
      if (o.results == undefined || o.results == "UNAUTHORISED") return;
      var exit = false;
      o.results.merge_from &&
        o.results.merge_from.forEach((results) => {
          results.container_id == W.search.dataObject.metadata.albumid &&
            (exit = true);
          W.search.refresh_data({ results: results });
        });
      if (exit) {
        W.search_edit.exit();
        W.search.escape();
      } else W.search_edit.reload_data(o);
    });
};

W.search_edit.create_album = function (e) {
  var args = W.search_menus.get_args();
  args.snapshot_id = W.search.dataObject.metadata.snapshot_id;
  args.indices = W.search_edit.get_selected();
  W.util.getInput({
    title: "Enter name of new album:",
    cmd: W.search_edit.cmd("create_album"),
    args: args,
    el: e.target,
    cb: W.search_edit.move_tracks_callback,
  });
};

W.search_edit.move_tracks_callback = function (o) {
  if (o.results == undefined || o.results == "UNAUTHORISED") return;
  if (o.results.album_empty) {
    W.search.refresh_data(o);
    W.search_edit.exit();
    W.search.escape();
  } else W.search_edit.reload_data(o);
};

W.search_edit.move_tracks = function (e) {
  if (W.search_edit.move_tracks_mode) return;
  if (!W.search_edit.get_selected().length) {
    W.util.Popup.alert({
      title: "No tracks have been selected.",
    });
    return;
  }

  W.search_edit.move_tracks_mode = true;

  // This flag is used to detect if the user escapes from
  // selecting a different artist - i.e. without actually
  // selecting a different artist. In that case, we want to redisplay
  // the move_tracks popup.
  W.search_edit.move_tracks_changed_artist = false;

  var get_albums = function (artistid, artist) {
    var jsonStr = W.system.get_jsonStr(
      W.search_edit.cmd("search_artist_albums"),
      W.search_menus.get_args(),
    );
    jsonStr.args.artistid = artistid;
    W.util.JSONpost("/json", jsonStr, (o) => {
      if (!o.results.albumids.length) {
        W.search_edit.move_tracks_mode = false;
        W.util.Popup.alert({
          title: "There are no other albums for this artist",
        });
      } else {
        W.search_edit.move_tracks_albumids = o.results.albumids;
        display_albums(artist, o.results.albums);
      }
    });
  };

  var change_artist = function (e) {
    W.search_edit.move_tracks_exit();
    // Not 100% sure why we have to set this as true, but
    // life's too short to worry too much about it.
    W.search_edit.move_tracks_mode = true;
    W.search_edit.search_for_artist({
      element: W.search.resultsUL,
      on_select: change_artist_execute,
      cleanup: function () {
        // Redisplay move_tracks if the user escaped
        if (!W.search_edit.move_tracks_changed_artist) {
          // If we don't set it to false, move_tracks
          // will quit.
          W.search_edit.move_tracks_mode = false;
          W.search_edit.move_tracks();
        }
      },
    });
  };

  var change_artist_execute = function (artistid, artist) {
    // We set this flag to true to distinguish this situation
    // from one in which the user exited without selecting
    // a different artist
    W.search_edit.move_tracks_changed_artist = true;
    get_albums(artistid, artist);
  };

  var display_albums = function (artist, albums) {
    var radio_counter,
      top_div,
      div,
      span,
      input,
      buttons,
      results_rect,
      popup_rect,
      popup_height,
      viewport_height,
      x,
      y;
    // It should by now be safe to reset this flag
    W.search_edit.move_tracks_changed_artist = false;
    W.util.Popup.bar.innerHTML = "Choose album to which tracks will be moved:";
    top_div = W.search_edit.MoveTracksContainer.cloneNode(true);
    W.util.Popup.content.appendChild(top_div);
    span = top_div.querySelector("span");
    span.innerHTML = artist;
    top_div.querySelector(".W-button").onclick = change_artist;
    radio_counter = 0;
    albums.forEach(function (album, index) {
      div = W.search_edit.MoveTracksAlbums.cloneNode(true);
      span = div.querySelector("span");
      span.innerHTML = album;
      input = div.querySelector("input");
      input.id = "W_move_tracks_radio_button_" + radio_counter++;
      !index && (input.checked = true);
      top_div.appendChild(div);
    });
    let listener_id = W.keyboard.set_listener(function (e) {
      if (e.keyCode == 27) W.search_edit.move_tracks_exit(); //escape
      if (e.ctrlKey && e.keyCode == 83) {
        e.preventDefault();
        W.search_edit.move_tracks_exit(true); //Ctrl-S
      }
    });
    W.search_edit.move_tracks_keyboard_listener_ids.push(listener_id);
    W.util.Popup.cleanup = W.search_edit.move_tracks_exit;
    div = W.search_edit.MoveTracksButtons.cloneNode(true);
    buttons = div.querySelectorAll(".W-button");
    buttons[0].onclick = function () {
      W.search_edit.move_tracks_exit(true);
    };
    buttons[1].onclick = function () {
      W.search_edit.move_tracks_exit(false);
    };
    top_div.appendChild(div);
    W.util.Popup.resize();
    results_rect = W.search.resultsUL.getBoundingClientRect();
    popup_rect = W.util.Popup.frame.getBoundingClientRect();
    popup_height = popup_rect.bottom - popup_rect.top;
    viewport_height = Math.max(
      document.documentElement.clientHeight,
      window.innerHeight || 0,
    );
    x = results_rect.left;
    y = Math.min(results_rect.top, viewport_height / 2 - popup_height / 2);
    W.util.Popup.move(x, y);
    W.util.Popup.show();
  };

  get_albums(
    W.search.dataObject.metadata.artistid,
    W.search.dataObject.metadata.artist,
  );
};

W.search_edit.move_tracks_exit = function (save = false) {
  if (!W.search_edit.move_tracks_mode) return;
  if (save) {
    var move_to;
    W.util.Popup.content
      .querySelectorAll(".search-edit-move-tracks-albums")
      .forEach(function (div, index) {
        if (div.childNodes[1].querySelector("input").checked)
          move_to = W.search_edit.move_tracks_albumids[index];
      });
    var jsonStr = W.system.get_jsonStr(
      W.search_edit.cmd("move_tracks_to_album"),
      W.search_menus.get_args(),
    );
    jsonStr.args.snapshot_id = W.search.dataObject.metadata.snapshot_id;
    jsonStr.args.move_to = move_to;
    jsonStr.args.indices = W.search_edit.get_selected();
  }
  W.search_edit.move_tracks_albumids = undefined;
  W.search_edit.move_tracks_mode = false;
  W.util.Popup.empty();
  W.util.Popup.content.classList.remove("search-edit-move-tracks-container");
  W.util.Popup.close();
  let listener_id = W.search_edit.move_tracks_keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  save && W.util.JSONpost("/json", jsonStr, W.search_edit.move_tracks_callback);
};

W.search_edit.exit_special_modes = function () {
  W.search_edit.exit_rename_tracks();
  W.search_edit.merge_albums_exit();
  W.search_edit.move_tracks_exit();
};

W.util.ready(function () {
  // Get elements
  W.search_edit.Shield = document.body.querySelector(".search-edit-shield");
  W.search_edit.MergeContainer = document.body.querySelector(
    ".search-edit-merge-container",
  );
  W.search_edit.MergeAlbums = document.body.querySelector(
    ".search-edit-merge-albums",
  );
  W.search_edit.MergeButtons = document.body.querySelector(
    ".search-edit-merge-buttons",
  );
  W.search_edit.MoveTracksContainer = document.body.querySelector(
    ".search-edit-move-tracks-container",
  );
  W.search_edit.MoveTracksAlbums = document.body.querySelector(
    ".search-edit-move-tracks-albums",
  );
  W.search_edit.MoveTracksButtons = document.body.querySelector(
    ".search-edit-move-tracks-buttons",
  );
  // Remove them from document.body
  document.body.removeChild(W.search_edit.Shield);
  W.search_edit.MergeAlbums.parentNode.removeChild(W.search_edit.MergeAlbums);
  W.search_edit.MergeButtons.parentNode.removeChild(W.search_edit.MergeButtons);
  document.body.removeChild(W.search_edit.MergeContainer);
  W.search_edit.MoveTracksAlbums.parentNode.removeChild(
    W.search_edit.MoveTracksAlbums,
  );
  W.search_edit.MoveTracksButtons.parentNode.removeChild(
    W.search_edit.MoveTracksButtons,
  );
  document.body.removeChild(W.search_edit.MoveTracksContainer);
});

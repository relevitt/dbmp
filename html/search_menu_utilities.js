"use strict";
W.search_menu_utilities = {};

W.search_menu_utilities.submenu_get_items = function (
  cb,
  menu_object,
  get_cmd,
  jsonStr,
  create_new_item,
  create_new_item_type,
  afterwards,
) {
  W.search_menu_utilities.dataObject.get_cmd = get_cmd;
  W.search_menu_utilities.dataObject.metadata.cb = cb;
  W.search_menu_utilities.dataObject.metadata.menu_object = menu_object;
  W.search_menu_utilities.dataObject.metadata.jsonStr = jsonStr;
  W.search_menu_utilities.dataObject.metadata.create_new_item = create_new_item;
  W.search_menu_utilities.dataObject.metadata.create_new_item_type =
    create_new_item_type;
  W.search_menu_utilities.dataObject.metadata.afterwards = afterwards;
  W.search_menu_utilities.dataObject.get("");
};

W.search_menu_utilities.submenu_build = function () {
  var items = [];
  const jsonStr = W.search_menu_utilities.dataObject.metadata.jsonStr;
  if (jsonStr.args.sonos_uid) {
    W.search_menu_utilities.dataObject.data.forEach((item, index, data) => {
      if (item.itemid == jsonStr.args.sonos_uid) {
        data.splice(index, 1);
      }
    });
  }
  var s = W.search_menu_utilities.dataObject.startIndex;
  !s &&
    W.search_menu_utilities.dataObject.metadata.create_new_item &&
    items.push({
      label:
        "Create new " +
        W.search_menu_utilities.dataObject.metadata.create_new_item_type,
      onclick: W.search_menu_utilities.submenu_onclick_new,
    });
  for (var i = s; i < W.search_menu_utilities.dataObject.data.length; i++) {
    W.search_menu_utilities.dataObject.data[i].title &&
      items.push({
        label: W.search_menu_utilities.dataObject.data[i].title,
        onclick: W.search_menu_utilities.submenu_onclick,
      });
  }
  !s &&
    W.search_menu_utilities.dataObject.metadata.cb(
      items,
      W.search_menu_utilities.scroll,
      W.search_menu_utilities.submenu_onhide,
    );
  s &&
    W.search_menu_utilities.dataObject.metadata.menu_object.menu.submenuShowing.add_items(
      items,
      true,
    );
};

W.search_menu_utilities.submenu_onclick = function (e) {
  const children =
    W.search_menu_utilities.dataObject.metadata.menu_object.menu.submenuShowing.children();
  var index = Array.prototype.indexOf.call(children, e.target);
  var counter = 0;
  var dest_id;
  W.search_menu_utilities.dataObject.metadata.create_new_item && index--;
  for (var i = 0; i < W.search_menu_utilities.dataObject.data.length; i++) {
    if (W.search_menu_utilities.dataObject.data[i].itemid) {
      if (counter == index) break;
      counter++;
    }
  }
  dest_id = W.search_menu_utilities.dataObject.data[i].itemid;
  W.search_menu_utilities.dataObject.metadata.jsonStr.args.dest_id = dest_id;
  W.search_menu_utilities.last_dest_id = dest_id;
  W.search_menu_utilities.dataObject.metadata.jsonStr.cmd &&
    W.util.JSONpost(
      "/json",
      W.search_menu_utilities.dataObject.metadata.jsonStr,
      W.search_menu_utilities.dataObject.metadata.afterwards,
    );
};

W.search_menu_utilities.submenu_onclick_new = function (e) {
  W.search.refresh_data();
  const item_type =
    W.search_menu_utilities.dataObject.metadata.create_new_item_type;
  W.util.getInput({
    title: `Please enter ${item_type} name`,
    cmd: W.search_menu_utilities.dataObject.metadata.jsonStr.cmd,
    args: W.search_menu_utilities.dataObject.metadata.jsonStr.args,
    el: e.target,
    cb: () => {
      W.util.toast(`New ${item_type} created`);
    },
  });
};

W.search_menu_utilities.scroll = function (e) {
  if (
    e.target.scrollTop + e.target.clientHeight >
    0.9 * e.target.scrollHeight
  ) {
    W.search_menu_utilities.dataObject.get_more();
  }
};

W.search_menu_utilities.submenu_onhide = function () {
  W.search_menu_utilities.dataObject.empty();
  W.util.strip_object(W.search_menu_utilities.dataObject.metadata);
  W.search_menu_utilities.dataObject.metadata = {};
};

W.util.ready(function () {
  W.search_menu_utilities.dataObject = new W.lazyDataObject({
    pageLength: 100,
    build_cmd: W.search_menu_utilities.submenu_build,
    get_cmd: undefined,
    get_function: undefined,
    progress_fn: [
      function () {
        W.search.progress("visible");
      },
      function () {
        W.search.progress("hidden");
      },
    ],
  });
});

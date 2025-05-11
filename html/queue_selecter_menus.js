"use strict";
W.queue_selecter_menus = {};

W.queue_selecter_menus.init = function () {
  if (
    W.queue_selecter.menu &&
    W.queue_selecter.menu.system_object != W.system.object
  ) {
    W.queue_selecter.menu.remove();
    delete W.queue_selecter.menu;
  }
  if (W.queue_selecter.menu == undefined) {
    W.queue_selecter.menu = new W.menu(W.queue_selecter_menus.getMenuParams());
    W.queue_selecter.menu.system_object = W.system.object;
  }
};

W.queue_selecter_menus.getMenuParams = function () {
  var args = {
    showClass: ".queue-selecter-item-f2",
    init: W.queue_selecter_menus.menuInit,
    hide: W.queue_selecter_menus.menuHide,
  };
  args.items = [];
  if (W.system.object == "dbmp") {
    args.items.push(
      {
        onclick: W.queue_selecter.rename,
        label: "Rename",
      },
      {
        onclick: W.queue_selecter.del,
        label: "Delete",
      },
    );
  }
  args.items.push(
    {
      onclick: W.queue_selecter.clear,
      label: "Clear all tracks",
    },
    {
      submenu: [
        {
          onclick: W.queue_selecter.pasteBeginning,
          label: "at beginning",
        },
        {
          onclick: W.queue_selecter.pasteTopPage,
          label: "at top of page",
        },
        {
          onclick: W.queue_selecter.pasteBeforeSelected,
          label: "before selection",
        },
        {
          onclick: W.queue_selecter.pasteEnd,
          label: "at end",
        },
      ],
      label: "Paste",
      init: W.queue_selecter_menus.pasteInit,
    },
  );
  if (W.system.object == "dbmp") {
    args.items.push({
      onclick: W.queue_selecter.addAll,
      label: "Add all tracks",
    });
  }
  args.items.push({
    onclick: W.queue_selecter.shuffle,
    label: "Shuffle",
  });
  if (W.system.object == "dbmp") {
    args.items.push({
      onclick: W.queue_selecter.lock,
      label: "Unlock",
    });
  }
  if (W.system.object == "sonos") {
    args.items.push(
      {
        onclick: W.queue_selecter.detach_zone,
        label: "Detach zone from group",
      },
      {
        onclick: W.queue_selecter.add_zone,
        label: "Add zone to group",
      },
    );
  }
  return args;
};

W.queue_selecter_menus.menuInit = function (index, e) {
  let parent = e.target;
  while (!parent.classList.contains("queue-selecter-item"))
    parent = parent.parentNode;
  if (W.queue_selecter.menu.rightArrow)
    W.css.removeClasses(W.queue_selecter.menu.rightArrow, "qs_menu_arrow");
  if (W.queue_selecter.menu.queueItem)
    W.css.removeClasses(W.queue_selecter.menu.queueItem, "qs_menu_showing");
  W.queue_selecter.menu.rightArrow = parent.querySelector(
    ".queue-selecter-item-f3",
  );
  W.queue_selecter.menu.queueItem = parent.querySelector(
    ".queue-selecter-item-innerframe",
  );
  W.css.addClasses(W.queue_selecter.menu.rightArrow, "qs_menu_arrow");
  W.css.addClasses(W.queue_selecter.menu.queueItem, "qs_menu_showing");
  W.queue_selecter.menu.lockedItems = [];
  if (W.system.object == "dbmp") {
    if (W.util.inputShowing) {
      if (
        e.target == W.util.inputParent.querySelector(".queue-selecter-item-f2")
      )
        return false;
      W.util.inputHide();
    }
    var unlock = W.queue_selecter.menu.container.children.length - 1;
    var unlockText = "Lock";
    if (W.data.status.queues[index].locked) {
      W.queue_selecter.menu.lockedItems = [0, 1, 2, 3, 4, 5];
      unlockText = "Unlock";
    } else if (W.data.status.queues[index].system) {
      W.queue_selecter.menu.lockedItems = [0, 1, unlock];
      unlockText = "Unlock";
    }
    if (false) W.queue_selecter.menu.lockedItems.push(3); //TODO check whether clipboard has content
    W.queue_selecter.menu.container.children[unlock].innerHTML = unlockText;
  } else {
    if (W.data.status.queues[index].zones.length < 2)
      W.queue_selecter.menu.lockedItems.push(3);
    if (W.data.status.queues.length < 2)
      W.queue_selecter.menu.lockedItems.push(4);
  }
};

W.queue_selecter_menus.pasteInit = function (submenu) {
  submenu.lockedItems = [];
  if (
    W.data.status.queues[W.queue_selecter.menu.index].id != W.data.queue.id ||
    W.data.queue.totalRecords <= W.data.queue.pageLength ||
    W.data.queue.startIndex < W.data.queue.pageLength
  )
    submenu.lockedItems.push(1);
  if (
    W.data.status.queues[W.queue_selecter.menu.index].id != W.data.queue.id ||
    !W.queue.getSelected().length
  )
    submenu.lockedItems.push(2);
};

W.queue_selecter_menus.menuHide = function () {
  W.css.removeClasses(W.queue_selecter.menu.rightArrow, "qs_menu_arrow");
  W.css.removeClasses(W.queue_selecter.menu.queueItem, "qs_menu_showing");
  W.queue_selecter.menu.rightArrow = undefined;
  W.queue_selecter.menu.queueItem = undefined;
};

W.util.ready(function () {
  W.util.mediaQuery.addEventListener("change", () => {
    if (W.util.isDesktop()) W.queue_selecter.menu.reset_position();
  });
});

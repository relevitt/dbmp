"use strict";
W.queue_selecter = {};

W.queue_selecter.dragoverEl = 0;
W.queue_selecter.dragoverEl_time = 0;

W.queue_selecter.build = function () {
  var heading = document.querySelector("#queue-selecter-heading");
  var add = document.querySelector("#queue-selecter-add-frame");
  var div = document.querySelector("#queue-selecter");
  var cln;
  W.util.stripChildren(div);
  W.util.stripChildren(add, false);
  W.queue_selecter_menus.init();

  // Set main heading
  if (W.system.object == "sonos") {
    heading.innerHTML = "S2 Groups:";
  } else {
    heading.innerHTML = "Queues:";
    add.appendChild(W.queue_selecter.addQueueDiv);
  }

  // Iterate through queues and append them under the correct subheading
  var s1Appended = false;
  for (var i = 0; i < W.data.status.queues.length; i++) {
    var queue = W.data.status.queues[i];

    // If switching to S1 groups, append the S1 subheading
    if (queue.system_version === "S1" && !s1Appended) {
      div.appendChild(W.queue_selecter.Subheading.cloneNode(true));
      s1Appended = true;
    }

    // Clone row template and populate fields
    cln = W.queue_selecter.rowTemplate.cloneNode(true);
    var f1 = cln.querySelector(".queue-selecter-item-f1");
    var f2 = cln.querySelector(".queue-selecter-item-f2");
    f1.innerHTML = queue.name;
    f1.dataset.active_queue = queue.id == W.data.queue.id ? true : false;

    // Add interaction or highlight selection
    f1.onclick = function (e) {
      const change_queue = W.queue_selecter.change.bind(e.target);
      if (e.target.dataset.active_queue == "false") change_queue();
      W.system.showSection("player");
    };
    if (queue.id != W.data.queue.id) {
      W.css.addClasses(f1, "qs_link");
      W.util.dragclick(f1, 500);
    } else {
      W.queue_selecter.selectedIndex = i;
      if (W.data.status.queues.length > 1) W.css.addClasses(cln, "qs_selected");
    }

    // Special styling for first Sonos group
    if (!i && W.system.object == "sonos") {
      W.css.addClasses(cln.querySelector("div"), "qs_sonos_first_div");
    }

    // Add menu button
    f2.classList.add("W-menu-button");
    W.queue_selecter.menu.add(f2);

    // Append the row to the main container
    div.appendChild(cln);
  }

  // Finalize by updating playing state
  W.queue_selecter.setplaying();
};

W.queue_selecter.init = function () {
  W.queue_selecter.build();
  W.queue_selecter.setplaying();
};

W.queue_selecter.queue_name = function () {
  W.queue_selecter.setplaying();
};

W.queue_selecter.setplaying = function () {
  var playing = document.querySelector(".queue-selecter-playing");
  if (playing) W.css.removeClasses(playing, "qs_playing");
  if (W.data.status) {
    var els = document.querySelectorAll(".queue-selecter-item-f1");
    for (var i = 0; i < els.length; i++) {
      if (W.data.status.queues[i].id == W.data.status.queue.id) {
        W.css.addClasses(els[i], "qs_playing");
      }
    }
  }
};

W.queue_selecter.add_queue_click = function () {
  W.util.input({
    el: W.queue_selecter.addQueueDiv,
    cmd: "db_player.add_queue",
  });
};
W.queue_selecter.change = function () {
  var queues = document.querySelectorAll(".queue-selecter-item-f1");
  var index;
  for (var i = 0; i < queues.length; i++) {
    if (this == queues[i]) index = i;
  }
  W.queue_selecter.change_to = W.data.status.queues[index].id;
  if (W.system.object == "sonos") {
    W.data.WS_change_sonos_group(W.queue_selecter.change_to);
    return;
  }
  W.data.queue.get(-1, W.queue_selecter.change_to);
};

W.queue_selecter.rename = function () {
  W.queue_commands.rename(
    W.data.status.queues[W.queue_selecter.menu.index],
    document.querySelectorAll(".queue-selecter-item-innerframe")[
      W.queue_selecter.menu.index
    ],
  );
};

W.queue_selecter.del = function () {
  W.queue_commands.del(W.data.status.queues[W.queue_selecter.menu.index]);
};

W.queue_selecter.clear = function () {
  W.queue_commands.clear(W.data.status.queues[W.queue_selecter.menu.index]);
};

W.queue_selecter.pasteBeginning = function () {
  W.queue_selecter.paste(0);
};
W.queue_selecter.pasteTopPage = function () {
  W.queue_selecter.paste(W.data.queue.startIndex);
};
W.queue_selecter.pasteBeforeSelected = function () {
  W.queue_selecter.paste(W.queue.getSelected(true)[0]);
};
W.queue_selecter.pasteEnd = function () {
  W.queue_selecter.paste(-1);
};

W.queue_selecter.paste = function (dest) {
  W.queue_commands.paste(
    W.data.status.queues[W.queue_selecter.menu.index],
    dest,
  );
};

W.queue_selecter.addAll = function () {
  W.queue_commands.addAll(W.data.status.queues[W.queue_selecter.menu.index]);
};

W.queue_selecter.shuffle = function () {
  W.queue_commands.shuffle(W.data.status.queues[W.queue_selecter.menu.index]);
};

W.queue_selecter.lock = function (e) {
  W.queue_commands.lock(
    W.data.status.queues[W.queue_selecter.menu.index],
    e.target,
  );
};

W.queue_selecter.detach_zone = function (e) {
  W.queue_commands.detach_zone(
    W.data.status.queues[W.queue_selecter.menu.index],
    e.target,
  );
};

W.queue_selecter.add_zone = function (e) {
  W.queue_commands.add_zone(
    W.data.status.queues[W.queue_selecter.menu.index],
    e.target,
  );
};

W.queue_selecter.scroll = function () {
  if (W.queue_selecter.menu.index >= 0) W.queue_selecter.menu.reposition();
};

W.util.ready(function () {
  // Get elements
  W.queue_selecter.addQueueDiv = document.querySelector("#queue-selecter-add");
  W.queue_selecter.rowTemplate = document.querySelector(".queue-selecter-item");
  W.queue_selecter.Subheading = document.querySelector(
    ".queue-selecter-subheading",
  );
  // Remove them from document.body
  W.queue_selecter.addQueueDiv.parentNode.removeChild(
    W.queue_selecter.addQueueDiv,
  );
  W.queue_selecter.rowTemplate.parentNode.removeChild(
    W.queue_selecter.rowTemplate,
  );
  W.queue_selecter.Subheading.parentNode.removeChild(
    W.queue_selecter.Subheading,
  );
  // Continue with initalisation ...
  W.queue_selecter.addQueueDiv
    .querySelector(".queue-selecter-link")
    .addEventListener("click", W.queue_selecter.add_queue_click, true);
  W.css.addClasses(
    W.queue_selecter.addQueueDiv.querySelector(".queue-selecter-link"),
    "qs_link",
  );
  document
    .querySelector("#queue-selecter")
    .addEventListener("scroll", throttle(W.queue_selecter.scroll, 66));
});

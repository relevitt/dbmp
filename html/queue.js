"use strict";
W.queue = {};

// W.queue.getRowAtIndex returns the <li> element at index n.

W.queue.getRowAtIndex = function (n) {
  return document.getElementById("queue").childNodes[n];
};

// W.queue.getSelected

W.queue.getSelected = function (addOffset) {
  var indices = [];
  var offset = 0;
  if (addOffset) offset = W.data.queue.startIndex;
  var selected = document.querySelectorAll("#queue .selected");
  for (var i = 0; i < selected.length; i++) {
    indices.push(W.util.getLiIndex(selected[i]) + offset);
  }
  return indices;
};

/* W.queue.populateRow inserts text into each <span> child of a <li> element.
The text is taken from W.data.queue.data[index].*/

W.queue.populateRow = function (li, index) {
  var div = li.querySelector("div");
  var n = W.data.queue.startIndex + index + 1;
  div.querySelector(".f1").innerHTML = n;
  div.querySelector(".f2").innerHTML = W.data.queue.data[index].artist;
  div.querySelector(".f3").innerHTML = W.data.queue.data[index].album;
  div.querySelector(".f4").innerHTML = W.data.queue.data[index].song;
  div.querySelector(".f5").innerHTML = W.data.queue.data[index].play_time;
};

/* The next two functions are for adding event listeners to the <li>
elements.  They are split into two sections as the last <li> element in the 
queue (which has no text, and therefore can't be selected or dragged) has
only the event listeners in W.queue.addListeners2. */

W.queue.addListeners1 = function (el) {
  el.querySelectorAll(".f1-outer, .f1a").forEach((el) => {
    el.addEventListener("click", W.queue.onplay);
  });
  el.querySelector(".f8").addEventListener(
    "click",
    W.queue_menus.trackMenu_show,
  );
  el.addEventListener("contextmenu", W.queue_menus.trackMenu_show);
  el.querySelector(".f6").addEventListener("click", W.queue.ondelete);
  el.querySelectorAll(".f2, .f3, .f4, .f5, .f7").forEach((el) => {
    el.addEventListener("click", function (e) {
      W.util.selectThis(e);
      W.queue.track_song(false);
    });
  });
  el.addEventListener(
    "dblclick",
    function (o) {
      W.search_top.show(true);
      W.search.new_search(o);
    },
    false,
  );
  el.addEventListener("dragstart", W.queue.ondragstart, false);
};

W.queue.addListeners2 = function (el) {
  el.addEventListener("dragover", W.util.ondragover, false);
  el.addEventListener("dragenter", W.util.ondragenter, false);
  el.addEventListener("dragleave", W.util.ondragleave, false);
  el.addEventListener("drop", W.queue.ondrop, false);
  el.addEventListener("dragend", W.queue.ondragend, false);
};

/*
W.queue.paginate
*/

W.queue.paginate = function () {
  W.paginate({
    parent: document.querySelector("#queue-paginator"),
    dataObject: W.data.queue,
    dragover: true,
    onclick: function () {
      W.queue.track_song(false);
      W.data.queue.get(Number(this.dataset.startIndex), W.data.queue.id);
    },
    now: true,
    now_onclick: function () {
      W.queue.track_song(true);
      W.queue.go_to_now();
    },
  });
};

/*
W.queue.go_to
*/

W.queue.go_to = function (pos, now, select_pos) {
  if (
    pos < W.data.queue.startIndex ||
    pos >=
      W.data.queue.startIndex +
        Math.min(W.data.queue.data.length, W.data.queue.pageLength)
  ) {
    let start =
      Math.floor(pos / W.data.queue.pageLength) * W.data.queue.pageLength;
    W.data.queue.get(
      start,
      W.data.queue.id,
      false,
      select_pos
        ? {
            selected: [pos - start],
            fn: function () {
              W.queue.scroll_to(pos);
            },
          }
        : undefined,
    );
    return;
  }
  if (now) W.queue.scroll_to_now();
  else W.queue.scroll_to(pos, select_pos);
};

/*
W.queue.scroll_to
*/

W.queue.scroll_to = function (pos, select_pos) {
  var index, queue, li;
  var queue = document.querySelector("#queue");
  queue.focus();
  if (
    pos < W.data.queue.startIndex ||
    pos >=
      W.data.queue.startIndex +
        Math.min(W.data.queue.data.length, W.data.queue.pageLength)
  ) {
    index = 0;
  } else index = pos - W.data.queue.startIndex;
  li = W.queue.getRowAtIndex(index);
  queue.scrollTop = li.offsetTop - 200; //Can we calculate this value?
  if (select_pos) {
    W.queue.deselect_all();
    W.queue.getRowAtIndex(pos).classList.add("selected");
  }
};

/*
W.queue.go_to_now
*/

W.queue.go_to_now = function () {
  if (!W.data.queue.track_song) return;
  W.queue.go_to(W.data.queue.queue_position, true);
};

/*
W.queue.scroll_to_now
*/

W.queue.scroll_to_now = function () {
  var queue = document.querySelector("#queue");
  queue.removeEventListener("scroll", W.queue.track_song_off_debounce);
  W.queue.scroll_to(W.data.queue.queue_position);
  setTimeout(function () {
    queue.addEventListener("scroll", W.queue.track_song_off_debounce, false);
  }, 250);
};

/*
W.queue.track_song
*/

W.queue.track_song = function (on) {
  clearTimeout(W.queue.track_song.timer);
  W.data.queue.track_song = on;
  !on &&
    (W.queue.track_song.timer = setTimeout(function () {
      W.queue.track_song(true);
    }, 90000));
};

W.queue.track_song.timer = null;

W.queue.track_song_off_debounce = throttle(function () {
  W.queue.track_song(false);
});

/*
W.queue.find
*/

W.queue.find = function (again) {
  var cb = function (o) {
    W.queue.find_last_track_num = o.results;
    if (o.results == null) return;
    W.queue.go_to(o.results, false, true);
  };
  var find = function (search_term, start) {
    W.queue.find_last_search_term = search_term;
    var jsonStr = W.system.create_cmd_and_get_jsonStr("find_in_queue");
    jsonStr.args.search_term = search_term;
    jsonStr.args.start = start == undefined ? null : start;
    W.util.JSONpost("/json", jsonStr, cb);
  };
  if (again) {
    find(W.queue.find_last_search_term, W.queue.find_last_track_num);
    return;
  }
  W.util.getInput({
    title: "Enter search term",
    fn: find,
  });
};

/*  
    W.queue.build (re)builds the queue when requested by:

        W.data.queue.get
        W.data.queue.move_rows
        W.data.queue.delete_rows

    W.data.queue is an instance of W.dataObject. See W.dataObject.prototype
    for its methods.
*/

W.queue.build = function (args) {
  // args:
  // 	- selected
  // 	- preserve_scroll

  var heading = document.querySelector("#queue-header-text");
  var ul = document.querySelector("#queue");
  var cln;
  if (args.preserve_scroll == true) var scrollTop = ul.scrollTop;
  W.queue.set_name();
  switch (W.system.object) {
    default:
      heading.innerHTML = "Queue";
      break;
    case "sonos":
      heading.innerHTML = "Group";
  }
  while (ul.firstChild) {
    ul.removeChild(ul.firstChild);
  }
  const f1 = W.queue.rowTemplate.querySelector(".f1");
  if (W.data.queue.startIndex >= 99 - W.data.queue.pageLength) {
    W.css.removeClasses(f1, "queue_f1_small");
    W.css.addClasses(f1, "queue_f1_large");
  } else {
    W.css.removeClasses(f1, "queue_f1_large");
    W.css.addClasses(f1, "queue_f1_small");
  }
  for (var i = 0; i < W.data.queue.getViewportLength(); i++) {
    cln = W.queue.rowTemplate.cloneNode(true);
    cln.tabIndex = 1;
    W.queue.populateRow(cln, i);
    W.queue.addListeners1(cln);
    W.queue.addListeners2(cln);
    ul.appendChild(cln);
  }
  cln = W.queue.lastRowTemplate.cloneNode(true);
  ul.appendChild(cln);
  W.queue.addListeners2(cln);
  if (
    W.queue.dragging &&
    W.queue.dragstartIndex == W.data.queue.startIndex &&
    W.util.dragdataObjectId == W.data.queue.id
  ) {
    var row;
    for (var i = 0; i < W.util.draggedIndices.length; i++) {
      row = W.queue.getRowAtIndex(W.util.draggedIndices[i]);
      row.classList.add("selected");
      W.css.addClasses(row, "queue_dragging");
    }
  }
  W.queue.paginate();
  W.queue.setloaded();
  if (args.selected) {
    for (var i = 0; i < args.selected.length; i++) {
      W.queue.getRowAtIndex(args.selected[i]).classList.add("selected");
    }
  } else !W.queue.dragging && W.queue.scroll_to_now();
  if (args.preserve_scroll == true) ul.scrollTop = scrollTop;
};

W.queue.set_name = function () {
  document.querySelector("#queue-span-name").innerHTML = W.data.queue.label;
};

/*
Drag and drop
*/

W.queue.dragging = false;
W.queue.dragstartIndex = 0;

W.queue.ondragstart = function (event) {
  W.queue.dragging = true;
  W.queue.dragstartIndex = W.data.queue.startIndex;
  W.css.removeClasses(document.querySelector("#queue"), "queue_ul_not_dragged");
  W.util.ondragstart({
    event: event,
    draggingclass: "queue_dragging",
    dragoverclass: "queue_dragover",
    dragtemplate: W.queue.lastRowTemplate,
    dataObject: W.data.queue,
    rowpopulate: W.queue.populateRow,
    dragframe: document.getElementById("queue-div-frame"),
    dragexitElements: [
      document.querySelector("#queue-selecter-top"),
      document.querySelector("#player"),
    ],
  });
};

W.queue.ondrop = function (event) {
  W.queue.dragging = false;
  W.util.ondrop(event, W.queue.dragstartIndex);
  W.queue.setloaded();
};

W.queue.ondragend = function (event) {
  W.util.ondragend(event);
  W.queue.dragging = false;
  W.css.addClasses(document.querySelector("#queue"), "queue_ul_not_dragged");
};

/*
WS functions ...

	W.queue.setloaded
	W.queue.queue_position
	W.queue.status

*/

W.queue.getloaded = function () {
  if (
    W.data.status &&
    W.data.queue.queue_position >= W.data.queue.startIndex &&
    W.data.queue.queue_position <=
      W.data.queue.startIndex + W.data.queue.getViewportLength()
  ) {
    var pos = W.data.queue.queue_position - W.data.queue.startIndex;
    return W.queue.getRowAtIndex(pos);
  }
};

W.queue.setloaded = function () {
  const LIs = document.querySelectorAll("#queue>li");
  LIs.forEach((LI) => {
    W.css.removeClasses(LI, "queue_loaded");
  });
  const loaded = W.queue.getloaded();
  loaded && W.css.addClasses(loaded, "queue_loaded");
  W.queue.status();
};

W.queue.status = function () {
  const LIs = document.querySelectorAll("#queue>li");
  LIs.forEach((LI) => {
    W.css.removeClasses(LI, "queue_playing");
    W.css.removeClasses(LI, "queue_not_playing");
  });
  const loaded = W.queue.getloaded();
  if (loaded) {
    if (W.queue.loaded_is_playing()) {
      W.css.addClasses(loaded, "queue_playing");
    } else {
      W.css.addClasses(loaded, "queue_not_playing");
    }
  }
};

W.queue.loaded_is_playing = function () {
  if (!W.data.queue.is_playing() || !W.data.status.playing) return false;
  if (!W.data.status.playing_from_queue) return false;
  return true;
};

W.queue.queue_position = function () {
  W.queue.paginate();
  W.queue.setloaded();
  W.queue.go_to_now();
};

W.queue.queue_name = function () {
  W.queue.setloaded();
};

//W.queue.ondelete

W.queue.ondelete = function (event) {
  event.preventDefault();
  event.stopPropagation();
  W.queue.delete_row(W.util.getLiIndex(event.target));
};

//W.queue.delete_row

W.queue.delete_row = function (index) {
  if (W.queue.dragging || W.data.queue.cacheUpdating || W.data.queue.locked) {
    return;
  }
  var selected = document
    .querySelector("#queue")
    .getElementsByClassName("selected");
  var selected_indices = [];
  var n;
  for (var i = 0; i < selected.length; i++) {
    n = W.util.getLiIndex(selected[i]);
    if (n != index) {
      if (index < n) {
        n--;
      }
      selected_indices.push(n);
    }
  }
  W.data.queue.delete_rows([index], undefined, selected_indices);
};

//W.queue.ondelete_selected

W.queue.ondelete_selected = function () {
  if (W.queue.dragging || W.data.queue.cacheUpdating || W.data.queue.locked) {
    return;
  }
  var indices = W.queue.getSelected();
  if (!indices.length) return;
  indices.reverse();
  W.data.queue.delete_rows(indices);
};

//W.queue.ondelete_all

W.queue.ondelete_all = function (o) {
  W.queue_commands.clear(W.data.queue);
};

//W.queue.onplay

W.queue.onplay = function (e) {
  e.preventDefault();
  e.stopPropagation();
  var target = e.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  var index = W.util.getLiIndex(target) + W.data.queue.startIndex;
  var jsonStr;
  if (!W.data.queue.is_playing()) {
    /* We should never need to do this on sonos, because we
		should always be displaying the 'queue' (i.e. the group) that is playing.
		Therefore, haven't bothered to update this. */
    jsonStr = W.system.create_cmd_and_get_jsonStr("set_queue");
    jsonStr.args.id = W.data.queue.id;
    W.util.JSONpost("/json", jsonStr);
  } else if (
    index == W.data.queue.queue_position &&
    W.data.status.playing_from_queue
  ) {
    jsonStr = W.system.create_cmd_and_get_jsonStr("play_pause");
    W.util.JSONpost("/json", jsonStr);
    return;
  }
  jsonStr = W.system.create_cmd_and_get_jsonStr("set_queue_pos");
  jsonStr.args.position = index;
  W.util.JSONpost("/json", jsonStr);
};

//W.queue.rename

W.queue.rename = function (e) {
  W.queue_commands.rename(W.data.queue, e.target, true);
};

//W.queue.del

W.queue.del = function () {
  W.queue_commands.del(W.data.queue);
};

//Paste

W.queue.pasteBeginning = function () {
  W.queue.paste(0);
};
W.queue.pasteTopPage = function () {
  W.queue.paste(W.data.queue.startIndex);
};
W.queue.pasteBeforeSelected = function () {
  W.queue.paste(W.queue.getSelected(true)[0]);
};
W.queue.pasteEnd = function () {
  W.queue.paste(-1);
};
W.queue.paste = function (dest) {
  W.queue_commands.paste(W.data.queue, dest);
};

//W.queue.addAll

W.queue.addAll = function () {
  W.queue_commands.addAll(W.data.queue);
};

//W.queue.shuffle

W.queue.shuffle = function () {
  W.queue_commands.shuffle(W.data.queue);
};

//W.queue.lock

W.queue.lock = function (e) {
  W.queue_commands.lock(W.data.queue, e.target);
};

//W.queue.detach_zone

W.queue.detach_zone = function (e) {
  W.queue_commands.detach_zone(
    W.data.status.queues[W.queue_selecter.selectedIndex],
    e.target,
  );
};

//W.queue.add_zone

W.queue.add_zone = function (e) {
  W.queue_commands.add_zone(
    W.data.status.queues[W.queue_selecter.selectedIndex],
    e.target,
  );
};

//W.queue.add_local_stream

W.queue.add_local_stream = function (e) {
  var jsonStr = W.system.create_cmd_and_get_jsonStr("add_stream_to_queue");
  W.util.JSONpost("/json", jsonStr);
};

//W.queue.select_all

W.queue.select_all = function () {
  var rows = document.querySelectorAll("#queue LI");
  for (var i = 0; i < rows.length - 1; i++) {
    rows[i].classList.add("selected");
  }
};

//W.queue.deselect_all

W.queue.deselect_all = function () {
  var rows = document
    .querySelector("#queue")
    .getElementsByClassName("selected");
  while (rows.length) {
    rows[0].classList.remove("selected");
  }
};

//W.queue.set_queue_alert

W.queue.set_queue_alert = function (alert) {
  if (alert) {
    W.queue.set_queue_alert_showing = true;
    W.util.Popup.processing(
      undefined,
      W.queue.set_queue_alert_cleanup,
      "Waiting for file to load ...",
    );
  } else {
    W.queue.set_queue_alert_showing && W.util.Popup.processing("close");
  }
};

W.queue.set_queue_alert_cleanup = function () {
  W.queue.set_queue_alert_showing = false;
};

// Document ready ...

W.util.ready(function () {
  W.queue.rowTemplate = document.querySelector("#queue li").cloneNode(true);
  W.queue.lastRowTemplate = document
    .querySelectorAll("#queue li")[1]
    .cloneNode(true);
  var queue = document.querySelector("#queue");
  W.css.addClasses(queue, "queue_ul_not_dragged");
  queue.tabIndex = 1;
  queue.style.outline = "none";
  queue.addEventListener("scroll", W.queue.track_song_off_debounce, false);
  W.queue.track_song(true);
  W.util.mediaQuery.addEventListener("change", () => {
    W.queue.paginate();
  });
});

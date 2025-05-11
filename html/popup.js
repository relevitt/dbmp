"use strict";

W.popup = function () {
  this.keyboard_listener_ids = [];
  this.frame = W.popup.Popup.cloneNode(true);
  this.bar = this.frame.querySelector(".W-popup-bar");
  this.close_button = this.frame.querySelector(".W-popup-close");
  this.content = this.frame.querySelector(".W-popup-content");
  this.shield = W.popup.Shield.cloneNode();
  this.init = function () {}; // Runs when popup is displayed
  this.cleanup = function () {}; //Runs when popup is closed

  this.close = this.close.bind(this);
  this.constrain = W.util.debounce(W.util.constrain, 100).bind(this);
  this.ondirectoryclick = this.ondirectoryclick.bind(this);
  this.resize = this.resize.bind(this);

  W.css.removeClasses(this.frame, "popup_visible", "hidden");
  W.css.addClasses(this.frame, "hidden");
  this.frame.visible = false;

  this.close_button.onclick = this.close;

  document.body.appendChild(this.frame);
  document.body.appendChild(this.shield);
  W.util.initDrag(this.bar, this.frame);
};

W.popup.prototype.close = function (e) {
  if (!this.frame.visible) return;
  W.css.removeClasses(this.frame, "popup_visible", "hidden");
  W.css.addClasses(this.frame, "hidden");
  this.frame.visible = false;
  W.css.removeClasses(this.shield, "shield_visible", "hidden");
  W.css.addClasses(this.shield, "hidden");
  for (let listener_id of this.keyboard_listener_ids) {
    W.keyboard.restore_previous_listener(listener_id);
  }
  this.keyboard_listener_ids = [];
  window.removeEventListener("resize", this.constrain);
  this.cleanup();
};

W.popup.prototype.ondirectoryclick = function (e) {
  var arg1, arg2;
  var jsonStr = W.system.get_jsonStr("util.directory");
  if (e.target.dataset.n != undefined) {
    arg1 = "/";
    arg2 = "";
    var path = this.DirName.split("/");
    for (var i = 1; i <= Number(e.target.dataset.n); i++) {
      arg1 += path[i];
      if (i < Number(e.target.dataset.n)) arg1 += "/";
    }
  } else {
    arg1 = this.DirName;
    arg2 = e.target.dataset.dirname;
  }
  jsonStr.args.items = [arg1, arg2];
  W.util.JSONpost(
    "/json",
    jsonStr,
    function (o) {
      this.directory({
        title: this.directory_title,
        items: o.results,
        fromdirectory: true,
      });
    }.bind(this),
  );
};

W.popup.prototype.show = function () {
  if (this.frame.visible) {
    this.resize();
    this.constrain();
    return;
  }
  W.css.removeClasses(this.frame, "popup_visible", "hidden");
  W.css.addClasses(this.frame, "popup_visible");
  this.frame.visible = true;
  let listener_id = W.keyboard.set_listener(
    function (e) {
      if (e.keyCode == 27) this.close(); //escape
    }.bind(this),
  );
  this.keyboard_listener_ids.push(listener_id);
  this.init();
  this.resize();
  this.constrain();
  window.addEventListener("resize", this.constrain);
};

W.popup.prototype.toggle = function () {
  if (this.frame.visible) this.close();
  else this.show();
};

W.popup.prototype.resize = function (
  min_width,
  min_height,
  max_width,
  max_height,
) {
  // Temporarily unset size to let layout define its natural size
  this.content.style.width = "auto";
  this.content.style.height = "auto";

  // Force reflow to ensure layout is up to date
  const rect = this.content.getBoundingClientRect();
  let x = rect.width;
  let y = rect.height;

  // Apply min/max constraints
  if (min_width !== undefined) x = Math.max(x, min_width);
  if (max_width !== undefined) x = Math.min(x, max_width);
  if (min_height !== undefined) y = Math.max(y, min_height);
  if (max_height !== undefined) y = Math.min(y, max_height);

  // Enforce viewport limits
  x = Math.min(x, window.innerWidth * 0.95);
  y = Math.min(y, window.innerHeight * 0.95);

  // Apply final dimensions
  this.content.style.width = `${x}px`;
  this.content.style.height = `${y}px`;

  // Set the outer frame height (adding header if needed)
  this.frame.style.width = `${x}px`;
  this.frame.style.height = `${y + 24}px`; // adjust if 24px is your bar height
};

W.popup.prototype.empty = function () {
  this.bar.innerHTML = "";
  this.cleanup = function () {};
  W.util.stripChildren(this.content);
};

W.popup.prototype.destroy = function () {
  W.util.stripChildren(this.frame);
  document.body.removeChild(this.frame);
  document.body.removeChild(this.shield);
  var keys = Object.keys(this);
  for (var i = 0; i < keys.length; i++) {
    this[keys[i]] = undefined;
  }
  delete this;
};

W.popup.prototype.center = function (x, y) {
  x = x != undefined ? x : true;
  y = y != undefined ? y : true;
  var rect = this.frame.getBoundingClientRect();
  x &&
    (this.frame.style.left =
      "" + Math.max((window.innerWidth - rect.width) / 2, 0) + "px");
  y &&
    (this.frame.style.top =
      "" + Math.max((window.innerHeight - rect.height) / 2, 0) + "px");
};

W.popup.prototype.move_over_element = function (el) {
  var rect = el.getBoundingClientRect();
  this.move(rect.left, rect.top);
};

W.popup.prototype.move = function (x, y) {
  this.frame.style.left = "" + x + "px";
  this.frame.style.top = "" + y + "px";
};

W.popup.prototype.modal = function (mode) {
  W.css.removeClasses(this.shield, "shield_visible", "hidden");
  if (mode) {
    W.css.addClasses(this.shield, "shield_visible");
  } else {
    W.css.addClasses(this.shield, "hidden");
  }
};

W.popup.prototype.processing = function (cmd, arg, heading) {
  /*

		cmd:		undefined / 'count' / 'progress' / 'close'
		arg:		if cmd is 'count', the number of items processed so far;
				    if cmd is 'progress', the total items to be processed
                    if cmd is undefined, an optional cleanup function
		heading:	the heading to display (defaults to 'Processing ...')

	*/
  if (heading == undefined) {
    heading = "Processing ...";
  }
  if (cmd == "count") {
    var p = this.content.querySelector("progress");
    if (p) {
      p.value = arg;
    }
    this.bar.innerHTML = heading;
    return;
  }
  var d, d1, d2, i;
  var cleanup = function () {};
  this.empty();
  if (cmd == "close") {
    this.close();
    this.ticket != undefined && W.data.progress_complete(this.ticket);
    return;
  }
  if (cmd == undefined && arg != undefined) cleanup = arg;
  this.cleanup = function () {
    cleanup();
    if (this.ticket != undefined) {
      W.data.progress_cancel(this.ticket);
      this.ticket = undefined;
    }
  };
  this.bar.innerHTML = heading;
  if (cmd == "progress") {
    d = W.popup.PopupProgress.cloneNode();
    d.innerHTML = '<progress value="0" max="' + arg + '"></progress>';
  } else {
    d = W.popup.PopupProcessing.cloneNode(true);
    d1 = d.querySelector("div");
    d1.id = "fountainG";
    i = 1;
    d2 = d1.querySelectorAll("div");
    d2.forEach((div) => {
      div.id = "fountainG_" + i;
      i++;
    });
  }
  this.content.appendChild(d);
  d.style.display = "inline-block";
  d.style.width = "" + d.scrollWidth + "px";
  d.style.display = "block";
  this.show();
  this.resize(250);
  this.center();
  this.modal(true);
};

W.popup.prototype.directory = function (args) {
  /* args:
		title: the title to appear in this.bar 
		items: the data to be displayed, 
		onfileclick: the function to be called when a file link is clicked, 
		center: if true, the popup will be centered, 
		parentnode: if required, a custom parentnode,
		fromdirectory: if true, it means we were called from clicking a directory link
		onload: if required, a function to be run after the directory tree has been created
	*/

  if (!args.fromdirectory) {
    this.empty();
    this.bar.innerHTML = this.directory_title = args.title;
    this.onfileclick = args.onfileclick;
  } else {
    W.util.stripChildren(this.content.querySelector(".W-popup-directory"));
  }
  this.DirName = args.items.dirname;
  var div, el, a, t, path;
  if (args.parentnode) {
    if (!args.parentnode.querySelector(".W-popup-directory")) {
      div = W.popup.PopupDirectory.cloneNode();
      args.parentnode.appendChild(div);
    }
    this.content.appendChild(args.parentnode);
  }
  div = this.content.querySelector(".W-popup-directory");
  if (!div) {
    div = W.popup.PopupDirectory.cloneNode();
    this.content.appendChild(div);
  }
  path = this.DirName.split("/");
  el = W.popup.PopupDirectorySpan.cloneNode();
  for (var i = 0; i < path.length; i++) {
    a = W.popup.PopupDirectoryDir.cloneNode();
    if (!i) a.innerHTML = "Filesystem";
    else a.innerHTML = path[i];
    a.dataset.n = i;
    a.onclick = this.ondirectoryclick;
    a.style.textDecoration = "underline";
    el.appendChild(a);
    if (i < path.length - 1) {
      t = document.createTextNode("/");
      el.appendChild(t);
    }
  }
  t = document.createTextNode(":");
  el.appendChild(t);
  el.appendChild(document.createElement("br"));
  div.appendChild(el);
  if (args.items.dirs && args.items.dirs[0]) {
    for (i = 0; i < args.items.dirs.length; i++) {
      a = W.popup.PopupDirectoryListItemLink.cloneNode();
      a.innerHTML = "&#47;" + args.items.dirs[i] + "<br>";
      a.dataset.dirname = args.items.dirs[i];
      a.onclick = this.ondirectoryclick;
      div.appendChild(a);
    }
  }
  if (args.items.files && args.items.files[0]) {
    for (i = 0; i < args.items.files.length; i++) {
      a = this.onfileclick
        ? W.popup.PopupDirectoryListItemLink.cloneNode()
        : W.popup.PopupDirectoryListItem.cloneNode();
      a.innerHTML = args.items.files[i] + "<br>";
      this.onfileclick && (a.filename = args.items.files[i]);
      this.onfileclick && (a.onclick = this.onfileclick);
      div.appendChild(a);
    }
  }
  if (args.onload) {
    args.onload();
  }
  this.show();
  if (args.center) {
    this.center();
  }
};

W.popup.prototype.progress_init = function (process_msg, init_msg, ticket) {
  this.progress_process_msg = process_msg;
  this.progress_init_msg = init_msg;
  this.ticket = ticket;
};

W.popup.prototype.progress_total_calc = function (total_calc) {
  this.bar.innerHTML = this.progress_init_msg + total_calc;
};

W.popup.prototype.progress_total = function (total) {
  this.progress_t = total;
  this.processing(
    "progress",
    total,
    this.progress_process_msg + " 0 of " + total,
  );
};
W.popup.prototype.progress_count = function (count) {
  this.processing(
    "count",
    count,
    this.progress_process_msg + count + " of " + this.progress_t,
  );
};

W.popup.prototype.show_options = function (args) {
  /*
		args.items: an array of options to be displayed, each
			    in the form:
				items[].label: the item's label to be displayed
				items[].click: the item's onclick
		args.bar:   the text to appear in the popup bar
		args.title: the text to appear as the title
    args.title_wrap: true or false
	*/

  var div, el;
  this.empty();
  this.cleanup = function () {
    this.empty();
  };
  this.bar.innerHTML = args.bar;
  div = W.popup.PopupOptions.cloneNode(true);
  //Title
  el = div.querySelector(".W-popup-options-title");
  args.title_wrap && W.css.addClasses(el, "popup_title_wrap");
  el.innerHTML = args.title;
  //Buttons
  el = div.querySelector(".W-popup-options-buttons");
  for (var i = 0; i < args.items.length; i++) {
    el.appendChild(W.button(args.items[i].label, args.items[i].click));
    el.appendChild(document.createElement("br"));
  }
  this.content.appendChild(div);
  this.show();
  this.center();
};

W.popup.prototype.alert = function (args) {
  /*
		args.title: the text to appear as the title 
	*/

  var div, el;
  this.empty();
  this.cleanup = function () {
    W.css.removeClasses(this.bar, "popup_alertbar");
    this.empty();
  };
  this.bar.innerHTML = "Alert";
  W.css.addClasses(this.bar, "popup_alertbar");
  div = W.popup.PopupAlert.cloneNode(true);
  //Title
  el = div.querySelector(".W-popup-alert-title");
  el.innerHTML = args.title;
  //Button
  el = div.querySelector(".W-popup-alert-button");
  el.appendChild(W.button("OK", this.close));
  this.content.appendChild(div);
  this.show();
  this.center();
};

W.popup.prototype.show_options_get_index = function (e) {
  var buttons = this.content.querySelectorAll(
    ".W-popup-options-buttons .W-button",
  );
  for (var i = 0; i < buttons.length; i++) {
    if (e.target == buttons[i]) return i;
  }
};

W.popup.tooltip = function (text, el) {
  W.popup.ToolTip.innerHTML = text;
  document.body.appendChild(W.popup.ToolTip);
  const rect = el.getBoundingClientRect();
  const x = rect.right;
  const y = rect.top;
  W.popup.ToolTip.style.left = `${x + 10}px`;
  W.popup.ToolTip.style.top = `${y - 50}px`;
  const click_function = (e) => {
    document.body.removeChild(W.popup.ToolTip);
    document.removeEventListener("click", click_function);
  };
  setTimeout(() => {
    document.addEventListener("click", click_function);
  }, 100);
};

W.util.ready(function () {
  //elements for cloning
  W.popup.Popup = document.querySelector(".W-popup");
  W.popup.Shield = document.querySelector(".W-modal-shield");
  W.popup.PopupDirectory = document.querySelector(".W-popup-directory");
  W.popup.PopupDirectorySpan = document.querySelector(
    ".W-popup-directory-span",
  );
  W.popup.PopupDirectoryDir = document.querySelector(".W-popup-directory-dir");
  W.popup.PopupDirectoryListItemLink = document.querySelector(
    ".W-popup-directory-list-item-link",
  );
  W.popup.PopupDirectoryListItem = document.querySelector(
    ".W-popup-directory-list-item",
  );
  W.popup.PopupProgress = document.querySelector(".W-popup-progress");
  W.popup.PopupProcessing = document.querySelector(".W-popup-processing");
  W.popup.PopupOptions = document.querySelector(".W-popup-options");
  W.popup.PopupAlert = document.querySelector(".W-popup-alert");
  W.popup.ToolTip = document.getElementById("W-popup-tooltip");
  //now that we have them, remove them from the dom
  document.body.removeChild(W.popup.Popup);
  document.body.removeChild(W.popup.Shield);
  document.body.removeChild(W.popup.ToolTip);
  W.popup.PopupDirectorySpan.removeChild(W.popup.PopupDirectoryDir);
  W.popup.PopupDirectory.removeChild(W.popup.PopupDirectorySpan);
  W.popup.PopupDirectory.removeChild(W.popup.PopupDirectoryListItemLink);
  W.popup.PopupDirectory.removeChild(W.popup.PopupDirectoryListItem);
  document.body.removeChild(W.popup.PopupDirectory);
  document.body.removeChild(W.popup.PopupProgress);
  document.body.removeChild(W.popup.PopupProcessing);
  document.body.removeChild(W.popup.PopupOptions);
  document.body.removeChild(W.popup.PopupAlert);
  //W.util.Popup
  W.util.Popup = new W.popup();
});

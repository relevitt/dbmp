"use strict";
W.import = {};

W.import.keyboard_listener_ids = [];
W.import.zipfile_keyboard_listener_ids = [];

W.import.set_visibility = function (v) {
  const container = document.querySelector("#import-container");
  W.css.removeClasses(container, "import_visible", "hidden");
  if (v == "visible") W.css.addClasses(container, "import_visible");
  else W.css.addClasses(container, "hidden");
};

W.import.show = function () {
  if (W.import.visible) return;
  W.search_top.close();
  W.logging.close();
  W.import.visible = true;
  W.quarantine.close();
  W.qedit.close();
  W.import.History = [];
  W.import.SelectedDirectories = [];
  W.import.SelectedFiles = [];
  W.import.set_visibility("visible");
  W.util.stripChildren(W.import.SelectedUL);
  var el = W.import.SelectedPlaceholderRowTemplate.cloneNode(true);
  W.import.SelectedUL.appendChild(el);
  let listener_id = W.keyboard.set_listener(W.import.keyboard);
  W.import.keyboard_listener_ids.push(listener_id);
  document
    .querySelector("#import-input")
    .addEventListener("input", W.import.onTxtInput);
};

W.import.close = function () {
  if (!W.import.visible) return;
  W.import.visible = false;
  W.import.set_visibility("hidden");
  let listener_id = W.import.keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  document
    .querySelector("#import-input")
    .removeEventListener("input", W.import.onTxtInput);
  W.util.Popup.empty();
  W.css.removeClasses(W.util.Popup.content, "import_outcome");
};

W.import.clear_and_close = function () {
  W.import.History = undefined;
  W.import.SelectedDirectories = undefined;
  W.import.SelectedFiles = undefined;
  W.import.zipfiles = undefined;
  W.import.filebrowser_data = undefined;
  W.util.stripChildren(W.import.SelectedUL);
  W.util.stripChildren(document.querySelector("#import-directory-name"));
  W.util.stripChildren(W.import.DirectoryUL);
  W.import.close();
};

W.import.escape = function () {
  if (W.import.zipfiles) {
    if (W.import.zipfiles.p3 && W.import.zipfiles.p3.frame.visible)
      W.import.zipfiles.p3.close();
    else if (W.import.zipfiles.p2 && W.import.zipfiles.p2.frame.visible)
      W.import.zipfiles.p2.close();
    else W.import.zipfiles.p1.close();
  } else if (document.querySelector("#import-input").value) {
    document.querySelector("#import-input").value = "";
    W.import.build_filebrowser_listing(W.import.filebrowser_data);
  } else if (W.import.History.length > 1) {
    W.import.History.pop();
    var previous = W.import.History[W.import.History.length - 1];
    W.import.getDirectoryListing(previous[0], previous[1]);
  } else W.import.clear_and_close();
};

W.import.keyboard = function (e) {
  if (e.keyCode == 27)
    W.import.escape(); //escape
  else if (
    e.keyCode == 33 || //page up
    e.keyCode == 34 || //page down
    e.keyCode == 38 || //up arrow
    e.keyCode == 40 //down arrow
  )
    W.import.DirectoryUL.focus();
  else if (
    (e.keyCode >= 48 && e.keyCode <= 90) ||
    e.keyCode >= 186 ||
    e.keyCode == 8 || //backspace
    e.keyCode == 16 || //shift
    e.keyCode == 46 //delete
  )
    document.querySelector("#import-input").focus();
};

W.import.onTxtInputChanged = function () {
  var str = document.querySelector("#import-input").value.toLowerCase();
  var items = {};
  items.dirs = [];
  items.files = [];
  for (var i = 0; i < W.import.filebrowser_data.dirs.length; i++) {
    if (W.import.filebrowser_data.dirs[i].toLowerCase().includes(str))
      items.dirs.push(W.import.filebrowser_data.dirs[i]);
  }
  for (i = 0; i < W.import.filebrowser_data.files.length; i++) {
    if (W.import.filebrowser_data.files[i].toLowerCase().includes(str))
      items.files.push(W.import.filebrowser_data.files[i]);
  }
  W.import.build_filebrowser_listing(items);
};

W.import.onTxtInput = W.util.debounce(W.import.onTxtInputChanged, 250);

W.import.onHomeDirectoryClick = function (o) {
  W.import.getDirectoryListing("qlist_home", undefined, true);
};

W.import.onSearchDirectoryClick = function (o) {
  W.import.getDirectoryListing("qlist_search", undefined, true);
};

W.import.onDownloadsDirectoryClick = function (o) {
  W.import.getDirectoryListing("qlist_downloads", undefined, true);
};

W.import.onCWDClick = function (o) {
  var args = JSON.parse(o.target.dataset.cwd);
  W.import.getDirectoryListing("qlist", args, true);
};

W.import.onDirectoryClick = function (o) {
  var target = o.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  var args = W.import.filebrowser_data.cwd;
  args.push(target.dataset.dirname);
  W.import.getDirectoryListing("qlist", args, true);
};

W.import.getDirectoryListing = function (cmd, args, breadtrail) {
  breadtrail && W.import.History.push([cmd, args]);
  var jsonStr = W.system.get_jsonStr("qimport." + cmd);
  jsonStr.args.items = args;
  W.util.JSONpost("/json", jsonStr, W.import.build_filebrowser);
  W.util.Popup.processing();
};

W.import.list_to_path = function (l) {
  var p = "/";
  for (var i = 1; i < l.length; i++) {
    p += l[i];
    if (i < l.length - 1) {
      p += "/";
    }
  }
  return p;
};

W.import.addToSelected = function (o) {
  var target = o.target;
  if (target.nodeName != "SPAN") target = target.parentNode;
  var item;
  if (!Object.keys(target.dataset).length) {
    target = target.parentNode;
  }
  if ("dirname" in target.dataset) {
    item = W.import.filebrowser_data.cwd.slice(
      0,
      W.import.filebrowser_data.cwd.length,
    );
    if (target.dataset.dirname) {
      item.push(target.dataset.dirname);
    }
    for (var i = 0; i < W.import.SelectedDirectories.length; i++) {
      if (W.import.SelectedDirectories[i].equals(item)) {
        return;
      }
    }
    W.import.SelectedDirectories.push(item);
  } else {
    item = W.import.filebrowser_data.cwd.slice(
      0,
      W.import.filebrowser_data.cwd.length,
    );
    item.push(target.dataset.filename);
    for (var i = 0; i < W.import.SelectedFiles.length; i++) {
      if (W.import.SelectedFiles[i].equals(item)) {
        return;
      }
    }
    W.import.SelectedFiles.push(item);
  }
  W.import.build_selected();
};

W.import.SelectedTooltip = function (e) {
  var target = e.target;
  if (target.innerHTML == "") {
    target = target.parentNode.children[0];
  }
  if (target.scrollWidth <= target.clientWidth) return;
  var tooltip = document.querySelector("#import-tooltip");
  var tooltipContent = tooltip.querySelector("#tooltip-content");
  tooltipContent.innerHTML = target.innerHTML;
  W.css.removeClasses(tooltip, "import_tooltip_visible", "hidden");
  W.css.addClasses(tooltip, "import_tooltip_visible");
  var rect = target.parentNode.getBoundingClientRect();
  var ttrect = tooltip.getBoundingClientRect();
  var x = W.util.isDesktop() ? rect.left - 24 : rect.right;
  var y = W.util.isDesktop()
    ? rect.top - ttrect.height / 2 + rect.height / 2
    : rect.top - ttrect.height - 8; // 8px spacing above
  tooltip.style.right = "calc(100% - " + x + "px)";
  tooltip.style.top = "" + y + "px";
  e.target.onmouseout = function (o) {
    const tooltip = document.querySelector("#import-tooltip");
    W.css.removeClasses(tooltip, "import_tooltip_visible", "hidden");
    W.css.addClasses(tooltip, "hidden");
  };
};

W.import.SelectedRemove = function (e) {
  const tooltip = document.querySelector("#import-tooltip");
  W.css.removeClasses(tooltip, "import_tooltip_visible", "hidden");
  W.css.addClasses(tooltip, "hidden");
  var target = e.target;
  while (target.nodeName != "LI") target = target.parentNode;
  var id = Number(target.dataset.id);
  switch (target.dataset.type) {
    case "directory":
      W.import.SelectedDirectories.splice(id, 1);
      break;
    case "file":
      W.import.SelectedFiles.splice(id, 1);
      break;
  }
  W.import.build_selected();
};

W.import.add_selected_listeners = function () {
  document.querySelectorAll(".import-selected-li").forEach((el) => {
    el.removeEventListener("click", W.import.SelectedRemove);
    el.children[1].removeEventListener("mouseover", W.import.SelectedTooltip);
    el.children[1].removeEventListener("click", W.import.SelectedRemove);
    if (W.util.isDesktop()) {
      el.children[1].addEventListener("mouseover", W.import.SelectedTooltip);
      el.addEventListener("click", W.import.SelectedRemove);
    } else {
      el.children[1].addEventListener("click", W.import.SelectedRemove);
    }
  });
};

W.import.build_selected = function () {
  var el;
  W.util.stripChildren(W.import.SelectedUL);

  for (var i = 0; i < W.import.SelectedDirectories.length; i++) {
    el = W.import.SelectedRowTemplate.cloneNode(true);
    el.children[0].innerHTML =
      W.import.list_to_path(W.import.SelectedDirectories[i]) + "&#47;";
    el.dataset.type = "directory";
    el.dataset.id = i;
    W.import.SelectedUL.appendChild(el);
    el.children[0].addEventListener("mouseover", W.import.SelectedTooltip);
    // el.children[1].addEventListener("mouseover", W.import.SelectedTooltip);
    // el.onclick = W.import.SelectedRemove;
  }
  for (var i = 0; i < W.import.SelectedFiles.length; i++) {
    el = W.import.SelectedRowTemplate.cloneNode(true);
    W.css.addClasses(el.querySelector(".f1"), "import_file");
    el.children[0].innerHTML = W.import.list_to_path(W.import.SelectedFiles[i]);
    el.dataset.type = "file";
    el.dataset.id = i;
    W.import.SelectedUL.appendChild(el);
    el.children[0].addEventListener("mouseover", W.import.SelectedTooltip);
    // el.children[1].addEventListener("mouseover", W.import.SelectedTooltip);
    // el.onclick = W.import.SelectedRemove;
  }
  if (!W.import.SelectedDirectories.length && !W.import.SelectedFiles.length) {
    el = W.import.SelectedPlaceholderRowTemplate.cloneNode(true);
    W.import.SelectedUL.appendChild(el);
  }
  W.import.add_selected_listeners();
};

W.import.build_filebrowser = function (o) {
  var directory_name_div = document.querySelector("#import-directory-name");
  var el, el1;
  W.util.Popup.processing("close");
  W.import.filebrowser_data = o.results;
  W.util.stripChildren(directory_name_div);
  document.querySelector("#import-input").value = "";

  for (var i = 0; i < W.import.filebrowser_data.cwd.length; i++) {
    if (i < W.import.filebrowser_data.cwd.length - 1) {
      el = W.import.ImportCwdElement.cloneNode();
      el.innerHTML = W.import.filebrowser_data.cwd[i];
      el.dataset.cwd = JSON.stringify(
        W.import.filebrowser_data.cwd.slice(0, i + 1),
      );
      el.onclick = W.import.onCWDClick;
    } else {
      el = W.import.ImportCwdSelectionElement.cloneNode(true);
      el1 = el.querySelector(".import-cwd-last-element");
      el1.innerHTML = W.import.filebrowser_data.cwd[i];
      if (i > 0) {
        el.dataset.dirname = "";
        el.onclick = W.import.addToSelected;
      }
    }
    directory_name_div.appendChild(el);
    if (i < W.import.filebrowser_data.cwd.length - 1) {
      el = W.import.ImportSepElement.cloneNode(true);
      directory_name_div.appendChild(el);
    }
  }
  W.import.build_filebrowser_listing(W.import.filebrowser_data);
};

W.import.build_filebrowser_listing = function build_filebrowser_listing(items) {
  var el, i;
  W.util.stripChildren(W.import.DirectoryUL);
  if (items.dirs && items.dirs[0]) {
    for (i = 0; i < items.dirs.length; i++) {
      el = W.import.DirectoryRowTemplate.cloneNode(true);
      el.children[0].innerHTML = "&#47;" + items.dirs[i];
      el.dataset.dirname = items.dirs[i];
      W.css.addClasses(el.querySelector(".f1"), "import_directory");
      el.children[0].onclick = W.import.onDirectoryClick;
      el.children[1].onclick = W.import.addToSelected;
      W.import.DirectoryUL.appendChild(el);
    }
  }
  if (items.files && items.files[0]) {
    for (i = 0; i < items.files.length; i++) {
      el = W.import.DirectoryRowTemplate.cloneNode(true);
      el.children[0].innerHTML = items.files[i];
      el.dataset.filename = items.files[i];
      W.css.addClasses(el.querySelector(".f1"), "import_file");
      el.children[1].onclick = W.import.addToSelected;
      W.import.DirectoryUL.appendChild(el);
    }
  }
};

W.import.filebrowser = function () {
  W.import.show();
  W.import.getDirectoryListing("qlist", [], true);
};

W.import.zipfile_confirm = function (ticket, file_groups, zipfile, reload) {
  var i, ii, top_div, el, buttons, parent_el, group, p, span;

  if (!W.import.zipfiles) {
    W.import.zipfiles = {};
    W.import.zipfiles.ticket = ticket;
    W.import.zipfiles.file_groups = file_groups;
    W.import.zipfiles.zipfile = zipfile;
    W.import.zipfiles.p1 = new W.popup();
  }

  p = W.import.zipfiles.p1;
  p.empty();
  p.bar.innerHTML = "Please confirm directory for unzipping:";
  top_div = W.import.ImportZipfileConfirmContent.cloneNode(true);
  p.content.appendChild(top_div);
  el = top_div.querySelector(".import-zipfile-confirm-filename");
  el.innerHTML = zipfile;
  buttons = top_div.querySelectorAll(".import-zipfile-confirm-buttons span");
  buttons[0].onclick = W.import.zipfile_confirmed;
  buttons[1].onclick = W.import.zipfile_reload;
  for (ii = 0; ii < file_groups.length; ii++) {
    group = file_groups[ii];
    parent_el = W.import.ImportZipfileConfirmPath.cloneNode();
    top_div.appendChild(parent_el);
    for (i = 0; i < group.path.exists.length; i++) {
      if (i) {
        el = W.import.ImportSepElement.cloneNode(true);
        parent_el.appendChild(el);
      }
      el = W.import.ImportCwdElement.cloneNode();
      el.innerHTML = group.path.exists[i];
      el.dataset.group = ii;
      el.dataset.n = i;
      el.onclick = function (e) {
        var group =
          W.import.zipfiles.file_groups[Number(e.target.dataset.group)];
        var path = W.import.list_to_path(
          group.path.exists.slice(0, Number(e.target.dataset.n) + 1),
        );
        var jsonStr = W.system.get_jsonStr("util.directory");
        jsonStr.args.items = [path, ""];
        var onload = function () {
          var div = W.import.zipfiles.p2.content.querySelector(
            ".import-zipfile-directory-buttons",
          );
          div.children[0].onclick = W.import.zipfile_select_directory;
          div.children[1].onclick = W.import.zipfile_new_directory;
        };
        W.import.zipfiles.p2_group = group;
        W.util.JSONpost("/json", jsonStr, function (o) {
          !W.import.zipfiles.p2 && (W.import.zipfiles.p2 = new W.popup());
          W.import.zipfiles.p2.directory({
            title: "Please choose directory:",
            items: o.results,
            parentnode: W.import.ImportZipfileDirectory.cloneNode(true),
            onload: onload,
          });
        });
      };
      parent_el.appendChild(el);
    }
    for (i = 0; i < group.path.not_exists.length; i++) {
      el = W.import.ImportSepElement.cloneNode(true);
      parent_el.appendChild(el);
      el = W.import.ImportZipfileConfirmPathNew.cloneNode();
      el.innerHTML = group.path.not_exists[i];
      parent_el.appendChild(el);
    }
    el = W.import.ImportZipfileConfirmPathNew.cloneNode();
    el.innerHTML = ":";
    parent_el.appendChild(el);
    parent_el = W.import.ImportZipfileConfirmFilelist.cloneNode(true);
    top_div.appendChild(parent_el);
    parent_el.dataset.i = ii;
    for (i = 0; i < group.files.length; i++) {
      reload && (group.files[i].deleted = false);
      if (!group.files[i].deleted) {
        el = W.import.ImportZipfileItem.cloneNode(true);
        span = el.querySelector("span");
        span.innerHTML = group.files[i].name;
        el.onclick = W.import.zipfile_delete;
        el.dataset.i = i;
        parent_el.appendChild(el);
      }
    }
    ii < file_groups.length - 1 &&
      parent_el.appendChild(document.createElement("br"));
  }
  p.cleanup = W.import.zipfile_cleanup;
  var maxheight =
    document.querySelector("#import-container").getBoundingClientRect().height -
    52;
  var maxwidth = document
    .querySelector("#import-container")
    .getBoundingClientRect().width;
  p.show();
  p.resize(undefined, undefined, maxwidth, maxheight);
  p.center();
};

W.import.zipfile_cleanup = function () {
  !W.import.zipfiles.result_returned &&
    W.data.WS_return_result(W.import.zipfiles.ticket, {});
  W.import.zipfiles.p3 && W.import.zipfiles.p3.destroy();
  W.import.zipfiles.p2 && W.import.zipfiles.p2.destroy();
  W.import.zipfiles.p1.destroy();
  W.import.zipfiles = undefined;
};

W.import.zipfile_confirmed = function () {
  W.data.WS_return_result(
    W.import.zipfiles.ticket,
    W.import.zipfiles.file_groups,
  );
  W.import.zipfiles.result_returned = true;
  W.import.zipfiles.p1.close();
};

W.import.zipfile_reload = function () {
  for (var i = 0; i < W.import.zipfiles.file_groups.length; i++) {
    var group = W.import.zipfiles.file_groups[i];
    if (group.original_path) {
      group.path.exists = group.original_path.exists;
      group.path.not_exists = group.original_path.not_exists;
      group.original_path = undefined;
    }
  }
  W.import.zipfile_confirm(
    W.import.zipfiles.ticket,
    W.import.zipfiles.file_groups,
    W.import.zipfiles.zipfile,
    true,
  );
};

W.import.zipfile_select_directory = function () {
  var path = W.import.zipfiles.p2.DirName.split("/");
  path[0] = "Filesystem";
  W.import.zipfiles.p2_group.original_path = {};
  W.import.zipfiles.p2_group.original_path.exists =
    W.import.zipfiles.p2_group.path.exists;
  W.import.zipfiles.p2_group.original_path.not_exists =
    W.import.zipfiles.p2_group.path.not_exists;
  W.import.zipfiles.p2_group.path.exists = path;
  W.import.zipfiles.p2_group.path.not_exists = [];
  W.import.zipfiles.p2.close();
  W.import.zipfile_confirm(
    W.import.zipfiles.ticket,
    W.import.zipfiles.file_groups,
    W.import.zipfiles.zipfile,
  );
};

W.import.zipfile_new_directory = function () {
  if (!W.import.zipfiles.p3) {
    W.import.zipfiles.p3 = new W.popup();
    W.import.zipfiles.p3.cleanup = function () {
      W.util.Input.setAttribute("type", "text");
      W.util.inputHide();
      let listener_id = W.import.zipfile_keyboard_listener_ids.pop();
      W.keyboard.restore_previous_listener(listener_id);
    };
    W.import.zipfiles.p3.bar.innerHTML = "Enter directory name:";
  }
  let listener_id = W.keyboard.set_listener();
  W.import.zipfile_keyboard_listener_ids.push(listener_id);
  W.import.zipfiles.p3.show();
  var cb = function (o) {
    if (o.results.exists) alert("Directory already exists.");
    else if (o.results.failure) alert("Could not create new directory.");
    else
      W.import.zipfiles.p2.directory({
        title: W.import.zipfiles.p2.directory_title,
        items: o.results,
        fromdirectory: true,
      });
  };
  W.util.input({
    el: W.import.zipfiles.p3.content,
    cmd: "qimport.make_directory",
    args: { cwd: W.import.zipfiles.p2.DirName },
    onsubmit: W.import.zipfiles.p3.close,
    cb: cb,
    toggle: false,
  });
  W.import.zipfiles.p3.resize();
  var el = W.import.zipfiles.p2.content.querySelector(
    ".import-zipfile-directory-buttons",
  );
  W.import.zipfiles.p3.move_over_element(el);
};

W.import.zipfile_delete = function (e) {
  var target, group, file;
  target = e.target;
  while (target.nodeName != "DIV") {
    target = target.parentNode;
  }
  group = Number(target.parentNode.dataset.i);
  file = Number(target.dataset.i);
  W.import.zipfiles.file_groups[group].files[file].deleted = true;
  W.import.zipfile_confirm(
    W.import.zipfiles.ticket,
    W.import.zipfiles.file_groups,
    W.import.zipfiles.zipfile,
  );
};

W.import.import_to_search = function (e) {
  if (
    W.import.SelectedDirectories.equals([]) &&
    W.import.SelectedFiles.equals([])
  ) {
    return;
  }
  var jsonStr = W.system.get_jsonStr("qimport.importtosearch");
  jsonStr.args.dirs = W.import.SelectedDirectories;
  jsonStr.args.files = W.import.SelectedFiles;
  jsonStr.args.progress = W.data.progress_init(
    W.util.Popup,
    "Processing files: ",
    "Counting files ...",
  );
  W.import.SelectedDirectories = [];
  W.import.SelectedFiles = [];
  W.import.build_selected();
  W.util.Popup.processing(undefined, undefined, "Counting files ...");
  W.util.JSONpost("/json", jsonStr, W.import.imported_to_search);
};

W.import.imported_to_search = function (o) {
  if (!o.results) return;

  var i,
    items,
    innerHTML = "";
  var div = W.util.Popup.content;
  const directories = o.results.directories;
  const files = o.results.files;
  W.util.Popup.processing("close");

  function wrapMessage(filename, statusMessage) {
    return `<strong>${filename}</strong> ${statusMessage}<br>`;
  }

  if (directories.success.length || files.success.length) {
    innerHTML += "<strong>Added to Pending:</strong><br>";
    directories.success.forEach((item) => {
      innerHTML += `${item}<br>`;
    });
    files.success.forEach((item) => {
      innerHTML += `${item}<br>`;
    });
    innerHTML += "<br>";
  }

  if (directories.failure.length) {
    innerHTML += "<strong>Ignored - no audio files found:</strong><br>";
    directories.failure.forEach((item) => {
      innerHTML += `${item}<br>`;
    });
    innerHTML += "<br>";
  }

  const zipFailures = [];
  const otherFailures = [];

  if (files.failure.length) {
    files.failure.forEach((item) => {
      if (/\.zip$/i.test(item)) {
        zipFailures.push(item);
      } else {
        otherFailures.push(item);
      }
    });
  }

  if (otherFailures.length) {
    innerHTML += "<strong>Ignored - not audio file(s):</strong><br>";
    otherFailures.forEach((item) => {
      innerHTML += `${item}<br>`;
    });
    innerHTML += "<br>";
  }

  if (zipFailures.length) {
    innerHTML += "<strong>Ignored - zipfile(s) not processed:</strong><br>";
    zipFailures.forEach((item) => {
      innerHTML += `${item}<br>`;
    });
  }

  if (innerHTML == "") return;
  div.innerHTML = innerHTML;
  const bdiv = W.import.ImportPopupButtons.cloneNode(true);
  const buttons = bdiv.querySelectorAll("span");
  buttons[0].onclick = function (e) {
    W.css.removeClasses(W.util.Popup.content, "import_outcome");
    W.util.Popup.close();
    W.quarantine.show(true);
  };
  buttons[1].onclick = function (e) {
    W.css.removeClasses(W.util.Popup.content, "import_outcome");
    W.util.Popup.close();
    W.import.show();
  };
  div.appendChild(bdiv);
  W.css.addClasses(div, "import_outcome");
  W.util.Popup.show();
  W.util.Popup.center();
  buttons[0].focus();
};

W.import.initResizer = function () {
  const resizer = document.getElementById("import-resizer");
  const left = document.getElementById("import-left");
  const right = document.getElementById("import-right");

  // Minimum allowed height to keep #import-directory-name visible
  const minHeightPercent = 25;
  // Maximum allowed height to preserve nav bar
  const maxHeightPercent = 83;

  let isResizing = false;
  let startY = 0;
  let initialLeftMaxHeight = 60;
  var windowHeight;

  function handleStart(e) {
    isResizing = true;
    startY = e.clientY || (e.touches && e.touches[0].clientY);

    // Compute the current % maxHeight from element height
    windowHeight = window.visualViewport.height;
    initialLeftMaxHeight = (left.offsetHeight / windowHeight) * 100;

    document.addEventListener("mousemove", handleMove);
    document.addEventListener("mouseup", handleEnd);
    document.addEventListener("touchmove", handleMove, { passive: false });
    document.addEventListener("touchend", handleEnd);
    document.body.style.userSelect = "none";
  }

  function handleMove(e) {
    if (!isResizing) return;

    const currentY = e.clientY || (e.touches && e.touches[0].clientY);
    const deltaY = currentY - startY;

    let newLeftMaxHeight = initialLeftMaxHeight + (deltaY / windowHeight) * 100;

    // Clamp to limits
    newLeftMaxHeight = Math.max(
      minHeightPercent,
      Math.min(newLeftMaxHeight, maxHeightPercent),
    );

    left.style.maxHeight = `${newLeftMaxHeight}%`;

    if (window.innerWidth < 1024) {
      right.style.height = `calc(100% - ${left.offsetHeight}px)`;
    }

    e.preventDefault();
  }

  function handleEnd() {
    isResizing = false;
    document.removeEventListener("mousemove", handleMove);
    document.removeEventListener("mouseup", handleEnd);
    document.removeEventListener("touchmove", handleMove);
    document.removeEventListener("touchend", handleEnd);
    document.body.style.userSelect = "";
  }

  resizer.addEventListener("mousedown", handleStart);
  resizer.addEventListener("touchstart", handleStart, { passive: false });

  W.util.mediaQuery.addEventListener("change", (e) => {
    const left = document.getElementById("import-left");
    const right = document.getElementById("import-right");

    if (e.matches) {
      // We switched to desktop view
      left.style.maxHeight = "";
      right.style.height = "";
    }
  });
};

W.util.ready(function () {
  // elements for cloning
  W.import.DirectoryRowTemplate = document.querySelector(
    "#import-directory-listing li",
  );
  W.import.SelectedRowTemplate = document.querySelector(".import-selected-li");
  W.import.SelectedPlaceholderRowTemplate = document.querySelector(
    ".import-selected-li-placeholder",
  );
  W.import.ImportCwdElement = document.querySelector(".import-cwd-element");
  W.import.ImportSepElement = document.querySelector(".import-sep-element");
  W.import.ImportCwdSelectionElement = document.querySelector(
    ".import-cwd-selection-element",
  );
  W.import.ImportZipfileConfirmContent = document.querySelector(
    ".import-zipfile-confirm-content",
  );
  W.import.ImportZipfileConfirmPath = document.querySelector(
    ".import-zipfile-confirm-path",
  );
  W.import.ImportZipfileConfirmPathNew =
    W.import.ImportZipfileConfirmPath.querySelector("span");
  W.import.ImportZipfileConfirmFilelist = document.querySelector(
    ".import-zipfile-confirm-filelist",
  );
  W.import.ImportZipfileItem = document.querySelector(".import-zipfile-item");
  W.import.ImportZipfileDirectory = document.querySelector(
    ".import-zipfile-directory",
  );
  W.import.ImportPopupButtons = document.querySelector(
    ".W-import-popup-buttons",
  );
  // now that we have them, remove them from document.body
  W.import.DirectoryRowTemplate.parentNode.removeChild(
    W.import.DirectoryRowTemplate,
  );
  W.import.SelectedRowTemplate.parentNode.removeChild(
    W.import.SelectedRowTemplate,
  );
  W.import.SelectedPlaceholderRowTemplate.parentNode.removeChild(
    W.import.SelectedPlaceholderRowTemplate,
  );
  W.import.ImportCwdElement.parentNode.removeChild(W.import.ImportCwdElement);
  W.import.ImportSepElement.parentNode.removeChild(W.import.ImportSepElement);
  W.import.ImportCwdSelectionElement.parentNode.removeChild(
    W.import.ImportCwdSelectionElement,
  );
  document.body.removeChild(W.import.ImportZipfileDirectory);
  W.import.ImportZipfileItem.parentNode.removeChild(W.import.ImportZipfileItem);
  W.import.ImportZipfileConfirmPathNew.parentNode.removeChild(
    W.import.ImportZipfileConfirmPathNew,
  );
  W.import.ImportZipfileConfirmPath.parentNode.removeChild(
    W.import.ImportZipfileConfirmPath,
  );
  W.import.ImportZipfileConfirmFilelist.parentNode.removeChild(
    W.import.ImportZipfileConfirmFilelist,
  );
  document.body.removeChild(W.import.ImportZipfileConfirmContent);
  document.body.removeChild(W.import.ImportPopupButtons);
  // initialisation continues ...
  document.getElementById("import-home-directory").onclick =
    W.import.onHomeDirectoryClick;
  document.getElementById("import-search-directory").onclick =
    W.import.onSearchDirectoryClick;
  document.getElementById("import-downloads-directory").onclick =
    W.import.onDownloadsDirectoryClick;
  document.getElementById("import-close").onclick = W.import.clear_and_close;
  document.getElementById("import-import").onclick = W.import.import_to_search;
  document.getElementById("import-clear-quarantine").onclick =
    W.quarantine.clear;
  document.getElementById("import-goto-quarantine").onclick = function () {
    W.quarantine.show(true);
  };
  W.import.DirectoryUL = document.querySelector("#import-directory-listing");
  W.import.SelectedUL = document.querySelector("#import-selected");
  const container = document.getElementById("import-container");
  container.appendChild(
    document.querySelector(".mobile-nav-bar").cloneNode(true),
  );
  W.import.initResizer();
  W.util.mediaQuery.addEventListener("change", () => {
    W.import.add_selected_listeners();
  });
});

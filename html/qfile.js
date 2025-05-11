"use strict";
W.qfile = {};

W.qfile.lastSelectedIndex = null;

W.qfile.initList = function (container, options) {
  container.innerHTML = ""; // Clear any existing options

  options.forEach((optionText) => {
    const option = W.qfile.Option.cloneNode(true);
    option.textContent = optionText;
    container.appendChild(option);

    // Handle selection
    option.addEventListener("click", (e) => {
      const items = [...container.querySelectorAll(".list-item")];
      const index = items.indexOf(option);
      if (e.shiftKey && W.qfile.lastSelectedIndex !== null) {
        // Handle Shift+Click for range selection
        const start = Math.min(W.qfile.lastSelectedIndex, index);
        const end = Math.max(W.qfile.lastSelectedIndex, index);

        items
          .slice(start, end + 1)
          .forEach((item) => item.classList.add("selected"));
      } else if (e.ctrlKey || e.metaKey) {
        // Toggle selection on Ctrl/Command click
        option.classList.toggle("selected");
      } else {
        // Single selection (clears previous selection)
        items.forEach(
          (item) => item != option && item.classList.remove("selected"),
        );
        option.classList.toggle("selected");
      }

      W.qfile.lastSelectedIndex = index; // Update the last selected index
    });
  });
};

W.qfile.getSelectedItems = function () {
  return [...W.util.Popup.content.querySelectorAll(".list-item.selected")].map(
    (item) => item.textContent,
  );
};

W.qfile.copy_song_names = function (o) {
  var strt = W.qfile.Input.value;
  strt = strt - 1;
  const selected = W.qfile.getSelectedItems();
  for (var i = 0; i < selected.length; i++) {
    W.data.qedit.data[strt].title = selected[i];
    strt += 1;
    if (strt >= W.data.qedit.data.length) break;
  }
  W.qedit.rebuild();
};

W.qfile.copy_artist = function (o) {
  W.data.qedit.artist = "";
  const selected = W.qfile.getSelectedItems();
  for (var i = 0; i < selected.length; i++) {
    W.data.qedit.artist += selected[i];
  }
  W.qedit.rebuild();
};

W.qfile.copy_album = function (o) {
  W.data.qedit.album = "";
  const selected = W.qfile.getSelectedItems();
  for (var i = 0; i < selected.length; i++) {
    W.data.qedit.album += selected[i];
  }
  W.qedit.rebuild();
};

W.qfile.removeitem = function (o) {
  W.qfile.lastSelectedIndex = null;
  const selected = W.util.Popup.content.querySelectorAll(".list-item.selected");
  selected.forEach((option) => option.parentNode.removeChild(option));
};

W.qfile.back = function (o) {
  var jsonStr = W.system.get_jsonStr("util.directory");
  jsonStr.args.items = [W.util.Popup.DirName, ""];
  W.util.JSONpost("/json", jsonStr, function (o) {
    W.util.Popup.directory({
      title: "Open Text File",
      items: o.results,
      onfileclick: W.qfile.onFileClick,
    });
  });
};

W.qfile.onFileClick = function (e) {
  var file = e.target.filename; //Review
  var jsonStr = W.system.get_jsonStr("qimport.popupFile");
  jsonStr.args.items = [W.util.Popup.DirName, file];
  W.util.JSONpost("/json", jsonStr, W.qfile.CopyFile);
};

W.qfile.CopyFile = function (o) {
  var items = o.results;
  if (items.binary) {
    alert("Sorry, can't open binary file");
    return;
  }
  W.util.Popup.empty();
  W.util.Popup.bar.innerHTML = "Copy Text File";
  var div = W.qfile.Qfile.cloneNode(true);
  var buttons = div.querySelectorAll(".W-button");
  buttons[0].onclick = W.qfile.copy_artist;
  buttons[1].onclick = W.qfile.copy_album;
  buttons[2].onclick = W.qfile.copy_song_names;
  buttons[3].onclick = W.qfile.removeitem;
  buttons[4].onclick = W.qfile.back;
  W.qfile.Input = div.querySelector("input");
  W.qfile.Input.value = "1";
  const container = div.querySelector(".static-list");
  W.qfile.initList(container, items.content);
  W.util.Popup.content.appendChild(div);
  W.util.Popup.resize();
  let width = container.scrollWidth;
  Array.from(container.children).forEach((el) => {
    el.style.width = "" + width + "px";
  });
};

W.qfile.onOpenTextFile = function () {
  var jsonStr = W.system.get_jsonStr("qimport.popup");
  jsonStr.args.id = W.data.qedit.data[0].id; //Maybe the ID should be a separate variable
  W.util.JSONpost("/json", jsonStr, function (o) {
    W.util.Popup.directory({
      title: "Open Text File",
      items: o.results,
      onfileclick: W.qfile.onFileClick,
      center: true,
    });
  });
};

W.util.ready(function () {
  // elements for cloning
  W.qfile.Qfile = document.body.querySelector(".qfile");
  W.qfile.Option = W.qfile.Qfile.querySelector(".list-item");
  // now that we have them, remove them from document.body
  W.qfile.Option.parentNode.removeChild(W.qfile.Option);
  document.body.removeChild(W.qfile.Qfile);
});

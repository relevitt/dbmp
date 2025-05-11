"use strict";
W.keyboard = {};

W.keyboard.simulateEscapeKey = function () {
  console.log("Simulating Escape keypress");

  const event = new KeyboardEvent("keydown", {
    key: "Escape",
    keyCode: 27, // Legacy property for compatibility
    code: "Escape",
    bubbles: true, // Ensure it propagates through the DOM
    cancelable: true, // Allow handlers to cancel the event
  });

  document.dispatchEvent(event);
};

W.keyboard.listener_next_id = 0;

W.keyboard.replaced_listeners = [];

W.keyboard.listener_ids = [];

W.keyboard.listener_current = undefined;

W.keyboard.set_listener = function (new_listener) {
  // console.log('W.keyboard.set_listener');
  // console.log(new_listener);
  // console.log(W.keyboard.listener_next_id);
  W.keyboard.replaced_listeners.push(W.keyboard.listener_current);
  W.keyboard.listener_ids.push(W.keyboard.listener_next_id);
  if (W.keyboard.listener_current) {
    document.removeEventListener("keydown", W.keyboard.listener_current);
  }
  if (new_listener) {
    document.addEventListener("keydown", new_listener);
  }
  W.keyboard.listener_current = new_listener;
  // returns W.keyboard.listener_next_id before incrementing it
  return W.keyboard.listener_next_id++;
};

W.keyboard.restore_previous_listener = function (listener_id) {
  // console.log('W.keyboard.restore_previous_listener');
  // console.log(listener_id);

  // Get the position of that listener_id in the list
  let position = W.keyboard.listener_ids.indexOf(listener_id);

  // This situation shouldn't happen
  if (position == -1) {
    console.warn("Missing keyboard listener_id");
    return;
  }

  // If it's not the last in the list of ids, we just remove it from
  // W.keyboard.replaced_listeners

  if (position != W.keyboard.listener_ids.length - 1) {
    // It's position should be one place ahead in the array of
    // replaced listeners, because the first element of that
    // array will have been set to 'undefined' when
    // W.util.ready is executed
    W.keyboard.replaced_listeners.splice(position + 1, 1);
  }

  // If it's the last in the list of ids, then it must also be
  // W.keyboard.listener_current, so we replace it with the
  // previous listener
  else {
    let previous_listener = W.keyboard.replaced_listeners.pop();
    if (W.keyboard.listener_current) {
      document.removeEventListener("keydown", W.keyboard.listener_current);
    }
    if (previous_listener) {
      document.addEventListener("keydown", previous_listener);
    }
    W.keyboard.listener_current = previous_listener;
  }

  // Remove id from the list of ids
  W.keyboard.listener_ids.splice(position, 1);
};

W.keyboard.keydown = function (e) {
  if (e.ctrlKey) {
    if (!W.searchVisible)
      switch (e.keyCode) {
        case 27: //escape
          e.preventDefault();
          W.queue.deselect_all();
          document.querySelector("#queue").focus();
          break;
        case 32: //space bar
          e.preventDefault();
          var parent = document.querySelector("#queue");
          if (parent.children.length <= 1) return;
          if (document.activeElement.parentNode == parent) {
            e.target = document.activeElement;
            W.util.selectThis.apply(document.activeElement, [e]);
          }
          break;
        case 38: //up arrow
          e.preventDefault();
          var parent = document.querySelector("#queue");
          if (parent.children.length <= 1) return;
          if (document.activeElement.parentNode == parent) {
            var index = W.util.getLiIndex(document.activeElement);
            if (index) parent.children[index - 1].focus();
          } else parent.children[parent.children.length - 2].focus();
          break;
        case 40: //down arrow
          e.preventDefault();
          var parent = document.querySelector("#queue");
          if (parent.children.length <= 1) return;
          if (document.activeElement.parentNode == parent) {
            var index = W.util.getLiIndex(document.activeElement);
            if (index < parent.children.length - 1)
              parent.children[index + 1].focus();
          } else parent.children[0].focus();
          break;
        case 46: //delete
          e.preventDefault();
          W.queue.ondelete_selected();
          break;
        case 65: //Ctrl-A
          e.preventDefault();
          W.queue.select_all();
          break;
        case 67: //Ctrl-C
          e.preventDefault();
          W.queue_commands.copySelected();
          break;
        case 70: //Ctrl-F
          e.preventDefault();
          e.shiftKey ? W.queue.find(true) : W.queue.find();
          break;
        case 86: //Ctrl-V
          e.preventDefault();
          W.queue.pasteEnd();
          break;
        case 88: //Ctrl-X
          e.preventDefault();
          W.queue_commands.copySelected();
          W.queue.ondelete_selected();
          break;
        default:
          break;
      }
    else if (!W.search.edit_mode)
      switch (e.keyCode) {
        case 70: //Ctrl-F
          e.preventDefault();
          W.search.find();
          break;
        default:
          break;
      }
    else
      switch (e.keyCode) {
        case 46: //delete
          e.preventDefault();
          W.search_edit.delete_selected();
          break;
        case 65: //Ctrl-A
          e.preventDefault();
          W.search_edit.select_all();
          break;
        case 67: //Ctrl-C
          e.preventDefault();
          W.search_edit.copy_selected();
          break;
        case 83: //Ctrl-S
          if (W.search_edit.rename_tracks_mode) {
            e.preventDefault();
            W.search_edit.exit_rename_tracks(true);
          }
          break;
        case 86: //Ctrl-V
          e.preventDefault();
          W.search_edit.paste(undefined, "at end");
          break;
        case 88: //Ctrl-X
          e.preventDefault();
          W.search_edit.cut_selected();
          break;
        default:
          break;
      }
    return;
  } else if (
    e.keyCode == 32 || //space
    e.keyCode == 37 || //left arrow
    e.keyCode == 39 //right arrow
  ) {
    if (W.searchVisible) !W.search.edit_mode && W.search_top.TxtInput.focus();
    else {
      var jsonStr;
      switch (e.keyCode) {
        case 32:
          e.preventDefault();
          jsonStr = W.system.create_cmd_and_get_jsonStr("play_pause");
          break;
        case 37:
          jsonStr = W.system.create_cmd_and_get_jsonStr("prev_track");
          break;
        case 39:
          jsonStr = W.system.create_cmd_and_get_jsonStr("next_track");
          break;
      }
      W.util.JSONpost("/json", jsonStr);
    }
  } else if (
    e.keyCode == 33 || //page up
    e.keyCode == 34 || //page down
    e.keyCode == 38 || //up arrow
    e.keyCode == 40 //down arrow
  ) {
    if (W.searchVisible) W.search.resultsUL.focus();
    else document.querySelector("#queue").focus();
  } else if (
    e.keyCode == 8 || //backspace
    e.keyCode == 16 || //shift
    e.keyCode == 46 //delete
  ) {
    if (W.searchVisible) {
      if (!W.search.edit_mode) W.search_top.TxtInput.focus();
      else if (
        (e.keyCode == 8 || e.keyCode == 46) &&
        !W.search_edit.rename_tracks_mode
      ) {
        e.preventDefault();
        W.search_edit.delete_selected();
      }
    } else if (e.keyCode == 8 || e.keyCode == 46) {
      e.preventDefault();
      W.queue.ondelete_selected();
    }
  } else if ((e.keyCode >= 48 && e.keyCode <= 90) || e.keyCode >= 186) {
    if (W.searchVisible) !W.search.edit_mode && W.search_top.TxtInput.focus();
    else W.search_top.show();
  } else if (e.keyCode == 27) {
    if (W.search.edit_mode) W.search_edit.exit(true);
    else if (W.searchVisible) W.search.escape();
    else {
      W.queue.deselect_all();
      document.querySelector("#queue").focus();
    }
  }
};

W.util.ready(function () {
  // This will therefore always have an id of 0 and
  // be the first in the array W.keyboard.listener_ids
  W.keyboard.set_listener(W.keyboard.keydown);
});

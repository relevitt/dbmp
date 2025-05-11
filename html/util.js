"use strict";

W.util = {};

//strip_object

W.util.strip_object = function (obj) {
  Object.keys(obj).forEach(function (key) {
    obj[key] = undefined;
    delete obj[key];
  });
};

//has_class

W.util.has_class = function (element, cls) {
  return (" " + element.className + " ").indexOf(" " + cls + " ") > -1;
};

//create_moves

W.util.create_moves = function (indices, dest) {
  /*
	Arguments:
		indices: an array of indices to be moved
		dest: the position before which the indices are to be moved

	Returns:
		An array of [index, range, dest] arrays, representing each individual move required.

	Example:
		You have an array [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
		You wish to move items 0, 1, 2, 3 to before position 5
		create_moves([0,1,2,3], 5) will return [[0, 4, 5]]

	*/

  var _indices = indices.slice(0);
  var moves = [];
  var series_start = -1;
  var index, counter, series_dest, i;
  while (_indices.length) {
    index = _indices.shift();
    if (dest == index) {
      dest += 1;
      continue;
    }
    if (dest == index + 1) continue;
    if (series_start == -1) {
      series_start = index;
      series_dest = dest;
      counter = 0;
    }
    counter++;
    if (!_indices.length || _indices[0] > index + 1) {
      if (series_dest < series_start || series_dest > series_start + counter) {
        moves.push([series_start, counter, series_dest]);
      }
      series_start = -1;
    }
    if (dest < index) dest++;
    if (dest > index) {
      for (i = 0; i < _indices.length; i++) {
        if (_indices[i] < dest) _indices[i]--;
      }
    }
  }
  return moves;
};

//generateUUID

W.util.getUUID = function () {
  var d = new Date().getTime();
  if (window.performance && typeof window.performance.now === "function") {
    d += performance.now(); //use high-precision timer if available
  }
  var uuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
    /[xy]/g,
    function (c) {
      var r = (d + Math.random() * 16) % 16 | 0;
      d = Math.floor(d / 16);
      return (c == "x" ? r : (r & 0x3) | 0x8).toString(16);
    },
  );
  return uuid;
};

//Get input

W.util.getInput = function (args) {
  /*
		title:		text to appear in popup bar
		cmd:		(optional) command to be sent to the server
		args:		(optional) arguments to be sent to the server
		cb:		    (optional) callback after the server responds
		el:		    (optional) element over which the popup should be positioned
		pwd:		(optional) true if a password is being requested
		fn:		    (optional) a function to be called instead of sending cmd to the server
        cleanup:    (optional) a function to be called when W.util.inputHide() is invoked
	*/

  W.util.Popup.empty();
  W.util.Popup.cleanup = function () {
    W.util.inputPwd && W.util.inputFn("CANCELLED"); //Should happen only if user cancelled
    W.util.Input.setAttribute("type", "text");
    W.util.inputHide();
    W.util.Popup.empty();
  };
  W.util.Popup.modal(true);
  W.util.Popup.show();
  W.util.Popup.bar.innerHTML = args.title;
  W.util.input({
    el: W.util.Popup.content,
    cmd: args.cmd,
    args: args.args,
    onsubmit: W.util.Popup.close,
    cb: args.cb,
    pwd: args.pwd,
    fn: args.fn,
    toggle: false,
    cleanup: args.cleanup,
  });
  if (args.pwd) W.util.Input.setAttribute("type", "password");
  W.util.Popup.resize();
  if (args.el) W.util.Popup.move_over_element(args.el);
  else W.util.Popup.center();
};

//Set password

W.util.setPassword = function () {
  var fn = function (pwd) {
    W.util.inputPwd && (W.util.inputPwd = false); //So that we act appropriately on W.util.cleanup
    W.data.WS_send_pwd(pwd);
  };
  W.util.getInput({
    title: "Please enter new password",
    fn: fn,
    pwd: true,
  });
};

//Get password

W.util.getPassword = function (wrong_pwd) {
  var fn = function (pwd) {
    W.util.inputPwd && (W.util.inputPwd = false); //So that we act appropriately on W.util.cleanup
    W.data.WS_send_pwd(pwd);
  };
  W.util.getInput({
    title: wrong_pwd ? "Wrong password - try again" : "Please enter password",
    fn: fn,
    pwd: true,
  });
};

//input

W.util.inputShowing = false;

W.util.input_keyboard_listener_ids = [];

W.util.input = function (args) {
  /*
		el:		        parent to which input element should be appended
		cmd:  		    (optional) command to be sent to the server
		args:	  	    (optional) arguments to be sent to the server
		onsubmit:	    (optional) additional function to be called after onsubmit   
		cb:		        (optional) callback after the server responds
		pwd:		      (optional) true if a password is being requested 
		fn:		        (optional) a function to be called instead of sending cmd to the server
		toggle:		    (optional) false if the input shouldn't be hidden after submit  
    cleanup:      (optional) a function to be called when W.util.inputHide() is invoked
    placeholder:  (optional) placeholder text
	*/

  W.util.inputToggle = typeof args.toggle !== "undefined" ? args.toggle : true;
  W.util.inputPwd = typeof args.pwd !== "undefined" ? args.pwd : false;
  if (W.util.inputShowing && W.util.inputToggle) {
    W.util.inputHide();
    if (args.el == W.util.inputParent) return;
  }
  W.util.inputParent = args.el;
  W.util.inputCmd = args.cmd;
  W.util.inputArgs = args.args;
  W.util.inputCallback = args.cb;
  W.util.inputOnSubmit = args.onsubmit;
  W.util.inputFn = args.fn;
  W.util.inputCleanup = args.cleanup;
  W.util.inputShowing = true;
  let listener_id = W.keyboard.set_listener(W.util.inputKeydown);
  W.util.input_keyboard_listener_ids.push(listener_id);
  if (W.util.inputToggle) document.addEventListener("click", W.util.inputClick);
  args.el.appendChild(W.util.Input);
  W.util.Input.focus();
  if (args.placeholder) W.util.Input.placeholder = args.placeholder;
};

W.util.inputHide = function () {
  W.util.inputShowing = false;
  W.util.inputClickStarted = false;
  let listener_id = W.util.input_keyboard_listener_ids.pop();
  W.keyboard.restore_previous_listener(listener_id);
  if (W.util.inputToggle)
    document.removeEventListener("click", W.util.inputClick);
  W.util.inputParent.removeChild(W.util.Input);
  W.util.Input.value = "";
  W.util.Input.placeholder = "";
  W.util.inputCleanup && W.util.inputCleanup();
};

W.util.inputClick = function (e) {
  if (!W.util.inputClickStarted) {
    W.util.inputClickStarted = true;
    return;
  }
  if (e.target == W.util.Input) return;
  W.util.inputHide();
};

W.util.inputSubmit = function () {
  if (W.util.inputFn) {
    W.util.inputFn(W.util.Input.value);
  } else if (W.util.inputCmd) {
    var jsonStr = W.system.get_jsonStr(W.util.inputCmd, W.util.inputArgs);
    jsonStr.args.name = W.util.Input.value;
    W.util.JSONpost("/json", jsonStr, W.util.inputCallback);
  }
  if (W.util.inputOnSubmit) W.util.inputOnSubmit();
  else W.util.inputHide();
};

W.util.inputKeydown = function (e) {
  if (e.keyCode == 27) {
    if (W.util.inputToggle) W.util.inputHide();
    else W.util.inputOnSubmit && W.util.inputOnSubmit();
  }
  if (e.keyCode == 13) W.util.inputSubmit();
};

//Debounce and throttle

W.util.debounce = function (fn, delay) {
  var timer = null;
  return function () {
    var context = this,
      args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () {
      fn.apply(context, args);
    }, delay);
  };
};

function throttle(fn, threshold, scope) {
  threshold || (threshold = 250);
  var last, deferTimer;
  return function () {
    var context = scope || this;
    var now = +new Date(),
      args = arguments;
    if (last && now < last + threshold) {
      // hold on to it
      clearTimeout(deferTimer);
      deferTimer = setTimeout(function () {
        last = now;
        fn.apply(context, args);
      }, threshold);
    } else {
      last = now;
      fn.apply(context, args);
    }
  };
}

//Cookies

W.util.setCookie = function (cname, cvalue, exdays) {
  if (exdays == undefined) exdays = 30;
  var d = new Date();
  d.setTime(d.getTime() + exdays * 24 * 60 * 60 * 1000);
  var expires = "expires=" + d.toUTCString();
  document.cookie = cname + "=" + cvalue + "; " + expires;
};

W.util.getCookie = function (cname) {
  var name = cname + "=";
  var ca = document.cookie.split(";");
  for (var i = 0; i < ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == " ") c = c.substring(1);
    if (c.indexOf(name) == 0) return c.substring(name.length, c.length);
  }
  return "";
};

// attach the .equals method to Array's prototype to call it on any array
Array.prototype.equals = function (array) {
  if (!array) {
    return false;
  }
  if (this.length != array.length) {
    return false;
  }
  for (var i = 0, l = this.length; i < l; i++) {
    if (this[i] instanceof Array && array[i] instanceof Array) {
      if (!this[i].equals(array[i])) {
        return false;
      }
    } else if (this[i] != array[i]) {
      return false;
    }
  }
  return true;
};

// W.util.JSONpost

W.util.JSONpost = function (url, data, cb, err) {
  var request = new XMLHttpRequest();
  request.open("POST", url, true);
  request.setRequestHeader(
    "Content-Type",
    "application/x-www-form-urlencoded; charset=UTF-8",
  );
  request.onload = function () {
    if (request.status >= 200 && request.status < 400) {
      cb && cb(JSON.parse(request.responseText));
    } else err && err();
  };
  request.send(JSON.stringify(data));
};

// W.util.GET

W.util.GET = function (args) {
  /*
		args.url:		url to send GET request to
		args.success:		function to call on success
		args.error:		function to call on failure
		args.JSON:		if true, JSON parse results
	*/

  var request = new XMLHttpRequest();
  request.open("GET", args.url, true);
  request.onload = function () {
    if (request.status >= 200 && request.status < 400)
      args.success &&
        args.success(
          args.JSON ? JSON.parse(request.responseText) : request.responseText,
        );
    else
      args.error &&
        args.error("HTTP error", request.status, request.responseText);
  };
  args.error &&
    (request.onerror = function () {
      args.error("There was an error");
    });
  request.send();
};

// W.util.ready

W.util.ready = function (fn) {
  if (document.readyState != "loading") fn();
  else document.addEventListener("DOMContentLoaded", fn);
};

// W.util.stripChildren

W.util.stripChildren = function (el, recursive) {
  recursive = recursive == undefined ? true : recursive;
  if (recursive) {
    for (var i = 0; i < el.children.length; i++) {
      W.util.stripChildren(el.children[i], recursive);
    }
  }
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
};

// W.util.getLiIndex

W.util.getLiIndex = function (el) {
  var li = el;
  while (li.nodeName != "LI") {
    li = li.parentNode;
  }
  var ul = li;
  while (ul.nodeName != "UL") {
    ul = ul.parentNode;
  }
  return Array.prototype.indexOf.call(ul.childNodes, li);
};

/* W.util.selectThis adds or removes the 'selected' class to/from
<li> elements in a <ul> when they are clicked.  It also handles ctrl-click
and shift-click. Not sure if shift-click always does what a user would
expect. Might need further checking.*/

W.util.selectThis = function (e) {
  e.preventDefault();
  var target = e.target;
  while (target.nodeName != "LI") {
    if (target.nodeName == "INPUT") {
      return;
    }
    target = target.parentNode;
  }
  var ul = target;
  while (ul.nodeName != "UL") {
    ul = ul.parentNode;
  }
  var selected = ul.getElementsByClassName("selected");
  var is_selected = false;
  if (target.classList.contains("selected")) {
    is_selected = true;
  }
  let selectMultiple = ul.dataset ? ul.dataset.selectMultiple == "true" : false;
  let ctrlKey = e.ctrlKey || selectMultiple;
  if (!ctrlKey && !e.shiftKey) {
    if (selected.length > 1) {
      is_selected = false;
    }
    while (selected.length) {
      selected[0].classList.remove("selected");
    }
  }
  if (!e.shiftKey) {
    if (is_selected) {
      target.classList.remove("selected");
    } else {
      target.classList.add("selected");
    }
  } else if (selected.length) {
    var top = W.util.getLiIndex(selected[0]);
    var bottom = W.util.getLiIndex(selected[selected.length - 1]);
    var clicked = W.util.getLiIndex(target);
    if (clicked < top) {
      bottom = top;
      top = clicked;
    } else if (clicked > bottom) {
      top = bottom;
      bottom = clicked;
    } else {
      top = bottom = clicked;
    }
    for (var i = top; i <= bottom; i++) {
      ul.childNodes[i].classList.add("selected");
    }
  } else {
    target.classList.add("selected");
  }
};

/*
Drag and drop
*/

W.util.ondragstart = function (args) {
  /*
		Args:
			event: triggering event

			draggingclass: class to add to the stationary version of the li elements
								being dragged (default: "dragging")

			dragoverclass: class to add to the li element over which elements are being
								dragged (default: "dragover") 

			dragtemplate: template to use for the li elements of the dragicon

			dataObject: dataObject to act upon 

			rowpopulate: function to populate the li elements of the dragicon (which must take as args
                the li element and its dataObject index)

			dragframe: (optional) encapsulating element which, if the mouse enters it,
                should cause the dragoverclass to be removed from li elements 

			dragframeElements: (optional) array of additional elements (within the dragframe) which, if 
                the mouse enters them, should cause the dragoverclass to be removed from 
                li elements (may be needed because of event bubbling)

			dragexitElements: (optional) array of elements, outside the dragframe, which, if 
                the mouse enters them, should cause the dragoverclass to be removed from 
                li elements (may be needed because dom was too slow to catch a 
                dragover event on the dragframe)
	*/

  W.util.draggedIndices = [];
  W.util.draggedData = [];
  var ul = args.event.target;
  while (ul.nodeName != "UL") {
    ul = ul.parentNode;
  }
  W.util.dragstartUL = ul;
  W.util.draggingclass =
    args.draggingclass != undefined ? args.draggingclass : "dragging";
  W.util.dragoverclass =
    args.dragoverclass != undefined ? args.dragoverclass : "dragover";
  W.util.dragdataObject = args.dataObject;
  W.util.dragdataObjectId = args.dataObject.id;
  W.util.dragdataObjectSnapshotId = args.dataObject.snapshot_id;
  W.util.dragsystem = W.system.object;
  W.util.dragframe = args.dragframe;
  W.util.dragframeElements = args.dragframeElements
    ? args.dragframeElements
    : [];
  W.util.dragframeElements.push(args.dragframe);
  W.util.dragexitElements = args.dragexitElements;
  var selected = ul.getElementsByClassName("selected");
  var index;
  if (args.event.target.classList.contains("selected")) {
    for (var i = 0; i < selected.length; i++) {
      index = W.util.getLiIndex(selected[i]);
      W.util.draggedIndices.push(index);
      W.util.draggedData.push(W.util.dragdataObject.data[index]);
    }
  } else {
    while (selected.length) {
      selected[0].classList.remove("selected");
    }
    args.event.target.classList.add("selected");
    index = W.util.getLiIndex(args.event.target);
    W.util.draggedIndices = [index];
    W.util.draggedData = [W.util.dragdataObject.data[index]];
  }

  args.event.dataTransfer.setData("text/plain", "dummy text");
  args.event.dataTransfer.effectAllowed = "move";

  var li;
  W.util.dragUL = document.createElement("ul");
  W.css.addClasses(W.util.dragUL, "util_dragicon");
  for (var i = 0; i < W.util.draggedIndices.length; i++) {
    li = args.dragtemplate.cloneNode(true);
    args.rowpopulate(li, W.util.draggedIndices[i]);
    W.util.dragUL.appendChild(li);
  }
  document.body.appendChild(W.util.dragUL);
  args.event.dataTransfer.setDragImage(W.util.dragUL, 0, 0);

  for (var i = 0; i < selected.length; i++) {
    W.css.addClasses(selected[i], W.util.draggingclass);
  }

  if (W.util.dragframe)
    W.util.dragframe.addEventListener(
      "dragenter",
      W.util.ondragenterframe,
      false,
    );

  if (W.util.dragexitElements) {
    for (i = 0; i < W.util.dragexitElements.length; i++) {
      W.util.dragexitElements[i].addEventListener(
        "dragenter",
        W.util.ondragexit,
        false,
      );
    }
  }
};

W.util.dragoverLI = 0;

W.util.ondragover = function (event) {
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
  var target = event.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  if (target != W.util.dragoverLI) {
    if (W.util.dragoverLI) {
      W.css.removeClasses(W.util.dragoverLI, W.util.dragoverclass);
    }
    W.util.dragoverLI = target;
    W.css.addClasses(target, W.util.dragoverclass);
  }
};

W.util.ondragexit = function (event) {
  event.stopPropagation();
  event.preventDefault();
  if (W.util.dragoverLI) {
    W.css.removeClasses(W.util.dragoverLI, W.util.dragoverclass);
    W.util.dragoverLI = 0;
  }
};

W.util.ondragenterframe = function (event) {
  event.stopPropagation();
  event.preventDefault();
  if (W.util.dragframeElements.indexOf(event.target) > -1) {
    if (W.util.dragoverLI) {
      W.css.removeClasses(W.util.dragoverLI, W.util.dragoverclass);
      W.util.dragoverLI = 0;
    }
  }
};

W.util.ondragenter = function (event) {
  event.stopPropagation();
  event.preventDefault();
};

W.util.ondragleave = function (event) {};

W.util.ondrop = function (event, dragstartIndex) {
  /*
		event:			the triggering event
		dragstartIndex:		if required, the dragstartIndex
	*/

  event.preventDefault();
  event.stopPropagation();
  var target = event.target;
  while (target.nodeName != "LI") {
    target = target.parentNode;
  }
  var dest = W.util.getLiIndex(target);
  W.util.dragdataObject.move_rows(
    dest,
    W.util.draggedIndices,
    W.util.draggedData,
    dragstartIndex,
    W.util.dragdataObjectId,
    W.util.dragdataObjectSnapshotId,
    W.util.dragsystem,
  );
};

W.util.ondragend = function (event) {
  var selected = W.util.dragstartUL.getElementsByClassName("selected");
  for (var i = 0; i < selected.length; i++) {
    W.css.removeClasses(selected[i], W.util.draggingclass);
  }
  if (W.util.dragframe)
    W.util.dragframe.removeEventListener("dragenter", W.util.ondragenterframe);
  if (W.util.dragexitElements) {
    for (i = 0; i < W.util.dragexitElements.length; i++) {
      W.util.dragexitElements[i].removeEventListener(
        "dragenter",
        W.util.ondragexit,
      );
    }
  }
  W.util.dragoverLI &&
    W.css.removeClasses(W.util.dragoverLI, W.util.dragoverclass);
  W.util.dragoverLI = 0;
  document.body.removeChild(W.util.dragUL);
};

W.util.dragoverEl = 0;
W.util.dragoverEl_time = 0;

W.util.dragclick = function (el, delay) {
  el.addEventListener(
    "dragover",
    function (event) {
      var d = new Date();
      if (event.target != W.util.dragoverEl) {
        W.util.dragoverEl = event.target;
        W.util.dragoverEl_time = d.getTime();
      } else {
        if (delay > 0 && d.getTime() - W.util.dragoverEl_time > delay * 2) {
          W.util.dragoverEl_time = d.getTime();
        } else if (d.getTime() - W.util.dragoverEl_time > delay) {
          event.target.onclick();
        }
      }
    },
    false,
  );
};

// Utility to convert the text value of panel.style.transform
// into x and y values
W.util.getTranslate = (panel) => {
  const transform = panel.style.transform;
  const match = transform.match(
    /translate\((-?\d+(\.\d+)?)px,\s*(-?\d+(\.\d+)?)px\)/,
  );
  if (match) {
    return {
      x: parseFloat(match[1]),
      y: parseFloat(match[3]),
    };
  }
  return { x: 0, y: 0 };
};

// Utility function to drag an element around. It is used by
// - menu.js
// - popup.js

W.util.initDrag = function (grabBarElement, panel, endDragfn, context) {
  // grabBarElement:   the element being grabbed by the mouse or touch
  // panel:            the element being moved
  // endDragfn:        a function to be called by endDrag
  // context:          will be passed as a parameter to endDragfn

  let startX = 0;
  let startY = 0;
  let currentX = 0;
  let currentY = 0;
  let dragging = false;

  const startDrag = (x, y) => {
    const offset = W.util.getTranslate(panel);
    startX = x;
    startY = y;
    currentX = offset.x;
    currentY = offset.y;
    dragging = true;
    panel.style.transition = "none";
    grabBarElement.classList.add("cursor-grabbing");
  };

  const doDrag = (x, y) => {
    if (!dragging) return;
    const dx = x - startX;
    const dy = y - startY;
    const newX = currentX + dx;
    const newY = currentY + dy;
    panel.style.transform = `translate(${newX}px, ${newY}px)`;
  };

  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    panel.style.transition = "transform 0.2s ease";
    grabBarElement.classList.remove("cursor-grabbing");
    if (endDragfn) endDragfn(context);
  };

  // Mouse events
  grabBarElement.addEventListener("mousedown", (e) => {
    e.preventDefault();
    startDrag(e.clientX, e.clientY);
    document.addEventListener("mousemove", mouseMove);
    document.addEventListener("mouseup", mouseUp);
  });

  const mouseMove = (e) => doDrag(e.clientX, e.clientY);
  const mouseUp = () => {
    endDrag();
    document.removeEventListener("mousemove", mouseMove);
    document.removeEventListener("mouseup", mouseUp);
  };

  // Touch events
  grabBarElement.addEventListener(
    "touchstart",
    (e) => {
      if (e.touches.length !== 1) return;
      const touch = e.touches[0];
      startDrag(touch.clientX, touch.clientY);
    },
    { passive: true },
  );

  grabBarElement.addEventListener(
    "touchmove",
    (e) => {
      if (!dragging || e.touches.length !== 1) return;
      const touch = e.touches[0];
      doDrag(touch.clientX, touch.clientY);
    },
    { passive: true },
  );

  grabBarElement.addEventListener("touchend", endDrag);
  grabBarElement.addEventListener("touchcancel", endDrag);
};

// This function gets bound to each new popup or menu object.
// It tries to keep the popup or menu within the
// bounds of the parent window (plus a margin)

W.util.constrain = function () {
  const panel = this.frame;
  const margin = 20; // Tweak as desired

  const translate = W.util.getTranslate(panel);
  const rect = panel.getBoundingClientRect();
  const top_limit = margin;
  const bottom_limit = document.body.clientHeight - margin;
  const left_limit = margin;
  const right_limit = document.body.clientWidth - margin;

  let available = 0,
    required = 0,
    leftshift = 0,
    topshift = 0;

  if (rect.right > right_limit && rect.left > left_limit) {
    available = rect.left - left_limit;
    required = rect.right - right_limit;
    leftshift = -Math.min(available, required);
  }

  if (rect.left < left_limit && rect.right < right_limit) {
    available = right_limit - rect.right;
    required = left_limit - rect.left;
    leftshift = Math.min(available, required);
  }

  if (rect.bottom > bottom_limit && rect.top > top_limit) {
    available = rect.top - top_limit;
    required = rect.bottom - bottom_limit;
    topshift = -Math.min(available, required);
  }

  if (rect.top < top_limit && rect.bottom < bottom_limit) {
    available = bottom_limit - rect.bottom;
    required = top_limit - rect.top;
    topshift = Math.min(available, required);
  }
  // Use style.top and style.left if there is no translate
  // in effect
  if (translate.x === 0 && translate.y == 0) {
    panel.style.top = "" + (rect.top + topshift) + "px";
    panel.style.left = "" + (rect.left + leftshift) + "px";
  } else {
    // Use transform if translate is in effect
    let newX = translate.x + leftshift;
    let newY = translate.y + topshift;
    panel.style.transform = `translate(${newX}px, ${newY}px)`;
  }
};

W.util.check_auth = function (cb) {
  // cb: 	a function in the form:
  //			function(auth){}
  //		where auth is true or false

  var jsonStr = W.system.get_jsonStr("system.check_auth");
  W.util.JSONpost("/json", jsonStr, function (o) {
    cb(o.results == true ? true : false);
  });
};

W.util.isDesktop = function () {
  return window.matchMedia("(min-width: 1024px)").matches;
};

W.util.toast = (text, duration = 2000) => {
  // 2 seconds
  const toast = document.getElementById("toast");
  toast.innerHTML = text;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
};

W.util.formatBreakableText = function (text, maxChunkLength = 30) {
  return text
    .replace(/([,{:}])/g, "$1\u200B") // Add zero-width space after delimiters
    .replace(new RegExp(`(.{${maxChunkLength}})(?!$)`, "g"), "$1\u200B"); // Optional: Insert breaks if no natural ones
};

// This will insert soft hyphens (&shy;) where required
// in every element whose classList contains "hyphens-auto"
W.util.hyphenate = function () {
  const elements = document.querySelectorAll(".hyphens-auto");
  if (!elements.length) return;

  const tempSpan = document.createElement("span");
  tempSpan.style.visibility = "hidden";
  tempSpan.style.position = "absolute";
  tempSpan.style.whiteSpace = "nowrap";
  document.body.appendChild(tempSpan);

  const measureText = (text, font) => {
    tempSpan.style.font = font;
    tempSpan.textContent = text;
    return tempSpan.offsetWidth;
  };

  elements.forEach((container) => {
    const originalText = container.textContent.replace(/\u00AD/g, "");
    const words = originalText.split(/(\s+)/);
    let resultHTML = "";
    let longWordFound = false;

    for (let word of words) {
      if (word.length > 15) {
        longWordFound = true;
        break; // Exit loop early if a long word that needs hyphenation is found.
      }
    }
    if (!longWordFound) return;

    // Process all words if long words needing hyphenation were found
    const containerWidth = container.clientWidth;
    const computedStyle = window.getComputedStyle(container);
    const font = computedStyle.font;

    for (let word of words) {
      if (word.trim().length === 0) {
        resultHTML += word;
        continue;
      }

      if (word.length <= 15 || measureText(word, font) <= containerWidth) {
        resultHTML += word;
      } else {
        let broken = "";
        let remainingWord = word;

        while (remainingWord.length > 0) {
          let low = 0;
          let high = remainingWord.length - 1;
          let breakIndex = -1;

          while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            if (
              measureText(remainingWord.slice(0, mid + 1) + "-", font) <=
              containerWidth
            ) {
              breakIndex = mid;
              low = mid + 1;
            } else {
              high = mid - 1;
            }
          }

          if (breakIndex !== -1) {
            broken += remainingWord.slice(0, breakIndex + 1) + "&shy;";
            remainingWord = remainingWord.slice(breakIndex + 1);
          } else {
            broken += remainingWord.slice(0, 1) + "&shy;";
            remainingWord = remainingWord.slice(1);
          }
        }
        resultHTML += broken;
      }
    }
    container.innerHTML = resultHTML;
  });

  document.body.removeChild(tempSpan);
};

W.util.fixAlbumArtURL = function (uri) {
  if (!uri || !uri.includes("get_cover?")) {
    return uri;
  }

  const isSecure = window.location.protocol === "https:";
  const securePort = W.data.https_port;

  try {
    const url = new URL(uri, window.location.origin);

    if (isSecure) {
      if (url.protocol === "http:") {
        url.protocol = "https:";
        url.port = securePort;

        // Only rewrite hostname if it's localhost or something invalid
        // Otherwise preserve the server that actually hosts the image
        if (
          url.hostname === "localhost" ||
          url.hostname === "127.0.0.1" ||
          url.hostname.endsWith(".local")
        ) {
          url.hostname = window.location.hostname;
        }
      }
    }

    return url.toString();
  } catch (e) {
    console.warn("Invalid album art URI:", uri);
    return uri;
  }
};

W.util.ready(function () {
  W.util.Input = document.querySelector("#W-util-input");
  W.util.Input && document.body.removeChild(W.util.Input);
  W.util.mediaQuery = window.matchMedia("(min-width: 1024px)");
  W.util.mediaQuery.addEventListener("change", () => {
    W.util.Popup.frame.visible && W.util.Popup.resize();
  });
});

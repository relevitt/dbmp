// This is used to ensure that if we're showing a menu then,
// upon a switch to mobile, we'll continue to display the
// associated screen
W.menus = [];

W.menu = function (args) {
  /*
		args.items:       array of menu items:
                        items[].label
                        items[].onclick
                        items[].sticky: if true, don't hide the menu when the item
                          is clicked (default: false)

                        -or-

                        items[].label
                        items[].submenu: array of submenuitems:
                          submenuitems[].label
                          submenuitems[].onclick
                        items[].init: function to be executed before the submenu is displayed

                        -or-

                        items[].label
                        items[].submenu: an empty array
                        items[].create_items_fn: a function that will be called when the menu item 
                          is clicked. The create_items_fn will be passed a callback and 
                          menu_object (see below)as its only parameters. In order to build 
                          and show the submenu, the callback must be called with an 
                          array of submenu items:
                            submenuitems[].label
                            submenuitems[].onclick
                          and optionally:
                            a function to be called if there is a vertical scroll 
                              event on the subsubmenu
                            a function to be executed when the submenu is hidden

                      submenus can be recursive (i.e. subsubmenus)

		args.showClass: 	the class of the elements, if any, which will display the menu if clicked; 
					            used to derive the index of the clicked element; leave undefined if inapplicable

		args.showingClass:the class to be applied to the clicked element while the menu is displaying;
					            if no parameter is given, the default class ("menu_selected") will
								      be applied; if an empty string is given, no class will be applied

		args.menuDirection:'right' to display the menu to the right of the clicked element (the default)
					            'bottom' to display the menu below the clicked element
					            'over' to align the top left corners
                      'topleft' to display menu above and to the left

		args.init: 		    function to be executed before the menu is displayed;
					            if the function returns false, the menu will not be displayed

    args.before_click:function to be executed just before items[].onclick is executed (eg to remove
                      styling). Called with {e:e}, where e is the click event

    args.display:     function to be executed after the menu is displayed

		args.hide:		    function to be executed when the menu is hidden

    args.close:       bespoke close function to be called when close icon (mobile only) is clicked

		args.sticky:		  if set to true, the menu won't be hidden, until menu.hide_now() is called

		args.locationElement:	if provided, the menu will be positioned relative to args.locationElement

		args.check_auth:	if set to true, the menu will display only after W.util.check_auth has
							        performed successfully
	*/

  var div;
  var submenu;
  var menu_object;
  this.showClass = args.showClass;
  this.showingClass =
    args.showingClass == undefined ? "menu_selected" : args.showingClass;
  this.menuDirection =
    args.menuDirection == undefined ? "right" : args.menuDirection;
  this.init = args.init;
  this.before_click = args.before_click;
  this.check_auth = args.check_auth;
  this.menuDisplay = args.display;
  this.menuHide = args.hide;
  this.menuClose = args.close;
  this.sticky = args.sticky;
  this.locationElement = args.locationElement;
  this.shifted_position = {};
  this.showing = false;
  this.index = -1;
  this.menu_objects = [];
  this.submenus = [];
  this.submenuParentDiv = undefined;
  this.submenuShowing = undefined;
  this.frame = W.menu.Frame.cloneNode(true);
  this.innerframe = this.frame.querySelector(".W-menu-innerframe");
  this.container = this.frame.querySelector(".W-menu-container");
  document.body.appendChild(this.frame);
  W.menus.push(this);

  this.show = this.show.bind(this);
  this.hide = this.hide.bind(this);
  this.hide_now = this.hide_now.bind(this);
  this.display = this.display.bind(this);
  this.conceal = this.conceal.bind(this);
  this.update_display = this.update_display.bind(this);
  this.redisplay = this.redisplay.bind(this);
  this.click_despatcher = this.click_despatcher.bind(this);
  this.shift = this.shift.bind(this);
  this.reposition = this.reposition.bind(this);
  this.constrain = W.util.constrain.bind(this);
  this.onresize = W.util.debounce(this.redisplay, 100);
  this.reset_position = W.util.debounce(this.reset_position, 200).bind(this);

  for (var i = 0; i < args.items.length; i++) {
    if (args.items[i].submenu != undefined) {
      div = W.menu.RowParent.cloneNode();
    } else {
      div = W.menu.Row.cloneNode();
    }
    div.innerHTML = args.items[i].label;
    menu_object = {};
    menu_object.div = div;
    if (args.items[i].onclick != undefined)
      menu_object.onclick = W.menu.getClickFunction(
        this,
        args.items[i].onclick,
      );
    menu_object.sticky = args.items[i].sticky;
    if (args.items[i].submenu != undefined) {
      menu_object.is_submenu_parent = true;
      if (args.items[i].submenu.length) {
        submenu = new W.submenu(
          this,
          div,
          args.items[i].submenu,
          args.items[i].init,
        );
        menu_object.onclick = W.menu.getClickFunction(this, submenu.show);
        this.submenus.push(submenu);
      } else if (args.items[i].create_items_fn) {
        menu_object.create_items_fn = args.items[i].create_items_fn;
        menu_object.menu = this;
        menu_object.showing = false;
        menu_object.onclick = function (e) {
          if (this.showing) {
            this.showing = false;
            this.menu.submenuShowing && this.menu.submenuShowing.hide();
            return;
          }
          var cb = function (items, onscroll, onhide) {
            var div = e.target;
            this.menu.create_ondemand_submenu(
              this,
              e,
              div,
              items,
              onscroll,
              onhide,
            );
            this.showing = true;
          }.bind(this);
          this.create_items_fn(cb, this);
        }.bind(menu_object);
      }
    }
    this.menu_objects.push(menu_object);
    this.container.appendChild(div);
  }
  W.util.initDrag(
    this.frame.querySelector(".W-menu-dragbar"),
    this.frame,
    (context) => {
      const rect = context.frame.getBoundingClientRect();
      context.anchor = { x: rect.left, y: rect.top };
    },
    this,
  );
};

W.menu.prototype.children = function () {
  return this.innerframe.querySelectorAll(".W-menu-row, .W-menu-row-parent");
};

W.menu.prototype.show = function (e, auth_checked) {
  var index = -1;
  if (this.showClass) {
    var showItems = document.querySelectorAll(this.showClass);
    for (var i = 0; i < showItems.length; i++) {
      if (e.target == showItems[i]) index = i;
    }
  } else index = 0;
  if (this.index < 0 || (this.index >= 0 && this.index != index)) {
    this.submenuShowing && this.submenuShowing.hide();
    if (this.check_auth && !auth_checked) {
      W.util.check_auth(
        function (auth) {
          auth && this.show(e, true);
        }.bind(this),
      );
      return;
    }
    this.targetElement = this.locationElement || e.target;
    if (this.init) {
      if (this.init(index, e) == false) return;
    }
    if (this.index >= 0 && this.showClass && this.showingClass) {
      W.css.removeClasses(
        document.querySelectorAll(this.showClass)[this.index],
        this.showingClass,
      );
    }
    const children = this.children();
    for (i = 0; i < children.length; i++) {
      W.css.removeClasses(children[i], "menu_locked");
    }
    if (this.lockedItems) {
      for (i = 0; i < this.lockedItems.length; i++) {
        children[this.lockedItems[i]] &&
          W.css.addClasses(children[this.lockedItems[i]], "menu_locked");
      }
    }
    if (this.showingClass) W.css.addClasses(e.target, this.showingClass);
    this.showing = true;
    this.update_display();
    window.addEventListener("resize", this.onresize);
    this.index = index;
    !this.showClass &&
      !this.parentElement_set_by_add &&
      e &&
      (this.parentElement = e.target);
    document.addEventListener("click", this.click_despatcher);
    !this.sticky && document.addEventListener("keydown", this.hide);
    this.menuDisplay && this.menuDisplay();
    return;
  }
  this.hide();
};

W.menu.prototype.hide = function () {
  this.submenuShowing && this.submenuShowing.hide();
  !this.sticky && this.hide_now();
};

W.menu.prototype.hide_now = function () {
  if (!this.showing) return;
  this.showing = false;
  this.anchor = undefined;
  if (this.showClass && this.showingClass) {
    W.css.removeClasses(
      document.querySelectorAll(this.showClass)[this.index],
      this.showingClass,
    );
  } else if (!this.showClass && this.showingClass) {
    W.css.removeClasses(this.parentElement, this.showingClass);
  }
  this.update_display();
  window.removeEventListener("resize", this.onresize);
  this.index = -1;
  document.removeEventListener("click", this.click_despatcher);
  !this.sticky && document.removeEventListener("keydown", this.hide);
  this.submenuShowing && this.submenuShowing.hide();
  if (this.menuHide) this.menuHide();
};

W.menu.prototype.display = function () {
  W.css.removeClasses(this.frame, "menu_visible", "hidden");
  W.css.addClasses(this.frame, "menu_visible");
  this.reposition();
};

W.menu.prototype.conceal = function () {
  W.css.removeClasses(this.frame, "menu_visible", "hidden");
  W.css.addClasses(this.frame, "hidden");
  this.frame.style.transform = "translate(0px, 0px)";
};

// This is triggered by show or hide and, in the case of a
// submenu showing or hiding, it cascades back up to the
// top menu

W.menu.prototype.update_display = function () {
  if (W.util.isDesktop()) {
    if (this.showing) this.display();
    else this.conceal();
  } else {
    if (this.showing && !this.submenuShowing) this.display();
    else this.conceal();
  }
};

// This is triggered by crossing the window resizing and
// cascades down from the top menu to the last showing submenu

W.menu.prototype.redisplay = function () {
  if (W.util.isDesktop()) {
    if (this.showing) this.display();
    else this.conceal();
  } else {
    if (this.showing && !this.submenuShowing) this.display();
    else this.conceal();
  }
  this.submenuShowing && this.submenuShowing.redisplay();
};

W.menu.prototype.click_despatcher = function (e) {
  if (this.frame.contains(e.target)) return this.onclick(e);
  var check_submenus = function (menu) {
    if (menu.submenuShowing) {
      if (menu.submenuShowing.frame.contains(e.target))
        return menu.submenuShowing;
      return check_submenus(menu.submenuShowing);
    }
  };
  var result = check_submenus(this);
  if (result) return result.onclick(e);
  if (this.showClass) {
    var showItems = document.querySelectorAll(this.showClass);
    for (var i = 0; i < showItems.length; i++) {
      if (showItems[i].contains(e.target)) return;
    }
  } else if (this.parentElement && this.parentElement.contains(e.target))
    return;
  this.hide();
};

W.menu.prototype.add = function (el) {
  /*
		el: the element which when clicked will show the menu
	*/
  el.addEventListener("click", this.show, true);
  if (!this.showClass) {
    this.parentElement = el;
    this.parentElement_set_by_add = true;
  }
};

W.menu.getClickFunction = function (menu, fn) {
  return function (e) {
    var index = Array.prototype.indexOf.call(this.children(), e.target);
    if (this.lockedItems != undefined && this.lockedItems.indexOf(index) >= 0)
      return;
    fn(e);
  }.bind(menu);
};

W.menu.prototype.create_ondemand_submenu = function (
  parent_menu_object,
  e,
  div,
  items,
  onscroll,
  onhide,
) {
  if (!items || !items.length) return;
  var submenu = new W.submenu(this, div, items);
  submenu.parent_menu_object = parent_menu_object; //Should this be standardised for all submenus?
  submenu.ondemand = true;
  onscroll && (submenu.onscroll = throttle(onscroll, 66));
  submenu.onscroll &&
    submenu.container.addEventListener("scroll", submenu.onscroll);
  submenu.onhide = onhide;
  this.submenus.push(submenu);
  submenu.show(e);
};

W.menu.prototype.onclick = function (e) {
  if (this.innerframe.querySelector(".W-menu-close").contains(e.target)) {
    if (this.menuClose) this.menuClose();
    else this.hide_now();
    return;
  }
  if (this.innerframe.querySelector(".W-menu-bar").contains(e.target)) {
    return;
  }
  const children = this.children();
  for (var i = 0; i < children.length; i++) {
    if (children[i].contains(e.target)) break;
  }
  if (
    this.submenuShowing &&
    this.submenuParentDiv != this.menu_objects[i].div
  ) {
    this.submenuShowing.hide();
  }
  this.before_click && this.before_click({ e: e });
  this.menu_objects[i].onclick(e);
  if (this.menu_objects && this.menu_objects[i]) {
    if (this.menu_objects[i].sticky) return;
    if (this.menu_objects[i].is_submenu_parent) return;
  }
  this.hide();
};

W.menu.prototype.shift = function (x, y) {
  this.shifted_position.x = x;
  this.shifted_position.y = y;
  this.showing && this.reposition();
};

W.menu.prototype.reposition = function () {
  var rect = this.targetElement.getBoundingClientRect();
  var top = rect.top;
  var bottom = rect.bottom;
  var left = rect.left;
  var right = rect.right;
  this.shifted_position.x != undefined &&
    (left = right = this.shifted_position.x);
  this.shifted_position.y != undefined &&
    (top = bottom = this.shifted_position.y);
  if (!W.util.isDesktop() && this.anchor) {
    top = this.anchor.y;
    left = this.anchor.x;
  } else if (this.menuDirection == "right") {
    var menuRect = this.frame.getBoundingClientRect();
    var menuTop = top - 4;
    var vpTop = window.innerHeight - menuRect.height;
    top = Math.min(menuTop, vpTop);
    left = right + 14;
  } else if (this.menuDirection == "bottom") {
    top = bottom + 10;
    left = Math.max(left, right - this.frame.clientWidth);
  } else if (this.menuDirection == "over") {
    // We use defaults
  } else if (this.menuDirection == "topleft") {
    var menuRect = this.frame.getBoundingClientRect();
    top = Math.max(0, top - menuRect.height - 24);
    left = Math.max(0, right - menuRect.width + 2);
  }
  this.frame.style.top = "" + top + "px";
  this.frame.style.left = "" + left + "px";
  this.constrain();
  rect = this.frame.getBoundingClientRect();
  this.anchor = { x: rect.left, y: rect.top };
};

W.menu.prototype.remove = function () {
  while (this.submenus.length) {
    this.submenus.pop().remove();
  }
  this.parentElement_set_by_add &&
    this.parentElement.removeEventListener("click", this.show, true);
  document.removeEventListener("click", this.click_despatcher);
  !this.sticky && document.removeEventListener("keydown", this.hide);
  document.body.removeChild(this.frame);
  W.util.strip_object(this);
};

W.menu.prototype.reset_position = function () {
  this.anchor = undefined;
  this.frame.style.transform = "translate(0px, 0px)";
};

W.submenu = function (parentMenu, parentDiv, items, init) {
  /*
		parentMenu: the W.menu or W.submenu object of which this is a submenu,
		parentDiv: the div element of the parentMenu which, when clicked,
			   shows this submenu,
		items: array of submenu items
			items[].onclick
			items[].label,

			-or-

			items[].label
			items[].submenu: array of sub-submenuitems:
				sub-submenuitems[].label
				sub-submenuitems[].onclick
			items[].init: function to be executed before the sub-submenu is displayed

			-or-

			items[].label
			items[].submenu: an empty array
			items[].create_items_fn: a function that will be called when the submenu item 
				is clicked. The create_items_fn will be passed a callback and menu_object (see below) 
				as its only parameters.	In order to build and show the sub-submenu, the callback must be
				called with an array of	sub-submenu items:
					sub-submenuitems[].label
					sub-submenuitems[].onclick
				and optionally:
					a function to be called if there is a vertical scroll event on the subsubmenu
					a function to be executed when the subsubmenu is hidden

		init: function to be executed before this submenu is displayed
	*/

  var div;
  this.parentMenu = parentMenu;
  this.parentDiv = parentDiv;
  this.init = init;
  this.showing = false;
  this.menu_objects = [];
  this.submenus = [];
  this.submenuParentDiv = undefined;
  this.submenuShowing = undefined;
  this.frame = W.submenu.Frame.cloneNode(true);
  this.container = this.frame.querySelector(".W-submenu-container");
  document.body.appendChild(this.frame);

  this.show = this.show.bind(this);
  this.hide = this.hide.bind(this);
  this.display = this.display.bind(this);
  this.conceal = this.conceal.bind(this);
  this.update_display = this.update_display.bind(this);
  this.redisplay = this.redisplay.bind(this);
  this.reposition = this.reposition.bind(this);
  this.constrain = W.util.constrain.bind(this);
  // this.check_size = this.check_size.bind(this);

  this.add_items(items);
  this.set_title();
  W.util.initDrag(
    this.frame.querySelector(".W-submenu-dragbar"),
    this.frame,
    (context) => {
      const rect = context.frame.getBoundingClientRect();
      context.anchor = { x: rect.left, y: rect.top };
    },
    this,
  );
};

W.submenu.prototype.children = function () {
  return this.frame.querySelectorAll(".W-submenu-row, .W-submenu-row-parent");
};

W.submenu.prototype.show = function (e) {
  if (!this.showing) {
    if (this.init) this.init(this);
    this.submenuShowing && this.submenuShowing.hide();
    this.showing = true;
    this.parentMenu.submenuParentDiv = this.parentDiv;
    this.parentMenu.submenuShowing = this;
    this.parentItemRect = this.parentDiv.getBoundingClientRect();
    W.css.addClasses(this.parentDiv, "menu_selected");
    const children = this.children();
    for (i = 0; i < children.length; i++) {
      W.css.removeClasses(children[i], "menu_locked");
    }
    if (this.lockedItems) {
      for (i = 0; i < this.lockedItems.length; i++) {
        W.css.addClasses(children[this.lockedItems[i]], "menu_locked");
      }
    }
    this.update_display();
    return;
  }
  this.hide();
};

W.submenu.prototype.hide = function () {
  if (!this.showing) return;
  this.showing = false;
  W.css.removeClasses(this.parentDiv, "menu_selected");
  this.parent_menu_object && (this.parent_menu_object.showing = false);
  if (this.parentMenu.submenuShowing == this)
    this.parentMenu.submenuShowing = undefined;
  this.submenuShowing && this.submenuShowing.hide();
  this.update_display();
  this.onhide && this.onhide();
  this.ondemand && this.remove();
};

W.submenu.prototype.display = function () {
  W.css.removeClasses(this.frame, "menu_visible", "hidden");
  W.css.addClasses(this.frame, "menu_visible");
  this.reposition();
};

W.submenu.prototype.conceal = function () {
  W.css.removeClasses(this.frame, "menu_visible", "hidden");
  W.css.addClasses(this.frame, "hidden");
  this.frame.style.transform = "translate(0px, 0px)";
  let parent = this;
  while (parent.parentMenu) {
    parent = parent.parentMenu;
    parent.anchor = this.anchor;
  }
};

// This is triggered by show or hide and cascades back
// up to the top menu

W.submenu.prototype.update_display = function () {
  if (W.util.isDesktop()) {
    if (this.showing) this.display();
    else this.conceal();
  } else {
    if (this.showing && !this.submenuShowing) this.display();
    else this.conceal();
  }
  this.parentMenu.update_display();
};

// This is triggered by the window resizing and
// cascades down from the top menu

W.submenu.prototype.redisplay = function () {
  if (W.util.isDesktop()) {
    this.parentItemRect = this.parentDiv.getBoundingClientRect();
    if (this.showing) this.display();
    else this.conceal();
  } else {
    if (this.showing && !this.submenuShowing) this.display();
    else this.conceal();
  }
  this.submenuShowing && this.submenuShowing.redisplay();
};

W.submenu.prototype.reposition = function () {
  this.anchor = this.parentMenu.anchor;
  var submenuRect = this.frame.getBoundingClientRect();
  const vpTop = Math.max(0, window.innerHeight - submenuRect.height - 20); //20px to leave a margin at page bottom
  const vpLeft = Math.max(0, window.innerWidth - submenuRect.width - 20); //20px to leave a margin at page right

  var top, left;

  if (W.util.isDesktop()) {
    top = this.parentItemRect.top;
    left = this.parentItemRect.right + 10;
  } else {
    top = this.anchor.y;
    left = this.anchor.x;
  }

  top = Math.min(top, vpTop);
  left = Math.min(left, vpLeft);
  this.frame.style.top = "" + top + "px";
  this.frame.style.left = "" + left + "px";

  this.constrain();
  // this.check_size();

  submenuRect = this.frame.getBoundingClientRect();
  this.anchor = { x: submenuRect.left, y: submenuRect.top };
  let parent = this;
  while (parent.parentMenu) {
    parent = parent.parentMenu;
    parent.anchor = this.anchor;
  }
};

// // Unclear why, but we have to add two pixels to prevent
// // the scrollbar from always being displayed. It's a hack, but
// // couldn't easily debug the problem.
// W.submenu.prototype.check_size = function () {
//   if (this.size_checked) return;
//   this.size_checked = true;
//   let rect = this.container.getBoundingClientRect();
//   this.container.style.height = "" + (rect.height + 2) + "px";
// };

W.submenu.prototype.add_items = function (items, dont_widen) {
  this.dont_widen = dont_widen;
  var submenu;
  var menu_object;
  for (var i = 0; i < items.length; i++) {
    if (items[i].submenu != undefined) {
      div = W.submenu.RowParent.cloneNode();
    } else {
      div = W.submenu.Row.cloneNode();
    }
    div.innerHTML = items[i].label;
    menu_object = {};
    menu_object.div = div;
    if (items[i].onclick != undefined) menu_object.onclick = items[i].onclick;
    if (items[i].submenu != undefined) {
      menu_object.is_submenu_parent = true;
      if (items[i].submenu.length) {
        submenu = new W.submenu(this, div, items[i].submenu, items[i].init);
        menu_object.onclick = submenu.show;
        this.submenus.push(submenu);
      } else if (items[i].create_items_fn) {
        menu_object.create_items_fn = items[i].create_items_fn;
        menu_object.menu = this;
        menu_object.showing = false;
        menu_object.onclick = function (e) {
          if (this.showing) {
            this.showing = false;
            this.menu.submenuShowing && this.menu.submenuShowing.hide();
            return;
          }
          var cb = function (items, onscroll, onhide) {
            var div = e.target;
            this.menu.create_ondemand_submenu(
              this,
              e,
              div,
              items,
              onscroll,
              onhide,
            );
            this.showing = true;
          }.bind(this);
          this.create_items_fn(cb, this);
        }.bind(menu_object);
      }
    }
    this.menu_objects.push(menu_object);
    this.container.appendChild(div);
  }
};

W.submenu.prototype.set_title = function () {
  let title = "";
  let parent_text = this.parentDiv.textContent;
  if (this.parentMenu.parentDiv != undefined) {
    title = this.parentMenu.parentDiv.textContent + " ";
    parent_text = parent_text.toLowerCase();
  }
  title = title + parent_text + ":";
  title = title.replace(/\bspotify\b/i, "Spotify");
  title = title.replace(/\bsonos\b/i, "Sonos");
  const titleDiv = this.frame.querySelector(".W-submenu-title");
  titleDiv.innerHTML = title;
};

W.submenu.prototype.create_ondemand_submenu = function (
  parent_menu_object,
  e,
  div,
  items,
  onscroll,
  onhide,
) {
  if (!items || !items.length) return;
  var submenu = new W.submenu(this, div, items);
  submenu.parent_menu_object = parent_menu_object;
  onscroll && (submenu.onscroll = throttle(onscroll, 66));
  submenu.onscroll &&
    submenu.container.addEventListener("scroll", submenu.onscroll);
  submenu.onhide = onhide;
  submenu.ondemand = true;
  this.submenus.push(submenu);
  submenu.show(e);
};

W.submenu.prototype.onclick = function (e) {
  if (this.frame.querySelector(".W-submenu-back").contains(e.target)) {
    this.hide();
    return;
  }
  if (this.frame.querySelector(".W-submenu-close").contains(e.target)) {
    let parent = this;
    while (parent.parentMenu) parent = parent.parentMenu;
    parent.hide();
    return;
  }
  if (this.frame.querySelector(".W-submenu-bar").contains(e.target)) {
    return;
  }
  if (this.frame.querySelector(".W-submenu-title").contains(e.target)) {
    return;
  }
  var menu_object;
  const children = this.children();
  for (var i = 0; i < children.length; i++) {
    if (children[i].contains(e.target)) {
      menu_object = this.menu_objects[i];
      break;
    }
  }
  if (this.submenuShowing && this.submenuParentDiv != menu_object.div) {
    this.submenuShowing.hide();
  }
  menu_object.onclick(e);
  if (!menu_object.is_submenu_parent) {
    var top_menu = this.parentMenu;
    while (top_menu.parentMenu) top_menu = top_menu.parentMenu;
    top_menu.hide();
  }
};

W.submenu.prototype.remove = function () {
  this.showing && this.hide();
  var index = this.parentMenu.submenus.indexOf(this);
  if (index > -1) {
    this.parentMenu.submenus.splice(index, 1);
  }
  while (this.submenus.length) {
    this.submenus.pop().remove();
  }
  this.onscroll && this.container.removeEventListener("scroll", this.onscroll);
  document.body.removeChild(this.frame);
  W.util.strip_object(this);
};

W.util.ready(function () {
  //elements for cloning
  W.menu.Frame = document.querySelector(".W-menu-frame");
  W.menu.Row = document.querySelector(".W-menu-row");
  W.menu.RowParent = document.querySelector(".W-menu-row-parent");
  W.submenu.Frame = document.querySelector(".W-submenu-frame");
  W.submenu.Row = document.querySelector(".W-submenu-row");
  W.submenu.RowParent = document.querySelector(".W-submenu-row-parent");
  //now that we have them, remove them from the dom
  W.menu.Row.parentNode.removeChild(W.menu.Row);
  W.menu.RowParent.parentNode.removeChild(W.menu.RowParent);
  document.body.removeChild(W.menu.Frame);
  W.submenu.Row.parentNode.removeChild(W.submenu.Row);
  W.submenu.RowParent.parentNode.removeChild(W.submenu.RowParent);
  document.body.removeChild(W.submenu.Frame);
  W.util.mediaQuery.addEventListener("change", () => {
    var active_menu;
    W.menus.forEach((menu) => {
      menu.showing && (active_menu = menu);
    });
    if (!active_menu) return;
    if (!W.util.isDesktop()) {
      var section = active_menu.targetElement;
      while (!W.system.sectionIDs.includes(section.id)) {
        section = section.parentElement;
        if (section == document.body) return;
      }
      W.system.showSection(section.id);
    }
  });
});

"use strict";

W.paginate = function (args) {
  /* args:
		parent: a UL element,
		dataObject: the dataObject to be paginated,
		dragover: if set to true, dragover will trigger a click after a short delay,
		onclick: custom onclick function (optional),
		now: if set to true, a now link will be displayed,
		now_onclick: custom now onclick function (optional)
	*/
  W.css.removeClasses(args.parent, "hidden", "paginate_visible");
  W.util.stripChildren(args.parent);
  if (args.dataObject.totalRecords <= args.dataObject.pageLength) {
    W.css.addClasses(args.parent, "hidden");
    return;
  }
  W.css.addClasses(args.parent, "paginate_visible");
  var currentPage =
    Math.floor(args.dataObject.startIndex / args.dataObject.pageLength) + 1;
  var totalPages = Math.ceil(
    args.dataObject.totalRecords / args.dataObject.pageLength,
  );
  if (args.now && args.dataObject.queue_position != undefined) {
    var now =
      Math.floor(args.dataObject.queue_position / args.dataObject.pageLength) +
      1;
  }
  var first, prev, next, last;

  first = "&lt;&lt;";
  prev = "&lt;";
  next = "&gt;";
  last = "&gt;&gt;";
  if (W.util.isDesktop()) {
    first = first + " first";
    prev = prev + " prev";
    next = "next " + next;
    last = "last " + last;
  }

  const buildLI = function (now, txt, page, active) {
    var li = W.paginate.LI.cloneNode(true);
    var s = li.querySelector("span");
    s.innerHTML = txt;
    if (active) {
      W.css.addClasses(s, "paginate_active");
    } else if (page) {
      W.css.addClasses(s, "paginate_link");
      s.dataset.startIndex = (page - 1) * args.dataObject.pageLength;
      if (now && args.now_onclick) s.onclick = args.now_onclick;
      else {
        s.onclick = args.onclick
          ? args.onclick
          : function () {
              args.dataObject.get(
                Number(this.dataset.startIndex),
                args.dataObject.id,
              );
            };
      }
      if (args.dragover) W.util.dragclick(s, 500);
    }
    return li;
  };
  if (args.now) {
    if (now != undefined) {
      args.parent.appendChild(buildLI(true, "now", now, false));
    } else {
      args.parent.appendChild(buildLI(true, "now", 0, false));
    }
  }
  if (currentPage > 1) {
    args.parent.appendChild(buildLI(false, first, 1, false));
    args.parent.appendChild(buildLI(false, prev, currentPage - 1, false));
    if (currentPage == totalPages && currentPage - 2) {
      args.parent.appendChild(
        buildLI(false, currentPage - 2, currentPage - 2, false),
      );
    }
    args.parent.appendChild(
      buildLI(false, currentPage - 1, currentPage - 1, false),
    );
  } else {
    args.parent.appendChild(buildLI(false, first, 0, false));
    args.parent.appendChild(buildLI(false, prev, 0, false));
  }
  args.parent.appendChild(buildLI(false, currentPage, currentPage, true));
  if (currentPage < totalPages) {
    args.parent.appendChild(
      buildLI(false, currentPage + 1, currentPage + 1, false),
    );
    if (currentPage == 1 && currentPage + 1 < totalPages) {
      args.parent.appendChild(
        buildLI(false, currentPage + 2, currentPage + 2, false),
      );
    }
    args.parent.appendChild(buildLI(false, next, currentPage + 1, false));
    args.parent.appendChild(buildLI(false, last, totalPages, false));
  } else {
    args.parent.appendChild(buildLI(false, next, 0, false));
    args.parent.appendChild(buildLI(false, last, 0, false));
  }
  var gotoLI = W.paginate.LI.cloneNode(true);
  var gotoSPAN = gotoLI.querySelector("span");
  var gotoSelect = W.paginate.Select.cloneNode(true);
  var gotoOption = gotoSelect.querySelector("option");
  gotoOption.parentNode.removeChild(gotoOption);
  gotoSPAN.appendChild(gotoSelect);
  for (var i = 1; i <= totalPages; i++) {
    let page = gotoOption.cloneNode();
    page.text = i;
    gotoSelect.add(page);
  }
  gotoSelect.value = currentPage;
  args.parent.appendChild(gotoLI);
  gotoSelect.onchange = function (e) {
    e.target.startIndex = (e.target.value - 1) * args.dataObject.pageLength;
    (args.onclick
      ? args.onclick
      : function () {
          args.dataObject.get(
            Number(this.dataset.startIndex),
            args.dataObject.id,
          );
        }
    ).bind(e.target)(e);
  };
};

W.util.ready(function () {
  // elements for cloning
  var ul = document.querySelector("#paginator-for-cloning");
  W.paginate.LI = ul.querySelector("li");
  W.paginate.Select = W.paginate.LI.querySelector("select");
  // now that we have them, remove them from document.body
  W.paginate.Select.parentNode.removeChild(W.paginate.Select);
  ul.removeChild(W.paginate.LI);
  document.body.removeChild(ul);
});

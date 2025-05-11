"use strict";
W.coverartarchive = {};

W.coverartarchive.queue = [];

W.coverartarchive.search = function (args) {
  /*
		args.start:		e.g. 0
		args.artist:	e.g. 'Beatles'
		args.album:		e.g. 'Revolver'
		args.cb:		on success callback function
		args.error:		on error callback function
	*/
  if (W.coverartarchive.queue.push(args) == 1) W.coverartarchive.execute();
};

W.coverartarchive.callnext = function () {
  W.coverartarchive.queue.shift();
  if (W.coverartarchive.queue.length)
    setTimeout(W.coverartarchive.execute, 250);
};

W.coverartarchive.execute = function () {
  var args = W.coverartarchive.queue[0];

  var success = function (o) {
    W.coverartarchive.get_images(o, args);
  };

  var error = function (msg, code, response) {
    args.error ? args.error(msg, code, response) : console.log(msg, code);
    W.coverartarchive.callnext();
  };

  var url = "https://musicbrainz.org/ws/2/release/?query=release:";
  url += "%22" + encodeURIComponent(args.album) + "%22";
  url += "%20AND%20artistname:%22" + encodeURIComponent(args.artist) + "%22";
  if (args.start) url += "&offset=" + args.start;
  url += "&limit=8";
  url += "&fmt=json";

  W.util.GET({
    url: url,
    success: success,
    error: error,
    JSON: true,
  });
};

W.coverartarchive.get_images = function (o, args) {
  var queue = [];
  var results = {};
  var item;

  results.totalRecords = o.count;
  results.uris = [];

  for (item of o.releases) queue.push(item.id);

  function callnext() {
    queue.shift();
    if (queue.length) setTimeout(execute, 25);
    else complete();
  }

  function execute() {
    var id = queue[0];

    var success = function (o) {
      var item;
      var image = "";
      for (item of o.images) {
        if (item.front) {
          image = item.image;
          break;
        }
      }
      results.uris.push(image);
      callnext();
    };

    var error = function (msg, code, response) {
      console.log(msg, code);
      results.uris.push("");
      callnext();
    };

    var url = "https://coverartarchive.org/release/" + id;

    W.util.GET({
      url: url,
      success: success,
      error: error,
      JSON: true,
    });
  }

  function complete() {
    W.coverartarchive.callnext();
    args.cb(results);
  }

  if (queue.length) execute();
  else complete();
};

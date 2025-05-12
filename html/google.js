"use strict";
W.google = {};

W.google.daily_limit_exceeded = false;
W.google.queue = [];

W.google.search = function (args) {
  /*
		args.start:		e.g. 0
		args.num:		number of results to be returned (1-10)
		args.query:		e.g. 'Beatles Revolver'
		args.cb:		on success callback function
		args.error:		on error callback function
	*/

  if (W.google.queue.push(args) == 1) W.google.execute();
};

W.google.callnext = function () {
  W.google.queue.shift();
  if (W.google.queue.length) setTimeout(W.google.execute, 250);
};

W.google.execute = function () {
  var args = W.google.queue[0];
  if (!W.data.google.key || !W.data.google.cx) {
    if (args.error) args.error();
    W.google.callnext();
    return;
  }
  if (W.google.daily_limit_exceeded) {
    args.error
      ? args.error(
          "HTTP error",
          403,
          "Not executing search as Google's daily search limit was exceeded",
        )
      : console.log(
          "Not executing search as Google's daily search limit was exceeded",
        );
    W.google.callnext();
    return;
  }

  var success = function (o) {
    args.cb(o);
    W.google.callnext();
  };
  var error = function (msg, code, response) {
    if (
      code == 403 &&
      JSON.parse(response).error.message == "Daily Limit Exceeded"
    )
      W.google.daily_limit_exceeded = true;
    args.error ? args.error(msg, code, response) : console.log(msg, code);
    W.google.callnext();
  };

  var url = "https://www.googleapis.com/customsearch/v1?";
  url += "key=";
  url += W.data.google.key;
  url += "&cx=";
  url += W.data.google.cx;
  url += "&searchType=image";
  url += "&start=" + (args.start || 1);
  url += "&num=" + (args.num || 10);
  url += "&q=" + encodeURIComponent(args.query.replace(/ /g, "+"));

  W.util.GET({
    url: url,
    success: success,
    error: error,
    JSON: true,
  });
};

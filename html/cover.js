"use strict";

W.cover = {};

W.cover.keyboard_listener_ids = [];

// Initialise and show cover art options

W.cover.click = function (e) {
  if (W.data.status.song.albumid) {
    W.cover.last_search = {};
    W.cover.last_search.artist = W.data.status.song.artist;
    W.cover.last_search.album = W.data.status.song.album;
    W.cover.last_search.artistid = undefined;
    W.cover.last_search.albumid = W.data.status.song.albumid;
    W.cover.last_search.artist_srch = W.data.status.song.artist;
    W.cover.last_search.album_srch = W.data.status.song.album;
    W.cover.show_options();
  }
};

W.cover.artist_search = function (artist, artistid) {
  W.cover.last_search = {};
  W.cover.last_search.artist = artist;
  W.cover.last_search.album = undefined;
  W.cover.last_search.artistid = artistid;
  W.cover.last_search.albumid = undefined;
  W.cover.last_search.artist_srch = artist;
  W.cover.last_search.album_srch = undefined;
  W.cover.show_options();
};

W.cover.album_search = function (artist, album, albumid) {
  W.cover.last_search = {};
  W.cover.last_search.artist = artist;
  W.cover.last_search.album = album;
  W.cover.last_search.artistid = undefined;
  W.cover.last_search.albumid = albumid;
  W.cover.last_search.artist_srch = artist;
  W.cover.last_search.album_srch = album;
  W.cover.show_options();
};

W.cover.show_options = function (e) {
  var items = [
    {
      label: "Search google images",
      click: function (e) {
        W.cover.google_search(
          W.cover.last_search.artist_srch,
          W.cover.last_search.album_srch,
          0,
        );
      },
    },
    {
      label: "Search spotify images",
      click: function (e) {
        W.cover.spotify_search(
          W.cover.last_search.artist_srch,
          W.cover.last_search.album_srch,
          0,
        );
      },
    },
  ];

  if (W.cover.last_search.album)
    items.push({
      label: "Search coverart archive",
      click: function (e) {
        W.cover.coverartarchive_search(
          W.cover.last_search.artist_srch,
          W.cover.last_search.album_srch,
          0,
        );
      },
    });

  items.push(
    {
      label: "Open image file",
      click: W.cover.open_albumdir,
    },
    {
      label: "Blank cover",
      click: W.cover.blank,
    },
    {
      label: "Default cover",
      click: W.cover.remove,
    },
  );

  W.util.Popup.show_options({
    bar: "Choose cover art for:",
    title:
      W.cover.last_search.artist +
      (W.cover.last_search.album ? "/" + W.cover.last_search.album : ""),
    title_wrap: true,
    items: items,
  });
};

//Searching google images

W.cover.google_last_search = {};
W.cover.google_last_search.query = "";
W.cover.google_last_search.urls = [];
W.cover.google_last_search.exhausted = false;

W.cover.google_search = function (artist, album, page) {
  var query = artist + (album ? " " + album : "");
  if (page == undefined) {
    page = 0;
  }
  page = parseInt(page);
  if (W.cover.google_last_search.query != query) {
    W.cover.google_last_search.query = query;
    W.cover.google_last_search.urls = [];
    W.cover.google_last_search.exhausted = false;
    W.cover.google_last_search.next = 1;
  }
  if (
    W.cover.google_last_search.urls.length >= (page + 1) * 4 ||
    (W.cover.google_last_search.urls.length > page * 4 &&
      W.cover.google_last_search.exhausted)
  ) {
    var st = page * 4;
    var en = Math.min(st + 4, W.cover.google_last_search.urls.length);
    var next = page + 1;
    if (
      en == W.cover.google_last_search.urls.length &&
      W.cover.google_last_search.exhausted
    ) {
      next = -1;
    }
    W.util.Popup.processing();
    W.util.Popup.cleanup = function () {};
    W.util.Popup.bar.innerHTML = "Getting images ...";
    W.cover.google_results({
      results: {
        urls: W.cover.google_last_search.urls.slice(st, en),
        prev: page - 1,
        next: next,
      },
    });
    return;
  }
  if (W.cover.google_last_search.exhausted) {
    W.cover.google_results({
      results: {
        urls: [],
        prev: -1,
        next: -1,
      },
    });
    return;
  }
  W.google.search({
    start: W.cover.google_last_search.next,
    query: query,
    cb: function (o) {
      var i = 0;
      if (o.items) {
        for (i = 0; i < o.items.length; i++) {
          W.cover.google_last_search.urls.push(o.items[i].link);
        }
      }
      if (
        !i ||
        o.queries.nextPage == undefined ||
        !o.queries.nextPage[0].count
      ) {
        W.cover.google_last_search.exhausted = true;
      } else {
        W.cover.google_last_search.next = o.queries.nextPage[0].startIndex;
      }
      W.cover.google_search(artist, album, page);
    },
    error: function () {
      W.cover.google_results({
        error: "<b><i>There was an error searching Google.</i></b>",
        results: {
          urls: [],
          prev: -1,
          next: -1,
        },
      });
    },
  });
  W.util.Popup.processing();
  W.util.Popup.cleanup = function () {};
  W.util.Popup.bar.innerHTML = "Searching google ...";
};

W.cover.google_results = function (o) {
  W.cover.last_search.fn = W.cover.google_search;
  W.cover.search_results(o, "Google image search:");
};

//Searching spotify images

W.cover.spotify_last_search = {};
W.cover.spotify_last_search.artist = "";
W.cover.spotify_last_search.album = "";
W.cover.spotify_last_search.urls = [];
W.cover.spotify_last_search.exhausted = false;

W.cover.spotify_search = function (artist, album, page) {
  if (page == undefined) {
    page = 0;
  }
  page = parseInt(page);
  if (
    W.cover.spotify_last_search.artist != artist ||
    W.cover.spotify_last_search.album != album
  ) {
    W.cover.spotify_last_search.artist = artist;
    W.cover.spotify_last_search.album = album;
    W.cover.spotify_last_search.urls = [];
    W.cover.spotify_last_search.exhausted = false;
    W.cover.spotify_last_search.next = 0;
  }
  if (
    W.cover.spotify_last_search.urls.length >= (page + 1) * 4 ||
    (W.cover.spotify_last_search.urls.length > page * 4 &&
      W.cover.spotify_last_search.exhausted)
  ) {
    var st = page * 4;
    var en = Math.min(st + 4, W.cover.spotify_last_search.urls.length);
    var next = page + 1;
    if (
      en == W.cover.spotify_last_search.urls.length &&
      W.cover.spotify_last_search.exhausted
    ) {
      next = -1;
    }
    W.util.Popup.processing();
    W.util.Popup.cleanup = function () {};
    W.util.Popup.bar.innerHTML = "Getting images ...";
    W.cover.spotify_results({
      results: {
        urls: W.cover.spotify_last_search.urls.slice(st, en),
        prev: page - 1,
        next: next,
      },
    });
    return;
  }
  if (W.cover.spotify_last_search.exhausted) {
    W.cover.spotify_results({
      results: {
        urls: [],
        prev: -1,
        next: -1,
      },
    });
    return;
  }
  var jsonStr = W.system.get_jsonStr(
    album ? "spotify.search_albums" : "spotify.search_artists",
  );
  jsonStr.args.id = album ? album : artist;
  if (album && artist) jsonStr.args.artist = artist;
  jsonStr.args.startIndex = W.cover.spotify_last_search.next;
  jsonStr.args.rowsPerPage = 50;

  W.util.JSONpost(
    "/json",
    jsonStr,
    function (o) {
      var i = 0;
      if (o.results && o.results.results) {
        for (i = 0; i < o.results.results.length; i++) {
          W.cover.spotify_last_search.urls.push(o.results.results[i].artURI);
        }
      }
      if (
        !i ||
        o.results.totalRecords <= W.cover.spotify_last_search.next + i
      ) {
        W.cover.spotify_last_search.exhausted = true;
      } else {
        W.cover.spotify_last_search.next += i;
      }
      W.cover.spotify_search(artist, album, page);
    },
    function () {
      W.cover.spotify_results({
        error: "<b><i>There was an error searching Spotify.</i></b>",
        results: {
          urls: [],
          prev: -1,
          next: -1,
        },
      });
    },
  );
  W.util.Popup.processing();
  W.util.Popup.cleanup = function () {};
  W.util.Popup.bar.innerHTML = "Searching spotify ...";
};

W.cover.spotify_results = function (o) {
  W.cover.last_search.fn = W.cover.spotify_search;
  W.cover.search_results(o, "Spotify image search:");
};

//Searching coverartarchive images

W.cover.coverartarchive_last_search = {};
W.cover.coverartarchive_last_search.artist = "";
W.cover.coverartarchive_last_search.album = "";
W.cover.coverartarchive_last_search.urls = [];
W.cover.coverartarchive_last_search.exhausted = false;

W.cover.coverartarchive_search = function (artist, album, page) {
  if (page == undefined) {
    page = 0;
  }
  page = parseInt(page);
  if (
    W.cover.coverartarchive_last_search.artist != artist ||
    W.cover.coverartarchive_last_search.album != album
  ) {
    W.cover.coverartarchive_last_search.artist = artist;
    W.cover.coverartarchive_last_search.album = album;
    W.cover.coverartarchive_last_search.urls = [];
    W.cover.coverartarchive_last_search.exhausted = false;
    W.cover.coverartarchive_last_search.next = 0;
  }
  if (
    W.cover.coverartarchive_last_search.urls.length >= (page + 1) * 4 ||
    (W.cover.coverartarchive_last_search.urls.length > page * 4 &&
      W.cover.coverartarchive_last_search.exhausted)
  ) {
    var st = page * 4;
    var en = Math.min(st + 4, W.cover.coverartarchive_last_search.urls.length);
    var next = page + 1;
    if (
      en == W.cover.coverartarchive_last_search.urls.length &&
      W.cover.coverartarchive_last_search.exhausted
    ) {
      next = -1;
    }
    W.util.Popup.processing();
    W.util.Popup.cleanup = function () {};
    W.util.Popup.bar.innerHTML = "Getting images ...";
    W.cover.coverartarchive_results({
      results: {
        urls: W.cover.coverartarchive_last_search.urls.slice(st, en),
        prev: page - 1,
        next: next,
      },
    });
    return;
  }
  if (W.cover.coverartarchive_last_search.exhausted) {
    W.cover.coverartarchive_results({
      results: {
        urls: [],
        prev: -1,
        next: -1,
      },
    });
    return;
  }

  W.coverartarchive.search({
    start: W.cover.coverartarchive_last_search.next,
    artist: artist,
    album: album,
    cb: function (o) {
      var i = 0;
      if (o.uris.length) {
        for (i = 0; i < o.uris.length; i++) {
          W.cover.coverartarchive_last_search.urls.push(o.uris[i]);
        }
      }
      if (
        !i ||
        o.totalRecords <= W.cover.coverartarchive_last_search.next + i
      ) {
        W.cover.coverartarchive_last_search.exhausted = true;
      } else {
        W.cover.coverartarchive_last_search.next += i;
      }
      W.cover.coverartarchive_search(artist, album, page);
    },
    error: function () {
      W.cover.coverartarchive_results({
        error: "<b><i>There was an error searching coverartarchive.</i></b>",
        results: {
          urls: [],
          prev: -1,
          next: -1,
        },
      });
    },
  });
  W.util.Popup.processing();
  W.util.Popup.cleanup = function () {};
  W.util.Popup.bar.innerHTML = "Searching coverartarchive ...";
};

W.cover.coverartarchive_results = function (o) {
  W.cover.last_search.fn = W.cover.coverartarchive_search;
  W.cover.search_results(o, "coverartarchive image search:");
};

//Displaying search results

W.cover.search_results = function (o, title) {
  if (!o.results) {
    return;
  }
  var div = W.cover.CoverSearch.cloneNode(true);
  var loaded_images = 0;
  var show = function () {
    W.util.Popup.processing("close");
    W.util.Popup.empty();
    W.util.Popup.cleanup = function () {
      W.util.Popup.empty();
    };
    W.util.Popup.content.appendChild(div);
    W.util.Popup.bar.innerHTML = title;
    W.util.Popup.show();
    W.util.Popup.center();
  };
  var loaded = function (e) {
    loaded_images++;
    if (loaded_images >= o.results.urls.length) {
      show();
    }
  };
  var i, buttons, inputs, img, img_div, a;
  buttons = div.querySelectorAll(".cover-search-buttons > span");
  buttons[0].onclick = W.cover.show_options;
  buttons[1].onclick = W.cover.modify_search;
  div.querySelector(".cover-search-title").innerHTML =
    W.cover.last_search.artist +
    (W.cover.last_search.album ? "/" + W.cover.last_search.album : "");
  inputs = div.querySelectorAll(".cover-search-params input");
  inputs[0].value = W.cover.last_search.artist_srch;
  inputs[1].value = W.cover.last_search.album_srch;
  W.cover.last_search.artistid &&
    inputs[1].parentNode.parentNode.removeChild(inputs[1].parentNode);
  inputs.forEach((input) => {
    input.onkeyup = function (e) {
      if (event.keyCode == 13) {
        W.cover.modify_search();
      }
    };
    input.onfocus = function (e) {
      let listener_id = W.keyboard.set_listener();
      W.cover.keyboard_listener_ids.push(listener_id);
    };
    input.onblur = function (e) {
      let listener_id = W.cover.keyboard_listener_ids.pop();
      W.keyboard.restore_previous_listener(listener_id);
    };
  });
  img_div = div.querySelector(".cover-search-images");
  W.util.stripChildren(img_div);
  if (o.error) {
    div.querySelector(".cover-search-instruction").innerHTML = o.error;
    show();
  } else {
    div.querySelector(".cover-search-instruction").innerHTML =
      "Click image to view and select ...";
    for (var i = 0; i < o.results.urls.length; i++) {
      img = W.cover.loadImage(o.results.urls[i], loaded);
      img.onclick = W.cover.show_image;
      img_div.appendChild(img);
    }
    if (!o.results.urls.length) {
      show();
    }
  }
  a = div.querySelectorAll(".cover-search-pagination a");
  if (o.results.prev >= 0) {
    a[0].onclick = W.cover.search_prev;
  }
  if (o.results.next >= 0) {
    a[1].onclick = W.cover.search_next;
  }

  W.cover.last_search.next = o.results.next;
  W.cover.last_search.prev = o.results.prev;
};

W.cover.search_next = function (o) {
  W.cover.last_search.fn(
    W.cover.last_search.artist_srch,
    W.cover.last_search.album_srch,
    W.cover.last_search.next,
  );
};

W.cover.search_prev = function (o) {
  W.cover.last_search.fn(
    W.cover.last_search.artist_srch,
    W.cover.last_search.album_srch,
    W.cover.last_search.prev,
  );
};

W.cover.modify_search = function (e) {
  var inputs = document.querySelectorAll(".cover-search-params > input");
  W.cover.last_search.artist_srch = inputs[0].value;
  W.cover.last_search.album_srch = W.cover.last_search.albumid
    ? inputs[1].value
    : undefined;
  W.cover.last_search.fn(
    W.cover.last_search.artist_srch,
    W.cover.last_search.album_srch,
    0,
  );
};

//Open an image file

W.cover.open_albumdir = function (e) {
  var onload = function () {
    var div = W.util.Popup.content.querySelector(".cover-directory-title");
    div.innerHTML =
      W.cover.last_search.artist +
      (W.cover.last_search.album ? "/" + W.cover.last_search.album : "");
    div = W.util.Popup.content.querySelector(".cover-directory-buttons span");
    div.onclick = W.cover.show_options;
  };
  var jsonStr = W.system.get_jsonStr(
    W.cover.last_search.albumid
      ? "covers.open_albumdir"
      : "covers.open_artistdir",
  );
  jsonStr.args.item_id =
    W.cover.last_search.albumid || W.cover.last_search.artistid;
  W.util.JSONpost("/json", jsonStr, function (o) {
    W.util.Popup.directory({
      title: "Open image file for:",
      items: o.results,
      onfileclick: W.cover.open_imgfile,
      center: true,
      parentnode: W.cover.CoverDirectory.cloneNode(true),
      onload: onload,
    });
  });
};

W.cover.open_imgfile = function (e) {
  var src = "/get_cover?d=" + W.util.Popup.DirName + "&f=" + e.target.filename;
  W.cover.show_image({ target: { src: src } });
};

//View an image

W.cover.show_image = function (e) {
  var img = document.createElement("img");
  img.onload = function (e) {
    W.cover.show_image_popup.close();
    W.cover.show_image_popup.content.appendChild(img);
    W.cover.show_image_popup.show();
    W.cover.show_image_popup.center();
  };
  img.src = e.target.src;
  img.onclick = W.cover.onreplace;
};

//Replace an image

W.cover.replace = function (src, id, is_artist) {
  var jsonStr = W.system.get_jsonStr("covers.replace");
  jsonStr.args.url = src;
  is_artist ? (jsonStr.args.artistid = id) : (jsonStr.args.albumid = id);
  W.util.JSONpost("/json", jsonStr);
};

W.cover.onreplace = function (e) {
  W.cover.show_image_popup.close();
  if (W.cover.last_search.artistid)
    W.cover.replace(e.target.src, W.cover.last_search.artistid, true);
  else W.cover.replace(e.target.src, W.cover.last_search.albumid);
};

//Blank cover

W.cover.blank = function () {
  var url = window.location.href + "icons/blank.png";
  if (W.cover.last_search.artistid)
    W.cover.replace(url, W.cover.last_search.artistid, true);
  else W.cover.replace(url, W.cover.last_search.albumid);
};

//Default cover

W.cover.remove = function (e) {
  var jsonStr = W.system.get_jsonStr("covers.remove");
  if (W.cover.last_search.artistid)
    jsonStr.args.artistid = W.cover.last_search.artistid;
  else jsonStr.args.albumid = W.cover.last_search.albumid;
  W.util.JSONpost("/json", jsonStr);
};

W.cover.loadImage = function (url, cb) {
  var timer;
  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }
  function handleFail() {
    this.onload = this.onabort = this.onerror = function () {};
    clearTimer();
    if (this.src === url) {
      this.src = "icons/no_image.jpg";
    }
    cb();
  }
  var img = W.cover.Image.cloneNode(true);
  img.onerror = img.onabort = handleFail;
  img.onload = function () {
    clearTimer();
    cb();
  };
  img.src = url;
  timer = setTimeout(
    (function (theImg) {
      return function () {
        handleFail.call(theImg);
      };
    })(img),
    5000,
  );
  return img;
};

W.util.ready(function () {
  // elements for cloning
  W.cover.CoverSearch = document.body.querySelector(".cover-search");
  W.cover.CoverDirectory = document.body.querySelector(".cover-directory");
  W.cover.Image = W.cover.CoverSearch.querySelector("img");
  // now that we have them, we remove them from document.body
  document.body.removeChild(W.cover.CoverSearch);
  document.body.removeChild(W.cover.CoverDirectory);
  // initialisation continues ...
  document.querySelector("#player-image").onclick = W.cover.click;
  W.cover.show_image_popup = new W.popup();
  W.css.addClasses(W.cover.show_image_popup.frame, "cover_popup");
  W.cover.show_image_popup.bar.innerHTML = "Click image to replace cover";
  W.cover.show_image_popup.cleanup = function () {
    W.util.stripChildren(W.cover.show_image_popup.content);
  };
});

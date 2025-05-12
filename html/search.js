"use strict";
W.search = {};

W.search.getLI = function (dataRow, number) {
  var LI, number_span, artist_span, album_span, title_span, img_span, img;
  const search_fn = function (e) {
    W.search.new_search(e, {
      index: number - 1,
    });
  };
  switch (W.search.dataObject.metadata.search_type) {
    case "artists":
    case "related_artists":
      LI = W.search.RowSearchResults.cloneNode(true);
      LI.children[1].innerHTML = dataRow.title;
      LI.querySelector("img").src = dataRow.artURI;
      LI.onclick = search_fn;
      break;
    case "albums":
    case "album_from_artistid":
    case "artist_from_track_uri":
    case "playlists":
    case "playlists_from_userid":
      LI = W.search.RowSearchResults.cloneNode(true);
      LI.children[1].innerHTML =
        dataRow.title ||
        W.search.dataObject.metadata.artist + " Recommendations";
      LI.querySelector("img").src =
        dataRow.artURI || W.search.dataObject.metadata.artistArtURI;
      LI.onclick = search_fn;
      break;
    case "songs":
      LI = W.search.RowSearchResultsTrack.cloneNode(true);
      LI.children[1].innerHTML = dataRow.title;
      LI.children[2].innerHTML = dataRow.artist;
      LI.querySelector("img").src = dataRow.artURI;
      LI.onclick = search_fn;
      break;
    case "tracks_from_albumid":
    case "tracks_from_playlistid":
    case "tracks_from_playlistid_from_userid":
    case "tracks_from_trackid":
    case "tracks_from_albumid_from_artistid":
    case "album_from_track_uri":
    case "recommendations_from_track_uri":
    case "find":
      if (
        W.search_top.object == "database" &&
        W.search.dataObject.metadata.item_type != "playlist"
      ) {
        switch (W.search.dataObject.metadata.search_type) {
          default:
            LI = W.search.RowArtistAlbumTrack.cloneNode(true);
            number_span = LI.querySelector(".search-track-number");
            number_span.innerHTML = number;
            W.css.addClasses(number_span, "search_track_hover_play");
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            number_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
          case "find":
            LI = W.search.RowArtistTopTrack.cloneNode(true);
            img = LI.querySelector("img");
            img.src = dataRow.artURI;
            album.span = LI.querySelector(".search-track-album");
            album_span.innerHTML = dataRow.album;
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            img.onclick = W.search.click_function;
            album_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
        }
      } else {
        switch (W.search.dataObject.metadata.item_type) {
          case "album":
            LI = W.search.RowArtistAlbumTrack.cloneNode(true);
            number_span = LI.querySelector(".search-track-number");
            number_span.innerHTML = number;
            W.css.addClasses(number_span, "search_track_hover_play");
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            number_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
          case "album_various":
            LI = W.search.RowVariousAlbumTrack.cloneNode(true);
            number_span = LI.querySelector(".search-track-number");
            number_span.innerHTML = number;
            W.css.addClasses(number_span, "search_track_hover_play");
            artist_span = LI.querySelector(".search-track-artist");
            artist_span.innerHTML = dataRow.artist;
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            number_span.onclick = W.search.click_function;
            artist_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
          case "trackList":
            LI = W.search.RowArtistTopTrack.cloneNode(true);
            img = LI.querySelector("img");
            img.src = dataRow.artURI;
            album_span = LI.querySelector(".search-track-album");
            album_span.innerHTML = dataRow.album;
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            img.onclick = W.search.click_function;
            album_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
          case "program":
          case "playlist":
            LI = W.search.RowArtistRecommendationsTrack.cloneNode(true);
            img = LI.querySelector("img");
            img.src = dataRow.artURI;
            img_span = LI.querySelector(".search-track-image");
            artist_span = LI.querySelector(".search-track-artist");
            artist_span.innerHTML = dataRow.artist;
            album_span = LI.querySelector(".search-track-album");
            album_span.innerHTML = dataRow.album;
            title_span = LI.querySelector(".search-track-title");
            title_span.innerHTML = dataRow.title;
            img_span.onclick = W.search.click_function;
            artist_span.onclick = W.search.click_function;
            album_span.onclick = W.search.click_function;
            title_span.onclick = W.search.click_function;
            LI.addEventListener("contextmenu", W.search_menus.track_menu_show);
            LI.querySelector(".search-track-menu").onclick =
              W.search_menus.track_menu_show;
            break;
        }
      }
      if (W.search.dataObject.metadata.trackid != undefined) {
        const trackid = dataRow.itemid.toString();
        const testid = W.search.dataObject.metadata.trackid.toString();
        const testarray = testid.split(",");
        if (testarray.includes(trackid)) {
          W.css.addClasses(LI, "search_track_highlight");
          W.search.dataObject.metadata.highlit = number;
        }
      }
      break;
    default:
      break;
  }
  return LI;
};

W.search.clear_display = function () {
  W.util.Popup.close(); // In case we're changing coverart
  W.cover.show_image_popup.close(); // Ditto
  W.util.stripChildren(W.search.resultsUL);
  W.search.resultsUL.scrollTop = 0;
};

W.search.build = function (args) {
  // args:
  // 	- refresh
  // 	- restart
  //  - startIndex - if provided, the starting index
  //  - buildSize - if provided, the number of items to be built
  //
  // It might be that the ability to provide startIndex and buildSize is
  // unnecessary and, even if it were necessary, I think it's only being
  // implemented here rather than more generally. It was one attempted
  // fix of problems arising from the fact that spotify can now include
  // lots of empty playlist search results, because it's refusing to return
  // Spotify playlists. As we are only displaying results with content,
  // there's now a mismatch between whats being displayed (no gaps) and
  // the data we're holding (gaps). This means we cannot assume the
  // index of the displayed element matches the index of the data. As a result
  // the onclick search_fn in W.search.getLI above includes the index of the data.
  // However, we were still getting bugs. Eventually, this was traced to an error
  // below where the 'number' parameter being passed to W.search.getLI was
  // being calculated incorrectly. Fixing this resolved the bug. I've kept
  // the startIndex and buildSize parameters nevertheless, as they seem harmless.
  // My concern was that perhaps more data would be received before the last batch
  // of data was fully built, but I don't think this can happen, as I think the
  // whole build process will complete before more data can be received.

  // if we got here via escape, we'll redisplay search text
  const escaped = W.search.escaped;
  W.search.escaped = false;
  var LI;
  escaped && (W.search_top.TxtInput.value = "");
  if (args.refresh) {
    var artist_mode,
      user_mode,
      album_mode,
      playlist_mode,
      categories,
      selected_button,
      params;
    // Now that we have database playlists that have spotify tracks, there is potentially
    // a lot of switching of W.search_top.object between database and spotify.
    // The python module should probably always specify which system the data relates to,
    // but as this is a lot of work, we just set W.search.dataObject.metadata.system to be the same
    // as W.search_top.object (if W.search.dataObject.metadata.system hasn't been set) and
    // we set W.search_top.object to be the same as W.search.dataObject.metadata.system
    // (if W.search.dataObject.metadata.system has been set). Thus if the python module provides the
    // info, we use it. If not, we assume it's the same as W.search_top.object. In other words, the
    // python module only needs to notify changes. We need to record the info, so that as we escape back through
    // the search history, we keep reinstating the appropriate W.search_top.object.
    W.search.dataObject.metadata === undefined &&
      (W.search.dataObject.metadata = {});
    W.search.dataObject.metadata.system === undefined &&
      (W.search.dataObject.metadata.system = W.search_top.object);
    W.search.dataObject.metadata.system != W.search_top.object &&
      W.search_top.init(W.search.dataObject.metadata.system);
    params = {};
    params.static_image =
      W.search_top.object == "spotify" ||
      W.search.dataObject.metadata.item_type == "playlist";

    switch (W.search.dataObject.metadata.search_type) {
      case "artists":
      case "albums":
      case "songs":
      case "playlists":
        escaped &&
          (W.search_top.TxtInput.value = W.search.dataObject.id
            ? W.search.dataObject.id
            : "");
        W.search.switch_container(W.search.SubContainerOne);
        if (W.search.dataObject.metadata.search_type == "playlists") {
          W.search.SubContainerOne.classList.add(
            "search-subcontainer-one-playlists",
          );
        } else
          W.search.SubContainerOne.classList.remove(
            "search-subcontainer-one-playlists",
          );
        break;
      case "artist_from_track_uri":
        // This is a bit of a hack! There seem to be two
        // problems if we don't do this. First, for an artist with enough
        // albums to trigger a further search when scrolling down, the further search
        // would send the track_uri, rather than the artistid, which is a waste of time.
        // Secondly, if the search page is opened up through this route and we don't
        // make these changes to the dataObject, a further text search doesn't
        // get the right prefix (e.g. spotify.search_artists).
        W.search.dataObject.get_cmd = "album_from_artistid";
        W.search.dataObject.get_function = W.search_top.cmd;
        W.search.dataObject.id = W.search.dataObject.metadata.artistid;
        W.search.dataObject.metadata.search_type = "album_from_artistid";
        if (W.search_top.object != W.search.dataObject.metadata.system) {
          W.search_top.init(W.search.dataObject.metadata.system);
          W.search.set_search_module(W.search_top.object, true);
          params.static_image = W.search_top.object == "spotify";
        }
      case "album_from_artistid":
      case "related_artists":
      case "biography":
        artist_mode = true;
      case "playlists_from_userid":
        user_mode = artist_mode ? false : true;
        W.search.switch_container(W.search.SubContainerTwo, params);
        W.search.switch_container(W.search.ArtistSubContainerOne, {
          category: "artist",
        });
        document.querySelector("#search-artist-details-image img").src =
          W.search.dataObject.metadata.artistArtURI;
        document.querySelector("#search-artist-details-name").innerHTML =
          W.search.dataObject.metadata.artist;
        break;
      case "album_from_track_uri":
        //This is a bit of a hack! See above.
        W.search.dataObject.get_cmd = "songs_from_albumid";
        W.search.dataObject.get_function = W.search_top.cmd;
        W.search.dataObject.id = W.search.dataObject.metadata.albumid;
        W.search.dataObject.metadata.search_type = "tracks_from_albumid";
        if (W.search_top.object != W.search.dataObject.metadata.system) {
          W.search_top.init(W.search.dataObject.metadata.system);
          W.search.set_search_module(W.search_top.object, true);
        }
      case "recommendations_from_track_uri":
        //This is a bit of a hack! See above.
        if (W.search_top.object != W.search.dataObject.metadata.system) {
          W.search_top.init(W.search.dataObject.metadata.system);
          W.search.set_search_module(W.search_top.object, true);
        }
      case "tracks_from_albumid":
      case "tracks_from_trackid":
      case "tracks_from_albumid_from_artistid":
        artist_mode = true;
        album_mode = true;
      case "tracks_from_playlistid":
      case "tracks_from_playlistid_from_userid":
        user_mode = artist_mode ? false : true;
        playlist_mode = album_mode ? false : true;
        W.search.switch_container(W.search.SubContainerTwo, params);
        W.search.switch_container(W.search.ArtistSubContainerTwo, {
          category: "artist",
        });
        params.category = "artist-album";
        W.search.switch_container(W.search.ArtistAlbumSubContainerOne, params);
        document.querySelector("#search-artist-details-image img").src =
          W.search.dataObject.metadata.artistArtURI;
        document.querySelector("#search-artist-details-name").innerHTML =
          W.search.dataObject.metadata.artist;
        document.querySelector("#search-artist-album-details-image img").src =
          W.search.dataObject.metadata.albumArtURI;
        document.querySelector("#search-artist-album-details-name").innerHTML =
          W.search.dataObject.metadata.album
            ? W.search.dataObject.metadata.album
            : W.search.dataObject.metadata.item_type == "program"
              ? W.search.dataObject.metadata.artist + " Recommendations"
              : "";
        break;
      case "find":
        artist_mode = true;
        album_mode = true;
        W.search.switch_container(W.search.SubContainerTwo, params);
        W.search.switch_container(W.search.ArtistSubContainerTwo, {
          category: "artist",
        });
        W.search.switch_container(W.search.ArtistAlbumSubContainerTwo, {
          category: "artist-album",
        });
        document.querySelector("#search-artist-details-image img").src =
          W.search.dataObject.metadata.artistArtURI;
        document.querySelector("#search-artist-details-name").innerHTML =
          W.search.dataObject.metadata.artist;
        W.search.ArtistAlbumSubContainerTwo.innerHTML =
          "Searched tracks for: <b>" + W.search.dataObject.value + "</b>";
        break;
      default:
        break;
    }
    if (artist_mode) {
      categories = ["albums", "biography"];
      if (W.search_top.object == "spotify") categories.push("related");
      selected_button = 0;
      if (W.search.dataObject.metadata.search_type == "biography")
        selected_button = 1;
      if (W.search.dataObject.metadata.search_type == "related_artists")
        selected_button = 2;
    }
    if (user_mode) {
      if (!W.search.dataObject.metadata.artistid) categories = [];
      else categories = ["playlists"];
    }
    if (artist_mode || user_mode)
      W.search.set_buttons(
        document.querySelector("#search-artist-details-buttons"),
        W.search.ArtistButtons,
        categories,
        selected_button,
      );
    categories = [];
    if (W.search_top.object == "spotify") categories.push("spotify");
    if (album_mode) categories.push("play", "add", "replace", "edit", "more");
    if (playlist_mode)
      categories.push("play", "add", "replace", "edit", "more");
    if (album_mode || playlist_mode)
      W.search.set_buttons(
        document.querySelector("#search-artist-album-details-buttons"),
        W.search.AlbumButtons,
        categories,
      );
  }
  if (W.search.dataObject.metadata.search_type == "biography") {
    W.search.build_biography();
    return;
  }
  args.restart && W.util.stripChildren(W.search.resultsUL);
  const s = args.restart
    ? 0
    : (args.startIndex ?? W.search.dataObject.startIndex);
  const stop =
    args.buildSize != undefined
      ? s + args.buildSize
      : W.search.dataObject.data.length;
  for (var i = s; i < stop; i++) {
    if (W.search.dataObject.data[i].itemid) {
      LI = W.search.getLI(W.search.dataObject.data[i], i + 1);
      if (LI) W.search.resultsUL.appendChild(LI);
    }
  }
  !W.search.dataObject.metadata.scrollTopEdit &&
    (W.search.resultsUL.scrollTop =
      W.search.dataObject.metadata.scrollTop || 0);
  W.search.updateGridColumns();
  W.util.hyphenate();
  if (params != undefined) W.search.checkTextVisible(params.category);
};

W.search.checkTextVisible = function (category) {
  if (category !== "artist-album") return;
  const isTextTruncated = (el) => {
    const clampLines = 4;
    const computed = window.getComputedStyle(el);
    const lineHeight = parseFloat(computed.lineHeight);
    const maxHeight = lineHeight * clampLines;
    const actualHeight = el.scrollHeight;
    return actualHeight > Math.floor(maxHeight) + 20;
  };
  const textSpan = document.getElementById("search-artist-album-details-name");
  if (isTextTruncated(textSpan)) {
    let text = textSpan.innerHTML;
    let len = text.length - 3;
    let anchor = `<button data-text="${text}"
      onclick="W.popup.tooltip(event.target.dataset.text, event.target)"
      >...</button>`;
    textSpan.innerHTML = text.substring(0, len) + anchor;
    while (isTextTruncated(textSpan)) {
      len -= 1;
      textSpan.innerHTML = text.substring(0, len) + anchor;
    }
  }
};

W.search.updateGridColumns = function () {
  const irrelevant = [
    W.search.ArtistSubContainerTwo,
    W.search.ArtistSubContainerThree,
    W.search.ArtistSubContainerFour,
  ];
  const stop_now = [
    W.search.SubContainerOne,
    W.search.SubContainerTwo,
    W.search.ArtistSubContainerOne,
  ];

  let parent = W.search.resultsUL;

  while (parent && !stop_now.includes(parent)) {
    if (irrelevant.includes(parent)) return;
    parent = parent.parentNode;
  }

  const ul = W.search.resultsUL;
  if (!ul) return;

  const li = ul.querySelector("li"); // Get a sample LI
  if (!li) return; // Exit if no LIs exist

  // Get UL width
  const ulWidth = ul.clientWidth; // Use clientWidth to ignore scrollbars

  // Use offsetWidth instead of getBoundingClientRect
  const liWidth = Math.max(150, li.offsetWidth);
  const computedStyle = getComputedStyle(li);
  const liMarginLeft = parseFloat(computedStyle.marginLeft) || 0;
  const liMarginRight = parseFloat(computedStyle.marginRight) || 0;
  const liTotalWidth = liWidth + liMarginLeft + liMarginRight; // Full width with margins

  // Calculate columns
  const columns = Math.max(1, Math.floor(ulWidth / liTotalWidth));

  // Determine the new grid class
  const newGridClass = `grid-cols-${columns}`;

  // Find and replace the existing `grid-cols-x` class
  const existingGridClass = Array.from(ul.classList).find((cls) =>
    cls.startsWith("grid-cols-"),
  );
  if (existingGridClass) ul.classList.remove(existingGridClass);

  // Add the new grid class
  ul.classList.add(newGridClass);
};

W.search.scroll = function (e) {
  W.search.dataObject.metadata.scrollTop = e.target.scrollTop;
  if (
    e.target.scrollTop + e.target.clientHeight >
    0.9 * e.target.scrollHeight
  ) {
    W.search.dataObject.get_more();
  }
};

W.search.new_search = function (e, args = {}) {
  // args:
  // 		find:			string - search term for searching within an artist
  // 		bespoke_search:	string - type of search (see below)
  // 		item_ids:		array - array of item ids (used for recommendations from)
  // 		index:			int - the index of the related W.search.dataObject.data

  var index, get_cmd, search_term, value;
  var metadata = {};
  var metadata_was =
    W.search.dataObject == undefined ? {} : W.search.dataObject.metadata;
  var get_function = W.search_top.cmd;
  if (args.index != undefined) {
    index = args.index;
  } else {
    e && (index = W.util.getLiIndex(e.target));
  }
  if (args.find != undefined) {
    if (!args.find) return;
    get_cmd = "find_track";
    search_term = metadata_was.artistid;
    value = args.find;
    metadata.artist = metadata_was.artist;
    metadata.artistid = metadata_was.artistid;
    metadata.artistArtURI = metadata_was.artistArtURI;
    metadata.item_type = "program";
    metadata.search_type = "find";
  } else if (args.bespoke_search && args.bespoke_search == "related_artists") {
    get_cmd = "related_artists";
    search_term = {
      artist_name: metadata_was.artist,
      artist_uri: metadata_was.artistid,
    };
    metadata.artist = metadata_was.artist;
    metadata.artistid = metadata_was.artistid;
    metadata.artistArtURI = metadata_was.artistArtURI;
    metadata.search_type = "related_artists";
  } else if (args.bespoke_search && args.bespoke_search == "biography") {
    get_function = undefined;
    get_cmd = "covers.wikipedia_get_biography";
    search_term = metadata_was.artist;
    metadata.artist = metadata_was.artist;
    metadata.artistid = metadata_was.artistid;
    metadata.artistArtURI = metadata_was.artistArtURI;
    metadata.search_type = "biography";
  } else if (args.bespoke_search && args.bespoke_search == "view_artist") {
    get_cmd = "search.artist_from_track_uri";
    get_function = undefined;
    search_term = W.data.queue.data[index].id;
    metadata.search_type = "artist_from_track_uri";
  } else if (
    args.bespoke_search &&
    args.bespoke_search == "recommendations_track"
  ) {
    get_cmd = "search.recommendations_from_track_uri";
    get_function = undefined;
    if (args.item_ids != undefined) search_term = args.item_ids.join();
    else search_term = W.data.queue.data[index].id;
    metadata.search_type = "recommendations_from_track_uri";
  } else if (args.bespoke_search && args.bespoke_search == "display_albums") {
    get_cmd = "album_from_artistid";
    search_term = metadata_was.artistid;
    metadata.artist = metadata_was.artist;
    metadata.artistid = metadata_was.artistid;
    metadata.artistArtURI = metadata_was.artistArtURI;
    metadata.search_type = "album_from_artistid";
  } else
    switch (metadata_was.search_type) {
      case "artists":
      case "related_artists":
        get_cmd = "album_from_artistid";
        search_term = W.search.dataObject.data[index].itemid;
        metadata.artist = W.search.dataObject.data[index].title;
        metadata.artistid = W.search.dataObject.data[index].itemid;
        metadata.artistArtURI = W.search.dataObject.data[index].artURI;
        metadata.search_type = "album_from_artistid";
        break;
      case "albums":
        get_cmd = "songs_from_albumid";
        search_term = W.search.dataObject.data[index].itemid;
        metadata.album = W.search.dataObject.data[index].title;
        metadata.albumid = W.search.dataObject.data[index].itemid;
        metadata.albumArtURI = W.search.dataObject.data[index].artURI;
        metadata.search_type = "tracks_from_albumid";
        break;
      case "playlists":
        metadata.search_type = "tracks_from_playlistid";
      case "playlists_from_userid":
        get_cmd = "songs_from_playlistid";
        search_term = W.search.dataObject.data[index].itemid;
        metadata.album = W.search.dataObject.data[index].title;
        metadata.albumid = W.search.dataObject.data[index].itemid;
        metadata.albumArtURI = W.search.dataObject.data[index].artURI;
        W.search_top.object == "spotify" &&
          (metadata.pubic = W.search.dataObject.data[index].pubic);
        metadata.search_type = metadata.search_type
          ? metadata.search_type
          : "tracks_from_playlistid_from_userid";
        break;
      case "tracks_from_playlistid_get_playlists":
        get_cmd = "playlists_from_userid";
        search_term = metadata_was.artistid;
        metadata.artist = metadata_was.artist;
        metadata.artistid = metadata_was.artistid;
        metadata.artistArtURI = metadata_was.artistArtURI;
        metadata.search_type = "playlists_from_userid";
        break;
      case "songs":
      case "tracks_from_albumid_from_artistid":
      case "tracks_from_playlistid":
      case "tracks_from_playlistid_from_userid":
      case "find":
      case "recommendations_from_track_uri":
        get_cmd = "songs_from_albumid";
        search_term = W.search.dataObject.data[index].albumid;
        metadata.trackid = W.search.dataObject.data[index].itemid;
        metadata.album = W.search.dataObject.data[index].album;
        metadata.albumid = W.search.dataObject.data[index].albumid;
        metadata.albumArtURI = W.search.dataObject.data[index].artURI;
        metadata.search_type = "tracks_from_trackid";
        break;
      case "album_from_artistid":
      case "artist_from_track_uri":
        get_cmd = "songs_from_albumid";
        search_term = W.search.dataObject.data[index].itemid;
        metadata.artist = metadata_was.artist;
        metadata.artistid = metadata_was.artistid;
        metadata.album = W.search.dataObject.data[index].title;
        metadata.albumid = W.search.dataObject.data[index].itemid;
        metadata.albumArtURI =
          W.search.dataObject.data[index].artURI || metadata_was.artistArtURI;
        metadata.artistArtURI = metadata_was.artistArtURI;
        metadata.search_type = "tracks_from_albumid_from_artistid";
        W.search_top.object == "spotify" &&
          (metadata.item_type = W.search.dataObject.data[index].itemtype);
        break;
      default: // this is triggered by W.search.new_search(e)
        get_cmd = "search.songs_from_track_uri";
        get_function = undefined;
        search_term = W.data.queue.data[index].id;
        metadata.search_type = "album_from_track_uri";
        break;
    }
  get_cmd &&
    W.search.new_search_execute({
      get_cmd: get_cmd,
      get_function: get_function,
      metadata: metadata,
      search_term: search_term,
      value: value,
    });
};

W.search.new_search_execute = function (args) {
  const { get_cmd, get_function, metadata, search_term, value, keep_display } =
    args;
  !keep_display && W.search.clear_display();
  if (W.search.dataObject != undefined) {
    const cmd = W.search.dataObject.get_cmd.split(".").pop();
    const cancellable = [
      "search_artists",
      "search_albums",
      "search_albums_recent",
      "search_songs",
      "search_playlists",
    ];
    if (W.search.dataObject.searching == true && cancellable.includes(cmd))
      return;
    W.search.dataObject.make_dormant();
    W.search.search_history.push(W.search.dataObject);
  }
  W.search.dataObject = new W.lazyDataObject({
    pageLength: 100,
    build_cmd: W.search.build,
    get_cmd: get_cmd,
    get_function: get_function,
    progress_fn: [
      function () {
        W.search.progress("visible");
      },
      function () {
        W.search.progress("hidden");
      },
    ],
  });
  W.search.dataObject.metadata = metadata;
  W.search.dataObject.get(search_term, value);
};

W.search.refresh_data = function (o) {
  if (!W.search.search_history || !W.search.search_history.length) return;
  var keyword = W.search.is_it_a_playlist() ? "playlist" : "album";
  var del;
  for (var i = W.search.search_history.length - 1; i >= 0; i--) {
    if (o) {
      if (
        o.results.data_type == "album" &&
        o.results.data_source == W.search_top.object
      ) {
        if (
          o.results.action == "album_delete" ||
          o.results.action == "album_change"
        ) {
          del = false;
          switch (W.search.search_history[i].get_cmd) {
            case "album_from_artistid":
            case "find_track":
            case "related_artists":
              del =
                W.search.search_history[i].id == o.results.artistid_deleted
                  ? true
                  : false;
              break;
            case "songs_from_albumid":
              del =
                o.results.action == "album_delete" &&
                W.search.search_history[i].id == o.results.container_id
                  ? true
                  : false;
              break;
            case "covers.wikipedia_get_biography":
              del =
                W.search.search_history[i].metadata.artistid ==
                o.results.artistid_deleted
                  ? true
                  : false;
              break;
            case "songs_from_playlistid":
            case "artists":
            case "albums":
            case "songs":
            case "search_playlists":
            case "albums_recent":
              W.search.search_history[i].metadata.refresh_data = true;
              break;
            default:
              break;
          }
          if (del) W.search.search_history.pop();
          else if (W.search.search_history[i].get_cmd.indexOf(keyword) > -1) {
            W.search.search_history[i].metadata.refresh_data = true;
          }
        }
      }
    } else if (W.search.search_history[i].get_cmd.indexOf(keyword) > -1) {
      W.search.search_history[i].metadata.refresh_data = true;
    }
  }
};

W.search.find = function () {
  if (
    !W.search.dataObject.metadata.search_type ||
    W.search.dataObject.metadata.search_type == "artists" ||
    W.search.dataObject.metadata.search_type == "albums" ||
    W.search.dataObject.metadata.search_type == "playlists" ||
    W.search.dataObject.metadata.search_type == "songs"
  )
    return;
  W.util.getInput({
    title: "Enter track to find",
    fn: function (value) {
      W.search.new_search(undefined, {
        find: value,
      });
    },
  });
};

W.search.display_albums = function () {
  W.search.dataObject.metadata.search_type == "biography" && W.search.escape();
  W.search.dataObject.metadata.search_type == "related_artists" &&
    W.search.escape();
  switch (W.search.dataObject.metadata.search_type) {
    // If we are click the album button
    // on the artist page, we already have the data, so
    // no need to get it again
    case "album_from_artistid":
      W.search.build({
        refresh: true,
        restart: true,
      });
      break;
    case "tracks_from_albumid_from_artistid":
      W.search.escape();
      break;
    case "find":
      W.search.escape(false);
      W.search.display_albums();
      break;
    case "tracks_from_albumid":
    case "tracks_from_trackid":
    case "recommendations_from_track_uri":
      W.search.new_search(undefined, {
        bespoke_search: "display_albums",
      });
      break;
    default:
      break;
  }
};

W.search.display_related = function () {
  W.search.dataObject.metadata.search_type == "biography" && W.search.escape();
  W.search.dataObject.metadata.search_type != "related_artists" &&
    W.search.new_search(undefined, {
      bespoke_search: "related_artists",
    });
};

W.search.display_biography = function () {
  W.search.dataObject.metadata.search_type == "related_artists" &&
    W.search.escape();
  W.search.dataObject.metadata.search_type != "biography" &&
    W.search.new_search(undefined, {
      bespoke_search: "biography",
    });
};

W.search.build_biography = function () {
  var results = W.search.dataObject.data[0];
  var get_page = function (e) {
    var jsonStr = W.system.get_jsonStr("covers.wikipedia_get_biography_page");
    jsonStr.args.page = e.target.innerHTML;
    var cb = function (r) {
      results.extract = r.results;
      build_bio();
    };
    W.util.JSONpost("/json", jsonStr, cb);
  };
  var build_bio = function () {
    W.search.switch_container(W.search.ArtistSubContainerThree, {
      category: "artist",
    });
    W.search.resultsUL.innerHTML = results.extract;
    document.querySelector("#search-artist-right-disambiguation").onclick =
      function () {
        build_disambiguation();
      };
  };
  var build_disambiguation = function () {
    W.search.switch_container(W.search.ArtistSubContainerFour, {
      category: "artist",
    });
    var LI;
    for (var i = 0; i < results.metadata[1].length; i++) {
      LI = W.search.RowDisambiguation.cloneNode(true);
      LI.children[0].innerHTML = results.metadata[1][i];
      LI.children[0].onclick = get_page;
      LI.children[1].innerHTML = results.metadata[2][i];
      W.search.resultsUL.appendChild(LI);
    }
    document.querySelector("#search-artist-right-disambiguation-back").onclick =
      function () {
        build_bio();
      };
  };
  build_bio();
};

W.search.display_playlists = function () {
  switch (W.search.dataObject.metadata.search_type) {
    case "tracks_from_playlistid":
      W.search.dataObject.metadata.search_type =
        "tracks_from_playlistid_get_playlists";
      W.search.new_search();
      break;
    case "tracks_from_playlistid_from_userid":
      W.search.escape();
    case "tracks_from_playlistid_get_playlists":
      break;
  }
};

W.search.click_function = function (e) {
  if (W.search.edit_mode) {
    W.util.selectThis(e);
  } else {
    switch (W.search.dataObject.metadata.item_type) {
      case "trackList":
      case "program":
      case "playlist":
      case "find":
        W.search.new_search(e);
        break;
      default:
        W.search.play_song(e);
        break;
    }
  }
};

/*
These next several functions allow for an album or track to
be played by clicking it from a UL listing, as well as from
an album or playlist listing. At present, the option to play
from a UL listing has been removed, because I wasn't using it.
It might be reinstated for the mobile interface, so I've
not yet deleted the functionaility here.
*/

W.search.album_spotify = function () {
  let id = W.search.dataObject.id;
  if (!id || !id.startsWith("spotify:")) return;

  // Handle synthetic IDs like artistRecommendations or artistTopTracks
  if (id.includes("ecommendation") || id.includes("artistTopTracks")) {
    const parts = id.split(":");
    if (parts.length >= 3) {
      id = `spotify:artist:${parts[2]}`;
    }
  }

  const parts = id.split(":");
  if (parts.length !== 3) return;

  const [_, type, itemId] = parts;
  const url = `https://open.spotify.com/${type}/${itemId}`;
  window.open(url, "_blank");
};

W.search.album_play = function () {
  W.search.play_album();
};

W.search.album_add = function () {
  W.search.add_album();
};

W.search.album_replace = function () {
  W.search.play_album(undefined, true);
};

W.search.album_edit = function () {
  W.search_edit.init();
};

W.search.album_more = function (e) {
  W.search_menus.album_menu.show(e);
};

W.search.play_album = function (e, clear) {
  W.search.add_album({ e: e, clear: clear, add_and_play: true });
};

W.search.add_album = function (params = {}) {
  // params:
  //  e
  //  clear (default: false)
  //  add_and_play (default: false)
  //  play_now (default: false)
  //  play_next (default: false)
  //  indices (default: undefined)
  //  tracks (default: undefined)

  params.e && params.e.stopPropagation();
  var jsonStr;
  var args = {};
  args.container_id = params.e
    ? W.search.dataObject.data[W.util.getLiIndex(params.e.target)].itemid
    : W.search.dataObject.metadata.albumid;
  args.data_type = W.search.is_it_a_playlist() ? "playlist" : "album";
  args.data_source = W.search_top.object;
  args.clear = params.clear ? params.clear : false;
  args.add_and_play = params.add_and_play ? params.add_and_play : false;
  args.play_now = params.play_now ? params.play_now : false;
  args.play_next = params.play_next ? params.play_next : false;
  if (params.indices) args.indices = params.indices;
  if (params.tracks) args.tracks = params.tracks;

  switch (W.search_top.object) {
    case "database":
      switch (W.system.object) {
        case "dbmp":
          args.dest_id = W.data.queue.id;
          jsonStr = W.search_top.jsonStr("db_player", "add_container", args);
          break;
        case "sonos":
          params.clear &&
            W.util.JSONpost(
              "/json",
              W.search_top.jsonStr("sonos", "queue_clear"),
            );
          jsonStr = W.search_top.jsonStr("sonos", "add_container", args);
          break;
      }
      break;
    case "spotify":
      params.clear &&
        W.util.JSONpost("/json", W.search_top.jsonStr("sonos", "queue_clear"));
      args.data_source = W.search_top.object;
      jsonStr = W.search_top.jsonStr("sonos", "add_container", args);
      break;
  }
  W.util.JSONpost("/json", jsonStr);
};

W.search.play_song = function (e) {
  W.search.add_song(e, true);
};

W.search.add_song = function (e, add_and_play = false) {
  if (W.search.edit_mode) return;
  e.stopPropagation();
  var jsonStr;
  var args = {};
  args.song_id = W.search.dataObject.data[W.util.getLiIndex(e.target)].itemid;
  args.add_and_play = add_and_play;

  switch (W.search_top.object) {
    case "database":
      switch (W.system.object) {
        case "dbmp":
          args.id = ""; //We should delete parameter from server
          jsonStr = W.search_top.jsonStr("db_player", "add_track", args);
          break;
        case "sonos":
          jsonStr = W.search_top.jsonStr("sonos", "add_track", args);
          break;
      }
      break;
    case "spotify":
      jsonStr = W.search_top.jsonStr("sonos", "add_track", args);
      break;
  }
  W.util.JSONpost("/json", jsonStr);
};

W.search.update_artwork = function (items) {
  if (!W.searchVisible) return;
  var images = document.querySelectorAll("img");
  for (var i = 0; i < images.length; i++) {
    images[i].src == window.location.href + items.uri_was.substring(1) &&
      (images[i].src = items.uri);
  }
  var update = function (dataObject) {
    var row;
    for (var i = 0; i < dataObject.data.length; i++) {
      row = dataObject.data[i];
      row.artURI == items.uri_was && (row.artURI = items.uri);
    }
    dataObject.metadata &&
      dataObject.metadata.artistArtURI &&
      dataObject.metadata.artistArtURI == items.uri_was &&
      (dataObject.metadata.artistArtURI = items.uri);
    dataObject.metadata &&
      dataObject.metadata.albumArtURI &&
      dataObject.metadata.albumArtURI == items.uri_was &&
      (dataObject.metadata.albumArtURI = items.uri);
  };
  update(W.search.dataObject);
  for (i = 0; i < W.search.search_history.length; i++) {
    update(W.search.search_history[i]);
  }
};

W.search.is_it_a_playlist = function () {
  if (!W.search.dataObject || !W.search.dataObject.metadata) return false;
  return W.search.dataObject.metadata.item_type
    ? W.search.dataObject.metadata.item_type == "playlist"
    : W.search.dataObject.metadata.search_type == "playlists" ||
        W.search.dataObject.metadata.search_type == "tracks_from_playlistid";
};

W.search.escape = function (rebuild = true) {
  W.search_top.TxtInput.value = "";
  if (W.search.search_history.length) {
    W.search.clear_display();
    W.search.dataObject = W.search.search_history.pop();
    W.search.dataObject.make_active();
    if (rebuild) {
      W.search.escaped = true; // we'll restore the search text
      if (W.search.dataObject.metadata.refresh_data) {
        W.search.dataObject.metadata.refresh_data = false;
        W.search.dataObject.get();
      } else if (!W.search.dataObject.searching) {
        W.search.build({
          refresh: true,
          restart: true,
        });
      }
    }
    if (W.search.dataObject.metadata.search_category != undefined)
      W.search.init(W.search.dataObject.metadata.search_category);
  } else W.search_top.close();
};

W.search.onTxtInputChanged = function () {
  var get_cmd;
  var metadata = {};
  metadata.search_category = W.search.category;
  W.search.switch_container(W.search.SubContainerOne);
  W.search.clear_display();
  switch (W.search.category) {
    case "artists":
      get_cmd = "artists";
      metadata.search_type = "artists";
      break;
    case "albums":
      get_cmd = "albums";
      metadata.search_type = "albums";
      break;
    case "tracks":
      get_cmd = "songs";
      metadata.search_type = "songs";
      break;
    case "database_playlists":
      get_cmd = "search_playlists";
      metadata.search_type = "playlists";
      break;
    case "playlists":
      get_cmd = "playlists";
      metadata.search_type = "playlists";
      break;
    case "my_albums":
      get_cmd = "my_albums";
      metadata.search_type = "albums";
      break;
    case "my_tracks":
      get_cmd = "my_tracks";
      metadata.search_type = "songs";
      break;
    case "my_playlists":
      get_cmd = "my_playlists";
      metadata.search_type = "playlists";
      break;
    case "recently_added":
      get_cmd = "albums_recent";
      metadata.search_type = "albums";
      break;
    default:
      break;
  }
  if (get_cmd) {
    W.search.new_search_execute({
      get_cmd: get_cmd,
      get_function: W.search_top.cmd,
      metadata: metadata,
      search_term: W.search_top.TxtInput.value,
      keep_display: true,
    });
  }
};

W.search.init = function (c, get) {
  W.search.category = c;
  W.search.set_category_buttons(c);
  get && W.search.onTxtInputChanged();
};

W.search.set_category_buttons = function (c) {
  const buttons = document.querySelectorAll(".search-category");
  if (!buttons.length) return;
  buttons.forEach((bn) => {
    W.css.removeClasses(bn, "search_category_selected");
  });
  const selected = document.querySelector(
    "#search-category-" + c.replace("_", "-"),
  );
  W.css.addClasses(selected, "search_category_selected");
  switch (c) {
    case "my_albums":
    case "my_tracks":
    case "my_playlists":
    case "database_playlists":
      W.search_top.TxtInputToggle("off");
      break;
    default:
      W.search_top.TxtInputToggle("on");
      break;
  }
};

W.search.change_category = function (target) {
  var category = target.id
    .substring("search-category-".length)
    .replace("-", "_");
  if (W.search.category != category) {
    W.search.init(category, true);
    W.util.setCookie("search_new_category", category);
  }
};

W.search.progress = function (s) {
  document.querySelector("#search-progress").style.visibility = s;
};

W.search.close = function () {
  W.search.edit_mode && W.search_edit.exit();
  W.search.clear_display();
  W.search.switch_container(W.search.SubContainerOne);
  W.search.search_history = [];
  W.search.dataObject = undefined;
};

W.search.switch_container = function (container, args) {
  /* 
    args:
      - category:       undefined / "artist" / "artist-album"
      - static_image:   true / false (default: false)
   
  */

  const category = args != undefined ? args.category : undefined;
  var parent;

  switch (category) {
    default:
      parent = document.querySelector("#search-container");
      break;
    case "artist":
      parent = document.querySelector("#search-artist-right");
      break;
    case "artist-album":
      parent = document.querySelector("#search-artist-album-details");
      break;
  }
  W.util.stripChildren(parent, false);
  parent.appendChild(container);
  // All this bother is to apply the default cursor to artist and
  // album images when we are displaying Spotify or Playlist search
  // results, as we can't change those images using the cover change
  // menu
  if (
    container == W.search.SubContainerTwo ||
    container == W.search.ArtistAlbumSubContainerOne
  ) {
    var img =
      container.querySelector("#search-artist-details-image img") ||
      container.querySelector("#search-artist-album-details-image img");
    W.css.removeClasses(img, "search_image_fixed", "search_image_not_fixed");
    if (args.static_image) W.css.addClasses(img, "search_image_fixed");
    else W.css.addClasses(img, "search_image_not_fixed");
  }
  if (category == "artist-album") return;
  W.search.resultsUL = document.querySelector(".search-resultsUL");
  W.util.stripChildren(W.search.resultsUL);
  W.search.resultsUL.tabIndex = 1;
  W.search.resultsUL.style.outline = "none";
};

W.search.set_search_module = function (s, no_init) {
  var categories;
  switch (s) {
    case "database":
      categories = [
        "artists",
        "albums",
        "tracks",
        "database_playlists",
        "recently_added",
      ];
      break;
    case "spotify":
      categories = [
        "artists",
        "albums",
        "tracks",
        "playlists",
        "my_albums",
        "my_tracks",
        "my_playlists",
        "recently_added",
      ];
      break;
  }
  W.search.set_buttons(
    document.querySelector("#search-categories"),
    W.search.CategoryButtons,
    categories,
  );
  if (no_init) return;
  if (categories.indexOf(W.search.category) == -1) {
    W.util.setCookie("search_new_category", "artists");
    W.search.init("artists");
    return;
  }
  if (s == "database") {
    W.search.init(W.search.category, true);
    return;
  }
  switch (W.search.category) {
    case "my_albums":
    case "my_tracks":
    case "my_playlists":
      W.search.init(W.search.category, true);
      break;
    default:
      W.search.init(W.search.category);
      break;
  }
};

W.search.set_buttons = function (parent, buttons, categories, selected_button) {
  if (!parent) return;
  W.util.stripChildren(parent, false);
  for (var i = 0; i < categories.length; i++) {
    parent.appendChild(buttons[categories[i]]);
    W.css.removeClasses(parent.lastChild, "search_category_selected");
    if (i == selected_button)
      W.css.addClasses(parent.lastChild, "search_category_selected");
  }
};

W.util.ready(function () {
  // resizing
  W.util.mediaQuery.addEventListener("change", W.util.hyphenate);
  //cookies
  var c = W.util.getCookie("search_new_category");
  if (c == "") c = "artists";
  W.search.init(c);
  //buttons
  W.search.CategoryButtons = {};
  var buttons = document.querySelectorAll(".search-category");
  var category, i;
  for (i = 0; i < buttons.length; i++) {
    category = buttons[i].id
      .substring("search-category-".length)
      .replace("-", "_");
    W.search.CategoryButtons[category] = buttons[i];
    buttons[i].onclick = function (e) {
      var target = e.target;
      while (!W.util.has_class(target, "search-category")) {
        target = target.parentNode;
      }
      W.search.change_category(target);
    };
  }
  document.querySelector("#search-artist-details-image img").onclick =
    function () {
      if (
        W.search_top.object == "spotify" ||
        W.search.dataObject.metadata.item_type == "playlist"
      )
        return;
      var artist = W.search.dataObject.metadata.artist;
      var id = W.search.dataObject.metadata.artistid;
      W.cover.artist_search(artist, id);
    };
  document.querySelector("#search-artist-album-details-image img").onclick =
    function () {
      if (
        W.search_top.object == "spotify" ||
        W.search.dataObject.metadata.item_type == "playlist"
      )
        return;
      var artist = W.search.dataObject.metadata.artist;
      var title = W.search.dataObject.metadata.album;
      var id = W.search.dataObject.metadata.albumid;
      W.cover.album_search(artist, title, id);
    };
  W.search.ArtistButtons = {};
  buttons = document.querySelectorAll("#search-artist-details-buttons span");
  for (i = 0; i < buttons.length; i++) {
    category = buttons[i].id.split("-")[4];
    W.search.ArtistButtons[category] = buttons[i];
    buttons[i].onclick = W.search["display_" + category];
  }
  W.search.AlbumButtons = {};
  buttons = document.querySelectorAll(
    "#search-artist-album-details-buttons span",
  );
  for (i = 0; i < buttons.length; i++) {
    category = buttons[i].id.split("-")[5];
    W.search.AlbumButtons[category] = buttons[i];
    buttons[i].onclick = W.search["album_" + category];
  }
  //scrolling
  var results = document.querySelectorAll(".search-resultsUL");
  for (i = 0; i < results.length; i++)
    results[i].addEventListener("scroll", throttle(W.search.scroll, 66));
  //elements
  W.search.SubContainerOne = document.querySelector("#search-subcontainer-one");
  W.search.SubContainerTwo = document.querySelector("#search-subcontainer-two");
  W.search.ArtistSubContainerOne = document.querySelector(
    "#search-artist-right-subcontainer-one",
  );
  W.search.ArtistSubContainerTwo = document.querySelector(
    "#search-artist-right-subcontainer-two",
  );
  W.search.ArtistSubContainerThree = document.querySelector(
    "#search-artist-right-subcontainer-three",
  );
  W.search.ArtistSubContainerFour = document.querySelector(
    "#search-artist-right-subcontainer-four",
  );
  W.search.ArtistAlbumSubContainerOne = document.querySelector(
    "#search-artist-album-details-subcontainer-one",
  );
  W.search.ArtistAlbumSubContainerTwo = document.querySelector(
    "#search-artist-album-details-subcontainer-two",
  );
  W.search.RowSearchResults = document
    .querySelector(".search-results-li")
    .cloneNode(true);
  W.search.RowSearchResultsTrack = document
    .querySelector(".search-results-track-li")
    .cloneNode(true);
  W.search.RowArtistAlbumTrack = document
    .querySelector(".search-artist-album-track")
    .cloneNode(true);
  W.search.RowVariousAlbumTrack = document
    .querySelector(".search-various-album-track")
    .cloneNode(true);
  W.search.RowArtistTopTrack = document
    .querySelector(".search-artist-top-track")
    .cloneNode(true);
  W.search.RowArtistRecommendationsTrack = document
    .querySelector(".search-artist-recommendations-track")
    .cloneNode(true);
  W.search.RowBlankTrack = document
    .querySelector(".search-blank-track")
    .cloneNode(true);
  W.search.RowDisambiguation = document
    .querySelector("#search-artist-right-subcontainer-four li")
    .cloneNode(true);
  //switch containers
  W.search.switch_container(W.search.ArtistAlbumSubContainerOne, {
    category: "artist-album",
  });
  W.search.switch_container(W.search.ArtistSubContainerOne, {
    category: "artist",
  });
  W.search.switch_container(W.search.SubContainerOne);
  let search = document.getElementById("search");
  search.appendChild(document.querySelector(".mobile-nav-bar").cloneNode(true));
});

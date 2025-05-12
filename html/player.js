"use strict";
W.player = {};
W.player.volume_updating = false;

W.player.millisecs_to_str = function (m) {
  if (m == undefined) {
    return -1;
  }
  var minutes = Math.floor(m / 60000);
  var seconds = Math.round((m % 60000) / 1000);
  var output = "" + minutes + ":";
  if (seconds < 10) {
    output += "0";
  }
  output += seconds;
  return output;
};

W.player.updateCover = function (uri) {
  var img = document.querySelector("#player-image");

  if (uri === "disconnected") {
    img.src = "icons/blank.png";
    img.alt = "The player is disconnected";
    W.css.removeClasses(img, "player_pointer");
    return;
  }

  uri = W.util.fixAlbumArtURL(uri);
  let src = uri || "icons/NoImage.png";

  // Only update image after it's loaded (optional)
  const song = W.data.status.song;
  const tempImg = new Image();
  tempImg.onload = function () {
    if (song === W.data.status.song) {
      img.src = tempImg.src;
      img.alt = "Cover art";
      if (W.data.status.song.albumid) {
        W.css.addClasses(img, "player_pointer");
      } else {
        W.css.removeClasses(img, "player_pointer");
      }
    }
  };
  tempImg.onerror = function () {
    img.src = "icons/NoImage.png";
    img.alt = "Cover art not available";
    W.css.removeClasses(img, "player_pointer");
  };
  tempImg.src = src;
};

W.player.init = function () {
  W.player.song_change();
  W.player.song_position();
  W.player.status();
};

W.player.song_change = function () {
  document.getElementById("player-song").textContent = W.data.status.song.title
    ? W.data.status.song.title
    : "[Unknown]";
  document.getElementById("player-artist").textContent = W.data.status.song
    .artist
    ? W.data.status.song.artist
    : "[Unknown]";

  const spotifyLink = document.getElementById("player-spotify-link");
  const track = W.data.status.song;
  W.css.removeClasses(spotifyLink, "hidden");

  if (track.id && track.id.startsWith("spotify:track:")) {
    const spotifyId = track.id.split(":")[2];
    spotifyLink.href = "https://open.spotify.com/track/" + spotifyId;
    W.css.removeClasses(spotifyLink, "hidden");
  } else {
    spotifyLink.href = "#";
    W.css.addClasses(spotifyLink, "hidden");
  }
};

W.player.song_position = function (pos) {
  if (pos == undefined && W.player.progress_move) {
    return;
  }
  if (pos == undefined) {
    pos = W.data.status.song_progress;
  }
  var progressbar = document.querySelector("#player-progress-bar");
  var progresshandle = document.querySelector("#player-progress-handle");
  var progresscounter = document.querySelector("#player-progress-counter");
  var progress = "" + (pos / W.data.status.song_length) * 100 + "%";
  var decrement = Math.round((pos / W.data.status.song_length) * 24);
  progressbar.style.width = progress;
  progresshandle.style.left = "calc(" + progress + " - " + decrement + "px)";
  progresscounter.children[0].textContent = W.player.millisecs_to_str(pos);
  progresscounter.children[1].textContent = W.player.millisecs_to_str(
    W.data.status.song_length,
  );
};

W.player.progress_dragInit = function () {
  const progressContainer = document.querySelector(
    "#player-progress-container",
  );
  const progressBar = document.querySelector("#player-progress");

  function getEventX(e) {
    if (e.touches && e.touches.length > 0) return e.touches[0].clientX;
    if (e.changedTouches && e.changedTouches.length > 0)
      return e.changedTouches[0].clientX;
    return e.clientX || e.x;
  }

  function progressMouseToPos(e) {
    const rect = progressBar.getBoundingClientRect();
    const x = getEventX(e);
    const width = rect.width;
    let pos = x - rect.left - 2;
    if (pos < 0) pos = 0;
    if (pos > width) pos = width;
    return pos / width;
  }

  function handleProgressMove(e) {
    if (!W.data.status.song_length) return;
    const position = progressMouseToPos(e) * W.data.status.song_length;
    W.player.song_position(position);
  }

  function onMouseDown(e) {
    e.preventDefault();
    if (!W.data.status.song_length) return;

    W.player.progress_move = true;
    handleProgressMove(e);

    if (!W.player.progress_move_listeners_added) {
      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
      document.addEventListener("touchmove", onMouseMove, { passive: false });
      document.addEventListener("touchend", onMouseUp);
      W.player.progress_move_listeners_added = true;
    }
  }

  function onMouseMove(e) {
    e.preventDefault();
    handleProgressMove(e);
  }

  function onMouseUp(e) {
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
    document.removeEventListener("touchmove", onMouseMove);
    document.removeEventListener("touchend", onMouseUp);
    W.player.progress_move_listeners_added = false;

    if (!W.data.status.song_length) return;
    if (W.player.progress_move) {
      setTimeout(() => (W.player.progress_move = false), 100);
      const pos = Math.round(progressMouseToPos(e) * W.data.status.song_length);
      const jsonStr = W.system.create_cmd_and_get_jsonStr("jump");
      jsonStr.args.position = pos;
      W.util.JSONpost("/json", jsonStr);
    }
  }

  // Bind both mouse and touch events
  progressContainer.addEventListener("mousedown", onMouseDown);
  progressContainer.addEventListener("touchstart", onMouseDown, {
    passive: false,
  });
};

W.player.status = function () {
  const play = document.querySelector("#player-controls-play i");
  W.css.removeClasses(
    play,
    "player_controls_playing",
    "player_controls_paused",
  );
  if (W.data.status.playing) W.css.addClasses(play, "player_controls_playing");
  else W.css.addClasses(play, "player_controls_paused");
};

W.player.control_click = function (e) {
  var jsonStr;
  let button = e.target;
  if (!button.id) button = button.parentNode;
  switch (button.id) {
    case "player-controls-prev":
      jsonStr = W.system.create_cmd_and_get_jsonStr("prev_track");
      break;
    case "player-controls-stop":
      jsonStr = W.system.create_cmd_and_get_jsonStr("stop");
      break;
    case "player-controls-play":
      jsonStr = W.system.create_cmd_and_get_jsonStr("play_pause");
      break;
    case "player-controls-next":
      jsonStr = W.system.create_cmd_and_get_jsonStr("next_track");
      break;
  }
  W.util.JSONpost("/json", jsonStr);
};

W.player.channel_to_id = function (channel) {
  return "player-volume-div-" + channel.replace(/ /g, "-");
};

W.player.volume_init = function () {
  W.util.stripChildren(W.player.volDiv);
  var channels = Object.keys(W.data.status.volume);
  var add = function (channel) {
    var el = W.player.volTemplate.cloneNode(true);
    el.id = W.player.channel_to_id(channel);
    el.querySelector(".player-volume-name").textContent = channel;
    el.querySelector(".player-volume-speakers button").onclick =
      W.player.onmute;
    W.player.volDiv.appendChild(el);
  };
  if (channels.length == 1) {
    add(channels[0]);
  } else {
    var zones = W.data.status.queue.zones;
    var channel, index, i;
    if (channels.indexOf("Group Volume") != -1) {
      add("Group Volume");
    }
    for (i = 0; i < zones.length; i++) {
      channel = zones[i];
      index = channels.indexOf(channel);
      if (index != -1) {
        channels.splice(index, 1);
        add(channel);
      }
    }
  }
  W.player.volume();
  W.player.mute();
};

W.player.volume = function (o) {
  if (o == undefined && W.player.volume_move) return;
  var channels = Object.keys(W.data.status.volume);
  var channel;
  var vol;
  var i;
  var update_display = function (channel, vol) {
    vol = Math.max(vol, 0);
    var volDiv = document.querySelector("#" + W.player.channel_to_id(channel));
    var volumebar = volDiv.querySelector(".player-volume-bar");
    var volumehandle = volDiv.querySelector(".player-volume-handle");
    var volumecounter = volDiv.querySelector(".player-volume-container span");
    var volume = "" + vol + "%";
    var decrement = Math.round((vol / 100) * 24);
    volumebar.style.width = volume;
    volumehandle.style.left = "calc(" + volume + " - " + decrement + "px)";
    volumecounter.textContent = vol;
    volumecounter.style.left = "calc(" + volume + " - " + decrement + "px)";
  };
  var tell_server = function (channel, vol) {
    W.player.volume_updating = true;
    W.data.status.volume[channel] = vol;
    var jsonStr = W.system.create_cmd_and_get_jsonStr("set_main_volume");
    jsonStr.args.volume = vol;
    jsonStr.args.channel = channel;
    W.util.JSONpost("/json", jsonStr);
    setTimeout(function () {
      W.player.volume_updating = false;
    }, 1000);
  };
  if (o == undefined) {
    for (i = 0; i < channels.length; i++) {
      channel = channels[i];
      vol = W.data.status.volume[channel];
      update_display(channel, vol);
    }
  } else {
    channel = o.channel;
    vol = o.vol;
    const old_v = W.data.status.volume[channel];
    if (
      vol != old_v &&
      (!W.player.volume_updating || vol - old_v > 10 || old_v - vol > 10)
    ) {
      tell_server(channel, vol);
    }
    update_display(channel, vol);
    if (channels.length > 1) {
      var c;
      // The algorithm Sonos uses for updating zone volumes
      // when the group volume is changed is obscure, so we
      // don't try to anticipate the result. It seems that
      // the greater the change in group volume, the more
      // the zone volumes converge. For example, if zone 1
      // is set to 25 and zone 2 is set to 50 and the group
      // volume is changed to 95, both zones will become 95
      // and the zone volumes will remain in sync.
      if (channel == "Group Volume") return;
      else {
        var new_g = 0;
        for (i = 0; i < channels.length; i++) {
          c = channels[i];
          if (c == channel) {
            new_g = new_g + vol;
          } else if (c != "Group Volume") {
            new_g = new_g + W.data.status.volume[c];
          }
        }
        new_g = Math.round(new_g / (i - 1));
        update_display("Group Volume", new_g);
      }
    }
  }
};

W.player.volume_mouse_down_div = undefined;

// Set up volume drag
(function () {
  function getEventX(e) {
    if (e.touches && e.touches.length > 0) return e.touches[0].clientX;
    if (e.changedTouches && e.changedTouches.length > 0)
      return e.changedTouches[0].clientX;
    return e.clientX || e.x;
  }

  function volumeMouseToVol(e) {
    const volumeEl =
      W.player.volume_mouse_down_div.querySelector(".player-volume");
    const rect = volumeEl.getBoundingClientRect();
    const width = rect.width;
    let vol = getEventX(e) - rect.left - 2;
    if (vol < 0) vol = 0;
    if (vol > width) vol = width;
    return Math.round((vol / width) * 100);
  }

  function updateVolume(e) {
    if (!W.player.volume_mouse_down_div) return;

    const channel = W.player.volume_mouse_down_div.querySelector(
      ".player-volume-name",
    ).textContent;
    const vol = volumeMouseToVol(e);
    W.player.volume({ channel, vol });
  }

  function volumeMouseDown(e) {
    e.preventDefault();

    let target = e.target;
    while (target && target.id === "") target = target.parentNode;
    if (!target) return;

    W.player.volume_mouse_down_div = target;
    W.player.volume_move = true;

    const channel = target.querySelector(".player-volume-name").textContent;
    const vol = volumeMouseToVol(e);
    W.player.volume({ channel, vol });

    const span = target.querySelector(".player-volume-container span");
    if (span) span.style.visibility = "visible";

    if (!W.player.volume_move_listeners_added) {
      document.addEventListener("mousemove", volumeMouseMove);
      document.addEventListener("mouseup", volumeMouseUp);
      document.addEventListener("touchmove", volumeMouseMove, {
        passive: false,
      });
      document.addEventListener("touchend", volumeMouseUp);
      W.player.volume_move_listeners_added = true;
    }
  }

  function volumeMouseMove(e) {
    e.preventDefault();
    updateVolume(e);
  }

  function volumeMouseUp(e) {
    document.removeEventListener("mousemove", volumeMouseMove);
    document.removeEventListener("mouseup", volumeMouseUp);
    document.removeEventListener("touchmove", volumeMouseMove);
    document.removeEventListener("touchend", volumeMouseUp);
    W.player.volume_move_listeners_added = false;

    if (!W.player.volume_mouse_down_div) return;

    const channel = W.player.volume_mouse_down_div.querySelector(
      ".player-volume-name",
    ).textContent;
    const span = W.player.volume_mouse_down_div.querySelector(
      ".player-volume-container span",
    );
    if (span) span.style.visibility = "hidden";

    const jsonStr = W.system.create_cmd_and_get_jsonStr("set_main_volume");
    jsonStr.args.volume = volumeMouseToVol(e);
    jsonStr.args.channel = channel;
    W.util.JSONpost("/json", jsonStr);

    setTimeout(() => {
      W.player.volume_move = false;
      W.player.volume_mouse_down_div = undefined;
    }, 100);
  }

  const originalVolumeInit = W.player.volume_init;
  W.player.volume_init = function () {
    originalVolumeInit();
    // Add touchstart listeners
    const containers = document.querySelectorAll(".player-volume-container");
    containers.forEach((el) => {
      el.addEventListener("mousedown", volumeMouseDown);
      el.addEventListener("touchstart", volumeMouseDown, { passive: false });
    });
  };
})();

W.player.mute = function (args) {
  args = args || W.data.status.mute;
  var channels = Object.keys(args);
  var channel;
  var mute;
  var update_display = function (channel, mute) {
    var speakers;
    switch (channel) {
      case "Group Volume":
      case "Master Volume":
        speakers = document.querySelector("#player-controls-vol i");
        W.css.removeClasses(
          speakers,
          "player_controls_vol",
          "player_controls_muted",
        );
        if (mute) W.css.addClasses(speakers, "player_controls_muted");
        else W.css.addClasses(speakers, "player_controls_vol");

      default:
        var volDiv = document.querySelector(
          "#" + W.player.channel_to_id(channel),
        );
        speakers = volDiv.querySelector(".player-volume-speakers button i");
        W.css.removeClasses(
          speakers,
          "player_volume_on",
          "player_volume_muted",
        );
        if (mute) W.css.addClasses(speakers, "player_volume_muted");
        else W.css.addClasses(speakers, "player_volume_on");
    }
  };
  for (var i = 0; i < channels.length; i++) {
    channel = channels[i];
    mute = parseInt(args[channel]);
    update_display(channel, mute);
  }
};

W.player.onmute = function (e) {
  var target = e.target;
  var channel;
  while (target.id == "") {
    target = target.parentNode;
  }
  if (target.id == "player-controls-vol") channel = "Group Volume";
  else channel = target.querySelector(".player-volume-name").textContent;
  var jsonStr = W.system.create_cmd_and_get_jsonStr("mute");
  jsonStr.args.channel = channel;
  W.util.JSONpost("/json", jsonStr);
};

W.player.desktop_mode = true;

W.player.handleScreenChange = function () {
  const desktop_mode = W.util.isDesktop();
  if (W.player.desktop_mode == desktop_mode) return;
  W.player.desktop_mode = desktop_mode;
  if (!desktop_mode) {
    W.player.volDiv.parentNode.removeChild(W.player.volDiv);
    W.player.vol_mobile.content.appendChild(W.player.volDiv);
  } else {
    W.player.vol_mobile.content.removeChild(W.player.volDiv);
    const controls = document.querySelector("#player-controls");
    controls.insertAdjacentElement("afterend", W.player.volDiv);
  }
};

W.util.ready(function () {
  W.player.progress_dragInit();
  var controls = document.querySelectorAll("#player-controls button");
  for (var i = 0; i < controls.length; i++) {
    controls[i].onclick = W.player.control_click;
  }
  W.player.volDiv = document.querySelector("#player-volume-outer");
  document.querySelector("#player-controls-vol").onclick = W.player.onmute;
  W.player.volTemplate = document
    .querySelector(".player-volume-div")
    .cloneNode(true);
  W.player.vol_button = document.querySelector("#player-volume-button");
  W.player.vol_mobile = new W.popup();
  document.querySelector("#player-volume-button").onclick = function () {
    W.player.vol_mobile.toggle();
  };
  W.player.vol_mobile.init = function () {
    W.css.addClasses(W.player.vol_button, "system_selected");
  };
  W.player.vol_mobile.cleanup = function () {
    W.css.removeClasses(W.player.vol_button, "system_selected");
  };
  W.player.handleScreenChange();
  W.util.mediaQuery.addEventListener("change", W.player.handleScreenChange);
});

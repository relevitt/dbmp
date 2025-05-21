"use strict";
W.data = {};

function normalizeMessage(message) {
  return message.replace(/\d+/g, "{count}"); // Replace numbers with "{count}"
}

/*W.data.queue is an array with the client copy of the queue data. */

W.data.queue = new W.dataObject({
  pageLength: 50,
  cacheSize: 50,
  build_cmd: function (args) {
    W.queue.build(args);
    W.queue_selecter.build();
  },
  paginate_cmd: W.queue.paginate,
  get_cmd: "get_queue",
  reconcile_cmd: "get_queue_ids",
  delete_cmd: "delete_queue_rows",
  move_cmd: "move_queue_rows",
  transfer_cmd: "transfer_queue_rows",
  use_system_cmd: true,
});

W.data.queue.is_playing = function () {
  return W.data.queue.id == W.data.status.queue.id;
};

W.data.quarantine = new W.dataObject({
  pageLength: 50,
  cacheSize: 50,
  build_cmd: W.quarantine.build,
  paginate_cmd: W.quarantine.paginate,
  get_cmd: "qimport.quarantine",
  reconcile_cmd: "qimport.getids",
  delete_cmd: "qimport.delete",
  move_cmd: undefined,
  use_system_cmd: false,
});

W.data.qedit = new W.simpleDataObject({
  build_cmd: W.qedit.build,
  get_cmd: "qimport.edit",
});

W.data.logs = new W.dataObject({
  pageLength: 50,
  cacheSize: 0,
  build_cmd: W.logging.build,
  paginate_cmd: undefined,
  get_cmd: "log_store.get_page",
  reconcile_cmd: undefined,
  delete_cmd: undefined,
  move_cmd: undefined,
  use_system_cmd: false,
});

W.data.status = 0;

W.data.WS_sockets = {};

W.data.selected_sonos_group_id = 0;

// true of false
W.data.password_set = false;

W.data.WS_socket_create = function (config) {
  let url =
    config.protocol + "://" + location.host.split(":")[0] + ":" + config.port;
  let socket = new WebSocket(url);
  W.data.WS_sockets[config.name] = socket;
  socket.onopen = W.data[config.onopen];
  socket.onmessage = W.data[config.onmessage];
  socket.onerror = function (error) {
    // Add logging if we want it
  };
  socket.onclose = function (event) {
    // Add logging if we want it
  };
};

W.data.WS_onopen = function () {
  var jsonStr = {};
  jsonStr.object = W.system.object;
  jsonStr.clientid = W.system.client_id; //unused?
  jsonStr.queueid = W.data.selected_sonos_group_id;
  W.data.WS_send(jsonStr);
};

W.data.WS_change_sonos_group = function (uid) {
  var jsonStr = {};
  jsonStr.sonos_group = uid;
  W.data.WS_send(jsonStr);
};

W.data.WS_send = function (jsonStr) {
  if (W.data.WS_sockets.comms) {
    W.data.WS_sockets.comms.send(JSON.stringify(jsonStr));
  }
};

/*
For queues, the displayed queue need not be the one playing. Therefore, WS updates may be received
for more than one queue. 

For sonos, the W.player and W.queue modules are always showing the same group. Therefore, we subscribe 
to WS updates only for one group, being the one we are displaying.
*/

W.data.WS_receive = function (event) {
  var items = JSON.parse(event.data);
  switch (items.type) {
    case "init":
      W.data.status = items;
      W.data.status.song_length =
        items.song_length != undefined && items.song_length != -1
          ? items.song_length
          : 0;
      W.data.queue.get(-1);
      W.queue_selecter.init();
      W.player.init();
      W.player.volume_init();
      W.player.updateCover(
        items.connected ? items.song.album_art_uri : "disconnected",
      );
      W.queue_menus.init();
      // We store this to retain a record of the last displayed
      // sonos queue when switch the display from sonos to dbmp
      if (W.system.object == "sonos") {
        W.data.selected_sonos_group_id = items.queue.id;
      }
      break;
    case "queues": // Not used by WS_sonos.py, as 'init' occurs when groups change
      W.data.status.queues = items.queues;
      W.queue_selecter.init();
      if (items.deleted == W.data.queue.id) {
        W.data.queue.get(-1);
      } else {
        W.data.queue.label =
          W.data.status.queues[W.queue_selecter.selectedIndex].name;
        W.data.queue.locked =
          W.data.status.queues[W.queue_selecter.selectedIndex].locked;
        W.queue.set_name();
      }
      break;
    case "queue_contents":
      if (W.data.queue.id == items.queue.id) {
        W.data.queue.reconcile();
      }
      break;
    case "queue": //This is the queue being played, not the one being displayed
      W.data.status.queue.id = items.queue.id;
      W.queue.queue_name();
      W.queue_selecter.queue_name();
      break;
    case "queue_position":
      if (W.data.queue.id == items.id || W.system.object == "sonos") {
        W.data.queue.queue_position = items.queue_position;
        W.queue.queue_position();
      }
      break;
    case "song":
      var album_art_uri = W.data.status.song.album_art_uri;
      W.data.status.song = items.song;
      if (album_art_uri != items.song.album_art_uri) {
        W.player.updateCover(items.song.album_art_uri);
      }
      W.data.status.song_length =
        items.song_length != undefined && items.song_length != -1
          ? items.song_length
          : 0;
      W.player.init();
      break;
    case "playing_from_queue":
      if (items.results !== W.data.status.playing_from_queue) {
        W.data.status.playing_from_queue = items.result;
        W.queue.status();
      }
      break;
    case "artwork":
      if (
        items.category == "album" &&
        W.data.status.song.albumid == items.item_id
      ) {
        W.data.status.song.album_art_uri = items.uri;
        W.player.updateCover(items.uri);
      }
      W.search.update_artwork(items);
      break;
    case "song_progress":
      W.data.status.song_progress = items.song_progress;
      W.player.song_position();
      break;
    case "status":
      W.data.status.playing = items.playing;
      W.data.status.paused = items.paused;
      W.queue.status();
      W.player.status();
      break;
    case "volume":
      W.data.status.volume = items.volume;
      W.player.volume();
      break;
    case "mute":
      var channel = Object.keys(items.mute)[0];
      if (W.data.status.mute[channel] != items.mute[channel]) {
        W.data.status.mute[channel] = items.mute[channel];
        W.player.mute(items.mute);
      }
      break;
    case "snapshot_id":
      W.data.queue.snapshot_id = items.snapshot_id;
      break;
    case "progress_total_calc":
      W.data.progress_list[items.ticket].progress_total_calc(items.total_calc);
      break;
    case "progress_total":
      W.data.progress_list[items.ticket].progress_total(items.total);
      break;
    case "progress_count":
      W.data.progress_list[items.ticket].progress_count(items.count);
      break;
    case "zipfiles":
      W.import.zipfile_confirm(items.ticket, items.file_groups, items.zipfile);
      break;
    case "get_pwd":
      W.util.getPassword(items.wrong_pwd);
      break;
    case "set_queue_alert":
      W.queue.set_queue_alert(items.alert);
      break;
    case "log":
      if (
        W.data.logs.id &&
        W.data.logs.id != "all" &&
        W.data.logs.id != items.message.source
      )
        return;
      if (items.message.name === "log_summarizer") {
        let last_log = W.data.logs.data.at(-1);
        if (!last_log) break;
        let repeating_log =
          ["name", "source", "level"].every(
            (field) => items.message[field] === last_log[field],
          ) &&
          normalizeMessage(items.message.message) ===
            normalizeMessage(last_log.message);
        if (repeating_log) {
          W.logging.repeating_log(items.message);
          break;
        }
      }
      let next_page = false;
      if (
        W.data.logs.totalRecords &&
        W.data.logs.totalRecords % W.data.logs.pageLength === 0
      ) {
        next_page = true;
        if (
          W.data.logs.startIndex ===
          W.data.logs.totalRecords - W.data.logs.pageLength
        ) {
          W.data.logs.data = [];
          W.data.logs.startIndex += W.data.logs.pageLength;
        }
      }
      W.data.logs.data.push(items.message);
      W.data.logs.totalRecords += 1;
      if (next_page) W.logging.build();
      else W.logging.add_log(items.message);
      break;
    case "log_history":
      W.data.logs.data = items.logs.results;
      W.data.logs.startIndex = items.logs.startIndex;
      W.data.logs.totalRecords = items.logs.totalRecords;
      W.logging.build();
      break;
    case "hostname":
      document.title = `dbmp on ${items.hostname}`;
      break;
    case "google":
      W.data.google = items.google;
      break;
    case "password":
      // true or false
      W.data.password_set = items.password_set;
    case "root_cert":
      W.data.root_cert_available = items.root_cert;
  }
};

W.data.WS_checkclosed = function (event) {
  W.data.WS_config.forEach((config) => {
    let socket = W.data.WS_sockets[config.name];
    if (!socket || socket.readyState == 3) {
      W.data.WS_socket_create(config);
    }
  });
};

W.data.WS_send_pwd = function (pwd) {
  var jsonStr = {};
  jsonStr.pwd = pwd;
  W.data.WS_send(jsonStr);
};

W.data.WS_return_result = function (ticket, results) {
  var jsonStr = {};
  jsonStr.return_result = true;
  jsonStr.results = results;
  jsonStr.ticket = ticket;
  W.data.WS_send(jsonStr);
};

W.data.progress_list = {};

W.data._ticket = 0;

W.data.progress_init = function (o, process_msg, init_msg) {
  var ticket = W.data._ticket++;
  W.data.progress_list[ticket] = o;
  o.progress_init(process_msg, init_msg, ticket);
  return {
    sid: W.data.status.sid,
    ticket: ticket,
  };
};

W.data.progress_cancel = function (ticket) {
  var jsonStr = {};
  jsonStr.progress_cancel = true;
  jsonStr.ticket = ticket;
  W.data.WS_send(jsonStr);
  W.data.progress_complete(ticket);
};

W.data.progress_complete = function (ticket) {
  delete W.data.progress_list[ticket];
};

W.util.ready(function () {
  fetch("/config.json")
    .then((res) => res.json())
    .then((cfg) => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const port = protocol === "wss" ? cfg.wss_port : cfg.ws_port;

      W.data.WS_config = [
        {
          name: "comms",
          port: port,
          protocol: protocol,
          onopen: "WS_onopen",
          onmessage: "WS_receive",
        },
      ];
      W.data.https_port = cfg.https_port;
      W.data.WS_config.forEach(W.data.WS_socket_create);
      setInterval(W.data.WS_checkclosed, 1000);

      // Handle page visibility changes
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
          W.data.WS_checkclosed();
        }
      });
    })
    .catch((err) => {
      console.error("Failed to fetch websocket config:", err);
    });
});

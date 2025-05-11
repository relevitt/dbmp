"use strict";
W.dataObject = function (args) {
  /* args:
		pageLength: the number of rows to be displayed on a page 
		cacheSize: the number of additional rows to be held in cache 
		build_cmd: the function to be called to display a page of data, 
		paginate_cmd: the function to be called to display a paginator, 
		get_cmd: the json cmd to be sent to the server to get data, 
		reconcile_cmd: the json cmd to be sent to the server to get a list of expected ids, 
		delete_cmd: the json cmd to be sent to the server to delete rows, 
		move_cmd: the json cmd to be sent to the server to move rows,
		transfer_cmd: the json cmd to be sent to the server to transfer rows,
		use_system_cmd: whether to use the system module to build json cmds
	*/

  this.data = [];
  this.pageLength = args.pageLength;
  this.cacheSize = args.cacheSize;
  this.cacheTrigger = this.cacheSize - 10;
  this.build = args.build_cmd;
  this.paginate = args.paginate_cmd;
  this.get_cmd = args.get_cmd;
  this.reconcile_cmd = args.reconcile_cmd;
  this.delete_cmd = args.delete_cmd;
  this.move_cmd = args.move_cmd;
  this.transfer_cmd = args.transfer_cmd;
  this.use_system_cmd = args.use_system_cmd;
  this.cacheUpdating = false;
};

W.dataObject.prototype.empty = function () {
  this.data = [];
  this.startIndex = 0;
  this.totalRecords = 0;
};

W.dataObject.prototype.get = function (start, id, preserve_scroll, selected) {
  var jsonStr;
  var args = {};
  var cb;
  args.startIndex = start == undefined ? 0 : start;
  args.rowsPerPage = this.pageLength;
  args.numRows = this.pageLength + this.cacheSize;
  id != undefined && (args.id = id);
  if (this.use_system_cmd) {
    jsonStr = W.system.create_cmd_and_get_jsonStr(this.get_cmd, args);
  } else {
    jsonStr = W.system.get_jsonStr(this.get_cmd, args);
  }
  cb = function (o) {
    this.empty();
    this.totalRecords = o.results.totalRecords;
    this.startIndex = o.results.startIndex;
    this.snapshot_id = o.results.snapshot_id;
    if (o.results.label != undefined) {
      this.label = o.results.label;
    }
    if (o.results.id != undefined) {
      this.id = o.results.id;
    }
    if (o.results.locked != undefined) {
      this.locked = o.results.locked;
    }
    if (o.results.queue_position != undefined) {
      this.queue_position = o.results.queue_position;
    }
    for (var i = 0; i < o.results.results.length; i++) {
      this.data.push(o.results.results[i]);
    }
    this.build({
      selected: selected ? selected.selected : false,
      preserve_scroll: preserve_scroll,
    });
    selected && selected.fn();
  }.bind(this);
  W.util.JSONpost("/json", jsonStr, cb);
};

W.dataObject.prototype.getCacheSize = function () {
  return Math.max(0, this.data.length - this.pageLength);
};

W.dataObject.prototype.getViewportLength = function () {
  return Math.min(this.data.length, this.pageLength);
};

W.dataObject.prototype.reconcile = function () {
  console.log("reconciling");
  var cb;
  var jsonStr;
  var args = {};
  if (this.id != undefined) {
    args.id = this.id;
  }
  args.startIndex = this.startIndex;
  args.rowsPerPage = this.pageLength + this.getCacheSize();

  if (this.use_system_cmd) {
    jsonStr = W.system.create_cmd_and_get_jsonStr(this.reconcile_cmd, args);
  } else {
    jsonStr = W.system.get_jsonStr(this.reconcile_cmd, args);
  }

  cb = function (o) {
    if (o.results.id == undefined || o.results.id == this.id) {
      if (o.results.results.length != this.data.length) {
        console.log("length mismatch");
        this.get(this.startIndex, this.id, true);
        return;
      }
      for (var i = 0; i < this.data.length; i++) {
        if (o.results.results[i] != this.data[i].id) {
          console.log("content mismatch");
          this.get(this.startIndex, this.id, true);
          return;
        }
      }
      if (this.totalRecords != o.results.totalRecords) {
        console.log("totalRecords mismatch");
        this.totalRecords = o.results.totalRecords;
        this.snapshot_id = o.results.snapshot_id;
        this.paginate();
        return;
      }
      this.snapshot_id = o.results.snapshot_id;
      console.log("reconciled");
    }
  }.bind(this);
  W.util.JSONpost("/json", jsonStr, cb);
};

W.dataObject.prototype.move_rows = function (
  dest,
  indices,
  movedData,
  offset,
  startId,
  snapshot_id,
  system,
) {
  //We receive raw indices without offset. The offset is added below

  if (W.system.object == "dbmp" && system == "sonos") return;
  var moved = []; //The positions to be shown as selected after the move. Excludes those not being displayed.
  var d = dest + this.startIndex;
  if (offset == this.startIndex && this.id == startId) {
    for (var i = indices.length - 1; i >= 0; i--) {
      this.data.splice(indices[i], 1);
      if (indices[i] < dest) {
        dest--;
      }
    }
  } else if (
    offset == this.startIndex + this.pageLength &&
    this.id == startId
  ) {
    for (var i = indices.length - 1; i >= 0; i--) {
      this.data.splice(this.pageLength + indices[i], 1);
    }
  } else if (offset > this.startIndex + this.pageLength && this.id == startId) {
    for (var i = 0; i < indices.length; i++) {
      this.data.pop();
    }
  } else if (this.id != startId) {
    while (
      this.data.length + indices.length >
      this.pageLength + this.cacheSize
    ) {
      this.data.pop();
    }
  } else {
    var rem = indices.length;
    while (dest && rem) {
      this.data.shift();
      rem--;
      dest--;
    }
    while (rem) {
      movedData.shift();
      rem--;
    }
  }
  while (movedData.length) {
    this.data.splice(dest, 0, movedData.shift());
    if (dest < this.pageLength) {
      moved.push(dest);
    }
    dest++;
  }
  for (var i = 0; i < indices.length; i++) {
    indices[i] += offset;
  }
  var update_loaded = function () {
    var i_was = -1;
    var new_dest = d;
    var new_loaded = this.queue_position;
    for (var i = 0; i < indices.length; i++) {
      if (indices[i] < d) {
        new_dest--;
      }
      if (indices[i] == this.queue_position) {
        i_was = i;
      } else {
        if (indices[i] < this.queue_position) {
          new_loaded--;
        }
        if (new_dest + i <= new_loaded) {
          new_loaded++;
        }
      }
    }
    if (i_was >= 0) {
      new_loaded = new_dest + i_was;
    }
    return new_loaded;
  }.bind(this);
  if (this.queue_position != undefined) {
    if (this.id == startId) this.queue_position = update_loaded();
    else {
      if (d <= this.queue_position) {
        this.queue_position = this.queue_position + indices.length;
      }
    }
  }
  var jsonStr;
  var args = {};
  if (this.id != undefined) {
    args.id = this.id;
  }
  if (startId != undefined) {
    args.startId = startId;
  }
  args.system = W.util.dragsystem;
  args.dest = d;
  args.indices = indices;
  args.snapshot_id = snapshot_id;

  if (this.use_system_cmd) {
    if (this.id == args.startId) {
      jsonStr = W.system.create_cmd_and_get_jsonStr(this.move_cmd, args);
    } else {
      args.source_snapshot_id = snapshot_id;
      args.snapshot_id = this.snapshot_id;
      jsonStr = W.system.create_cmd_and_get_jsonStr(this.transfer_cmd, args);
    }
  } else {
    jsonStr = W.system.get_jsonStr(this.move_cmd, args);
  }
  var cb = function (o) {
    if (o.results && o.results.status && o.results.status == "ERROR") return;
    if (
      o.results &&
      o.results.status &&
      o.results.status == "WRONG_SNAPSHOT_ID"
    ) {
      this.get(this.startIndex, this.id, true);
      return;
    }
    o.results && (this.snapshot_id = o.results.snapshot_id);
    this.build({
      selected: moved,
      preserve_scroll: true,
    });
  }.bind(this);
  W.util.JSONpost("/json", jsonStr, cb);
};

W.dataObject.prototype.delete_rows = function (
  indices,
  deletions,
  selected = false,
) {
  //We receive raw indices without offset. The offset is added below

  for (var i = 0; i < indices.length; i++) {
    this.data.splice(indices[i], 1);
    this.totalRecords--;
    indices[i] += this.startIndex;
    if (this.queue_position != undefined && indices[i] < this.queue_position) {
      this.queue_position--;
    }
  }
  if (this.queue_position != undefined && this.queue_position < 0) {
    this.queue_position = 0;
  }

  var next = this.startIndex + this.data.length;
  var cacheSize = this.getCacheSize();
  var jsonStr;
  var args;

  if (this.totalRecords > next && cacheSize < this.cacheTrigger) {
    args = {};
    if (this.id != undefined) {
      args.id = this.id;
    }
    args.startIndex = next + indices.length; //We have already deleted from our data
    args.rowsPerPage = this.cacheSize - cacheSize;
    args.numRows = this.cacheSize - cacheSize;

    if (this.use_system_cmd) {
      jsonStr = W.system.create_cmd_and_get_jsonStr(this.get_cmd, args);
    } else {
      jsonStr = W.system.get_jsonStr(this.get_cmd, args);
    }

    cb = function (o) {
      for (var i = 0; i < o.results.results.length; i++) {
        this.data.push(o.results.results[i]);
      }
      this.cacheUpdating = false;
    }.bind(this);
    this.cacheUpdating = true;
    W.util.JSONpost("/json", jsonStr, cb);
  } else if (this.startIndex && !this.data.length) {
    this.get(this.startIndex - this.pageLength, this.id);
  }
  args = {};
  if (this.id != undefined) {
    args.id = this.id;
  }
  if (deletions != undefined) {
    args.indices = deletions;
  } else {
    args.indices = indices;
  }
  args.snapshot_id = this.snapshot_id;
  if (this.use_system_cmd) {
    jsonStr = W.system.create_cmd_and_get_jsonStr(this.delete_cmd, args);
  } else {
    jsonStr = W.system.get_jsonStr(this.delete_cmd, args);
  }
  var cb = function (o) {
    if (o.results && o.results.status && o.results.status == "ERROR") return;
    if (
      o.results &&
      o.results.status &&
      o.results.status == "WRONG_SNAPSHOT_ID"
    ) {
      this.get(this.startIndex, this.id, true);
      return;
    }
    o.results && (this.snapshot_id = o.results.snapshot_id);
    this.build({
      selected: selected,
      preserve_scroll: true,
    });
  }.bind(this);
  W.util.JSONpost("/json", jsonStr, cb);
};

/*
	Simple form of dataObject, with:
		get(id)
		no pagination
		no cache
		no server reconciliation

*/

W.simpleDataObject = function (args) {
  /* args:
		build_cmd: the function to be called to display a page of data, 
		get_cmd: the json cmd to be sent to the server to get data, 
	*/

  this.data = [];
  this.build = args.build_cmd;
  this.get_cmd = args.get_cmd;
};

W.simpleDataObject.prototype.empty = function () {
  this.data = [];
};

W.simpleDataObject.prototype.get = function (id) {
  var jsonStr = W.system.get_jsonStr(this.get_cmd);
  jsonStr.args.id = id;
  var cb = function (o) {
    this.empty();
    if (o.results.artist != undefined) {
      this.artist = o.results.artist;
    }
    if (o.results.album != undefined) {
      this.album = o.results.album;
    }
    this.data = o.results.results;
    this.build();
  }.bind(this);
  W.util.JSONpost("/json", jsonStr, cb);
};

W.simpleDataObject.prototype.move_rows = function (dest, indices, movedData) {
  var moved = []; //The updated positions after the move.
  var d = dest;
  for (var i = indices.length - 1; i >= 0; i--) {
    this.data.splice(indices[i], 1);
    if (indices[i] < dest) {
      dest--;
    }
  }
  while (movedData.length) {
    this.data.splice(dest, 0, movedData.shift());
    moved.push(dest);
    dest++;
  }
  this.build({
    selected: moved,
  });
};

W.simpleDataObject.prototype.delete_rows = function (indices) {
  for (var i = 0; i < indices.length; i++) {
    this.data.splice(indices[i], 1);
  }
};

/*
	Lazy loading dataObject, used in search.js

*/

W.lazyDataObject = function (args) {
  /* args:
		pageLength:	the number of rows to be displayed on a page 
		build_cmd:	the function to be called to display a page of data 
		get_cmd:	the json cmd to be sent to the server to get data
		get_function:	(optional) the function to be called to build the json cmd
		progress_fn:	(optional) an array with two functions, the first to be called
				when data is requested, the second when data is returned
		delete_cmd:	(if applicable) the json cmd to be sent to the server to delete rows
		move_cmd:	(if applicable) the json cmd to be sent to the server to move rows
		loadAll:	(optional) if true, all data will be loaded (no lazy loading)
		loadAllfn:	(optional) a function to execute when all data has been loaded and 
				build_cmd has returned; takes indices of any selected items as its argument
	*/

  this.data = [];
  this.metadata = {};
  // this.searching is set to true only by this.get and not by
  // this.get_more, while this.updating is set to true by
  // this.__get__, meaning it is set to true by both this.get
  // and by this get_more. The two flags are used for different
  // purposes.
  this.searching = false;
  this.active = true;
  this.pageLength = args.pageLength;
  this.build = args.build_cmd;
  this.get_cmd = args.get_cmd;
  this.get_function = args.get_function;
  this.progress_fn = args.progress_fn;
  this.delete_cmd = args.delete_cmd;
  this.move_cmd = args.move_cmd;
  this.loadAll = args.loadAll;
  this.loadAllfn = args.loadAllfn;
};

W.lazyDataObject.prototype.make_active = function () {
  this.active = true;
  if (this.updating && this.progress_fn) {
    this.stop_progress();
    var fn = function () {
      this.progress_fn[0]();
      this.progress_timer = 0;
    }.bind(this);
    this.progress_timer = setTimeout(fn, 1000);
  }
};

W.lazyDataObject.prototype.make_dormant = function () {
  this.stop_progress();
  this.active = false;
};

W.lazyDataObject.prototype.empty = function () {
  this.data = [];
  this.startIndex = 0;
  this.totalRecords = 0;
  this.loadedAll = false;
};

W.lazyDataObject.prototype.get = function (id, value) {
  // We don't do this for this.get_more
  this.searching = true;

  // This will warn the user if the search is going to
  // be long running (recommendations and related artists)
  if (
    this.get_cmd.includes("recommendations") ||
    this.get_cmd.includes("related_artists") ||
    String(id).includes("Recommendations")
  ) {
    window.setTimeout(() => {
      if (W.search.dataObject && W.search.dataObject.updating)
        W.util.toast(
          `This may take some time.<br>
If you leave this page,<br>
the search will continue<br>
in the background`,
          4000,
        );
    }, 2000);
  }

  this.__get__(
    0,
    id != undefined ? id : this.id,
    value != undefined ? value : this.value,
    function (o) {
      this.searching = false;
      this.stop_progress();
      this.updating = false;
      if (o.results == "CANCELLED") return;
      var i;
      this.empty();
      this.totalRecords = o.results.totalRecords;
      this.startIndex = o.results.startIndex;
      if (o.results.id != undefined) {
        this.id = o.results.id;
      }
      if (o.results.value != undefined) {
        this.value = o.results.value;
      }
      if (o.results.metadata != undefined) {
        if (!this.metadata) this.metadata = o.results.metadata;
        else {
          var keys = Object.keys(o.results.metadata);
          for (i = 0; i < keys.length; i++) {
            this.metadata[keys[i]] ||
              (this.metadata[keys[i]] = o.results.metadata[keys[i]]);
          }
          // Force an update of these items
          o.results.metadata.artist &&
            (this.metadata.artist = o.results.metadata.artist);
          o.results.metadata.artistid &&
            (this.metadata.artistid = o.results.metadata.artistid);
          o.results.metadata.artistArtURI &&
            (this.metadata.artistArtURI = o.results.metadata.artistArtURI);
        }
      }
      for (i = 0; i < o.results.results.length; i++) {
        this.data.push(o.results.results[i]);
      }
      if (this.active)
        this.build({
          refresh: true,
        });
      this.loadAll && this.get_more(null, this.pageLength);
    }.bind(this),
  );
};

W.lazyDataObject.prototype.stop_progress = function () {
  if (this.progress_fn) {
    if (this.progress_timer) {
      clearTimeout(this.progress_timer);
      this.progress_timer = 0;
    }
    this.progress_fn[1]();
  }
};

W.lazyDataObject.prototype.get_more = function (e, n) {
  if (this.loadedAll || this.updating) return;
  if (this.totalRecords > this.data.length) {
    n =
      n != undefined
        ? n
        : Math.min(this.pageLength, parseInt(this.data.length / 5));
    this.__get__(
      this.data.length,
      this.id,
      this.value,
      function (o) {
        this.stop_progress();
        this.updating = false;
        if (o.results == "CANCELLED") return;
        this.totalRecords = o.results.totalRecords;
        this.startIndex = o.results.startIndex;
        for (var i = 0; i < o.results.results.length; i++) {
          this.data.push(o.results.results[i]);
        }
        if (this.active)
          this.build({
            startIndex: this.startIndex,
            buildSize: o.results.results.length,
          });
        this.loadAll && this.get_more(null, this.pageLength);
      }.bind(this),
      n,
    );
  } else {
    this.loadedAll = true;
    this.loadAllfn && this.loadAllfn();
  }
};

W.lazyDataObject.prototype.__get__ = function (start, id, value, cb, length) {
  var jsonStr = W.system.get_jsonStr(
    this.get_function ? this.get_function(this.get_cmd) : this.get_cmd,
  );
  var cb;
  if (start == undefined) {
    jsonStr.args.startIndex = 0;
  } else {
    jsonStr.args.startIndex = start;
  }
  jsonStr.args.rowsPerPage = length || this.pageLength;
  if (id != undefined) {
    jsonStr.args.id = id;
  }
  if (value != undefined) {
    jsonStr.args.value = value;
  }
  if (this.progress_fn) {
    this.stop_progress();
    var fn = function () {
      this.progress_fn[0]();
      this.progress_timer = 0;
    }.bind(this);
    this.progress_timer = setTimeout(fn, 1000);
  }
  // It seems poor design to set this.updating here
  // and unset it in the cb
  this.updating = true;
  W.util.JSONpost("/json", jsonStr, cb, this.stop_progress);
};

W.lazyDataObject.prototype.move_rows = function (dest, indices) {
  var jsonStr = W.system.get_jsonStr(this.move_cmd, W.search_menus.get_args());
  var moves = W.util.create_moves(indices, dest);
  var moved = []; //The positions to be shown as selected after the move.
  dest = undefined;
  var cb = function (o) {
    this.stop_progress();
    if (o.results == "UNAUTHORISED") return;
    if (o.results.status == "ERROR") return;
    if (o.results.status == "WRONG_SNAPSHOT_ID") {
      W.search_edit.reload_data(o);
      return;
    }
    this.metadata.snapshot_id = o.results.snapshot_id;
    if (this.metadata.snapshot_id) {
      var movedData = [];
      var i, n, index, range, dest;
      range = jsonStr.args.move[1];
      dest = jsonStr.args.move[2];
      index = jsonStr.args.move[0] + range;
      for (i = 0; i < range; i++) {
        index--;
        movedData.push(this.data[index]);
        this.data.splice(index, 1);
        indices.shift();
        for (n = 0; n < indices.length; n++) {
          if (index < indices[n]) indices[n]--;
          if (dest <= indices[n]) indices[n]++;
        }
        if (index < dest) {
          dest--;
        }
      }
      while (movedData.length) {
        this.data.splice(dest, 0, movedData.pop());
        moved.push(dest);
        dest++;
      }
      this.build({
        restart: true,
      });
      if (moves.length) execute();
      else {
        this.loadAllfn && this.loadAllfn(moved);
        moved = [];
      }
    } else {
      moves = [];
      while (indices.length) moved.push(indices.shift());
      this.loadAllfn && this.loadAllfn(moved);
      moved = [];
    }
  }.bind(this);
  var execute = function () {
    jsonStr.args.move = moves.shift();
    jsonStr.args.snapshot_id = this.metadata.snapshot_id;
    if (this.progress_fn) {
      this.stop_progress();
      var fn = function () {
        this.progress_fn[0]();
        this.progress_timer = 0;
      }.bind(this);
      this.progress_timer = setTimeout(fn, 1000);
    }
    W.util.JSONpost("/json", jsonStr, cb, this.stop_progress);
  }.bind(this);
  moves.length && execute();
};

W.lazyDataObject.prototype.delete_rows = function (indices) {
  if (!indices.length || !this.delete_cmd) return;
  var jsonStr = W.system.get_jsonStr(
    this.delete_cmd,
    W.search_menus.get_args(),
  );
  var chunks = [];
  var chunk = [];
  var item;
  for (var i = 0; i < indices.length; i++) {
    if (W.search_top.object == "spotify")
      item = {
        uri: this.data[indices[i]].itemid,
        positions: [indices[i]],
      };
    else item = indices[i];
    chunk.push(item);
    if (chunk.length == 50) {
      chunks.push(chunk);
      chunk = [];
    }
  }
  chunk.length && chunks.push(chunk);
  chunk = undefined;
  indices = undefined;
  var cb = function (o) {
    var p;
    this.stop_progress();
    if (o.results == "UNAUTHORISED") return;
    if (o.results.status == "ERROR") return;
    if (o.results.status == "WRONG_SNAPSHOT_ID") {
      W.search_edit.reload_data(o);
      return;
    }
    this.metadata.snapshot_id = o.results.snapshot_id;
    if (this.metadata.snapshot_id) {
      for (var i = 0; i < jsonStr.args.tracks.length; i++) {
        if (W.search_top.object == "spotify")
          p = jsonStr.args.tracks[i].positions[0];
        else p = jsonStr.args.tracks[i];
        this.data.splice(p, 1);
        this.totalRecords--;
      }
      this.build({
        restart: true,
      });
      this.loadAllfn && this.loadAllfn();
      chunks.length && execute();
    } else {
      chunks = [];
    }
  }.bind(this);
  var execute = function () {
    jsonStr.args.tracks = chunks.shift();
    jsonStr.args.snapshot_id = this.metadata.snapshot_id;
    if (this.progress_fn) {
      this.stop_progress();
      var fn = function () {
        this.progress_fn[0]();
        this.progress_timer = 0;
      }.bind(this);
      this.progress_timer = setTimeout(fn, 1000);
    }
    W.util.JSONpost("/json", jsonStr, cb, this.stop_progress);
  }.bind(this);
  execute();
};

PRAGMA journal_mode = WAL;
CREATE TABLE "artist" (
	"id"	INTEGER,
	"artist"	TEXT,
	"date_added"	TEXT,
	"artwork_update"	INTEGER,
	PRIMARY KEY("id" ASC)
);
CREATE TABLE "auth_access" (
	"clientid"	INTEGER NOT NULL,
	"time"	INTEGER NOT NULL
);
CREATE TABLE "clipboard_access" (
	"clientid"	INTEGER NOT NULL,
	"time"	INTEGER NOT NULL
);
CREATE TABLE "clipboard_data" (
	"clientid"	INTEGER NOT NULL,
	"songid"	TEXT NOT NULL,
	"type"	TEXT NOT NULL,
	"track_num"	INTEGER NOT NULL
);
CREATE TABLE "config" (
	"key"	TEXT,
	"value"	TEXT,
	PRIMARY KEY("key")
);
CREATE TABLE "covers" (
	"artist_last_searched"	INTEGER DEFAULT 0,
	"artist_last_id_updated"	INTEGER DEFAULT 0,
	"album_last_searched"	INTEGER DEFAULT 0,
	"album_last_id_updated"	INTEGER DEFAULT 0
);
CREATE TABLE "disc" (
	"id"	INTEGER,
	"title"	TEXT,
	"artistid"	INTEGER,
	"genre"	TEXT,
	"year"	INTEGER,
	"date_added"	TEXT,
	"artwork_update"	INTEGER,
	"snapshot_id"	INTEGER NOT NULL DEFAULT 1,
	PRIMARY KEY("id" ASC)
);
CREATE TABLE "lastfm_artists" (
	"lastfm_url"	TEXT UNIQUE ON CONFLICT IGNORE,
	"lastfm_name"	TEXT,
	"spotify_uri"	TEXT,
	"spotify_name"	TEXT,
	"spotify_art_uri"	TEXT
);
CREATE TABLE "lastfm_tracks" (
	"lastfm_url"	TEXT UNIQUE ON CONFLICT IGNORE,
	"lastfm_name"	TEXT,
	"lastfm_artist"	TEXT,
	"spotify_title"	TEXT,
	"spotify_uri"	TEXT,
	"spotify_artist"	TEXT,
	"spotify_artist_uri"	TEXT,
	"spotify_album"	TEXT,
	"spotify_album_uri"	TEXT,
	"spotify_album_artURI"	TEXT,
	"play_time"	TEXT
);
CREATE TABLE "logs" (
	"timestamp"	REAL,
	"source"	TEXT,
	"log"	TEXT
);
CREATE TABLE "playlist_data" (
	"playlistid"	INTEGER NOT NULL,
	"songid"	TEXT NOT NULL,
	"track_num"	INTEGER NOT NULL,
	"type"	TEXT NOT NULL DEFAULT 's'
);
CREATE TABLE "playlist_names" (
	"id"	INTEGER NOT NULL,
	"name"	TEXT,
	"snapshot_id"	INTEGER,
	"artwork_uris"	TEXT,
	PRIMARY KEY("id")
);
CREATE TABLE "queue_data" (
	"queue_id"	INTEGER NOT NULL,
	"songid"	INTEGER NOT NULL,
	"track_num"	INTEGER NOT NULL
);
CREATE TABLE "queue_names" (
	"id"	INTEGER,
	"name"	TEXT,
	"position"	INTEGER,
	"playing"	INTEGER DEFAULT 0,
	"locked"	INTEGER NOT NULL DEFAULT 0,
	"system"	INTEGER NOT NULL DEFAULT 0,
	"snapshot_id"	INTEGER NOT NULL DEFAULT 1,
	"seek"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id" ASC)
);
INSERT INTO queue_names (
    id,
    name,
    position,
    playing,
    locked,
    system,
    snapshot_id,
    seek) 
    VALUES (1, "player", 0, 1, 0, 1, 1, 0);
CREATE TABLE "search" (
	"id"	INTEGER NOT NULL,
	"filename"	TEXT UNIQUE,
	"title"	TEXT,
	"album"	TEXT,
	"artist"	TEXT,
	"extra"	TEXT,
	"tag_title"	TEXT,
	"tag_album"	TEXT,
	"tag_artist"	TEXT,
	"tag_genre"	TEXT,
	"tag_track_num"	INTEGER,
	"updated"	INTEGER,
	PRIMARY KEY("id")
);
CREATE TABLE "song" (
	"id"	INTEGER,
	"filename"	TEXT,
	"title"	TEXT,
	"artistid"	INTEGER,
	"discid"	INTEGER,
	"genre"	TEXT,
	"track_num"	INTEGER,
	"start_frame"	INTEGER,
	"num_frames"	INTEGER,
	"play_time"	TEXT DEFAULT NULL,
	"year"	INTEGER,
	"date_added"	TEXT,
	PRIMARY KEY("id" ASC)
);
CREATE TABLE "sonos_queue_data" (
	"groupid"	TEXT,
	"track_num"	INTEGER,
	"album"	TEXT,
	"artist"	TEXT,
	"song"	TEXT,
	"play_time"	TEXT,
	"id"	TEXT,
	"history"	TEXT DEFAULT '[]'
);
CREATE TABLE "sonos_queues" (
	"groupid"	TEXT NOT NULL,
	"snapshot_id"	INTEGER NOT NULL DEFAULT 1,
	PRIMARY KEY("groupid")
);
CREATE TABLE "spotify_auth" (
	"client_id"	TEXT NOT NULL,
	"user_id"	TEXT NOT NULL,
	"access_token"	TEXT NOT NULL,
	"expires_in"	INTEGER NOT NULL,
	"refresh_token"	TEXT NOT NULL
);
CREATE TABLE "spotify_recommendations" (
	"seed_uri"	TEXT,
	"position"	INTEGER,
	"recommended_track_uri"	TEXT,
	"timestamp"	INTEGER
);
CREATE TABLE "spotify_recommendations_seeds" (
	"seed_uri"	TEXT,
	"spotify_uri"	TEXT
);
CREATE TABLE "spotify_related_artists" (
	"seed_artist_uri"	TEXT,
	"position"	INTEGER,
	"related_artist_uri"	TEXT,
	"timestamp"	INTEGER
);
CREATE TABLE "spotify_track_cache" (
    "song" TEXT,
    "songid" TEXT UNIQUE ON CONFLICT IGNORE, 
    "artist" TEXT,
    "artistid" TEXT, 
    "album" TEXT,
    "albumid" TEXT,
    "artURI" TEXT, 
    "play_time" TEXT
);
CREATE INDEX "song_discid" ON "song" (
	"discid"	ASC
);
CREATE INDEX "song_artistid" ON "song" (
	"artistid"	ASC
);
CREATE INDEX "disc_artistid" ON "disc" (
	"artistid"	ASC
);

"use strict";
W.spotify = {};

function generateCodeVerifier(length) {
  let text = "";
  let possible =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < length; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

async function generateCodeChallenge(codeVerifier) {
  const data = new TextEncoder().encode(codeVerifier);
  const digest = await window.crypto.subtle.digest("SHA-256", data);
  return btoa(String.fromCharCode.apply(null, [...new Uint8Array(digest)]))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

W.spotify.auth = async function (same_window) {
  const code_verifier = generateCodeVerifier(128);
  const code_challenge = await generateCodeChallenge(code_verifier);

  const where = same_window === true ? "_self" : W.system.client_id;
  if (where !== "_self") {
    const win = window.open("", where);
    if (win) win.focus();
  }

  const cb = function (o) {
    console.log(window.localStorage.getItem("code_challenge"));
    if (o.results && o.results.spotify_client_id && o.results.redirect) {
      var spotify_client_id = o.results.spotify_client_id;
      var redirect = encodeURIComponent(o.results.redirect);
      var URI = "https://accounts.spotify.com/authorize/?";
      URI += "client_id=" + spotify_client_id;
      URI += "&response_type=code";
      URI += "&redirect_uri=" + redirect;
      URI +=
        "&scope=playlist-read-private%20playlist-read-collaborative%20playlist-modify-public%20";
      URI +=
        "playlist-modify-private%20user-library-read%20user-library-modify%20user-read-private%20";
      URI += "streaming%20user-read-email%20";
      URI += "user-follow-modify%20user-follow-read";
      URI += "&code_challenge_method=S256";
      URI += "&code_challenge=" + code_challenge;
      URI += "&state=" + W.system.client_id;
      window.open(URI, where);
    } else window.open("spotify_error.html", where);
  };

  // We don't use W.system.get_jsonStr here, because this function may be called from
  // a window that doesn't import system.js
  var jsonStr = {};
  jsonStr.cmd = "spotify.auth";
  jsonStr.args = {};
  jsonStr.args.client_id = W.system.client_id;
  jsonStr.args.code_verifier = code_verifier;
  W.util.JSONpost("/json", jsonStr, cb);
};

"use strict";
W.spotify = {};

window.addEventListener("message", function (event) {
  const data = event.data;

  if (data.spotify_code && data.uuid) {
    console.log("Received Spotify code via postMessage");

    const query = new URLSearchParams({
      code: data.spotify_code,
      state: data.uuid
    });

    fetch(`/spotify_auth?${query}`)
      .then(r => r.text())
      .then((html) => {
        console.log("Spotify linking completed.");
        // Optional: show feedback in the UI
      })
      .catch(err => {
        console.error("Failed to send Spotify code to backend:", err);
      });
  }
});

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

W.spotify.auth = async function () {
  const code_verifier = generateCodeVerifier(128);
  const code_challenge = await generateCodeChallenge(code_verifier);

  const cb = function (o) {
    if (o.results && o.results.spotify_client_id) {
      const spotify_client_id = o.results.spotify_client_id;
      const redirect = encodeURIComponent("https://relevitt.github.io/dbmp/spotify_redirect.html");
      const params = new URLSearchParams({
        client_id: spotify_client_id,
        response_type: "code",
        redirect_uri: "https://relevitt.github.io/dbmp/spotify_redirect.html",
        scope: "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-library-read user-library-modify user-read-private streaming user-read-email user-follow-modify user-follow-read",
        code_challenge_method: "S256",
        code_challenge: code_challenge,
        state: W.system.client_id
      });

      // Open the Spotify auth window (which will redirect to your GitHub page)
      const popup = window.open(`https://accounts.spotify.com/authorize?${params}`, "spotify_auth_popup");
      if (popup) popup.focus();
    } else {
      window.open("spotify_error.html", "spotify_auth_popup");
    }
  };

  // Request Spotify client ID + redirect URI from backend
  const jsonStr = {
    cmd: "spotify.auth",
    args: {
      client_id: W.system.client_id,
      code_verifier: code_verifier
    }
  };
  W.util.JSONpost("/json", jsonStr, cb);
};

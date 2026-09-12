"use strict";
const payload = JSON.parse(document.body.dataset.login);
if (window.opener) {
  window.opener.postMessage({type: "slicer-link-login", ...payload}, location.origin);
  document.querySelector("p").textContent = "Connected. You can close this window.";
  window.close();
} else {
  document.querySelector("p").textContent = "Return to Slicer Link and connect again. Keep its sign-in window open.";
}

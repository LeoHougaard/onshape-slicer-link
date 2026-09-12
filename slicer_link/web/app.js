"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("slicer-link-session") || "";
let catalog = null, loginWindow = null, loginNonce = "", activeJob = null, timer = null;
const params = new URLSearchParams(location.search);
const context = {
  document_id: params.get("documentId"), workspace_id: params.get("workspaceId"),
  element_id: params.get("elementId"), configuration: params.get("configuration") || ""
};
const validContext = (!params.has("workspaceType") || params.get("workspaceType") === "w") && [context.document_id, context.workspace_id, context.element_id].every(v => /^[a-f0-9]{24}$/.test(v || ""));
const pairCode = location.pathname === "/pair" ? location.hash.slice(1) : "";
if (pairCode) history.replaceState(null, "", location.pathname);

function notice(message = "") { $("notice").textContent = message; $("notice").hidden = !message; }
async function api(path, body, method = body === undefined ? "GET" : "POST") {
  const response = await fetch(path, {method, headers: {"Content-Type": "application/json", ...(token ? {Authorization: `Bearer ${token}`} : {})}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const result = await response.json();
  if (response.status === 401) {
    token = ""; sessionStorage.removeItem("slicer-link-session");
    $("connected").hidden = true; $("welcome").hidden = false;
  }
  if (!response.ok) throw new Error(result.error || (typeof result.detail === "string" ? result.detail : "The request could not be completed."));
  return result;
}
function action(id, fn) {
  $(id).addEventListener("click", async () => {
    $(id).disabled = true; notice();
    try { await fn(); } catch (error) { notice(error.message); }
    finally { $(id).disabled = false; enableRefresh(); }
  });
}
function selected() { return [...document.querySelectorAll("#links input:checked")].map(item => item.value); }
function enableRefresh() { $("refresh").disabled = !selected().length || !$("devices").value || !!activeJob; }
function removeButton(label, fn) {
  const button = document.createElement("button"); button.className = "text remove"; button.textContent = "Remove";
  button.setAttribute("aria-label", `Remove ${label}`);
  button.onclick = async () => { try { await fn(); await state(); } catch (error) { notice(error.message); } };
  return button;
}
async function state() {
  const data = await api("/api/state");
  $("welcome").hidden = true; $("connected").hidden = false;
  $("pairing").hidden = !pairCode; $("workspace").hidden = !!pairCode;
  $("choose").disabled = !validContext; $("context-help").hidden = validContext;
  const checked = new Set(selected()), priorDevice = $("devices").value;
  $("links").replaceChildren();
  for (const link of data.links) {
    const row = document.createElement("li"); row.className = "part";
    const input = document.createElement("input"); input.type = "checkbox"; input.id = `link-${link.id}`;
    input.value = link.id; input.checked = !checked.size || checked.has(link.id); input.onchange = enableRefresh;
    const label = document.createElement("label"); label.htmlFor = input.id; label.textContent = link.name;
    const detail = document.createElement("small"); detail.textContent = link.source.configuration || "Default configuration"; label.append(document.createTextNode(" "), detail);
    row.append(input, label, removeButton(link.name, () => api(`/api/links/${link.id}`, undefined, "DELETE")));
    $("links").append(row);
  }
  $("empty").hidden = !!data.links.length;
  $("devices").replaceChildren(); $("computers").replaceChildren();
  if (!data.devices.length) $("devices").append(new Option("Pair a computer first", ""));
  for (const computer of data.devices) {
    $("devices").append(new Option(computer.name, computer.id));
    const row = document.createElement("li"); row.append(document.createTextNode(`${computer.name} `),
      removeButton(computer.name, () => api(`/api/devices/${computer.id}`, undefined, "DELETE")));
    $("computers").append(row);
  }
  if (data.devices.some(d => d.id === priorDevice)) $("devices").value = priorDevice;
  $("setup-help").hidden = !!data.devices.length;
  const successful = data.usage.reduce((sum, day) => sum + day.successful, 0);
  $("usage").textContent = `${successful} successful Onshape API requests recorded by this installation.`;
  enableRefresh();
}
action("connect", async () => {
  // Open synchronously so browsers permit the OAuth popup from an iframe.
  loginWindow = window.open("about:blank", "slicer-link-auth", "popup,width=620,height=760");
  if (!loginWindow) throw new Error("Allow the sign-in popup, then connect again.");
  loginNonce = crypto.randomUUID().replaceAll("-", "") + crypto.randomUUID().replaceAll("-", "");
  try { loginWindow.location = (await api(`/auth/start?nonce=${loginNonce}`)).url; }
  catch (error) { loginWindow.close(); throw error; }
});
window.addEventListener("message", async event => {
  if (event.origin !== location.origin || event.source !== loginWindow || event.data?.type !== "slicer-link-login" || event.data.nonce !== loginNonce) return;
  try {
    token = (await api("/api/session", {code: event.data.code, nonce: loginNonce})).token;
    sessionStorage.setItem("slicer-link-session", token); loginNonce = "";
    await state(); notice();
  } catch (error) { notice(error.message); }
});
action("claim", async () => {
  const computer = await api("/api/devices/claim", {code: pairCode});
  $("claim").hidden = true; notice(`${computer.name} is connected. Return to the helper to finish setup.`);
});
action("choose", async () => {
  catalog = await api("/api/selection", context); $("parts").replaceChildren();
  for (const part of catalog.parts) $("parts").append(new Option(part.name, part.id));
  $("catalog").hidden = false; $("add").disabled = !catalog.parts.length;
  if (!catalog.parts.length) notice("There are no solid parts in this Part Studio configuration.");
});
action("add", async () => {
  await api("/api/links", {selection: catalog.id, part_id: $("parts").value}); await state();
});
action("refresh", async () => {
  activeJob = (await api("/api/jobs", {device: $("devices").value, links: selected(), request_id: crypto.randomUUID().replaceAll("-", "")})).id;
  $("transfer").hidden = false; $("handoff").href = `onshape-slicer-link://job/${activeJob}`;
  $("handoff").hidden = false; $("check-job").hidden = true;
  $("job-status").textContent = "Preparing models. Open the helper to save them to your project folder.";
  watchJob(Date.now());
});
async function watchJob(started) {
  clearTimeout(timer);
  try {
    const job = await api(`/api/jobs/${activeJob}`);
    if (job.status === "failed") { activeJob = null; $("handoff").hidden = true; throw new Error(job.error); }
    if (job.status === "delivered") {
      $("job-status").textContent = job.changed ? `${job.changed} source ${job.changed === 1 ? "file" : "files"} updated. Select the objects in your slicer and use Reload from disk.` : "Files are ready. No file contents changed in this transfer. Reload in your slicer if needed.";
      activeJob = null; $("handoff").hidden = true; $("check-job").hidden = true; await state(); return;
    }
    if (job.status === "prepared") $("job-status").textContent = "Models prepared. Open the helper to save the files.";
    if (Date.now() - started < 180000) timer = setTimeout(() => watchJob(started), 2000);
    else { $("job-status").textContent = "Transfer is waiting. Open the helper, then check the transfer."; $("check-job").hidden = false; }
  } catch (error) { notice(error.message); $("check-job").hidden = !activeJob; }
  enableRefresh();
}
action("check-job", () => watchJob(Date.now()));
action("disconnect", async () => {
  await api("/api/session", undefined, "DELETE"); token = ""; sessionStorage.removeItem("slicer-link-session");
  clearTimeout(timer); activeJob = null; $("connected").hidden = true; $("welcome").hidden = false;
});
$("devices").onchange = enableRefresh;
if (validContext && params.get("server") === "https://cad.onshape.com" && window.parent !== window) {
  window.parent.postMessage({documentId: context.document_id, workspaceId: context.workspace_id,
    elementId: context.element_id, messageName: "applicationInit"}, "https://cad.onshape.com");
}
// Selection comes from a pinned catalog fetched on demand. Unsolicited browser
// selection messages never become a saved part identity.
if (token) state().catch(error => notice(error.message));

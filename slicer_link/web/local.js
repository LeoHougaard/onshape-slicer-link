"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("slicer-link-session") || "";
let catalog = null, busy = false, documentContext = {};
let setupFinished = false, editingSetup = false, wizardStep = null;
const selected = () => [...document.querySelectorAll("#links input:checked")].map(el => el.value);
function showSetup() {
  const guided = !setupFinished || editingSetup;
  $("setup-progress").hidden = !guided;
  $("setup-progress").textContent = `Step ${wizardStep} of 3`;
  $("setup-back").hidden = !guided || wizardStep === 1;
  $("setup-back").disabled = busy;
  $("change-setup").hidden = guided;
  $("change-setup").disabled = busy;
  $("slicer-step").hidden = !guided || wizardStep !== 1;
  $("document-step").hidden = !guided || wizardStep !== 2;
  $("parts-step").hidden = guided && wizardStep !== 3;
  $("parts-heading").textContent = guided ? "Choose a part" : "Your linked parts";
  $("add-parts-label").hidden = guided;
  if (guided) $("add-parts-options").open = true;
  $("daily-help").hidden = guided;
}
function notice(message = "") { $("notice").textContent = message; $("notice").hidden = !message; }
function enable() {
  $("send").disabled = busy || !$("slicer").value || !selected().length;
  $("reopen").disabled = $("send").disabled;
  $("project").disabled = busy || !$("slicer").value || !documentContext.document_id;
  for (const id of ["slicer", "document", "studios", "choose", "add", "save-path", "browse-path", "stop"]) $(id).disabled = busy;
  $("choose").disabled = busy || !$("studios").value;
  $("account-setup").disabled = busy;
  $("slicer-next").disabled = busy || !$("slicer").value;
  showSetup();
}
async function api(path, body, method = body === undefined ? "GET" : "POST") {
  const response = await fetch(path, {method, headers: {"Content-Type": "application/json", Authorization: `Bearer ${token}`},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || (typeof result.detail === "string" ? result.detail : "This request failed."));
  return result;
}
function action(id, fn) {
  $(id).addEventListener("click", async () => {
    if (busy) return;
    busy = true; notice(); enable();
    try { await fn(); } catch (error) { notice(error.message); }
    finally { busy = false; enable(); }
  });
}
async function state() {
  const [data, local] = await Promise.all([api("/api/state"), api("/api/local/state")]);
  const choice = $("slicer").value || local.slicer;
  $("slicer").replaceChildren(new Option("Choose your slicer", ""));
  for (const slicer of local.slicers) $("slicer").append(new Option(slicer.name, slicer.id));
  if (local.slicers.some(s => s.id === choice)) $("slicer").value = choice;
  documentContext = local.context;
  setupFinished = local.setup_complete;
  if (wizardStep === null) wizardStep = !$("slicer").value ? 1 : local.context.document_id ? 3 : 2;
  $("project-name").textContent = local.project.path || "No saved project connected yet.";
  if (!$("studio-url").value && local.context.document_id) {
    const c = local.context;
    $("studio-url").value = `https://cad.onshape.com/documents/${c.document_id}/w/${c.workspace_id}/e/${c.element_id}` +
      (c.configuration ? `?configuration=${encodeURIComponent(c.configuration)}` : "");
  }
  $("document-details").hidden = !local.context.studios;
  $("studios").replaceChildren(new Option("Choose a Part Studio", ""));
  for (const studio of local.context.studios || []) $("studios").append(new Option(studio.name, studio.id));
  $("studios").value = local.context.element_id || "";
  $("document-link").textContent = local.context.name || "Open document in Onshape";
  if (local.context.document_id) $("document-link").href = `https://cad.onshape.com/documents/${local.context.document_id}/w/${local.context.workspace_id}`;
  const checked = new Set(selected());
  $("links").replaceChildren();
  for (const link of data.links) {
    if (documentContext.document_id && (link.source.document_id !== documentContext.document_id || link.source.workspace_id !== documentContext.workspace_id)) continue;
    const row = document.createElement("li"); row.className = "part";
    const input = document.createElement("input"); input.type = "checkbox"; input.id = `part-${link.id}`; input.value = link.id;
    input.checked = !checked.size || checked.has(link.id); input.onchange = enable;
    const label = document.createElement("label"); label.htmlFor = input.id; label.textContent = link.name;
    const detail = document.createElement("small"); detail.textContent = link.source.configuration || "Default configuration"; label.append(detail);
    const remove = document.createElement("button"); remove.className = "text remove"; remove.textContent = "Unlink";
    remove.onclick = async () => {
      if (busy) return;
      try { await api(`/api/links/${link.id}`, undefined, "DELETE"); await state(); } catch (e) { notice(e.message); }
    };
    row.append(input, label, remove); $("links").append(row);
  }
  $("empty").hidden = !!$("links").children.length;
  $("usage").textContent = `${data.usage.reduce((sum, day) => sum + day.successful, 0)} successful Onshape API requests recorded by this app.`;
  $("connecting").hidden = true; $("app").hidden = false; enable();
}
action("document", async () => {
  await api("/api/local/document", {url: $("studio-url").value.trim()});
  catalog = null; $("catalog").hidden = true; await state();
  wizardStep = 3;
  if (documentContext.element_id) await chooseParts();
});
async function chooseParts() {
  documentContext = await api("/api/local/studio", {id: $("studios").value});
  const c = documentContext;
  catalog = await api("/api/selection", {document_id: c.document_id, workspace_id: c.workspace_id, element_id: c.element_id, configuration: c.configuration || ""});
  $("parts").replaceChildren();
  for (const part of catalog.parts) $("parts").append(new Option(part.name, part.id));
  $("catalog").hidden = false;
  if (!catalog.parts.length) notice("This Part Studio has no supported solid parts.");
}
action("choose", chooseParts);
$("studios").onchange = () => { catalog = null; $("catalog").hidden = true; enable(); };
action("add", async () => {
  if (!catalog || !$("parts").value) throw new Error("Choose a solid part first.");
  await api("/api/links", {selection: catalog.id, part_id: $("parts").value}); await state();
});
action("save-path", async () => {
  await api("/api/local/slicer-path", {name: $("slicer-name").value, path: $("slicer-path").value.trim()}); await state();
  const target = [...$("slicer").options].find(option => option.textContent === $("slicer-name").value);
  if (target) {
    $("slicer").value = target.value;
    await api("/api/local/slicer", {id: target.value});
    wizardStep = 2;
  }
});
action("browse-path", async () => {
  const result = await api("/api/local/browse-slicer", {});
  if (result.path) $("slicer-path").value = result.path;
});
action("project", async () => {
  const result = await api("/api/local/project", {id: $("slicer").value});
  if (!result.cancelled) { await state(); notice("Project connected. Click Send / Update to prepare its source files."); }
});
async function send(reopen) {
  const body = {slicer: $("slicer").value, links: selected(), reopen};
  const signature = JSON.stringify(body);
  let pending;
  try { pending = JSON.parse(sessionStorage.getItem("slicer-link-pending")); } catch (_) {}
  if (!pending || pending.signature !== signature) pending = {signature, id: crypto.randomUUID().replaceAll("-", "")};
  sessionStorage.setItem("slicer-link-pending", JSON.stringify(pending));
  $("status").textContent = "Checking Onshape and sending your parts...";
  const result = await api("/api/local/send", {...body, request_id: pending.id});
  sessionStorage.removeItem("slicer-link-pending");
  if (result.status === "failed") { $("status").textContent = "Send did not finish."; throw new Error(result.error); }
  const messages = [];
  if (result.opened) messages.push(`Sent ${result.opened} ${result.opened === 1 ? "part" : "parts"} to ${result.slicer}. Finish any import prompt in the slicer.`);
  if (result.reload.length) messages.push(`Use Reload from disk in ${result.slicer} for: ${result.reload.join(", ")}.`);
  if (result.uncertain.length) messages.push(`An earlier launch was interrupted. Check ${result.slicer} for ${result.uncertain.join(", ")}. If missing, use Open selected parts again below.`);
  $("status").textContent = messages.join("\n");
  if (!result.uncertain.length) {
    editingSetup = false;
    $("add-parts-options").open = false;
  }
  await state();
}
action("send", () => send(false));
action("reopen", () => send(true));
action("connect", async () => {
  const popup = window.open("about:blank", "slicer-link-auth", "popup,width=620,height=760");
  if (!popup) throw new Error("Allow the sign-in popup, then reconnect.");
  try { popup.location = (await api(`/auth/start?nonce=${crypto.randomUUID().replaceAll("-", "")}`)).url; }
  catch (error) { popup.close(); throw error; }
});
action("stop", async () => {
  await api("/api/local/stop", {}); $("app").hidden = true;
  $("connecting").hidden = false; $("connecting").textContent = "Slicer Link stopped. Open its desktop shortcut to start it again.";
});
action("account-setup", async () => {
  await api("/api/local/setup", {});
  $("app").hidden = true;
  $("connecting").hidden = false;
  $("connecting").textContent = "Continue in the connection setup window. You can close this tab.";
});
$("setup-back").onclick = () => { if (!busy) { wizardStep = Math.max(1, wizardStep - 1); enable(); } };
$("slicer-next").onclick = () => { if (!busy && $("slicer").value) { wizardStep = 2; enable(); } };
$("change-setup").onclick = () => { if (!busy) { editingSetup = true; wizardStep = 1; enable(); } };
$("slicer").onchange = async () => {
  if (busy || !$("slicer").value) return;
  busy = true; notice();
  enable();
  try { await api("/api/local/slicer", {id: $("slicer").value}); await state(); wizardStep = 2; }
  catch (error) { notice(error.message); }
  finally { busy = false; enable(); }
};
(async () => {
  const hash = new URLSearchParams(location.hash.slice(1));
  if (hash.has("local-code")) {
    history.replaceState(null, "", location.pathname + location.search);
    token = (await api("/api/session", {code: hash.get("local-code"), nonce: hash.get("nonce")})).token;
    sessionStorage.setItem("slicer-link-session", token);
  }
  await state();
})().catch(error => { $("connecting").hidden = true; notice(error.message); });

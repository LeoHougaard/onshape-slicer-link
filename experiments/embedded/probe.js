"use strict";
const params = new URLSearchParams(location.search);
const context = {
  documentId: params.get("documentId"),
  workspaceId: params.get("workspaceId") || params.get("workspaceOrVersionId"),
  elementId: params.get("elementId"),
};
const source = params.get("server");
const valid = source === "https://cad.onshape.com" &&
  Object.values(context).every(value => /^[a-f0-9]{24}$/.test(value || "")) &&
  !params.get("versionId") && (!params.has("workspaceOrVersion") || params.get("workspaceOrVersion") === "w");
const rows = document.getElementById("context");
const selected = new Map();
for (const [label, value] of Object.entries(context)) {
  if (!value) continue;
  const title = document.createElement("dt"), detail = document.createElement("dd");
  title.textContent = label; detail.textContent = value; rows.append(title, detail);
}
document.getElementById("connection").textContent = valid ? "Onshape context received" : "Open from Onshape";
document.getElementById("heading").textContent = valid ? "Connected to this document" : "Local connection is running";
document.getElementById("description").textContent = valid
  ? "Onshape supplied this workspace automatically. No document link needs to be pasted."
  : "Open Slicer Link from your Onshape document to check embedded access.";
window.addEventListener("message", event => {
  if (!valid || event.origin !== source || event.source !== window.parent) return;
  document.documentElement.dataset.onshapeMessageReceived = "true";
  const item = event.data;
  if (item?.messageName !== "itemSelectedInSelectItemDialog") return;
  const id = value => typeof value === "string" && /^[a-f0-9]{24}$/.test(value);
  if (![item.documentId, item.workspaceId, item.elementId, item.documentMicroversionId].every(id) ||
      item.versionId || typeof item.idTag !== "string" || !item.idTag ||
      typeof item.partName !== "string" || item.isSurface || item.isSketch || item.isComposite) {
    document.getElementById("selection-status").textContent = "Select a solid part from an editable workspace.";
    return;
  }
  const record = {
    documentId: item.documentId, workspaceId: item.workspaceId, elementId: item.elementId,
    microversionId: item.documentMicroversionId, partId: item.idTag,
    configuration: item.elementConfiguration || "", name: item.partName,
    studioName: item.elementName || "Part Studio"
  };
  const key = JSON.stringify([record.documentId, record.workspaceId, record.elementId, record.partId, record.configuration]);
  selected.set(key, record);
  const list = document.getElementById("parts"); list.replaceChildren();
  for (const part of selected.values()) {
    const row = document.createElement("li"); row.textContent = part.name;
    const detail = document.createElement("small");
    detail.textContent = `${part.studioName} · ${part.configuration || "Default configuration"} · CAD snapshot ${part.microversionId}`;
    row.append(detail); list.append(row);
  }
  document.getElementById("selection-status").textContent = `${selected.size} parts selected. Choose your slicer, then Add to slicer.`;
  document.getElementById("add").disabled = false;
  document.querySelector("details").open = true;
  // Non-secret CAD selection evidence for the UI test; no browser credentials.
  window.slicerLinkSelectionEvidence = Array.from(selected.values());
});
document.getElementById("choose").disabled = !valid;
document.getElementById("choose").onclick = () => {
  if (!valid) return;
  window.parent.postMessage({messageName: "openSelectItemDialog", ...context,
    dialogTitle: "Choose parts for your slicer", selectParts: true, selectMultiple: true,
    showBrowseDocuments: true, showStandardContent: false}, source);
};
if (valid && window.parent !== window) {
  window.parent.postMessage({messageName: "applicationInit", ...context}, source);
}
document.getElementById("open-desktop").onclick = () => {
  const kind = document.getElementById("slicer").value;
  const frame = document.getElementById("desktop");
  frame.src = `/desktop/${kind}/`;
  frame.hidden = false;
  document.getElementById("desktop-status").textContent = "Dedicated local session. Updates are not connected yet.";
};

let pendingImport = null;
document.getElementById("add").onclick = async () => {
  if (!valid || !selected.size) return;
  const kind = document.getElementById("slicer").value;
  const controls = ["add", "choose", "slicer", "open-desktop"].map(id => document.getElementById(id));
  controls.forEach(control => { control.disabled = true; });
  const status = document.getElementById("desktop-status");
  const frame = document.getElementById("desktop");
  frame.style.pointerEvents = "none";
  status.textContent = "Exporting the selected CAD snapshot and adding it to the slicer. Saving a recovery copy and checking the result…";
  // A retry uses the same id, so a dropped HTTP reply cannot duplicate an import.
  pendingImport ||= {kind, selections: Array.from(selected.values()), request_id: crypto.randomUUID().replaceAll("-", "")};
  try {
    const session = await (await fetch("/api/session")).json();
    const response = await fetch(`/api/${pendingImport.kind}/add`, {method: "POST",
      headers: {"Content-Type": "application/json", "X-OSL-Session": session.session},
      body: JSON.stringify({selections: pendingImport.selections, request_id: pendingImport.request_id})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The import stopped.");
    const receipts = document.getElementById("receipts"); receipts.replaceChildren();
    for (const object of result.objects) {
      const row = document.createElement("li");
      row.textContent = `${object.name} · Plate ${object.plates.join(", ")} · Verified CAD snapshot ${object.revision} · ${object.configuration || "Default configuration"}`;
      receipts.append(row);
    }
    status.textContent = `${result.objects.length} parts added and verified in ${kind === "orca" ? "OrcaSlicer" : "Bambu Studio"}. Updates are not connected yet.`;
    window.slicerLinkImportEvidence = result;
    selected.clear(); document.getElementById("parts").replaceChildren();
    pendingImport = null;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    controls.forEach(control => { control.disabled = false; });
    document.getElementById("add").disabled = !selected.size;
    frame.style.pointerEvents = "";
  }
};

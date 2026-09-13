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
  document.getElementById("selection-status").textContent = `${selected.size} source selections received from Onshape. Slicer import is not connected yet.`;
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

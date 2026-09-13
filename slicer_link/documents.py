"""Resolve user-pasted Onshape document links without fetching arbitrary URLs."""

import re
from urllib.parse import parse_qs, urlsplit

from .model import object_id, require


def resolve(client, address):
    parsed = urlsplit(address.strip())
    require(
        parsed.scheme == "https" and parsed.netloc == "cad.onshape.com",
        "Paste an Onshape document link from cad.onshape.com.",
    )
    match = re.fullmatch(
        r"/documents/([a-f0-9]{24})(?:/w/([a-f0-9]{24})(?:/e/([a-f0-9]{24}))?)?/?", parsed.path
    )
    require(match, "Use a document or Part Studio link in an editable workspace, not a saved version.")
    document, workspace, element = match.groups()
    info = client.request(f"/api/v16/documents/{document}")
    require(isinstance(info, dict), "Onshape did not return this document.")
    workspace = object_id(workspace or (info.get("defaultWorkspace") or {}).get("id"))
    tabs = client.request(f"/api/v16/documents/d/{document}/w/{workspace}/elements")
    require(isinstance(tabs, list), "Onshape did not return the document's tabs.")
    studios = [
        {"id": object_id(tab["id"]), "name": str(tab.get("name", "Part Studio"))[:200]}
        for tab in tabs
        if tab.get("elementType") == "PARTSTUDIO"
    ]
    require(studios, "This document has no Part Studios. Choose a document with solid parts.")
    selected = element if any(tab["id"] == element for tab in studios) else ""
    if not selected and len(studios) == 1:
        selected = studios[0]["id"]
    return {
        "document_id": document,
        "workspace_id": workspace,
        "element_id": selected,
        "configuration": parse_qs(parsed.query).get("configuration", [""])[0] if selected == element else "",
        "name": str(info.get("name", "Onshape document"))[:200],
        "studios": studios,
    }

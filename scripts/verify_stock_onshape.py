"""Read-only verification against the previously authorized replacement test account.

Uses the existing Windows-encrypted development grant. Never logs credentials or
edits CAD. Does not register an application or authorize an additional account.
"""

import json
import time
import uuid
from pathlib import Path

from cryptography.fernet import Fernet

from companion.auth_probe import protect, read_config
from companion.export_part import decode_source
from slicer_link.auth import token_request
from slicer_link.files import atomic_write
from slicer_link.model import Source, link_filename, require
from slicer_link.onshape import Client, Exporter
from slicer_link.store import Store

ROOT = Path(__file__).resolve().parents[1]


def main():
    evidence = json.loads((ROOT / "artifacts/onshape/auth-results.json").read_text())
    require(
        evidence.get("account_context", "").startswith("Replacement test application; previous credentials"),
        "Only the user-confirmed replacement test account may be used.",
    )
    client_id, client_secret, base = read_config(ROOT / ".env")
    token_file = ROOT / "artifacts/onshape/tokens.dpapi"
    stored = json.loads(protect(token_file.read_bytes(), decrypt=True))
    require(
        stored["client_id"] == client_id and stored["base_url"] == base == "https://cad.onshape.com",
        "The test application and stored grant do not match.",
    )
    if stored["expires_at"] <= time.time() + 120:
        tokens = token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": stored["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        stored.update(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=time.time() + tokens["expires_in"],
        )
        atomic_write(token_file, protect(json.dumps(stored).encode()))
    statuses = []
    client = Client(stored["access_token"], statuses.append)
    info = client.request("/api/v16/users/sessioninfo")
    owner = info.get("id") or info.get("userId")
    require(
        isinstance(owner, str) and len(owner) == 24, "Session identity did not match the new OAuth parser."
    )
    old = decode_source(json.loads((ROOT / "artifacts/onshape/linked-part/current.json").read_text()))
    source = Source(
        old["document_id"],
        old["workspace_id"],
        old["element_id"],
        old["initial_microversion"],
        old["initial_part_id"],
        old["configuration"],
    )
    folder = ROOT / "artifacts/stock/onshape" / uuid.uuid4().hex
    store = Store(folder, Fernet.generate_key())
    try:
        identity = uuid.uuid4().hex
        link = {
            "id": identity,
            "name": "Test part",
            "filename": link_filename("Test part", identity),
            "source": source.to_dict(),
        }
        statuses.clear()
        exporter = Exporter(store)
        first = exporter.refresh(owner, client, [link])
        initial_statuses = statuses[:]
        statuses.clear()
        second = Exporter(store).refresh(owner, client, [link])
        require(first == second and statuses == [200], "Unchanged refresh did not use the persistent cache.")
        result = {
            "status": "passed",
            "account": "user-confirmed replacement test account",
            "session_identity_parser": True,
            "first_refresh_http_statuses": initial_statuses,
            "unchanged_refresh_http_statuses": statuses,
            "bounds_mm": first[0]["bounds_mm"],
            "cad_edits": 0,
            "hosted_oauth_flow_verified": False,
        }
        atomic_write(
            ROOT / "artifacts/stock/onshape/live-results.json", json.dumps(result, indent=2).encode()
        )
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()

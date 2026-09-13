"""One-time migration of the already authorized replacement test account.

The packaged app then runs independently of this checkout and its old test grant.
"""

import json
import secrets
import shutil
from pathlib import Path

from companion.auth_probe import protect, read_config
from companion.export_part import decode_source
from slicer_link import platforms
from slicer_link.local import configuration
from slicer_link.model import require
from slicer_link.store import Store

ROOT = Path(__file__).resolve().parents[1]


def main():
    if configuration():
        print("Local application is already configured. No credentials were replaced.")
        return
    evidence = json.loads((ROOT / "artifacts/onshape/auth-results.json").read_text())
    require(
        evidence.get("account_context", "").startswith("Replacement test application; previous credentials"),
        "Only the confirmed replacement account may be migrated.",
    )
    client_id, client_secret, base = read_config(ROOT / ".env")
    stored = json.loads(protect((ROOT / "artifacts/onshape/tokens.dpapi").read_bytes(), decrypt=True))
    require(
        stored["client_id"] == client_id and stored["base_url"] == base == "https://cad.onshape.com",
        "The application and stored grant do not match.",
    )
    old_root = ROOT / "artifacts/local-test"
    key = protect((old_root / "key.dpapi").read_bytes(), decrypt=True)
    old = Store(old_root / "service", key)
    try:
        identity = old.get("local", "identity")
        require(identity and identity["client_id"] == client_id, "The local test account is not verified.")
        owner = identity["owner"]
        folder = platforms.config_dir() / "local/service"
        require(
            not (folder / "app.sqlite3").exists(),
            "Local application data already exists; keep it for migration review.",
        )
        new = Store(folder, key)
        try:
            old.db.backup(new.db)
            if (old.root / "meshes").exists():
                shutil.copytree(old.root / "meshes", new.root / "meshes", dirs_exist_ok=True)
            new.put(
                "account",
                owner,
                owner,
                {
                    "id": owner,
                    "tokens": new.encrypt(
                        {k: stored[k] for k in ("access_token", "refresh_token", "expires_at")}
                    ),
                },
            )
            source = decode_source(
                json.loads((ROOT / "artifacts/onshape/linked-part/current.json").read_text())
            )
            new.put(
                "local-context",
                owner,
                owner,
                {k: source[k] for k in ("document_id", "workspace_id", "element_id", "configuration")},
            )
            for kind in ("session", "oauth", "login", "device", "computer", "pair"):
                for row in new.db.execute("SELECT id FROM records WHERE kind=?", (kind,)).fetchall():
                    new.delete(kind, row[0])
        finally:
            new.close()
        configuration(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "key": key.decode(),
                "owner": owner,
                "control": secrets.token_urlsafe(32),
            }
        )
        print("Replacement test account, links, and export cache migrated to the local application.")
    finally:
        old.close()


if __name__ == "__main__":
    main()

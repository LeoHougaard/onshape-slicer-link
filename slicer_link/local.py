"""Packaged local application: one process, native credential storage, browser UI."""

import argparse
import json
import logging
import secrets
import socket
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from cryptography.fernet import Fernet

from . import __version__, platforms
from .auth import Auth
from .helper import Remote
from .local_service import create_local_app, login_address
from .model import LinkError, require
from .service import Settings
from .store import Store

ORIGIN = "http://localhost:8767"
VAULT = "local-application-settings-v1"


def configuration(value=None):
    if value is not None:
        platforms.secret(VAULT, json.dumps(value))
        return value
    saved = platforms.secret(VAULT)
    return json.loads(saved) if saved else None


def setup():
    """One-time OAuth application credentials, kept in the native password store."""
    import tkinter as tk
    from tkinter import ttk

    result = []
    root = tk.Tk()
    root.title("Connect local Slicer Link")
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Connect to Onshape", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(
        frame,
        wraplength=510,
        text=(
            "Create a private Connected Desktop App in Onshape's Developer settings. "
            "Enable only Read documents. Use this redirect URL:\n\n" + ORIGIN + "/auth/callback\n\n"
            "Paste its client ID and secret below. They stay in your computer's password store. "
            "No server, domain, or paid hosting is needed."
        ),
    ).pack(pady=16)
    ttk.Button(
        frame,
        text="Open Onshape Developer settings",
        command=lambda: webbrowser.open("https://cad.onshape.com/user/settings"),
    ).pack(anchor="w")
    client_id, client_secret = tk.StringVar(), tk.StringVar()
    for label, variable, masked in [("Client ID", client_id, False), ("Client secret", client_secret, True)]:
        ttk.Label(frame, text=label).pack(anchor="w", pady=(12, 4))
        ttk.Entry(frame, textvariable=variable, show="*" if masked else "", width=65).pack(fill="x")
    message = tk.StringVar()
    ttk.Label(frame, textvariable=message, wraplength=510).pack(pady=10)

    def save():
        if not client_id.get().strip() or not client_secret.get().strip():
            message.set("Enter both values from your private Onshape application.")
            return
        value = {
            "client_id": client_id.get().strip(),
            "client_secret": client_secret.get().strip(),
            "key": Fernet.generate_key().decode(),
            "owner": "",
            "control": secrets.token_urlsafe(32),
        }
        try:
            configuration(value)
        except LinkError as error:
            message.set(str(error))
            return
        result.append(value)
        root.destroy()

    ttk.Button(frame, text="Save and sign in", command=save).pack(anchor="w")
    root.mainloop()
    return result[0] if result else None


def run():
    config = configuration() or setup()
    if not config:
        return
    listener = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", 8767))
        listener.listen()
    except OSError:
        listener.close()
        # Reopening the desktop shortcut reuses the existing local process.
        Remote(ORIGIN, config["control"], development=True).request("/api/local/open", {})
        return
    directory = platforms.config_dir() / "local"
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=directory / "app.log", level=logging.WARNING)
    store = Store(directory / "service", config["key"])
    auth = Auth(store, config["client_id"], config["client_secret"], ORIGIN)

    def open_app():
        if config.get("owner") and store.get("account", config["owner"]):
            webbrowser.open(login_address(store, config["owner"], ORIGIN))
        else:
            webbrowser.open(auth.begin(secrets.token_urlsafe(32)))

    def connected(owner):
        config["owner"] = owner
        configuration(config)

    app = create_local_app(
        Settings(ORIGIN, str(store.root), config["key"], development=True),
        store,
        auth,
        directory / "models",
        stop=lambda: setattr(server, "should_exit", True),
        reopen=open_app,
        control_token=config["control"],
        connected=connected,
    )
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False, proxy_headers=False))

    def startup():
        for _ in range(200):
            if server.started:
                open_app()
                return
            time.sleep(0.1)

    threading.Thread(target=startup, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--pick-slicer", help=argparse.SUPPRESS)
    parser.add_argument(
        "--pick-kind", choices=["slicer", "project"], default="slicer", help=argparse.SUPPRESS
    )
    args = parser.parse_args()
    try:
        if args.pick_slicer:
            import tkinter as tk
            from tkinter import filedialog

            path = Path(args.pick_slicer)
            require(
                path.resolve().parent == (platforms.config_dir() / "local").resolve()
                and path.name.startswith(".picker-")
                and path.is_file()
                and not path.is_symlink(),
                "Invalid file picker request.",
            )
            root = tk.Tk()
            root.withdraw()
            options = {"parent": root, "title": "Choose OrcaSlicer or Bambu Studio"}
            if args.pick_kind == "project":
                options.update(
                    title="Connect your saved slicer project", filetypes=[("Slicer project", "*.3mf")]
                )
            selected = filedialog.askopenfilename(**options)
            path.write_text(json.dumps(selected), encoding="utf-8")
            root.destroy()
            return
        run()
    except (LinkError, OSError, ValueError) as error:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Slicer Link", str(error), parent=root)
        root.destroy()


if __name__ == "__main__":
    main()

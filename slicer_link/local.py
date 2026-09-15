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


def setup(existing=None):
    from .setup import setup as wizard

    return wizard(configuration, existing=existing)


def local_listener(config, reconfigure):
    listener = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", 8767))
        listener.listen()
    except OSError:
        listener.close()
        require(config, "Another application is using Slicer Link's local address. Close it and retry.")
        remote = Remote(ORIGIN, config["control"], development=True)
        if not reconfigure:
            remote.request("/api/local/open", {})
            return None
        remote.request("/api/local/exit", {})
        for _ in range(100):
            listener = socket.socket()
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind(("127.0.0.1", 8767))
                listener.listen()
                return listener
            except OSError:
                listener.close()
                time.sleep(0.1)
        raise LinkError("Slicer Link is still closing. Open connection setup again in a moment.")
    return listener


def run(*, reconfigure=False):
    config = configuration()
    listener = local_listener(config, reconfigure)
    if listener is None:
        return
    try:
        if reconfigure or not config:
            config = setup(config)
        if not config:
            listener.close()
            return
    except BaseException:
        listener.close()
        raise
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
    server = uvicorn.Server(
        uvicorn.Config(app, log_config=None, access_log=False, proxy_headers=False, ws="none")
    )

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
    parser.add_argument("--setup", action="store_true", help="Open the guided Onshape connection setup.")
    parser.add_argument("--install-shortcut", action="store_true", help=argparse.SUPPRESS)
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
        if args.install_shortcut:
            platforms.register_local_shortcut()
        run(reconfigure=args.setup)
    except (LinkError, OSError, ValueError) as error:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Slicer Link", str(error), parent=root)
        root.destroy()


if __name__ == "__main__":
    main()

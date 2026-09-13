"""Small on-demand desktop helper. GUI, credential storage, and ordinary STL files."""

import argparse
import json
import logging
import queue
import re
import socket
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from . import __version__, platforms
from .files import Library
from .model import MAX_MESH_BYTES, LinkError, canonical, require, service_origin
from .onshape import NoRedirect


def handoff_id(uri):
    parsed = urlsplit(uri)
    require(
        parsed.scheme == "onshape-slicer-link"
        and parsed.netloc == "job"
        and re.fullmatch(r"/[a-f0-9]{32}", parsed.path)
        and not parsed.query
        and not parsed.fragment,
        "This Slicer Link address is invalid. Start a refresh from Onshape again.",
    )
    return parsed.path[1:]


class Remote:
    def __init__(self, origin, token="", *, development=False):
        self.origin = service_origin(origin, development=development)
        self.token = token
        handlers = [NoRedirect]
        if urlsplit(self.origin).hostname in {"localhost", "127.0.0.1"}:
            handlers.append(ProxyHandler({}))
        self.opener = build_opener(*handlers)

    def request(self, path, body=None, *, binary=False):
        require(path.startswith("/api/") or path == "/health", "Invalid application endpoint.")
        headers = {"Accept": "application/octet-stream" if binary else "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with self.opener.open(
                Request(
                    self.origin + path,
                    headers=headers,
                    data=None if body is None else canonical(body).encode(),
                ),
                timeout=45,
            ) as response:
                limit = MAX_MESH_BYTES if binary else 4 * 1024 * 1024
                data = response.read(limit + 1)
                require(len(data) <= limit, "The application returned too much data.")
                return data if binary else json.loads(data)
        except HTTPError as error:
            try:
                data = json.loads(error.read(8192))
                message = data.get("error") or data.get("detail")
            except (ValueError, OSError):
                message = None
            finally:
                error.close()
            raise LinkError(
                message
                if isinstance(message, str)
                else "The application rejected this request. Reconnect or try again."
            ) from None
        except (OSError, ValueError):
            raise LinkError("Cannot reach the application. Check your connection and try again.") from None


def transfer(
    remote,
    identity,
    folder,
    *,
    progress=lambda message: None,
    cancelled=lambda: False,
    wait=time.sleep,
    timeout=300,
):
    require(re.fullmatch(r"[a-f0-9]{32}", identity), "Invalid transfer identifier.")
    deadline = time.monotonic() + timeout
    while True:
        require(not cancelled(), "Transfer cancelled. Existing files were retained.")
        job = remote.request(f"/api/transfers/{identity}")
        require(job.get("id") == identity, "The application returned a different transfer.")
        if job["status"] == "failed":
            raise LinkError(job.get("error", "Onshape export failed."))
        if job["status"] in {"prepared", "delivered"}:
            break
        require(job["status"] == "preparing", "Unexpected transfer status. Update the helper.")
        require(time.monotonic() < deadline, "The export is still running. Retry this transfer in a moment.")
        progress("Waiting for Onshape to prepare the models…")
        wait(2)
    progress("Checking and saving source files…")
    library = Library(folder)

    def fetch(sha):
        require(not cancelled(), "Transfer cancelled. Existing files were retained.")
        return remote.request(f"/api/transfers/{identity}/meshes/{sha}", binary=True)

    result = library.apply(
        identity, job["links"], fetch, account=remote.origin + "/" + job["owner"], created=job["created"]
    )
    # A lost acknowledgement is safe to retry. The completed job is recorded
    # locally before contacting the service, and its geometry is not reapplied.
    try:
        remote.request(f"/api/transfers/{identity}/receipt", {"changed": result["changed"]})
        result["acknowledged"] = True
    except LinkError:
        result["acknowledged"] = False
    return result


class Window:
    def __init__(self, root, args):
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk, self.root, self.args = tk, ttk, root, args
        self.events = queue.Queue()
        self.busy = False
        self.config = platforms.read_config()
        self.job = handoff_id(args.uri) if args.uri else None
        self.stop = threading.Event()
        root.title("Onshape Slicer Link")
        root.geometry("600x540")
        root.minsize(520, 480)
        self.frame = ttk.Frame(root, padding=24)
        self.frame.pack(fill="both", expand=True)
        ttk.Label(self.frame, text="Slicer Link", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="")
        self.content = ttk.Frame(self.frame)
        self.content.pack(fill="both", expand=True, pady=16)
        ttk.Label(self.frame, textvariable=self.status, wraplength=535).pack(fill="x")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.drain)
        if self.config.get("origin"):
            self.home()
        else:
            self.setup()

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def button(self, text, command):
        def invoke():
            if not self.busy:
                try:
                    command()
                except (LinkError, OSError, ValueError) as error:
                    self.status.set(str(error))

        button = self.ttk.Button(self.content, text=text, command=invoke)
        button.pack(anchor="w", pady=5)
        return button

    def task(self, work, done=lambda result: None):
        if self.busy:
            return
        self.busy = True
        self.stop.clear()

        def run():
            try:
                result = work()
                self.events.put(("done", (done, result)))
            except Exception as error:
                logging.getLogger(__name__).exception("Helper operation failed")
                message = (
                    str(error)
                    if isinstance(error, LinkError)
                    else "This operation failed. Check the folder, network, and desktop password store, then retry."
                )
                self.events.put(("error", message))

        threading.Thread(target=run, daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status.set(value)
                elif kind == "done":
                    self.busy = False
                    callback, result = value
                    callback(result)
                else:
                    self.busy = False
                    self.status.set(value)
        except queue.Empty:
            pass
        self.root.after(100, self.drain)

    def text(self, text):
        self.ttk.Label(self.content, text=text, wraplength=530).pack(anchor="w", pady=(0, 12))

    def folder_field(self):
        from tkinter import filedialog

        self.folder = self.tk.StringVar(
            value=self.config.get("folder", str(Path.home() / "Documents" / "Slicer Link"))
        )
        self.ttk.Label(self.content, text="Project folder").pack(anchor="w")
        self.ttk.Entry(self.content, textvariable=self.folder).pack(fill="x", pady=5)

        def choose():
            path = filedialog.askdirectory(
                parent=self.root, title="Choose the folder containing your slicer project"
            )
            if path:
                self.folder.set(path)

        self.button("Choose folder…", choose)

    def setup(self):
        self.clear()
        self.text(
            "Connect this computer once. Models will be saved as ordinary STL files beside your slicer project."
        )
        self.ttk.Label(self.content, text="Application address").pack(anchor="w")
        default = self.config.get("origin") or self.args.service or bundled_origin()
        self.origin = self.tk.StringVar(value=default)
        self.ttk.Entry(self.content, textvariable=self.origin).pack(fill="x", pady=5)
        self.folder_field()
        self.button("Connect with Onshape", self.pair)
        self.text("Your Onshape password and API credentials stay out of this helper.")

    def pair(self):
        origin, folder = self.origin.get().strip(), self.folder.get().strip()
        self.status.set("Opening secure sign-in…")

        def work():
            remote = Remote(origin, development=self.args.development)
            require(
                remote.request("/health").get("protocol") == 1,
                "Update the helper to connect to this application.",
            )
            # Probe secure storage before issuing a device token.
            platforms.secret(remote.origin)
            pairing = remote.request("/api/devices", {"name": socket.gethostname()[:80] or "My computer"})
            parsed = urlsplit(pairing["url"])
            require(
                pairing["url"].startswith(remote.origin + "/pair#") and parsed.path == "/pair",
                "Unexpected pairing address.",
            )
            remote.token = pairing["token"]
            webbrowser.open(pairing["url"])
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline and not self.stop.is_set():
                self.events.put(
                    ("status", "Finish signing in and choose Pair this computer in your browser.")
                )
                device = remote.request("/api/device")
                if device.get("owner"):
                    platforms.register_protocol()
                    platforms.secret(remote.origin, pairing["token"])
                    config = {
                        "schema": 1,
                        "origin": remote.origin,
                        "folder": str(Path(folder).expanduser().resolve()),
                        "device": device["id"],
                        "slicers": platforms.slicers(),
                    }
                    platforms.save_config(config)
                    return config
                self.stop.wait(2)
            raise LinkError("Pairing expired. Connect again when you are ready.")

        def done(config):
            self.config = config
            self.status.set("Connected. Refresh a part from Slicer Link inside Onshape.")
            self.home()

        self.task(work, done)

    def home(self):
        self.clear()
        self.text(
            "Save your .3mf project in the same folder as its linked STL files. Your slicer uses these stable filenames when you reload."
        )
        self.folder_field()
        if self.job:
            self.button("Save refreshed files", self.save_transfer)
        else:
            self.text("Ready. Open Slicer Link in Onshape, refresh your parts, then choose Open helper.")
        self.button("Open project folder", self.open_folder)
        for name, command in self.config.get("slicers", {}).items():
            self.button("Open " + name, lambda command=command: platforms.launch(command))
        if not self.config.get("slicers"):
            self.button("Choose slicer executable…", self.choose_slicer)
        self.button("Restore previous geometry…", self.restore)
        self.button("Check connection", self.check)
        self.button("Connection setup…", self.setup)

    def chosen_folder(self):
        value = self.folder.get().strip()
        require(value, "Choose a project folder first.")
        return str(Path(value).expanduser().resolve())

    def choose_slicer(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self.root, title="Choose the official slicer executable or AppImage"
        )
        if path:
            require(Path(path).is_file(), "Choose an installed slicer executable.")
            self.config["slicers"] = {Path(path).stem: [str(Path(path).resolve())]}
            platforms.save_config(self.config)
            self.home()

    def remote(self):
        token = platforms.secret(self.config["origin"])
        require(token, "This computer is not paired. Open connection setup.")
        return Remote(self.config["origin"], token, development=self.args.development)

    def save_transfer(self):
        folder = self.chosen_folder()
        self.status.set("Starting transfer…")

        def work():
            result = transfer(
                self.remote(),
                self.job,
                folder,
                cancelled=self.stop.is_set,
                progress=lambda text: self.events.put(("status", text)),
                wait=self.stop.wait,
            )
            self.config["folder"] = folder
            platforms.save_config(self.config)
            return result

        def done(result):
            message = "Files ready. Select the objects in your slicer and use Reload from disk. For a new part, import its STL once."
            if not result["acknowledged"]:
                message += " The app could not confirm delivery. Retry to send the receipt; saved files will be kept."
            self.status.set(message)

        self.task(work, done)

    def open_folder(self):
        folder = Path(self.chosen_folder())
        folder.mkdir(parents=True, exist_ok=True)
        platforms.open_folder(folder)

    def check(self):
        self.task(
            lambda: self.remote().request("/api/device"),
            lambda value: self.status.set(
                "Connected to " + self.config["origin"]
                if value.get("owner")
                else "Complete pairing in your browser."
            ),
        )

    def restore(self):
        from tkinter import messagebox

        library = Library(self.chosen_folder())
        try:
            links = [link for link in library.manifest()["links"].values() if link.get("previous")]
        except (OSError, ValueError, LinkError) as error:
            self.status.set(str(error))
            return
        if not links:
            self.status.set("This folder has no previous downloaded geometry to restore.")
            return
        popup = self.tk.Toplevel(self.root)
        popup.title("Restore previous geometry")
        combo = self.ttk.Combobox(popup, state="readonly", values=[link["name"] for link in links], width=50)
        combo.pack(padx=20, pady=20)
        combo.current(0)

        def apply():
            item = links[combo.current()]
            if messagebox.askokcancel(
                "Restore geometry",
                f"Restore the previous downloaded STL for {item['name']}? Then use Reload from disk in your slicer.",
                parent=popup,
            ):
                popup.destroy()
                self.task(
                    lambda: library.restore(item["id"]),
                    lambda result: self.status.set(
                        "Previous file restored. Use Reload from disk in your slicer."
                    ),
                )

        self.ttk.Button(popup, text="Restore file", command=apply).pack(pady=(0, 20))

    def close(self):
        # Daemon work must not be cut off in the middle of writing files.
        if self.busy:
            self.stop.set()
            self.status.set("Finishing the current operation safely. Close again when it stops.")
        else:
            self.root.destroy()


def bundled_origin():
    path = Path(__file__).with_name("assets") / "service.json"
    return json.loads(path.read_text())["origin"] if path.exists() else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uri", nargs="?")
    parser.add_argument("--service", help="Application address for initial setup")
    parser.add_argument("--development", action="store_true", help="Allow loopback HTTP during development")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    try:
        Window(root, args)
        root.mainloop()
    except (LinkError, OSError, ValueError) as error:
        root.withdraw()
        messagebox.showerror("Slicer Link", str(error), parent=root)
        root.destroy()


if __name__ == "__main__":
    main()

"""Small native wizard. Credentials are saved only after the final step."""

import secrets
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from cryptography.fernet import Fernet

from . import __version__
from .model import LinkError

SETTINGS_URL = "https://cad.onshape.com/user/settings"
REDIRECT = "http://localhost:8767/auth/callback"
HELP_URL = "https://cad.onshape.com/help/Content/Plans/my_account_developer.htm"


class SetupWizard:
    def __init__(self, root, save, *, existing=None, open_url=webbrowser.open):
        self.root, self.save, self.open_url = root, save, open_url
        self.existing = existing or {}
        self.result = None
        self.step = 0
        self.reusing = bool(self.existing.get("client_id"))
        self.identifier = "com.onshapeslicerlink.local." + secrets.token_hex(6)
        self.client_id = tk.StringVar(root, self.existing.get("client_id", ""))
        self.client_secret = tk.StringVar(root, self.existing.get("client_secret", ""))
        self.message = tk.StringVar(root)
        root.title("Set up Slicer Link")
        scale = max(1, float(root.tk.call("tk", "scaling")) / (96 / 72))
        size = round(650 * scale)
        self.wraplength = round(510 * scale)
        root.geometry(f"{size}x{size}")
        root.minsize(size, size)
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        frame = ttk.Frame(root, padding=28)
        frame.pack(fill="both", expand=True)
        self.progress = ttk.Label(frame)
        self.progress.pack(anchor="w", pady=(0, 10))
        self.heading = ttk.Label(frame, font=("Segoe UI", 20, "bold"))
        self.heading.pack(anchor="w", pady=(0, 16))
        self.content = ttk.Frame(frame)
        navigation = ttk.Frame(frame)
        navigation.pack(side="bottom", fill="x")
        ttk.Label(frame, textvariable=self.message, wraplength=self.wraplength).pack(
            side="bottom", fill="x", pady=12
        )
        self.content.pack(fill="both", expand=True)
        self.back = ttk.Button(navigation, text="Back", command=self.previous)
        self.back.pack(side="left")
        self.next = ttk.Button(navigation, command=self.advance)
        self.next.pack(side="right")
        ttk.Button(
            navigation, text="Onshape's illustrated guide", command=lambda: self.open_url(HELP_URL)
        ).pack(side="left", padx=16)
        self.render()

    def text(self, value):
        ttk.Label(self.content, text=value, wraplength=self.wraplength, justify="left").pack(
            anchor="w", fill="x", pady=(0, 12)
        )

    def copy_field(self, label, value):
        ttk.Label(self.content, text=label).pack(anchor="w")
        row = ttk.Frame(self.content)
        row.pack(fill="x", pady=(3, 12))
        variable = tk.StringVar(self.root, value)
        entry = ttk.Entry(row, textvariable=variable, state="readonly")
        entry.variable = variable
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.message.set(f"Copied {label}. Paste it into Onshape.")

        ttk.Button(row, text="Copy", command=copy).pack(side="right")

    def input(self, label, variable, *, masked=False):
        ttk.Label(self.content, text=label).pack(anchor="w", pady=(4, 6))
        row = ttk.Frame(self.content)
        row.pack(fill="x", pady=(0, 10))
        entry = ttk.Entry(row, textvariable=variable, show="*" if masked else "")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="Paste", command=lambda: self.paste(variable)).pack(side="right")
        if masked:
            visible = tk.BooleanVar(self.root)
            ttk.Checkbutton(
                self.content,
                text="Show secret on this screen",
                variable=visible,
                command=lambda: entry.config(show="" if visible.get() else "*"),
            ).pack(anchor="w", pady=(0, 12))
        entry.bind("<Return>", lambda _event: self.advance())
        entry.selection_range(0, "end")
        entry.focus_set()

    def paste(self, variable):
        try:
            value = self.root.clipboard_get().strip()
        except tk.TclError:
            self.message.set("Nothing to paste. Copy the key in Onshape first, then click Paste here.")
            return
        if not value:
            self.message.set("Nothing to paste. Copy the key in Onshape first, then click Paste here.")
            return
        variable.set(value)
        self.message.set("Pasted. Click Next to continue." if self.step == 3 else "Pasted. Ready to sign in.")

    def secret_help(self):
        messagebox.showinfo(
            "Find your OAuth secret",
            "In Onshape, click your account icon at the top right, then My account.\n\n"
            "Choose Developer on the left, then OAuth applications. Open the connection you created "
            "for Slicer Link, usually My Slicer Link, and select Keys and secret.\n\n"
            "If you lost the secret, use the option there to regenerate it. This replaces the old secret "
            "for this connection, so update any other Slicer Link installation using it too.\n\n"
            "Copy the new OAuth secret key before closing Onshape's popup. Come back here and click Paste. "
            "Use the client ID from this same connection on the next screen.",
            parent=self.root,
        )

    def render(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.message.set("")
        step, total = (self.step - 1, 3) if self.reusing and self.step >= 3 else (self.step + 1, 5)
        self.progress.config(text=f"Connect Onshape · Step {step} of {total} · Version {__version__}")
        self.back.config(state="disabled" if self.step == 0 else "normal")
        titles = (
            "Open your Onshape settings",
            "Name your connection",
            "Allow read access",
            "Copy the secret",
            "Finish connecting",
        )
        self.heading.config(text=titles[self.step])
        self.next.config(text="Save and open Onshape" if self.step == 4 else "Next")
        if self.step == 0:
            self.text(
                "You'll use two windows: Onshape in your browser and this setup wizard. Keep both open."
            )
            ttk.Button(
                self.content, text="Open Onshape settings", command=lambda: self.open_url(SETTINGS_URL)
            ).pack(anchor="w", pady=(0, 16))
            self.text("1. Open settings above and sign in to your Onshape account.")
            self.text("2. Click Developer in the list on the left, then the OAuth applications tab.")
            self.text("3. Click Create new OAuth application. Leave that form open and click Next here.")
            self.text(
                "Use OAuth applications, not the separate API keys tab. This wizard needs an OAuth client ID and secret."
            )
            ttk.Button(
                self.content, text="Use an existing Onshape connection", command=self.use_existing
            ).pack(anchor="w")
        elif self.step == 1:
            self.text(
                "For each field: click Copy here, click the matching box in Onshape, and press Ctrl+V to paste."
            )
            self.copy_field("Name", "My Slicer Link")
            self.copy_field("Primary format", self.identifier)
            self.copy_field("Summary", "Send my Onshape parts to my slicer.")
            self.text("Keep the Onshape form open. Click Next here to finish its settings.")
        elif self.step == 2:
            self.text(
                "In the same Onshape form, set Type to Connected Desktop App. This lets the connection run on your computer."
            )
            self.copy_field("Redirect URLs", REDIRECT)
            self.text("Leave OAuth URL blank.")
            self.text("Under Permissions, check only Application can read your documents.")
            self.text(
                "Click Create application in Onshape. Keep the popup with the secret key open, then click Next here."
            )
        elif self.step == 3:
            if self.reusing:
                self.text(
                    "In Onshape, open My account > Developer > OAuth applications. "
                    "Open the connection you want to use, then select Keys and secret."
                )
            self.text(
                "Your saved secret is filled in. Keep it, or click Paste to replace it with the OAuth secret from Onshape."
                if self.reusing and self.existing.get("client_id")
                else "Paste the secret you copied when creating this connection. If you lost it, use the help below."
                if self.reusing
                else "In Onshape's popup, copy the value labelled OAuth secret key. Return here and click Paste below."
            )
            self.input("OAuth secret key / Client secret", self.client_secret, masked=True)
            self.text(
                "Onshape shows this secret only once. Copy the value itself, without its label. The other key, the client ID, goes on the next screen."
            )
            self.text("An API key or your Onshape password will not work here.")
            ttk.Button(
                self.content, text="I closed the popup or can't find the secret", command=self.secret_help
            ).pack(anchor="w")
        else:
            self.text(
                "1. Return to your connection in Onshape. Close the secret popup if it is still open."
                if self.reusing
                else "1. Close the secret popup in Onshape after copying its value on the previous screen."
            )
            self.text(
                "2. Open your connection: My account > Developer > OAuth applications > My Slicer Link, or the name you chose."
            )
            self.text(
                "3. Select Keys and secret. Copy the OAuth client identifier key, then click Paste here."
            )
            self.input("OAuth client identifier key / Client ID", self.client_id)
            self.text(
                "Both keys must come from that same connection. Save and open Onshape will ask you to sign in and allow access. Success brings you to Choose your slicer."
            )
            self.text(
                "If Onshape rejects the client ID, reopen Slicer Link connection setup from Windows Start. On Linux, use the app launcher's Connection setup action."
            )

    def use_existing(self):
        if not self.reusing and self.existing.get("client_id"):
            self.client_id.set(self.existing.get("client_id", ""))
            self.client_secret.set(self.existing.get("client_secret", ""))
        self.reusing = True
        self.step = 3
        self.render()

    def previous(self):
        if self.step:
            self.step = 0 if self.reusing and self.step == 3 else self.step - 1
            self.render()

    def advance(self):
        if self.step == 0 and self.reusing:
            # Starting a new registration must not pair its ID with a saved secret.
            self.reusing = False
            self.client_id.set("")
            self.client_secret.set("")
        if self.step in (3, 4):
            value = self.client_secret.get() if self.step == 3 else self.client_id.get()
            value = value.strip()
            label = "OAuth secret key" if self.step == 3 else "OAuth client identifier key"
            if not value:
                self.message.set(f"The field is empty. Copy the {label} in Onshape, then click Paste here.")
                return
            if any(char.isspace() for char in value):
                self.message.set(
                    f"This includes spaces or line breaks. Copy only the {label} value, without its label, then click Paste."
                )
                return
            if value.startswith(("http:", "https:", '"', "'")) or any(char in value for char in "*•…"):
                self.message.set(
                    f"This looks like an address, quoted text, or a hidden key. Copy the actual {label} value from Onshape."
                )
                return
            if self.step == 4 and value == self.client_secret.get().strip():
                self.message.set(
                    "Both fields contain the same value. Client ID is the OAuth client identifier key in Keys and secret. The secret belongs on the previous screen."
                )
                return
        if self.step < 4:
            self.step += 1
            self.render()
            return
        value = {
            "client_id": self.client_id.get().strip(),
            "client_secret": self.client_secret.get().strip(),
            "key": self.existing.get("key") or Fernet.generate_key().decode(),
            "owner": "",
            "control": self.existing.get("control") or secrets.token_urlsafe(32),
        }
        try:
            self.save(value)
        except (LinkError, OSError) as error:
            self.message.set(str(error))
            return
        self.result = value
        self.root.destroy()


def setup(save, *, existing=None):
    root = tk.Tk()
    wizard = SetupWizard(root, save, existing=existing)
    root.mainloop()
    return wizard.result

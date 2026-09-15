"""Small native wizard. Credentials are saved only after the final step."""

import secrets
import tkinter as tk
import webbrowser
from tkinter import ttk

from cryptography.fernet import Fernet

from .model import LinkError

SETTINGS_URL = "https://cad.onshape.com/user/settings"
REDIRECT = "http://localhost:8767/auth/callback"


class SetupWizard:
    def __init__(self, root, save, *, existing=None, open_url=webbrowser.open):
        self.root, self.save, self.open_url = root, save, open_url
        self.existing = existing or {}
        self.result = None
        self.step = 3 if self.existing.get("client_id") else 0
        self.identifier = "com.onshapeslicerlink.local." + secrets.token_hex(6)
        self.client_id = tk.StringVar(root, self.existing.get("client_id", ""))
        self.client_secret = tk.StringVar(root, self.existing.get("client_secret", ""))
        self.message = tk.StringVar(root)
        root.title("Set up Slicer Link")
        root.geometry("620x560")
        root.minsize(570, 490)
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        frame = ttk.Frame(root, padding=28)
        frame.pack(fill="both", expand=True)
        self.progress = ttk.Label(frame)
        self.progress.pack(anchor="w", pady=(0, 10))
        self.heading = ttk.Label(frame, font=("Segoe UI", 20, "bold"))
        self.heading.pack(anchor="w", pady=(0, 16))
        self.content = ttk.Frame(frame)
        self.content.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.message, wraplength=510).pack(fill="x", pady=12)
        navigation = ttk.Frame(frame)
        navigation.pack(fill="x")
        self.back = ttk.Button(navigation, text="Back", command=self.previous)
        self.back.pack(side="left")
        self.next = ttk.Button(navigation, command=self.advance)
        self.next.pack(side="right")
        self.render()

    def text(self, value):
        ttk.Label(self.content, text=value, wraplength=510, justify="left").pack(
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
        entry = ttk.Entry(self.content, textvariable=variable, show="*" if masked else "")
        entry.pack(fill="x")
        entry.bind("<Return>", lambda _event: self.advance())
        entry.focus_set()

    def render(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.message.set("")
        self.progress.config(text=f"Connect Onshape · Step {self.step + 1} of 5")
        self.back.config(state="disabled" if self.step == 0 else "normal")
        titles = (
            "Open your Onshape settings",
            "Name your connection",
            "Allow read access",
            "Copy the secret",
            "Finish connecting",
        )
        self.heading.config(text=titles[self.step])
        self.next.config(text="Save and sign in" if self.step == 4 else "Next")
        if self.step == 0:
            self.text("Onshape needs a one-time connection. We'll walk through it together.")
            ttk.Button(
                self.content, text="Open Onshape settings", command=lambda: self.open_url(SETTINGS_URL)
            ).pack(anchor="w", pady=(0, 16))
            self.text("Sign in, then choose Developer → OAuth applications → Create new OAuth application.")
            self.text("When the form is open, click Next here.")
            ttk.Button(self.content, text="I already have client details", command=self.use_existing).pack(
                anchor="w"
            )
        elif self.step == 1:
            self.text("Copy these into the matching fields in Onshape.")
            self.copy_field("Name", "My Slicer Link")
            self.copy_field("Primary format", self.identifier)
            self.copy_field("Summary", "Send my Onshape parts to my slicer.")
        elif self.step == 2:
            self.text("Type: choose Connected Desktop App.")
            self.copy_field("Redirect URLs", REDIRECT)
            self.text("Leave OAuth URL blank.")
            self.text("Under Permissions, check only Application can read your documents.")
            self.text("Click Create application in Onshape, then Next here.")
        elif self.step == 3:
            self.text(
                "Keep your saved secret, or paste a replacement from Onshape."
                if self.existing.get("client_id")
                else "Onshape shows an OAuth secret key once. Copy it here before closing that window."
            )
            self.input("Client secret", self.client_secret, masked=True)
            self.text("This is the generated key, not your Onshape password.")
        else:
            self.text("In Onshape, open Keys and secret. Copy the OAuth client identifier key here.")
            self.input("Client ID", self.client_id)
            self.text(
                "Next, your browser will ask you to allow read access. Your connection stays on this computer."
            )

    def use_existing(self):
        self.step = 3
        self.render()

    def previous(self):
        if self.step:
            self.step -= 1
            self.render()

    def advance(self):
        if self.step in (3, 4):
            value = self.client_secret.get() if self.step == 3 else self.client_id.get()
            if not value.strip() or any(char.isspace() for char in value.strip()):
                self.message.set("Paste the complete key from Onshape to continue.")
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

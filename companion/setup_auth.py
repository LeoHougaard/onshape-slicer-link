"""Local credential entry and authentication window.

Run: python -m companion.setup_auth
SPDX-License-Identifier: AGPL-3.0-only
"""
import argparse
import os
from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
from http.server import ThreadingHTTPServer

from companion.auth_probe import ROOT, ORIGIN, Probe, ProbeError, handler_for


def save_credentials(root, client_id, secret):
    values = {'ONSHAPE_CLIENT_ID': client_id.strip(),
              'ONSHAPE_CLIENT_SECRET': secret.strip(),
              'ONSHAPE_BASE_URL': 'https://cad.onshape.com'}
    for key in ('ONSHAPE_CLIENT_ID', 'ONSHAPE_CLIENT_SECRET'):
        value = values[key]
        if not value or len(value) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ProbeError('Paste both the client ID and secret, without internal spaces or line breaks.')
    path = Path(root) / '.env'
    lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition('=')[0].strip() not in values]
    lines.extend(f'{key}={value}' for key, value in values.items())
    staging = Path(root) / 'artifacts/onshape'
    staging.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=staging,
                                         prefix='credentials-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write('\n'.join(lines) + '\n')
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return values['ONSHAPE_CLIENT_ID'], values['ONSHAPE_CLIENT_SECRET']


class SetupWindow:
    def __init__(self, window, manual_browser=False):
        self.window, self.server = window, None
        self.manual_browser = manual_browser
        window.title('Onshape Slicer Link — Connect your app')
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=24)
        frame.grid(sticky='nsew')
        ttk.Label(frame, text='Connect your Onshape app', font=('Segoe UI', 17, 'bold')).grid(sticky='w')
        ttk.Label(frame, text='Your app is already registered. Paste its credentials below.').grid(sticky='w', pady=(8, 20))
        ttk.Label(frame, text='Application secret').grid(sticky='w')
        self.secret = ttk.Entry(frame, show='●', width=64)
        self.secret.grid(sticky='ew', pady=(5, 14))
        ttk.Label(frame, text='Client ID').grid(sticky='w')
        self.client_id = ttk.Entry(frame, width=64)
        self.client_id.grid(sticky='ew', pady=(5, 5))
        ttk.Label(frame, text='Find the client ID in your app’s “Keys and secret” tab.').grid(sticky='w')
        ttk.Label(frame, text='Account: cad.onshape.com\nCredentials stay in this project’s private .env file.').grid(sticky='w', pady=(18, 16))
        self.button = ttk.Button(frame, text='Save credentials' if manual_browser else 'Save and open sign-in', command=self.connect)
        self.button.grid(sticky='w')
        self.status = ttk.Label(frame, text='', wraplength=490)
        self.status.grid(sticky='w', pady=(14, 0))
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.secret.focus_set()

    def connect(self):
        server = None
        try:
            # Reserve the callback port before saving or opening the browser.
            probe = Probe(self.client_id.get().strip(), self.secret.get().strip(),
                          'https://cad.onshape.com', ROOT / 'artifacts/onshape/tokens.dpapi')
            server = ThreadingHTTPServer(('127.0.0.1', 8766), handler_for(probe))
            save_credentials(ROOT, probe.client_id, probe.client_secret)
        except (ProbeError, OSError) as error:
            if server is not None:
                server.server_close()
            self.status.configure(text=str(error) if isinstance(error, ProbeError)
                                  else 'Could not save credentials or open port 8766. Close any running authentication probe and retry.')
            return
        self.server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.secret.delete(0, tk.END)
        self.secret.configure(state='disabled')
        self.client_id.configure(state='disabled')
        self.button.configure(state='disabled')
        if self.manual_browser:
            self.status.configure(text='Saved. Open ' + ORIGIN + ' in the browser profile signed into your TEST account. Click Connect to Onshape and check the account before authorizing. Keep this window open.')
        else:
            self.status.configure(text='Saved. In the browser, click Connect to Onshape, then Verify token refresh after authorization. Keep this window open.\n\nIf the browser did not open, visit ' + ORIGIN)
            webbrowser.open(ORIGIN)

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        self.window.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual-browser', action='store_true',
                        help='Let the user choose the browser profile for account switching.')
    arguments = parser.parse_args()
    window = tk.Tk()
    SetupWindow(window, manual_browser=arguments.manual_browser)
    window.mainloop()


if __name__ == '__main__':
    main()

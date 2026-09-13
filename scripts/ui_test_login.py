"""Short-lived loopback transfer between the test browser and the native vault.

Never print the credential. Run explicitly with save or restore, then use the
printed one-use URL from the authorized Onshape sign-in page. No product routes
or application OAuth grants are changed.
"""

import argparse
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from slicer_link.model import LinkError
from slicer_link.platforms import secret

EMAIL = "3.1415robot.robot@gmail.com"
ORIGIN = "https://cad.onshape.com"
VAULT = "ui-test-login:" + EMAIL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("save", "restore", "status"))
    args = parser.parse_args()
    if args.mode == "status":
        print(json.dumps({"email": EMAIL, "saved": bool(secret(VAULT))}))
        return

    path = "/" + secrets.token_urlsafe(32)
    finished = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def allowed(self):
            return (
                self.path == path
                and self.headers.get("Origin") == ORIGIN
                and self.headers.get("Host") == f"127.0.0.1:{server.server_port}"
            )

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Access-Control-Allow-Origin", ORIGIN)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.reply(200 if self.allowed() else 403, {})

        def do_POST(self):
            nonlocal finished
            if not self.allowed() or self.headers.get("Content-Type") != "application/json":
                self.reply(403, {"ok": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or data.get("email") != EMAIL:
                    raise ValueError
                if args.mode == "save":
                    password = data.get("password")
                    if not isinstance(password, str) or not password:
                        raise ValueError
                    secret(VAULT, password)
                    if secret(VAULT) != password:
                        raise ValueError
                    self.reply(200, {"ok": True})
                else:
                    password = secret(VAULT)
                    if not password:
                        raise ValueError
                    self.reply(200, {"ok": True, "password": password})
                finished = True
                print(json.dumps({"ok": True, "mode": args.mode}), flush=True)
            except (ValueError, OSError, LinkError):
                self.reply(400, {"ok": False})

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 1
        print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}{path}"}), flush=True)
        deadline = time.monotonic() + 180
        while not finished and time.monotonic() < deadline:
            server.handle_request()
        if not finished:
            print(json.dumps({"ok": False, "reason": "expired"}), flush=True)


if __name__ == "__main__":
    main()

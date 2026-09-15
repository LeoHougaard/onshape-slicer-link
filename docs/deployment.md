# Run on your own computer

For installation, follow the [step-by-step setup guide](helper-setup.md).
You do not need to rent a server, register a domain, or set up a public tunnel.

The Windows installer runs the local app and opens its browser page. Its local
service listens on `127.0.0.1:8767`; Onshape sign-in returns to
`http://localhost:8767/auth/callback`. It still needs internet access to Onshape.
The service validates local requests and authenticates actions.

The [embedded preview](embedded-setup.md) has rendered complete stock slicers
inside an actual Onshape tab using a separate local service on port 8768.
That result does not make it part of the installer or establish compatibility
with every browser. Developer preparation is still required.

Earlier Render, hosted-helper, and custom-slicer instructions are historical.
Do not use **Set up hosted app.cmd**, **Start local test.cmd**, **Start Orca
Link.cmd**, or **Start Bambu Link.cmd** for the current installer. Developers
should use the [current source instructions](development.md).

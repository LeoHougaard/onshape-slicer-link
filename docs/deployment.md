# Run locally

Paid hosting is not allowed for this project. No Render service was created.
The local application replaces that proposal.

Use the [local setup instructions](helper-setup.md). The packaged app starts its
own server on `127.0.0.1:8767` and opens `http://localhost:8767`. It does not expose
a port on the LAN, create a public tunnel, or require a domain or TLS certificate.
It validates Host and browser Origin headers and authenticates local actions.

An Onshape right-panel extension requires an HTTPS iframe. This release uses a
local browser window; it does not claim to have solved iframe integration.
[Onshape extensions](https://onshape-public.github.io/docs/app-dev/extensions/).

# Onshape Slicer Link

An Onshape panel and a small desktop helper for the **official, unmodified
OrcaSlicer and Bambu Studio**. Normal slicer updates remain independent.

Link a solid part in Onshape, refresh it to stable STL files, then use the slicer's
native **Reload from disk**. The slicer handles arrangement, settings, slicing,
and printing. Slicer Link never rewrites your `.3mf` project.

The first implementation is ready for hands-on testing after its hosted app is
configured. Live Onshape export and both stock Windows slicers have passed the
initial checks. The Onshape extension itself still needs deployment and private
registration. [Verification and limits](docs/stock-verification.md).

## Get started

The Windows installer is built locally at
`dist/OnshapeSlicerLink-Setup-x86_64.exe`. This is a development installer; the
hosted application is not live yet.

The application operator runs **Set up hosted app.cmd** once to follow the guided
Render and private Onshape registration steps. The proposed Render service costs
about US$7.25/month before taxes or extra usage. Review that cost before creating
it. [Deployment instructions](docs/deployment.md).

After hosting is configured, install the helper, connect to Onshape, and choose a
project folder. Keep linked STL files and the slicer project together.
[Desktop setup](docs/helper-setup.md) ? [First user test](docs/user-test.md)

Windows and Linux x86-64 are supported targets. Linux packaging is provided;
Linux testing is explicitly waived for this handoff.

## Work on the application

Use Python 3.11 or newer and `uv`:

```sh
uv sync --locked --extra server --extra dev --extra browser
uv run playwright install chromium
uv run pytest tests/stock -q
```

Set `OSL_ORIGIN`, `OSL_ENCRYPTION_KEY`, `ONSHAPE_CLIENT_ID`, and
`ONSHAPE_CLIENT_SECRET` in the server environment, then run
`uv run onshape-slicer-link-server`. The server listens locally on port 8767.
Use `OSL_DEVELOPMENT=1` only for a loopback HTTP origin during development.
The desktop helper starts with `uv run onshape-slicer-link`.

Build on the target OS with `uv run python scripts/build_helper.py --origin
https://YOUR-HOST`. On Windows, compile `packaging/windows.iss` with Inno Setup
6 to create the installer. Manual packaging workflows build draft artifacts;
they do not deploy or publish a release.

[Architecture and API allowance](docs/architecture.md) ?
[Implementation plan](docs/implementation-plan.md)

The code is licensed under AGPL-3.0-only. The earlier prototype and its custom
slicer experiments are preserved as reference in `companion/`, `experiments/`,
and the [historical README](docs/prototype-readme.md). They are not the delivery
path for this application.

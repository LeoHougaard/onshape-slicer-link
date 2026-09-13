# Onshape Slicer Link

A local application that sends Onshape parts to your installed, unmodified
OrcaSlicer or Bambu Studio. No hosted server, subscription, tunnel, or domain.

## Use it

1. Open **Start Slicer Link.cmd**, or install and open the Windows application.
2. Choose OrcaSlicer or Bambu Studio from the detected installations. For a
   portable installation, use **Browse** under the slicer chooser.
3. Paste your Onshape document link and click **Connect document**. Choose a
   Part Studio and link the parts you want. The app remembers these choices.
4. Click **Send / Update**. New parts open in your selected slicer. Source files
   are managed automatically; there is no separate save or import step.
5. After CAD changes, click **Send / Update** again and use the slicer's native
   **Reload from disk** on the existing parts.

The app cannot observe an unsaved slicer project or apply a native reload for you.
It reports the handoff and reload requirement accurately. Repeated updates do not
import duplicate objects. **Open selected parts again** is an explicit recovery
option when starting a new project or reopening a missing object.

The Windows installer is `dist/OnshapeSlicerLink-Setup-x86_64.exe`. It contains the
local server, browser interface, and runtime. Leo's replacement test-account grant
has been migrated on this computer. Other installations have a one-time local
Onshape connection setup. [Setup](docs/helper-setup.md).

This version uses a separate local browser window. Embedding it inside the
Onshape document is still outstanding. Linux x86-64 source and packaging are
provided; Linux execution is untested at Leo's request.

[Architecture](docs/architecture.md) ? [First test](docs/user-test.md) ?
[Verification](docs/stock-verification.md)

## Development

```sh
uv sync --locked --extra server --extra dev --extra browser
uv run playwright install chromium
uv run pytest tests/stock -q
uv run python -m slicer_link.local
uv run python scripts/build_helper.py
```

Build on the target operating system. Compile `packaging/windows.iss` with
Inno Setup 6 for the Windows installer. The manual packaging workflow builds
Windows and Linux artifacts and does not run Linux tests.

Licensed under AGPL-3.0-only. The earlier custom-slicer experiments and hosted
helper remain as historical code. The supported entry point is `slicer_link.local`.

# Trying the slicer inside Onshape

The embedded version shows the full, unmodified OrcaSlicer or Bambu Studio
desktop inside an Onshape document tab. Both desktops and real Onshape part
imports have worked in Windows development tests.

**It is not included in the Windows test installer.** There is no finished
installer for this preview. A new computer needs developer preparation, and
the complete one-click update workflow is unfinished.

For the version you can install yourself now, use the
[local app setup guide](helper-setup.md).

## If a maintainer has prepared your computer

1. Ask the maintainer to start the local preview and your chosen slicer.
   **Connect desktop** connects to an already running desktop; it does not
   install or start the underlying environment.
2. Sign in to your own Onshape account and open your test document. The
   maintainer must have set up the private Slicer Link extension for this
   account. A public GitHub repository does not add it to your Onshape account.
3. Open the existing **Slicer Link** tab. To add it, use the **+** at the bottom
   of the document, then **Applications > Slicer Link**.
4. If the browser asks whether Onshape may connect to devices on your local
   network, allow it for this local preview. This was needed in the Edge test.
5. Choose your slicer in the panel and click **Connect desktop**. You should
   see its complete desktop. Finish any normal slicer setup dialogs.
6. Click **Choose Onshape parts**, choose a solid test part in the picker, then
   click **Add to slicer**. Wait for the result and inspect the part in the
   embedded slicer.

If **Slicer Link** is missing from Applications, or the desktop cannot connect,
the preview setup is incomplete. Reinstalling the local app does not configure
this preview. Send the maintainer the visible error message.

## What to expect

Use disposable test projects. Profiles and saved files live in the separate
local slicer environment. Windows file browsing and moving projects between
that environment and your normal desktop still need a finished user interface.

The following are still in development:

- Installation and startup on a new computer.
- Updating every linked object in one click, including recovery after a failure.
- Complete link preservation through renaming, copying, and plate moves.
- Automatic updates, non-default configuration coverage, and normal slicer
  update compatibility.

The proposed update flow saves a recovery copy, updates the project, and reopens
it in the same slicer. Reopening clears its Undo history. This is a proposed
workflow, not a working update button in the preview.

## For the maintainer

The preview is on
[`feature/embedded-stock-slicer`](https://github.com/LeoHougaard/onshape-slicer-link/tree/feature/embedded-stock-slicer).
Read the [runtime verification record](https://github.com/LeoHougaard/onshape-slicer-link/blob/feature/embedded-stock-slicer/docs/embedded-runtime-verification.md)
and [implementation plan](https://github.com/LeoHougaard/onshape-slicer-link/blob/feature/embedded-stock-slicer/docs/embedded-plan.md)
before offering a test session.

The Windows experiment uses a dedicated WSL2 distribution called
`OnshapeSlicerProbe`, Docker inside that distribution, and pinned LinuxServer
slicer images. Each image is roughly 6 to 7 GB. Virtualization must work on the
host. The start commands below do not install WSL, provision the distribution,
install Docker, register an Onshape extension, or create an Onshape login.

Preparation also requires that user's local app connection, the development
dependencies, a private Onshape Element tab extension pointing to
`http://localhost:8768/`, and the account's private App Store subscription.
Keep credentials and runtime data on the local computer.

After those prerequisites are in place, run from the feature-branch checkout:

```powershell
uv sync --locked --extra embedded-dev
uv run --extra embedded-dev python -m scripts.embedded_runtime start orca
uv run --extra embedded-dev python -m scripts.embedded_probe
```

Use `bambu` instead of `orca` to start Bambu Studio. Keep the preview server
running during the session. Verify the real Onshape tab and an import before
handing it over; a running container alone is not a completed setup.

These commands resume a prepared development environment. Linux-host testing
remains deferred.

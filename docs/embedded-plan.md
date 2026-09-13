# Isolated stock slicer implementation

Leo authorized building and UI testing the dedicated local slicer environment.
The complete acceptance list in [acceptance-audit.md](acceptance-audit.md) remains
the completion gate. Free/local operation and unmodified slicer releases remain
requirements. A rendered desktop or source-file refresh alone is not completion.

The previous working implementation is preserved on GitHub at tag
`local-bridge-v0.2.0`, commit `9a3d865`. The repository is private. Current
credentials were checked against all 122 tracked and pending source files before
the checkpoint push; none matched. Work continues on
`feature/embedded-stock-slicer`.

## Plan and verification

1. Establish the local runtime and actual Onshape extension entry point. Verify
   the embedded page in the authorized test account and the stock slicer in a
   dedicated desktop. Verify that other desktop windows receive no input.
2. Prove import, native reload and saved-project inspection in both stock
   applications using disposable asymmetric fixtures across multiple plates.
   Preserve and compare placement, rotation, material and supported settings;
   test copies, renaming, save/reopen and failure recovery.
3. Connect the proven adapter to the existing cached, pinned Onshape exporter.
   Make Add and Update available in the embedded UI. Count clicks and show the
   revision actually loaded, with manual updates by default.
4. Package installation and update/recovery controls, verify UI flows and the
   complete requirement matrix, and retain explicit failures if any gate fails.

No paid service or public tunnel is planned. Local HTTP embedding worked in the
shared Windows browser, so this prototype needs no certificate installation.
Other browsers and the final desktop stream still need verification.
Ordinary slicer updates must use upstream binaries, with compatibility checks
for the external automation. Container image updates are a different user flow
from the desktop application's updater and must be explained in setup.

## Current evidence

- Baseline bridge suite: 35 Windows tests passed during the acceptance audit.
- Test account browser sign-in, native password storage, repeat sign-in and
  actual Part Studio rendering passed. See [UI test access](ui-test-access.md).
- A private, free application extension loads `http://localhost:8768/` inside
  an actual Onshape application tab. Onshape supplies document, workspace and
  application element IDs automatically. No hosted service, public tunnel,
  certificate installation or browser security override was required.
- Onshape's native picker supplied two solid parts from different Part Studios,
  including each source's configuration and exact document microversion. The
  local page made no REST API requests to obtain those selections. See
  [the embedding verification](embedded-verification.md) for the evidence and
  limits. These are source selections, not persisted slicer links.
- WSL 2.7.3 is installed, but there is no usable distribution or Docker runtime.
  Windows reports Virtual Machine Platform enabled, no active hypervisor, and
  AMD firmware virtualization disabled. Importing a checksum-verified official
  Alpine minirootfs as a disposable WSL2 startup probe failed with
  `HCS_E_HYPERV_NOT_INSTALLED` and an explicit firmware virtualization error.
  No system settings were changed. Firmware settings cannot be changed from
  this development process.
- Linux compatibility testing is deferred at Leo's request. This WSL startup
  check was a prerequisite for the isolated runtime on Windows.

Step 1 is partially verified. Steps 2 through 4 remain open. No claim about
reliable native reload, preservation, two-click updates or slicer embedding is
supported by this prototype yet.

## Next step

Enable SVM Mode in the ASUS PRIME B550M-A WIFI II firmware and reboot Windows.
ASUS documents the setting under Advanced > CPU Configuration > SVM Mode.
Then verify WSL2 startup, create the dedicated desktop and test the stock
slicers before expanding the UI or persistence model.

Reference: [ASUS virtualization instructions](https://www.asus.com/ca-en/support/faq/1045141/).

If runtime startup is blocked by firmware virtualization, continue independent
Onshape embedding and adapter work, then record the exact prerequisite for Leo.
Do not replace the isolated session with automation of Leo's everyday desktop.

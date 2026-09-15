# Isolated stock slicer implementation

Leo authorized building and UI testing the dedicated local slicer environment.
The complete acceptance list in [acceptance-audit.md](acceptance-audit.md) remains
the completion gate. Free/local operation and unmodified slicer releases remain
requirements. A rendered desktop or source-file refresh alone is not completion.

The previous working implementation is preserved on GitHub at tag
`local-bridge-v0.2.0`, commit `9a3d865`. The repository was private at that checkpoint. Current
credentials were checked against all 122 tracked and pending source files before
the checkpoint push; none matched. The embedded development work has since
been merged into `main`.

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
- After Leo enabled SVM, WSL2 imported and started the dedicated Alpine
  distribution. Docker runs inside that distribution without Docker Desktop.
  Both dedicated stock desktops render inside the real Onshape application tab.
- Native reload changed three objects across two plates in both applications.
  Saved geometry, transforms, material, plate assignment and wall/infill settings
  were compared. Reload recenters asymmetric geometry, shifting CAD landmarks.
- A bounded project rewrite/reopen experiment retained the source-coordinate
  frame and revision-bearing filenames in both native saves. It is not yet a
  general project writer. It clears native Undo history when reopening.
- Add to slicer now exports a real selected Onshape part, imports it through the
  stock UI, saves a recovery copy and verifies the saved mesh and source revision.
  The real Onshape UI test passed in both applications. Existing objects and
  settings were unchanged in the checked Bambu project.
- The local proxy has dedicated authentication for its backends, Host and Origin
  checks, a same-origin request token, private automation-route exclusions and
  WebSocket input suppression during imports. The existing local OAuth grant
  stays on Windows. Opening the panel still makes no Onshape REST requests.
- 51 Windows tests passed in 10.32 seconds, including the existing 35 bridge
  checks. Native GUI evidence is separate from that suite.
- Linux compatibility testing remains deferred at Leo's request. The WSL checks
  above test the isolated runtime on Windows.

Step 1 is verified for this Windows development setup. Steps 2 and 3 are partial;
step 4 remains open. The complete acceptance list is still the release gate.
See [the current native verification](embedded-runtime-verification.md).

## Next steps and decision

The proposed normal workflow is one initial part selection and Add, followed by
one Update linked parts click after CAD edits. The application must handle all
files and native dialogs. Leo emphasized that it is only worth building if it
requires less work than exporting/importing manually.

The candidate update is an automatic recovery save, project geometry update,
reopen and native readback. Leo asked how many clicks this takes; the answer is
one planned click, with no manual file handling. Clearing Undo history is the
outstanding workflow tradeoff raised for review. The bounded experiment is
reviewable, but the full update command has not been implemented or approved as
a completed end-to-end workflow.

Before promoting a project writer, test repeated asymmetric updates, renamed
copies moved between plates, non-default configurations, unknown/missing links,
painted or multi-volume objects, sliced data, interrupted saves, active plate
retention and rollback. Compare actual native saves, not command delivery.
Native window IDs and UUIDs regenerate and cannot be durable link identities.

Complete the no-slicer/startup flow, installation, normal upstream update flow,
source registry backup and recovery UI. The current scripts and test-account
setup are development tools, not a finished installer or release.

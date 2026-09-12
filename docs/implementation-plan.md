# Stock slicer implementation

Current direction, September 11, 2026. This supersedes the custom-build delivery
proposal in the historical experiment documents. Preserve the experiments as
reference; do not modify or distribute slicer binaries.

## Required outcome

- An Onshape application manages selection, links, refresh, and connection status.
- Official OrcaSlicer and Bambu Studio remain independently updatable.
- Geometry travels through stable STL files and the slicer's native Import and
  Reload from disk commands. The user applies reloads; there is no UI automation
  in the product and no claim to observe an unsaved stock slicer project.
- Windows and Linux x86-64 are required. Target broad distro compatibility.
  Leo explicitly waived Linux testing on September 11. Do not provision Linux
  test environments or make Linux execution a completion gate. ARM is outside scope.
- A packaged helper offers guided setup, detects slicers, and checks connections.
  It must not require Python, development credentials, or a terminal for users.
- No background Onshape polling. Cache immutable exports, share requests, count
  actual requests, and avoid downloads when source revisions are unchanged.
- Slicing and printing are user actions. Native reload placement and Undo rules
  replace the experiment's stronger geometry-transaction guarantees.
- Failed exports retain the last good files. Keep previous downloaded geometry.
  Store portable link metadata beside source files; never rewrite user 3MF files.
- Further live CAD testing uses only the designated test account.

## Implementation and verification

1. [ ] Establish stock reload behavior with isolated disposable projects.
2. [x] Build the portable source model, validated binary STL handling, export
       cache, request accounting, and safe local file transactions.
3. [x] Build one hosted service with SQLite persistence, OAuth, a small Onshape
       panel, paired devices, and authenticated transfer jobs.
4. [ ] Build the Windows/Linux helper, guided setup, URI handoff, slicer discovery,
       and platform packaging. Keep OS integration out of the shared core.
5. [ ] Exercise failure cases, API-call budgets, real browser UI, packaged helper,
       and both stock slicers. Linux execution is explicitly waived.
6. [ ] Document deployment and the exact Onshape registration fields. Verify the
       deployed private app if a suitable host and account access are available.

The finish line is a verified user workflow, not a successful build. Record
unavailable environments and unverified behavior explicitly. Do not treat the
old custom-build results as evidence for stock slicers.

## Evidence so far

- Shared core and HTTP integration: 18 checks passed, including rollback after
  a partial file commit, recovery after restart, delivery receipt retries,
  stale transfers, account/device isolation, and persistent export caching.
- Edge browser at 360 and 320 px: panel selection through real HTTP service and
  helper file transfer passed using a fake CAD provider. Screenshot inspected.
- Installed unmodified Orca development build: native Reload All changed an
  asymmetric fixture from 32 to 46 mm, preserving its saved instance transform.
  Further reopen, Undo, settings, and Bambu checks are in progress.
- Windows bundled helper built. Packaged execution still needs verification.
- No live hosted app or new Onshape extension has been deployed yet.
- Linux test image downloads finished before the waiver arrived. No VM was
  created or started. Linux testing will not continue.

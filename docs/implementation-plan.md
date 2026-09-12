# Stock slicer implementation

Latest direction: no paid hosting is allowed. Leo requested a quick local test.
The immediate gate is a running loopback app using the existing replacement
test-account grant and a verified local STL save. The Onshape iframe and a
packaged cross-platform local installation are deferred for this quick test.
Render setup is withdrawn; no service or hosting charge was created.

Local test evidence: the app is bound to `127.0.0.1:8767`. A real Edge browser
used the replacement account, selected a solid part, refreshed it, and saved
one 15,284-byte STL to `artifacts/local-test/project/`. No browser errors occurred.
The page was visually inspected. Unauthenticated saves/stops and unexpected
Host headers are rejected. The page includes a button to stop the local server.
This is a Windows development launcher, not the final cross-platform installer.

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

1. [x] Establish stock reload behavior with isolated disposable projects.
2. [x] Build the portable source model, validated binary STL handling, export
       cache, request accounting, and safe local file transactions.
3. [x] Build one hosted service with SQLite persistence, OAuth, a small Onshape
       panel, paired devices, and authenticated transfer jobs.
4. [x] Build the Windows/Linux helper, guided setup, URI handoff, slicer discovery,
       and platform packaging. Keep OS integration out of the shared core.
5. [x] Exercise the core failure cases, API-call budgets, browser UI, packaged
       helper startup, and both stock slicers. Leo will do the broader hands-on
       tests. Linux execution is explicitly waived.
6. [x] Prepare Render deployment, the operator wizard, and exact Onshape fields.
       The source is in Leo's private GitHub repository. The Windows installer
       is built. Hosting and private registration require Leo's account actions.
7. [ ] User handoff: create the Render service, authorize the hosting charge,
       register/subscribe the private Onshape app, and perform the first user test.

The finish line is a verified user workflow, not a successful build. Record
unavailable environments and unverified behavior explicitly. Do not treat the
old custom-build results as evidence for stock slicers.

## Evidence so far

- Shared core, HTTP, auth, and browser integration: 23 checks passed, including rollback after
  a partial file commit, recovery after restart, delivery receipt retries,
  stale transfers, account/device isolation, and persistent export caching.
- Edge browser at 360 and 320 px: panel selection through real HTTP service and
  helper file transfer passed using a fake CAD provider. Screenshot inspected.
- Installed unmodified Orca development build: native Reload All changed an
  asymmetric fixture from 32 to 46 mm, preserving its saved instance transform.
  Bambu's selected part also changed from 32 to 46 mm. A two-plate Bambu check
  retained transforms, settings, and plate assignments while leaving the other
  part unchanged. Broader reload/reopen/Undo checks are handed to Leo.
- Windows bundled helper built; its setup window was opened and inspected.
  The Inno Setup installer also compiled successfully.
- The new exporter passed a live read-only refresh on the replacement test
  account. Initial refresh: five HTTP responses including the redirect. A second
  refresh reused the persistent export cache with one revision check.
- No live hosted app or new Onshape extension has been deployed yet.
- Linux test image downloads finished before the waiver arrived. No VM was
  created or started. Linux testing will not continue.

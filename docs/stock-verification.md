# Stock application verification

September 12 local application update: 35 automated Windows checks passed.
These include document-root URL selection, persisted document/slicer choices,
one-click browser send, stable paths, no duplicate imports, interrupted launch,
failed export/start, ownership/Host/Origin boundaries, and saved-project source
mirroring without modifying the 3MF. A real document-root API lookup passed on
the replacement test account. The packaged browser UI and native picker cancel
flow passed. The rebuilt 0.2.0 installer completed successfully and the installed
application is running with the migrated test connection.

Both installed stock slicers accepted ordinary STL command-line input. Their
native Save commands produced 3MF files containing the intended test geometry and
source filenames. Evidence is in `artifacts/stock/direct-send/`. Disposable data
directories isolated the native checks from the user's running slicer. No product
code sends UI keystrokes or changes slicer preferences.

The released local launcher replaces the hosted prerequisite below. The remaining
Onshape integration limit is embedding the app inside the document, not hosting.


September 11, 2026. This record covers the new application, not the earlier custom
slicer builds. Leo will perform broader hands-on testing. Linux tests are waived.

| Check | Result |
| --- | --- |
| Shared core, API, authentication, and browser suite | 23 checks passed on Windows |
| Browser panel | Edge, 360 and 320 px wide, actual HTTP service and helper file transfer; fake CAD provider |
| OAuth popup and pairing | Actual callback, nonce exchange, session, and pairing with a simulated provider consent response; no cookies required |
| Live Onshape export | Passed on the user-confirmed replacement test account; no CAD edits |
| Unchanged live refresh | One HTTP 200 revision request; persistent cached export reused |
| Initial live refresh | Five HTTP responses: 200, 200, 200, 307, 200 |
| Packaged Windows helper | Built with bundled Python/Tk; setup window opened and inspected |
| Official OrcaSlicer | Installed 2.5.0-dev build 93d5b658; native Reload All changed asymmetric fixture from 32 to 46 mm |
| Official Bambu Studio | Installed 02.08.02.61; native Reload from disk changed asymmetric fixture from 32 to 46 mm |
| Saved transform | Unchanged in both single-part stock checks; Orca fixture had a nonzero rotation and off-center placement |
| Bambu two-plate project | Selected first part changed; second stayed unchanged. Both rotations, placements, plate assignments, wall counts, and infill overrides remained intact |
| Linux | Supported by source and packaging configuration; not executed, at Leo's request |
| Hosted Onshape extension | Awaiting Render account setup and private Onshape registration |

The Bambu multi-plate exercise does not establish one-command reload of all plates.
Use each slicer's selection and reload controls. The broader user test should
cover project reopening, native Undo, restore, painted supports, and real models.

The file tests cover partial commit rollback, crash recovery, bad downloads,
outside edits, account separation, cache reuse, receipt retries, stale transfers,
and rejection of unsafe paths. HTTP tests cover ownership of links, selections,
devices, and downloads; pairing replay; body limits; and failed exports retaining
existing files. Authentication tests cover nonce binding, one-use codes, encrypted
CAD tokens, expiry, and token refresh without an extra CAD probe.

Evidence is in ignored local `artifacts/stock/`: browser and helper screenshots,
disposable stock `.3mf` projects, live request results, and package build logs.
The stock tests used separate data directories. Product code does not automate
the slicer UI or rewrite `.3mf` files. The hand-built multi-plate input was a
disposable test fixture created from a stock-saved project.

Windows checks:

```powershell
$env:OSL_BROWSER_CHANNEL = 'msedge'
uv run --extra server --extra dev --extra browser pytest tests/stock -q
uv run --extra dev ruff check slicer_link tests/stock scripts/build_helper.py scripts/verify_stock_onshape.py
```

The read-only live test is `python -m scripts.verify_stock_onshape`. It is a local
developer tool using the existing test account's Windows-encrypted grant. It is
not included in the helper or run by CI.

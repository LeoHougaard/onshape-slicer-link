# Full acceptance audit

September 12, 2026. The user's full requirement list is the acceptance gate.
The local file bridge is a working baseline, not completion of that gate.

## Baseline and scope

Baseline: commit `da02722`, installed local application 0.2.0. Preserve the
installed application while deciding how to close the integration gaps.

Reproduction on Windows:

```powershell
$env:OSL_BROWSER_CHANNEL = 'msedge'
.\.venv\Scripts\python.exe -m pytest tests/stock -q
```

Result this audit: 35 passed in 14.33 seconds, with two dependency deprecation
warnings. These tests verify the bridge, not every requirement below. Earlier
native application evidence is in [stock-verification.md](stock-verification.md).
Linux execution is waived by the user. No new live CAD requests, credential
changes, slicer modifications or project mutations were needed for this audit.

## Acceptance matrix

| Requirement | Evidence and remaining gap |
| --- | --- |
| Parts from any Part Studio in both slicers | Workspace and Part Studio selection exists; both stock applications imported a fixture. Configured, same-name parts across multiple studios still need a complete native acceptance test. |
| Add to slicer inside Onshape, targeting active plate | Missing. Onshape documents a Part context action with part ID and configuration parameters. A free local action registration and delivery to a specific live slicer/plate are not verified. |
| Update all linked parts in at most two clicks | Not met. Send / Update refreshes source files; native reload is separate. Neither complete click count nor all-project coverage has been established. |
| Preserve placement, orientation, plate, material and supported settings | Partial. Native fixture checks preserved transforms; the Bambu two-plate check also preserved plate assignments and wall/infill overrides. Both stock source implementations copy volume config, material ID and transformation during reload. This is not proof for all supported settings or geometry changes. |
| Keep links through copy, rename, plate moves, save/reopen | Not fully verified. Stable source filenames and source mirroring exist. The app has no live object inventory and cannot detect every copy or acknowledge its loaded revision. |
| Reliable identity, configurations and each object's CAD snapshot | Source identity, anchor microversion and configuration are retained by the exporter. The UI does not establish or show the revision loaded by each slicer object. Exported revision and loaded revision must remain distinct. |
| Manual default and optional automatic geometry updates | Manual default exists. Automatic geometry application is missing. Periodically exporting files would not satisfy it. |
| Easy setup, secure authentication, clear multiple/no-slicer behavior | Packaged local runtime, native credential storage and executable choice exist. First-use OAuth registration remains manual; selecting an executable does not select a particular open project. |
| Stock slicers, normal updates, free/local, Linux x86 | Current bridge uses stock binaries and no hosted service. Linux packaging exists but execution is waived. No verified architecture currently satisfies every row above while preserving these constraints. |

## Failure ledger

| Category | Observed fact | Cause or hypothesis | Impact |
| --- | --- | --- | --- |
| Live project control | Bambu's inspected interprocess handler accepts existing file paths and posts an import event. Orca's documented host API is read-only. | High confidence: the inspected interfaces do not expose the required object replacement transaction or completion receipt. Other possible interfaces must be proven, not assumed. | Blocks guaranteed live updates and per-object acknowledgement. |
| Object identity and persistence | The bridge tracks exports and import attempts, not live objects. | High confidence: a source-file ledger cannot tell which copies have reloaded, including after Undo or reopening older projects. | Blocks truthful per-object snapshot reporting. |
| Destination selection | The bridge chooses an executable and launches it with filenames. | High confidence: process launch success does not identify the receiving project or active plate. | Ambiguous behavior with multiple windows. |
| Onshape entry point | The installed product opens its own local browser page. | Native Part context actions are documented, but local action URL registration has not been verified. OAuth localhost redirect support alone is not evidence of extension URL support. | Add to slicer inside Onshape remains unimplemented. |
| Verification coverage | Prior native checks covered imports and limited reload cases. | High confidence: bridge tests cannot measure copied-object identity, loaded snapshots or click count across a real project. | The release cannot claim full compliance. |

Both slicers' inspected `reload_all_from_disk()` select all, call native reload
and restore selection. `Selection::add_all()` iterates non-wipe-tower GL volumes,
without an explicit active-plate filter. Therefore this audit does **not** claim
Reload All is restricted to the active plate. Its complete multi-plate behavior
still needs a native test. The previous Bambu test reloaded a selected object;
its unchanged second object does not establish a Reload All limitation.

## Architecture decision

The desired end-to-end design needs a local authenticated Onshape action, pinned
CAD exports, and a slicer adapter that can identify the target project, enumerate
linked objects, replace their geometry through native operations, preserve links
in project saves, and report the revision actually applied. Keep API checks
manual by default and deduplicate exports across copies. Automatic mode must use
the same verified replacement path, with an explicit request budget.

The missing piece is the slicer adapter. Three routes need to be distinguished:

| Route | What it offers | Why it is not an accepted full solution yet |
| --- | --- | --- |
| Supported native integration hooks | Native object updates and durable metadata could provide the required behavior. | Current inspected interfaces lack required operations. Upstream acceptance and shipping cannot be promised; a private fork conflicts with the user's stock requirement. |
| Desktop UI automation around stock slicers | Could drive existing import, save and reload commands without changing binaries. | Needs explicit direction before replacing the previously rejected automation approach. It must prove window targeting, modal recovery, state verification and Linux desktop compatibility. It is not yet a reliable solution or a two-click guarantee. |
| Update a saved 3MF and reopen it | Could inspect and update a complete saved project while retaining stock binaries. | Changes the live workflow, cannot see unsaved edits, and needs schema/version and geometry-setting preservation tests. No project writer has been implemented. |

Recommendation: retain 0.2.0 as the usable baseline and resolve this integration
decision before adding more file-bridge features. Do not label source refresh as
automatic object synchronization or claim that packaging closes these gaps.

The first experiment after choosing a route must use disposable projects in both
stock applications: two studios with identical part names, two configurations,
copies renamed and moved across plates, asymmetric geometry changes, material
and setting overrides, and save/reopen. Measure actual click count and inspect
saved geometry, transforms, plate assignments, settings and source snapshots.
Include an interrupted update, missing part and multiple open slicer windows.
Stop before product expansion if the adapter cannot pass this gate.

## Sources

- [Orca host API](https://github.com/orcaslicer/orcaslicer/wiki/host), explicitly read-only.
- [Orca plugin development](https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugin_development), plugin registration is not proof of live model mutation support.
- [Onshape extensions](https://onshape-public.github.io/docs/app-dev/extensions/), Part context actions and parameter replacement.
- [Bambu interprocess handler](https://github.com/bambulab/BambuStudio/blob/926a7192574bcb9b3a732e1ec59a46d79cb45466/src/slic3r/GUI/InstanceCheck.cpp).
- [Bambu native reload](https://github.com/bambulab/BambuStudio/blob/926a7192574bcb9b3a732e1ec59a46d79cb45466/src/slic3r/GUI/Plater.cpp).
- [Orca native reload](https://github.com/OrcaSlicer/OrcaSlicer/blob/a49b8927088cde075c8ccfc7dcaf1bedc3b52af9/src/slic3r/GUI/Plater.cpp).

Local external checkouts contain historical custom changes. This audit inspected
`git show HEAD:<path>` at the source commits above, not their working files.

# Embedded stock desktop and CAD import experiment

September 14, 2026. Windows development verification using Leo's authorized
Onshape test account. This is progress toward the acceptance gate, not a release.

## Local runtime

After SVM was enabled, WSL2 started the dedicated `OnshapeSlicerProbe` Alpine
distribution. Docker runs inside it; Docker Desktop is not installed or needed.
The two containers expose only loopback ports and keep profiles in dedicated
volumes. They do not mount the host desktop, Docker socket or Onshape credentials.
Audio, microphone, clipboard, sharing and gamepad forwarding are disabled.

The LinuxServer images extract upstream slicer AppImages. No slicer source or
binary was patched. Development image digests are pinned in
`scripts/embedded_runtime.py`. Observed versions were OrcaSlicer 2.4.2 and
Bambu Studio 02.08.02.61. Images are large, roughly 6–7 GB each; easy installation
and a normal upstream update flow still need implementation and testing.

The low-level local desktop interface is Pelorus/PIXELFLUX. No language model,
remote inference account or paid service is configured. Its private API is not
forwarded to the browser. The Python adapter uses it to inspect native windows,
read accessibility labels, send input and save screenshots inside the container.

References: [Orca image](https://docs.linuxserver.io/images/docker-orcaslicer/),
[Bambu image](https://docs.linuxserver.io/images/docker-bambustudio/),
[desktop interface](https://github.com/linuxserver/pelorus/blob/master/API.md).

## Actual Onshape embedding

Both complete stock desktops rendered inside the real Onshape application tab.
The local panel receives document/workspace context and native picker selections
without a pasted document URL. The new compact layout leaves most of the tab for
the slicer. Screenshots were inspected at
`artifacts/embedded/browser/onshape-orca.png` and `onshape-bambu.png`.

The isolated Edge test profile required Onshape's normal local-network permission.
The test grants that permission only for `https://cad.onshape.com`; it does not
disable browser security or change Leo's normal browser profile. Onshape also
logs a report-only framing warning, which did not prevent rendering. Cross-browser
compatibility is not established by this result.

[Playwright's permission API](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-grant-permissions)
documents the test mechanism.

## Native fixture comparison

Both applications loaded a two-plate fixture containing asymmetric L prisms.
A native clone made three objects total. The part length changed from 32 to
46 mm. Wall counts of 4 and 6, infill of 23% and 37%, material assignment and
two different rotations were retained.

| Operation | Orca | Bambu |
| --- | --- | --- |
| Native reload reaches original, clone and second plate | Passed | Passed after selecting all objects |
| Reload preserves saved object transforms and settings | Passed | Passed |
| Native reload preserves original CAD landmarks | Failed: geometry recenters | Failed: geometry recenters |
| Bounded project update/reopen preserves CAD landmarks | Passed | Passed |
| Updated source filename survives native reopen/save | Passed | Passed |

The project experiment changed only the known fixture's mesh and source filename.
It was then reopened and saved by the actual application. Both slicers recentered
the mesh internally and compensated the object transform. Comparing world
coordinates verified the intended result to less than 0.000001 mm. Comparing only
the stored transform would have given the wrong conclusion.

Project settings, object settings, source metadata and plate membership were
compared. Bambu regenerated part UUIDs during reload; both applications regenerated
instance IDs during reopen. These IDs are unsuitable for durable source links.

Run the comparison against the captured native saves:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_embedded_projects
```

The result is saved to `artifacts/embedded/project-comparison.json`. The bounded
writer, `scripts/probe_project_update.py`, intentionally accepts only the known
unsliced fixture with simple unpainted meshes. It is not a general project writer.
Its fixed source-offset handling must not be copied into a repeated-update path.

## Real CAD Add

The native picker selected **Round test** from **Prism**, with configuration
`default` and snapshot `13a5435a132f26c8567dbe38`. One subsequent **Add to slicer**
click exported, imported and verified it in each stock application. No user file
picker or command line was required during the import.

The backend reused the existing local OAuth grant and pinned exporter. It saved
a recovery 3MF, imported an immutable revision-bearing source filename, then
saved another 3MF and compared triangle geometry with the exported STL. The
receipt includes the native object, plate, configuration and verified revision.
For the Bambu test, all three pre-existing objects, their transforms, meshes and
print settings compared equal before and after the import.

The source registry and revision records are in the local development database.
Credentials stay in the existing encrypted store and native credential vault.
No Onshape token is sent to the container or browser. Files, browser profiles,
screenshots, native projects and local receipts remain ignored artifacts.

Actual import receipts:

- Bambu: `artifacts/embedded/jobs/1c426978c85d44f482bed756ff72c068/receipt.json`
- Orca: `artifacts/embedded/jobs/abd9f73503b7489792ee57e3c39d7104/receipt.json`
- A second Part Studio, **The Second / Round**, into an empty Bambu project:
  `artifacts/embedded/jobs/ba7c72b12b2745a6a5586a811571ff56/receipt.json`

The UI test can repeat an import into the dedicated test project:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_embedded_ui --add-orca
.\.venv\Scripts\python.exe -m scripts.verify_embedded_ui --add-bambu
```

These commands intentionally add a part. With no flags the script only inspects
the two embedded desktops. It restores only the authorized test login from the
native password vault. A fresh Bambu empty project was also saved successfully.

## Failures and remaining gates

- The desktop interface's letter shortcuts did not work reliably. The adapter
  uses `wtype` for text/modifier combinations and the tested desktop input path
  for Return. Native save completion is checked rather than assumed.
- Windows tried IPv6 before IPv4 for each `localhost` backend request, adding
  about two seconds. Using `127.0.0.1` internally reduced the measured request to
  roughly four milliseconds. The browser-facing address remains localhost.
- Screenshots can be black or stale without an active desktop stream. Visual
  checks must establish the browser stream before capturing the desktop.
- A direct AT-SPI action experiment left a Bambu dialog unresponsive and removed
  its accessible application entry. That experiment was removed. The dedicated
  Bambu container was restarted; saved fixtures and its profile were retained.
- Clicking an Import submenu could close it after GTK opened it on pointer entry.
  The adapter now hovers over the parent menu and waits for the named child item.
  The second-Studio import into an empty Bambu project passed after this change.
- Startup can show native configuration/update dialogs. The adapter stops on
  unexpected or multiple windows instead of guessing which button to press.
- Interrupted imports fail closed. Retrying the same request cannot duplicate
  a completed import, but recovery from an interrupted job still needs a UI.
- First-use setup, stream reconnection, friendly native object names, alternate
  active plates, native rename/move persistence, non-default configurations,
  automatic updates and the complete one-click update workflow are unfinished.
- The chosen update proposal reopens the project and clears native Undo history.
  Recovery copies are the proposed replacement. This tradeoff was raised with
  Leo; his stated criterion is less work than manual export/import.
- No claim of Linux-host compatibility testing, printing, upstream updater
  compatibility or full acceptance compliance is made.

The Windows suite passed 51 tests in 10.32 seconds, including 35 existing bridge
tests. New tests cover private-route exclusions, hostile Host/Origin requests,
WebSocket restrictions, import request authentication/concurrency, changed-mesh
detection and retry behavior. Native GUI evidence above is separate from this
suite. Ruff passed for the development modules and tests.

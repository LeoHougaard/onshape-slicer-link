# Manual updates through the companion

Use `Start Orca Link.cmd` or `Start Bambu Link.cmd` in the project folder. Each starts or reuses this project's companion and launches the corresponding experimental portable slicer with its separate profile. The configured test Onshape account remains in use.

Open a linked 3MF project, then click **Update linked parts** next to **Undo/Redo** in the top toolbar at the top of either experimental slicer. One click updates every linked object across the project's plates, with no confirmation dialog or separate export command. It downloads current CAD geometry through the companion, validates it, and replaces the linked geometry while retaining the slicer setup. Slicing and printing stay manual. The same command remains available under **File > Onshape Slicer Link**.

These are separate modified slicer builds, not stock add-ons. Keeping native changes minimal and supporting ordinary slicer upgrades remain design requirements; a supported stock installation route has not been demonstrated. See [extension findings](extension-audit.md).

**Revert linked geometry** restores the preceding geometry from the project, including without a running companion. Save the project to retain its links and previous geometry. Revert records automatic updates as paused; the optional automatic-update mode is not implemented.

For an existing linked test project, the development launcher also accepts a path:

```powershell
powershell -NoProfile -File scripts/start_link.ps1 -Slicer orca -Project artifacts/orca/results/bridge-reverted.3mf
powershell -NoProfile -File scripts/start_link.ps1 -Slicer bambu -Project artifacts/bambu/results/bridge-reverted.3mf
```

The companion keeps using port 8766 for OAuth callbacks and serves authenticated local update requests on `/v1/update`. It refreshes expiring OAuth tokens under the authentication lock. The slicer receives a separate local connection key through `OSL_COMPANION_FILE`; OAuth tokens and the application secret never enter the slicer or 3MF project. The connection key is generated when the companion starts and read afresh for each manual update.

Requests carry source identities, not caller-chosen output paths. The companion translates each initial part ID to an immutable current microversion, downloads and validates geometry, and returns the complete batch. It never returns stale cached geometry after a failed request. Remote links no longer depend on the old local snapshot path. Local experiment links retain their existing file-based behavior.

The slicer makes the local HTTP request on a worker thread with a modal progress dialog. Cancel discards the result. There is a 120-second request limit, a 32 MiB response limit, and a maximum of 16 distinct Onshape sources per command. Duplicate object copies share one fetch but retain independent transforms. All replacements are prepared before committing any object. Queued duplicate geometry commands are ignored while a command or its error dialog is active. Revert does not make a network request.

The transport connects only to IPv4 loopback, disables proxies and redirects, and sends no CAD credentials. The service validates Host and the local key, rejects browser Origin headers, and does not allow cross-origin requests. A simultaneous request from another slicer gets a visible busy error and can be retried. Geometry is applied only by the slicer that requested it.

## Verification

Both native builds fetched the live 60 mm revision from the saved 50 mm project with its legacy snapshot path deliberately set to a nonexistent file. The saved results matched the validated export, retained the 37° rotation, position, plate, material and tested process settings, and showed zero reference drift across 144 unchanged vertices. Stopping the companion still allowed Revert; a subsequent Update reported a connection error. Saved geometry and setup matched the original after that failure. No slicing or printing command was issued, no slicing guard error appeared, and the saved projects contain no toolpaths.

Compare the retained projects with:

```powershell
python scripts/verify_cad_update.py orca --bridge --include-revert
python scripts/verify_cad_update.py bambu --bridge --include-revert
```

Screenshots and detailed reports are under `artifacts/onshape/export-test/`. The Python suite has 23 passing tests, including seven service tests for batch failures, stale-cache rejection, refresh failure, account mismatch, busy handling and HTTP authentication/bounds and exclusive port ownership on Windows.

This remains a development build on Leo's machine. The native Onshape Add to slicer action, installation on a clean machine, configured parts, multi-Part-Studio acceptance tests and optional automatic geometry updates remain separate work. The old credential-entry window is still an authentication-only tool; close it before starting this companion. No public binary distribution has been made.

The final build also passed cancellation with a deliberately delayed local test response in each slicer. Two queued Update commands produced only one request per slicer. Both native dialogs reported cancellation with existing geometry retained. Both development launchers were exercised, including starting a fresh companion and reusing it from the other slicer.

Final rebuilt DLLs repeated the live Update successfully after the startup fixes. The saved `artifacts/{orca,bambu}/results/bridge-final.3mf` projects exactly match the verified geometry, source history, transforms, plate membership and object settings. Final DLL hashes and compact results are in `experiments/results/{orca,bambu}/companion-bridge.json`. The two test projects remain open at the 60 mm revision.

The subsequent toolbar-button test passed separately in both rebuilt slicers. A physical click updated two linked objects on plates 1 and 2 from the saved 50 mm geometry to the current 30 mm CAD snapshot. Their independent 37-degree and -20-degree rotations, positions, material selection, layer height, infill and different wall counts survived. Both previous meshes were retained, unchanged reference vertices had zero drift, and neither saved project contains toolpaths. The native no-slicing guard reported no failure. A concurrent update attempt in Orca initially received the expected busy error; retrying after the companion became free passed. This does not establish a two-click maximum for error recovery or simultaneous updates from multiple slicers.

The test projects are `artifacts/{orca,bambu}/results/button-update.3mf`; separate reports and DLL hashes are in `experiments/results/{orca,bambu}/update-button.json`. Run `python scripts/verify_button_update.py orca` and the same command with `bambu` to compare the saved results. Screenshots are in `artifacts/onshape/export-test/*-button-updated.png`. These checks used seeded plate membership and did not repeat normal user plate dragging. The earlier bridge reports describe the preceding build; the button reports identify the currently installed experimental DLLs.

# Onshape export experiment

The test account's Part Studio URL identified one native solid, Part 1, with no configuration parameters. Its initial part ID was `JHD` at microversion `997441c4a1b9159531e64e85`. The live export passed on September 10, 2026, local time.

The binary STL contains 152 vertices and 304 triangles. Its bounds are `[-25, -12.5, -7.5]` to `[25, 12.5, 7.5]` mm, matching Onshape's bounding-box API to floating-point precision. It is closed, consistently oriented, nondegenerate, and has positive volume. Vertices retain the CAD coordinate frame; the exporter does not center or place them on the bed.

The synchronous STL endpoint redirects to an Onshape modeling server. The client only forwards the token to an HTTPS `cad[-region].onshape.com/modelexport` URL after checking the document, element, microversion, part ID, millimeter units, and unit scale. This follows Onshape's [synchronous export protocol](https://onshape-public.github.io/docs/api-adv/translation/).

Every geometry read uses an immutable `/m/<microversion>` path. The source identity embeds the document, workspace, Part Studio, fixed configuration, and initial part ID/microversion. The existing native slicer experiment preserves this identity string in object metadata. Display names and filenames do not identify the source. Updates translate the initial part ID to the selected target microversion and accept exactly one `OK` result. See [ID translation](https://onshape-public.github.io/docs/api-adv/associativity/).

## Run

Credentials and encrypted OAuth tokens must already be configured for the test account. The current command requires an unexpired access token; use the local authentication page's refresh button if needed.

```powershell
python -m companion.export_part --url "<Part Studio workspace URL>" --output artifacts/onshape/linked-part
python -m companion.export_part --update artifacts/onshape/linked-part/current.json --output artifacts/onshape/linked-part
```

The first command selects a part automatically only when there is exactly one. Configured sources, assemblies, composite parts, and mesh imports are rejected in this first experiment. These limits are narrower than the planned V1 scope.

Validated exports are cached under content hashes. `current.json` is replaced atomically after download, mesh validation, and bounding-box checks. A repeated live export of the same microversion passed. A deliberately unresolved part ID returned an API translation error; the update failed and left `current.json` byte-for-byte unchanged. Reports and initial API responses are in `artifacts/onshape/export-test/` and `artifacts/onshape/linked-part/`.

Seven focused tests cover fixed coordinates and units, malformed/open/reversed meshes, pinned requests, source identity, split/missing translations, credential-safe redirects, and failed writes retaining the active snapshot.

## First real part in each slicer

The portable experimental OrcaSlicer and Bambu Studio builds each imported `artifacts/onshape/linked-part/current.json` through their native Add linked part command. The block with a through-hole appeared on plate 1. Normal project saves produced `artifacts/orca/results/onshape-first.3mf` and `artifacts/bambu/results/onshape-first.3mf`. Inspection of each saved archive found exactly one link with the exported source identity and microversion, and no G-code. Separate screenshots and import reports are in `artifacts/onshape/export-test/`.

The prototype still labels imported objects "Linked asymmetric part". That display-name limitation does not change the stored source identity. The test used isolated profiles and left Leo's existing slicer sessions untouched.

Both test processes were closed and each saved project opened in a fresh process. The real part appeared correctly in both, with Slice available and Print disabled. Reopen screenshots are saved separately.

## Real CAD update and Revert

Leo changed the part's length from 50 to 60 mm in the test account. The companion translated the original part ID to the new microversion `68d76e4be86db2bb4b9c0ae3` and exported a validated 60 × 25 × 15 mm mesh. Its X bounds changed from ±25 to ±30 mm. The source identity stayed fixed.

For each slicer, an isolated copy of the first saved 3MF was prepared with a 37° Z rotation, position `[108, 97, 7.5]` mm, plate 1, extruder 1, 0.16 mm layer height, four walls, and 22% infill. Placement and overrides were seeded in the test archive, then loaded by the real application. This preparation does not test manual dragging or settings entry. Update and Revert used the native integration commands; saves used the application's normal Save action.

| Check | OrcaSlicer portable experiment | Bambu Studio portable experiment |
| --- | --- | --- |
| Updated geometry matches the validated 60 mm export | Pass | Pass |
| Rotation, position, plate membership and object settings retained | Pass | Pass |
| Material type, preset and color retained | Pass | Pass |
| Unchanged reference vertices checked | 144 | 144 |
| Maximum reference drift | 7.96 × 10⁻¹⁰ mm | 7.96 × 10⁻¹⁰ mm |
| Updated project closed and reopened in a fresh process | Pass | Pass |
| Native Revert after reopening restores the exact original mesh | Pass | Pass |
| Revert retains setup and records automatic updates paused | Pass | Pass |
| Geometry commands triggered the native slicing-start guard | No | No |
| Saved projects contain toolpaths | No | No |

The guard checks for a running background process and any increase in slicing-start calls during geometry commands. Neither application displayed a guard failure; both kept Slice available and Print disabled. No slicing or printing command was issued. Invalidation of previously generated toolpaths was established by the earlier local experiment and was not repeated on this CAD part.

Snapshots before Update, after Update, and after Revert are retained as `artifacts/{orca,bambu}/results/onshape-{before-update,updated,reverted}.3mf`. Each updated project contains its previous geometry; Revert succeeded after loading that geometry from disk. Both test processes were closed after saving the results. The companion's current snapshot remains the 60 mm CAD revision. Revert only changed the slicer geometry.

The independent saved-project comparison checks triangle coordinates against the actual exported mesh, retained transforms and settings, source identity, revision history, plate membership, and unchanged reference vertices. Run:

```powershell
python scripts/verify_cad_update.py orca --include-revert
python scripts/verify_cad_update.py bambu --include-revert
```

Separate reports and screenshots are in `artifacts/onshape/export-test/`; compact results are in `experiments/results/{orca,bambu}/onshape-cad-update.json`.

The complete Onshape-to-slicer workflow remains unfinished. Configuration handling, the native Onshape context action, the initial Add delivery, and real CAD deletion/split scenarios remain to be demonstrated. This CAD edit grew symmetrically about its center; the asymmetric-growth check belongs to the earlier L-shaped local experiment. Plate moves and edits made after Update were also covered there, not repeated here. The companion made no CAD changes.

The subsequent [manual companion bridge](manual-update.md) now fetches geometry directly from the slicer Update command, including when the legacy snapshot file is missing.

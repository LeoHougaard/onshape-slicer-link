# Local experiment results

The local geometry milestone passed in both custom native builds on September 10, 2026. This proves the bounded local experiment, not an end-to-end Onshape connection or a stock-slicer plugin.

| Check | OrcaSlicer | Bambu Studio |
| --- | --- | --- |
| Stock extension inspection | Live model mutation missing from inspected Python host API | No general model-editing extension found in inspected source |
| Two asymmetric local revisions | Fixtures pass closed-mesh, orientation, volume, and fixed-reference checks | Same shared fixtures |
| Native replacement and setting retention | Passed | Passed |
| Native 3MF round trip and Revert | Passed | Passed |
| Live add to active plate | Passed | Passed |
| Rotation and plate move retained | Passed, plate 2 | Passed, plate 2 |
| Live update and dedicated Revert | Passed | Passed |
| Fresh-process reopen and update | Passed | Passed |
| Failed local update retains project | Passed | Passed |
| Geometry command starts slicing | 0 attempts | 0 attempts |
| Previously sliced toolpaths invalidated | Passed, no new slice started | Passed, no new slice started |
| Separate portable folder: launch and local update/Revert | Passed | Passed |

Source pins and API findings are in [extension-audit.md](extension-audit.md). The experiment code and build notes are in [build.md](build.md).

Both applications also launched from separate portable folders with copied resources, runtimes, and isolated profiles. Each reran the local add/update/Revert/failure scenario successfully using the same application DLL as the verified build. Fresh-process reopening and real toolpath invalidation were checked in the build folders; they were not repeated in the portable folders. Compact reports are retained in `experiments/results/{orca,bambu}/`. These portable checks ran on the development machine, not a clean Windows installation.

The test command moves the object through native model APIs. Its object-tree display can retain the old plate label until reopening, and its camera remains on the first plate. Saved projects reopen with the correct plate assignment. Normal user-driven plate moves still need a separate interaction check before claiming the complete workflow; the local command's display refresh also needs cleanup.

Both native test executables passed on September 10, 2026. Each linked its own pinned slicer's real model and 3MF implementation. Both measured 0.0 mm drift at the unchanged source reference vertex. Checks cover independent copies, same-name unlinked objects, object and volume extruder assignments, layer height, wall count, infill, rejected identity/mesh changes, and Revert after subsequent transforms and settings edits and a 3MF round trip. Reports are in `artifacts/{orca,bambu}/native-results.json`.

The initial 3MF checks failed in both slicers. Their importers recentered the mesh and folded single-volume offsets into instance transforms. The experiment now preserves the source frame when reading linked objects. Ordinary unlinked imports retain upstream behavior.

Both live GUI experiments passed. Each added revision 1 through the native import path, rotated it 37 degrees, moved it to a new second plate, applied revision 2, saved, moved it again and changed its wall count, reverted, and rejected an invalid snapshot. Both measured 0.0 mm reference drift and 0 calls to the instrumented slicing-start function during geometry commands. Both applications were visually inspected on plate 2 and closed through their normal Save prompt. GUI reports and screenshots are in `artifacts/{orca,bambu}/results/`.

Each saved project was then opened by a fresh process. Plate 2 was manually sliced using the actual Slice plate button. The native check updated and reverted the reopened object, verified retention of both transforms, plate 2, 7 walls, 0.16 mm layer height, 27% infill, and extruder 1, and asserted that previously valid toolpaths became invalid. Both reported zero slicing-start attempts during Update/Revert. Screenshots show the completed manual slice and the invalidated preview with slicing available and printing disabled. Printing was never invoked.

Tested geometry: a closed L-shaped prism, 6 mm tall, with one arm growing from 32 to 46 mm. Native tests exercise three-axis rotation; live plate tests use a 37-degree Z rotation. Growth through the bed, collisions, painted/cut objects, arbitrary self-intersections, large exports, and clean-machine installation remain unverified. Do not expand this result to those cases.

The local experiment does not test Onshape authentication, exports, Part Studio selection, configuration identity, network failures, or missing CAD parts. Subsequent test-account authentication and a real CAD update/Revert now pass separately; see [the Onshape export experiment](export-experiment.md) for evidence and remaining limits.

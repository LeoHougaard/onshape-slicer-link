# Local geometry experiment

The first milestone is replacement of two local revisions of an asymmetric part in each slicer, using an installable integration or a small source change. A passing library test alone does not establish application compatibility.

1. Inspect exact installed versions and supported extension operations. Record source commits and missing operations separately.
2. Generate two watertight meshes with a shared CAD origin and an off-center dimensional change. Include unchanged reference vertices to measure movement under rotation.
3. Implement the smallest viable native replacement route. Retain the object, its current transforms, plate assignment, material, and basic object overrides. Validate before mutation. Retain previous geometry for a dedicated Revert.
4. Verify in each real application with isolated profiles and test projects. Save and reopen; move plates and rotate after an update, then revert; exercise malformed geometry. Check that no slicing or printing starts.
5. Record measured results and remaining gaps. Proceed to Onshape only after both application experiments pass.

Supported settings to test initially: extruder/material selection, layer height, wall count, and sparse infill density. Reject painted or cut objects for this experiment.

The coordinate rule is to preserve the original source frame and all current slicer transforms. Do not recenter each revision. Reference-frame retention passed in both applications. Bed-crossing notices still need implementation and validation; geometry must not move silently.

## Progress

- Repository created; original brief preserved.
- Both slicers installed. Orca registry reports 2.5.0 and its profile reports 2.5.0-dev. Bambu reports 02.08.02.61.
- Two other custom Orca sessions and an unsaved Bambu session are open. Use separate profiles and test instances.
- Source/API inspection complete. Stock extension APIs do not provide the required writes; the experiment uses small native source changes.
- Shared replacement logic passes against both actual native model libraries, including project round trips and dedicated Revert. Initial reference-frame failures on reopening were fixed and rechecked.
- Both live application experiments passed, including normal save/close and fresh-process reopen. Manually generated toolpaths were invalidated without another slice starting. See `results.md` for scope and evidence.
- Test-account OAuth and immutable snapshot export pass. One real Onshape part was imported and saved with its source identity in each experimental slicer. See `export-experiment.md`.
- A real 50 → 60 mm CAD update passes in both portable slicers with retained rotation, placement, plate and tested settings. Revert also passes after saving and reopening the updated projects.
- The manual slicer Update command now fetches geometry through the companion in both builds, including with a missing legacy snapshot file. Offline Revert and visible connection-failure handling pass.
- Next: connect the native part-context Add handoff, then validate multiple Part Studios, configurations and broader failure handling. Installer and automatic-update work remain later stages.

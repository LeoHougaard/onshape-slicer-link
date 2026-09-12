# First user test

Use the replacement test Onshape account and an ordinary solid part. Complete
the hosted-app setup first. Both OrcaSlicer and Bambu Studio must be official,
unmodified installations; the old experimental launchers are not part of this test.

1. Install the new helper. Connect to the hosted app, choose a project folder,
   and pair this computer in the browser.
2. In an Onshape Part Studio, open Slicer Link. Choose and link a solid part,
   select this computer, refresh, and open the helper. Save the files.
3. Import its STL once into the slicer. Rotate and position it, choose the print
   settings you want, and save a `.3mf` in the same folder.
4. Change one CAD dimension. Refresh from Onshape and save the new files using
   the helper. Select the object in the slicer and use **Reload from disk**.
5. Check the shape, position, settings, supports, and seam painting. Save and
   reopen the project, then try another refresh and reload.
6. Try **Restore previous geometry** in the helper and reload in the slicer.
   This should restore the previous downloaded STL.

For a second part or another plate, repeat using the slicer's own selection and
reload commands. Copies of the same imported part use the same source file.

Nothing should slice or print until you request it. If the slicer's own automatic
slicing preference is enabled, the helper does not change it; disable that preference
when you want fully manual slicing.

Please report which slicer/version you used, the step that failed, and the visible
error. Keep the project folder for diagnosis. Do not send credentials or `.env.server`.

Linux testing is optional and is not required for this handoff.

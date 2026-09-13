# First local test

1. Open Slicer Link and choose the installed slicer you want to use.
2. Paste the test document's Onshape link and choose **Connect document**.
   Confirm its name, select the intended Part Studio, and link a solid part.
3. Click **Send / Update**. Confirm the part opens in the selected stock slicer.
   There should be no file-save dialog or manual STL import.
4. Arrange the part and change an object setting in the slicer. Edit its shape in
   Onshape, then click **Send / Update** again. No duplicate object should appear.
5. In the slicer, select the existing object and use **Reload from disk**. Check
   dimensions, placement, object settings, and any painted supports.
6. Save the slicer project. Use **Connect saved project** to select its .3mf,
   then Send / Update once. Reopen the project, make another CAD change, and
   repeat the update/reload. Report if the slicer cannot find its managed source file.
7. Close and reopen Slicer Link. Confirm that the document and slicer choices
   persist. Repeat with the other slicer if desired.

**Open selected parts again** is for a new slicer project or an object you have
removed. It intentionally imports again, so it can create duplicates.

The app does not slice or print automatically. Linux testing is optional and has
not been performed by the agent.

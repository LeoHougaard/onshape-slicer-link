# Check your first setup

Use this checklist after the [setup guide](helper-setup.md). It covers the local
Windows test release. Choose a simple test part; no printer is required.

- [ ] Choose one slicer and open an empty project. Link one solid Onshape part
  and click **Send / Update**. The part appears without manually exporting or
  importing an STL.
- [ ] Move and rotate the part in the slicer. Change a setting such as infill.
  Note the position and setting so you can compare them after reloading.
- [ ] Change an obvious dimension in Onshape. Click **Send / Update** again.
  There should still be only one object in the slicer.
- [ ] Select that object, right-click it, and choose **Reload from disk**.
  Check the new shape, position, orientation, and print setting. Report any
  unwanted shift. Native reload can recenter changed geometry.
- [ ] Save the slicer project as `.3mf`. In Slicer Link, use **Connect saved
  project** and click **Send / Update** once to prepare its source files.
- [ ] Close and reopen that project. Make another CAD change, send, and reload.
  Confirm the slicer finds its source file and the object updates.
- [ ] Use **Stop local app** under **Connection & API use**, then reopen
  **Onshape Slicer Link** from Start. Your slicer, document, and links should
  still be selected.

If you try multiple objects or plates, check each updated object. Review painted
supports and materials separately; this checklist does not establish that every
kind of setting survives a geometry change. Slicing and printing remain manual.

For a failure, [open an issue](https://github.com/LeoHougaard/onshape-slicer-link/issues)
with the failed step, expected result, actual result, and your Windows and slicer
versions. Omit secrets and private CAD files. Linux testing is not required.

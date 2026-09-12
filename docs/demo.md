# Desktop demo

The [short cut](../artifacts/demo/onshape-slicer-link-demo-short.mp4) is 11.47 seconds. Idle pauses are reduced to about one second; the CAD edit, Update and Revert remain at their original speed. It is silent, uses H.264 with yuv420p for playback compatibility, and preserves the original recording. The retained source intervals are in `artifacts/demo/short-edit.json`.

The silent recording is [onshape-slicer-link-demo.mp4](../artifacts/demo/onshape-slicer-link-demo.mp4). It is 58 seconds at 2560 by 1392 pixels. It shows the test Onshape account beside the experimental OrcaSlicer, changing the sketch dimension from 30 to 60 mm, clicking Update linked parts, and using Revert linked geometry. The recording is a continuous desktop capture with the idle tail removed. There is no audio track.

The Update command now uses the existing top toolbar beside Undo/Redo in both slicers. It no longer consumes space beside Slice/Print or uses a split-button shape. A native click passed separately in Orca and Bambu. Orca's button was also visually checked at a 1130-pixel window width, where the earlier placement was clipped.

The saved Orca projects measured 30, 60 and 30 mm before Update, after Update and after Revert. Rotation, position, plate membership and object settings matched; unchanged reference vertices had zero drift. The projects contain no toolpaths and the native no-slicing guard reported no failure. Evidence is in `artifacts/demo/verification.json` and `orca-demo-{before,updated,reverted}.3mf`. Bambu independently updated its 50 mm fixture to the restored live 30 mm geometry; see `artifacts/demo/bambu-toolbar-verification.json`.

After recording, the Onshape test sketch was restored to 30 mm through Undo and Orca was refreshed and saved. The ready project is `artifacts/orca/results/demo.3mf`. The original pre-demo Orca project was preserved in `artifacts/demo/orca-before-demo.3mf`.

The two older Continuous Extrusion/Infill Orca sessions were closed normally with their modified settings saved. The Infill settings were saved as `Continuous Infill - preserved before Onshape demo`. The previously untitled stock Bambu project was saved to `artifacts/demo/bambu-unsaved-preserved.3mf` before closing it. Build tools and the recorder have finished. Only the demo Orca instance and the companion need to remain running for this integration.

These are experimental modified builds. Standard installed slicer binaries were not replaced. Mouse and keyboard input were used to test and record the native integration, not to implement geometry replacement.

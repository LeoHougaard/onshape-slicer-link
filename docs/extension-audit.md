# Extension inspection

Inspected September 10, 2026. This is source evidence, separate from application test results.

| Target | Installed version evidence | Inspected source | Finding |
| --- | --- | --- | --- |
| OrcaSlicer | Windows uninstall registry: 2.5.0. Existing profile: 2.5.0-dev. Binary has no ProductVersion resource. | `a49b8927088cde075c8ccfc7dcaf1bedc3b52af9` | Python host bindings expose reading the live model, but no object insertion, live mesh replacement, metadata transaction, or toolpath invalidation command. |
| Bambu Studio | Windows uninstall registry and existing profile: 02.08.02.61. | `926a7192574bcb9b3a732e1ec59a46d79cb45466`, tag `v02.08.02.61` | No equivalent general model-editing plugin interface found. Networking plugin integration does not provide the required model operations. |

The preferred stock add-on route is not established. The current experiment uses separate native builds. It does not modify the installed programs or use keyboard/mouse automation as the integration.

Keep the slicers as close to stock as possible. Prefer a supported add-on with normal slicer upgrades; retain only the native hooks needed for geometry replacement, project persistence, and manual update controls while that route is unavailable. Keep Onshape authentication and export in the shared companion. The experimental builds are a fallback, not a decision to maintain a separate slicer product. A stock upgrade does not currently inherit this integration.

Orca evidence: [host application bindings](https://github.com/OrcaSlicer/OrcaSlicer/blob/a49b8927088cde075c8ccfc7dcaf1bedc3b52af9/src/slic3r/plugin/host/PluginHostApp.cpp), [model bindings](https://github.com/OrcaSlicer/OrcaSlicer/blob/a49b8927088cde075c8ccfc7dcaf1bedc3b52af9/src/slic3r/plugin/host/PluginHostModel.cpp), and [plugin documentation](https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugin_development).

Bambu evidence: [GUI sources](https://github.com/bambulab/BambuStudio/blob/926a7192574bcb9b3a732e1ec59a46d79cb45466/src/slic3r/CMakeLists.txt) and [Plater implementation](https://github.com/bambulab/BambuStudio/blob/926a7192574bcb9b3a732e1ec59a46d79cb45466/src/slic3r/GUI/Plater.cpp).

## Proposed narrow hook

Expose one transaction on the UI thread that accepts validated geometry in a stable source frame and updates an existing object. The transaction must preserve object identity, instance transforms, volume transforms, configuration, and plate membership; record preceding geometry; invalidate toolpaths; and never schedule slicing.

The experiment adds a small `ModelVolume::swap_prepared_geometry` operation, project-persisted metadata, and native menu commands. Most logic is shared in `experiments/LinkedGeometry.hpp` and `experiments/LinkedGeometryGui.inc`. Orca could later expose that transaction through its Python host API. Bambu still needs a native entry point.

Existing Replace/Reload functions are useful references, but they also apply bed-contact changes and general Undo. They are not sufficient proof of the requested Revert and anchoring behavior.

Orca also has an automatic reslice timer. The experiment disables it and background slicing while a linked object exists in the project. This intentionally keeps slicing manual after subsequent plate edits too.

## Experiment limits

- Local JSON snapshots replace Onshape exports. Source IDs and revisions are explicit and independent of filenames and display names.
- Only one closed, consistently oriented, unpainted volume is supported. Cuts and variable layer settings are rejected. Arbitrary self-intersection detection is still missing.
- Hex-encoded metadata includes the preceding mesh in the project. This is a bounded experiment format, not the final format for large CAD exports.
- The experiment's Revert command reverts each linked object that has preceding geometry. It does not rewind placement or settings.
- No stock-plugin runtime replacement has been demonstrated. Source findings must not be described as a successful installable stock integration.
- A private Onshape app, authentication, networking, packaging, and automatic geometry updates remain gated on the local experiment.

# Onshape Slicer Link

Link Onshape source geometry to objects in OrcaSlicer and Bambu Studio while the slicer retains arrangement and print settings.

The local geometry experiment passes in separate custom builds of OrcaSlicer and Bambu Studio: placement, plate assignment, settings, Revert, project reopening, and invalidation of real toolpaths without starting another slice. See [measured results and limits](docs/results.md).

Live Onshape authentication, token refresh, and a real 50 → 60 mm CAD update pass in both experimental slicers. Rotation, placement and tested settings survived, and Revert restored the original geometry after saving and reopening. The slicer's manual Update command now fetches CAD through the companion. See [manual update instructions](docs/manual-update.md) and the [export experiment](docs/export-experiment.md). The native Onshape Add action and an installer remain unfinished. The inspected stock extension APIs lack the required model-editing operations; this prototype uses native source changes.

The [private-app setup and authentication probe](docs/onshape-next.md) include a local credential-entry window. Leo's account uses `cad.onshape.com`.

See [the project brief](PROJECT_BRIEF.md) and [the experiment plan](docs/experiment-plan.md).

Updates must never initiate slicing or printing. Source identity belongs to the object and must survive plate moves and project saves. Failed updates must leave the current geometry intact.

In the experimental builds, click **Update linked parts** next to **Undo/Redo** in the top toolbar to update all linked objects across all plates in one click. This passed separately in both slicers with two differently rotated objects on separate plates. Stock slicers remain the preferred delivery target; these separate custom builds are the current fallback and need rebuilding for slicer upgrades.

Code in this project is licensed under AGPL-3.0-only. Slicer source retains its upstream license and notices. No modified slicer binaries are distributed yet.

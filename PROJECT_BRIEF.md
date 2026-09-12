> Current direction: the stock-slicer application in [docs/architecture.md](docs/architecture.md)
> supersedes this historical prototype brief. Both slicers remain unmodified;
> native Reload from disk replaces the custom in-slicer update engine.
> Linux testing is waived, and Leo will do the broader hands-on test.

# Onshape Slicer Link

Project brief and handoff, September 10, 2026.

## Purpose

Build a persistent link between a part selected in Onshape and an object on a build plate in OrcaSlicer or Bambu Studio. Leo rapidly iterates on CAD and prints parts. Repeated exporting, importing, and restoring the print setup create friction and opportunities to print the wrong geometry.

The desired interaction is: select a part in Onshape, choose **Add to slicer**, arrange it normally, then use **Update linked parts** inside the slicer when the CAD changes. The geometry updates while the slicer preserves the arrangement and basic print settings.

This is a new project, separate from Leo's existing Onshape gear FeatureScript project. No integration code has been written, and no end-to-end workflow has been tested. This brief records the planning discussion.

## User and environment

- Initial user: Leo, on Windows.
- CAD: Onshape in a browser.
- Target slicers: standard OrcaSlicer and Bambu Studio. Both are required targets; supporting one does not establish support for the other.
- Prefer a normal installable add-on so routine slicer updates remain straightforward. A customized slicer build is an acceptable fallback, already accepted by Leo.
- Develop and distribute the integration in compliance with AGPLv3. The proposed approach is open-source integration code, with corresponding source and build instructions for distributed slicer changes. Check dependency and distribution obligations against the actual implementation.

## Confirmed workflow and decisions

1. Inside an Onshape document, select a part in any Part Studio tab and choose **Add to slicer**. Different Part Studios in the same document must work. Assembly selection is optional future work.
2. Add the selected part directly to the active plate in the open slicer project.
3. The user can rotate and position it, create new plates, and move it between plates. These actions must not break the source link.
4. **Update linked parts** retrieves current source geometry and updates linked objects in their current locations. It must not reconstruct the entire project or move objects back to their original plates.
5. Manual updates are the default. An optional automatic geometry-update mode is desired, after the manual path is reliable.
6. Support reverting the most recent geometry update. A browser for historical revisions is not required for V1. The exact mechanism, native Undo or a dedicated Revert command, is not yet chosen.
7. Updating geometry must invalidate affected slicing results. **Do not automatically slice.** Leo explicitly rejected this because slicing can take a long time. This also applies to automatic geometry updates.
8. Never start a print automatically. Printing and slicing remain user actions.
9. Focus V1 on orientation, plate placement, and basic object settings. Painted supports, painted seams, and slicer cuts are deferred.
10. Use a native Onshape app, initially private and installed on Leo's account. Public App Store distribution can be considered later.

## Proposed details to validate

These are design defaults from the discussion, not separately settled requirements in every detail:

- Save source-link metadata in the slicer project so links survive closing, reopening, and moving objects between plates. A cache alone must not be the only record of the link.
- Copies share a source link but keep independent orientations, positions, and plate assignments. An update normally refreshes all copies following that source.
- Preserve basic settings such as material assignment and per-object process overrides. Enumerate the exact supported settings during the prototype and verify them.
- Capture the selected configuration when adding a part. Later changing the configuration displayed in the Onshape browser should not silently switch the linked object to a different variant.
- Track the selected workspace's current geometry, and record the exact source snapshot used for each successful update. Do not rely on part names or filenames as identity.
- Revert restores the preceding geometry without undoing unrelated plate edits. The interaction with later edits and native Undo needs testing.
- After a revert, pause automatic updates for that source so they do not immediately reapply the change the user just rejected.
- Preserve current rotation and placement, and detect collisions or out-of-bed geometry caused by growth. Do not silently rearrange the plate.

## Proposed architecture

### Native Onshape app

Register an OAuth application and add a part-context action named **Add to slicer**. Pass the source document, workspace, Part Studio, part ID, and configuration through the handoff.

Use a private App Store entry for installation and testing on Leo's account. Onshape documents private entries and self-subscription for individual accounts. Public publication is not needed to begin testing.

The app supplies part selection and authorization; it does not by itself update a desktop slicer's live project. Confirm the browser-to-desktop handoff before committing to infrastructure. Depending on the supported action route, a reachable HTTPS endpoint or small relay may be necessary. Onshape App Store registration does not host the application code for us.

### Local companion

A small local service handles Onshape authentication, geometry export, caching, and communication with the active slicer. Python packaged as a Windows application is the proposed starting choice, not a fixed requirement.

Keep credentials in appropriate local credential storage and out of project files. Validate incoming requests and protect local communication. Request only the Onshape access the workflow requires.

Use one shared implementation for Onshape communication and revision handling. Avoid building a large dashboard or a separate project-management application.

### Slicer integrations

Each slicer needs an integration that can add an object to the active plate, retain its source metadata, replace its geometry, preserve object and instance state, expose Update/Revert, and invalidate toolpaths without starting slicing.

Prefer supported extension mechanisms. If they lack an operation, investigate a small upstreamable extension hook. A narrow custom build is the accepted fallback. Do not promise a universal plugin or rely on brittle mouse/keyboard automation as the finished solution.

The documented general Orca plugin host access is currently read-only. Experimental slicing-pipeline access does not establish that a plugin can safely replace a live plate object and participate in its undo and save behavior. Bambu compatibility also needs independent proof.

## Update behavior

1. Resolve the linked source and configuration at a specific Onshape snapshot.
2. Export and validate the new geometry before changing the live object.
3. Preserve current placement, plate membership, supported settings, and the previous geometry.
4. Replace geometry using the slicer's supported model-editing mechanisms, maintaining consistent coordinates between exports.
5. Commit the new source snapshot and invalidate affected toolpaths without triggering slicing.
6. If the operation fails, retain the prior object intact and show that the update failed. Never label a failed or unchecked update as current.

Do not silently relink a deleted or replaced CAD part to a similarly named part. Surface broken links for review. Detect unsupported slicer edits before updating and explain the limitation instead of silently discarding the user's work.

"Current" means verified against a source snapshot at a stated check time. With manual updates, old geometry can be intentional, especially after Revert. The precise freshness display and any pre-print notice remain open. Do not promise to prevent old jobs being printed through printer history or other workflows outside this integration.

## Acceptance tests

Run the core tests in both target slicers and record their exact versions.

1. Add parts from two Part Studio tabs to the active plate. Include identical display names to verify source identity is unambiguous.
2. Rotate and position linked parts, create another plate, and move a linked object onto it.
3. Change CAD dimensions and update. Verify the geometry against the selected source and verify retained orientation, placement, plate membership, and supported object settings.
4. Use an asymmetric shape and an off-center dimensional edit to expose coordinate-origin errors that a centered cube would hide.
5. Exercise the proposed copy behavior, preserving independent placements while updating shared geometry.
6. Revert the latest update and verify the previous geometry returns without losing the intended arrangement.
7. Save, close, reopen, and update again. Verify links and the supported settings survive.
8. Interrupt an export, lose network access, revoke source access, and remove a source part. Verify the existing project remains intact and failure is visible.
9. Verify configuration selection does not silently change and unrelated source edits do not replace the wrong object.
10. Verify updates invalidate stale toolpaths but never start slicing or printing.

Inspect the real slicer result. A successful download, changed mesh file, or passing unit test alone does not prove this workflow works.

## Build order and first experiment

Start with the slicer integration, before the Onshape UI, cloud infrastructure, or installer.

Use two local revisions of one asymmetric part. In standard Orca, attempt to replace its geometry through an installable integration while preserving rotation, position, plate assignment, basic settings, revert behavior, and persistence after reopening. Repeat in standard Bambu Studio. This experiment should settle whether supported extension mechanisms are sufficient.

If that route fails, identify the exact missing operations and test the smallest source change needed. Do not spend weeks polishing a companion application while assuming the live-project update will work later.

Once the integration route is demonstrated:

1. Add Onshape authentication and snapshot-based export to the local companion.
2. Add the private native Onshape action and prove delivery to the active slicer plate.
3. Implement persistence, failure handling, and Revert; run the acceptance tests.
4. Package installation and document supported slicer versions and upgrade behavior.
5. Add optional automatic geometry updates without changing the manual slicing policy.

## Open questions and risks

- Which installed/stable versions provide sufficient extension hooks, and what must be changed if they do not?
- Can both slicers retain custom source metadata through normal project saves and upgrades?
- How should updates preserve anchoring and bed contact when a rotated part changes size? Keeping a transform unchanged alone may not produce the expected physical placement.
- What should happen when no slicer is running, or multiple slicers or projects are open? Only delivery to an unambiguous active plate has been agreed.
- What are the exact scopes, account setup, API limits, and hosting needs for Leo's private Onshape app?
- Can part identity survive the CAD operations Leo normally uses? Handle uncertain identity explicitly, including split, merge, and delete/recreate operations.
- How should Revert behave after subsequent plate edits, and what persists across closing the application?
- How will optional auto-update pause around user edits, updates in progress, and intentional reverts?

## Alternatives not selected

- Repeated manual exports and reimports do not meet the intended workflow.
- Regenerating entire slicer projects risks overwriting the user's plate work.
- A browser extension that depends on scraping Onshape's UI is not the preferred selection mechanism; native extensions provide an official route.
- A custom slicer fork is a fallback because ongoing upgrade maintenance matters to Leo.
- Automatic slicing was explicitly rejected. Advanced support-paint transfer and revision-history browsing are deferred.

## Verified references

Documentation reviewed September 9 and 10, 2026. These establish available building blocks, not a tested end-to-end integration. Verify them against the versions selected for development.

- [Onshape extensions and part context-menu parameters](https://onshape-public.github.io/docs/app-dev/extensions/)
- [Private Onshape app registration and self-subscription](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm)
- [Onshape OAuth authorization](https://onshape-public.github.io/docs/auth/oauth/)
- [Onshape export APIs](https://onshape-public.github.io/docs/api-adv/translation/)
- [Onshape change notifications](https://onshape-public.github.io/docs/app-dev/webhook/)
- [Orca plugin development and current host-access limitations](https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugin_development)
- [Orca source repository](https://github.com/OrcaSlicer/OrcaSlicer)
- [Bambu Studio source repository](https://github.com/bambulab/BambuStudio)

## Handoff to a new project session

Read this brief before choosing an implementation. Preserve the manual slicing decision, support for both slicers, independent plate arrangement, private native Onshape app, and preference for standard slicer installations. Distinguish confirmed decisions from proposed defaults and unresolved technical questions.

The next implementation step is the bounded local-geometry experiment above. Report what was actually demonstrated in each slicer, any missing extension operations, and the smallest viable integration route. Implementation has not begun.

# Local application plan

Current direction, September 12, 2026. No paid hosting is allowed. The user wants
easy connection to a specific Onshape document and an independently updatable,
unmodified slicer. The quick save-file test is superseded by the local app.

## Outcome and verification

- [x] One local app with a packaged runtime and no hosted setup.
- [x] Detect installed slicers, offer a native executable picker, remember choice.
- [x] Accept Onshape document links; display document and Part Studio names;
  remember the exact workspace and selected tab without idle CAD requests.
- [x] One Send / Update action manages files and opens new parts in the chosen
  stock slicer. Verify direct import in both stock Windows applications.
- [x] Updates preserve stable source paths and do not reimport duplicate objects.
  Report native reload and interrupted-launch uncertainty honestly.
- [x] Connect a saved 3MF through a native picker; maintain source files beside
  it without rewriting the project or overwriting outside edits.
- [x] Migrate only the authorized replacement test account and cached exports.
- [x] Test document selection, browser send, restart/retry behavior, authentication,
  account isolation, file recovery, and saved-project source mirroring.
- [x] Inspect final packaged browser UI, verify the native picker, rebuild and
  install the Windows app, and verify the installed local server.
- [ ] Leo's broader project/reload testing. Linux execution is explicitly waived.

Embedding the app inside Onshape is still outstanding. This local release uses
its own browser window. No further hosting infrastructure is proposed.

Evidence: 35 Windows automated checks passed. Direct command-line STL imports in
both installed stock slicers were saved through their native Save commands and
the resulting 3MF model/source metadata was inspected. A live document-root URL
resolved its name, default workspace and Part Studio through the new resolver.
The core export and unchanged-cache behavior were verified earlier on the same
replacement account. No CAD model edits were made for these checks.

# Local Onshape embedding verification

Verified through the shared Windows browser on September 12, 2026, using the
authorized free test account. This is an integration experiment, not a release.

## Reproduce

Start the read-only local page from the repository:

```powershell
.\.venv\Scripts\python.exe -m scripts.embedded_probe
```

The private Onshape test application's **Slicer Link** extension has location
**Element tab** and action URL `http://localhost:8768/`. The account subscribed
to its private, free App Store entry. In an Onshape document, use the bottom
plus menu, Applications, Slicer Link. The existing test document already has
this application tab.

The existing OAuth application remains a Connected Desktop App with its
existing credentials, redirects and read scope. The private store entry is
marked Integrated Cloud App to expose the extension. This combination worked
in this account; it is not yet a validated installation procedure for other
accounts. Nothing was submitted for public App Store review.

## Observed result

The application iframe loaded the local HTTP page. Onshape supplied document,
workspace and application element context without a pasted URL. The native
**Choose Onshape parts** dialog returned these selections:

| Part Studio | Part | Configuration | Source CAD snapshot |
| --- | --- | --- | --- |
| Prism | Round test | `default` | `13a5435a132f26c8567dbe38` |
| The Second | Round | `default` | `13a5435a132f26c8567dbe38` |

Both cards appeared inside the Onshape application tab. Onshape messages
provided source IDs, part ID, configuration and snapshot. The local page has
no Onshape REST API calls or credential access. Onshape itself still makes
its usual browser requests. This experiment does not measure a complete
export/update workflow's API usage.

The browser reported a report-only frame policy warning for localhost, but
rendered the iframe and delivered picker messages. No security policy was
disabled. Broader browser compatibility remains unverified.

## Boundaries and unfinished work

- The existing Windows suite passed again after this experiment, 35 tests in
  9.86 seconds. Focused HTTP checks passed for page/static serving, health,
  framing policy, cache prevention, wrong-host rejection and POST rejection.
  Ruff passed for the probe script. These checks do not verify slicer behavior.
- The server binds only to `127.0.0.1`, accepts the exact `localhost:8768` host,
  permits GET/HEAD only and restricts framing to `https://cad.onshape.com`.
- The page accepts picker messages only from its Onshape parent and validates
  source IDs. This check is not authorization for future CAD requests; the
  production adapter must independently authenticate and authorize requests.
- Selections live in page memory. Reloading clears them. Copies, renamed
  objects, saved projects and durable link identity have not been implemented.
- Default configurations worked. Non-default configurations, versioned
  sources and cross-document selections have not been tested. The probe
  currently accepts editable workspace sources only.
- The picker closed after each selected part, despite requesting multiple
  selection. Opening it again accumulated the next source in the page.
- No slicer runs inside this page. The desktop area explicitly says it is
  under development. Displayed snapshots describe selected CAD sources, not
  geometry loaded in a slicer.
- No Linux compatibility tests were run or are required at this stage.

The next verification is runtime startup after firmware SVM is enabled,
followed by native import/reload and saved-project preservation in both
unmodified slicers. See [the implementation plan](embedded-plan.md).

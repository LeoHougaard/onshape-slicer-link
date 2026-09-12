# Onshape authentication and handoff

The local slicer milestone passed. Live OAuth authorization, a document-list read, encrypted token storage, and token refresh passed on Leo's original account. Leo then requested all further testing use a separate account. The original probe has been stopped and its local credentials and tokens removed. Historical evidence is in `artifacts/onshape/previous-account-auth-results.json`. Authorization and live refresh now also pass with the replacement test-app credentials, recorded in `artifacts/onshape/auth-results.json`. The session endpoint returned no display-name fields, so the account selection is user-confirmed rather than independently matched to the name Robot Robot. Do not use the original account for further integration work. Export of one unconfigured test part and its first import/save in both experimental slicers now pass. See [export results](export-experiment.md). A real 50 to 60 mm CAD update and Revert after saving/reopening now pass in both experimental slicers. The native Onshape action remains unverified.

Leo confirmed the account uses `https://cad.onshape.com`, rather than an Enterprise address. The setup wizard uses that address.

## Ready to run

`companion/auth_probe.py` is a Windows authentication probe, using only the Python standard library. It listens on IPv4 loopback port 8766, accepts callbacks for `http://localhost:8766/oauth/callback`, verifies a document-list read, and stores tokens using Windows user-bound DPAPI. It checks one-time OAuth state, rejects foreign Host headers and cross-origin sign-in requests, avoids logging callback codes, and retains existing encrypted credentials on failed refresh. It does not export geometry or communicate with a slicer.

Five tests pass with a simulated Onshape transport and real Windows encryption: exchange/refresh storage, replay rejection, refresh failure retention, local HTTP origin/host checks, and the initial OAuth redirect. This is not proof of authentication against Onshape.

Browser testing exposed a sign-in defect: `Referrer-Policy: no-referrer` suppressed the form POST's usable Origin, so the local CSRF check rejected it. The page now uses `same-origin` and allows the official Onshape redirect chain in its form-action policy. A real Chromium form click reaches `https://oauth.onshape.com/oauth/signin`. Leo completed authorization, and the subsequent live token refresh and document-list read returned HTTP 200.

For the manual account-registration step, run this in Git Bash from the project:

```bash
bash scripts/setup_onshape_private.sh
```

If the application is already registered, run `python -m companion.setup_auth` instead. This opens a native window with a masked secret field and a client-ID field. **Save and open sign-in** writes the credentials to the ignored `.env`, starts the loopback authentication probe, and opens its page. Keep the setup window open through authorization and token-refresh verification. Closing it stops the probe.

For switching accounts, use `python -m companion.setup_auth --manual-browser`. This saves the new credentials and starts the local page without opening the default browser. Open `http://localhost:8766/` in the browser profile signed into the test account and confirm the account on Onshape's authorization screen. Local credential removal does not revoke the old grant at Onshape; use My account > Applications > Revoke in the original account for that.

The wizard opens Onshape, lists the exact registration fields, and captures the client secret with hidden input into the ignored `.env` file. It configures a private Connected Desktop App with document-read permission. After registration, start `python -m companion.auth_probe`, open `http://localhost:8766`, authorize the app, and choose **Verify token refresh**. Do not share the credentials in chat. The wizard itself was syntax-checked; it has not been run against an account.

Onshape explicitly supports localhost redirects for desktop OAuth and permits leaving the OAuth URL blank for local development. See [desktop OAuth](https://onshape-public.github.io/docs/auth/oauth/#installed-desktop-applications) and [account registration](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm). A public distributed app must not bundle Leo's private client secret; its authentication deployment needs a separate design review.

## Handoff to validate after authentication

Use a **Tree context menu** extension, context **Part**, label **Add to slicer**, action **Open in new window**. The documented substitutions include document, workspace/version, element, part, and configuration. Test a browser-to-localhost action first. OAuth's localhost exception does not itself prove that extension Action URLs permit HTTP localhost; validate that in the actual registration UI and browser. If rejected, use a small HTTPS launch page/relay. A server-side GET/POST action cannot address the user's loopback service. [Extension action routes and parameters](https://onshape-public.github.io/docs/app-dev/extensions/).

Once the action endpoint works, create the private store entry, subscribe with Leo's account, and refresh the document. Registration alone does not host the endpoint. Public publication is not required. [Private installation](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm#CreatinganOnshapeAppStoreentry).

## Source identity requires translation

Onshape warns that part IDs are not stable long-term identifiers. The production link should carry a project-owned link UUID plus document, workspace, Part Studio, fixed configuration, source microversion, and the part ID valid at that microversion. Translate that ID to the target microversion and accept exactly one resolved target. Preserve the previous reference alongside the previous mesh for Revert. Reject missing, split, or ambiguous identities, even when names match. [Onshape architecture](https://onshape-public.github.io/docs/api-intro/architecture/), [ID translation and split examples](https://onshape-public.github.io/docs/api-adv/associativity/).

The export experiment established pinned geometry reads and translated identity across one unconfigured CAD change. The native handoff must still establish the precise microversion associated with the initial browser selection and configuration behavior in ID translation. A CAD edit racing with the initial handoff must not silently associate a stale selection with a new snapshot. Do not implement persistent links by treating the raw part ID as immutable.

Remaining gates: initial browser selection/snapshot identity, configured sources, two Part Studios with identical names, the native Add handoff, and broader failures with real Onshape responses. Manual Update now fetches through the companion in both slicers; see [manual updates](manual-update.md). Millimeter export, translation across one real edit, and rejection of an unresolved ID now pass. No network or CAD failure acceptance claim has been made from the local mesh tests.

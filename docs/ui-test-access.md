# Onshape UI test access

Leo explicitly authorized use of `3.1415robot.robot@gmail.com` for building and
testing this project through the actual Onshape UI. This is the designated free
test account. Do not use Leo's original account for integration tests.

## Current state

Browser sign-in succeeded. The account's Emails UI independently showed
`3.1415robot.robot@gmail.com` as its primary email and Free as its subscription.
The existing `Test` document's `Prism` Part Studio rendered a rectangular part
with a hole and a round part. No CAD geometry was edited during this check.

Leo explicitly requested saving the password for future test logins. It was
transferred directly from the masked browser field to Windows Credential Manager
without printing the value or saving it in project files. A full sign-out and
sign-in using the saved credential succeeded. Both temporary transfer servers
exited after one successful operation. Browser persistence across application
restarts is not required for this recovery path and remains unverified.

The Part Studio briefly displayed `Poor connection` during the initial rendering
check; it cleared after reauthentication and reopening. Rendering and
authentication are verified; reliable interactive CAD editing is not yet
established. Inspect connection health before editing tests.

The local app's native credential vault contains its existing OAuth configuration
and an account record. This audit made no CAD API requests. The stored OAuth
grant does not authenticate the Onshape browser, and its ownership must be
matched to the authorized browser identity before treating both as the same
test connection.

## Repeatable workflow

1. Use the collaborative browser tools for interactive Onshape testing. Inspect
   the page before acting; do not assume a previously used tab is still signed
   into the correct account.
2. Use the saved credential through `scripts.ui_test_login` when sign-in is
   needed. Let Leo handle any additional verification challenge. Do not put
   passwords, cookies, OAuth grants or complete browser storage in source files,
   tool output or evidence.
3. Verify the account email in Onshape's account UI before creating or editing
   test documents. Keep fixtures clearly named for Onshape Slicer Link testing.
4. Verify that a fixture Part Studio opens and renders before claiming that CAD
   UI access is ready. Record non-secret document IDs and test outcomes under
   ignored `artifacts/stock/` as needed.
5. Use the installed app's canonical credential store for any required API test,
   so token renewal persists correctly. The legacy
   `scripts/verify_stock_onshape.py` uses pre-migration credentials and must not
   be run unchanged against the current connection.
6. For full workflow tests, inspect both the actual Onshape UI and disposable
   stock slicer projects. Keep existing user slicer windows outside automation.
   The separate embedded prototype now has
   [desktop and import verification](embedded-runtime-verification.md).
   Its end-user setup and complete update flow are still unfinished.

## Credential recovery

Run `.\.venv\Scripts\python.exe -m scripts.ui_test_login status` to check presence
without revealing the value. The credential uses the existing project's native
vault helper under key `ui-test-login:3.1415robot.robot@gmail.com`, separate from
OAuth credentials. This is developer testing support, not product login logic.

For reauthentication, open the Onshape sign-in page, enter the authorized email,
and continue to its masked password field. Run the module with `restore`; it
prints a random one-use loopback URL and expires after three minutes. From
browser JavaScript, first verify the exact origin, `/signin` path and email.
POST JSON containing only `email` to that URL. Assign the response's password to
the masked field using the native input value setter, then dispatch bubbling
`input` and `change` events. Return only a success boolean to the tool, never
the response or field value. Submit the normal Sign in button and verify success.

`save` mode accepts the authorized email and password from the existing masked
field by the same direct browser-to-vault route. Use it only when Leo supplies a
replacement password. Both modes bind to IPv4 loopback, require the exact Onshape
Origin and local Host, limit request size, disable response caching, and exit
after a successful transfer. They do not log HTTP requests or credential values.

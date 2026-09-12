# Host the Onshape application

Render is the proposed managed host for the first deployment. The draft
[`render.yaml`](../render.yaml) creates one Starter web service and a 1 GB persistent
disk. Current base cost is about US$7.25/month before taxes or extra usage.
Its free service cannot attach the persistent disk this application needs.
[Pricing](https://render.com/pricing), [persistent disks](https://render.com/docs/disks)

No Render service has been created, no hosting charge has been approved, and no
new Onshape extension has been registered by this implementation.

## One-time operator setup

The application operator does this once. People installing the desktop helper
only connect their account and choose a folder.

1. Use the private [source repository](https://github.com/LeoHougaard/onshape-slicer-link).
   `.env`, `.env.server`, `artifacts/`, and `data/` are excluded from it.
2. In the Render dashboard, create a Blueprint from that repository and review
   the paid Starter service and persistent disk before creating them. Provide
   `OSL_ENCRYPTION_KEY` through Render's secret environment field. The local setup
   wizard generates this Fernet key. OAuth credentials start empty so you can get
   the HTTPS address before registering the Onshape application.
3. Note the resulting HTTPS `onrender.com` address. `RENDER_EXTERNAL_URL` supplies
   the service's own origin automatically. A custom domain is optional; set
   `OSL_ORIGIN` if using one. Verify `/health` returns protocol 1.
4. Register or update the private Onshape OAuth application in the designated
   test account. Use the callback and extension fields below. Add the HTTPS
   callback alongside any existing development callback that is still needed.
   Add its client ID and secret to the Render service's environment and redeploy.
5. Install `dist/OnshapeSlicerLink-Setup-x86_64.exe`, enter the public HTTPS address,
   pair the computer, and start the user test. This development installer is
   already built. For later distribution, build the helper with
   `uv run python scripts/build_helper.py --origin https://YOUR-HOST` to include
   the public address. The installer never contains an Onshape client secret.

The existing local prototype grant belongs to the replacement test account.
Continue using that account for testing. Do not use the original account.

Start **Set up hosted app.cmd** on Windows, or run
`bash scripts/setup_hosted_app.sh` in Git Bash. It opens the account pages and
walks through the four stages. The wizard has been syntax checked; account
registration and billing choices are deliberately left for the account owner.

## Onshape registration fields

Onshape embeds an HTTPS application; it does not host its server code.
[Extension configuration](https://onshape-public.github.io/docs/app-dev/extensions/)

| Field | Value |
| --- | --- |
| Application type | Integrated Cloud App |
| OAuth permission | Read documents, `OAuth2Read` |
| Redirect URL | `https://YOUR-HOST/auth/callback` |
| Application/OAuth entry URL | `https://YOUR-HOST/` |
| Extension location | Element right panel |
| Extension action URL | `https://YOUR-HOST/?documentId={$documentId}&workspaceId={$workspaceOrVersionId}&workspaceType={$workspaceOrVersion}&elementId={$elementId}&configuration={$configuration}` |
| Availability | Part Studios in workspaces |
| Store entry | Private, subscribed by the test account |

Use My account > Developer for an individually owned application. Create the
private store entry and subscribe to it, then reopen the document. Registration
alone does not make an extension appear in a document. The current dashboard's
exact labels may differ; follow the official registration and extension docs.
Onshape appends the `server` query parameter automatically. Do not add a
`{$server}` substitution or use the deprecated `{$workspaceId}` substitution.
[Developer settings](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm),
[OAuth](https://onshape-public.github.io/docs/auth/oauth/),
[right-panel messages](https://onshape-public.github.io/docs/app-dev/messages/element-right-panel/)

The callback opens in a popup and sends a one-time login code back to the panel.
Allow that sign-in popup. CAD access and refresh tokens stay encrypted in the
service database. The panel does not need third-party cookies.

## Updates and backups

Automatic deployment is disabled in the blueprint. Run the Windows checks and
review a build before manually deploying it. Keep exactly one service instance
and one Uvicorn worker. Update helper packages independently of the slicers.

Back up `/var/data` and the encryption key before a service upgrade. Use SQLite's
backup API or stop the service for a filesystem copy; copying only the main DB
while WAL writes are active is not a complete backup. Monitor the persistent disk,
which holds the database and retained immutable mesh exports. Start with small
test parts on Starter and increase memory or storage if actual use requires it.

An operator with an existing Docker host can instead use
`docker compose -f packaging/compose.yaml up -d --build` with `.env.server` and an
HTTPS reverse proxy forwarding to `127.0.0.1:8767`. Do not expose the raw HTTP port
as the production origin. The container deployment has not been executed here.

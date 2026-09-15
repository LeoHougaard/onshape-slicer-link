# Set up Onshape Slicer Link

This guide installs the local Windows app. It opens a browser tab beside Onshape
and sends parts to your installed OrcaSlicer or Bambu Studio. Your slicer stays
unmodified. The version that puts the slicer inside Onshape is a separate
preview and does not yet have a beginner installer.

Already connected? Jump to [send your first part](#3-send-your-first-part),
[update a part](#update-a-part), or [troubleshooting](#if-something-does-not-work).

## Before you start

You need:

- A Windows PC with a 64-bit Intel or AMD processor.
- Your own Onshape account and an internet connection.
- OrcaSlicer or Bambu Studio, installed and opened at least once. Finish its
  printer setup before continuing. Use the official
  [OrcaSlicer download](https://github.com/OrcaSlicer/OrcaSlicer/releases/latest)
  or [Bambu Studio download](https://bambulab.com/en/download/studio).
- An Onshape document containing a solid part. Start with a simple test model.

No Python, command line, paid hosting, or BIOS changes are needed for this
Windows installer. You do not need a connected printer to try sending a part.

## 1. Install and open Slicer Link

1. Open the [Windows test release](https://github.com/LeoHougaard/onshape-slicer-link/releases/tag/local-bridge-v0.2.0-friends).
2. Under **Assets**, click **OnshapeSlicerLink-Setup-x86_64.exe**. The files named
   **Source code** are for developers; they are not the installer.
3. Open the downloaded file from your browser's downloads or your Downloads
   folder. Follow the installer and keep the default installation folder.
4. Finish with **Open local Slicer Link** selected. Later, open the Windows Start
   menu, type **Onshape Slicer Link**, and open the app.

On a new computer, a window titled **Connect local Slicer Link** appears.
Continue below. If the Slicer Link browser page opens instead, this computer
already has a connection and you can skip to step 3.

## 2. Connect your own Onshape account

This is a one-time setup. Onshape calls the connection an "OAuth application."
You will copy its **Client ID** and **Client secret** into Slicer Link. These
are generated connection details, not your Onshape password.

### Create the connection in Onshape

1. Leave the Slicer Link setup window open. Click **Open Onshape Developer settings**
   and sign in to your own account.
2. In Onshape, open your account icon at the top right, choose **My account**,
   then **Developer** on the left.
3. Open **OAuth applications** and click **Create new OAuth application**.
4. Fill in the form using this table.

| Onshape field | What to enter |
| --- | --- |
| Name | `My Slicer Link` |
| Primary format | A unique identifier, such as `com.onshapeslicerlink.local.alex123`. Replace `alex123` with your own name and a few digits. |
| Summary | `Send my Onshape parts to my local slicer.` |
| Type | **Connected Desktop App** |
| Redirect URLs | `http://localhost:8767/auth/callback` |
| OAuth URL | Leave blank for this local setup. |
| Permissions | Check only **Application can read your documents**, also called **OAuth2Read**. Leave the other permissions unchecked. |

5. Click **Create application**. Keep the window showing the secret open.

Copy the redirect address exactly, including `http`, `8767`, and
`/auth/callback`. It points back to the app on your computer. These fields and
the desktop localhost exception are documented in
[Onshape's account setup help](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm).
This local app does not require an Onshape App Store entry.

### Copy the two values and sign in

1. Copy the newly generated **OAuth secret key** into **Client secret** in the
   Slicer Link setup window. Onshape shows this secret only once.
2. In Onshape, open your application's **Keys and secret** tab. Copy its
   **OAuth client identifier key** into **Client ID** in Slicer Link.
3. In Slicer Link, click **Save and sign in**.
4. In the browser, check that you are signed into the intended Onshape account
   and approve the request to read your documents.

You should now see the Slicer Link page with **Your slicer** and
**Your Onshape document**. Windows stores the connection in its password store.
Keep the client secret private. Each friend creates their own connection.

If you closed the secret before copying it, Onshape can generate a replacement
from **Keys and secret**. Do that before clicking **Save and sign in**.

## 3. Send your first part

1. In Slicer Link, choose OrcaSlicer or Bambu Studio under **Send parts to**.
   For this first test, keep one window of that slicer open with an empty
   project. Save any work before closing extra windows.
2. In Onshape, open your document and its Part Studio. A Part Studio is the tab
   where you create the parts. Use the editable workspace, not a saved version.
3. Copy the full address from the browser's address bar. Paste it into
   **Onshape document link** in Slicer Link and click **Connect document**.
4. Check the document name. If needed, select the correct **Part Studio** and
   click **Choose parts**.
5. In **Solid part**, choose a part, then click **Link part**. Its name appears
   in the linked-parts list with a checked box.
6. Click **Send / Update**. Switch to your slicer and finish any import prompt.

The part should appear on a plate. Arrange it and choose print settings normally.
Slicer Link does not slice or start a print.

To add more parts, repeat the selection and **Link part** step. You can select
another Part Studio in the same document. Check the boxes for the parts you
want to send, then click **Send / Update**.

If your slicer is missing, open **Can't find your slicer?**, choose its name
under **Application**, and click **Browse...**. Select the installed
`orca-slicer.exe` or `bambu-studio.exe`, then click **Use this slicer**. Select
the application file, not a shortcut or folder.

## Update a part

1. Finish your edit in Onshape and let the part finish rebuilding.
2. In Slicer Link, leave the parts you want to update checked and click
   **Send / Update**. Wait for the message asking you to reload them.
3. In OrcaSlicer or Bambu Studio, open **Prepare**. Select the existing object
   in the object list, right-click it, and choose **Reload from disk**.
   Some OrcaSlicer versions also provide **Reload All**.
4. Check the changed shape before slicing or printing.

Select the object itself, not empty plate space or a print-setting entry. For
several objects, select their rows together with Ctrl-click before reloading.
Check every affected plate; reloading one selected object may leave others
unchanged.

Slicer Link saves the replacement geometry automatically. Repeating
**Send / Update** does not import another copy. Reloading is still manual, and
the app cannot confirm that you performed it.

Native reload retained placement and ordinary object settings in the tested
examples, but geometry can recenter when its bounds change. Check alignment,
supports, and painted settings after changing geometry. Full preservation for
every project is not established by this test release.

## Save your project and keep the link

1. In the slicer, use **File > Save Project as** to save a project ending in
   `.3mf`. A project saves your objects and print settings together.
2. In Slicer Link, expand **Keep the link after reopening a saved project**.
3. Click **Connect saved project** and select that `.3mf` file.
4. Click **Send / Update** once to prepare the files beside your project.

Next time, open the saved `.3mf` in the slicer and open Slicer Link from the
Start menu. Use the same update and reload steps above.

Keep the model files Slicer Link creates beside the project. The slicer needs
them for reloading. If you move the project, use **Connect saved project** at
its new location and **Send / Update** again. Test a reload after reopening.
Only one project per Onshape document, workspace, and slicer can be connected
at a time. A project file alone does not transfer the connection to another PC.

## Everyday questions

**Do I save exported files myself?** No. Slicer Link manages the STL model files.
They remain on disk because stock slicers use them to reload geometry. You only
choose where to save your slicer project.

**What if no slicer is open?** Sending a new part starts the selected slicer.
For a part you sent before, open its project first and reload it after updating.

**What if both slicers are open?** **Send parts to** chooses the application.
If several windows of that application are open, the slicer decides where to
import. This version cannot target a particular window or plate.

**How do I put a linked part into a new project?** Expand **Start a new project
or reopen missing parts** and click **Open selected parts again**. Use this
only when the part is missing; it intentionally imports another copy.

**Can I update my slicer normally?** Yes. This version uses your installed,
unmodified slicer. If its location changes, choose it again in Slicer Link.

**How do I close Slicer Link?** Expand **Connection & API use** and click
**Stop local app**. Closing its browser tab alone leaves the app running.
The Start menu shortcut opens it again.

**Does it cost anything?** Slicer Link needs no paid hosting or subscription.
It uses Onshape's API, the connection that reads your CAD data. Onshape currently
lists 2,500 annual calls for a Free account. Successful calls through your
private connection count against its owner's allowance. Check **My account >
Developer** for your usage. The local app makes no background CAD checks and
reuses cached exports. See [Onshape's API limits](https://onshape-public.github.io/docs/auth/limits/),
checked September 14, 2026. Making this GitHub repository public does not make it
a public Onshape App Store application or change those limits.

## If something does not work

| What you see | What to do |
| --- | --- |
| Windows blocks or questions the installer | This test installer is unsigned. Check that it came from this project's release page. If you cannot open it, report the exact Windows message; do not disable antivirus protection. |
| No Developer page or option to create an application | Check that you opened **My account**, not document settings. Company-managed accounts may need their administrator's help. Report the missing option if using a personal account. |
| Onshape rejects the redirect address | Check the type is **Connected Desktop App** and the redirect is exactly `http://localhost:8767/auth/callback`. Reopen Slicer Link from Start. |
| Sign-in fails after saving the client details | Recheck the Onshape application and read permission. If you pasted the wrong Client ID or secret, report the error for help resetting the connection. There is no reset button yet. Do not share the secret. |
| A reconnect window is blocked | Allow the sign-in popup for the local Slicer Link page, then click **Reconnect Onshape** under **Connection & API use**. |
| The local page cannot be reached, or its session expired | Open **Onshape Slicer Link** from Start. A bookmarked address does not start the app or restore its session. |
| No parts are listed | Open a Part Studio containing a solid part. An assembly, sketch, or surface alone is not supported. Choose the studio and click **Choose parts** again. |
| A document link is rejected | Copy the address from an editable workspace you can access in Onshape. Saved-version links are not supported by this update flow. |
| **Send / Update** is unavailable | Choose a slicer, link a part, and check its box. |
| Sending finishes but the shape is unchanged | Wait for the send to finish, then **Reload from disk** on the existing object. Confirm you edited the linked document and Part Studio. |
| **Reload from disk** is missing or disabled | In **Prepare**, right-click the top-level object row in the object list. Try one linked solid object first. The command needs an object with a source file. |
| The slicer asks where a source file went | Reconnect the saved `.3mf` with **Connect saved project**, then **Send / Update**. If the slicer still asks, locate the matching `.stl` beside the project. Keep these files with the project. |
| A part never opened, or you removed it | Check for a slicer import prompt. If the object is absent, use **Open selected parts again** once. |
| An API limit error appears | For 429, wait before retrying. For 402, check annual usage in Onshape. Repeated sends will not restore an exhausted allowance. |

Still stuck? [Report a problem](https://github.com/LeoHougaard/onshape-slicer-link/issues).
Include your Windows version, slicer name and version, the step above, and the
error message. Crop private documents and account details out of screenshots.
Never post passwords, client secrets, or browser sign-in links.

## Where your data lives

The Windows app keeps settings, logs, and managed models in
`%LOCALAPPDATA%\OnshapeSlicerLink\local`. Paste that address into File Explorer's
address bar to open it. `app.log` is the local error log. Inspect it for private
paths or document details before sharing excerpts.

Install future updates over the existing application and keep this data folder.
Deleting it can break source links. Save your slicer projects and their adjacent
model files when backing up; copying those files does not copy your Onshape login.

## Linux users

Linux x86-64 is a target, but it has not been tested. This Windows test release
does not include a Linux download or promise compatibility with every distribution.

If a maintainer gives you `onshape-slicer-link-linux-x86_64.tar.gz`, extract it,
open the extracted `OnshapeSlicerLink` folder in a terminal, and run
`bash install.sh`. You need a graphical desktop with an unlocked Secret Service
or KWallet password store. The script installs under your user account and opens
the app. Follow the same Onshape and slicer steps above.

The script does not create an application-menu shortcut. Reopen it by running
`~/.local/share/onshape-slicer-link/OnshapeSlicerLink`, or the corresponding path
under a custom `XDG_DATA_HOME`. Linux data uses
`~/.config/onshape-slicer-link/local`, unless `XDG_CONFIG_HOME` is set. AppImages
must be executable before selecting them with **Browse...**. Installed Flatpaks
are detected, but this path also remains untested.

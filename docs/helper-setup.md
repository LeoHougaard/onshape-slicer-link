# Local application setup

Install your normal OrcaSlicer or Bambu Studio first. Updates to either slicer
remain independent of Slicer Link.

## Windows

Run `OnshapeSlicerLink-Setup-x86_64.exe`, then open **Onshape Slicer Link** from
the Start menu. Installation is per user and includes the Python runtime.
Reopening the shortcut reuses the running app and opens a connected browser tab.
Use **Stop local app** in Connection & API use to shut it down safely.

On Leo's development computer the existing replacement test-account connection
has already been migrated. No new application or hosted setup is required.

## Choose the slicer and document

Select your installed slicer from the list. If it is missing, expand the chooser,
select the application name, and use **Browse** to find its executable or AppImage.
The app remembers your selection without changing the slicer's preferences.

Copy a document link from Onshape's address bar, paste it into **Onshape document
link**, and click **Connect document**. General document links use the default
workspace. Workspace links keep the exact workspace. The app displays the document
name and its Part Studios. A link to a particular Part Studio selects that tab.
Saved-version links are rejected because they cannot follow workspace edits.

Choose a Part Studio, link the solid parts, and click **Send / Update**. New parts
open in your chosen slicer. Finish any native import prompt there. Subsequent sends
update stable source files and ask you to use **Reload from disk** for existing
parts. There is no separate save-file step and no automatic slicing or printing.

Changing documents preserves existing links; the panel displays the selected
document's links. Removing a link does not delete your source file or slicer object.
Changing slicers keeps a separate source folder and import history for each.

## Saved projects

After saving a .3mf in the slicer, use **Connect saved project** in Slicer Link.
Choose that file once. Later sends maintain source files beside it automatically,
which lets native Reload from disk find them after reopening the project. The app
does not edit the 3MF. Reconnect the project if you move it. Only one project per
Onshape document/workspace/slicer is connected at a time.

## First connection on a different computer

The app opens a setup window if no local credentials exist. In your Onshape
account's Developer settings, register a private **Connected Desktop App**, enable
only **Read documents / OAuth2Read**, and set its redirect URL to
`http://localhost:8767/auth/callback`. Enter the client ID and secret in the setup
window, then authorize the account in your browser. Onshape documents this
localhost exception for installed desktop applications.
[Developer settings](https://cad.onshape.com/help/Content/Plans/my_account_developer.htm).

Credentials use Windows Credential Manager or Linux Secret Service/KWallet.
The database encrypts CAD tokens with a key from that password store. There is no
plaintext fallback and no credential is included in the installer. Internet access
to Onshape is still required. Onshape's own API allowance still applies.

## Linux x86-64

Extract the Linux archive and run `bash install.sh`. The application installs
under your user account. A graphical desktop and an unlocked Secret Service or
KWallet password store are required. AppImages can be selected with **Browse**;
installed Flatpaks are detected and receive read access to the model folder for
that launch. Linux packaging and behavior have not been executed here.

## Data and updates

The local database, logs, and managed model files are under the app's `local`
folder in `%LOCALAPPDATA%/OnshapeSlicerLink` on Windows, or
`$XDG_CONFIG_HOME/onshape-slicer-link` on Linux, defaulting to `~/.config`.
Keep these files when updating the app because slicer projects refer to the stable
model paths. Back up this folder and the native credential store together.

No hosting setup is needed. The older helper installer and Render instructions
are superseded. This release opens its own browser window; Onshape iframe
integration is not part of the verified local workflow yet.

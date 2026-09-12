# Connect your computer

This is a development build of the stock-slicer replacement. The hosted Onshape
application and its private app registration must be configured before connecting.

On Windows, run the installer and leave **Connect with Onshape** selected. The
portable archive also works if you keep its entire folder in a permanent location.

On Linux x86-64, extract the archive and run `install.sh`. It installs for your
user and opens setup. A graphical desktop, its password store, and `xdg-utils`
are required. Runtime libraries travel with the helper; Python is not required.
The Linux package's tested distro versions are listed in the release verification
record. Do not assume every Linux distribution is compatible.

1. Choose a project folder. Keep its linked STL files and your `.3mf` project together.
2. Choose **Connect with Onshape**. Complete sign-in in your browser, then choose
   **Pair this computer**. Return to the helper when it says connected.
3. Open Slicer Link from a Part Studio in Onshape. Choose and link the solid parts.
4. Choose your computer and **Refresh selected parts**, then **Open helper**.
5. In the helper, check the destination and choose **Save refreshed files**.
6. Import each new STL into your slicer once. Save the slicer project in that folder.
   After later refreshes, select the objects and use the native **Reload from disk** command.

Released installers include the application address. For an unconfigured development
build, enter the HTTPS address supplied by the application operator.

The helper detects standard Windows and Linux installations and Flatpak app IDs.
If it finds none, use **Choose slicer executable** to select an official executable
or AppImage. It opens the slicer without importing duplicate objects. The helper
does not modify either slicer or its preferences, so normal slicer updates continue
to work.

For Flatpak slicers, choose a project folder accessible to the slicer. If Reload
opens a file chooser, select the matching STL in that folder. A desktop portal may
need to grant access to the folder. Slicer Link does not change Flatpak permissions.

Review placement, supports, seam painting, and other geometry-dependent choices
after a reload. Use native Undo immediately to undo a slicer reload, or use the
helper's **Restore previous geometry** and reload again. Restore covers the previous
downloaded STL, not your whole slicer project.

Keep the full project folder when moving computers, including `slicer-link.json`
and `.slicer-link`. Pair the new computer with the same Onshape account. Original
model and source files survive uninstalling the helper.

Refresh is manual. The service makes no idle Onshape requests. An unchanged refresh
normally needs one revision check per distinct document/workspace. The displayed
request count covers this installation, not all applications using your allowance.

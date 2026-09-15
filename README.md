# Onshape Slicer Link

Send parts from Onshape to your normal, unmodified OrcaSlicer or Bambu Studio.
Slicer Link runs on your computer and manages the model files for you. You keep
using your slicer to arrange, slice, and print, and update it normally.

## Start here

**[Download the Windows installer](https://github.com/LeoHougaard/onshape-slicer-link/releases/tag/local-bridge-v0.2.0-friends)**

[Linux x86-64 test download and Arch instructions](docs/helper-setup.md#arch-linux-and-other-linux-desktops)

**[Follow the step-by-step setup guide](docs/helper-setup.md)**

You need a Windows PC with an Intel or AMD 64-bit processor, an Onshape account,
internet access, and either slicer installed. The installer includes its runtime;
you do not need Python, a terminal, Docker, a server, or BIOS changes.

This is an early test release. Each person connects their own Onshape account
once. That involves copying two values from Onshape's settings; the guide shows
where to find them. No paid hosting is needed. Onshape API limits apply.

## What you can try today

1. Choose your slicer and paste an Onshape document link.
2. Choose a Part Studio and link a solid part.
3. Click **Send / Update**. The part opens in your slicer.
4. After changing the part in Onshape, click **Send / Update**, then use
   **Reload from disk** in the slicer.

You do not export, name, or import an STL yourself. Reloading is still manual.
Slicer Link cannot choose between several open projects or verify what an
unsaved project contains. Start with one slicer window and a simple test part.

See [everyday use and reloading](docs/helper-setup.md#update-a-part),
[saved projects](docs/helper-setup.md#save-your-project-and-keep-the-link), and the
[first-test checklist](docs/user-test.md).

## What about the slicer inside Onshape?

There are two versions of the project. The download above is the local app.

| Version | Where it opens | Ready for friends to install? |
| --- | --- | --- |
| Local app | A separate browser tab and your installed slicer | Windows test installer available; follow the setup guide |
| Embedded preview | The complete stock slicer inside an Onshape tab | Needs developer preparation; no end-user installer yet |

The embedded preview has displayed both slicers in Onshape and imported real CAD
parts. The complete one-click update flow and easy installation are unfinished.
[Read about trying the preview](docs/embedded-setup.md).

An experimental Linux x86-64 package is also available for friends to test,
including Arch users. Linux installation and execution remain untested.
macOS and ARM are not supported targets.

## Help and development

- [Setup and troubleshooting](docs/helper-setup.md)
- [Report a problem](https://github.com/LeoHougaard/onshape-slicer-link/issues)
- [Build and run from source](docs/development.md)
- [Local app architecture](docs/architecture.md)
- [Windows verification record](docs/stock-verification.md)

This project is licensed under [AGPL-3.0-only](LICENSE). Earlier hosted-service
and custom-slicer experiments remain in the repository as development history.
Use the setup guide above when installing the current local app.

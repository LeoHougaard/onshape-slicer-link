# Build and run from source

For normal use, download the Windows installer and follow the
[setup guide](helper-setup.md). This page is for developers and maintainers.

## Local app

Use Python 3.11 or newer and `uv`. From a checkout of this repository:

```sh
uv sync --locked --extra dev --extra browser
uv run --extra browser playwright install chromium
uv run --extra dev --extra browser pytest tests/stock -q
uv run python -m slicer_link.local
```

The first launch opens the graphical connection wizard. Follow it to create
your own read-only Connected Desktop App. Never
copy another user's credentials, browser profile, or local application data.

On Windows, **Start Slicer Link.cmd** opens an existing per-user installation,
or uses `.venv` from this checkout if the app is not installed. Downloading the
source ZIP alone does not prepare that environment.

## Build a package

Build on the target operating system, using the locked dependencies:

```sh
uv sync --locked --extra dev
uv run --extra dev python scripts/build_helper.py
```

On Windows, compile `packaging/windows.iss` with Inno Setup 6. The result is
`dist/OnshapeSlicerLink-Setup-0.3.2-x86_64.exe`. The build also produces
`dist/onshape-slicer-link-windows-x86_64.zip` with the executable and its runtime.

Linux builds produce `dist/onshape-slicer-link-linux-x86_64.tar.gz`, containing
`install.sh`. Linux packaging is configured but Linux execution is untested.
The manual **Build helper packages** GitHub workflow builds both targets and
uploads workflow artifacts. It does not publish a release or run Linux tests.

The builder includes the setup guide as `READ-ME.md`. Keep its download and
help links usable outside the source tree.

## Before sharing a download

1. Build from the commit identified by the release tag. Run the stock tests on
   Windows and confirm the packaged version and installer startup.
2. Check the package contains application files and documentation only. Keep
   credentials, `.env` files, browser profiles, logs, and test projects out.
3. Attach the Windows installer and a SHA-256 checksum file to the release.
   Include the setup guide, tested scope, and known limits in its notes.
4. Check the release page and installer download while signed out. GitHub's
   automatically generated **Source code** archives are not installers.

The `local-bridge-v0.2.0` tag preserves the earlier baseline. The
`v0.3.0-test` release adds guided setup to the local workflow.
The embedded development code is also on `main`, but is not
included in the installer; see [preview setup and limitations](embedded-setup.md).

## Historical experiments

`companion/`, the custom-slicer C++ experiments, and the hosted setup scripts
record earlier approaches. They are not required for the local installer.
The packaged entry point is `slicer_link.local`, and the builder packages
`slicer_link/`, not the experimental desktop scripts.

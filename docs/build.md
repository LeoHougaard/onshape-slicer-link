# Build the experiment on Windows

Requires Python, Git, CMake, Visual Studio 2022 Build Tools with C++, a Windows SDK, and the slicer's native dependencies. Exact source commits are in `sources.lock.json`. The experiment is AGPL-3.0-only; retain upstream licenses and notices.

The current development machine already has a native Orca dependency prefix at `C:/Users/Leo/Code Projects/OrcaSlicer-2.4.0/deps/build/OrcaSlicer_dep/usr/local`. It is reused read-only. A clean-machine dependency build and redistributable package have not yet been verified.

1. Run `python scripts/setup_sources.py` to fetch the commits in `sources.lock.json`. It preserves existing checkouts and refuses a mismatched commit.
2. Build native dependencies using each pinned repository's `deps` CMake project and Windows build instructions. Assimp 5.4.3 is needed by both inspected sources. This checkout builds it into `build/deps`.
3. Run `python scripts/make_fixtures.py` and `python scripts/apply_experiment.py`. The patcher checks its anchors and is safe to rerun at the pinned commits.
4. Configure and build each target with its dependency prefix. Example commands follow.

```powershell
cmake -S external/orca -B build/orca -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_PREFIX_PATH="<native dependency prefix>" `
  -DOpenCV_DIR="<native dependency prefix>/staticlib" `
  -Dassimp_DIR="<assimp prefix>/lib/cmake/assimp-5.4" `
  -DSLIC3R_STATIC=ON -DSLIC3R_PCH=ON -DBUILD_TESTING=OFF
cmake --build build/orca --config Release --target osl_native_test OrcaSlicer_app_gui -- /m:3 /p:CL_MPCount=4

cmake -S external/bambu -B build/bambu -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_PREFIX_PATH="<native dependency prefix>" `
  -DOpenCV_DIR="<native dependency prefix>/staticlib" `
  -Dassimp_DIR="<assimp prefix>/lib/cmake/assimp-5.4" `
  -DPKG_CONFIG_EXECUTABLE="<working pkg-config executable>" `
  -DSLIC3R_STATIC=ON -DSLIC3R_PCH=ON -DBUILD_TESTING=OFF
cmake --build build/bambu --config Release --target osl_native_test BambuStudio_app_gui -- /m:3 /p:CL_MPCount=4
```

This machine uses wxWidgets 3.3 from the existing dependency prefix. Run `python scripts/apply_experiment.py --wx33` to reproduce the separate Bambu build adjustments. These cover wx package discovery, list iterators, string conversions, timer-event construction, combo popup casts, a private tooltip API, and the browser-data-path configuration constructor. They are unrelated to geometry linking. Prefer the pinned Bambu dependency build when testing the standard upstream toolchain.

The borrowed prefix lacks Bambu's libharu and Boost.Stacktrace headers. This experiment builds `external/bambu/deps/libharu/libharu` with `BUILD_SHARED_LIBS=OFF`, `LIBHPDF_EXAMPLES=OFF`, and `CMAKE_INSTALL_PREFIX=<workspace>/build/deps`. Copy the `include` directory from the pinned `external/boost-stacktrace` checkout into `build/deps/include`. Configure Bambu with `-DOSL_EXTRA_INCLUDE_DIR=<workspace>/build/deps/include` and `-DHPDF_LIBRARY_RELEASE=<workspace>/build/deps/lib/hpdf.lib`. These dependencies must accompany a reproducible source distribution; do not substitute headers or binaries in the shared dependency prefix.

Run each native test executable with the absolute fixture directory and a separate output directory. It writes `native-results.json` only on success. The native test does not establish GUI compatibility.

For the GUI test, start a separate application instance with `--datadir` pointing to an isolated test profile. Set `OSL_EXPERIMENT_DIR` to a directory containing a copy of `experiments/fixtures`. In an empty project choose File > Onshape Slicer Link > Run local experiment. Results and saved projects are written beneath that directory's `results`. Review the application and reopen the saved project in a fresh process before marking GUI persistence as passed.

After reopening `gui-reverted.3mf`, select plate 2 and manually click **Slice plate**. Wait for completion, then choose File > Onshape Slicer Link > Check reopened experiment. It verifies that Update/Revert preserve the saved setup and invalidate those real toolpaths without starting another slice. The PowerShell driver supports isolated launch, show, capture, native test commands, and close; it validates the process path and window owner before acting. UI input used during verification is test scaffolding, not the integration.

After the three native/GUI reports pass, `python scripts/stage_experiment.py orca` (or `bambu`) creates a separate local development folder at `artifacts/<target>/portable`. It refuses to overwrite an existing folder. Open `Run experiment.cmd`, wait for startup, and choose File > Onshape Slicer Link > Run local experiment in the empty project. This uses a separate profile and copies of the resources and runtime; it does not replace the installed slicer. The local scenario passed in both portable folders on this development machine.

No installer or modified slicer binary is ready for public distribution. Before distributing, supply the exact corresponding source, these experiment files, build-system adjustments, dependency versions and source, build instructions, and license notices with the binary. Publishing source and a clean rebuild remain release tasks.

The manual companion bridge adds `experiments/LinkedGeometryCompanion.hpp`, copied alongside `LinkedGeometryGui.inc` by the same patcher. It uses the slicers' existing libcurl and wxWidgets dependencies; no new native library is required. Rebuild each GUI library and application DLL after applying it. Both application DLLs were rebuilt and staged separately. The development `Start Orca Link.cmd` and `Start Bambu Link.cmd` launchers start `python -m companion.server` as needed and set `OSL_COMPANION_FILE` for their slicer process. See [manual updates](manual-update.md).

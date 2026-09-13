"""Build a helper with its runtime. Run on the target OS, never cross-compile."""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Release builds target Windows/Linux x86-64.")
    target = "windows" if sys.platform == "win32" else "linux"
    staging = ROOT / "artifacts" / "stock" / "package" / target
    staging.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--noupx",
        "--name",
        "OnshapeSlicerLink",
        "--distpath",
        str(ROOT / "dist" / target),
        "--workpath",
        str(staging / "work"),
        "--specpath",
        str(staging),
        "--paths",
        str(ROOT),
        "--collect-submodules",
        "keyring.backends",
        "--collect-submodules",
        "uvicorn",
        "--collect-data",
        "slicer_link",
    ]
    if target == "windows":
        command += ["--windowed"]
    command.append(str(ROOT / "packaging" / "helper_entry.py"))
    subprocess.run(command, cwd=ROOT, check=True, stderr=subprocess.STDOUT)
    destination = ROOT / "dist" / target / "OnshapeSlicerLink"
    shutil.copyfile(ROOT / "LICENSE", destination / "LICENSE")
    shutil.copyfile(ROOT / "docs" / "helper-setup.md", destination / "READ-ME.md")
    if target == "linux":
        shutil.copyfile(ROOT / "packaging" / "install-linux.sh", destination / "install.sh")
        (destination / "install.sh").chmod(0o755)
        shutil.make_archive(
            str(ROOT / "dist" / "onshape-slicer-link-linux-x86_64"),
            "gztar",
            root_dir=destination.parent,
            base_dir=destination.name,
        )
    else:
        shutil.make_archive(
            str(ROOT / "dist" / "onshape-slicer-link-windows-x86_64"),
            "zip",
            root_dir=destination.parent,
            base_dir=destination.name,
        )
    print(f"Built {destination}. This does not publish or install it.")


if __name__ == "__main__":
    main()

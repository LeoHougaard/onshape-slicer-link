#!/usr/bin/env bash
# Per-user installation. Run from the extracted release folder.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/onshape-slicer-link"
test "$(uname -m)" = x86_64 || { echo 'This release requires x86-64 Linux.' >&2; exit 1; }
test -f "$source_dir/OnshapeSlicerLink" && test -d "$source_dir/_internal"
mkdir -p -- "$install_dir"
# Updates replace application files. Project files and settings live elsewhere.
if [[ "$source_dir" != "$(cd -- "$install_dir" && pwd -P)" ]]; then
  cp -R -- "$source_dir/OnshapeSlicerLink" "$source_dir/_internal" "$source_dir/LICENSE" "$source_dir/READ-ME.md" "$install_dir/"
fi
chmod u+x -- "$install_dir/OnshapeSlicerLink"
exec "$install_dir/OnshapeSlicerLink" --install-shortcut

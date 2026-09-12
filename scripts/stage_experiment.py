"""Stage a separate portable experiment directory from a verified native build.

This is a local development bundle, not the production installer.
SPDX-License-Identifier: AGPL-3.0-only
"""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('target', choices=['orca', 'bambu'])
target = parser.parse_args().target
name = 'OrcaSlicer' if target == 'orca' else 'BambuStudio'
executable = 'orca-slicer.exe' if target == 'orca' else 'bambu-studio.exe'
source = ROOT / 'build' / target / 'src/Release'
artifact = ROOT / 'artifacts' / target
destination = artifact / 'portable'
if destination.exists():
    raise SystemExit(f'Refusing to mix builds in existing directory: {destination}')
for report in [artifact / 'native-results.json', artifact / 'results/gui-results.json',
               artifact / 'results/gui-reopened-results.json']:
    if json.loads(report.read_text())['status'] != 'passed':
        raise SystemExit(f'Unverified build: {report}')
destination.mkdir(parents=True)
shutil.copy2(source / executable, destination / executable)
for dll in source.glob('*.dll'):
    shutil.copy2(dll, destination / dll.name)
shutil.copytree((source / 'resources').resolve(), destination / 'resources')
if (source / 'python').exists():
    shutil.copytree(source / 'python', destination / 'python')
shutil.copytree(ROOT / 'experiments/fixtures', destination / 'experiment/fixtures')
(destination / 'profile').mkdir()
shutil.copy2(artifact / 'profile' / f'{name}.conf', destination / 'profile' / f'{name}.conf')
shutil.copy2(ROOT / 'LICENSE', destination / 'LICENSE')
shutil.copytree(ROOT / 'docs', destination / 'source-notes')
(destination / 'Run experiment.cmd').write_text(
    '@echo off\nset "OSL_EXPERIMENT_DIR=%~dp0experiment"\n'
    f'"%~dp0{executable}" --datadir "%~dp0profile"\n', encoding='utf-8')
print(destination)

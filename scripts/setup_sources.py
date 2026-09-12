"""Fetch pinned upstream sources without resetting existing work.

SPDX-License-Identifier: AGPL-3.0-only
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, check=True)


for name, source in json.loads((ROOT / 'sources.lock.json').read_text()).items():
    destination = ROOT / 'external' / name
    if destination.exists():
        actual = subprocess.check_output(
            ['git', '-C', str(destination), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != source['commit']:
            raise SystemExit(f'{destination} is at {actual}; expected {source["commit"]}. Existing work retained.')
        print(f'{name}: pinned checkout already present')
        continue
    destination.mkdir(parents=True)
    run('git', 'init', str(destination))
    run('git', '-C', str(destination), 'remote', 'add', 'origin', source['repository'])
    run('git', '-C', str(destination), 'fetch', '--depth', '1', 'origin', source['commit'])
    run('git', '-C', str(destination), 'checkout', '--detach', 'FETCH_HEAD')
    run('git', '-C', str(destination), 'submodule', 'update', '--init', '--recursive', '--depth', '1')

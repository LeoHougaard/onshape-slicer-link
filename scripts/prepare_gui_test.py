"""Create offline, isolated slicer profiles and fixture copies. Never copies credentials.

SPDX-License-Identifier: AGPL-3.0-only
"""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

for target, name, version in [('orca', 'OrcaSlicer', '2.5.0-dev'), ('bambu', 'BambuStudio', '02.08.02.61')]:
    root = ROOT / 'artifacts' / target
    profile = root / 'profile'
    destination = profile / f'{name}.conf'
    if destination.exists():
        raise SystemExit(f'Refusing to overwrite an existing test profile: {destination}')
    profile.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / 'experiments/fixtures').iterdir():
        destination = root / 'fixtures' / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    config = {
        'header': f'{name} {version}',
        'app': {'version': version, 'single_instance': False, 'auto_slice_after_change': True,
                'background_processing': '1', 'show_splash_screen': False, 'show_daily_tips': False,
                'check_updates': False, 'sync_user_preset': False, 'stealth_mode': True,
                'language': 'en_US', 'region': 'North America', 'role_type': '0'},
        'firstguide': {'finish': True, 'privacyuse': False},
        'models': [{'model': 'Bambu Lab A1 mini', 'nozzle_diameter': '0.4', 'vendor': 'BBL'}],
        'filaments': ['Generic PLA @BBL A1M'],
        'presets': {'machine': 'Bambu Lab A1 mini 0.4 nozzle', 'process': '0.20mm Standard @BBL A1M',
                    'filaments': ['Generic PLA @BBL A1M'], 'filament_colors': '#00AE42'},
    }
    destination.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print(root)

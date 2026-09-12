# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
import tempfile
import unittest

from companion.auth_probe import ProbeError, read_config
from companion.setup_auth import save_credentials


class SetupAuthTests(unittest.TestCase):
    def test_pasted_credentials_round_trip_and_preserve_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('# keep this\nUNRELATED=value\nONSHAPE_CLIENT_SECRET=old\n')
            save_credentials(root, ' client-id ', ' secret-value\r\n')
            self.assertEqual(read_config(root / '.env'),
                             ('client-id', 'secret-value', 'https://cad.onshape.com'))
            self.assertIn('UNRELATED=value', (root / '.env').read_text())
            self.assertFalse(list((root / 'artifacts/onshape').glob('*.tmp')))

    def test_invalid_input_retains_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = b'ONSHAPE_CLIENT_SECRET=existing\n'
            (root / '.env').write_bytes(original)
            for secret in ['', 'bad\nONSHAPE_BASE_URL=changed', 'internal space']:
                with self.assertRaises(ProbeError):
                    save_credentials(root, 'client-id', secret)
                self.assertEqual((root / '.env').read_bytes(), original)

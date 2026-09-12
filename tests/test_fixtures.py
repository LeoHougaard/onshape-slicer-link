# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
from pathlib import Path
import unittest
from collections import Counter

spec = importlib.util.spec_from_file_location('fixtures', Path(__file__).parents[1] / 'scripts/make_fixtures.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class FixturesTest(unittest.TestCase):
    def test_closed_oriented_mesh_and_expected_volume(self):
        for length in (32, 46):
            vertices, triangles = fixtures.mesh(length)
            edges = Counter((t[i], t[(i+1) % 3]) for t in triangles for i in range(3))
            self.assertTrue(all(n == 1 and edges[(b, a)] == 1 for (a, b), n in edges.items()))
            volume6 = 0
            for t in triangles:
                a, b, c = [vertices[i] for i in t]
                volume6 += a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0])
            self.assertAlmostEqual(volume6/6, (length*8 + 12*16)*6)

    def test_reference_vertices_do_not_move(self):
        first, _ = fixtures.mesh(32)
        second, _ = fixtures.mesh(46)
        self.assertEqual([first[i] for i in (0, 3, 4, 5, 6, 9, 10, 11)],
                         [second[i] for i in (0, 3, 4, 5, 6, 9, 10, 11)])
        self.assertEqual(second[1][0] - first[1][0], 14)

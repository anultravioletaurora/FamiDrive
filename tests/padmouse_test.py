"""famidrive-padmouse: the stick curve and axis scaling, no devices.

    python3 padmouse_test.py path/to/famidrive_padmouse.py
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_padmouse", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Info:
    def __init__(self, lo, hi):
        self.min, self.max = lo, hi


class Sticks(unittest.TestCase):
    def test_dead_zone_then_a_curve(self):
        self.assertEqual(m.curve(0.1), 0.0)
        self.assertEqual(m.curve(-0.18), 0.0)
        self.assertAlmostEqual(m.curve(1.0), 1.0)
        self.assertAlmostEqual(m.curve(-1.0), -1.0)
        self.assertLess(m.curve(0.5), 0.5)   # slower near the middle

    def test_axes_around_their_middle(self):
        self.assertAlmostEqual(m.norm(0, Info(-32768, 32767)), 0.0, places=3)
        self.assertAlmostEqual(m.norm(32767, Info(-32768, 32767)), 1.0, places=3)
        self.assertAlmostEqual(m.norm(0, Info(0, 255)), -1.0)
        self.assertAlmostEqual(m.norm(255, Info(0, 255)), 1.0)


if __name__ == "__main__":
    unittest.main()

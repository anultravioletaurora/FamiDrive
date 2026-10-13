"""famidrive-status: how its progress bars ease toward a new reading.

    python3 status_test.py path/to/famidrive_status.py
"""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("famidrive_status", SCRIPT)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class Ease(unittest.TestCase):
    def test_first_reading_shows_at_once(self):
        self.assertEqual(s.ease_toward(None, 0.4, 1 / 30), 0.4)

    def test_glides_fast_then_gently(self):
        shown, steps = 0.2, []
        for _ in range(60):   # two seconds at 30 frames a second
            before = shown
            shown = s.ease_toward(shown, 0.6, 1 / 30)
            steps.append(shown - before)
        self.assertGreater(steps[0], steps[10])               # quick at first
        self.assertTrue(all(x > 0 for x in steps))            # never past it and back
        self.assertAlmostEqual(shown, 0.6, delta=0.005)       # a pixel or so off by the next reading

    def test_goes_back_down_too(self):
        self.assertLess(s.ease_toward(0.9, 0.1, 1 / 30), 0.9)


if __name__ == "__main__":
    unittest.main()

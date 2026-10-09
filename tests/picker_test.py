"""famidrive-picker, off-screen, against a stand-in for greetd.

    python3 picker_test.py path/to/famidrive_picker.py

Draws with SDL's dummy video driver, presses keys by posting events, and
answers greetd's side of the login over a real socket.
"""

import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPT = Path(sys.argv.pop(1)).read_text()
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402


class FakeGreetd:
    """Answers each request from a list of replies, and keeps the requests."""

    def __init__(self, path, replies):
        self.requests, self.replies = [], list(replies)
        self.srv = socket.socket(socket.AF_UNIX)
        self.srv.bind(path)
        self.srv.listen(1)
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        c, _ = self.srv.accept()

        def read(n):
            b = b""
            while len(b) < n:
                chunk = c.recv(n - len(b))
                if not chunk:
                    raise EOFError
                b += chunk
            return b
        try:
            while True:
                self.requests.append(json.loads(read(struct.unpack("=I", read(4))[0])))
                reply = self.replies.pop(0) if self.replies else {"type": "success"}
                data = json.dumps(reply).encode()
                c.sendall(struct.pack("=I", len(data)) + data)
        except EOFError:
            pass


class Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.spec = self.dir / "spec.json"
        self.last = self.dir / "last"
        self.spec.write_text(json.dumps({
            "players": [{"user": "alice", "displayName": "Alice", "isGuest": False},
                        {"user": "bob", "displayName": "Bob", "isGuest": False},
                        {"user": "guest", "displayName": "Guest", "isGuest": True}],
            "session": ["/run/current-system/sw/bin/famidrive-start"],
            "last": str(self.last),
            "theme": None,
            "powerOff": [sys.executable, "-c", f"open({str(self.dir / 'off')!r}, 'w').write('off')"],
        }))
        os.environ["GREETD_SOCK"] = str(self.dir / "greetd.sock")

    def tearDown(self):
        self.tmp.cleanup()

    def play(self, keys, replies=()):
        """Run the picker, pressing `keys` one frame apart. Returns the
        exit code (None if it never exited) and greetd's requests."""
        greetd = FakeGreetd(os.environ["GREETD_SOCK"], replies)
        flip, frames = pygame.display.flip, [0]
        set_mode = pygame.display.set_mode

        def step():
            self.frame = pygame.display.get_surface().copy()
            frames[0] += 1
            if frames[0] <= len(keys):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=keys[frames[0] - 1]))
            elif frames[0] > len(keys) + 5:
                raise TimeoutError
            flip()
        pygame.display.flip = step
        pygame.display.set_mode = lambda size, flags=0: set_mode((1280, 720))
        sys.argv = ["famidrive-picker", str(self.spec)]
        code = None
        try:
            exec(compile(SCRIPT, "famidrive_picker.py", "exec"), {"__name__": "__main__"})
        except SystemExit as e:
            code = e.code
        except TimeoutError:
            pass
        finally:
            pygame.display.flip, pygame.display.set_mode = flip, set_mode
            pygame.quit()
        return code, greetd.requests

    def test_pick_second_player(self):
        code, reqs = self.play([pygame.K_RIGHT, pygame.K_RETURN])
        self.assertEqual(code, 0)
        self.assertEqual(reqs, [
            {"type": "create_session", "username": "bob"},
            {"type": "start_session", "cmd": ["/run/current-system/sw/bin/famidrive-start"], "env": []},
        ])
        self.assertEqual(self.last.read_text(), "bob")

    def test_last_player_starts_selected_and_wraps(self):
        self.last.write_text("guest")
        code, reqs = self.play([pygame.K_RIGHT, pygame.K_RETURN])
        self.assertEqual(reqs[0], {"type": "create_session", "username": "alice"})

    def test_pam_info_is_acknowledged(self):
        code, reqs = self.play([pygame.K_RETURN], replies=[
            {"type": "auth_message", "auth_message_type": "info", "auth_message": "hi"}])
        self.assertEqual(code, 0)
        self.assertEqual([r["type"] for r in reqs],
                         ["create_session", "post_auth_message_response", "start_session"])

    def test_power_off_below_the_players(self):
        code, reqs = self.play([pygame.K_DOWN, pygame.K_RETURN])
        self.assertIsNone(code)            # stays up while the box turns off
        self.assertEqual(reqs, [])         # nobody logged in
        self.assertEqual((self.dir / "off").read_text(), "off")
        self.assertFalse(self.last.exists())

    def test_back_up_to_the_players(self):
        code, reqs = self.play([pygame.K_DOWN, pygame.K_UP, pygame.K_RETURN])
        self.assertEqual(reqs[0], {"type": "create_session", "username": "alice"})

    def test_password_prompt_is_cancelled(self):
        code, reqs = self.play([pygame.K_RETURN], replies=[
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"}])
        self.assertIsNone(code)   # still on screen, showing why
        self.assertEqual([r["type"] for r in reqs], ["create_session", "cancel_session"])
        self.assertFalse(self.last.exists())

    def test_pictures_cut_to_circles(self):
        # Alice's from her config, Bob's fetched from RomM, the guest's
        # unreadable (an initial instead). 1280x720: circles 146 across,
        # 206 apart, centered at y 345; Alice's selected, so full color.
        def picture(path, color):
            img = pygame.Surface((40, 30))
            img.fill(color)
            pygame.image.save(img, str(path))
        pygame.init()
        picture(self.dir / "alice.png", (10, 200, 30))
        avatars = self.dir / "avatars"
        avatars.mkdir()
        picture(avatars / "bob.png", (200, 10, 10))
        (avatars / "guest.png").write_text("not a picture")
        pygame.quit()
        spec = json.loads(self.spec.read_text())
        spec["players"][0]["avatar"] = str(self.dir / "alice.png")
        spec["avatars"] = str(avatars)
        self.spec.write_text(json.dumps(spec))
        self.play([])
        at = lambda x: tuple(self.frame.get_at((x, 345 - 50)))[:3]
        self.assertEqual(at(434), (10, 200, 30))
        r, g, b = at(640)
        self.assertTrue(110 <= r <= 130 and g < 15, (r, g, b))   # dimmed red
        self.assertEqual(at(846), (66, 66, 66))   # the guest's grey, dimmed


if __name__ == "__main__":
    unittest.main(verbosity=2)

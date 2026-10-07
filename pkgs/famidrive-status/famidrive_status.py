"""famidrive-status APPID STATUS_FILE

The screen shown while Steam gets a game going: updating it, processing
its shaders, waiting on a prompt, or starting it. gamescope-fg --steam
starts this, writes the current state to STATUS_FILE (JSON: "state" and,
for "failed", "detail"), puts this window on top, and closes it once the
game's own window is up.

It draws in ES-DE's look: the fonts the theme itself uses for game names
and descriptions (read from the theme's theme.xml, FAMIDRIVE_STATUS_THEME),
and the game's scraped art when there is some (FAMIDRIVE_STATUS_MEDIA).
It takes no input: Select + Start (famidrive-quit) is the way out, and
when Steam shows a prompt, gamescope-fg puts Steam's window above this.
"""

import json
import math
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "x11")   # gamescope's Xwayland
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

STEAM = Path.home() / ".local/share/Steam"
THEME = Path(os.environ.get("FAMIDRIVE_STATUS_THEME", "/nonexistent"))
MEDIA = Path(os.environ.get("FAMIDRIVE_STATUS_MEDIA", str(Path.home() / "ES-DE/downloaded_media/steam")))

WHITE = (255, 255, 255)
DIM = (153, 153, 153)        # the theme's help text
BAR_BG = (68, 68, 68)        # its selected-row grey
PANEL = (17, 17, 17, 230)    # its help bar

# state -> (headline, explanation)
TEXT = {
    "asking": ("Asking Steam", "Steam is getting the game ready."),
    "updating": ("Updating", "Steam is downloading an update. The game starts when it's done."),
    "shaders": ("Processing Vulkan shaders",
                "Steam prepares these once per game, and again after a game or driver update. "
                "It makes the game run smoothly from the start."),
    "prompt": ("Steam needs you", "Answer Steam's question to continue."),
    "installing": ("Setting up the game",
                   "Steam is running the game's first-time setup, such as its publisher's launcher. "
                   "If a window asks something, answer it; some need a mouse or keyboard."),
    "launching": ("Starting", "The game is loading."),
    "failed": ("Steam couldn't start the game", ""),
}


def manifest(appid):
    return manifest_and_library(appid)[0]


def manifest_and_library(appid):
    for lib in [STEAM / "steamapps"] + [
            Path(p) / "steamapps" for p in re.findall(
                r'"path"\s+"([^"]+)"', read(STEAM / "steamapps/libraryfolders.vdf"))]:
        text = read(lib / f"appmanifest_{appid}.acf")
        if text:
            return text, lib
    return "", None


def folder_size(path):
    total = 0
    for dirpath, _, names in os.walk(path):
        for n in names:
            try:
                total += os.lstat(os.path.join(dirpath, n)).st_size
            except OSError:
                pass
    return total


def download_progress(appid):
    """Bytes done and to do of the game's download. Steam doesn't keep the
    manifest's BytesDownloaded current while it downloads (it can sit at 0
    the whole time), so this measures what has landed in
    steamapps/downloading/<appid> against BytesToStage, and only falls
    back to the manifest's counters when there's no such folder. Found on
    the first box 2026-10-06: Overwatch was at 28% in Steam's phone app
    while the manifest still said 0 bytes."""
    text, lib = manifest_and_library(appid)
    staging = int(field(text, "BytesToStage") or 0)
    if lib is not None and staging > 0 and (lib / "downloading" / str(appid)).is_dir():
        done = max(folder_size(lib / "downloading" / str(appid)), int(field(text, "BytesStaged") or 0))
        return min(done, staging), staging
    return int(field(text, "BytesDownloaded") or 0), int(field(text, "BytesToDownload") or 0)


def read(path):
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def field(text, key):
    m = re.search(rf'"{key}"\s+"([^"]*)"', text)
    return m.group(1) if m else None


def art(name):
    """(cover, background) paths from ES-DE's scraped media, by the
    placeholder's file name (famidrive-generators' safe())."""
    stem = re.sub(r'[/\\:*?"<>|]', "_", name).strip()

    def find(*kinds):
        for kind in kinds:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = MEDIA / kind / (stem + ext)
                if p.exists():
                    return p
        return None
    return find("covers", "miximages"), find("fanart", "screenshots", "titlescreens")


def load(path):
    try:
        return pygame.image.load(str(path)).convert_alpha() if path else None
    except (pygame.error, FileNotFoundError):
        return None


def theme_fonts():
    """(regular, light) font files the theme uses for game names and for
    descriptions. Art Book Next names them in theme.xml's <variables> as
    fontRegular and fontLight; other themes fall back to ES-DE's default."""
    names = dict(re.findall(r"<(font\w+)>([^<]+)</font\w+>", read(THEME / "theme.xml")))
    regular = names.get("fontRegular")
    light = names.get("fontLight", regular)
    return (THEME / regular if regular else None), (THEME / light if light else None)


def font(path, size):
    try:
        if path:
            return pygame.font.Font(str(path), size)
    except (FileNotFoundError, OSError):
        pass
    return pygame.font.Font(None, int(size * 1.3))


def wrap(text, f, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if f.size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def shader_progress(appid):
    """Steam's shader-processing percentage for this game, from its shader
    log ("Still replaying <appid> (57%, …)"), or None."""
    try:
        with open(STEAM / "logs/shader_log.txt", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 65536))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    found = re.findall(rf"Still replaying {appid} \((\d+)%", tail)
    return int(found[-1]) if found else None


def gb(n):
    return f"{n / 1e9:.1f} GB"


def main():
    appid, status_file = sys.argv[1], Path(sys.argv[2])
    pygame.init()
    display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    # Everything is drawn on a plain 32-bit canvas, then copied to the
    # display. Found on the first box 2026-10-05: with HDR on, gamescope's
    # display surface is 10 bits per channel, and anti-aliased text drawn
    # straight onto it came out as solid blocks.
    screen = pygame.Surface(display.get_size(), 0, 32)
    pygame.display.set_caption("FamiDrive")
    pygame.mouse.set_visible(False)
    w, h = display.get_size()
    u = h / 1080   # layout unit: sizes below are for 1080p

    text = manifest(appid)
    name = field(text, "name") or f"Steam game {appid}"
    cover_img, bg_img = (load(p) for p in art(name))

    regular, light = theme_fonts()
    title_f = font(regular, int(64 * u))
    head_f = font(regular, int(40 * u))
    body_f = font(light, int(28 * u))
    help_f = font(regular, int(24 * u))

    # The background: the game's art, scaled to fill and darkened.
    background = pygame.Surface((w, h), 0, 32)
    background.fill((0, 0, 0))
    if bg_img:
        s = max(w / bg_img.get_width(), h / bg_img.get_height())
        img = pygame.transform.smoothscale(bg_img, (int(bg_img.get_width() * s), int(bg_img.get_height() * s)))
        background.blit(img, ((w - img.get_width()) // 2, (h - img.get_height()) // 2))
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        background.blit(shade, (0, 0))

    cover = None
    if cover_img:
        s = (560 * u) / cover_img.get_height()
        cover = pygame.transform.smoothscale(cover_img, (int(cover_img.get_width() * s), int(560 * u)))

    state, detail, since = "asking", "", time.monotonic()
    rate, last_bytes, last_t = None, None, None
    done = total = 0
    shaders = None
    next_read = 0.0
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        try:
            st = json.loads(status_file.read_text())
            if st.get("state") != state:
                state, since = st.get("state", state), time.monotonic()
            detail = st.get("detail", "")
        except (OSError, ValueError):
            pass

        screen.blit(background, (0, 0))
        left = int(160 * u)
        if cover:
            y = (h - cover.get_height()) // 2 - int(40 * u)
            screen.blit(cover, (left, y))
            left += cover.get_width() + int(100 * u)
        width = w - left - int(160 * u)

        y = int(h * 0.30)
        for line in wrap(name, title_f, width)[:2]:
            screen.blit(title_f.render(line, True, WHITE), (left, y))
            y += title_f.get_linesize()
        y += int(30 * u)

        head, body = TEXT.get(state, TEXT["asking"])
        if state == "failed" and detail:
            body = detail

        # A spinning arc beside the headline, except once it has failed.
        if state != "failed":
            r = int(18 * u)
            cx, cy = left + r, y + head_f.get_linesize() // 2
            a = (time.monotonic() * 4) % (2 * math.pi)
            pygame.draw.arc(screen, WHITE, (cx - r, cy - r, 2 * r, 2 * r), a, a + 4.2, max(2, int(4 * u)))
            screen.blit(head_f.render(head, True, WHITE), (left + 2 * r + int(24 * u), y))
        else:
            screen.blit(head_f.render(head, True, WHITE), (left, y))
        y += head_f.get_linesize() + int(16 * u)

        if state == "updating":
            now = time.monotonic()
            if now >= next_read:
                next_read = now + 2
                done, total = download_progress(appid)
                if last_bytes is not None and done > last_bytes:
                    r_now = (done - last_bytes) / (now - last_t)
                    rate = r_now if rate is None else 0.7 * rate + 0.3 * r_now
                if last_bytes is None or done != last_bytes:
                    last_bytes, last_t = done, now
            if total > 10_000_000:   # a real download, not a few files' bookkeeping
                bar_w, bar_h = width, int(14 * u)
                pygame.draw.rect(screen, BAR_BG, (left, y, bar_w, bar_h), border_radius=bar_h // 2)
                pygame.draw.rect(screen, WHITE, (left, y, max(bar_h, int(bar_w * min(done / total, 1))), bar_h),
                                 border_radius=bar_h // 2)
                y += bar_h + int(16 * u)
                line = f"{gb(done)} of {gb(total)}"
                if rate:
                    mins = (total - done) / rate / 60
                    line += f"  ·  {rate / 1e6:.0f} MB/s  ·  about {max(1, round(mins))} min left"
                screen.blit(body_f.render(line, True, WHITE), (left, y))
                y += body_f.get_linesize() + int(8 * u)

        if state == "shaders":
            now = time.monotonic()
            if now >= next_read:
                next_read = now + 2
                shaders = shader_progress(appid)
            if shaders is not None:
                bar_w, bar_h = width, int(14 * u)
                pygame.draw.rect(screen, BAR_BG, (left, y, bar_w, bar_h), border_radius=bar_h // 2)
                pygame.draw.rect(screen, WHITE, (left, y, max(bar_h, int(bar_w * shaders / 100)), bar_h),
                                 border_radius=bar_h // 2)
                y += bar_h + int(16 * u)
                screen.blit(body_f.render(f"{shaders}%", True, WHITE), (left, y))
                y += body_f.get_linesize() + int(8 * u)

        for line in wrap(body, body_f, width):
            screen.blit(body_f.render(line, True, DIM), (left, y))
            y += body_f.get_linesize()
        elapsed = int(time.monotonic() - since)
        if state != "failed" and elapsed >= 10:
            screen.blit(body_f.render(f"{elapsed // 60}:{elapsed % 60:02d}", True, DIM), (left, y + int(12 * u)))

        # ES-DE's help bar, bottom right.
        hint = help_f.render("SELECT + START   BACK TO MENU", True, DIM)
        bar = pygame.Surface((hint.get_width() + int(48 * u), hint.get_height() + int(24 * u)), pygame.SRCALPHA)
        bar.fill(PANEL)
        bar.blit(hint, (int(24 * u), int(12 * u)))
        screen.blit(bar, (w - bar.get_width() - int(40 * u), h - bar.get_height() - int(40 * u)))

        display.blit(screen, (0, 0))
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    main()

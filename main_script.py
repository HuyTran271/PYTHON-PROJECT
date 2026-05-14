#!/usr/bin/env python3
"""
Chicken‑Invaders‑by‑Hand 🚀🐔  – *Ultimate HD Edition* (v2.0‑multi‑wave)
====================================================================
A single‑file clone that brings **MediaPipe hand‑tracking**, **web‑cam overlay**
and **fullscreen** play together with deeper gameplay inspired by
*Chicken Invaders 5 HD*:

• Multiple chicken breeds that unlock every few levels (health, speed, points)
• Power‑up capsules that upgrade your ship’s blaster (up to triple‑spread)
• Progressive difficulty scaling – faster eggs, trickier flight paths, bosses
• All original v1.2 features (hand control + webcam thumbnail + HD fullscreen)

NOTE  ▸  The game still runs even if you’re missing PNG/WAV assets – coloured
           placeholders are generated automatically.  Place custom artwork in
           an  assets/  folder next to this file using the names referenced
           below to get a fully‑themed experience.
"""
from __future__ import annotations

import random, math, time, sys, os, queue, threading, urllib.request
from pathlib import Path
from typing import Tuple, Optional, List
# Install pygame 2.6.1
import cv2, pygame as pg, mediapipe as mp
import numpy as np

###############################################################################
# ── MediaPipe hand‑tracking setup ─────────────────────────────────────────── #
###############################################################################
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float32/latest/gesture_recognizer.task"
)
MODEL_PATH = "gesture_recognizer.task"
if not Path(MODEL_PATH).exists():
    print("⏬  Downloading MediaPipe model …")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

BaseOptions = mp.tasks.BaseOptions
RecognizerOpt = mp.tasks.vision.GestureRecognizerOptions
Recognizer = mp.tasks.vision.GestureRecognizer
RunningMode = mp.tasks.vision.RunningMode

options = RecognizerOpt(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.5,
    min_hand_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

PALM_IDXS: Tuple[int, ...] = (0, 5, 9, 13, 17)  # landmark indices for palm‑centroid
centroid_x_norm: Optional[float] = None  # shared state: palm centre X ∈ [0,1]
centroid_y_norm: Optional[float] = None  # shared state: palm centre X ∈ [0,1]
fire_signal = threading.Event()  # raised on closed‑fist gesture
restart_signal = threading.Event()     # raised on thumb-up (GAME OVER → restart)
state_lock = threading.Lock()  # protects centroid_x_norm

FrameQ: "queue.Queue[Tuple[int, cv2.Mat]]" = queue.Queue(maxsize=2)
stop_event = threading.Event()

# Holds the most‑recent frame for the on‑screen thumbnail ----------------------
latest_frame: Optional[np.ndarray] = None


###############################################################################
# ── Webcam producer / consumer threads ────────────────────────────────────── #
###############################################################################

def _capture(cam: cv2.VideoCapture, t0: float):
    """Read frames, flip L↔R for natural mirror control, queue latest only."""
    global latest_frame
    while not stop_event.is_set():
        ok, frame = cam.read()
        if not ok:
            stop_event.set();
            break
        frame = cv2.flip(frame, 1)
        latest_frame = frame  # lightweight – np array ref
        ts = int((time.time() - t0) * 1000)
        if FrameQ.full():
            try:
                FrameQ.get_nowait()
            except queue.Empty:
                pass
        FrameQ.put((ts, frame), False)


def _infer():
    """Run MediaPipe gesture recogniser on the most recent frame."""
    global centroid_x_norm, centroid_y_norm
    with Recognizer.create_from_options(options) as rec:
        while not stop_event.is_set():
            try:
                ts, frame = FrameQ.get(timeout=0.1)
            except queue.Empty:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = rec.recognize_for_video(mp_img, ts)
            if res.hand_landmarks:
                hand = res.hand_landmarks[0]
                cx = sum(hand[i].x for i in PALM_IDXS) / len(PALM_IDXS)
                cy = sum(hand[i].y for i in PALM_IDXS) / len(PALM_IDXS)
                with state_lock:
                    centroid_x_norm = cx
                    centroid_y_norm = cy
                if res.gestures:
                    g = res.gestures[0][0].category_name.lower()
                    if g in {"closed_fist", "thumb_down", "okay"}:  # shoot
                        fire_signal.set()
                    elif g == "thumb_up":  # restart
                        restart_signal.set()
            else:
                with state_lock:
                    centroid_x_norm = None
                    centroid_y_norm = None


###############################################################################
# ── Pygame initialisation / globals ───────────────────────────────────────── #
###############################################################################
W, H = 900, 800  # will be overwritten once display size known
SHIP_Y = 0  # likewise – depends on H
STAR_COUNT = 140

ASSETS = Path(__file__).with_suffix("").parent / ("assets")

pg.init()
info = pg.display.Info()  # true fullscreen at native res
W, H = info.current_w, info.current_h
SHIP_Y = H - 80
pg.display.set_caption("Chicken Invaders – Hand Edition (fullscreen)")
screen = pg.display.set_mode((W, H), pg.FULLSCREEN)
clock = pg.time.Clock()
font = pg.font.SysFont("arial", 26)
font_big = pg.font.SysFont("arial", 54, bold=True)

hud_font   = pg.font.SysFont("arial", 36,  bold=True)   # for Level / Score / Gun
heart_font = pg.font.SysFont("arial", 48,  bold=True)   # for the ♥ lives indicator

pg.mixer.init()
shoot_snd = hit_snd = power_snd = None
try:
    shoot_snd = pg.mixer.Sound(str(ASSETS / "shoot.wav"))
    hit_snd = pg.mixer.Sound(str(ASSETS / "hit.wav"))
    power_snd = pg.mixer.Sound(str(ASSETS / "powerup.wav"))
except pg.error:
    pass


###############################################################################
# ── Utility: asset loader with fallback rectangles ───────────────────────── #
###############################################################################

def _load(name: str, size: Tuple[int, int], color: Tuple[int, int, int]):
    p = ASSETS / name
    if p.exists():
        return pg.transform.smoothscale(pg.image.load(p).convert_alpha(), size)
    surf = pg.Surface(size, pg.SRCALPHA)
    surf.fill((*color, 255))
    return surf


# Ship & bullet images -------------------------------------------------------
a_ship = _load("ship.png", (80, 60), (40, 200, 255))

BULLET_IMG: List[pg.Surface] = [
    _load("bullet_lvl1.png", (16, 32), (255, 80, 80)),  # level‑1 single
    _load("bullet_lvl1.png", (20, 40), (80, 255, 80)),  # level‑2 twin
    _load("bullet_lvl1.png", (24, 48), (80, 180, 255)),  # level‑3 triple spread
]
BULLET_SPEED = [12, 14, 16]
SHOT_COOLDOWN = [0.25, 0.20, 0.15]
MAX_GUN_LEVEL = len(BULLET_IMG)

# Chicken breeds -------------------------------------------------------------
CHICKEN_TYPES = [
    {
        "img": _load("chicken_easy.png", (60, 60), (255, 240, 40)),
        "hp": 1,
        "speed": 1.0,
        "points": 10,
    },
    {
        "img": _load("chicken_med.png", (70, 70), (255, 160, 40)),
        "hp": 2,
        "speed": 1.2,
        "points": 20,
    },
    {
        "img": _load("chicken_hard.png", (80, 80), (255, 80, 40)),
        "hp": 3,
        "speed": 1.4,
        "points": 30,
    },
]

a_egg = _load("egg.png", (14, 20), (255, 255, 255))
a_capsule = _load("capsule.png", (26, 26), (180, 180, 255))
a_heart = _load("NEU.png", (48, 48), (255, 0, 0))
# a_heart = pg.image.load("NEU.png")
# a_heart = pg.transform.smoothscale(a_heart, (48, 48))
###############################################################################
# ── Starfield background ─────────────────────────────────────────────────── #
###############################################################################
stars = [
    (random.randrange(0, W), random.randrange(0, H), random.uniform(0.8, 2.2))
    for _ in range(STAR_COUNT)
]


def draw_starfield(dt: int):
    for i, (x, y, s) in enumerate(stars):
        y += s * dt * 0.1
        if y > H:
            y -= H
        stars[i] = (x, y, s)
        pg.draw.circle(screen, (200, 200, 255), (int(x), int(y)), 1)


###############################################################################
# ── Sprite classes ───────────────────────────────────────────────────────── #
###############################################################################
class Bullet(pg.sprite.Sprite):
    def __init__(self, x: int, y: int, vx: float, vy: float, level: int):
        super().__init__()
        self.image = BULLET_IMG[level]
        self.rect = self.image.get_rect(center=(x, y))
        self.vx = vx
        self.vy = vy
        self.dmg = 1 # hit points dealt

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.bottom < 0 or self.rect.top > H or self.rect.right < 0 or self.rect.left > W:
            self.kill()


class Egg(pg.sprite.Sprite):
    def __init__(self, x: int, y: int, speed: float):
        super().__init__()
        self.image = a_egg
        self.rect = self.image.get_rect(center=(x, y))
        self.v = speed

    def update(self):
        self.rect.y += self.v
        if self.rect.top > H:
            self.kill()


class PowerUp(pg.sprite.Sprite):
    def __init__(self, x: int, y: int):
        super().__init__()
        self.image = a_capsule
        self.rect = self.image.get_rect(center=(x, y))
        self.v = 3

    def update(self):
        self.rect.y += self.v
        if self.rect.top > H:
            self.kill()


class Chicken(pg.sprite.Sprite):
    def __init__(self, x: int, y: int, ctype: dict, wave_idx: int):
        super().__init__()
        self.img = ctype["img"]
        self.image = self.img
        self.rect = self.image.get_rect(center=(x, y))
        self.dir = 1
        self.base_x = x
        self.base_y = y
        self.t = 0
        self.hp = ctype["hp"]
        self.points = ctype["points"]
        self.speed = ctype["speed"]
        self.wave = wave_idx

    def update(self):
        self.t += 1
        amp = 40 + 4 * self.wave
        self.rect.x += self.dir * self.speed
        if abs(self.rect.x - self.base_x) > amp:
            self.dir *= -1
        self.rect.y = self.base_y + int(8 * math.sin(self.t * 0.07))
        if random.random() < 0.002 + 0.0004 * self.wave:
            eggs.add(Egg(self.rect.centerx, self.rect.bottom, 4 + 0.2 * self.wave))

    def hit(self, dmg: int):
        self.hp -= dmg
        if self.hp <= 0:
            self.kill()
            return True
        return False


###############################################################################
# ── Game helpers ─────────────────────────────────────────────────────────── #
###############################################################################

def spawn_wave(level: int):
    """Populate chickens based on current level."""
    chickens.empty();
    eggs.empty();
    bullets.empty();
    powerups.empty()
    tier = min(level // 3, len(CHICKEN_TYPES) - 1)  # unlock tougher breeds
    ctype = CHICKEN_TYPES[tier]
    cols = 7 + tier
    rows = 3 + level // 2
    spacing_x = 70
    x0 = W / 2 - (cols - 1) * spacing_x / 2
    for r in range(rows):
        for c in range(cols):
            x = int(x0 + c * spacing_x)
            y = 100 + r * 80
            chickens.add(Chicken(x, y, ctype, level))


def draw_hud(score: int, lives: int, level: int, gun_lvl: int):
    # ── right-aligned numeric info ──────────────────────────────────────
    # Level (top-right)
    level_surf = hud_font.render(f"Level: {level}", True, (255, 255, 255))
    x_right    = W - level_surf.get_width() - 10
    y_top      = 12
    screen.blit(level_surf, (x_right, y_top))

    # Score (just below Level)
    score_surf = hud_font.render(f"Score: {score}", True, (255, 255, 255))
    y_score    = y_top + level_surf.get_height() + 6
    screen.blit(score_surf, (W - score_surf.get_width() - 10, y_score))

    # Gun (just below Score)
    gun_surf   = hud_font.render(f"Gun: {gun_lvl}", True, ( 80, 200, 255))
    y_gun      = y_score + score_surf.get_height() + 6
    screen.blit(gun_surf,   (W - gun_surf.get_width() - 10, y_gun))

    # ── centred ♥ lives indicator (larger font) ─────────────────────────
    # hearts     = "♥" * lives
    # hearts_sf  = heart_font.render(hearts, True, (255, 60, 60))
    # screen.blit(hearts_sf, hearts_sf.get_rect(midtop=(W // 2, 8)))
    total_w = lives * (a_heart.get_width() + 20)
    x_start = (W - total_w) // 2  # centre the whole row
    for i in range(lives):
        screen.blit(a_heart, (x_start + i * (a_heart.get_width() + 20), 8))
###############################################################################
# ── Main loop ─────────────────────────────────────────────────────────────── #
###############################################################################

def main():
    # ── Webcam init ──────────────────────────────────────────────────────── #
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else 0)
    if not cam.isOpened():
        print("❌ Webcam not found");
        sys.exit(1)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    t0 = time.time()
    threading.Thread(target=_capture, args=(cam, t0), daemon=True).start()
    threading.Thread(target=_infer, daemon=True).start()

    global bullets, eggs, chickens, powerups
    bullets = pg.sprite.Group()
    eggs = pg.sprite.Group()
    chickens = pg.sprite.Group()
    powerups = pg.sprite.Group()

    ship = pg.Rect(W // 2 - 40, SHIP_Y, 80, 60)
    level = 1;
    score = 0;
    lives = 3;
    gun_lvl = 0
    shot_cd = SHOT_COOLDOWN[gun_lvl];
    last_shot = 0.0
    spawn_wave(level)
    game_over = False

    while not stop_event.is_set():
        dt = clock.tick(60)  # ms frame time for starfield

        # ▸ Event handling ---------------------------------------------------
        for e in pg.event.get():
            if e.type == pg.QUIT or (e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE):
                stop_event.set()
        if game_over and restart_signal.is_set():
            restart_signal.clear()
            level = score = 0;
            level = 1  # reset vars
            lives = 3;
            gun_lvl = 0
            shot_cd = SHOT_COOLDOWN[0]
            spawn_wave(level)
            game_over = False

        if not game_over:
            # Hand‑control ---------------------------------------------------
            with state_lock:
                cx = centroid_x_norm
            if cx is not None:
                ship.centerx = int(cx * W)
                ship.clamp_ip(pg.Rect(0, SHIP_Y, W, 1))
            # Shooting (closed fist) ---------------------------------------
            if fire_signal.is_set():
                fire_signal.clear()
                if time.time() - last_shot > shot_cd:
                    # pattern depends on gun level ------------------------
                    if gun_lvl == 0:
                        bullets.add(Bullet(ship.centerx, ship.top, 0, -BULLET_SPEED[0], gun_lvl))
                    elif gun_lvl == 1:
                        bullets.add(Bullet(ship.centerx - 12, ship.top, 0, -BULLET_SPEED[1], gun_lvl))
                        bullets.add(Bullet(ship.centerx + 12, ship.top, 0, -BULLET_SPEED[1], gun_lvl))
                    else:  # triple spread
                        bullets.add(Bullet(ship.centerx, ship.top, 0, -BULLET_SPEED[2], gun_lvl))
                        bullets.add(Bullet(ship.centerx, ship.top, -3, -BULLET_SPEED[2], gun_lvl))
                        bullets.add(Bullet(ship.centerx, ship.top, +3, -BULLET_SPEED[2], gun_lvl))
                    if shoot_snd: shoot_snd.play()
                    last_shot = time.time()

            # Update sprites ----------------------------------------------
            bullets.update();
            eggs.update();
            chickens.update();
            powerups.update()

            # Bullet‑chicken collisions with HP handling -------------------
            for bullet in bullets.sprites():
                hits = pg.sprite.spritecollide(bullet, chickens, False)
                if hits:
                    bullet.kill()
                    for ch in hits:
                        died = ch.hit(bullet.dmg)
                        if died:
                            score += ch.points
                            # 10% chance spawn powerup capsule
                            if random.random() < 0.10:
                                powerups.add(PowerUp(ch.rect.centerx, ch.rect.centery))
            # Eggs hitting ship -------------------------------------------
            if any(egg.rect.colliderect(ship) for egg in eggs):
                eggs.empty();
                lives -= 1
                gun_lvl = 0
                shot_cd = SHOT_COOLDOWN[gun_lvl]
                if hit_snd: hit_snd.play()
                if lives <= 0: game_over = True
            # Power‑up pickup ---------------------------------------------
            for pu in powerups:
                if pu.rect.colliderect(ship):  # <-- works with a plain Rect
                    pu.kill()  # remove the capsule
                    gun_lvl = min(gun_lvl + 1, MAX_GUN_LEVEL - 1)
                    shot_cd = SHOT_COOLDOWN[gun_lvl]
                    if power_snd:
                        power_snd.play()
            # Next wave ----------------------------------------------------
            if not chickens and not game_over:
                level += 1;
                spawn_wave(level)

        # ▸ Drawing ---------------------------------------------------------
        screen.fill((5, 5, 20))
        draw_starfield(dt)
        screen.blit(a_ship, ship.topleft)
        chickens.draw(screen);
        bullets.draw(screen);
        eggs.draw(screen);
        powerups.draw(screen)

        # Webcam overlay (top‑left) ----------------------------------------
        if latest_frame is not None:
            cam_w = W // 4
            cam_h = int(latest_frame.shape[0] * cam_w / latest_frame.shape[1])
            cam_small = cv2.resize(latest_frame, (cam_w, cam_h), interpolation=cv2.INTER_AREA)
            cam_rgb = cv2.cvtColor(cam_small, cv2.COLOR_BGR2RGB)
            cam_surf = pg.surfarray.make_surface(np.transpose(cam_rgb, (1, 0, 2)))
            screen.blit(cam_surf, (0, 0))
            with state_lock:
                cx, cy = centroid_x_norm, centroid_y_norm
            if cx is not None and cy is not None:
                px = int(W*cx // 4)
                py = int(H*cy // 4)
                pg.draw.circle(screen, (255, 0, 0), (px, py), 6)

        draw_hud(score, lives, level, gun_lvl + 1)

        if game_over:
            txt = font_big.render("GAME OVER", True, (255, 80, 80))
            sub = font.render("Show Thumb Up to restart", True, (200, 200, 200))
            screen.blit(txt, txt.get_rect(center=(W // 2, H // 2 - 20)))
            screen.blit(sub, sub.get_rect(center=(W // 2, H // 2 + 30)))

        pg.display.flip()

    # Clean‑up -------------------------------------------------------------
    pg.quit();
    cam.release();
    cv2.destroyAllWindows()


###############################################################################
if __name__ == "__main__":
    try:
        main()
    finally:
        stop_event.set()

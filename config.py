import pygame as pg
from pathlib import Path

# Thư mục gốc và Assets
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"

# Kích thước màn hình ban đầu (sẽ được cập nhật bằng kích thước thực tế khi chạy Fullscreen)
WIDTH = 900
HEIGHT = 800

# Thiết lập tàu vũ trụ
SHIP_WIDTH = 80
SHIP_HEIGHT = 60
SHIP_SPEED_KB = 10  # Tốc độ di chuyển bằng bàn phím (pixels/frame)

# Thiết lập sao nền (Starfield)
STAR_COUNT = 140
STAR_LAYERS = [
    {"speed_mult": 0.5, "color": (120, 120, 180), "size": 1},   # Sao ở xa (chậm, mờ)
    {"speed_mult": 1.0, "color": (180, 180, 220), "size": 1.5}, # Sao trung bình
    {"speed_mult": 2.0, "color": (230, 230, 255), "size": 2},   # Sao ở gần (nhanh, sáng)
]

# Vũ khí & Đạn
MAX_GUN_LEVEL = 4  # Tăng lên 4 cấp độ súng!

BULLET_SETTINGS = {
    0: {"size": (16, 32), "color": (255, 80, 80), "speed": 12, "cooldown": 0.25},    # Cấp 1: Đạn đơn
    1: {"size": (20, 40), "color": (80, 255, 80), "speed": 14, "cooldown": 0.20},    # Cấp 2: Đạn đôi
    2: {"size": (24, 48), "color": (80, 180, 255), "speed": 16, "cooldown": 0.15},   # Cấp 3: Đạn tỏa 3 tia
    3: {"size": (28, 56), "color": (255, 100, 255), "speed": 18, "cooldown": 0.12},  # Cấp 4: Plasma Burst tỏa 5 tia!
}

# Các giống gà
CHICKEN_BREEDS = [
    {
        "img_name": "chicken_easy.png",
        "size": (60, 60),
        "color": (255, 240, 40),
        "hp": 1,
        "speed": 1.0,
        "points": 10,
    },
    {
        "img_name": "chicken_med.png",
        "size": (70, 70),
        "color": (255, 160, 40),
        "hp": 2,
        "speed": 1.2,
        "points": 20,
    },
    {
        "img_name": "chicken_hard.png",
        "size": (80, 80),
        "color": (255, 80, 40),
        "hp": 3,
        "speed": 1.4,
        "points": 30,
    },
]

# Boss Chicken Settings
BOSS_SETTINGS = {
    "img_name": "chicken_boss.png", # Có thể thay bằng hình ảnh Boss riêng nếu có
    "size": (200, 200),
    "color": (255, 50, 50),
    "hp_base": 20,       # Máu cơ bản của Boss (sẽ tăng theo màn chơi)
    "speed": 2.0,
    "points": 500,
    "egg_speed": 6.0,
}

# Âm thanh
SOUNDS = {
    "shoot": "shoot.wav",
    "hit": "hit.wav",
    "powerup": "powerup.wav",
    "boss_hit": "hit.wav", # Sử dụng tạm âm thanh hit
    "explosion": "hit.wav",
}

# MediaPipe Hand Tracking Setup
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float32/latest/gesture_recognizer.task"
)
MODEL_PATH = BASE_DIR / "gesture_recognizer.task"
PALM_IDXS = (0, 5, 9, 13, 17)

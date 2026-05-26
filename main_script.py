#!/usr/bin/env python3
"""
Chicken‑Invaders‑by‑Hand 🚀🐔  – *Ultimate HD Edition* (v2.5‑modular‑premium)
====================================================================
Mã nguồn đã được phân chia module hoá (modularized) thành các phần tách biệt
để dễ dàng quản lý, mở rộng và phát triển các tính năng cao cấp mới:

• config.py         : Cấu hình chung, cài đặt súng, giống gà, sao nền, âm thanh.
• assets_loader.py  : Trình tải âm thanh, hình ảnh và hệ thống dự phòng (fallback) tài nguyên.
• hand_tracker.py   : Trình quản lý camera và nhận diện cử chỉ MediaPipe đa luồng.
• sprites.py        : Các lớp thực thể (Đạn cấp 4, Trứng, Gà, Trùm khổng lồ, Khiên bảo vệ, Hạt lông vũ).
• game_engine.py    : Lõi vòng lặp chính của game, bộ xử lý va chạm, combo, rung màn hình.
• main.py           : Điểm chạy chính của kiến trúc mới.

Lưu ý: File main_script.py này hiện đóng vai trò là một Wrapper tương thích ngược. 
Khi chạy file này, nó sẽ tự động kích hoạt kiến trúc đa module mới ở file main.py.
"""
import sys
from pathlib import Path

# Thêm thư mục hiện tại của file vào sys.path để hỗ trợ chạy từ bất kỳ đâu
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

try:
    from main import main as run_game
except ImportError as e:
    print(f"❌ Không thể nạp module game mới: {e}")
    print("Vui lòng đảm bảo các file config.py, assets_loader.py, hand_tracker.py, sprites.py, game_engine.py và main.py đều nằm chung thư mục với file này.")
    sys.exit(1)

if __name__ == "__main__":
    run_game()

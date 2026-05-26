#!/usr/bin/env python3
"""
Chicken Invaders (Hand & Fallback Edition)
------------------------------------------
Bản nâng cấp tối ưu hóa kiến trúc đa module, hỗ trợ:
- Điều khiển bằng Webcam + Cử chỉ MediaPipe
- Điều khiển dự phòng bằng Chuột hoặc Bàn phím (nếu không có camera hoặc người dùng tự chọn)
- Các tính năng nâng cao: Trận chiến Trùm (Boss), Hệ thống Khiên (Shield), Combo điểm, Rung màn hình và Hệ thống Hạt lông gà.
"""
from game_engine import Game

def main():
    game = Game()
    game.run()

if __name__ == "__main__":
    main()

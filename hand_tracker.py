import threading
import queue
import time
from pathlib import Path
import urllib.request
import numpy as np
import cv2
import mediapipe as mp
from typing import Tuple, Optional
import config


class HandTracker:
    def __init__(self):
        self.centroid_x_norm: Optional[float] = None
        self.centroid_y_norm: Optional[float] = None
        self.fire_signal = threading.Event()
        self.restart_signal = threading.Event()
        self.state_lock = threading.Lock()
        
        self.frame_queue: "queue.Queue[Tuple[int, cv2.Mat]]" = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.latest_frame: Optional[np.ndarray] = None
        self.cam = None
        self.webcam_active = False
        self.threads = []

    def start(self) -> bool:
        """Khởi động hệ thống tracking bàn tay bằng webcam. Trả về True nếu thành công."""
        # 1. Tải Model MediaPipe nếu chưa tồn tại
        if not config.MODEL_PATH.exists():
            print("⏬ Đang tải mô hình MediaPipe Gesture Recognizer ...")
            try:
                urllib.request.urlretrieve(config.MODEL_URL, config.MODEL_PATH)
                print("✅ Tải mô hình thành công.")
            except Exception as e:
                print(f"❌ Không thể tải mô hình MediaPipe: {e}")
                self.webcam_active = False
                return False

        # 2. Khởi tạo Camera
        try:
            import os
            # Sử dụng CAP_DSHOW trên Windows để mở camera nhanh hơn
            self.cam = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
            if not self.cam.isOpened():
                print("⚠️ Không tìm thấy Webcam hoặc không mở được camera. Chuyển sang dùng Chuột/Bàn phím.")
                self.webcam_active = False
                return False
        except Exception as e:
            print(f"❌ Lỗi khi mở camera: {e}")
            self.webcam_active = False
            return False

        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.webcam_active = True

        # 3. Chạy các luồng phụ xử lý song song (Producer/Consumer)
        t0 = time.time()
        cap_thread = threading.Thread(target=self._capture, args=(t0,), daemon=True)
        infer_thread = threading.Thread(target=self._infer, daemon=True)
        
        cap_thread.start()
        infer_thread.start()
        self.threads = [cap_thread, infer_thread]
        
        print("🚀 Hệ thống nhận dạng bàn tay (Webcam) đã khởi động thành công.")
        return True

    def _capture(self, t0: float):
        """Luồng đọc khung hình từ webcam, lật gương và đẩy vào hàng đợi."""
        while not self.stop_event.is_set():
            try:
                if self.cam is None:
                    self.stop_event.set()
                    break
                
                ok, frame = self.cam.read()
                if not ok:
                    self.stop_event.set()
                    break
                
                # Lật gương (trái sang phải) để tạo cảm giác di chuyển tự nhiên
                frame = cv2.flip(frame, 1)
                self.latest_frame = frame  # Gán nhẹ nhàng qua reference
                
                ts = int((time.time() - t0) * 1000)
                
                # Giải phóng hàng đợi cũ nếu bị nghẽn
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                
                self.frame_queue.put((ts, frame), False) # type:ignore
            except Exception as e:
                print(f"⚠️ Lỗi trong luồng Capture webcam: {e}")
                time.sleep(0.05)

    def _infer(self):
        """Luồng nhận diện cử chỉ bàn tay bằng MediaPipe."""
        # Cài đặt MediaPipe Options
        BaseOptions = mp.tasks.BaseOptions
        RecognizerOpt = mp.tasks.vision.GestureRecognizerOptions
        Recognizer = mp.tasks.vision.GestureRecognizer
        RunningMode = mp.tasks.vision.RunningMode

        options = RecognizerOpt(
            base_options=BaseOptions(model_asset_path=str(config.MODEL_PATH)),
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        with Recognizer.create_from_options(options) as rec:
            while not self.stop_event.is_set():
                try:
                    try:
                        ts, frame = self.frame_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    res = rec.recognize_for_video(mp_img, ts)
                    
                    if res.hand_landmarks:
                        hand = res.hand_landmarks[0]
                        
                        # Tính centroid của bàn tay dựa trên 5 điểm lòng bàn tay
                        cx = sum(hand[i].x for i in config.PALM_IDXS) / len(config.PALM_IDXS)
                        cy = sum(hand[i].y for i in config.PALM_IDXS) / len(config.PALM_IDXS)
                        
                        with self.state_lock:
                            self.centroid_x_norm = cx
                            self.centroid_y_norm = cy
                            
                        # Kiểm tra cử chỉ bắn hoặc khởi động lại
                        if res.gestures:
                            g = res.gestures[0][0].category_name.lower()
                            if g in {"closed_fist", "thumb_down", "okay"}:  # Nắm đấm -> bắn
                                self.fire_signal.set()
                            elif g == "thumb_up":  # Ngón tay cái chỉ lên -> restart
                                self.restart_signal.set()
                    else:
                        # Không thấy tay
                        with self.state_lock:
                            self.centroid_x_norm = None
                            self.centroid_y_norm = None
                            
                except Exception as e:
                    # Tránh văng luồng khi có lỗi nhận diện nhỏ
                    pass

    def get_position(self) -> Tuple[Optional[float], Optional[float]]:
        """Lấy toạ độ chuẩn hoá (x, y) trong khoảng [0, 1] của bàn tay."""
        with self.state_lock:
            return self.centroid_x_norm, self.centroid_y_norm

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Lấy khung hình thô mới nhất phục vụ vẽ overlay."""
        return self.latest_frame

    def check_fire(self) -> bool:
        """Kiểm tra xem cử chỉ bắn có được kích hoạt, tự động reset tín hiệu."""
        if self.fire_signal.is_set():
            self.fire_signal.clear()
            return True
        return False

    def check_restart(self) -> bool:
        """Kiểm tra cử chỉ restart có được kích hoạt, tự động reset tín hiệu."""
        if self.restart_signal.is_set():
            self.restart_signal.clear()
            return True
        return False

    def close(self):
        """Dừng các luồng và giải phóng webcam."""
        self.stop_event.set()
        if self.cam:
            self.cam.release()
            self.cam = None
        print("🧹 Đã đóng kết nối camera và dọn dẹp tài nguyên HandTracker.")

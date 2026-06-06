import pygame as pg
import sys
from typing import Tuple, Dict, List, Optional
import config

class AssetsLoader:
    def __init__(self):
        self.images: Dict[str, pg.Surface] = {}
        self.sounds: Dict[str, Optional[pg.mixer.Sound]] = {}
        self.bullet_imgs: List[pg.Surface] = []
        self.chicken_imgs: List[pg.Surface] = []
        
        # Cố gắng khởi tạo mixer
        if not pg.mixer.get_init():
            try:
                pg.mixer.init()
            except pg.error:
                print("⚠️ Cảnh báo: Không thể khởi tạo pygame.mixer (Hệ thống âm thanh bị vô hiệu hóa).")

    def load_all(self):
        """Tải toàn bộ tài nguyên hình ảnh và âm thanh."""
        # 1. Tải ảnh Tàu Vũ Trụ
        self.images["ship"] = self._load_image(
            "ship.png", 
            (config.SHIP_WIDTH, config.SHIP_HEIGHT), 
            (40, 200, 255)
        )
        
        # 2. Tải ảnh Trứng & Vật phẩm & Tim mạng sống & Khiên bảo vệ
        self.images["egg"] = self._load_image("redegg.png", (22, 30), (255, 255, 255))
        self.images["capsule"] = self._load_image("capsule.png", (26, 26), (180, 180, 255))
        self.images["heart"] = self._load_image("heart.png", (48, 48), (255, 50, 50))
        self.images["shield_item"] = self._load_image("shield_item.png", (26, 26), (80, 220, 255)) # Hộp khiên màu xanh sáng

        # 3. Tải đạn cho từng cấp độ súng (4 cấp độ súng!)
        self.bullet_imgs = []
        for lvl in range(config.MAX_GUN_LEVEL):
            settings = config.BULLET_SETTINGS[lvl]
            img_file = f"bullet_lvl{lvl+1}.png"
            # Thử tìm file tương ứng, nếu không tìm thấy thì dùng bullet_lvl1.png làm gốc
            if not (config.ASSETS_DIR / img_file).exists():
                img_file = "bullet_lvl1.png"
            
            bullet_surf = self._load_image(img_file, settings["size"], settings["color"])
            self.bullet_imgs.append(bullet_surf)

        # 4. Tải các giống gà
        self.chicken_imgs = []
        for breed in config.CHICKEN_BREEDS:
            chicken_surf = self._load_image(breed["img_name"], breed["size"], breed["color"])
            self.chicken_imgs.append(chicken_surf)

        # Ảnh Boss (Dùng gà khó nhất phóng to, hoặc hình ảnh tương đương)
        self.images["chicken_boss"] = self._load_image(
            config.BOSS_SETTINGS["img_name"], 
            config.BOSS_SETTINGS["size"], 
            config.BOSS_SETTINGS["color"]
        )

        # 5. Tải âm thanh
        for name, file in config.SOUNDS.items():
            self.sounds[name] = self._load_sound(file)

    def _load_image(self, filename: str, size: Tuple[int, int], fallback_color: Tuple[int, int, int]) -> pg.Surface:
        """Tải một hình ảnh, nếu lỗi thì tự động tạo Surface hình vuông màu fallback."""
        path = config.ASSETS_DIR / filename
        if path.exists():
            try:
                img = pg.image.load(str(path)).convert_alpha()
                return pg.transform.smoothscale(img, size)
            except pg.error as e:
                print(f"⚠️ Lỗi khi tải ảnh {filename}: {e}. Dùng hình ảnh thay thế.")
        
        # Fallback: Tạo hình tròn hoặc hình chữ nhật màu
        surf = pg.Surface(size, pg.SRCALPHA)
        # Vẽ một vòng tròn đầy nghệ thuật để làm hình thế thay vì hộp màu trơn
        pg.draw.ellipse(surf, (*fallback_color, 255), (0, 0, size[0], size[1]))
        pg.draw.ellipse(surf, (255, 255, 255, 180), (size[0]//4, size[1]//4, size[0]//2, size[1]//2)) # Điểm sáng
        return surf

    def _load_sound(self, filename: str) -> Optional[pg.mixer.Sound]:
        """Tải âm thanh an toàn, trả về None nếu file thiếu hoặc lỗi mixer."""
        if not pg.mixer.get_init():
            return None
        path = config.ASSETS_DIR / filename
        if path.exists():
            try:
                return pg.mixer.Sound(str(path))
            except pg.error as e:
                print(f"⚠️ Lỗi khi tải âm thanh {filename}: {e}")
        return None

    def play_sound(self, name: str):
        """Phát âm thanh an toàn."""
        snd = self.sounds.get(name)
        if snd:
            snd.play()

import pygame as pg
import math
import random
from typing import Tuple, List, Optional
import config


class Bullet(pg.sprite.Sprite):
    def __init__(
        self, x: int, y: int, vx: float, vy: float, level: int, img: pg.Surface
    ):
        super().__init__()
        self.image = img
        self.rect = self.image.get_rect(center=(x, y))
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vx = vx
        self.vy = vy
        # Sát thương gây ra (Cấp càng cao sát thương càng mạnh)
        self.dmg = 1 if level < 3 else 2

    def update(self, w: int, h: int):
        self.x += self.vx
        self.y += self.vy
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)
        # Tự hủy khi ra khỏi màn hình
        if (
            self.rect.bottom < 0
            or self.rect.top > h
            or self.rect.right < 0
            or self.rect.left > w
        ):
            self.kill()


class Egg(pg.sprite.Sprite):
    def __init__(self, x: int, y: int, vx: float, vy: float, img: pg.Surface):
        super().__init__()
        self.image = img
        self.rect = self.image.get_rect(center=(x, y))
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vx = vx
        self.vy = vy

    def update(self, w: int, h: int):
        self.x += self.vx
        self.y += self.vy
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)
        if (
            self.rect.bottom < 0
            or self.rect.top > h
            or self.rect.right < 0
            or self.rect.left > w
        ):
            self.kill()


class PowerUp(pg.sprite.Sprite):
    TYPES = ["gun", "shield", "heart"]

    def __init__(self, x: int, y: int, p_type: str, img: pg.Surface):
        super().__init__()
        self.p_type = p_type  # "gun", "shield", "heart"
        self.image = img
        self.rect = self.image.get_rect(center=(x, y))
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vy = 3.0

    def update(self, w: int, h: int):
        self.y += self.vy
        self.rect.y = int(self.y)
        if self.rect.top > h:
            self.kill()


class Chicken(pg.sprite.Sprite):
    def __init__(
        self,
        x: int,
        y: int,
        img: pg.Surface,
        wave_idx: int,
        breed_data: dict,
        eggs_group: pg.sprite.Group,
        egg_img: pg.Surface,
    ):
        super().__init__()
        self.image = img
        self.rect = self.image.get_rect(center=(x, y))
        self.dir = 1
        self.base_x = x
        self.base_y = y
        self.t = random.randint(0, 100)  # Lệch pha hoạt ảnh cho tự nhiên

        self.hp = breed_data["hp"]
        self.points = breed_data["points"]
        self.speed = breed_data["speed"]
        self.wave = wave_idx

        self.eggs_group = eggs_group
        self.egg_img = egg_img

    def update(self, w: int, h: int):
        self.t += 1
        amp = 40 + 4 * self.wave
        self.rect.x += self.dir * self.speed

        if abs(self.rect.x - self.base_x) > amp:
            self.dir *= -1

        # Di chuyển dạng sóng lượn (sin)
        self.rect.y = self.base_y + int(8 * math.sin(self.t * 0.07))

        # Bắn trứng ngẫu nhiên dựa trên cấp màn chơi
        shoot_prob = 0.0002 + 0.0004 * self.wave
        if random.random() < shoot_prob:
            egg_speed = 4 + 0.2 * self.wave
            new_egg = Egg(
                self.rect.centerx, self.rect.bottom, 0, egg_speed, self.egg_img
            )
            self.eggs_group.add(new_egg)

    def hit(self, dmg: int) -> bool:
        """Trừ máu gà. Trả về True nếu gà bị tiêu diệt."""
        self.hp -= dmg
        if self.hp <= 0:
            self.kill()
            return True
        return False


class Boss(pg.sprite.Sprite):
    def __init__(
        self,
        x: int,
        y: int,
        img: pg.Surface,
        wave_idx: int,
        eggs_group: pg.sprite.Group,
        egg_img: pg.Surface,
    ):
        super().__init__()
        self.image = img
        self.rect = self.image.get_rect(center=(x, y))
        self.max_hp = config.BOSS_SETTINGS["hp_base"] + wave_idx * 15
        self.hp = self.max_hp
        self.points = config.BOSS_SETTINGS["points"]
        self.speed = config.BOSS_SETTINGS["speed"]
        self.wave = wave_idx

        self.eggs_group = eggs_group
        self.egg_img = egg_img

        self.dir = 1
        self.t = 0
        self.flash_t = 0  # Trạng thái chớp sáng khi bị bắn trúng
        self.shoot_cooldown = 0

        # Lưu hình ảnh gốc để phục vụ hiệu ứng chớp màu đỏ/trắng
        self.orig_image = img

    def update(self, w: int, h: int):
        self.t += 1

        # 1. Di chuyển ngang chậm và đảo hướng ở mép màn hình
        self.rect.x += self.dir * self.speed
        if self.rect.left < 50 or self.rect.right > w - 50:
            self.dir *= -1
            self.rect.y = min(
                self.rect.y + 15, h // 3
            )  # Đi dần xuống nhưng không quá 1/3 màn hình

        # 2. Xử lý hoạt ảnh chớp sáng khi bị trúng đạn
        if self.flash_t > 0:
            self.flash_t -= 1
            if self.flash_t % 4 < 2:
                # Vẽ một lớp màu đỏ đè lên
                tint_surf = self.orig_image.copy()
                tint_surf.fill((255, 100, 100, 150), special_flags=pg.BLEND_RGBA_MULT)
                self.image = tint_surf
            else:
                self.image = self.orig_image
        else:
            self.image = self.orig_image

        # 3. Logic bắn đạn nâng cao (Nhiều Pattern khác nhau)
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        else:
            # Chọn ngẫu nhiên kiểu tấn công
            attack_type = random.choice(["spread", "spiral", "aimed"])
            egg_speed = config.BOSS_SETTINGS["egg_speed"] + 0.1 * self.wave

            if attack_type == "spread":
                # Kiểu 1: Bắn tỏa hình quạt 5 quả trứng
                for angle in [-30, -15, 0, 15, 30]:
                    rad = math.radians(angle + 90)  # Xoay xuống dưới
                    vx = egg_speed * math.cos(rad)
                    vy = egg_speed * math.sin(rad)
                    self.eggs_group.add(
                        Egg(
                            self.rect.centerx,
                            self.rect.bottom - 20,
                            vx,
                            vy,
                            self.egg_img,
                        )
                    )
                self.shoot_cooldown = random.randint(
                    90, 150
                )  # Cooldown lâu hơn cho đợt đạn lớn

            elif attack_type == "spiral":
                # Kiểu 2: Đợt đạn xoáy ốc (bắn nhanh liên tục 4 quả lệch hướng nhẹ)
                for step in range(4):
                    vx = (step - 1.5) * 1.5
                    self.eggs_group.add(
                        Egg(
                            self.rect.centerx,
                            self.rect.bottom - 20,
                            vx,
                            egg_speed,
                            self.egg_img,
                        )
                    )
                self.shoot_cooldown = random.randint(60, 100)

            elif attack_type == "aimed":
                # Kiểu 3: Nhắm bắn thẳng về phía tàu của người chơi
                # Ta cần toạ độ tàu, nhưng để đơn giản, ta bắn 3 luồng trứng chéo xuống dưới
                self.eggs_group.add(
                    Egg(
                        self.rect.centerx,
                        self.rect.bottom - 20,
                        0,
                        egg_speed * 1.2,
                        self.egg_img,
                    )
                )
                self.eggs_group.add(
                    Egg(
                        self.rect.centerx - 40,
                        self.rect.bottom - 20,
                        -1.0,
                        egg_speed * 1.2,
                        self.egg_img,
                    )
                )
                self.eggs_group.add(
                    Egg(
                        self.rect.centerx + 40,
                        self.rect.bottom - 20,
                        1.0,
                        egg_speed * 1.2,
                        self.egg_img,
                    )
                )
                self.shoot_cooldown = random.randint(80, 120)

    def hit(self, dmg: int) -> bool:
        """Trừ máu Boss. Kích hoạt hiệu ứng chớp sáng. Trả về True nếu bị tiêu diệt."""
        self.hp -= dmg
        self.flash_t = 15  # Chớp sáng trong 15 frames
        if self.hp <= 0:
            self.kill()
            return True
        return False


class Particle(pg.sprite.Sprite):
    def __init__(self, x: int, y: int, color: Tuple[int, int, int]):
        super().__init__()
        self.size = random.randint(4, 9)
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)

        # Vẽ một hạt lông vũ tròn nhạt mềm mại
        self.color = color
        pg.draw.circle(
            self.image, (*color, 255), (self.size // 2, self.size // 2), self.size // 2
        )

        self.rect = self.image.get_rect(center=(x, y))

        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        # Vận tốc toả đều 360 độ
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 5.0)
        self.vx = speed * math.cos(angle)
        self.vy = speed * math.sin(angle)

        self.alpha = 255
        self.fade_speed = random.randint(6, 12)
        self.gravity = 0.08  # Rơi nhẹ xuống dưới tạo vẻ tự nhiên

    def update(self, w: int, h: int):
        self.x += self.vx
        self.y += self.vy
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)
        self.vy += self.gravity

        # Giảm kích thước và độ trong suốt
        self.alpha -= self.fade_speed
        if self.alpha <= 0:
            self.kill()
        else:
            # Tạo bản sao ảnh đã giảm alpha
            self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
            pg.draw.circle(
                self.image,
                (*self.color, self.alpha),
                (self.size // 2, self.size // 2),
                self.size // 2,
            )


class Shield(pg.sprite.Sprite):
    def __init__(self, ship_rect: pg.Rect):
        super().__init__()
        self.ship_rect = ship_rect
        self.radius = 60
        self.size = self.radius * 2
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
        self.rect = self.image.get_rect(center=self.ship_rect.center)
        self.t = 0

    def update(self, w: int, h: int):
        self.t += 1
        self.rect.center = self.ship_rect.center

        # Hiệu ứng vòng tròn khiên năng lượng nhấp nháy phát sáng (neon cyan)
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
        alpha = int(100 + 50 * math.sin(self.t * 0.2))  # Hiệu ứng sóng nhấp nháy

        # Vẽ vòng tròn ngoài dày, vòng trong mờ
        pg.draw.circle(
            self.image,
            (80, 200, 255, alpha),
            (self.radius, self.radius),
            self.radius,
            3,
        )
        pg.draw.circle(
            self.image,
            (80, 200, 255, alpha // 3),
            (self.radius, self.radius),
            self.radius - 5,
        )

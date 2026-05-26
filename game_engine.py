import pygame as pg
import cv2
import time
import numpy as np
import random
import sys
from typing import Tuple, List, Optional
import config
from assets_loader import AssetsLoader
from hand_tracker import HandTracker
from sprites import Bullet, Egg, PowerUp, Chicken, Boss, Particle, Shield

class Game:
    def __init__(self):
        pg.init()
        self.info = pg.display.Info()
        self.w = self.info.current_w
        self.h = self.info.current_h
        
        # Thiết lập cửa sổ Fullscreen
        pg.display.set_caption("Chicken Invaders – Hand & Fallback Edition")
        self.screen = pg.display.set_mode((self.w, self.h), pg.FULLSCREEN)
        
        # Surface đệm để hỗ trợ hiệu ứng rung màn hình (Screen Shake)
        self.game_surface = pg.Surface((self.w, self.h))
        
        self.clock = pg.time.Clock()
        self.loader = AssetsLoader()
        self.loader.load_all()
        
        self.tracker = HandTracker()
        self.webcam_available = self.tracker.start()
        
        # Trạng thái điều khiển:
        # Nếu có webcam: mặc định là "hand" (điều khiển bằng tay)
        # Nếu không có: mặc định là "mouse" (di chuột)
        self.control_mode = "hand" if self.webcam_available else "mouse"
        self.show_webcam_overlay = True
        
        # Khởi tạo các nhóm Sprites
        self.bullets = pg.sprite.Group()
        self.eggs = pg.sprite.Group()
        self.chickens = pg.sprite.Group()
        self.powerups = pg.sprite.Group()
        self.particles = pg.sprite.Group()
        self.boss_group = pg.sprite.GroupSingle()
        
        # Vị trí tàu vũ trụ
        self.ship_rect = pg.Rect(self.w // 2 - 40, self.h - 80, config.SHIP_WIDTH, config.SHIP_HEIGHT)
        
        # Lớp khiên bảo vệ
        self.shield_active = False
        self.shield_timer = 0  # Theo số khung hình (frames)
        self.shield_sprite = None
        
        # Các thông số game
        self.level = 1
        self.score = 0
        self.lives = 3
        self.gun_lvl = 0
        self.last_shot_time = 0.0
        self.game_over = False
        
        # Combo System
        self.combo_multiplier = 1.0
        self.last_kill_time = 0.0
        self.combo_timer = 0.0  # Thời gian duy trì combo (3 giây)
        
        # Hiệu ứng rung màn hình
        self.screen_shake_t = 0
        
        # Tạo bụi sao (Parallax Starfield)
        self.stars = []
        for _ in range(config.STAR_COUNT):
            layer_idx = random.randint(0, len(config.STAR_LAYERS) - 1)
            self.stars.append([
                random.randrange(0, self.w),
                random.randrange(0, self.h),
                layer_idx
            ])
            
        # Fonts
        self.hud_font = pg.font.SysFont("arial", 28, bold=True)
        self.small_hud_font = pg.font.SysFont("arial", 18, bold=True)
        self.title_font = pg.font.SysFont("arial", 56, bold=True)
        self.subtitle_font = pg.font.SysFont("arial", 24)
        
        # Khởi tạo màn chơi đầu tiên
        self.spawn_wave()

    def spawn_wave(self):
        """Khởi tạo màn chơi mới."""
        self.bullets.empty()
        self.eggs.empty()
        self.chickens.empty()
        self.powerups.empty()
        self.boss_group.empty()
        # Không xóa hạt lông vũ để màn chuyển tiếp trông mượt mà
        
        # Tắt khiên khi chuyển màn mới
        self.shield_active = False
        self.shield_timer = 0
        self.shield_sprite = None
        
        # Cứ mỗi 5 Level sẽ là BOSS WAVE
        if self.level % 5 == 0:
            boss_chicken = Boss(
                self.w // 2, 
                150, 
                self.loader.images["boss"], 
                self.level, 
                self.eggs, 
                self.loader.images["egg"]
            )
            self.boss_group.add(boss_chicken)
        else:
            # Tính toán số lượng và độ khó gà
            tier = min(self.level // 3, len(config.CHICKEN_BREEDS) - 1)
            breed_data = config.CHICKEN_BREEDS[tier]
            chicken_img = self.loader.chicken_imgs[tier]
            
            cols = 7 + tier
            rows = 3 + min(self.level // 2, 3) # Giới hạn tối đa 6 hàng để tránh chật màn hình
            spacing_x = 75
            x0 = self.w / 2 - (cols - 1) * spacing_x / 2
            
            for r in range(rows):
                for c in range(cols):
                    x = int(x0 + c * spacing_x)
                    y = 120 + r * 75
                    new_ch = Chicken(
                        x, y, 
                        tier, 
                        chicken_img, 
                        self.level, 
                        breed_data, 
                        self.eggs, 
                        self.loader.images["egg"]
                    )
                    self.chickens.add(new_ch)

    def trigger_shake(self, duration: int):
        """Kích hoạt rung màn hình."""
        self.screen_shake_t = duration

    def handle_events(self):
        """Xử lý sự kiện bàn phím/chuột."""
        for e in pg.event.get():
            if e.type == pg.QUIT:
                self.tracker.close()
                pg.quit()
                sys.exit()
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    self.tracker.close()
                    pg.quit()
                    sys.exit()
                elif e.key == pg.K_c:
                    # Chuyển đổi chế độ điều khiển nếu webcam khả dụng
                    if self.webcam_available:
                        if self.control_mode == "hand":
                            self.control_mode = "mouse"
                        elif self.control_mode == "mouse":
                            self.control_mode = "keyboard"
                        else:
                            self.control_mode = "hand"
                    else:
                        # Nếu không có webcam, luân phiên giữa chuột và bàn phím
                        self.control_mode = "keyboard" if self.control_mode == "mouse" else "mouse"
                elif e.key == pg.K_m:
                    # Bật/Tắt Webcam overlay
                    self.show_webcam_overlay = not self.show_webcam_overlay

        # Nhận diện restart từ cử chỉ webcam hoặc bấm chuột/phím Space khi Game Over
        if self.game_over:
            keys = pg.key.get_pressed()
            mouse_clicked = pg.mouse.get_pressed()[0]
            if keys[pg.K_SPACE] or mouse_clicked or self.tracker.check_restart():
                self.reset_game()

    def reset_game(self):
        """Khởi động lại game."""
        self.level = 1
        self.score = 0
        self.lives = 3
        self.gun_lvl = 0
        self.combo_multiplier = 1.0
        self.game_over = False
        self.shield_active = False
        self.shield_timer = 0
        self.shield_sprite = None
        self.spawn_wave()

    def process_ship_controls(self):
        """Xử lý di chuyển tàu vũ trụ và bắn đạn dựa trên chế độ điều khiển."""
        if self.game_over:
            return

        # 1. Di chuyển Tàu
        if self.control_mode == "hand" and self.webcam_available:
            cx, cy = self.tracker.get_position()
            if cx is not None:
                self.ship_rect.centerx = int(cx * self.w)
        elif self.control_mode == "mouse":
            mx, my = pg.mouse.get_pos()
            self.ship_rect.centerx = mx
        elif self.control_mode == "keyboard":
            keys = pg.key.get_pressed()
            if keys[pg.K_a] or keys[pg.K_LEFT]:
                self.ship_rect.x -= config.SHIP_SPEED_KB
            if keys[pg.K_d] or keys[pg.K_RIGHT]:
                self.ship_rect.x += config.SHIP_SPEED_KB

        # Giữ tàu luôn nằm trong phạm vi màn hình
        self.ship_rect.clamp_ip(pg.Rect(0, self.h - 80, self.w, 1))

        # 2. Xử lý Bắn đạn
        want_shoot = False
        if self.control_mode == "hand" and self.webcam_available:
            want_shoot = self.tracker.check_fire()
        elif self.control_mode == "mouse":
            # Click chuột trái để bắn
            want_shoot = pg.mouse.get_pressed()[0]
        elif self.control_mode == "keyboard":
            # Bấm hoặc giữ phím Space để bắn
            want_shoot = pg.key.get_pressed()[pg.K_SPACE]

        if want_shoot:
            now = time.time()
            settings = config.BULLET_SETTINGS[self.gun_lvl]
            cooldown = settings["cooldown"]
            
            if now - self.last_shot_time > cooldown:
                bullet_img = self.loader.bullet_imgs[self.gun_lvl]
                speed = settings["speed"]
                
                # Cấu hình kiểu bắn súng
                if self.gun_lvl == 0:
                    # Cấp 1: Bắn 1 tia thẳng
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, 0, -speed, self.gun_lvl, bullet_img))
                elif self.gun_lvl == 1:
                    # Cấp 2: Bắn song song 2 tia
                    self.bullets.add(Bullet(self.ship_rect.centerx - 14, self.ship_rect.top, 0, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx + 14, self.ship_rect.top, 0, -speed, self.gun_lvl, bullet_img))
                elif self.gun_lvl == 2:
                    # Cấp 3: Bắn tỏa 3 tia
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, 0, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, -2.5, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, +2.5, -speed, self.gun_lvl, bullet_img))
                else:
                    # Cấp 4: Plasma Burst bắn tỏa 5 tia siêu hoành tráng!
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, 0, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, -2, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, +2, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, -4.5, -speed, self.gun_lvl, bullet_img))
                    self.bullets.add(Bullet(self.ship_rect.centerx, self.ship_rect.top, +4.5, -speed, self.gun_lvl, bullet_img))

                self.loader.play_sound("shoot")
                self.last_shot_time = now

    def update_combo(self):
        """Cập nhật hệ thống điểm Combo."""
        now = time.time()
        if now - self.last_kill_time < 3.0: # Trong vòng 3 giây
            # Tăng combo dần tối đa 3x
            self.combo_multiplier = min(self.combo_multiplier + 0.1, 3.0)
        else:
            self.combo_multiplier = 1.0

    def spawn_feather_explosion(self, x: int, y: int, count: int = 12, color: Tuple[int, int, int] = (255, 240, 50)):
        """Sinh ra hiệu ứng lông gà tỏa ra tuyệt đẹp."""
        for _ in range(count):
            self.particles.add(Particle(x, y, color))

    def update(self, dt: int):
        """Cập nhật trạng thái trò chơi."""
        self.process_ship_controls()
        
        if not self.game_over:
            # Cập nhật các Sprites thường
            self.bullets.update(self.w, self.h)
            self.eggs.update(self.w, self.h)
            self.chickens.update(self.w, self.h)
            self.powerups.update(self.w, self.h)
            self.particles.update(self.w, self.h)
            self.boss_group.update(self.w, self.h)
            
            # Cập nhật Khiên bảo vệ
            if self.shield_active:
                self.shield_timer -= 1
                if self.shield_timer <= 0:
                    self.shield_active = False
                    self.shield_sprite = None
                else:
                    if self.shield_sprite is None:
                        self.shield_sprite = Shield(self.ship_rect)
                    self.shield_sprite.update(self.w, self.h)

            # Cập nhật Combo time-out bar
            now = time.time()
            if self.combo_multiplier > 1.0:
                self.combo_timer = max(0.0, 3.0 - (now - self.last_kill_time))
                if self.combo_timer <= 0:
                    self.combo_multiplier = 1.0

            # -------------------------------------------------------------
            # Xử lý va chạm Đạn - Gà thường
            # -------------------------------------------------------------
            for b in self.bullets.sprites():
                hits = pg.sprite.spritecollide(b, self.chickens, False)
                if hits:
                    b.kill()
                    for ch in hits:
                        self.spawn_feather_explosion(ch.rect.centerx, ch.rect.centery, 4, (255, 230, 100))
                        died = ch.hit(b.dmg)
                        if died:
                            # Cập nhật combo và cộng điểm nhân combo
                            self.update_combo()
                            self.last_kill_time = time.time()
                            self.score += int(ch.points * self.combo_multiplier)
                            
                            # Hiệu ứng nổ hạt lông gà đậm hơn khi gà bị tiêu diệt
                            self.spawn_feather_explosion(ch.rect.centerx, ch.rect.centery, 16, (255, 230, 40))
                            self.loader.play_sound("hit")
                            
                            # Tỉ lệ rơi vật phẩm (12% rơi vật phẩm)
                            if random.random() < 0.12:
                                p_type = random.choices(PowerUp.TYPES, weights=[0.60, 0.28, 0.12])[0]
                                if p_type == "gun":
                                    img = self.loader.images["capsule"]
                                elif p_type == "shield":
                                    img = self.loader.images["shield_item"]
                                else:
                                    img = self.loader.images["heart"]
                                    
                                self.powerups.add(PowerUp(ch.rect.centerx, ch.rect.centery, p_type, img))

            # -------------------------------------------------------------
            # Xử lý va chạm Đạn - Gà Boss
            # -------------------------------------------------------------
            boss = self.boss_group.sprite
            if boss:
                for b in self.bullets.sprites():
                    if b.rect.colliderect(boss.rect):
                        b.kill()
                        self.spawn_feather_explosion(b.rect.x, b.rect.y, 5, (255, 100, 100))
                        self.loader.play_sound("boss_hit")
                        
                        died = boss.hit(b.dmg)
                        if died:
                            # Diệt Boss!
                            self.update_combo()
                            self.last_kill_time = time.time()
                            self.score += int(boss.points * self.combo_multiplier)
                            
                            # Nổ lông gà đại tiệc siêu khủng!
                            self.spawn_feather_explosion(boss.rect.centerx, boss.rect.centery, 50, (255, 80, 80))
                            self.loader.play_sound("explosion")
                            
                            # Rơi cùng lúc 3 vật phẩm làm phần thưởng!
                            self.powerups.add(PowerUp(boss.rect.centerx - 40, boss.rect.centery, "gun", self.loader.images["capsule"]))
                            self.powerups.add(PowerUp(boss.rect.centerx, boss.rect.centery, "shield", self.loader.images["shield_item"]))
                            self.powerups.add(PowerUp(boss.rect.centerx + 40, boss.rect.centery, "heart", self.loader.images["heart"]))
                            
                            self.trigger_shake(25)  # Rung màn hình cực mạnh khi nổ Boss

            # -------------------------------------------------------------
            # Xử lý va chạm Trứng - Tàu vũ trụ
            # -------------------------------------------------------------
            collided_eggs = [egg for egg in self.eggs if egg.rect.colliderect(self.ship_rect)]
            if collided_eggs:
                for egg in collided_eggs:
                    egg.kill()
                    if self.shield_active:
                        # Nếu có khiên, phá hủy trứng mà không mất máu
                        self.spawn_feather_explosion(egg.rect.centerx, egg.rect.centery, 8, (100, 200, 255))
                    else:
                        # Bị trúng đạn trứng!
                        self.lives -= 1
                        self.gun_lvl = 0  # Reset súng về cấp 1
                        self.trigger_shake(15)  # Rung lắc màn hình
                        self.loader.play_sound("hit")
                        self.spawn_feather_explosion(self.ship_rect.centerx, self.ship_rect.top, 20, (255, 50, 50))
                        
                        # Xoá trứng đang rơi để tạo cơ hội hồi phục
                        self.eggs.empty()
                        
                        if self.lives <= 0:
                            self.game_over = True
                        break

            # -------------------------------------------------------------
            # Xử lý Tàu ăn Vật phẩm nâng cấp
            # -------------------------------------------------------------
            for pu in self.powerups.sprites():
                if pu.rect.colliderect(self.ship_rect):
                    pu.kill()
                    self.loader.play_sound("powerup")
                    
                    if pu.p_type == "gun":
                        self.gun_lvl = min(self.gun_lvl + 1, config.MAX_GUN_LEVEL - 1)
                    elif pu.p_type == "shield":
                        self.shield_active = True
                        self.shield_timer = 300  # 5 giây (300 frames ở 60fps)
                        self.shield_sprite = Shield(self.ship_rect)
                    elif pu.p_type == "heart":
                        self.lives = min(self.lives + 1, 5) # Tối đa 5 tim

            # -------------------------------------------------------------
            # Kiểm tra hoàn thành Wave chơi
            # -------------------------------------------------------------
            if not self.chickens and not self.boss_group and not self.game_over:
                self.level += 1
                self.spawn_wave()

    def draw_starfield(self, surface: pg.Surface, dt: int):
        """Vẽ sao nền Parallax đa tầng."""
        for i, star in enumerate(self.stars):
            x, y, layer_idx = star
            layer = config.STAR_LAYERS[layer_idx]
            
            # Tốc độ rơi phụ thuộc vào dt và nhân tốc độ của tầng sao
            y += layer["speed_mult"] * dt * 0.1
            if y > self.h:
                y -= self.h
                x = random.randrange(0, self.w)
            
            self.stars[i] = [x, y, layer_idx]
            pg.draw.circle(surface, layer["color"], (int(x), int(y)), int(layer["size"]))

    def draw_hud(self, surface: pg.Surface):
        """Vẽ HUD giao diện sang trọng hiện đại."""
        # 1. Vẽ Level, Score, Gun bên góc phải
        level_txt = self.hud_font.render(f"LEVEL: {self.level}", True, (255, 255, 255))
        score_txt = self.hud_font.render(f"SCORE: {self.score}", True, (80, 255, 120))
        
        control_name = "TAY (Webcam)" if self.control_mode == "hand" else ("CHUỘT" if self.control_mode == "mouse" else "BÀN PHÍM")
        ctrl_txt = self.small_hud_font.render(f"ĐIỀU KHIỂN: {control_name} [C để đổi]", True, (200, 200, 200))
        
        surface.blit(level_txt, (self.w - level_txt.get_width() - 20, 20))
        surface.blit(score_txt, (self.w - score_txt.get_width() - 20, 60))
        surface.blit(ctrl_txt, (self.w - ctrl_txt.get_width() - 20, 100))
        
        # 2. Vẽ cấp độ Gun dưới dạng các vạch năng lượng sáng
        gun_label = self.small_hud_font.render("GUN POWER", True, (80, 200, 255))
        surface.blit(gun_label, (self.w - 180, 140))
        for i in range(config.MAX_GUN_LEVEL):
            color = (80, 200, 255) if i <= self.gun_lvl else (40, 60, 80)
            pg.draw.rect(surface, color, (self.w - 180 + i * 35, 165, 30, 8), border_radius=2)

        # 3. Vẽ tim biểu thị mạng sống ở trên cùng trung tâm
        heart_img = self.loader.images["heart"]
        heart_w = heart_img.get_width()
        total_heart_w = self.lives * (heart_w + 12)
        start_x = (self.w - total_heart_w) // 2
        for i in range(self.lives):
            surface.blit(heart_img, (start_x + i * (heart_w + 12), 15))

        # 4. Hiển thị combo multiplier ở góc trái dưới dạng vòng năng lượng neon
        if self.combo_multiplier > 1.0:
            combo_txt = self.hud_font.render(f"COMBO x{self.combo_multiplier:.1f}", True, (255, 160, 50))
            surface.blit(combo_txt, (20, 20))
            
            # Thanh tiến trình thời gian duy trì combo
            pg.draw.rect(surface, (50, 50, 70), (20, 60, 150, 6), border_radius=3)
            pg.draw.rect(surface, (255, 160, 50), (20, 60, int(150 * (self.combo_timer / 3.0)), 6), border_radius=3)

        # 5. Nếu Khiên đang hoạt động, hiển thị thời gian còn lại
        if self.shield_active:
            shield_label = self.small_hud_font.render(f"🛡️ SHIELD: {self.shield_timer // 60 + 1}s", True, (80, 220, 255))
            surface.blit(shield_label, (20, 90))
            
            # Vạch năng lượng khiên mỏng chạy
            pg.draw.rect(surface, (30, 50, 70), (20, 115, 120, 4), border_radius=2)
            pg.draw.rect(surface, (80, 220, 255), (20, 115, int(120 * (self.shield_timer / 300.0)), 4), border_radius=2)

        # 6. Nếu ở Boss Wave, hiển thị thanh máu Boss ở đỉnh màn hình
        boss = self.boss_group.sprite
        if boss:
            bar_w = 400
            bar_h = 16
            bar_x = (self.w - bar_w) // 2
            bar_y = 75
            
            # Khung thanh máu
            pg.draw.rect(surface, (50, 20, 20), (bar_x, bar_y, bar_w, bar_h), border_radius=8)
            # Phần trăm máu hiện tại
            ratio = max(0.0, boss.hp / boss.max_hp)
            pg.draw.rect(surface, (255, 50, 50), (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=8)
            # Nhãn Boss
            boss_lbl = self.small_hud_font.render(f"BOSS CHICKEN : {int(ratio*100)}%", True, (255, 200, 200))
            surface.blit(boss_lbl, (bar_x + (bar_w - boss_lbl.get_width()) // 2, bar_y - 20))

    def draw(self, dt: int):
        """Vẽ toàn bộ lên game_surface, áp dụng rung màn hình và blit ra cửa sổ chính."""
        # Reset mặt phẳng vẽ
        self.game_surface.fill((10, 10, 25))
        
        # 1. Vẽ Starfield
        self.draw_starfield(self.game_surface, dt)
        
        # 2. Vẽ Tàu vũ trụ
        self.game_surface.blit(self.loader.images["ship"], self.ship_rect.topleft)
        
        # 3. Vẽ các đối tượng Sprite
        self.chickens.draw(self.game_surface)
        self.boss_group.draw(self.game_surface)
        self.bullets.draw(self.game_surface)
        self.eggs.draw(self.game_surface)
        self.powerups.draw(self.game_surface)
        self.particles.draw(self.game_surface)
        
        # 4. Vẽ Khiên quanh Tàu
        if self.shield_active and self.shield_sprite:
            self.game_surface.blit(self.shield_sprite.image, self.shield_sprite.rect.topleft)

        # 5. Vẽ Webcam Overlay dạng Thumbnail thu nhỏ (nếu active)
        if self.show_webcam_overlay and self.webcam_available:
            frame = self.tracker.get_latest_frame()
            if frame is not None:
                # Thu nhỏ ảnh camera về tỉ lệ 1/4
                cam_w = self.w // 5
                cam_h = int(frame.shape[0] * cam_w / frame.shape[1])
                
                # Resize hiệu năng cao bằng OpenCV
                cam_small = cv2.resize(frame, (cam_w, cam_h), interpolation=cv2.INTER_AREA)
                cam_rgb = cv2.cvtColor(cam_small, cv2.COLOR_BGR2RGB)
                
                # Chuyển đổi mảng numpy sang Pygame Surface
                cam_surf = pg.surfarray.make_surface(np.transpose(cam_rgb, (1, 0, 2)))
                
                # Tạo khung viền bo tròn phát sáng cho Webcam
                overlay_pos = (20, self.h - cam_h - 20)
                pg.draw.rect(self.game_surface, (50, 80, 120), (overlay_pos[0]-3, overlay_pos[1]-3, cam_w+6, cam_h+6), border_radius=6)
                self.game_surface.blit(cam_surf, overlay_pos)
                
                # Vẽ chấm tròn đỏ hiển thị vị trí nhận diện tay trên Webcam Thumbnail
                cx, cy = self.tracker.get_position()
                if cx is not None and cy is not None:
                    px = overlay_pos[0] + int(cx * cam_w)
                    py = overlay_pos[1] + int(cy * cam_h)
                    pg.draw.circle(self.game_surface, (255, 0, 0), (px, py), 6)
                    
                # Chú thích nhỏ
                cam_lbl = self.small_hud_font.render("WEBCAM ACTIVE [M để ẩn]", True, (150, 255, 150))
                self.game_surface.blit(cam_lbl, (overlay_pos[0], overlay_pos[1] - 25))

        # 6. Vẽ Giao diện HUD
        self.draw_hud(self.game_surface)

        # 7. Xử lý Game Over Overlay
        if self.game_over:
            # Làm mờ nền bằng lớp Surface đen phủ
            dim_bg = pg.Surface((self.w, self.h), pg.SRCALPHA)
            dim_bg.fill((0, 0, 0, 180))
            self.game_surface.blit(dim_bg, (0, 0))
            
            title = self.title_font.render("GAME OVER", True, (255, 80, 80))
            self.game_surface.blit(title, title.get_rect(center=(self.w // 2, self.h // 2 - 40)))
            
            score_txt = self.subtitle_font.render(f"Tổng Điểm Đạt Được: {self.score}", True, (255, 255, 255))
            self.game_surface.blit(score_txt, score_txt.get_rect(center=(self.w // 2, self.h // 2 + 20)))
            
            sub = self.subtitle_font.render(
                "Giơ ngón tay cái (Thumb Up) hoặc Click chuột / phím Space để chơi lại", 
                True, 
                (200, 200, 200)
            )
            self.game_surface.blit(sub, sub.get_rect(center=(self.w // 2, self.h // 2 + 70)))

        # 8. Thực thi Rung màn hình (Screen Shake) lên Screen chính
        if self.screen_shake_t > 0:
            self.screen_shake_t -= 1
            dx = random.randint(-6, 6)
            dy = random.randint(-6, 6)
        else:
            dx, dy = 0, 0
            
        self.screen.blit(self.game_surface, (dx, dy))
        pg.display.flip()

    def run(self):
        """Khởi động vòng lặp game chính."""
        try:
            while True:
                dt = self.clock.tick(60) # Chạy khóa cứng 60fps để chuyển động mượt mà
                self.handle_events()
                self.update(dt)
                self.draw(dt)
        finally:
            self.tracker.close()
            pg.quit()

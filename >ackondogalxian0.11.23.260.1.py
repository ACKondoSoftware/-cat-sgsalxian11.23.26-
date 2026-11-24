#!/usr/bin/env python3
# ============================================================
#  cat's galaxian 0.1 — A.C Holdings / Team Flames
#  60 FPS fixed-step engine, FILES = OFF.
#  Everything procedural: sprites are bit patterns, the OST and
#  every SFX are synthesized into mixer buffers at boot.
#  Controls:  ←/→ or A/D move   SPACE fire   ENTER start   ESC quit
# ============================================================
import math
import array
import random
import pygame

W, H, S, FPS = 240, 320, 3, 60
VERSION = "0.1"
SR = 44100
PX = 2
PLAYER_Y = H - 38

WHITE, BLACK = (252, 252, 252), (0, 0, 0)
SKY = (8, 10, 28)
STAR_COLS = [(40, 46, 78), (66, 74, 116), (104, 116, 168)]

# ------------------------------------------------------------ synth
def _sq(f, n, vol, duty=.5):
    p = max(2, int(SR / f)); hi = max(1, int(p * duty)); amp = int(32767 * vol)
    out = array.array('h', bytes(2 * n))
    for i in range(n):
        out[i] = amp if (i % p) < hi else -amp
    return out

def _noise(n, vol, falloff=2.0):
    out = array.array('h', bytes(2 * n))
    for i in range(n):
        k = (1 - i / max(1, n)) ** falloff
        out[i] = int(random.uniform(-1, 1) * 32767 * vol * k)
    return out

def _sweep(f0, f1, n, vol, duty=.5):
    out = array.array('h', bytes(2 * n))
    ph = 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * (i / max(1, n))
        ph += f / SR
        out[i] = int(32767 * vol) if (ph % 1.0) < duty else -int(32767 * vol)
    return out

NOTES = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
def nf(name):
    semi, i = NOTES[name[0]], 1
    if len(name) > 1 and name[1] == '#': semi, i = semi + 1, 2
    return 440.0 * 2 ** ((12 * (int(name[i:]) + 1) + semi - 69) / 12)

def _seq(spec, bpm, vol, duty, gate=.9):
    spb = 60.0 / bpm
    out = array.array('h')
    for name, beats in spec:
        ln = int(beats * spb * SR)
        if name is None:
            out.extend(array.array('h', bytes(2 * ln))); continue
        on = max(1, int(ln * gate))
        out.extend(_sq(nf(name), on, vol, duty))
        out.extend(array.array('h', bytes(2 * (ln - on))))
    return out

# OST: original arcade-style pulse motif, with sparse bass and rests.
BASS = [("A2", .5), (None, .5), ("E3", .5), (None, .5),
        ("G2", .5), (None, .5), ("D3", .5), (None, .5)] * 2
LEAD = [("A4", .25), ("E5", .25), ("A5", .25), (None, .25),
        ("G5", .25), ("E5", .25), ("C5", .25), (None, .25),
        ("D5", .25), ("F5", .25), ("D5", .25), (None, .25),
        ("E5", .25), ("B4", .25), ("A4", .25), (None, .25)] * 2

# ------------------------------------------------------------ audio
class Audio:
    def __init__(self):
        self.ok = False
        try:
            pygame.mixer.pre_init(SR, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(12)
            pygame.mixer.set_reserved(2)
            self.stereo = pygame.mixer.get_init()[2] == 2
            self.music = pygame.mixer.Channel(0)
            self.sfx = pygame.mixer.Channel(1)
            self.ok = True
        except Exception as exc:
            print("audio off:", exc)
        self.bank = {}

    def _snd(self, buf):
        if self.stereo:
            st = array.array('h', bytes(2 * len(buf) * 2))
            st[0::2] = buf; st[1::2] = buf
            buf = st
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def build(self, progress=lambda f: None):
        if not self.ok: return
        progress(.15)
        bass = _seq(BASS, 144, .10, .5, gate=.45)
        lead = _seq(LEAD, 144, .15, .5, gate=.55)
        n = max(len(bass), len(lead))
        bass.extend(array.array('h', bytes(2 * (n - len(bass)))))
        lead.extend(array.array('h', bytes(2 * (n - len(lead)))))
        mix = array.array('h', [max(-32767, min(32767, bass[i] + lead[i])) for i in range(n)])
        self.bank['ost'] = self._snd(mix)
        progress(.55)
        self.bank['shoot'] = self._snd(_sweep(1500, 620, int(SR * .09), .16, .25))
        self.bank['dive'] = self._snd(_sweep(280, 900, int(SR * .30), .13, .5))
        self.bank['hit'] = self._snd(_noise(int(SR * .18), .26, 1.6))
        self.bank['boom'] = self._snd(_noise(int(SR * .55), .32, 1.2))
        self.bank['wave'] = self._snd(_seq([("A4",.14),("C5",.14),("E5",.14),("A5",.42)], 200, .17, .5))
        self.bank['over'] = self._snd(_seq([("A3",.3),("F3",.3),("D3",.3),("A2",.9)], 120, .20, .5))
        progress(1.0)

    def play_ost(self):
        if self.ok: self.music.play(self.bank['ost'], loops=-1)

    def stop_ost(self):
        if self.ok: self.music.stop()

    def sfx_play(self, key):
        if self.ok and key in self.bank: self.sfx.play(self.bank[key])

# ------------------------------------------------------------ sprites
BEE = ["...#.#...", "..#####..", ".##.#.##.", "#.#####.#", "#.#.#.#.#",
       "..#####..", "..#.#.#..", ".#..#..#.", "#.......#"]

BUTTERFLY = [".#.....#.", "..#...#..", "#########", "###.#.###", "##..#..##",
             "#.##.##.#", "#.#...#.#", "..#.#.#..", ".#..#..#.", "#...#...#"]

FLAGSHIP = ["....#....", "...###...", "..#####..", ".##.#.##.", "#########",
            "##.###.##", "#.#.#.#.#", "#..###..#", "..#.#.#..", ".#..#..#.", "#.......#"]

SHIP = ["....#....", "...###...", "...#.#...", "..#####..", ".#.###.#.",
        "#########", "#.#####.#", "#.#...#.#", "..#...#.."]

SHIP_H = ["#########", "#.#####.#", "#########", "##.###.##", "#########",
          "#.#####.#", "#########", "..#...#..", ".#.....#."]

KINDS = {
    'bee':       (BEE, (108, 172, 255), 30),
    'butterfly': (BUTTERFLY, (206, 122, 255), 40),
    'escort':    (BUTTERFLY, (255, 96, 96), 60),
    'flagship':  (FLAGSHIP, (255, 220, 84), 150),
}

def blit_pat(surf, pat, x, y, col):
    for ry, row in enumerate(pat):
        for rx, ch in enumerate(row):
            if ch == '#':
                surf.fill(col, (x + rx, y + ry, 1, 1))

def blit_center(surf, pat, cx, cy, col, px=PX):
    x = int(cx) - len(pat[0]) * px // 2
    y = int(cy) - len(pat) * px // 2
    for ry, row in enumerate(pat):
        for rx, ch in enumerate(row):
            if ch == '#':
                surf.fill(col, (x + rx * px, y + ry * px, px, px))

# ------------------------------------------------------------ entities
class Enemy:
    __slots__ = ('kind', 'fx', 'fy', 'x', 'y', 'state', 'ph', 'dir', 'cool', 'alive')

    def __init__(self, kind, fx, fy):
        self.kind, self.fx, self.fy = kind, fx, fy
        self.x, self.y = fx, fy
        self.state, self.ph, self.dir, self.cool, self.alive = 'form', 0.0, 1, 0, True

class Bullet:
    __slots__ = ('x', 'y', 'vy', 'col')

    def __init__(self, x, y, vy, col):
        self.x, self.y, self.vy, self.col = x, y, vy, col

class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'col')

    def __init__(self, x, y, vx, vy, col):
        self.x, self.y, self.vx, self.vy, self.life, self.col = x, y, vx, vy, 26, col

# ------------------------------------------------------------ game
class Game:
    def __init__(self, scr, au):
        self.scr, self.au = scr, au
        self.font = pygame.font.SysFont("menlo,monospaced,monospace", 8, bold=True)
        self.small = pygame.font.SysFont("menlo,monospaced,monospace", 6, bold=True)
        self.tcache = {}
        self.t = 0
        self.state = 'title'
        self.stars = [(random.randrange(W), random.randrange(H), random.randrange(3))
                      for _ in range(70)]
        self.reset()

    # ---------- setup
    def reset(self):
        self.score = 0
        self.lives = 3
        self.wave = 1
        self.enemies = []
        self.pbullets = []
        self.ebullets = []
        self.parts = []
        self.sway = 0.0
        self.dive_timer = 90
        self.player_x = W / 2
        self.player_dead = 0
        self.build_wave()

    def build_wave(self):
        self.enemies.clear()
        self.pbullets.clear()
        self.ebullets.clear()
        gap = 22 - min(4, self.wave)
        rows = [('flagship', 0), ('escort', 1), ('butterfly', 2), ('bee', 3), ('bee', 4)]
        for kind, row in rows:
            for col in range(6):
                if kind == 'flagship' and col not in (2, 3):
                    continue
                if kind == 'escort' and col not in (1, 2, 3, 4):
                    continue
                self.enemies.append(Enemy(kind, W / 2 + (col - 2.5) * gap, 36 + row * 22))

    # ---------- helpers
    def txt(self, s, x, y, col=WHITE, small=False, center=False):
        key = (s, col, small)
        if key not in self.tcache:
            if len(self.tcache) >= 512: self.tcache.clear()
            self.tcache[key] = (self.small if small else self.font).render(s, False, col)
        surf = self.tcache[key]
        self.scr.blit(surf, (x - (surf.get_width() // 2 if center else 0), y))

    def boom(self, x, y, n, col):
        for _ in range(n):
            a = random.uniform(0, math.tau); sp = random.uniform(.5, 2.6)
            self.parts.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp, col))

    def formation_enemies(self):
        return [e for e in self.enemies if e.state == 'form' and e.alive]

    # ---------- states
    def step(self):
        self.t += 1
        getattr(self, 'st_' + self.state)()

    def st_title(self):
        self.sway = math.sin(self.t * .05) * 12
        if pygame.key.get_pressed()[pygame.K_RETURN] and self.t > 20:
            self.reset(); self.state = 'play'; self.au.play_ost()

    def st_over(self):
        self.step_parts()
        if pygame.key.get_pressed()[pygame.K_RETURN] and self.t > 60:
            self.reset(); self.state = 'title'; self.au.stop_ost()

    # ---------- play
    def st_play(self):
        k = pygame.key.get_pressed()
        self.sway = math.sin(self.t * .022) * min(24, 6 + self.wave)

        if self.player_dead:
            self.player_dead -= 1
            self.step_bullets(); self.step_parts()
            return

        dx = (int(k[pygame.K_RIGHT] or k[pygame.K_d]) - int(k[pygame.K_LEFT] or k[pygame.K_a]))
        self.player_x = max(12, min(W - 12, self.player_x + dx * 2.4))

        if k[pygame.K_SPACE] and not self.pbullets:
            self.pbullets.append(Bullet(self.player_x, PLAYER_Y - 10, -5.2, (150, 255, 190)))
            self.au.sfx_play('shoot')

        self.dive_timer -= 1
        if self.dive_timer <= 0:
            self.launch_dive()
            self.dive_timer = max(24, 90 - self.wave * 6) + random.randrange(30)

        self.step_enemies()
        self.step_bullets()
        self.step_parts()
        self.collide()

        if not [e for e in self.enemies if e.alive]:
            self.wave += 1
            self.au.sfx_play('wave')
            self.build_wave()

    def launch_dive(self):
        pool = self.formation_enemies()
        if not pool: return
        lead = random.choice(pool)
        self.start_dive(lead)
        if lead.kind == 'flagship':
            for e in pool:
                if e.kind == 'escort' and abs(e.fx - lead.fx) < 26:
                    self.start_dive(e)
        self.au.sfx_play('dive')

    def start_dive(self, e):
        e.state = 'dive'; e.ph = 0.0; e.dir = 1 if e.x < W / 2 else -1; e.cool = 24

    def step_enemies(self):
        for e in self.enemies:
            if not e.alive: continue
            if e.state == 'form':
                e.x = e.fx + self.sway
                e.y = e.fy
            else:
                e.ph += .085
                e.x += math.sin(e.ph * 1.9) * 2.9 * e.dir + (self.player_x - e.x) * .007
                e.y += 1.45 + self.wave * .09
                e.cool -= 1
                if e.cool <= 0:
                    e.cool = 46
                    self.ebullets.append(Bullet(e.x, e.y + 10, 2.5, (255, 150, 90)))
                    self.au.sfx_play('shoot')
                if e.y > H + 14:
                    e.state = 'form'; e.y = e.fy

    def step_bullets(self):
        for b in self.pbullets:
            b.y += b.vy
        self.pbullets = [b for b in self.pbullets if b.y > -8]
        for b in self.ebullets:
            b.y += b.vy
        self.ebullets = [b for b in self.ebullets if b.y < H + 8]

    def step_parts(self):
        for p in self.parts:
            p.x += p.vx; p.y += p.vy; p.vy += .04; p.life -= 1
        self.parts = [p for p in self.parts if p.life > 0]

    def collide(self):
        for b in list(self.pbullets):
            for e in self.enemies:
                if not e.alive: continue
                if abs(b.x - e.x) < 9 and abs(b.y - e.y) < 11:
                    e.alive = False
                    self.score += KINDS[e.kind][2]
                    self.boom(e.x, e.y, 14, KINDS[e.kind][1])
                    self.au.sfx_play('hit')
                    if b in self.pbullets: self.pbullets.remove(b)
                    break
        if self.player_dead: return
        for b in list(self.ebullets):
            if abs(b.x - self.player_x) < 8 and abs(b.y - PLAYER_Y) < 10:
                self.ebullets.remove(b); self.kill_player(); return
        for e in self.enemies:
            if e.alive and e.state == 'dive':
                if abs(e.x - self.player_x) < 10 and abs(e.y - PLAYER_Y) < 12:
                    e.alive = False; self.boom(e.x, e.y, 16, KINDS[e.kind][1])
                    self.kill_player(); return

    def kill_player(self):
        self.boom(self.player_x, PLAYER_Y, 26, (255, 210, 140))
        self.au.sfx_play('boom')
        self.lives -= 1
        self.ebullets.clear()
        self.pbullets.clear()
        self.player_dead = 50
        if self.lives <= 0:
            self.state = 'over'; self.au.stop_ost(); self.au.sfx_play('over')

    # ---------- render
    def draw(self):
        self.scr.fill(SKY)
        for sx, sy, d in self.stars:
            yy = (sy + self.t * (d + 1) * .22) % H
            self.scr.fill(STAR_COLS[d], (sx, int(yy), 1, 1))
        getattr(self, 'dr_' + self.state)()

    def dr_title(self):
        blit_center(self.scr, SHIP, W // 2, H - 60, (150, 255, 190))
        for i, (kind, row) in enumerate([('flagship', 0), ('escort', 1), ('butterfly', 2), ('bee', 3)]):
            pat, col, _ = KINDS[kind]
            blit_center(self.scr, pat, 44 + (i % 4) * 48, 92 + (i // 4) * 26, col)
        self.txt("CAT'S", W // 2, 36, (255, 220, 84), center=True)
        self.txt("GALAXIAN", W // 2, 52, (255, 96, 96), center=True)
        if (self.t // 24) % 2 == 0:
            self.txt("PUSH START", W // 2, 168, center=True)
        self.txt(f"v{VERSION}  60FPS  FILES OFF", W // 2, 196, (120, 136, 180), True, True)
        self.txt("A.C HOLDINGS / TEAM FLAMES", W // 2, 212, (255, 160, 68), True, True)

    def dr_play(self):
        for e in self.enemies:
            if e.alive:
                pat, col, _ = KINDS[e.kind]
                blit_center(self.scr, pat, e.x, e.y, col)
        for b in self.pbullets:
            self.scr.fill(b.col, (int(b.x), int(b.y), 1, 5))
        for b in self.ebullets:
            self.scr.fill(b.col, (int(b.x), int(b.y), 1, 4))
        for p in self.parts:
            self.scr.fill(p.col, (int(p.x), int(p.y), 1, 1))
        if not self.player_dead:
            blit_center(self.scr, SHIP, self.player_x, PLAYER_Y, (150, 255, 190))
        elif (self.t // 4) % 2:
            blit_center(self.scr, SHIP_H, self.player_x, PLAYER_Y, (255, 140, 140))
        self.txt(f"{self.score:06d}", 6, 6)
        wave_text = f"WAVE {self.wave:02d}"
        self.txt(wave_text, W - 6 - self.small.size(wave_text)[0], 6, (255, 220, 84), True)
        for i in range(self.lives):
            blit_pat(self.scr, SHIP, 6 + i * 12, H - 12, (150, 255, 190))

    def dr_over(self):
        for p in self.parts:
            self.scr.fill(p.col, (int(p.x), int(p.y), 1, 1))
        self.txt("GAME", W // 2, 120, (255, 96, 96), center=True)
        self.txt("OVER", W // 2, 136, (255, 96, 96), center=True)
        self.txt(f"SCORE {self.score:06d}", W // 2, 166, center=True)
        if self.t % 30 < 15:
            self.txt("ENTER", W // 2, 196, (255, 220, 84), True, True)

# ------------------------------------------------------------ boot
def main():
    pygame.mixer.pre_init(SR, -16, 1, 512)
    pygame.init()
    au = Audio()
    desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    scale = max(1, min(S, (desktop_w - 40) // W, (desktop_h - 100) // H))
    scr = pygame.display.set_mode((W * scale, H * scale), pygame.RESIZABLE)
    pygame.display.set_caption(f"cat's galaxian {VERSION}")
    clock = pygame.time.Clock()
    frame = pygame.Surface((W, H)).convert()
    font = pygame.font.SysFont("menlo,monospaced,monospace", 10, bold=True)

    def present():
        sw, sh = scr.get_size()
        ratio = min(sw / W, sh / H)
        if ratio >= 1:
            ratio = int(ratio)
        size = (max(1, int(W * ratio)), max(1, int(H * ratio)))
        scr.fill(BLACK)
        scr.blit(pygame.transform.scale(frame, size), ((sw-size[0])//2, (sh-size[1])//2))
        pygame.display.flip()

    def progress(f):
        frame.fill(BLACK)
        msg = font.render("SYNTHESIZING OST...", False, WHITE)
        frame.blit(msg, ((W-msg.get_width())//2, H//2-20))
        frame.fill((255, 220, 84), (12, H//2+10, int((W-24)*f), 4))
        present()
        pygame.event.pump()
    progress(0)
    au.build(progress)
    game = Game(frame, au)
    accumulator = 0.0
    step = 1.0 / FPS
    while True:
        accumulator += min(clock.tick(FPS) / 1000.0, 0.1)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return
        while accumulator >= step:
            game.step()
            accumulator -= step
        game.draw()
        present()

if __name__ == "__main__":
    main()

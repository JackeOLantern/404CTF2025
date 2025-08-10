
import sys
import os
import random
import pygame

TILE = 32
MOVE_MS = 120
ENEMY_MS = 220
LASER_RANGE = 4
SCREEN_SCALE = 1

RAW_MAP = [
    "#############",
    "#...........#",
    "#.###.#.###.#",
    "#o#.......#o#",
    "#.###.#.###.#",
    "#.....#.....#",
    "###.#.#.#.###",
    "#.....#.....#",
    "#.###.#.###.#",
    "#o#.......#o#",
    "#.###.#.###.#",
    "#...........#",
    "#############",
]
W, H = len(RAW_MAP[0]), len(RAW_MAP)

BG_COLOR = (11, 16, 36)
WALL_COLOR = (47, 111, 235)
DOT_COLOR = (255, 216, 102)
POWER_COLOR = (100, 210, 255)
PLAYER_COLOR = (255, 255, 160)
ENEMY_COLORS = [(230, 230, 230), (200, 255, 200), (255, 190, 190), (200, 200, 255)]

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ASSET_FILES = {
    "bg": "bg.png",
    "wall": "wall.png",
    "dot": "fruit.png",
    "power": "power.png",
    "pacman": "pacman.png",
    "trooper": "stormtrooper.png",
    "zombie": "zombie.png",
    "troll": "troll_jedi.png",
}

def load_img(name, size=None):
    path = os.path.join(ASSETS_DIR, ASSET_FILES.get(name, name))
    if not os.path.exists(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.smoothscale(img, size)
        return img
    except Exception:
        return None

def ensure_assets():
    size = (TILE, TILE)
    return {
        "bg": load_img("bg", None),
        "wall": load_img("wall", size),
        "dot": load_img("dot", (int(TILE*0.6), int(TILE*0.6))),
        "power": load_img("power", (int(TILE*0.9), int(TILE*0.9))),
        "pacman": load_img("pacman", size),
        "trooper": load_img("trooper", size),
        "zombie": load_img("zombie", size),
        "troll": load_img("troll", size),
    }

def inside(x, y): return 0 <= x < W and 0 <= y < H
def is_wall(x, y): return not inside(x, y) or RAW_MAP[y][x] == '#'
def neighbors(x, y):
    out = []
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
        nx, ny = x + dx, y + dy
        if not is_wall(nx, ny): out.append((nx, ny))
    return out

def manhattan(a, b): return abs(a[0]-b[0]) + abs(a[1]-b[1])

class Player:
    def __init__(self):
        self.tile = [1, 1]
        self.from_tile = [1, 1]
        self.to_tile = [1, 1]
        self.facing = [1, 0]
        self.moving = False
        self.start = 0
        self.duration = MOVE_MS
        self.shots = 1
        self.lives = 3

class Enemy:
    def __init__(self, kind, tile):
        self.kind = kind
        self.tile = list(tile)
        self.from_tile = list(tile)
        self.to_tile = list(tile)
        self.moving = False
        self.start = 0
        self.duration = ENEMY_MS
        self.respawn_at = None

class Game:
    def __init__(self):
        self.map = RAW_MAP[:]
        self.dots = set()
        self.powers = set()
        for y,row in enumerate(self.map):
            for x,c in enumerate(row):
                if c == ".": self.dots.add((x,y))
                if c == "o": self.powers.add((x,y))
        self.score = 0
        self.won = False
        self.over = False

def enemy_spawns():
    cx, cy = W//2, H//2
    spots = []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            x, y = cx+dx, cy+dy
            if not is_wall(x, y): spots.append((x,y))
    return spots or [(1,1)]

def reset_game():
    g = Game()
    p = Player()
    spawns = enemy_spawns()
    kinds = ["trooper", "trooper", "troll", "trooper"]
    enemies = [Enemy(k, spawns[i % len(spawns)]) for i,k in enumerate(kinds)]
    return g, p, enemies

def try_move_player(g, p, now, queued_dir):
    if g.over or g.won: return
    if not p.moving and queued_dir is not None:
        dx, dy = queued_dir
        tx, ty = p.tile[0] + dx, p.tile[1] + dy
        if not is_wall(tx, ty):
            p.moving = True
            p.from_tile = list(p.tile)
            p.to_tile = [tx, ty]
            p.start = now
            p.duration = MOVE_MS
            p.facing = [dx, dy]
    if p.moving and now - p.start >= p.duration:
        p.tile = list(p.to_tile)
        p.moving = False
        pos = (p.tile[0], p.tile[1])
        if pos in g.dots: g.dots.remove(pos); g.score += 10
        if pos in g.powers: g.powers.remove(pos); g.score += 50; p.shots += 1
        if not g.dots and not g.powers: g.won = True

def move_enemies(g, p, enemies, now):
    for e in enemies:
        if e.respawn_at is not None and now >= e.respawn_at:
            sp = random.choice(enemy_spawns())
            e.tile = list(sp); e.from_tile = list(sp); e.to_tile = list(sp)
            e.moving = False; e.respawn_at = None
        if e.respawn_at is not None: continue

        if not e.moving:
            opts = neighbors(e.tile[0], e.tile[1])
            if not opts: continue
            if e.kind == "trooper":
                next_t = min(opts, key=lambda n: manhattan(n, tuple(p.tile)))
            elif e.kind == "zombie":
                next_t = random.choice(opts) if random.random() < 0.5 else e.tile[:]
            else:
                opts2 = [n for n in opts if n != tuple(e.from_tile)]
                use = opts2 if opts2 else opts
                next_t = random.choice(use)
            e.moving = True; e.from_tile = list(e.tile); e.to_tile = list(next_t)
            e.start = now; e.duration = ENEMY_MS
        elif now - e.start >= e.duration:
            e.tile = list(e.to_tile); e.moving = False

        if not p.moving and tuple(e.tile) == tuple(p.tile):
            p.lives -= 1
            if p.lives <= 0: g.over = True; return
            p.tile = [1,1]; p.from_tile = [1,1]; p.to_tile = [1,1]; p.moving = False
            spawns = enemy_spawns()
            for en in enemies:
                s = random.choice(spawns)
                en.tile = list(s); en.from_tile = list(s); en.to_tile = list(s)
                en.moving = False; en.respawn_at = None
            break

def shoot_laser(g, p, enemies, now):
    if g.over or g.won: return
    if p.shots <= 0: return
    p.shots -= 1
    dx, dy = p.facing
    if dx == 0 and dy == 0: dx, dy = 1, 0
    for step in range(1, LASER_RANGE+1):
        tx, ty = p.tile[0] + dx*step, p.tile[1] + dy*step
        if is_wall(tx, ty): break
        for e in enemies:
            if e.respawn_at is None and (e.tile[0], e.tile[1]) == (tx, ty):
                e.respawn_at = now + 3000
                return

def draw_text(surface, text, pos, size=18, color=(255,255,255), center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)

def render(screen, g, p, enemies, sprites, last_shot_line):
    if sprites["bg"]:
        screen.blit(pygame.transform.smoothscale(sprites["bg"], screen.get_size()), (0,0))
    else:
        screen.fill(BG_COLOR)

    for y,row in enumerate(g.map):
        for x,c in enumerate(row):
            if c == '#':
                if sprites["wall"]:
                    screen.blit(sprites["wall"], (x*TILE, y*TILE))
                else:
                    pygame.draw.rect(screen, WALL_COLOR, (x*TILE, y*TILE, TILE, TILE))

    for (x,y) in g.dots:
        if sprites["dot"]:
            rect = sprites["dot"].get_rect(center=(x*TILE+TILE//2, y*TILE+TILE//2))
            screen.blit(sprites["dot"], rect.topleft)
        else:
            pygame.draw.rect(screen, DOT_COLOR, (x*TILE+TILE//2-3, y*TILE+TILE//2-3, 6, 6))
    for (x,y) in g.powers:
        if sprites["power"]:
            rect = sprites["power"].get_rect(center=(x*TILE+TILE//2, y*TILE+TILE//2))
            screen.blit(sprites["power"], rect.topleft)
        else:
            pygame.draw.rect(screen, POWER_COLOR, (x*TILE+TILE//2-6, y*TILE+TILE//2-6, 12, 12), width=2)

    px, py = p.tile
    if p.moving:
        t = min(1.0, (pygame.time.get_ticks() - p.start) / max(1, p.duration))
        px = p.from_tile[0] + (p.to_tile[0] - p.from_tile[0]) * t
        py = p.from_tile[1] + (p.to_tile[1] - p.from_tile[1]) * t
    cx, cy = int((px + 0.5) * TILE), int((py + 0.5) * TILE)

    pac = sprites["pacman"]
    if pac:
        angle = 0
        if p.facing == [1,0]: angle = 0
        elif p.facing == [-1,0]: angle = 180
        elif p.facing == [0,-1]: angle = 90
        elif p.facing == [0,1]: angle = -90
        pac2 = pygame.transform.rotate(pac, angle)
        rect = pac2.get_rect(center=(cx, cy))
        screen.blit(pac2, rect.topleft)
    else:
        pygame.draw.circle(screen, PLAYER_COLOR, (cx, cy), TILE//2 - 4)

    for i, e in enumerate(enemies):
        if e.respawn_at is not None: continue
        ex, ey = e.tile
        if e.moving:
            t = min(1.0, (pygame.time.get_ticks() - e.start) / max(1, e.duration))
            ex = e.from_tile[0] + (e.to_tile[0] - e.from_tile[0]) * t
            ey = e.from_tile[1] + (e.to_tile[1] - e.from_tile[1]) * t
        spr = sprites.get(e.kind) or None
        if spr:
            rect = spr.get_rect(center=(int((ex+0.5)*TILE), int((ey+0.5)*TILE)))
            screen.blit(spr, rect.topleft)
        else:
            ec = ENEMY_COLORS[i % len(ENEMY_COLORS)]
            pygame.draw.circle(screen, ec, (int((ex+0.5)*TILE), int((ey+0.5)*TILE)), TILE//2 - 6)

    if last_shot_line and pygame.time.get_ticks() - last_shot_line[2] < 120:
        (x1,y1,x2,y2,ts) = last_shot_line
        pygame.draw.line(screen, (255, 51, 85), (x1,y1), (x2,y2), 3)

    draw_text(screen, f"Score: {g.score}", (8, 6), 18)
    draw_text(screen, f"Lives: {'\u2665'*max(0,p.lives)}", (8, 26), 18)
    draw_text(screen, f"Shots: {p.shots} (Space)", (8, 46), 18)

    if g.won or g.over:
        msg = "Victoire !" if g.won else "Game Over"
        draw_text(screen, msg, (W*TILE//2, H*TILE//2), 28, (255,255,255), center=True)
        draw_text(screen, "Appuie sur R pour rejouer", (W*TILE//2, H*TILE//2 + 32), 20, (255,255,255), center=True)

def main():
    pygame.init()
    pygame.display.set_caption("Pacman — Jedi vs Empire (Pygame / Sprites)")
    screen = pygame.display.set_mode((W*TILE*SCREEN_SCALE, H*TILE*SCREEN_SCALE))
    clock = pygame.time.Clock()

    sprites = ensure_assets()
    g, p, enemies = reset_game()
    queued_dir = None
    last_shot_line = None

    running = True
    while running:
        now = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP: queued_dir = (0,-1); p.facing = [0,-1]
                elif event.key == pygame.K_DOWN: queued_dir = (0,1); p.facing = [0,1]
                elif event.key == pygame.K_LEFT: queued_dir = (-1,0); p.facing = [-1,0]
                elif event.key == pygame.K_RIGHT: queued_dir = (1,0); p.facing = [1,0]
                elif event.key == pygame.K_SPACE:
                    dx, dy = p.facing if any(p.facing) else (1,0)
                    x1, y1 = int((p.tile[0]+0.5)*TILE), int((p.tile[1]+0.5)*TILE)
                    tx, ty = p.tile[0], p.tile[1]
                    for step in range(1, LASER_RANGE+1):
                        tx2, ty2 = tx + dx*step, ty + dy*step
                        if is_wall(tx2, ty2): break
                        tx, ty = tx2, ty2
                    x2, y2 = int((tx+0.5)*TILE), int((ty+0.5)*TILE)
                    last_shot_line = (x1,y1,x2,y2, now)
                    shoot_laser(g, p, enemies, now)
                elif event.key == pygame.K_r:
                    g, p, enemies = reset_game(); queued_dir = None; last_shot_line = None

        try_move_player(g, p, now, queued_dir)
        move_enemies(g, p, enemies, now)

        render(screen, g, p, enemies, sprites, last_shot_line)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

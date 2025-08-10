
import sys
import math
import random
import pygame

# ----- Config -----
TILE = 32
MOVE_MS = 120          # player ms per tile
ENEMY_MS = 220         # enemy ms per tile
LASER_RANGE = 4
SCREEN_SCALE = 1       # keep 1:1 pixels

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

W = len(RAW_MAP[0])
H = len(RAW_MAP)

# Colors
BG_COLOR = (11, 16, 36)        # dark blue-ish
WALL_COLOR = (47, 111, 235)    # blue
DOT_COLOR = (255, 216, 102)    # yellow
POWER_COLOR = (100, 210, 255)  # cyan
PLAYER_COLOR = (255, 255, 160) # pale yellow
ENEMY_COLORS = [(230, 230, 230), (200, 255, 200), (255, 190, 190), (200, 200, 255)]

# ----- Helpers -----
def inside(x, y):
    return 0 <= x < W and 0 <= y < H

def is_wall(x, y):
    return not inside(x, y) or RAW_MAP[y][x] == '#'

def neighbors(x, y):
    out = []
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
        nx, ny = x + dx, y + dy
        if not is_wall(nx, ny):
            out.append((nx, ny))
    return out

def manhattan(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

# ----- Game State -----
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
        self.kind = kind  # "trooper"|"zombie"|"troll"
        self.tile = list(tile)
        self.from_tile = list(tile)
        self.to_tile = list(tile)
        self.moving = False
        self.start = 0
        self.duration = ENEMY_MS
        self.respawn_at = None

class Game:
    def __init__(self):
        self.map = RAW_MAP[:]  # immutable rows
        self.dots = set()
        self.powers = set()
        for y, row in enumerate(self.map):
            for x, c in enumerate(row):
                if c == '.': self.dots.add((x,y))
                if c == 'o': self.powers.add((x,y))
        self.score = 0
        self.won = False
        self.over = False

def enemy_spawns():
    cx, cy = W//2, H//2
    spots = []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            x, y = cx+dx, cy+dy
            if not is_wall(x, y):
                spots.append((x, y))
    return spots or [(1,1)]

def reset_game():
    g = Game()
    p = Player()

    spawns = enemy_spawns()
    kinds = ["trooper", "trooper", "troll", "trooper"]
    enemies = []
    for i,k in enumerate(kinds):
        enemies.append(Enemy(k, spawns[i % len(spawns)]))
    return g, p, enemies

# ----- Movement / Update -----
def try_move_player(g, p, now, queued_dir):
    if g.over or g.won:
        return None

    # start new step
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

    # finish step
    if p.moving and now - p.start >= p.duration:
        p.tile = list(p.to_tile)
        p.moving = False
        pos = (p.tile[0], p.tile[1])
        if pos in g.dots:
            g.dots.remove(pos)
            g.score += 10
        if pos in g.powers:
            g.powers.remove(pos)
            g.score += 50
            p.shots += 1
        if not g.dots and not g.powers:
            g.won = True

def move_enemies(g, p, enemies, now):
    for idx, e in enumerate(enemies):
        # respawn
        if e.respawn_at is not None and now >= e.respawn_at:
            sp = random.choice(enemy_spawns())
            e.tile = list(sp)
            e.from_tile = list(sp)
            e.to_tile = list(sp)
            e.moving = False
            e.respawn_at = None

        if e.respawn_at is not None:
            continue  # dead

        # choose next tile
        if not e.moving:
            opts = neighbors(e.tile[0], e.tile[1])
            if not opts:
                continue
            if e.kind == "trooper":  # greedy chase
                next_t = min(opts, key=lambda n: manhattan(n, tuple(p.tile)))
            elif e.kind == "zombie":
                if random.random() < 0.4:
                    next_t = random.choice(opts)
                else:
                    next_t = e.tile[:]  # sometimes idle
            else:  # troll: random non-backtrack if possible
                opts2 = [n for n in opts if n != tuple(e.from_tile)]
                use = opts2 if opts2 else opts
                next_t = random.choice(use)
            e.moving = True
            e.from_tile = list(e.tile)
            e.to_tile = list(next_t)
            e.start = now
            e.duration = ENEMY_MS
        elif now - e.start >= e.duration:
            e.tile = list(e.to_tile)
            e.moving = False

        # collision
        if not p.moving and tuple(e.tile) == tuple(p.tile):
            p.lives -= 1
            if p.lives <= 0:
                g.over = True
                return
            # reset positions
            p.tile = [1,1]
            p.from_tile = [1,1]
            p.to_tile = [1,1]
            p.moving = False
            spawns = enemy_spawns()
            for en in enemies:
                s = random.choice(spawns)
                en.tile = list(s)
                en.from_tile = list(s)
                en.to_tile = list(s)
                en.moving = False
                en.respawn_at = None
            break

def shoot_laser(g, p, enemies, now):
    if g.over or g.won:
        return
    if p.shots <= 0:
        return
    p.shots -= 1
    dx, dy = p.facing
    if dx == 0 and dy == 0:
        dx, dy = 1, 0
    for step in range(1, LASER_RANGE+1):
        tx, ty = p.tile[0] + dx*step, p.tile[1] + dy*step
        if is_wall(tx, ty):
            break
        for e in enemies:
            if e.respawn_at is None and (e.tile[0], e.tile[1]) == (tx, ty):
                e.respawn_at = now + 3000  # 3 seconds
                return

# ----- Rendering -----
def draw_text(surface, text, pos, size=18, color=(255,255,255), center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)

def render(screen, g, p, enemies):
    screen.fill(BG_COLOR)

    # walls
    for y, row in enumerate(g.map):
        for x, c in enumerate(row):
            if c == '#':
                pygame.draw.rect(screen, WALL_COLOR, (x*TILE, y*TILE, TILE, TILE))

    # dots
    for (x, y) in g.dots:
        pygame.draw.rect(screen, DOT_COLOR, (x*TILE + TILE//2 - 3, y*TILE + TILE//2 - 3, 6, 6))
    for (x, y) in g.powers:
        pygame.draw.rect(screen, POWER_COLOR, (x*TILE + TILE//2 - 6, y*TILE + TILE//2 - 6, 12, 12), width=2)

    # player (interpolate)
    px, py = p.tile
    if p.moving:
        t = min(1.0, (pygame.time.get_ticks() - p.start) / max(1, p.duration))
        px = p.from_tile[0] + (p.to_tile[0] - p.from_tile[0]) * t
        py = p.from_tile[1] + (p.to_tile[1] - p.from_tile[1]) * t
    cx, cy = int((px + 0.5) * TILE), int((py + 0.5) * TILE)
    pygame.draw.circle(screen, PLAYER_COLOR, (cx, cy), TILE//2 - 4)

    # enemies
    for i, e in enumerate(enemies):
        if e.respawn_at is not None:
            continue
        ex, ey = e.tile
        if e.moving:
            t = min(1.0, (pygame.time.get_ticks() - e.start) / max(1, e.duration))
            ex = e.from_tile[0] + (e.to_tile[0] - e.from_tile[0]) * t
            ey = e.from_tile[1] + (e.to_tile[1] - e.from_tile[1]) * t
        ec = ENEMY_COLORS[i % len(ENEMY_COLORS)]
        ec = (max(0, ec[0]-10*i), max(0, ec[1]-10*i), max(0, ec[2]-10*i))
        cx, cy = int((ex + 0.5) * TILE), int((ey + 0.5) * TILE)
        pygame.draw.circle(screen, ec, (cx, cy), TILE//2 - 6)

    # HUD
    draw_text(screen, f"Score: {g.score}", (8, 6), 18)
    draw_text(screen, f"Lives: {'\u2665'*max(0,p.lives)}", (8, 26), 18)
    draw_text(screen, f"Shots: {p.shots} (Space)", (8, 46), 18)

    # end states
    if g.won or g.over:
        msg = "Victoire !" if g.won else "Game Over"
        draw_text(screen, msg, (W*TILE//2, H*TILE//2), 28, (255,255,255), center=True)
        draw_text(screen, "Appuie sur R pour rejouer", (W*TILE//2, H*TILE//2 + 32), 20, (255,255,255), center=True)

def main():
    pygame.init()
    pygame.display.set_caption("Pacman — Jedi vs Empire (Pygame)")
    screen = pygame.display.set_mode((W*TILE*SCREEN_SCALE, H*TILE*SCREEN_SCALE))
    clock = pygame.time.Clock()

    g, p, enemies = reset_game()
    queued_dir = None

    running = True
    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP: queued_dir = (0, -1); p.facing = [0, -1]
                elif event.key == pygame.K_DOWN: queued_dir = (0, 1); p.facing = [0, 1]
                elif event.key == pygame.K_LEFT: queued_dir = (-1, 0); p.facing = [-1, 0]
                elif event.key == pygame.K_RIGHT: queued_dir = (1, 0); p.facing = [1, 0]
                elif event.key == pygame.K_SPACE: shoot_laser(g, p, enemies, now)
                elif event.key == pygame.K_r: g, p, enemies = reset_game(); queued_dir = None

        try_move_player(g, p, now, queued_dir)
        move_enemies(g, p, enemies, now)

        render(screen, g, p, enemies)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

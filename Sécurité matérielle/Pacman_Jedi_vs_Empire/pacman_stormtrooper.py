
import sys, os, random, pygame

TILE = 32
MOVE_MS = 110
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

BG_COLOR   = (11, 16, 36)
WALL_COLOR = (47, 111, 235)
DOT_COLOR  = (255, 216, 102)
POWER_COLOR= (100, 210, 255)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ASSET_FILES = {
    "bg": "bg.png",
    "wall": "wall.png",
    "dot": "fruit.png",
    "power": "power.png",
    "player": "stormtrooper.png",      # <<-- PLAYER IS A STORMTROOPER
    "trooper": "stormtrooper.png",     # enemies can also use this if we want
    "troll": "troll_jedi.png",
    "zombie": "zombie.png",
}

def load_img(name, size=None):
    path = os.path.join(ASSETS_DIR, ASSET_FILES.get(name, name))
    if not os.path.exists(path): return None
    try:
        img = pygame.image.load(path).convert_alpha()
        if size: img = pygame.transform.smoothscale(img, size)
        return img
    except Exception:
        return None

def inside(x, y): return 0 <= x < W and 0 <= y < H
def is_wall(x, y): return not inside(x, y) or RAW_MAP[y][x] == '#'
def neighbors(x, y):
    out = []
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = x+dx, y+dy
        if not is_wall(nx, ny): out.append((nx,ny))
    return out

def manhattan(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])

class Player:
    def __init__(self):
        self.tile = [1,1]
        self.from_tile = [1,1]
        self.to_tile = [1,1]
        self.facing = [1,0]
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
        self.dots = {(x,y) for y,row in enumerate(self.map) for x,c in enumerate(row) if c=='.'}
        self.powers = {(x,y) for y,row in enumerate(self.map) for x,c in enumerate(row) if c=='o'}
        self.score = 0
        self.won = False
        self.over = False

def enemy_spawns():
    cx, cy = W//2, H//2
    spots = []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            x,y = cx+dx, cy+dy
            if not is_wall(x,y): spots.append((x,y))
    return spots or [(1,1)]

def reset_game():
    g = Game()
    p = Player()
    sp = enemy_spawns()
    kinds = ["troll", "zombie", "troll", "zombie"]
    enemies = [Enemy(k, sp[i % len(sp)]) for i,k in enumerate(kinds)]
    return g, p, enemies

def try_move_player(g, p, now, desired):
    if g.over or g.won: return
    # if we can switch direction before finishing the current movement, queue it
    if not p.moving and desired is not None:
        dx, dy = desired
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
            s = random.choice(enemy_spawns())
            e.tile = list(s); e.from_tile = list(s); e.to_tile = list(s)
            e.moving = False; e.respawn_at = None
        if e.respawn_at is not None: continue
        if not e.moving:
            opts = neighbors(e.tile[0], e.tile[1])
            if not opts: continue
            if e.kind in ("troll","zombie"):
                opts2 = [n for n in opts if n != tuple(e.from_tile)]
                use = opts2 if opts2 else opts
                next_t = random.choice(use)
            else:
                next_t = min(opts, key=lambda n: manhattan(n, tuple(p.tile)))
            e.moving = True; e.from_tile = list(e.tile); e.to_tile = list(next_t)
            e.start = now; e.duration = ENEMY_MS
        elif now - e.start >= e.duration:
            e.tile = list(e.to_tile); e.moving = False
        if not p.moving and tuple(e.tile) == tuple(p.tile):
            p.lives -= 1
            if p.lives <= 0: g.over = True; return
            p.tile = [1,1]; p.from_tile = [1,1]; p.to_tile = [1,1]; p.moving = False
            sp = enemy_spawns()
            for en in enemies:
                s = random.choice(sp)
                en.tile = list(s); en.from_tile = list(s); en.to_tile = list(s)
                en.moving = False; en.respawn_at = None
            break

def shoot_laser(g, p, enemies, now):
    if g.over or g.won or p.shots <= 0: return
    p.shots -= 1
    dx, dy = p.facing if any(p.facing) else (1,0)
    for step in range(1, LASER_RANGE+1):
        tx, ty = p.tile[0] + dx*step, p.tile[1] + dy*step
        if is_wall(tx, ty): break
        for e in enemies:
            if e.respawn_at is None and (e.tile[0], e.tile[1]) == (tx, ty):
                e.respawn_at = now + 3000
                return

def draw_text(surf, text, pos, size=18, color=(255,255,255), center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(text, True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.topleft
    if center: rect.center = pos
    else: rect.topleft = pos
    surf.blit(img, rect)

def render(screen, g, p, enemies, sprites, shot_line):
    if sprites.get("bg"):
        screen.blit(pygame.transform.smoothscale(sprites["bg"], screen.get_size()), (0,0))
    else:
        screen.fill(BG_COLOR)

    for y,row in enumerate(g.map):
        for x,c in enumerate(row):
            if c == '#':
                if sprites.get("wall"):
                    screen.blit(sprites["wall"], (x*TILE, y*TILE))
                else:
                    pygame.draw.rect(screen, WALL_COLOR, (x*TILE, y*TILE, TILE, TILE))

    for (x,y) in g.dots:
        if sprites.get("dot"):
            rect = sprites["dot"].get_rect(center=(x*TILE+TILE//2, y*TILE+TILE//2))
            screen.blit(sprites["dot"], rect.topleft)
        else:
            pygame.draw.rect(screen, DOT_COLOR, (x*TILE+TILE//2-3, y*TILE+TILE//2-3, 6, 6))
    for (x,y) in g.powers:
        if sprites.get("power"):
            rect = sprites["power"].get_rect(center=(x*TILE+TILE//2, y*TILE+TILE//2))
            screen.blit(sprites["power"], rect.topleft)
        else:
            pygame.draw.rect(screen, POWER_COLOR, (x*TILE+TILE//2-6, y*TILE+TILE//2-6, 12, 12), width=2)

    # Player render (no rotation for photo sprite; flip horizontally for left)
    px, py = p.tile
    if p.moving:
        t = min(1.0, (pygame.time.get_ticks() - p.start) / max(1, p.duration))
        px = p.from_tile[0] + (p.to_tile[0] - p.from_tile[0]) * t
        py = p.from_tile[1] + (p.to_tile[1] - p.from_tile[1]) * t
    cx, cy = int((px + 0.5) * TILE), int((py + 0.5) * TILE)

    player_img = sprites.get("player")
    if player_img:
        img = player_img
        if p.facing == [-1,0]:
            img = pygame.transform.flip(img, True, False)
        rect = img.get_rect(center=(cx, cy))
        screen.blit(img, rect.topleft)
    else:
        pygame.draw.circle(screen, (255,255,160), (cx, cy), TILE//2 - 4)

    for i,e in enumerate(enemies):
        if e.respawn_at is not None: continue
        ex, ey = e.tile
        if e.moving:
            t = min(1.0, (pygame.time.get_ticks() - e.start) / max(1, e.duration))
            ex = e.from_tile[0] + (e.to_tile[0] - e.from_tile[0]) * t
            ey = e.from_tile[1] + (e.to_tile[1] - e.from_tile[1]) * t
        spr = sprites.get(e.kind)
        if spr:
            rect = spr.get_rect(center=(int((ex+0.5)*TILE), int((ey+0.5)*TILE)))
            screen.blit(spr, rect.topleft)
        else:
            pygame.draw.circle(screen, (200,200,255), (int((ex+0.5)*TILE), int((ey+0.5)*TILE)), TILE//2-6)

    if shot_line and pygame.time.get_ticks() - shot_line[2] < 120:
        x1,y1,x2,y2,_ = shot_line
        pygame.draw.line(screen, (255,51,85), (x1,y1), (x2,y2), 3)

    draw_text(screen, f"Score: {g.score}", (8, 6), 18)
    draw_text(screen, f"Lives: {'\\u2665'*max(0,p.lives)}", (8, 26), 18)
    draw_text(screen, f"Shots: {p.shots} (Space)", (8, 46), 18)
    if g.won or g.over:
        draw_text(screen, "Victoire !" if g.won else "Game Over", (W*TILE//2, H*TILE//2), 28, center=True)
        draw_text(screen, "Appuie sur R pour rejouer", (W*TILE//2, H*TILE//2+32), 20, center=True)

def main():
    pygame.init()
    pygame.display.set_caption("Stormtrooper Maze (Pygame)")
    screen = pygame.display.set_mode((W*TILE*SCREEN_SCALE, H*TILE*SCREEN_SCALE))
    clock = pygame.time.Clock()

    size = (TILE, TILE)
    sprites = {
        "bg": load_img("bg", None),
        "wall": load_img("wall", size),
        "dot": load_img("dot", (int(TILE*0.6), int(TILE*0.6))),
        "power": load_img("power", (int(TILE*0.9), int(TILE*0.9))),
        "player": load_img("player", size) or load_img("trooper", size) or load_img("pacman", size),
        "troll": load_img("troll", size),
        "zombie": load_img("zombie", size),
        "trooper": load_img("trooper", size),
    }

    g, p, enemies = reset_game()
    desired = None
    shot_line = None

    running = True
    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:    desired = (0,-1); p.facing = [0,-1]
                elif event.key == pygame.K_DOWN: desired = (0, 1); p.facing = [0, 1]
                elif event.key == pygame.K_LEFT: desired = (-1,0); p.facing = [-1,0]
                elif event.key == pygame.K_RIGHT:desired = (1, 0); p.facing = [1, 0]
                elif event.key == pygame.K_SPACE:
                    dx, dy = p.facing if any(p.facing) else (1,0)
                    x1,y1 = int((p.tile[0]+0.5)*TILE), int((p.tile[1]+0.5)*TILE)
                    tx,ty = p.tile
                    for step in range(1, LASER_RANGE+1):
                        tx2,ty2 = tx+dx*step, ty+dy*step
                        if is_wall(tx2,ty2): break
                        tx,ty = tx2,ty2
                    x2,y2 = int((tx+0.5)*TILE), int((ty+0.5)*TILE)
                    shot_line = (x1,y1,x2,y2, now)
                    shoot_laser(g, p, enemies, now)
                elif event.key == pygame.K_r:
                    g, p, enemies = reset_game(); desired = None; shot_line = None

        # Also accept held keys to keep moving in the pressed direction
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_UP]: desired = (0,-1); p.facing = [0,-1]
        elif pressed[pygame.K_DOWN]: desired = (0,1); p.facing = [0,1]
        elif pressed[pygame.K_LEFT]: desired = (-1,0); p.facing = [-1,0]
        elif pressed[pygame.K_RIGHT]: desired = (1,0); p.facing = [1,0]

        try_move_player(g, p, now, desired)
        move_enemies(g, p, enemies, now)

        render(screen, g, p, enemies, sprites, shot_line)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()

import itertools, os, random, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import pygame
from game.game import Game
from game.state import StateID
from weapons.weapon_parts import PART_ORDER
from weapons.weapon import Weapon

random.seed(1)
g = Game(headless=True)
DT = 1 / 60
mouse = {"pos": (640, 360), "down": False}
keys = set()
pygame.mouse.get_pos = lambda: mouse["pos"]
pygame.mouse.get_pressed = lambda *a, **k: (mouse["down"], False, False)
class K:
    def __getitem__(self, k): return k in keys
pygame.key.get_pressed = lambda: K()

def step(n=1):
    for _ in range(n): g.step(DT)

def click(btn):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=btn.rect.center)); step()

def key(k):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")); step()

# 1. every part combination computes sane stats & fires
lib = g.library
n = 0
for combo in itertools.product(*[lib.by_category[c] for c in PART_ORDER]):
    w = Weapon("t", dict(zip(PART_ORDER, combo)))
    s = w.stats
    assert s.damage > 0 and s.fire_rate > 0 and s.magazine_size >= 1 and s.dps > 0, combo
    n += 1
print("combos ok:", n)

# 2. menus
step(5)
for sid in (StateID.LOADOUT, StateID.SETTINGS):
    g.push(sid); step(3); g.pop(); step(1)
g.push(StateID.LOADOUT); click(g.top.buttons.buttons[3]); key(pygame.K_ESCAPE)
assert g.options.starter_index == 3
g.options.starter_index = 0
# 3. start the run via PLAY button
click(g.top.buttons.buttons[0])
assert g.top.state_id == StateID.GAME, g.top
ps = g.play_state; sess = g.session

def bot_frames(frames, god=True):
    for _ in range(frames):
        top = g.top
        if top.state_id != StateID.GAME: return top.state_id
        p = sess.player
        if god: p.hp = p.max_hp
        en = [e for e in ps.world.enemies if e.alive]
        if en:
            t = min(en, key=lambda e: (e.pos - p.pos).length())
            sp = t.pos - ps.camera.offset
            mouse["pos"] = (int(sp.x), int(sp.y))
            mouse["down"] = not mouse["down"] if p.weapon.stats.fire_mode in ("single", "charge", "burst") and random.random() < 0.15 else True
            d = t.pos - p.pos
            keys.clear()
            if d.length() < 250:
                if d.x > 0: keys.add(pygame.K_a)
                else: keys.add(pygame.K_d)
                if d.y > 0: keys.add(pygame.K_w)
                else: keys.add(pygame.K_s)
        else:
            mouse["down"] = False
            # walk toward pickups
            if ps.world.pickups:
                d = ps.world.pickups[0].pos - p.pos; keys.clear()
                keys.add(pygame.K_d if d.x > 0 else pygame.K_a); keys.add(pygame.K_s if d.y > 0 else pygame.K_w)
        step()
    return g.top.state_id

key(pygame.K_ESCAPE); assert g.top.state_id == StateID.PAUSE; step(3); key(pygame.K_ESCAPE)
assert g.top.state_id == StateID.GAME
editor_done = False
t0 = time.time()
for wave_iter in range(12):
    sid = bot_frames(60 * 240)
    if sid != StateID.WAVE_CLEAR: print([(e.enemy_type, e.pos, e.hp, e.max_hp) for e in ps.world.enemies], sess.player.pos, sess.player.weapon.ammo, sess.player.weapon.reserve, sess.player.weapon.stats.fire_mode)
    assert sid == StateID.WAVE_CLEAR, (sid, ps.waves.wave, len(ps.world.enemies), ps.spawner.pending)
    w = ps.waves.wave
    print(f"wave {w} cleared  money={sess.money} kills={sess.kills} parts={len(sess.owned_parts)} wpn={sess.player.weapon.name} t={time.time()-t0:.0f}s")
    step(2)
    key(pygame.K_1)  # pick upgrade 1
    assert g.top.state_id == StateID.INTERMISSION
    sess.money += 400  # bankroll for testing shop
    key(pygame.K_s); assert g.top.state_id == StateID.SHOP
    shop = g.top
    for b in list(shop.buttons.buttons[:6]):
        if b.enabled: click(b)
    for b in list(g.top.buttons.buttons):
        if "SLOT" in b.text and b.enabled: click(b); break
    for b in list(g.top.buttons.buttons):
        if "UPGRADE" in b.text and b.enabled: click(b); break
    step(2); key(pygame.K_ESCAPE)
    assert g.top.state_id == StateID.INTERMISSION
    key(pygame.K_e); assert g.top.state_id == StateID.WEAPON_EDITOR
    ed = g.top
    # click every owned part in each row, keep a random owned per row
    for btn, part in list(ed.part_buttons):
        pass
    for cat in PART_ORDER:
        owned = [p for p in lib.by_category[cat] if p.part_id in sess.owned_parts]
        choice = random.choice(owned)
        for btn, part in g.top.part_buttons:
            if part.part_id == choice.part_id: click(btn); break
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=g.top.part_buttons[-1][0].rect.center, rel=(0,0), buttons=(0,0,0))); step()
    key(pygame.K_RETURN)  # save
    key(pygame.K_ESCAPE)
    assert g.top.state_id == StateID.INTERMISSION
    key(pygame.K_SPACE)
    assert g.top.state_id == StateID.GAME
    for i in range(len(sess.weapons)):
        key(pygame.K_1 + i); step(5)

assert ps.waves.wave >= 10
print("upgrades taken:", [u.name for u in sess.upgrades_taken])
# 4. death -> game over
sess.player.hp = 1; sess.player.invuln = 0
ps._on_player_hit(999, sess.player.pos)
sid = bot_frames(200, god=False)
assert g.top.state_id == StateID.GAME_OVER, g.top
step(3)
click(g.top.buttons.buttons[1])
assert g.top.state_id == StateID.MAIN_MENU and g.session is None
print("ALL OK")

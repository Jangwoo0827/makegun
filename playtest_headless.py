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
import tempfile, settings
settings.SAVE_FILE = os.path.join(tempfile.gettempdir(), "gun_designer_test_options.json")
if os.path.exists(settings.SAVE_FILE): os.remove(settings.SAVE_FILE)
g = Game(headless=True)
assert g.top.state_id == StateID.DEVICE_SELECT, "first launch asks for the device"
import tempfile
g.saves.path = os.path.join(tempfile.gettempdir(), "gun_designer_test_save.json")
g.saves.delete()
from game.profile import Profile
_prof = os.path.join(tempfile.gettempdir(), "gun_designer_test_profile.json")
if os.path.exists(_prof): os.remove(_prof)
g.profile = Profile(_prof)  # never touch the real profile.json
g.profile.tutorial_done = True  # the bot plays the main flow; the tutorial has its own test below
g.profile.hints_seen = {"intermission", "editor", "shop", "wave_clear"}
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
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=btn.rect.center))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=btn.rect.center)); step()

def finger(kind, fid, x, y):
    t = {"down": pygame.FINGERDOWN, "move": pygame.FINGERMOTION, "up": pygame.FINGERUP}[kind]
    pygame.event.post(pygame.event.Event(t, finger_id=fid, x=x / 1280, y=y / 720, dx=0, dy=0, touch_id=0))

def key(k):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")); step()

# 0. device screen: pick PC (key 1) -> main menu, touch stays off
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1, mod=0, unicode="")); g.step(1 / 60)
assert g.top.state_id == StateID.MAIN_MENU and g.options.input_mode == "pc" and not g.touch.active

# 1. every part combination computes sane stats & fires
lib = g.library
n = 0
for _ in range(30000):
    combo = [random.choice(lib.by_category[c]) for c in PART_ORDER]
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
# 3. start the run via PLAY -> stage select -> stage 1
click(g.top.buttons.buttons[0])
assert g.top.state_id == StateID.STAGE_SELECT, g.top
assert not g.top.buttons.buttons[1].enabled, "stage 2 must start locked"
step(2)
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
            if d.length() > 420:
                keys.add(pygame.K_d if d.x > 0 else pygame.K_a); keys.add(pygame.K_s if d.y > 0 else pygame.K_w)
            elif d.length() < 250:
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
        ids = [p.part_id for p in lib.by_category[cat]]
        row = g.top.rows[cat]
        # scroll with the wheel / arrows like a player would, then click
        pygame.mouse.get_pos = lambda r=row: r.viewport.center
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3, flipped=False)); step(30)
        row.ensure_visible(ids.index(choice.part_id)); step(40)
        for btn, part in g.top.part_buttons:
            if part.part_id == choice.part_id:
                assert row.viewport.collidepoint(btn.rect.center), (choice.part_id, btn.rect, row.viewport)
                click(btn); break
        assert g.top.draft.part(cat).part_id == choice.part_id, choice.part_id
        pygame.mouse.get_pos = lambda: mouse["pos"]
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=g.top.part_buttons[-1][0].rect.center, rel=(0,0), buttons=(0,0,0))); step()
    key(pygame.K_RETURN)  # save
    key(pygame.K_ESCAPE)
    assert g.top.state_id == StateID.INTERMISSION
    if w == 2:
        # --- save at intermission -> main menu -> continue
        snap = (sess.money, set(sess.owned_parts), len(sess.upgrades_taken), [x.name for x in sess.weapons])
        g.quit(); g.running = True  # window-close path saves too
        assert g.saves.peek()["phase"] == "intermission"
        g.save_and_quit_to_menu(); assert g.top.state_id == StateID.MAIN_MENU
        assert g.top.buttons.buttons[0].text == "CONTINUE"
        click(g.top.buttons.buttons[0])
        assert g.top.state_id == StateID.INTERMISSION, g.top
        ps = g.play_state; sess = g.session
        assert (sess.money, set(sess.owned_parts), len(sess.upgrades_taken), [x.name for x in sess.weapons]) == snap
        assert ps.waves.wave == 2
        print("save/continue at intermission ok")
    key(pygame.K_SPACE)
    assert g.top.state_id == StateID.GAME
    if w == 3:
        # --- mid-wave save & quit from pause -> continue restarts wave 4
        bot_frames(300)
        money_mid = sess.money
        key(pygame.K_ESCAPE); assert g.top.state_id == StateID.PAUSE
        click(g.top.buttons.buttons[2])
        assert g.top.state_id == StateID.MAIN_MENU and g.saves.peek()["phase"] == "wave"
        click(g.top.buttons.buttons[0])
        assert g.top.state_id == StateID.GAME
        ps = g.play_state; sess = g.session
        assert ps.waves.wave == 4 and sess.money == money_mid, (ps.waves.wave, sess.money, money_mid)
        print("mid-wave save/continue ok")
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
assert not g.saves.has_save(), "game over must delete the save"

assert g.profile.stat("runs") == 1 and g.profile.cores > 0, (g.profile.stats, g.profile.cores)
print("profile after death:", g.profile.cores, "cores,", sorted(g.profile.achievements))

# --- bosses: all four + new enemies spawn, fight and die (stage 5 difficulty)
from systems.wave_manager import build_wave
assert "broodmother" in build_wave(20) and "boss" in build_wave(10)
assert build_wave(25, g.stages[4]).count("warden") == 1 and "boss" in build_wave(25, g.stages[4])
g.start_new_run(4); ps = g.play_state; sess = g.session
assert sess.stage.stage_id == "core" and len(ps.world.walls) == 4 + len(g.stages[4].obstacles)
for et in ["titan", "warden"]:
    e = ps.spawner.spawn_now(et, sess.player.pos); ps._add_enemy(e)
from entities.enemy_types import create_enemy
for et in ["broodmother", "splitter", "bomber", "sniper", "healer", "charger", "summoner", "mini"]:
    e = ps.spawner.spawn_now(et, sess.player.pos); ps._add_enemy(e)
ps.waves.phase = ps.waves.phase.ACTIVE
for _ in range(60 * 20):
    sess.player.hp = sess.player.max_hp
    step()
types = {e.enemy_type for e in ps.world.enemies}
print("alive after 20s:", sorted(types), "enemy bullets:", len(ps.world.enemy_bullets))
for e in ps.world.enemies: e.take_damage(1e9, True)
step(3)
print("kills:", sess.kills)
assert sess.boss_kills >= 3, sess.boss_kills
g.end_run()

# --- affixes
from systems.affixes import AFFIXES, apply_affix, affix_death_actions
g.start_new_run(0); ps = g.play_state; sess = g.session
for aff in AFFIXES:
    e = ps.spawner.spawn_now("normal", sess.player.pos); apply_affix(e, aff); ps._add_enemy(e)
sh = [e for e in ps.world.enemies if e.affix == "shielded"][0]
hp0 = sh.hp; sh.take_damage(5, True); assert sh.hp == hp0 and sh.shield < sh.shield_max, "shield absorbs"
assert affix_death_actions([e for e in ps.world.enemies if e.affix == "volatile"][0]).explosions
assert affix_death_actions([e for e in ps.world.enemies if e.affix == "splitting"][0]).summons == ["mini", "mini"]
step(30)
for e in ps.world.enemies: e.take_damage(1e9, True)
step(3)
assert g.profile.stat("total_affix_kills") >= 6
print("affixes ok")

# --- skills: dash (invulnerable) + grenade (kills)
p = sess.player
keys.clear(); keys.add(pygame.K_d)
x0 = p.pos.x; key(pygame.K_SPACE); assert p.dash_time > 0 and not p.take_damage(10), "dash = invulnerable"
step(15); assert p.pos.x - x0 > 60 and p.dash_cooldown > 0, (p.pos.x - x0)
keys.clear()
for i in range(6):
    e = ps.spawner.spawn_now("normal", p.pos); e.pos = p.pos + pygame.Vector2(200 + i * 4, 0); ps._add_enemy(e)
mouse["pos"] = (int(p.pos.x - ps.camera.offset.x + 200), int(p.pos.y - ps.camera.offset.y))
key(pygame.K_q); assert ps.grenades and p.grenade_cooldown > 0
step(60)
assert sess.run_stats.get("best_grenade_kills", 0) >= 5, sess.run_stats
print("skills ok, grenade dmg", int(ps.grenade_damage()))

# --- synergy + presets in editor
from weapons.weapon_parts import PartCategory as C
for pid in ("shotgun_receiver", "split_ammo", "frost_ammo", "chain_mod"):
    sess.owned_parts.add(pid)
w = sess.player.weapon
w.set_part(lib.get("shotgun_receiver")); w.set_part(lib.get("split_ammo"))
sess.player.refresh_weapons()
assert "SCATTERSHOT" in w.stats.synergies
ps._track_run_stats(); assert "synergist" in g.profile.achievements
g.push(StateID.WEAPON_EDITOR); ed = g.top
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=ed.preset_buttons[0].rect.center)); step()
assert g.profile.preset(0)["parts"]["receiver"] == "shotgun_receiver"
ed = g.top
ed._equip(lib.get("pistol_receiver")); assert ed.draft.part(C.RECEIVER).part_id == "pistol_receiver"
click(ed.preset_buttons[0]); assert g.top.draft.part(C.RECEIVER).part_id == "shotgun_receiver"
assert g.top._synergies_gained(lib.get("chain_mod")) == [] and sess.owned_parts
g.top.draft.parts[C.AMMO] = lib.get("frost_ammo")
assert "CRYO CHAIN" in g.top._synergies_gained(lib.get("chain_mod"))
step(2); key(pygame.K_ESCAPE)
print("synergy + presets ok")

# --- stage clear: finish stage 1 -> stage 2 unlocked, cores, victory screen
g.pop_to(StateID.GAME)
ps.waves.wave = sess.stage.waves - 1; ps.world.enemies.clear()
ps._start_wave()
assert ps.waves.is_final_wave
ps.spawner.queue.clear(); ps.waves.phase = ps.waves.phase.ACTIVE
step(5)
assert g.top.state_id == StateID.STAGE_CLEAR, g.top
assert g.profile.unlocked_stage >= 1 and g.profile.stat("stages_cleared") >= 1 and "stage_1" in g.profile.achievements
assert not g.saves.has_save(), "stage clear ends the run"
cores_before = g.profile.cores
click(g.top.buttons.buttons[0])  # NEXT stage
assert g.top.state_id == StateID.GAME and g.session.stage.stage_id == "foundry"
print("stage clear ok")

# --- meta upgrades apply to the next run
g.end_run()
g.profile.cores = 1000
g.push(StateID.META); m = g.top
for _ in range(3): click(m.buttons.buttons[0]); m = g.top   # VITALITY x3
assert g.profile.meta_level("vitality") == 3
key(pygame.K_ESCAPE)
g.start_new_run(0)
assert g.session.stats.max_hp == 100 + 36 and g.session.player.hp == 136, g.session.stats.max_hp
g.end_run()
print("meta ok")

# --- touch controls: ignored in PC mode; MOBILE mode: move stick, aim stick fires, buttons
g.start_new_run(0); ps = g.play_state; sess = g.session; p = sess.player
finger("down", 9, 200, 500); step(); finger("up", 9, 200, 500); step()
assert not g.touch.active and not g.touch._sticks, "PC mode ignores touch"
g.set_input_mode("mobile")
ps.waves.countdown = 999  # hold the wave so no enemies interfere
step(2)
x0 = p.pos.x
finger("down", 1, 200, 500); step(); finger("move", 1, 290, 500); step(40)
assert g.touch.active and p.pos.x - x0 > 100, ("touch move", p.pos.x - x0)
finger("up", 1, 290, 500); step()
shots0 = len(ps.world.bullets)
p.weapon.ammo = p.weapon.stats.magazine_size
finger("down", 2, 900, 400); step(); finger("move", 2, 900, 320); step(30)
assert len(ps.world.bullets) > shots0 or p.weapon.ammo < p.weapon.stats.magazine_size, "aim stick fires"
assert abs(p.aim_dir.y + 1) < 0.05, p.aim_dir   # aiming up
finger("up", 2, 900, 320); step()
dash_btn = [b for b in g.touch.buttons if b.name == "dash"][0]
finger("down", 3, *dash_btn.center); step(); finger("up", 3, *dash_btn.center)
assert p.dash_cooldown > 0, "dash button"
pause_btn = [b for b in g.touch.buttons if b.name == "pause"][0]
finger("down", 4, *pause_btn.center); step(); finger("up", 4, *pause_btn.center); step()
assert g.top.state_id == StateID.PAUSE
key(pygame.K_ESCAPE); assert g.top.state_id == StateID.GAME
pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(500, 500), rel=(5, 5), buttons=(0, 0, 0), touch=False)); step()
assert g.touch.active, "mobile mode stays on (chosen, not detected)"
g.push(StateID.SETTINGS); g.push(StateID.DEVICE_SELECT); click(g.top.buttons.buttons[0])
assert g.top.state_id == StateID.SETTINGS and g.options.input_mode == "pc" and not g.touch.active
g.pop()
print("touch ok")

# --- editor rows: drag scrolls without equipping; tap equips
g.push(StateID.WEAPON_EDITOR); ed = g.top
from weapons.weapon_parts import PartCategory as PC
sess.owned_parts |= set(lib.parts)
ed._build(); row = ed.rows[PC.RECEIVER]; before = ed.draft.part(PC.RECEIVER).part_id
y = row.viewport.centery
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(row.viewport.right - 40, y)))
pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(row.viewport.right - 300, y), rel=(-260, 0), buttons=(1, 0, 0)))
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(row.viewport.right - 300, y))); step(2)
assert row.target > 0 and ed.draft.part(PC.RECEIVER).part_id == before, "drag scrolls only"
ed.save_mode = False
saveto = [b for b in g.top.buttons.buttons if b.text == "SAVE TO"][0]; click(saveto)
click(g.top.preset_buttons[2]); assert g.profile.preset(2) is not None, "SAVE TO saves"
key(pygame.K_ESCAPE); g.end_run()
print("editor touch ui ok")

# --- v1.2: 8 stages, ascension, modes, characters, attachments, evolution, patch notes
assert len(g.stages) == 8 and g.stages[-1].stage_id == "omega"
from game.ascension import ascension_mods
from systems.wave_manager import build_wave, stage_scaling
a10 = ascension_mods(10)
assert abs(a10.enemy_hp - 1.40) < 1e-6 and a10.start_money == -100 and abs(a10.heal - 0.7) < 1e-6
assert len(build_wave(5, g.stages[0], a10.enemy_count)) > len(build_wave(5, g.stages[0]))
end = g.modes["endless"]
assert end.bosses_for(10) == ("boss",) and end.bosses_for(20) == ("titan",) and len(end.bosses_for(30)) == 2
assert end.bosses_for(15) == ()
rush = g.modes["bossrush"]
assert build_wave(3, rush)[0] == "broodmother"

# ascension applies on normal stages
g.profile.ascension_unlocked = 10; g.profile.selected_ascension = 7
g.start_new_run(0); s = g.session; ps = g.play_state
assert s.ascension.level == 7 and s.stats.heal_multiplier < 1.0 and s.price(100) == 120
hp0 = s.player.hp; s.player.hp = 10; s.player.heal(10); assert abs(s.player.hp - 17) < 0.01, s.player.hp
assert ps.waves.asc.level == 7
g.end_run(); g.profile.selected_ascension = 0

# final stage clear unlocks next ascension + achievement
g.profile.ascension_unlocked = 3; g.profile.selected_ascension = 3; g.profile.unlocked_stage = 7
g.start_new_run(7); ps = g.play_state; sess = g.session
ps.waves.wave = sess.stage.waves - 1; ps.world.enemies.clear(); ps._start_wave()
ps.spawner.queue.clear(); ps.waves.phase = ps.waves.phase.ACTIVE; step(5)
assert g.top.state_id == StateID.STAGE_CLEAR, g.top
assert g.profile.ascension_unlocked == 4 and "ascended" in g.profile.achievements and "stage_8" in g.profile.achievements
step(2); g.end_run(); g.profile.selected_ascension = 0
print("stages + ascension ok")

# endless: no final wave, best wave recorded on death
g.start_new_run(stage_id="endless"); ps = g.play_state; sess = g.session
assert sess.stage.mode == "endless" and not ps.waves.is_final_wave and sess.ascension.level == 0
ps.waves.wave = 33; sess.wave_reached = 33
sess.player.invuln = 0; sess.player.hp = 1; ps._on_player_hit(999, sess.player.pos)
for _ in range(120):
    step()
    if g.top.state_id == StateID.GAME_OVER: break
assert g.top.state_id == StateID.GAME_OVER and g.profile.stat("endless_best") >= 33 and "endless_30" in g.profile.achievements
g.end_run()

# boss rush: starts in the intermission with money/parts, records time on clear
g.start_new_run(stage_id="bossrush"); sess = g.session; ps = g.play_state
assert g.top.state_id == StateID.INTERMISSION and sess.money >= 1500 and len(sess.owned_parts) >= 18
key(pygame.K_SPACE); assert g.top.state_id == StateID.GAME and ps.waves.wave == 1
assert any(e.is_boss for e in ps.world.enemies) or "boss" in ps.spawner.queue
ps.waves.wave = rush.waves - 1; ps.world.enemies.clear(); ps.spawner.queue.clear()
sess.run_time = 123.4
ps.waves.phase = ps.waves.phase.CLEARED; ps.awaiting_next_wave = True
ps._start_wave(); ps.world.enemies.clear(); ps.spawner.queue.clear(); ps.waves.phase = ps.waves.phase.ACTIVE
step(5)
assert g.top.state_id == StateID.STAGE_CLEAR, g.top
assert g.profile.stat("bossrush_clears") == 1 and 120 < g.profile.stat("best_bossrush_time") < 130
assert len(g.top.buttons.buttons) == 1, "no NEXT stage after boss rush"
step(2); g.end_run()
print("endless + boss rush ok")

# characters: buy duelist, start with katana, color, stats
g.profile.cores = 500
g.push(StateID.LOADOUT); lo = g.top
from game.characters import all_characters
idx = [c.char_id for c in all_characters()].index("duelist")
click(lo.buttons.buttons[4 + idx])
assert "duelist" in g.profile.unlocked_characters and g.options.character == "duelist" and g.profile.cores == 380
key(pygame.K_ESCAPE)
g.start_new_run(0); s = g.session
from weapons.weapon_parts import PartCategory as C
assert s.player.weapon.part(C.ATTACHMENT).part_id == "katana" and s.player.color == (255, 100, 140)
assert abs(s.stats.crit_chance - (0.05 + 0.10)) < 1e-6
g.end_run(); g.options.character = "gunner"

# attachments: every type procs and kills
g.start_new_run(0); ps = g.play_state; s = g.session; p = s.player
ps.waves.countdown = 999
for att in ("bayonet", "katana", "grenade_launcher", "flamethrower", "support_drone", "tesla_attachment"):
    p.weapon.set_part(lib.get(att)); s.player.refresh_weapons()
    ps.world.enemies.clear(); ps.grenades.clear(); ps.attachments.timer = 0
    for i in range(4):
        e = ps.spawner.spawn_now("normal", p.pos); e.pos = p.pos + pygame.Vector2(60 + i * 10, (i - 1.5) * 12)
        e.max_hp = e.hp = 5; e.speed = e.base_speed = 0; ps.world.enemies.append(e)
    p.aim_at(p.pos + pygame.Vector2(100, 0))
    mouse["pos"] = (int(p.pos.x - ps.camera.offset.x + 100), int(p.pos.y - ps.camera.offset.y))
    mouse["down"] = att in ("grenade_launcher", "flamethrower")
    p.weapon.ammo = 0; p.weapon.reserve = 0  # no gun shots: only the attachment can kill
    kills0 = s.kills
    for _ in range(90):
        p.hp = p.max_hp; p.weapon.ammo = 0; step()
    mouse["down"] = False
    assert s.kills > kills0, f"{att} did not kill"
print("attachments ok")

# evolution through the shop
w = p.weapon
for pid in ("shotgun_receiver", "split_ammo"):
    s.owned_parts.add(pid); w.set_part(lib.get(pid))
w.level = 8; s.player.refresh_weapons()
assert s.evolution_for(w) is not None
s.money = 100
g.push(StateID.SHOP); sh = g.top
evo_btn = [b for b in sh.buttons.buttons if b.text.startswith("EVOLVE INTO")][0]
click(evo_btn)
assert w.evolution == "scattershot" and w.name == "Thunder Choir" and w.stats.evolution == "Thunder Choir"
assert "evolved" in g.profile.achievements or s.run_stats.get("run_evolutions") == 1
key(pygame.K_ESCAPE)
# save/load keeps ascension, character, evolution
g.pop_to(StateID.GAME); ps.awaiting_next_wave = True
g.save_run(); g.save_and_quit_to_menu(); assert g.continue_run()
w2 = g.session.player.weapon
assert w2.evolution == "scattershot" and w2.name == "Thunder Choir"
g.end_run()
print("evolution + save ok")

# new screens render
for sid in (StateID.PATCH_NOTES, StateID.LOADOUT, StateID.STAGE_SELECT):
    g.push(sid); step(3); g.pop()

# --- v1.3: architect, tutorial, codex + history, stats tabs, mobile text
assert g.stages[-1].bosses_for(25) == ("architect",) and g.modes["bossrush"].bosses_for(5) == ("architect",)
g.start_new_run(0); ps = g.play_state; sess = g.session
arch = ps.spawner.spawn_now("architect", sess.player.pos); ps._add_enemy(arch)
ps.waves.phase = ps.waves.phase.ACTIVE
for _ in range(60 * 6):
    sess.player.hp = sess.player.max_hp; step()
assert arch.mimic_parts is sess.player.weapon.parts and len(ps.world.enemy_bullets) > 0
arch.hp = arch.max_hp * 0.2; step(30); assert arch.phase == 3
arch.take_damage(1e9, True); step(3)
assert "architect" in g.profile.discovered["enemies"]
g.end_run()
print("architect ok")

# tutorial: holds the wave, advances through goals, then marks done
g.profile.tutorial_done = False; g.profile.hints_seen = set()
g.start_new_run(0); ps = g.play_state; p = g.session.player
t = ps.tutorial; assert t is not None and t.step.key == "move"
step(200); assert ps.waves.phase == ps.waves.phase.COUNTDOWN, "wave held during tutorial"
keys.clear(); keys.add(pygame.K_d); step(70); keys.clear()
assert t.step.key == "shoot", t.step
mouse["down"] = True
for i in range(180):
    mouse["down"] = i % 2 == 0; step()
mouse["down"] = False
assert t.step.key == "dash", (t.step.key, t.progress, p.weapon.ammo, p.weapon.reloading, p.weapon.stats.fire_mode, g.touch.active, p.alive, g.top)
key(pygame.K_SPACE); assert t.step.key == "grenade"
key(pygame.K_q); assert t.step.key == "clear"
step(200); assert ps.waves.phase != ps.waves.phase.COUNTDOWN, "wave starts after the basics"
ps.world.enemies.clear(); ps.spawner.queue.clear(); step(5)
assert g.top.state_id == StateID.WAVE_CLEAR and g.profile.tutorial_done and ps.tutorial is None
key(pygame.K_1); assert g.top.state_id == StateID.INTERMISSION
assert "wave_clear" in g.profile.hints_seen
g.end_run()
print("tutorial ok")

# codex + history + stats tabs
assert len(g.profile.history) >= 3 and "victory" in g.profile.history[0]
assert g.profile.discovered["parts"] and g.profile.discovered["synergies"]
g.push(StateID.STATS); st = g.top
for name in ("STATS", "ACHIEVEMENTS", "CODEX", "HISTORY"):
    click([b for b in g.top.buttons.buttons if b.text == name][0]); step(2)
    assert g.top.tab == name
for name in ("ENEMIES", "SYNERGIES", "PARTS"):
    st._tab("CODEX"); click([b for b in g.top.buttons.buttons if b.text == name][0]); step(2)
g.pop()
# mobile text enlarges small fonts only
from ui import fonts
g.set_input_mode("mobile"); assert fonts.get_font(12).get_height() > fonts.get_font(12).get_height() - 1
small_mobile = fonts.get_font(12).size("ABC")[0]
g.set_input_mode("pc"); small_pc = fonts.get_font(12).size("ABC")[0]
assert small_mobile > small_pc and fonts.get_font(40).size("A") == fonts.get_font(40).size("A")
print("codex + history + mobile text ok")

# --- every screen renders
for sid in (StateID.STAGE_SELECT, StateID.META, StateID.STATS):
    g.push(sid); step(3); g.pop()
g.profile.save()
assert os.path.exists(_prof)
print("ALL OK")

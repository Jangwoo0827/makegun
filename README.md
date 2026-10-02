# GUN DESIGNER

2D top-down roguelite shooter where you build your own gun from parts.

```bash
pip install pygame
python main.py
```

## Run as an .exe (no Python needed)
```bash
pip install pyinstaller
python tools/build_exe.py
```
Produces `dist/GunDesigner.exe`; saves and the profile are stored next to the exe.

## Controls
| Key | Action |
|---|---|
| WASD | Move |
| Mouse | Aim |
| Left mouse | Fire (hold for Auto, release for Charge) |
| R | Reload |
| Space / Left Shift | Dash (invulnerable) |
| Q / Right mouse | Throw grenade |
| 1 / 2 / 3, mouse wheel | Switch weapon slot |
| ESC | Pause |

## Saving
- The run autosaves at every wave start and between waves (`save_run.json`).
- **ESC → SAVE & QUIT** (or closing the window) mid-wave keeps your money, parts and upgrades; the wave restarts on **CONTINUE**.
- Dying deletes the save (roguelite rules).

## Stages & progression
- **5 stages** (Outskirts → Foundry → The Hive → Fortress → The Core), each with its own map, enemy mix, difficulty
  and bosses (`data/stages.json`). Clear every wave to unlock the next stage.
- **Cores** are earned at the end of every run (more for later stages, bosses and stage clears) and spent on
  **permanent upgrades** in UPGRADES (`data/meta_upgrades.json`).
- **Achievements & lifetime stats** in STATS (`data/achievements.json`), saved in `profile.json`.
- **Bosses:** THE GUNNER, THE TITAN, THE BROODMOTHER, THE WARDEN (protected by shield drones).
- **Elite affixes** on later stages: Swift, Armored, Shielded, Giant, Volatile, Splitting.
- **Part synergies** (`data/synergies.json`): e.g. Frost + Chain = CRYO CHAIN. The editor tells you which part
  completes a synergy.
- **Weapon presets:** 4 slots in the editor that persist across runs (left-click load, right-click save).

## Loop
Wave → kill enemies → collect money/parts → **WAVE CLEAR** (pick 1 of 3 upgrades) →
Shop / Weapon Editor → next wave. Elites appear from wave 5. Bosses every 10 waves, alternating
**THE GUNNER** (10, 30, ...) and **THE BROODMOTHER** (20, 40, ...).

Enemies: Grunt, Runner, Brute, Gunner, Charger, Bomber, Splitter (+ Mites), Sniper, Medic, Summoner, Elite Reaver.

## Weapon parts
Receiver · Barrel · Magazine · Trigger · Ammo · Modifier (56 parts, 40 run upgrades). In the editor,
scroll a part row with the mouse wheel or the `<` `>` arrows. All stats live in `data/weapons.json`;
enemies in `data/enemies.json`; upgrades in `data/upgrades.json`.

## Layout
- `game/` – Game loop + state stack, PlayState, World, Camera, RunSession
- `entities/` – Player, Enemy/Boss, Bullet, Pickup
- `weapons/` – parts, data loader, Weapon stat calc, builder/presets, gun renderer
- `systems/` – waves, spawning, collision, combat effects, loot, upgrades, shop, effects, sound
- `ui/` – HUD, menus, wave clear, shop, weapon editor, buttons, scroll rows
- `systems/save_manager.py` – save / continue; `systems/assets.py` – optional image loading
- `tools/make_placeholders.py` – regenerates `assets/placeholders/`

`python playtest_headless.py` runs an automated headless playthrough (menus → 12 waves incl. boss → game over).

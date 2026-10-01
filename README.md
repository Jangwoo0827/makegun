# GUN DESIGNER

2D top-down roguelite shooter where you build your own gun from parts.

```bash
pip install pygame
python main.py
```

## Controls
| Key | Action |
|---|---|
| WASD | Move |
| Mouse | Aim |
| Left mouse | Fire (hold for Auto, release for Charge) |
| R | Reload |
| 1 / 2 / 3, mouse wheel | Switch weapon slot |
| ESC | Pause |

## Saving
- The run autosaves at every wave start and between waves (`save_run.json`).
- **ESC → SAVE & QUIT** (or closing the window) mid-wave keeps your money, parts and upgrades; the wave restarts on **CONTINUE**.
- Dying deletes the save (roguelite rules).

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

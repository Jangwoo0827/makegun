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

## Loop
Wave → kill enemies → collect money/parts → **WAVE CLEAR** (pick 1 of 3 upgrades) →
Shop / Weapon Editor → next wave. Elites appear from wave 5; **THE GUNNER** boss every 10 waves.

## Weapon parts
Receiver · Barrel · Magazine · Trigger · Ammo · Modifier. All stats live in `data/weapons.json`;
enemies in `data/enemies.json`; upgrades in `data/upgrades.json`.

## Layout
- `game/` – Game loop + state stack, PlayState, World, Camera, RunSession
- `entities/` – Player, Enemy/Boss, Bullet, Pickup
- `weapons/` – parts, data loader, Weapon stat calc, builder/presets, gun renderer
- `systems/` – waves, spawning, collision, combat effects, loot, upgrades, shop, effects, sound
- `ui/` – HUD, menus, wave clear, shop, weapon editor, buttons

`python playtest_headless.py` runs an automated headless playthrough (menus → 12 waves incl. boss → game over).

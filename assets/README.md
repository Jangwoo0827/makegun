# Assets

The game runs with **no asset files**: everything is drawn with pygame shapes and sounds are synthesized.

## Images (optional)
If `assets/images/<category>/<name>.png` exists, the game draws it instead of the shape.

| Folder | Name | Drawn size | Notes |
|---|---|---|---|
| `enemies/` | enemy id from `data/enemies.json` (`normal`, `boss`, `broodmother`, ...) | ~2.4x radius | **face right**, the game rotates it |
| `player/` | `player` | 40x40 | **face right** |
| `parts/` | part id from `data/weapons.json` (`smg_receiver`, ...) | 96x48 | icon in editor and shop |
| `pickups/` | `money`, `health`, `ammo`, `buff`, `part` | 32x32 | |
| `tiles/` | `floor` (80x80, tiled), `wall` (40x40, tiled) | | |

**Placeholders:** `assets/placeholders/` has a labeled template with the exact file name and size for
every image (see `manifest.json`). Copy one into the matching `assets/images/` folder and paint over it.
After adding new enemies or parts, run `python tools/make_placeholders.py` to regenerate the templates.

## Sounds (optional)
Drop WAV files into `assets/sounds/` named after the effect:
`shoot, hit, enemy_die, explosion, pickup, hurt, reload, click, buy, wave, boss` (e.g. `assets/sounds/shoot.wav`).

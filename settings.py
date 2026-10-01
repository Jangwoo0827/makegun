"""Global configuration constants for Gun Designer."""
from __future__ import annotations

import os

# --- Paths ---------------------------------------------------------------
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
DATA_DIR: str = os.path.join(BASE_DIR, "data")
ASSETS_DIR: str = os.path.join(BASE_DIR, "assets")
SOUND_DIR: str = os.path.join(ASSETS_DIR, "sounds")
SAVE_FILE: str = os.path.join(BASE_DIR, "settings_save.json")

# --- Display -------------------------------------------------------------
TITLE: str = "GUN DESIGNER"
SCREEN_WIDTH: int = 1280
SCREEN_HEIGHT: int = 720
FPS: int = 60
MAX_DT: float = 1.0 / 20.0  # clamp to avoid tunnelling on hitches

# --- Arena ---------------------------------------------------------------
ARENA_WIDTH: int = 2400
ARENA_HEIGHT: int = 1600
WALL_THICKNESS: int = 40
GRID_SIZE: int = 80

# --- Player defaults -----------------------------------------------------
PLAYER_RADIUS: float = 16.0
PLAYER_MAX_HP: float = 100.0
PLAYER_MOVE_SPEED: float = 260.0
PLAYER_DAMAGE_MULTIPLIER: float = 1.0
PLAYER_FIRE_RATE_MULTIPLIER: float = 1.0
PLAYER_CRIT_CHANCE: float = 0.05
PLAYER_CRIT_DAMAGE: float = 1.5
PLAYER_INVULN_TIME: float = 0.6
PLAYER_PICKUP_RADIUS: float = 110.0
MAX_WEAPON_SLOTS: int = 3

# --- Economy -------------------------------------------------------------
STARTING_MONEY: int = 100
WAVE_CLEAR_BASE_REWARD: int = 100
WAVE_CLEAR_PER_WAVE: int = 25
SLOT_PRICES: tuple[int, ...] = (0, 300, 700)
SHOP_OFFER_COUNT: int = 6
SHOP_REROLL_COST: int = 25
WEAPON_UPGRADE_BASE_COST: int = 80
WEAPON_UPGRADE_DAMAGE_PER_LEVEL: float = 0.12
HEALTH_ITEM_PRICE: int = 60
AMMO_ITEM_PRICE: int = 30

# --- Waves ---------------------------------------------------------------
BOSS_WAVE_INTERVAL: int = 10
ELITE_WAVE_INTERVAL: int = 5
WAVE_START_DELAY: float = 2.0
SPAWN_INTERVAL: float = 0.55
MAX_ALIVE_ENEMIES: int = 28
RESERVE_MAGAZINES: int = 5

# --- Colors --------------------------------------------------------------
Color = tuple[int, int, int]

BG_COLOR: Color = (14, 16, 22)
GRID_COLOR: Color = (24, 28, 38)
WALL_COLOR: Color = (52, 58, 74)
WALL_EDGE_COLOR: Color = (86, 96, 120)
PLAYER_COLOR: Color = (120, 220, 255)
PLAYER_OUTLINE: Color = (230, 250, 255)
ENEMY_BULLET_COLOR: Color = (255, 90, 90)
UI_PANEL: Color = (24, 27, 36)
UI_PANEL_LIGHT: Color = (36, 41, 54)
UI_BORDER: Color = (70, 78, 100)
UI_TEXT: Color = (225, 230, 240)
UI_TEXT_DIM: Color = (140, 148, 168)
UI_ACCENT: Color = (255, 196, 64)
UI_GOOD: Color = (110, 230, 130)
UI_BAD: Color = (255, 90, 90)
HP_COLOR: Color = (230, 70, 80)
MONEY_COLOR: Color = (255, 214, 90)

RARITY_COLORS: dict[str, Color] = {
    "COMMON": (190, 195, 205),
    "UNCOMMON": (100, 220, 120),
    "RARE": (80, 160, 255),
    "EPIC": (190, 100, 255),
    "LEGENDARY": (255, 170, 40),
}
RARITY_WEIGHTS: dict[str, float] = {
    "COMMON": 50.0,
    "UNCOMMON": 28.0,
    "RARE": 14.0,
    "EPIC": 6.0,
    "LEGENDARY": 2.0,
}

"""WEAPON_EDITOR state: swap parts, preview the gun and see live stats."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from game.state import GameState, StateID
from ui.buttons import Button, ButtonGroup, draw_panel, wrap_text
from ui.fonts import draw_text
from ui.menus import draw_backdrop
from systems.assets import ASSETS
from ui.scroll_row import ScrollRow
from weapons.gun_renderer import draw_gun
from weapons.weapon import Weapon, WeaponStats
from weapons.weapon_builder import BLUEPRINTS, WeaponPreset
from weapons.weapon_parts import PART_ORDER, PartCategory, WeaponPart

if TYPE_CHECKING:
    from game.game import Game

W, H = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
PARTS_X, PARTS_Y, ROW_H = 520, 64, 90
PART_BTN_W: int = 128

# (label, getter, higher_is_better, format)
COMPARE_ROWS: tuple[tuple[str, str, bool, str], ...] = (
    ("DAMAGE", "damage", True, "{:.1f}"),
    ("BULLETS", "bullet_count", True, "{:.0f}"),
    ("FIRE RATE", "fire_rate", True, "{:.1f}"),
    ("MAGAZINE", "magazine_size", True, "{:.0f}"),
    ("RELOAD", "reload_time", False, "{:.2f}s"),
    ("RANGE", "range", True, "{:.0f}"),
    ("SPREAD", "spread", False, "{:.1f}"),
    ("BULLET SPD", "bullet_speed", True, "{:.0f}"),
    ("CRIT", "crit_chance", True, "{:.0%}"),
    ("PIERCE", "pierce", True, "{:.0f}"),
    ("EXPLOSION", "explosion_radius", True, "{:.0f}"),
    ("DPS", "dps", True, "{:.0f}"),
)


class WeaponEditorState(GameState):
    state_id = StateID.WEAPON_EDITOR

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.session = game.require_session()
        self.slot: int = self.session.player.current
        self.draft: Weapon = self._make_draft(self.slot)
        self.dirty: bool = False
        self.hover_part: WeaponPart | None = None
        self.message: str = ""
        self.message_time: float = 0.0
        self.buttons = ButtonGroup()
        self.part_buttons: list[tuple[Button, WeaponPart]] = []
        self.rows: dict[PartCategory, ScrollRow] = {
            c: ScrollRow(pygame.Rect(PARTS_X, PARTS_Y + i * ROW_H + 26, W - PARTS_X - 20, 52), PART_BTN_W)
            for i, c in enumerate(PART_ORDER)}
        self.time: float = 0.0
        self._build()
        for category, row in self.rows.items():  # start each row scrolled to the equipped part
            ids = [p.part_id for p in self.session.library.by_category[category]]
            row.ensure_visible(ids.index(self.draft.part(category).part_id), instant=True)

    def on_enter(self) -> None:
        pygame.mouse.set_visible(True)

    def _make_draft(self, slot: int) -> Weapon:
        src = self.session.weapons[slot]
        draft = self.session.builder.clone(src)
        draft.refresh(self.session.player.effective_stats)
        return draft

    # ---------------------------------------------------------------- layout
    def _build(self) -> None:
        self.buttons.clear()
        self.part_buttons.clear()
        s = self.session
        # Slot tabs
        for i in range(len(s.weapons)):
            self.buttons.add(Button((20 + i * 100, 64, 92, 34), f"SLOT {i + 1}", lambda i=i: self._select_slot(i),
                                    font_size=15, selected=i == self.slot, hotkey=pygame.K_1 + i))
        # Parts: one horizontally scrolling row per category
        for category in PART_ORDER:
            row_buttons: list[Button] = []
            for part in s.library.by_category[category]:
                owned = part.part_id in s.owned_parts
                name = part.name.replace(" Receiver", "").replace(" Barrel", "").replace(" Magazine", "")
                btn = Button((0, 0, PART_BTN_W, 52), name if owned else "LOCKED", lambda p=part: self._equip(p),
                             font_size=14, accent=settings.RARITY_COLORS[part.rarity.value], enabled=owned,
                             selected=self.draft.part(category).part_id == part.part_id,
                             subtext=part.rarity.value.title() if owned else name)
                row_buttons.append(btn)
                self.part_buttons.append((btn, part))
            self.rows[category].set_items(row_buttons)
        # Blueprints
        for i, bp in enumerate(BLUEPRINTS):
            ok = all(pid in s.owned_parts for pid in bp.part_ids.values())
            self.buttons.add(Button((20 + i * 162, 372, 154, 34), bp.name, lambda b=bp: self._load_blueprint(b),
                                    font_size=14, enabled=ok, accent=settings.RARITY_COLORS["EPIC"]))
        # Footer
        self.buttons.add(Button((W - 420, H - 54, 200, 44), "SAVE WEAPON", self._save, accent=settings.UI_GOOD,
                                hotkey=pygame.K_RETURN, enabled=self.dirty))
        self.buttons.add(Button((W - 210, H - 54, 190, 44), "BACK", self._back, hotkey=pygame.K_ESCAPE))

    # --------------------------------------------------------------- actions
    def _notify(self, text: str) -> None:
        self.message = text
        self.message_time = 2.0

    def _select_slot(self, slot: int) -> None:
        if slot == self.slot:
            return
        if self.dirty:
            self._save(stay=True)
        self.slot = slot
        self.draft = self._make_draft(slot)
        self.dirty = False
        self._build()

    def _equip(self, part: WeaponPart) -> None:
        if self.draft.part(part.category).part_id == part.part_id:
            return
        self.draft.parts[part.category] = part
        self.draft.refresh(self.session.player.effective_stats)
        self.dirty = True
        self.game.sound.play("click")
        self._build()

    def _load_blueprint(self, bp: WeaponPreset) -> None:
        for category, pid in bp.part_ids.items():
            self.draft.parts[category] = self.session.library.get(pid)
        self.draft.refresh(self.session.player.effective_stats)
        self.dirty = True
        self._notify(f"Loaded blueprint: {bp.name}")
        self._build()

    def _save(self, stay: bool = False) -> None:
        s = self.session
        target = s.weapons[self.slot]
        target.parts = dict(self.draft.parts)
        target.name = s.builder.auto_name(target)
        s.player.refresh_weapons()
        target.ammo = target.stats.magazine_size
        target.reserve = target.reserve_max
        target.cancel_actions()
        self.dirty = False
        self.game.sound.play("buy")
        self._notify(f"Saved: {target.name}")
        if not stay:
            self._build()

    def _back(self) -> None:
        self.game.pop()

    # ---------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
        for row in list(self.rows.values()):
            if row.handle_event(event):
                return
        self.buttons.handle_event(event)

    def _update_hover(self, pos: tuple[int, int]) -> None:
        self.hover_part = None
        for category, row in self.rows.items():
            idx = row.hovered_index(pos)
            if idx is not None:
                self.hover_part = self.session.library.by_category[category][idx]

    def update(self, dt: float) -> None:
        self.time += dt
        for row in self.rows.values():
            row.update(dt)
        self.message_time = max(0.0, self.message_time - dt)

    # ------------------------------------------------------------------ draw
    def _preview_stats(self) -> WeaponStats | None:
        if self.hover_part is None or self.hover_part.part_id not in self.session.owned_parts:
            return None
        if self.draft.part(self.hover_part.category).part_id == self.hover_part.part_id:
            return None
        trial = self.session.builder.clone(self.draft)
        trial.parts[self.hover_part.category] = self.hover_part
        return trial.compute_stats(self.session.player.effective_stats)

    def draw(self, surface: pygame.Surface) -> None:
        draw_backdrop(surface, 0.0)
        draw_text(surface, "GUN DESIGNER", (W // 2, 26), 32, settings.UI_ACCENT, True, "center")
        draw_text(surface, f"$ {self.session.money}", (W - 24, 14), 22, settings.MONEY_COLOR, True, "topright")

        # Preview panel
        pv = pygame.Rect(20, 104, 480, 260)
        draw_panel(surface, pv)
        name = self.session.builder.auto_name(self.draft)
        draw_text(surface, name + ("  *" if self.dirty else ""), (pv.centerx, pv.y + 18), 20, settings.UI_TEXT,
                  True, "center")
        draw_text(surface, f"Lv.{self.draft.level}", (pv.right - 14, pv.y + 10), 15, settings.UI_ACCENT, True,
                  "topright")
        draw_gun(surface, self.draft.parts, (pv.centerx - 70, pv.centery - 20), 0.0, 3.5)
        for j, line in enumerate(wrap_text(self.draft.describe_parts(), 12, pv.w - 24)[:2]):
            draw_text(surface, line, (pv.centerx, pv.bottom - 36 + j * 15), 12, settings.UI_TEXT_DIM, anchor="center")

        # Stats panel with deltas
        st = pygame.Rect(20, 414, 480, 296)
        draw_panel(surface, st)
        draw_text(surface, "STATS", (st.x + 14, st.y + 10), 16, settings.UI_ACCENT, True)
        cur = self.draft.stats
        new = self._preview_stats()
        for i, (label, attr, higher, fmt) in enumerate(COMPARE_ROWS):
            col, row = divmod(i, 6)
            x = st.x + 14 + col * 234
            y = st.y + 38 + row * 28
            a = float(getattr(cur, attr))
            draw_text(surface, label, (x, y), 15, settings.UI_TEXT_DIM)
            draw_text(surface, fmt.format(a), (x + 120, y), 15, settings.UI_TEXT, True)
            if new is not None:
                b = float(getattr(new, attr))
                if abs(b - a) > 1e-6:
                    better = (b > a) == higher
                    draw_text(surface, ("+" if b > a else "") + fmt.format(b - a).replace("s", ""),
                              (x + 180, y), 14, settings.UI_GOOD if better else settings.UI_BAD, True)
        mode = cur.fire_mode.upper() + (f" x{cur.burst_count}" if cur.fire_mode == "burst" else "")
        effects = [f"MODE {mode}", f"AMMO {cur.ammo_type.replace('_', ' ').upper()}"]
        if cur.move_speed_mult < 0.999:
            effects.append(f"MOVE {cur.move_speed_mult:.0%}")
        draw_text(surface, "   ".join(effects), (st.x + 14, st.y + 214), 14, settings.UI_TEXT)
        info = self.hover_part
        if info is not None:
            color = settings.RARITY_COLORS[info.rarity.value]
            draw_text(surface, f"{info.name}  [{info.rarity.value}]", (st.x + 14, st.y + 240), 15, color, True)
            ASSETS.blit_centered(surface, "parts", info.part_id, (st.right - 60, st.y + 226), (96, 48))
            desc = info.description if info.part_id in self.session.owned_parts else \
                "Locked - find it as a drop or buy it in the shop."
            for j, line in enumerate(wrap_text(desc, 13, st.w - 28)[:2]):
                draw_text(surface, line, (st.x + 14, st.y + 260 + j * 16), 13, settings.UI_TEXT_DIM)

        # Part rows
        for row, category in enumerate(PART_ORDER):
            owned = len(self.session.owned_in(category))
            total = len(self.session.library.by_category[category])
            draw_text(surface, f"{category.label.upper()}  {owned}/{total}", (PARTS_X, PARTS_Y + row * ROW_H + 6),
                      16, settings.UI_TEXT_DIM, True)
        draw_text(surface, "BLUEPRINTS", (20, 352), 12, settings.UI_TEXT_DIM, True)
        self.buttons.draw(surface)
        for row in self.rows.values():
            row.draw(surface)
        if self.message_time > 0:
            draw_text(surface, self.message, (PARTS_X, H - 40), 16, settings.UI_GOOD, True)
        elif self.dirty:
            draw_text(surface, "Unsaved changes - BACK discards them", (PARTS_X, H - 40), 15, settings.UI_ACCENT)

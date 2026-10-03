"""First-run tutorial: short goals shown during the first wave, plus one-time hints on menus.

Runs automatically until finished once (Profile.tutorial_done); SETTINGS -> REPLAY TUTORIAL resets it.
"""
from __future__ import annotations

from dataclasses import dataclass

import pygame

import settings
from ui.buttons import draw_panel
from ui.fonts import draw_text


@dataclass(frozen=True)
class Step:
    key: str
    pc: str
    mobile: str
    goal: float  # amount of progress needed (distance, shots, count...)


STEPS: tuple[Step, ...] = (
    Step("move", "Move with  W A S D", "Move with the LEFT stick", 260.0),
    Step("shoot", "Aim with the mouse, hold LEFT CLICK to shoot", "Drag the RIGHT stick to aim and shoot", 8.0),
    Step("dash", "Press SPACE to dash - you're invulnerable while dashing", "Tap DASH - you're invulnerable while dashing", 1.0),
    Step("grenade", "Press Q (or right click) to throw a grenade", "Tap NADE to throw a grenade", 1.0),
    Step("clear", "Clear the wave! Enemies drop money and new gun parts", "Clear the wave! Enemies drop money and new gun parts", 1.0),
)

# One-time hints shown the first time a screen is opened.
HINTS: dict[str, str] = {
    "intermission": "Between waves: SHOP buys parts & upgrades, WEAPON EDITOR builds your gun.",
    "editor": "Click parts to install them. Matching parts unlock SYNERGIES - hover a part to see which.",
    "shop": "Level a synergy weapon to Lv.8 here and it can EVOLVE into a legendary gun.",
    "wave_clear": "Pick one upgrade. Each can only be taken a few times per run.",
}


class Tutorial:
    def __init__(self, mobile: bool) -> None:
        self.mobile = mobile
        self.index: int = 0
        self.progress: float = 0.0
        self.done_flash: float = 0.0

    @property
    def finished(self) -> bool:
        return self.index >= len(STEPS)

    @property
    def step(self) -> Step | None:
        return None if self.finished else STEPS[self.index]

    def report(self, key: str, amount: float = 1.0) -> None:
        """Feed progress for a goal (`move` distance, `shoot` shots, `dash`, `grenade`, `clear`)."""
        step = self.step
        if step is None or step.key != key:
            return
        self.progress += amount
        if self.progress >= step.goal:
            self.index += 1
            self.progress = 0.0
            self.done_flash = 0.6

    def update(self, dt: float) -> None:
        self.done_flash = max(0.0, self.done_flash - dt)

    def draw(self, surface: pygame.Surface) -> None:
        step = self.step
        if step is None:
            return
        w = surface.get_width()
        rect = pygame.Rect(w // 2 - 330, 128, 660, 58)
        draw_panel(surface, rect, border=settings.UI_ACCENT if self.done_flash <= 0 else settings.UI_GOOD, alpha=225)
        draw_text(surface, f"TUTORIAL {self.index + 1}/{len(STEPS)}", (rect.x + 14, rect.y + 8), 12,
                  settings.UI_ACCENT, True)
        draw_text(surface, step.mobile if self.mobile else step.pc, (rect.centerx, rect.y + 34), 17,
                  settings.UI_TEXT, True, "center")
        if step.goal > 1:
            frac = min(1.0, self.progress / step.goal)
            pygame.draw.rect(surface, (40, 44, 56), (rect.x + 14, rect.bottom - 6, rect.w - 28, 3))
            pygame.draw.rect(surface, settings.UI_ACCENT, (rect.x + 14, rect.bottom - 6, int((rect.w - 28) * frac), 3))


def draw_hint(surface: pygame.Surface, text: str) -> None:
    """A one-line tip at the bottom of a menu screen."""
    w, h = surface.get_size()
    rect = pygame.Rect(w // 2 - 420, h - 128, 840, 40)
    draw_panel(surface, rect, border=settings.UI_ACCENT, alpha=235)
    draw_text(surface, "TIP  " + text, rect.center, 15, settings.UI_TEXT, True, "center")

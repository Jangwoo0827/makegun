"""Reusable UI widgets."""
from __future__ import annotations

from typing import Callable

import pygame

import settings
from ui.fonts import draw_text, get_font

Color = tuple[int, int, int]


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, color: Color = settings.UI_PANEL,
               border: Color = settings.UI_BORDER, radius: int = 8, alpha: int = 255) -> None:
    if alpha < 255:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*color, alpha), panel.get_rect(), border_radius=radius)
        surface.blit(panel, rect.topleft)
    else:
        pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 2, border_radius=radius)


def wrap_text(text: str, size: int, max_width: int) -> list[str]:
    font = get_font(size)
    words = text.split()
    lines: list[str] = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        if font.size(test)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


class Button:
    def __init__(self, rect: pygame.Rect | tuple[int, int, int, int], text: str,
                 on_click: Callable[[], None] | None = None, *, font_size: int = 20,
                 accent: Color = settings.UI_ACCENT, enabled: bool = True,
                 selected: bool = False, subtext: str = "", hotkey: int | None = None) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.text: str = text
        self.on_click = on_click
        self.font_size: int = font_size
        self.accent: Color = accent
        self.enabled: bool = enabled
        self.selected: bool = selected
        self.subtext: str = subtext
        self.hotkey: int | None = hotkey
        self.hovered: bool = False

    def handle_event(self, event: pygame.event.Event, sound: Callable[[], None] | None = None) -> bool:
        triggered = False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            triggered = True
        elif event.type == pygame.KEYDOWN and self.hotkey is not None and event.key == self.hotkey:
            triggered = True
        if triggered and self.enabled:
            if sound:
                sound()
            if self.on_click:
                self.on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        hovered = self.hovered or self.rect.collidepoint(pygame.mouse.get_pos())
        if not self.enabled:
            bg, border, fg = (28, 30, 38), (55, 58, 70), (90, 94, 108)
        elif self.selected:
            bg, border, fg = tuple(int(c * 0.35) for c in self.accent), self.accent, (255, 255, 255)
        elif hovered:
            bg, border, fg = settings.UI_PANEL_LIGHT, self.accent, (255, 255, 255)
        else:
            bg, border, fg = settings.UI_PANEL, settings.UI_BORDER, settings.UI_TEXT
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)  # type: ignore[arg-type]
        pygame.draw.rect(surface, border, self.rect, 2 if not self.selected else 3, border_radius=6)  # type: ignore[arg-type]
        if self.subtext:
            draw_text(surface, self.text, (self.rect.centerx, self.rect.centery - 8), self.font_size, fg,
                      bold=True, anchor="center")
            draw_text(surface, self.subtext, (self.rect.centerx, self.rect.centery + 11), 13,
                      self.accent if self.enabled else fg, anchor="center")
        else:
            draw_text(surface, self.text, self.rect.center, self.font_size, fg, bold=True, anchor="center")


class ButtonGroup:
    def __init__(self) -> None:
        self.buttons: list[Button] = []

    def add(self, button: Button) -> Button:
        self.buttons.append(button)
        return button

    def clear(self) -> None:
        self.buttons.clear()

    def handle_event(self, event: pygame.event.Event, sound: Callable[[], None] | None = None) -> bool:
        for b in list(self.buttons):
            if b.handle_event(event, sound):
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        for b in self.buttons:
            b.draw(surface)

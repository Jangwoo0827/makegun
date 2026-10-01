"""A horizontally scrolling row of buttons (mouse wheel, drag-free arrows, scrollbar)."""
from __future__ import annotations

from typing import Callable

import pygame

import settings
from ui.buttons import Button
from ui.fonts import draw_text

ARROW_W: int = 22
SCROLL_SPEED: float = 14.0  # smoothing factor


class ScrollRow:
    def __init__(self, rect: pygame.Rect, item_w: int, gap: int = 6) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.viewport: pygame.Rect = pygame.Rect(rect.x + ARROW_W + 4, rect.y, rect.w - 2 * (ARROW_W + 4), rect.h)
        self.item_w: int = item_w
        self.gap: int = gap
        self.items: list[Button] = []
        self.scroll: float = 0.0
        self.target: float = 0.0

    # ----------------------------------------------------------------- items
    def set_items(self, items: list[Button]) -> None:
        self.items = items
        self.target = min(self.target, self.max_scroll)
        self.scroll = min(self.scroll, self.max_scroll)
        self._layout()

    @property
    def content_w(self) -> int:
        n = len(self.items)
        return n * self.item_w + max(0, n - 1) * self.gap

    @property
    def max_scroll(self) -> float:
        return float(max(0, self.content_w - self.viewport.w))

    @property
    def scrollable(self) -> bool:
        return self.max_scroll > 0

    def ensure_visible(self, index: int, instant: bool = False) -> None:
        left = index * (self.item_w + self.gap)
        right = left + self.item_w
        if left < self.target:
            self.target = left
        elif right > self.target + self.viewport.w:
            self.target = right - self.viewport.w
        self.target = max(0.0, min(self.max_scroll, self.target))
        if instant:
            self.scroll = self.target
            self._layout()

    def scroll_by(self, dx: float) -> None:
        self.target = max(0.0, min(self.max_scroll, self.target + dx))

    def _layout(self) -> None:
        for i, b in enumerate(self.items):
            b.rect.x = int(self.viewport.x + i * (self.item_w + self.gap) - self.scroll)
            b.rect.y = self.viewport.y
            b.rect.w = self.item_w
            b.rect.h = self.viewport.h

    def _arrow_rects(self) -> tuple[pygame.Rect, pygame.Rect]:
        left = pygame.Rect(self.rect.x, self.rect.y, ARROW_W, self.rect.h)
        right = pygame.Rect(self.rect.right - ARROW_W, self.rect.y, ARROW_W, self.rect.h)
        return left, right

    # ---------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event, sound: Callable[[], None] | None = None) -> bool:
        step = (self.item_w + self.gap) * 2
        if event.type == pygame.MOUSEWHEEL:
            if self.scrollable and self.rect.collidepoint(pygame.mouse.get_pos()):
                delta = event.x if event.x else -event.y
                self.scroll_by(delta * (self.item_w + self.gap))
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            left, right = self._arrow_rects()
            if self.scrollable and left.collidepoint(event.pos):
                self.scroll_by(-step)
                return True
            if self.scrollable and right.collidepoint(event.pos):
                self.scroll_by(step)
                return True
            if not self.viewport.collidepoint(event.pos):
                return False
        if event.type == pygame.MOUSEMOTION:
            for b in self.items:
                b.hovered = self.viewport.collidepoint(event.pos) and b.rect.collidepoint(event.pos)
            return False
        for b in self.items:
            if b.handle_event(event, sound):
                return True
        return False

    def hovered_index(self, pos: tuple[int, int]) -> int | None:
        if not self.viewport.collidepoint(pos):
            return None
        for i, b in enumerate(self.items):
            if b.rect.collidepoint(pos):
                return i
        return None

    # ---------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        if abs(self.target - self.scroll) > 0.5:
            self.scroll += (self.target - self.scroll) * min(1.0, SCROLL_SPEED * dt)
        else:
            self.scroll = self.target
        self._layout()

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        old_clip = surface.get_clip()
        surface.set_clip(self.viewport)
        for b in self.items:
            if b.rect.right >= self.viewport.left and b.rect.left <= self.viewport.right:
                b.draw(surface)
        surface.set_clip(old_clip)
        if not self.scrollable:
            return
        left, right = self._arrow_rects()
        for rect, glyph, active in ((left, "<", self.target > 0), (right, ">", self.target < self.max_scroll)):
            color = settings.UI_ACCENT if active else settings.UI_BORDER
            pygame.draw.rect(surface, settings.UI_PANEL, rect, border_radius=4)
            pygame.draw.rect(surface, color, rect, 1, border_radius=4)
            draw_text(surface, glyph, rect.center, 18, color, True, "center")
        # thin scrollbar under the row
        bar_y = self.viewport.bottom + 3
        pygame.draw.line(surface, (40, 44, 56), (self.viewport.x, bar_y), (self.viewport.right, bar_y), 3)
        frac = self.viewport.w / self.content_w
        thumb_w = max(24, int(self.viewport.w * frac))
        thumb_x = self.viewport.x + int((self.viewport.w - thumb_w) * (self.scroll / self.max_scroll))
        pygame.draw.line(surface, settings.UI_ACCENT, (thumb_x, bar_y), (thumb_x + thumb_w, bar_y), 3)

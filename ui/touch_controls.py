"""On-screen touch controls for phones/tablets (web build).

Enabled when the player picks MOBILE on the device screen (Options.input_mode); never auto-detected.
- Left half: floating MOVE joystick.
- Right half: floating AIM joystick. Holding it aims and fires.
- Buttons: DASH, GRENADE, RELOAD, SWITCH weapon, PAUSE.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

import settings
from ui.fonts import draw_text

STICK_RADIUS: float = 85.0
DEADZONE: float = 0.18
Color = tuple[int, int, int]


@dataclass
class TouchButton:
    name: str
    label: str
    center: tuple[int, int]
    radius: int
    color: Color

    def hit(self, pos: tuple[float, float]) -> bool:
        return math.hypot(pos[0] - self.center[0], pos[1] - self.center[1]) <= self.radius * 1.15


@dataclass
class Stick:
    origin: pygame.Vector2
    pos: pygame.Vector2

    @property
    def vector(self) -> pygame.Vector2:
        d = self.pos - self.origin
        length = d.length()
        if length / STICK_RADIUS < DEADZONE:
            return pygame.Vector2()
        if length > STICK_RADIUS:
            d.scale_to_length(STICK_RADIUS)
        return d / STICK_RADIUS


class TouchControls:
    def __init__(self) -> None:
        self.active: bool = False
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        self.buttons: list[TouchButton] = [
            TouchButton("dash", "DASH", (w - 90, h - 300), 54, (120, 200, 255)),
            TouchButton("grenade", "NADE", (w - 200, h - 380), 46, (255, 140, 80)),
            TouchButton("reload", "R", (w - 90, h - 430), 36, (200, 200, 210)),
            TouchButton("switch", "SWAP", (w - 200, h - 500), 36, (255, 196, 64)),
            TouchButton("pause", "II", (w - 44, 44), 30, (200, 200, 210)),
        ]
        self._sticks: dict[int, tuple[str, Stick]] = {}  # finger id -> ("move"/"aim", stick)
        self._taps: list[str] = []
        self.last_aim: pygame.Vector2 = pygame.Vector2(1, 0)

    # ---------------------------------------------------------------- state
    @property
    def move(self) -> pygame.Vector2:
        for role, stick in self._sticks.values():
            if role == "move":
                return stick.vector
        return pygame.Vector2()

    @property
    def aim(self) -> pygame.Vector2 | None:
        """Aim direction while the aim stick is held past the deadzone, else None."""
        for role, stick in self._sticks.values():
            if role == "aim":
                v = stick.vector
                if v.length_squared() > 0:
                    self.last_aim = v.normalize()
                    return self.last_aim
        return None

    def take_taps(self) -> list[str]:
        taps, self._taps = self._taps, []
        return taps

    def reset(self) -> None:
        self._sticks.clear()
        self._taps.clear()

    # --------------------------------------------------------------- events
    @staticmethod
    def _screen_pos(event: pygame.event.Event) -> tuple[float, float]:
        return event.x * settings.SCREEN_WIDTH, event.y * settings.SCREEN_HEIGHT

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if the event belongs to the touch controls (callers should then ignore it)."""
        if not self.active:
            return False
        if event.type == pygame.FINGERDOWN:
            pos = self._screen_pos(event)
            for b in self.buttons:
                if b.hit(pos):
                    self._taps.append(b.name)
                    return True
            role = "move" if pos[0] < settings.SCREEN_WIDTH * 0.45 else "aim"
            # one finger per stick
            self._sticks = {f: s for f, s in self._sticks.items() if s[0] != role}
            self._sticks[event.finger_id] = (role, Stick(pygame.Vector2(pos), pygame.Vector2(pos)))
            return True
        if event.type == pygame.FINGERMOTION:
            entry = self._sticks.get(event.finger_id)
            if entry is not None:
                entry[1].pos.update(self._screen_pos(event))
            return True
        if event.type == pygame.FINGERUP:
            self._sticks.pop(event.finger_id, None)
            return True
        # Touch also produces synthetic mouse events (event.touch == True): swallow them in-game.
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
            return bool(getattr(event, "touch", False))
        return False

    # ----------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface, cooldowns: dict[str, float]) -> None:
        if not self.active:
            return
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        # sticks (ghosts when idle)
        held = {role: stick for role, stick in self._sticks.values()}
        ghosts = {"move": (170, settings.SCREEN_HEIGHT - 190), "aim": (settings.SCREEN_WIDTH - 420, settings.SCREEN_HEIGHT - 190)}
        for role, ghost in ghosts.items():
            stick = held.get(role)
            origin = stick.origin if stick else pygame.Vector2(ghost)
            knob = origin + stick.vector * STICK_RADIUS if stick else origin
            alpha = 120 if stick else 50
            color = (120, 200, 255) if role == "move" else (255, 120, 120)
            pygame.draw.circle(overlay, (*color, alpha // 2), origin, STICK_RADIUS)
            pygame.draw.circle(overlay, (*color, alpha), origin, STICK_RADIUS, 3)
            pygame.draw.circle(overlay, (*color, alpha + 60), knob, 34)
        for b in self.buttons:
            cd = cooldowns.get(b.name, 0.0)
            pygame.draw.circle(overlay, (*b.color, 70 if cd > 0 else 110), b.center, b.radius)
            pygame.draw.circle(overlay, (*b.color, 200), b.center, b.radius, 3)
            if cd > 0:  # remaining cooldown as a dark pie slice
                steps = max(2, int(32 * cd))
                pts = [b.center] + [(b.center[0] + math.cos(-math.pi / 2 + math.tau * cd * i / steps) * b.radius,
                                     b.center[1] + math.sin(-math.pi / 2 + math.tau * cd * i / steps) * b.radius)
                                    for i in range(steps + 1)]
                pygame.draw.polygon(overlay, (0, 0, 0, 150), pts)
        surface.blit(overlay, (0, 0))
        for b in self.buttons:
            draw_text(surface, b.label, b.center, 18 if b.radius > 40 else 14, (255, 255, 255), True, "center")
        if "move" not in held:
            draw_text(surface, "MOVE", ghosts["move"], 14, (180, 220, 255), True, "center")
        if "aim" not in held:
            draw_text(surface, "AIM + FIRE", ghosts["aim"], 14, (255, 180, 180), True, "center")

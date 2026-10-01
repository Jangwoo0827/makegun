"""Draws a weapon from its parts using pygame primitives (no image assets needed)."""
from __future__ import annotations

import math

import pygame

from systems.assets import ASSETS
from weapons.weapon_parts import PartCategory, WeaponPart

GUN_IMAGE_SCALE: int = 8  # gun part images are authored at 8x their in-game slot size
RECEIVER_IMAGE_HEIGHT: float = 1.9  # receiver image = body + grip below it, in receiver heights

Point = tuple[float, float]
Color = tuple[int, int, int]


def _shade(color: Color, factor: float) -> Color:
    return tuple(max(0, min(255, int(c * factor))) for c in color)  # type: ignore[return-value]


def _col(raw: object, fallback: Color) -> Color:
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return (int(raw[0]), int(raw[1]), int(raw[2]))
    return fallback


def part_color(part: WeaponPart, fallback: Color) -> Color:
    """The display color declared in a part's visual data."""
    return _col(part.visual.get("color"), fallback)


class GunShape:
    """Local-space geometry of a gun, grip at origin, pointing toward +x."""

    def __init__(self, parts: dict[PartCategory, WeaponPart]) -> None:
        rv = parts[PartCategory.RECEIVER].visual
        bv = parts[PartCategory.BARREL].visual
        mv = parts[PartCategory.MAGAZINE].visual
        self.receiver_len: float = float(rv.get("length", 30))
        self.receiver_h: float = float(rv.get("height", 14))
        self.receiver_color: Color = _col(rv.get("color"), (150, 150, 160))
        self.barrel_len: float = float(bv.get("length", 20))
        self.barrel_w: float = float(bv.get("width", 6))
        self.barrel_count: int = int(bv.get("count", 1))
        self.mag_shape: str = str(mv.get("shape", "rect"))
        self.mag_w: float = float(mv.get("w", 8))
        self.mag_h: float = float(mv.get("h", 12))
        self.trigger_color: Color = _col(parts[PartCategory.TRIGGER].visual.get("color"), (200, 200, 200))
        self.ammo_color: Color = _col(parts[PartCategory.AMMO].visual.get("color"), (255, 230, 120))
        self.mod_color: Color = _col(parts[PartCategory.MODIFIER].visual.get("color"), (70, 70, 80))

    @property
    def rx0(self) -> float:
        return -self.receiver_len * 0.3

    @property
    def rx1(self) -> float:
        return self.receiver_len * 0.7

    @property
    def muzzle_x(self) -> float:
        return self.rx1 + self.barrel_len


def _transform(points: list[Point], origin: Point, angle: float, scale: float, flip: bool) -> list[Point]:
    ca, sa = math.cos(angle), math.sin(angle)
    out: list[Point] = []
    for x, y in points:
        x *= scale
        y *= -scale if flip else scale
        out.append((origin[0] + x * ca - y * sa, origin[1] + x * sa + y * ca))
    return out


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def draw_gun(surface: pygame.Surface, parts: dict[PartCategory, WeaponPart], origin: Point,
             angle: float, scale: float = 1.0, outline: bool = True) -> Point:
    """Draw the gun and return the muzzle position in surface coordinates."""
    g = GunShape(parts)
    flip = math.cos(angle) < 0  # keep magazine pointing down when aiming left
    h2 = g.receiver_h / 2

    def image(category: PartCategory, x0: float, y0: float, x1: float, y1: float) -> bool:
        """Draw assets/images/gun/<part_id>.png stretched over a local-space slot. False if no image."""
        part_id = parts[category].part_id
        if not ASSETS.has("gun", part_id):
            return False
        w, h = max(1, int((x1 - x0) * scale)), max(1, int((y1 - y0) * scale))
        img = ASSETS.get("gun", part_id, (w, h))
        if img is None:
            return False
        if flip:
            img = pygame.transform.flip(img, False, True)
        img = pygame.transform.rotate(img, -math.degrees(angle))
        center = _transform([((x0 + x1) / 2, (y0 + y1) / 2)], origin, angle, scale, flip)[0]
        surface.blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))
        return True

    def draw_magazine() -> None:
        mx = g.receiver_len * 0.18
        if image(PartCategory.MAGAZINE, mx, h2 - 1, mx + g.mag_w, h2 - 1 + g.mag_h):
            pass
        elif g.mag_shape == "drum":
            center = _transform([(mx + g.mag_w / 2, h2 + g.mag_h / 2)], origin, angle, scale, flip)[0]
            pygame.draw.circle(surface, (70, 74, 84), center, g.mag_w / 2 * scale)
            if outline:
                pygame.draw.circle(surface, (30, 32, 38), center, g.mag_w / 2 * scale, max(1, int(scale)))
        elif g.mag_shape == "box":
            poly(_rect(mx, h2 - 1, mx + g.mag_w, h2 + g.mag_h), (80, 86, 70))
        else:
            poly([(mx, h2 - 1), (mx + g.mag_w, h2 - 1), (mx + g.mag_w + 2, h2 + g.mag_h),
                  (mx + 2, h2 + g.mag_h)], (70, 74, 84))

    receiver_img = ASSETS.has("gun", parts[PartCategory.RECEIVER].part_id)

    def poly(points: list[Point], color: Color, edge: bool = True) -> None:
        pts = _transform(points, origin, angle, scale, flip)
        pygame.draw.polygon(surface, color, pts)
        if edge and outline:
            pygame.draw.polygon(surface, _shade(color, 0.45), pts, max(1, int(scale)))

    if not receiver_img:  # a receiver image already contains its grip
        # Grip
        poly(_rect(g.rx0 + 2, h2 - 2, g.rx0 + 2 + g.receiver_h * 0.55, h2 + g.receiver_h * 0.9),
             _shade(g.receiver_color, 0.7))
        # Trigger guard / trigger
        tx = g.rx0 + g.receiver_h * 0.7
        poly(_rect(tx, h2 - 1, tx + 6, h2 + 6), g.trigger_color)
    if not receiver_img:
        draw_magazine()
    # Barrel(s)
    offsets = [0.0] if g.barrel_count <= 1 else [
        (i - (g.barrel_count - 1) / 2) * g.barrel_w * 1.3 for i in range(g.barrel_count)]
    for off in offsets:
        bw2 = g.barrel_w / 2
        if not image(PartCategory.BARREL, g.rx1 - 2, off - bw2, g.muzzle_x, off + bw2):
            poly(_rect(g.rx1 - 2, off - bw2, g.muzzle_x, off + bw2), (95, 100, 112))
    # Receiver body
    if not image(PartCategory.RECEIVER, g.rx0, -h2, g.rx1, -h2 + g.receiver_h * RECEIVER_IMAGE_HEIGHT):
        poly(_rect(g.rx0, -h2, g.rx1, h2), g.receiver_color)
    if receiver_img:  # magazine plugs in over the receiver art
        draw_magazine()
    if not receiver_img:  # shape-drawn guns show ammo/modifier as color accents
        poly(_rect(g.rx0 + 3, -1.5, g.rx1 - 3, 1.5), g.mod_color, edge=False)
        poly(_rect(g.rx1 - 9, -h2 + 2, g.rx1 - 4, -h2 + 6), g.ammo_color, edge=False)

    return _transform([(g.muzzle_x, 0.0)], origin, angle, scale, flip)[0]


def muzzle_distance(parts: dict[PartCategory, WeaponPart], scale: float = 1.0) -> float:
    return GunShape(parts).muzzle_x * scale

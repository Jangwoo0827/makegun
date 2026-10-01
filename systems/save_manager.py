"""Run save/load (JSON). One save slot holding the current run.

Phases:
  "intermission" - saved between waves; continue returns to the intermission hub
  "wave_clear"   - saved while choosing an upgrade; continue re-offers the same choices
  "wave"         - saved mid-wave; continue restarts that wave with current money/HP/parts
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from typing import Any

import settings
from entities.player_stats import PlayerStats
from game.session import RunSession
from systems.upgrade_manager import UpgradeManager
from weapons.weapon_builder import STARTER_PRESETS
from weapons.weapon_data import PartLibrary
from weapons.weapon_parts import PART_ORDER, PartCategory

SAVE_VERSION: int = 1
SAVE_PATH: str = os.path.join(settings.BASE_DIR, "save_run.json")


class SaveManager:
    def __init__(self, path: str = SAVE_PATH) -> None:
        self.path = path

    # ----------------------------------------------------------------- query
    def has_save(self) -> bool:
        return self.peek() is not None

    def peek(self) -> dict[str, Any] | None:
        """Read the save header without building a session; None if missing/corrupt."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return None
        return data

    def delete(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass

    # ------------------------------------------------------------------ save
    def save(self, session: RunSession, phase: str, resume_wave: int) -> bool:
        p = session.player
        data: dict[str, Any] = {
            "version": SAVE_VERSION,
            "phase": phase,
            "resume_wave": resume_wave,
            "money": session.money,
            "money_earned": session.money_earned,
            "kills": session.kills,
            "hp": p.hp,
            "owned_parts": sorted(session.owned_parts),
            "stats": asdict(session.stats),
            "slots_unlocked": session.slots_unlocked,
            "current_weapon": p.current,
            "weapons": [{"name": w.name, "level": w.level,
                         "parts": {c.value: w.parts[c].part_id for c in PART_ORDER}} for w in p.weapons],
            "upgrades_taken": [u.upgrade_id for u in session.upgrades_taken],
            "pending_upgrades": [u.upgrade_id for u in session.pending_upgrades],
            "last_wave_reward": session.last_wave_reward,
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1)
            os.replace(tmp, self.path)  # atomic: never leaves a half-written save
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------ load
    def load(self, library: PartLibrary, upgrades: UpgradeManager) -> tuple[RunSession, str] | None:
        data = self.peek()
        if data is None:
            return None
        try:
            return self._build_session(data, library, upgrades), str(data.get("phase", "wave"))
        except (KeyError, TypeError, ValueError):
            return None

    def _build_session(self, data: dict[str, Any], library: PartLibrary,
                       upgrades: UpgradeManager) -> RunSession:
        session = RunSession(library, upgrades, STARTER_PRESETS[0])
        session.money = int(data["money"])
        session.money_earned = int(data.get("money_earned", 0))
        session.kills = int(data.get("kills", 0))
        # Ignore parts that no longer exist in weapons.json (data may change between versions).
        session.owned_parts = {pid for pid in data["owned_parts"] if pid in library.parts} | library.starter_ids()

        valid = {f.name for f in fields(PlayerStats)}
        for key, value in data.get("stats", {}).items():
            if key in valid:
                setattr(session.stats, key, type(getattr(session.stats, key))(value))

        weapons = []
        for wd in data["weapons"][: settings.MAX_WEAPON_SLOTS]:
            part_ids: dict[PartCategory, str] = {}
            for category in PART_ORDER:
                pid = wd["parts"].get(category.value)
                if pid in library.parts and library.get(pid).category == category:
                    part_ids[category] = pid
            weapon = session.builder.build(part_ids, wd.get("name"))
            weapon.level = max(1, int(wd.get("level", 1)))
            weapons.append(weapon)
        if not weapons:
            raise ValueError("save has no weapons")
        player = session.player
        player.weapons = weapons
        player.current = min(int(data.get("current_weapon", 0)), len(weapons) - 1)
        session.slots_unlocked = max(len(weapons), int(data.get("slots_unlocked", 1)))

        by_id = {u.upgrade_id: u for u in upgrades.upgrades}
        session.upgrades_taken = [by_id[u] for u in data.get("upgrades_taken", []) if u in by_id]
        session.pending_upgrades = [by_id[u] for u in data.get("pending_upgrades", []) if u in by_id]
        session.last_wave_reward = int(data.get("last_wave_reward", 0))
        session.resume_wave = int(data["resume_wave"])
        session.wave_reached = session.resume_wave

        player.refresh_weapons()
        for w in weapons:
            w.refill(1.0)
        player.hp = max(1.0, min(float(data.get("hp", player.max_hp)), player.max_hp))
        return session

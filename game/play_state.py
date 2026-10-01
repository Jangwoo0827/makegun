"""GAME state: the actual combat in the arena."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from entities.enemy import Enemy
from entities.pickup import Pickup, PickupKind
from entities.player import BUFF_DEFS
from game.camera import Camera
from game.state import GameState, StateID
from game.world import World
from systems.collision import CollisionSystem
from systems.combat import CombatSystem
from systems.loot_manager import LootManager
from systems.spawn_manager import SpawnManager
from systems.wave_manager import WaveManager, WavePhase
from ui.hud import HUD
from weapons.weapon_parts import PartCategory
from weapons.gun_renderer import part_color

if TYPE_CHECKING:
    from game.game import Game

DEATH_DELAY: float = 1.2


class PlayState(GameState):
    state_id = StateID.GAME

    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        session = game.require_session()
        self.session = session
        self.world = World(session.player)
        session.player.pos = self.world.center()
        self.camera = Camera()
        self.camera.shake_enabled = game.options.screen_shake
        self.camera.snap_to(session.player.pos)
        self.world.effects.show_numbers = game.options.damage_numbers
        self.spawner = SpawnManager(game.enemy_db, self.world.walls)
        self.waves = WaveManager(self.spawner)
        self.combat = CombatSystem(self.world, game.sound, self.camera.shake)
        self.collisions = CollisionSystem(self.combat.on_bullet_hit_enemy, self.combat.on_bullet_hit_wall,
                                          self._on_player_hit, self._on_pickup)
        self.loot = LootManager(game.library)
        self.hud = HUD()
        self.death_timer: float = 0.0
        self.awaiting_next_wave: bool = False
        self._start_wave()

    # ------------------------------------------------------------ lifecycle
    def on_enter(self) -> None:
        pygame.mouse.set_visible(False)
        self.camera.shake_enabled = self.game.options.screen_shake
        self.world.effects.show_numbers = self.game.options.damage_numbers
        self.session.player.refresh_weapons()
        if self.awaiting_next_wave:
            self.awaiting_next_wave = False
            self._start_wave()

    def on_exit(self) -> None:
        pygame.mouse.set_visible(True)

    def _start_wave(self) -> None:
        for w in self.session.weapons:
            w.refill(1.0)
        self.world.pickups.clear()
        self.world.enemy_bullets.clear()
        self.waves.start_next_wave()
        self.session.wave_reached = self.waves.wave
        self.game.sound.play("boss" if self.waves.is_boss_wave else "wave")

    # --------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        player = self.session.player
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.push(StateID.PAUSE)
            elif event.key == pygame.K_r:
                if player.weapon.start_reload():
                    self.game.sound.play("reload")
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                player.switch_weapon(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEWHEEL and len(player.weapons) > 1:
            player.switch_weapon((player.current - event.y) % len(player.weapons))

    # --------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        world, player = self.world, self.session.player
        if not player.alive:
            self.death_timer += dt
            dt *= 0.3
            if self.death_timer >= DEATH_DELAY:
                self.game.push(StateID.GAME_OVER)
                return

        # Input -> player
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])
        mouse_screen = pygame.mouse.get_pos()
        mouse_world = self.camera.screen_to_world(mouse_screen)
        if player.alive:
            player.update(dt, move)
            player.aim_at(mouse_world)
            trigger = pygame.mouse.get_pressed()[0]
            weapon = player.weapon
            was_reloading = weapon.reloading
            for shot in weapon.update(dt, trigger):
                color = part_color(weapon.part(PartCategory.AMMO), (255, 230, 120))
                self.combat.fire(player.muzzle_pos(), player.angle, weapon.stats, shot, color, sweep_from=player.pos)
                player.muzzle_flash = 0.06
            if weapon.reloading and not was_reloading:
                self.game.sound.play("reload")

        # Spawning
        if self.waves.phase == WavePhase.ACTIVE:
            for e in self.spawner.update(dt, player.pos, len(world.enemies)):
                self._add_enemy(e)

        # Entities
        for b in world.bullets:
            b.update(dt)
        for b in world.enemy_bullets:
            b.update(dt)
        for e in world.enemies:
            actions = e.update(dt, player.pos)
            world.enemy_bullets.extend(actions.bullets)
            for etype in actions.summons:
                self._add_enemy(self.spawner.spawn_now(etype, player.pos, near=e.pos))
                self.waves.register_extra()
        for p in world.pickups:
            p.update(dt, player.pos, 110.0)

        self.collisions.update(player, world.enemies, world.bullets, world.enemy_bullets,
                               world.pickups, world.walls)

        # Deaths & cleanup
        for e in world.enemies:
            if not e.alive:
                self._on_enemy_killed(e)
        world.enemies = [e for e in world.enemies if e.alive]
        world.bullets = [b for b in world.bullets if b.alive]
        world.enemy_bullets = [b for b in world.enemy_bullets if b.alive]
        world.pickups = [p for p in world.pickups if p.alive]
        if len(world.bullets) > 1500:
            world.bullets = world.bullets[-1500:]

        world.effects.update(dt)
        self.camera.update(dt, player.pos, mouse_world - player.pos)

        if player.alive and self.waves.update(dt, len(world.enemies)):
            self._on_wave_cleared()

    def _add_enemy(self, enemy: Enemy) -> None:
        self.world.enemies.append(enemy)
        self.world.effects.burst(enemy.pos, enemy.data.color, 10, 120, 0.4, 3)
        if enemy.is_boss:
            self.camera.shake(16)
            self.game.sound.play("boss")

    def _on_enemy_killed(self, enemy: Enemy) -> None:
        s = self.session
        s.kills += 1
        self.waves.register_kill()
        self.world.effects.burst(enemy.pos, enemy.data.color, 16 if not enemy.is_boss else 80,
                                 220 if not enemy.is_boss else 420, 0.5, 4)
        self.camera.shake(20 if enemy.is_boss else 3)
        self.game.sound.play("enemy_die", 40)
        luck = s.player.weapon.stats.luck
        self.world.pickups.extend(self.loot.roll_drops(enemy, luck, s.owned_parts, self.waves.wave))

    def _on_wave_cleared(self) -> None:
        s = self.session
        for p in self.world.pickups:  # auto-collect leftovers
            self._on_pickup(p, quiet=True)
        self.world.pickups.clear()
        self.world.enemy_bullets.clear()
        reward = self.waves.clear_reward()
        s.earn(reward)
        s.last_wave_reward = reward
        s.pending_upgrades = s.upgrade_manager.roll_choices(self.waves.wave, 3, s.stats.luck)
        self.awaiting_next_wave = True
        self.game.sound.play("wave")
        self.game.push(StateID.WAVE_CLEAR)

    # ------------------------------------------------------------ callbacks
    def _on_player_hit(self, damage: float, source: pygame.Vector2) -> None:
        player = self.session.player
        if player.take_damage(damage):
            self.camera.shake(9)
            self.game.sound.play("hurt")
            self.world.effects.burst(player.pos, (255, 80, 80), 12, 200, 0.4, 3)
            self.world.effects.float_text(player.pos - pygame.Vector2(0, 26), f"-{int(damage)}", (255, 90, 90))

    def _on_pickup(self, pickup: Pickup, quiet: bool = False) -> None:
        s = self.session
        fx = self.world.effects
        pos = pickup.pos - pygame.Vector2(0, 18)
        if pickup.kind == PickupKind.MONEY:
            s.earn(int(pickup.value))
            if not quiet:
                fx.float_text(pos, f"+${int(pickup.value)}", (255, 214, 90), 14)
        elif pickup.kind == PickupKind.HEALTH:
            s.player.heal(pickup.value)
            fx.float_text(pos, f"+{int(pickup.value)} HP", (90, 240, 120))
        elif pickup.kind == PickupKind.AMMO:
            for w in s.weapons:
                w.refill(pickup.value)
            fx.float_text(pos, "AMMO", (120, 200, 255))
        elif pickup.kind == PickupKind.BUFF and pickup.buff:
            s.player.add_buff(pickup.buff)
            fx.float_text(pos, BUFF_DEFS[pickup.buff][0], (255, 120, 255), 18)
        elif pickup.kind == PickupKind.PART and pickup.part_id:
            part = s.library.get(pickup.part_id)
            if s.own_part(part.part_id):
                fx.float_text(pos, f"NEW PART: {part.name}", (255, 170, 40), 20)
            else:
                s.earn(50)
                fx.float_text(pos, "+$50 (duplicate)", (255, 214, 90))
        if not quiet:
            self.game.sound.play("pickup", 25)

    # ----------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface) -> None:
        offset = self.camera.offset
        self.world.draw(surface, offset)
        player = self.session.player
        self.hud.draw(surface, player, self.session.money, self.waves, self.world.boss())
        if self.game.top is self:
            self.hud.draw_crosshair(surface, pygame.mouse.get_pos(), player.weapon.stats.spread,
                                    player.weapon.charge_ratio if player.weapon.charge > 0 else 0.0)
        if not player.alive:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((120, 0, 0, min(140, int(self.death_timer * 140))))
            surface.blit(overlay, (0, 0))


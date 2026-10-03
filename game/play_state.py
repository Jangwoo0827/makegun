"""GAME state: the actual combat in the arena."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from entities.boss_types import Warden
from entities.enemy import Enemy, EnemyActions
from entities.grenade import Grenade
from entities.pickup import Pickup, PickupKind
from entities.player import BUFF_DEFS
from game.camera import Camera
from game.state import GameState, StateID
from game.world import World
from systems.collision import CollisionSystem, line_of_sight
from systems.affixes import affix_death_actions
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

    def __init__(self, game: "Game", start_wave: bool = True) -> None:
        super().__init__(game)
        session = game.require_session()
        self.session = session
        self.world = World(session.player, session.stage)
        session.player.pos = self.world.center()
        self.camera = Camera()
        self.camera.shake_enabled = game.options.screen_shake
        self.camera.snap_to(session.player.pos)
        self.world.effects.show_numbers = game.options.damage_numbers
        self.spawner = SpawnManager(game.enemy_db, self.world.walls)
        self.waves = WaveManager(self.spawner, session.stage)
        self.grenades: list[Grenade] = []
        self._pulse: bool = False  # touch: alternates the trigger so semi-auto guns keep firing
        self.stats_timer: float = 0.0
        self.combat = CombatSystem(self.world, game.sound, self.camera.shake)
        self.collisions = CollisionSystem(self.combat.on_bullet_hit_enemy, self.combat.on_bullet_hit_wall,
                                          self._on_player_hit, self._on_pickup)
        self.loot = LootManager(game.library)
        self.hud = HUD()
        self.death_timer: float = 0.0
        self.waves.wave = session.resume_wave
        self.awaiting_next_wave: bool = not start_wave
        if start_wave:
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
        self.game.touch.reset()

    def _start_wave(self) -> None:
        for w in self.session.weapons:
            w.refill(1.0)
        self.world.pickups.clear()
        self.world.enemy_bullets.clear()
        self.waves.start_next_wave()
        self.session.wave_reached = self.waves.wave
        self.game.save_run()  # autosave at wave start
        self.game.sound.play("boss" if self.waves.is_boss_wave else "wave")

    # --------------------------------------------------------------- events
    def handle_event(self, event: pygame.event.Event) -> None:
        player = self.session.player
        if self.game.touch.handle_event(event):
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.game.push(StateID.PAUSE)
            elif event.key == pygame.K_r:
                if player.weapon.start_reload():
                    self.game.sound.play("reload")
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                player.switch_weapon(event.key - pygame.K_1)
            elif event.key in (pygame.K_SPACE, pygame.K_LSHIFT):
                self._dash()
            elif event.key == pygame.K_q:
                self._throw_grenade()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._throw_grenade()
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
        touch = self.game.touch
        if touch.active:
            for tap in touch.take_taps():
                self._on_touch_button(tap)
                if self.game.top is not self:
                    return
            move = touch.move
            aim = touch.aim
            aim_dir = aim if aim is not None else self._assist_aim()
            mouse_world = player.pos + aim_dir * 200
            if aim is not None and player.weapon.stats.fire_mode in ("single", "burst"):
                self._pulse = not self._pulse  # tap-fire semi-auto guns at their fire rate
                trigger = self._pulse
            else:
                trigger = aim is not None
        else:
            move = self._keyboard_move()
            mouse_world = self.camera.screen_to_world(pygame.mouse.get_pos())
            trigger = pygame.mouse.get_pressed()[0]
        if player.alive:
            player.update(dt, move)
            player.aim_at(mouse_world)
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
        self.combat.update_homing(dt)
        for b in world.enemy_bullets:
            b.update(dt)
        drones = sum(1 for e in world.enemies if e.alive and e.enemy_type == "drone")
        for e in list(world.enemies):
            if isinstance(e, Warden):
                e.drones_alive = drones
            e.has_los = line_of_sight(e.pos, player.pos, world.inner_walls)
            self._apply_enemy_actions(e, e.update(dt, player.pos))
        for g in self.grenades:
            g.update(dt)
            if g.exploded:
                self._explode_grenade(g)
        self.grenades = [g for g in self.grenades if not g.exploded]
        for p in world.pickups:
            p.update(dt, player.pos, settings.PLAYER_PICKUP_RADIUS * self.session.stats.pickup_radius_multiplier)

        self.collisions.update(player, world.enemies, world.bullets, world.enemy_bullets,
                               world.pickups, world.walls)

        # Deaths & cleanup
        for e in list(world.enemies):
            if not e.alive:
                self._on_enemy_killed(e)
                self._apply_enemy_actions(e, e.on_death())
                self._apply_enemy_actions(e, affix_death_actions(e))
        world.enemies = [e for e in world.enemies if e.alive]
        world.bullets = [b for b in world.bullets if b.alive]
        world.enemy_bullets = [b for b in world.enemy_bullets if b.alive]
        world.pickups = [p for p in world.pickups if p.alive]
        if len(world.bullets) > 1500:
            world.bullets = world.bullets[-1500:]

        world.effects.update(dt)
        self.camera.update(dt, player.pos, mouse_world - player.pos)
        self.stats_timer -= dt
        if self.stats_timer <= 0:
            self.stats_timer = 0.5
            self._track_run_stats()

        if player.alive and self.waves.update(dt, len(world.enemies)):
            self._on_wave_cleared()

    # ---------------------------------------------------------------- skills
    @staticmethod
    def _keyboard_move() -> pygame.Vector2:
        keys = pygame.key.get_pressed()
        return pygame.Vector2(keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w])

    def _assist_aim(self) -> pygame.Vector2:
        """Touch: when the aim stick is idle, face the nearest visible enemy (without firing)."""
        p = self.session.player
        best, best_d = None, 650.0 ** 2
        for e in self.world.enemies:
            d = (e.pos - p.pos).length_squared()
            if e.alive and d < best_d and e.has_los:
                best, best_d = e, d
        if best is not None and best_d > 1:
            return (best.pos - p.pos).normalize()
        return p.aim_dir

    def _on_touch_button(self, name: str) -> None:
        player = self.session.player
        if name == "dash":
            self._dash()
        elif name == "grenade":
            self._throw_grenade()
        elif name == "reload":
            if player.weapon.start_reload():
                self.game.sound.play("reload")
        elif name == "switch" and len(player.weapons) > 1:
            player.switch_weapon((player.current + 1) % len(player.weapons))
        elif name == "pause":
            self.game.push(StateID.PAUSE)

    def _dash(self) -> None:
        player = self.session.player
        move = self.game.touch.move if self.game.touch.active else self._keyboard_move()
        if player.try_dash(move):
            self.game.profile.add_stat("total_dashes")
            self.world.effects.burst(player.pos, (120, 200, 255), 10, 160, 0.3, 3)
            self.game.sound.play("click")

    def grenade_damage(self) -> float:
        p = self.session.player
        base = max(settings.GRENADE_MIN_DAMAGE, p.weapon.stats.dps * settings.GRENADE_DPS_FACTOR)
        return base * p.stats.grenade_damage_multiplier

    def _throw_grenade(self) -> None:
        player = self.session.player
        if player.try_grenade():
            if self.game.touch.active:
                target = player.pos + player.aim_dir * settings.GRENADE_RANGE * 0.75
            else:
                target = self.camera.screen_to_world(pygame.mouse.get_pos())
            self.grenades.append(Grenade(player.pos, target, self.grenade_damage(), settings.GRENADE_RADIUS))

    def _explode_grenade(self, g: Grenade) -> None:
        alive_before = {e.uid for e in self.world.enemies if e.alive}
        self.combat.explode(g.pos, g.radius, g.damage, self.session.player.weapon.stats.lifesteal)
        killed = sum(1 for e in self.world.enemies if e.uid in alive_before and not e.alive)
        self.session.bump("best_grenade_kills", killed)

    def _track_run_stats(self) -> None:
        """Feed per-run achievement counters and pop toasts for new unlocks."""
        s = self.session
        s.bump("run_kills", s.kills)
        s.bump("run_money_peak", s.money)
        s.bump("run_parts", len(s.owned_parts))
        s.bump("run_synergies", max(len(w.stats.synergies) for w in s.weapons))
        self.game.profile.max_stat("best_grenade_kills", s.run_stats.get("best_grenade_kills", 0))
        for a in self.game.profile.check_achievements(s.run_stats):
            self.game.toast(f"ACHIEVEMENT: {a.name}", f"{a.description}  (+{a.reward} cores)")

    def _apply_enemy_actions(self, enemy: Enemy, actions: EnemyActions) -> None:
        world, player = self.world, self.session.player
        world.enemy_bullets.extend(actions.bullets)
        for etype in actions.summons:
            self._add_enemy(self.spawner.spawn_now(etype, player.pos, near=enemy.pos))
            self.waves.register_extra()
        for pos, radius, damage in actions.explosions:
            world.effects.explosion(pos, radius)
            self.camera.shake(10)
            self.game.sound.play("explosion", 60)
            if (player.pos - pos).length() <= radius + player.radius:
                self._on_player_hit(damage, pos)
        for pos, radius, fraction in actions.heals:
            for other in world.enemies:
                if other.alive and (other.pos - pos).length() <= radius:
                    other.hp = min(other.max_hp, other.hp + other.max_hp * fraction)
                    world.effects.burst(other.pos, (120, 255, 140), 4, 80, 0.3, 2)

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
        profile = self.game.profile
        profile.add_stat("total_kills")
        if enemy.is_boss:
            s.boss_kills += 1
            profile.add_stat("total_boss_kills")
        if enemy.affix is not None:
            profile.add_stat("total_affix_kills")
        self.world.effects.burst(enemy.pos, enemy.data.color, 16 if not enemy.is_boss else 80,
                                 220 if not enemy.is_boss else 420, 0.5, 4)
        self.camera.shake(20 if enemy.is_boss else 3)
        self.game.sound.play("enemy_die", 40)
        if s.stats.heal_on_kill > 0:
            s.player.heal(s.stats.heal_on_kill)
        luck = s.player.weapon.stats.luck
        self.world.pickups.extend(self.loot.roll_drops(enemy, luck, s.owned_parts, self.waves.wave))

    def _on_wave_cleared(self) -> None:
        s = self.session
        for p in self.world.pickups:  # auto-collect leftovers
            self._on_pickup(p, quiet=True)
        self.world.pickups.clear()
        self.world.enemy_bullets.clear()
        if s.stats.wave_heal > 0:
            s.player.heal(s.player.max_hp * s.stats.wave_heal)
        if self.waves.is_final_wave:
            self.world.pickups.clear()
            s.earn(self.waves.clear_reward())
            self._track_run_stats()
            self.game.sound.play("wave")
            self.game.finish_run(victory=True)
            self.game.push(StateID.STAGE_CLEAR)
            return
        reward = self.waves.clear_reward()
        s.earn(reward)
        s.last_wave_reward = reward
        s.pending_upgrades = s.upgrade_manager.roll_choices(self.waves.wave, 3, s.stats.luck, s.upgrades_taken)
        self.awaiting_next_wave = True
        self.game.save_run()
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
            amount = int(round(pickup.value * s.stats.money_multiplier))
            s.earn(amount)
            if not quiet:
                fx.float_text(pos, f"+${amount}", (255, 214, 90), 14)
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
        for g in self.grenades:
            g.draw(surface, offset)
        player = self.session.player
        self.hud.draw(surface, player, self.session.money, self.waves, self.world.boss())
        touch = self.game.touch
        if touch.active:
            touch.draw(surface, {"dash": player.dash_cooldown / max(0.01, player.dash_cooldown_max),
                                 "grenade": player.grenade_cooldown / max(0.01, player.grenade_cooldown_max)})
        else:
            self.hud.draw_skills(surface, player)
        if self.game.top is self and not touch.active:
            self.hud.draw_crosshair(surface, pygame.mouse.get_pos(), player.weapon.stats.spread,
                                    player.weapon.charge_ratio if player.weapon.charge > 0 else 0.0)
        if not player.alive:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((120, 0, 0, min(140, int(self.death_timer * 140))))
            surface.blit(overlay, (0, 0))


import math
import sys
from dataclasses import dataclass

import pygame


SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
FRAME_MS = 1000 / FPS
GROUND_Y = 620

BG_COLOR = (245, 245, 242)
TEXT_COLOR = (22, 22, 24)
SUBTEXT_COLOR = (70, 70, 78)
P1_COLOR = (90, 170, 255)
P2_COLOR = (255, 120, 120)
HURTBOX_COLOR = (80, 220, 120)
HITBOX_COLOR = (255, 90, 90)
CHARGE_COLOR = (255, 190, 70)
HEAVY_CHARGE_COLOR = (255, 120, 70)
PARRY_COLOR = (255, 235, 120)
DASH_COLOR = (120, 255, 190)
CENTER_LINE_COLOR = (185, 185, 190)
FLASH_COLOR = (255, 255, 255)

PLAYER_WIDTH = 28
PLAYER_HEIGHT = 56
STAGE_PADDING = 40
MIN_SEPARATION = 20

FORWARD_SPEED = 120 / FPS
BACKWARD_SPEED = 95 / FPS
ACCELERATION = 850 / (FPS * FPS)
DECELERATION = 1300 / (FPS * FPS)
STOP_THRESHOLD = 12 / FPS

LIGHT_RANGE = 44
LIGHT_HEIGHT = 18
MEDIUM_RANGE = 70
MEDIUM_HEIGHT = 22
HEAVY_RANGE = 96
HEAVY_HEIGHT = 28

HITSTOP_FRAMES = 7
ROUND_RESET_FRAMES = 90

LIGHT_STARTUP_FRAMES = 5
LIGHT_ACTIVE_FRAMES = 4
LIGHT_RECOVERY_FRAMES = 11

MEDIUM_STARTUP_FRAMES = 8
MEDIUM_ACTIVE_FRAMES = 5
MEDIUM_RECOVERY_FRAMES = 17

HEAVY_STARTUP_FRAMES = 10
HEAVY_ACTIVE_FRAMES = 6
HEAVY_RECOVERY_FRAMES = 20

CHARGE_MEDIUM_MS = 300
CHARGE_HEAVY_MS = 650
PARRY_STARTUP_FRAMES = 3
PARRY_ACTIVE_FRAMES = 7
PARRY_RECOVERY_FRAMES = 18
PUNISH_WINDOW_FRAMES = 12

MEDIUM_FEINT_FRAMES = 7
HEAVY_FEINT_FRAMES = 9
MEDIUM_FEINT_MOVE_MULT = 0.85
HEAVY_FEINT_MOVE_MULT = 0.75

MEDIUM_HOLD_MOVE_MULT = 0.55
HEAVY_HOLD_MOVE_MULT = 0.35
PRE_CHARGE_MOVE_MULT = 0.7

DASH_STARTUP_FRAMES = 2
DASH_TRAVEL_FRAMES = 6
DASH_TOTAL_DISTANCE = 88
DASH_SPEED = DASH_TOTAL_DISTANCE / DASH_TRAVEL_FRAMES
DASH_BRAKE_LOCKOUT_FRAMES = 5
DASH_BRAKE_SPEED_MULT = 0.45
DASH_AVAILABLE_FRAMES = 18

CLOSE_PUSHBACK = 58
MID_PUSHBACK = 96
FAR_PUSHBACK = 138

HEAD_RADIUS = 8
BODY_LENGTH = 18
ARM_LENGTH = 14
FOREARM_LENGTH = 14
THIGH_LENGTH = 16
CALF_LENGTH = 16
STICK_WIDTH = 4
SWORD_LENGTH = 32
SWORD_WIDTH = 7
SWORD_GUARD = 8
SWORD_HANDLE = 10
SWORD_COLOR = (255, 255, 255, 185)
SWORD_GLOW_COLOR = (255, 255, 255, 70)
SWORD_EDGE_COLOR = (245, 245, 250, 220)
SHEATH_COLOR = (18, 18, 20)
SHEATH_EDGE_COLOR = (70, 70, 78)


@dataclass(frozen=True)
class Pose:
    crouch: float = 0.0
    lean: float = 0.0
    shoulder_forward: float = 0.0
    shoulder_up: float = 0.0
    rear_arm_bend: float = 0.0
    lead_arm_bend: float = 0.0
    lead_leg_forward: float = 0.0
    rear_leg_forward: float = 0.0
    stretch: float = 0.0
    head_forward: float = 0.0
    sword_angle: float = 0.0
    sword_offset: float = 0.0


@dataclass(frozen=True)
class AttackProfile:
    name: str
    startup: int
    active: int
    recovery: int
    reach: int
    height: int
    parry_result: str


LIGHT_PROFILE = AttackProfile(
    name="LIGHT",
    startup=LIGHT_STARTUP_FRAMES,
    active=LIGHT_ACTIVE_FRAMES,
    recovery=LIGHT_RECOVERY_FRAMES,
    reach=LIGHT_RANGE,
    height=LIGHT_HEIGHT,
    parry_result="punish",
)

MEDIUM_PROFILE = AttackProfile(
    name="MEDIUM",
    startup=MEDIUM_STARTUP_FRAMES,
    active=MEDIUM_ACTIVE_FRAMES,
    recovery=MEDIUM_RECOVERY_FRAMES,
    reach=MEDIUM_RANGE,
    height=MEDIUM_HEIGHT,
    parry_result="punish",
)

HEAVY_PROFILE = AttackProfile(
    name="HEAVY",
    startup=HEAVY_STARTUP_FRAMES,
    active=HEAVY_ACTIVE_FRAMES,
    recovery=HEAVY_RECOVERY_FRAMES,
    reach=HEAVY_RANGE,
    height=HEAVY_HEIGHT,
    parry_result="pushback",
)


def charge_tier(charge_ms: float) -> str:
    if charge_ms >= CHARGE_HEAVY_MS:
        return "HEAVY"
    if charge_ms >= CHARGE_MEDIUM_MS:
        return "MEDIUM"
    return "LIGHT"


def approach(current: float, target: float, accel: float) -> float:
    if current < target:
        return min(current + accel, target)
    if current > target:
        return max(current - accel, target)
    return current


def blend(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend_pose(a: Pose, b: Pose, t: float) -> Pose:
    return Pose(
        crouch=blend(a.crouch, b.crouch, t),
        lean=blend(a.lean, b.lean, t),
        shoulder_forward=blend(a.shoulder_forward, b.shoulder_forward, t),
        shoulder_up=blend(a.shoulder_up, b.shoulder_up, t),
        rear_arm_bend=blend(a.rear_arm_bend, b.rear_arm_bend, t),
        lead_arm_bend=blend(a.lead_arm_bend, b.lead_arm_bend, t),
        lead_leg_forward=blend(a.lead_leg_forward, b.lead_leg_forward, t),
        rear_leg_forward=blend(a.rear_leg_forward, b.rear_leg_forward, t),
        stretch=blend(a.stretch, b.stretch, t),
        head_forward=blend(a.head_forward, b.head_forward, t),
        sword_angle=blend(a.sword_angle, b.sword_angle, t),
        sword_offset=blend(a.sword_offset, b.sword_offset, t),
    )


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class Player:
    def __init__(self, player_id: int, x: int, color: tuple[int, int, int], controls: dict[str, int]):
        self.player_id = player_id
        self.spawn_x = x
        self.color = color
        self.controls = controls
        self.rounds = 0
        self.reset_for_round()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), PLAYER_WIDTH, PLAYER_HEIGHT)

    @property
    def center_x(self) -> float:
        return self.x + PLAYER_WIDTH / 2

    def reset_for_round(self) -> None:
        self.x = float(self.spawn_x)
        self.y = float(GROUND_Y - PLAYER_HEIGHT)
        self.velocity_x = 0.0
        self.facing = 1
        self.alive = True

        self.state = "IDLE"
        self.state_frame = 0

        self.move_dir = 0
        self.left_pressed = False
        self.right_pressed = False
        self.confirm_pressed = False
        self.charge_held = False
        self.parry_pressed = False

        self.charge_ms = 0.0
        self.was_charging = False
        self.charge_release_tier = "LIGHT"

        self.attack_profile: AttackProfile | None = None
        self.attack_frame = 0
        self.attack_resolved = False

        self.parry_startup_frames = 0
        self.parry_active_frames = 0
        self.parry_recovery_frames = 0

        self.punish_window_frames = 0
        self.feint_lockout_frames = 0
        self.feint_move_mult = 1.0

        self.dash_available_frames = 0
        self.dash_startup_frames = 0
        self.dash_travel_frames = 0
        self.dash_direction = 0
        self.dash_brake_lockout_frames = 0

    def capture_input(self, keys: pygame.key.ScancodeWrapper, pressed_once: set[int]) -> None:
        left = keys[self.controls["left"]]
        right = keys[self.controls["right"]]
        self.left_pressed = self.controls["left"] in pressed_once
        self.right_pressed = self.controls["right"] in pressed_once

        if left and not right:
            self.move_dir = -1
        elif right and not left:
            self.move_dir = 1
        else:
            self.move_dir = 0

        self.charge_held = keys[self.controls["charge"]]
        self.confirm_pressed = self.controls["confirm"] in pressed_once
        self.parry_pressed = self.controls["parry"] in pressed_once

    def update_facing(self, opponent: "Player") -> None:
        self.facing = 1 if opponent.center_x > self.center_x else -1

    def distance_to(self, opponent: "Player") -> float:
        if self.center_x <= opponent.center_x:
            return opponent.x - (self.x + PLAYER_WIDTH)
        return self.x - (opponent.x + PLAYER_WIDTH)

    def current_charge_tier(self) -> str:
        return charge_tier(self.charge_ms)

    def can_start_attack(self) -> bool:
        return (
            self.alive
            and self.attack_profile is None
            and self.parry_startup_frames <= 0
            and self.parry_active_frames <= 0
            and self.parry_recovery_frames <= 0
            and self.feint_lockout_frames <= 0
            and self.dash_startup_frames <= 0
            and self.dash_travel_frames <= 0
            and self.dash_brake_lockout_frames <= 0
        )

    def can_start_parry(self) -> bool:
        return (
            self.alive
            and self.attack_profile is None
            and self.parry_startup_frames <= 0
            and self.parry_active_frames <= 0
            and self.parry_recovery_frames <= 0
            and self.feint_lockout_frames <= 0
            and self.dash_startup_frames <= 0
            and self.dash_travel_frames <= 0
            and self.dash_brake_lockout_frames <= 0
        )

    def start_attack(self, profile: AttackProfile) -> None:
        self.attack_profile = profile
        self.attack_frame = 0
        self.attack_resolved = False
        self.charge_ms = 0.0
        self.was_charging = False
        self.state = f"{profile.name}_STARTUP"
        self.state_frame = 0

    def start_feint(self, tier: str) -> None:
        self.charge_ms = 0.0
        self.was_charging = False
        if tier == "HEAVY":
            self.feint_lockout_frames = HEAVY_FEINT_FRAMES
            self.feint_move_mult = HEAVY_FEINT_MOVE_MULT
        else:
            self.feint_lockout_frames = MEDIUM_FEINT_FRAMES
            self.feint_move_mult = MEDIUM_FEINT_MOVE_MULT
        self.state = f"{tier}_FEINT"
        self.state_frame = 0

    def start_parry(self) -> None:
        self.parry_startup_frames = PARRY_STARTUP_FRAMES
        self.parry_active_frames = 0
        self.parry_recovery_frames = 0
        self.state = "PARRY_STARTUP"
        self.state_frame = 0

    def grant_dash(self) -> None:
        self.dash_available_frames = DASH_AVAILABLE_FRAMES
        self.state = "PARRY_SUCCESS"
        self.state_frame = 0

    def start_dash(self) -> None:
        self.dash_available_frames = 0
        self.dash_startup_frames = DASH_STARTUP_FRAMES
        self.dash_travel_frames = DASH_TRAVEL_FRAMES
        self.dash_direction = self.facing
        self.state = "DASH_STARTUP"
        self.state_frame = 0

    def brake_dash(self) -> None:
        self.dash_startup_frames = 0
        self.dash_travel_frames = 0
        self.velocity_x = 0.0
        self.dash_brake_lockout_frames = DASH_BRAKE_LOCKOUT_FRAMES
        self.state = "DASH_BRAKE"
        self.state_frame = 0

    def start_punish_window(self) -> None:
        self.punish_window_frames = PUNISH_WINDOW_FRAMES
        self.state = "PUNISH_WINDOW"
        self.state_frame = 0

    def is_parry_active(self) -> bool:
        return self.parry_active_frames > 0

    def is_attack_active(self) -> bool:
        return (
            self.attack_profile is not None
            and self.attack_profile.startup < self.attack_frame <= self.attack_profile.startup + self.attack_profile.active
        )

    def get_hitbox(self) -> pygame.Rect | None:
        if not self.is_attack_active() or self.attack_profile is None:
            return None
        reach = self.attack_profile.reach
        if self.facing == 1:
            hitbox_x = int(self.x + PLAYER_WIDTH)
        else:
            hitbox_x = int(self.x - reach)
        hitbox_y = int(self.y + (PLAYER_HEIGHT // 2 - self.attack_profile.height // 2))
        return pygame.Rect(hitbox_x, hitbox_y, reach, self.attack_profile.height)

    def knock_out(self) -> None:
        self.alive = False
        self.attack_profile = None
        self.attack_frame = 0
        self.charge_ms = 0.0
        self.velocity_x = 0.0
        self.parry_startup_frames = 0
        self.parry_active_frames = 0
        self.parry_recovery_frames = 0
        self.feint_lockout_frames = 0
        self.punish_window_frames = 0
        self.dash_available_frames = 0
        self.dash_startup_frames = 0
        self.dash_travel_frames = 0
        self.dash_brake_lockout_frames = 0
        self.state = "DEAD"
        self.state_frame = 0

    def get_move_scalar(self) -> float:
        if self.feint_lockout_frames > 0:
            return self.feint_move_mult
        if self.charge_held:
            tier = self.current_charge_tier()
            if tier == "HEAVY":
                return HEAVY_HOLD_MOVE_MULT
            if tier == "MEDIUM":
                return MEDIUM_HOLD_MOVE_MULT
            return PRE_CHARGE_MOVE_MULT
        if self.dash_brake_lockout_frames > 0:
            return DASH_BRAKE_SPEED_MULT
        return 1.0

    def get_target_velocity(self) -> float:
        if self.move_dir == 0:
            return 0.0
        move_forward = self.move_dir == self.facing
        base_speed = FORWARD_SPEED if move_forward else BACKWARD_SPEED
        return self.move_dir * base_speed * self.get_move_scalar()

    def apply_ground_movement(self) -> None:
        target_velocity = self.get_target_velocity()
        accel = ACCELERATION if abs(target_velocity) > abs(self.velocity_x) else DECELERATION
        self.velocity_x = approach(self.velocity_x, target_velocity, accel)
        if abs(target_velocity) < 1e-6 and abs(self.velocity_x) < STOP_THRESHOLD:
            self.velocity_x = 0.0
        self.x += self.velocity_x

    def advance_attack(self) -> None:
        assert self.attack_profile is not None
        self.attack_frame += 1
        self.state_frame += 1
        profile = self.attack_profile
        if self.attack_frame <= profile.startup:
            self.state = f"{profile.name}_STARTUP"
            return
        if self.attack_frame <= profile.startup + profile.active:
            self.state = f"{profile.name}_ACTIVE"
            return
        if self.attack_frame <= profile.startup + profile.active + profile.recovery:
            self.state = f"{profile.name}_RECOVERY"
            return
        self.attack_profile = None
        self.attack_frame = 0
        self.attack_resolved = False
        self.state = "IDLE"
        self.state_frame = 0

    def update(self, opponent: "Player") -> None:
        self.update_facing(opponent)

        if not self.alive:
            self.state = "DEAD"
            self.state_frame += 1
            return

        if self.confirm_pressed and (self.dash_startup_frames > 0 or self.dash_travel_frames > 0):
            self.brake_dash()
            return

        if self.dash_startup_frames > 0:
            self.dash_startup_frames -= 1
            self.velocity_x = 0.0
            self.state = "DASH_STARTUP"
            self.state_frame += 1
            return

        if self.dash_travel_frames > 0:
            self.x += self.dash_direction * DASH_SPEED
            self.dash_travel_frames -= 1
            self.state = "DASH_TRAVEL"
            self.state_frame += 1
            return

        if self.dash_brake_lockout_frames > 0:
            self.dash_brake_lockout_frames -= 1
            self.apply_ground_movement()
            self.state = "DASH_BRAKE"
            self.state_frame += 1
            return

        if self.parry_pressed and self.can_start_parry():
            self.start_parry()
            return

        if self.attack_profile is not None:
            self.advance_attack()
            return

        if self.parry_startup_frames > 0:
            self.parry_startup_frames -= 1
            if self.parry_startup_frames == 0:
                self.parry_active_frames = PARRY_ACTIVE_FRAMES
                self.parry_recovery_frames = PARRY_RECOVERY_FRAMES
            self.state = "PARRY_STARTUP"
            self.state_frame += 1
            return

        if self.parry_active_frames > 0:
            self.parry_active_frames -= 1
            self.parry_recovery_frames = max(0, self.parry_recovery_frames - 1)
            self.state = "PARRY_ACTIVE"
            self.state_frame += 1
            return

        if self.parry_recovery_frames > 0:
            self.parry_recovery_frames -= 1
            self.state = "PARRY_RECOVERY"
            self.state_frame += 1
            return

        if self.punish_window_frames > 0:
            self.punish_window_frames -= 1
            if self.confirm_pressed:
                self.state = "PUNISH_CONFIRM"
            else:
                self.state = "PUNISH_WINDOW"
            self.state_frame += 1
            return

        if self.dash_available_frames > 0:
            toward_pressed = (self.facing == 1 and self.right_pressed) or (self.facing == -1 and self.left_pressed)
            if toward_pressed:
                self.start_dash()
                return
            self.dash_available_frames -= 1
            self.state = "DASH_READY"
            self.state_frame += 1
            return

        if self.feint_lockout_frames > 0:
            self.feint_lockout_frames -= 1
            self.apply_ground_movement()
            self.state = f"{self.charge_release_tier}_FEINT"
            self.state_frame += 1
            return

        if self.confirm_pressed and self.can_start_attack():
            tier = self.current_charge_tier()
            if tier == "HEAVY":
                self.start_attack(HEAVY_PROFILE)
            elif tier == "MEDIUM":
                self.start_attack(MEDIUM_PROFILE)
            else:
                self.start_attack(LIGHT_PROFILE)
            return

        if self.charge_held:
            self.charge_ms += FRAME_MS
            self.was_charging = True
            self.apply_ground_movement()
            self.state = f"{self.current_charge_tier()}_CHARGE"
            self.state_frame += 1
            return

        if self.was_charging:
            self.charge_release_tier = charge_tier(max(self.charge_ms, CHARGE_MEDIUM_MS))
            self.start_feint(self.charge_release_tier)
            return

        self.apply_ground_movement()
        self.state = "MOVE" if self.move_dir != 0 or abs(self.velocity_x) > 0 else "IDLE"
        self.state_frame += 1

    def clamp_to_stage(self) -> None:
        self.x = max(STAGE_PADDING, min(self.x, SCREEN_WIDTH - STAGE_PADDING - PLAYER_WIDTH))

    def attack_progress(self) -> float:
        if self.attack_profile is None:
            return 0.0
        total = self.attack_profile.startup + self.attack_profile.active + self.attack_profile.recovery
        return clamp01(self.attack_frame / max(1, total))

    def get_pose(self) -> Pose:
        neutral = Pose(
            crouch=0.0,
            lean=0.0,
            shoulder_forward=0.0,
            shoulder_up=0.0,
            rear_arm_bend=0.3,
            lead_arm_bend=0.6,
            lead_leg_forward=1.0,
            rear_leg_forward=-0.8,
            stretch=0.0,
            head_forward=0.0,
            sword_angle=-0.9,
            sword_offset=-1.5,
        )
        walk_cycle = math.sin(self.x * 0.18 + self.state_frame * 0.55)
        walk_pose = Pose(
            crouch=0.5,
            lean=0.05 * (1 if self.move_dir == self.facing else -1 if self.move_dir != 0 else 0),
            shoulder_forward=1.2 * walk_cycle,
            shoulder_up=0.3,
            rear_arm_bend=-0.5 * walk_cycle,
            lead_arm_bend=0.5 * walk_cycle,
            lead_leg_forward=4.0 * walk_cycle,
            rear_leg_forward=-4.0 * walk_cycle,
            stretch=0.6,
            head_forward=0.8 * walk_cycle,
            sword_angle=-1.05 + 0.15 * walk_cycle,
            sword_offset=-1.0 * walk_cycle,
        )

        pose = neutral
        if self.state == "MOVE":
            pose = blend_pose(neutral, walk_pose, clamp01(abs(self.velocity_x) / max(FORWARD_SPEED, BACKWARD_SPEED)))

        if self.state.endswith("CHARGE"):
            tier = self.current_charge_tier()
            if tier == "HEAVY":
                return Pose(
                    crouch=7.0,
                    lean=0.22,
                    shoulder_forward=6.0,
                    shoulder_up=1.5,
                    rear_arm_bend=-1.8,
                    lead_arm_bend=2.8,
                    lead_leg_forward=2.0,
                    rear_leg_forward=-3.0,
                    stretch=1.5,
                    head_forward=2.0,
                    sword_angle=-1.9,
                    sword_offset=-6.0,
                )
            if tier == "MEDIUM":
                return Pose(
                    crouch=4.0,
                    lean=0.15,
                    shoulder_forward=4.0,
                    shoulder_up=1.0,
                    rear_arm_bend=-1.0,
                    lead_arm_bend=1.8,
                    lead_leg_forward=1.5,
                    rear_leg_forward=-2.0,
                    stretch=0.8,
                    head_forward=1.2,
                    sword_angle=-1.45,
                    sword_offset=-3.0,
                )

        if self.state == "PARRY_STARTUP":
            return Pose(crouch=3.0, lean=-0.08, shoulder_forward=-2.0, shoulder_up=4.0, rear_arm_bend=2.4, lead_arm_bend=2.4, sword_angle=-0.15, sword_offset=5.0)
        if self.state == "PARRY_ACTIVE":
            return Pose(crouch=1.0, lean=-0.16, shoulder_forward=-4.0, shoulder_up=6.0, rear_arm_bend=3.4, lead_arm_bend=3.0, sword_angle=0.2, sword_offset=7.0)
        if self.state == "PARRY_SUCCESS" or self.state == "DASH_READY":
            return Pose(crouch=2.0, lean=-0.1, shoulder_forward=-1.0, shoulder_up=5.0, rear_arm_bend=2.8, lead_arm_bend=2.6, sword_angle=-0.05, sword_offset=4.0)
        if self.state == "DASH_STARTUP":
            return Pose(crouch=5.0, lean=0.25, shoulder_forward=4.0, shoulder_up=-1.0, rear_arm_bend=-1.5, lead_arm_bend=1.0, lead_leg_forward=3.0, rear_leg_forward=-4.0, stretch=1.0, sword_angle=-1.35, sword_offset=-4.0)
        if self.state == "DASH_TRAVEL":
            dash_cycle = math.sin(self.state_frame * 1.3)
            return Pose(crouch=4.0, lean=0.35, shoulder_forward=8.0, shoulder_up=-2.0, rear_arm_bend=-2.0, lead_arm_bend=0.3, lead_leg_forward=5.0 + dash_cycle, rear_leg_forward=-5.0 - dash_cycle, stretch=2.2, head_forward=3.0, sword_angle=-1.25 + 0.05 * dash_cycle, sword_offset=-2.0)
        if self.state == "DASH_BRAKE":
            return Pose(crouch=6.0, lean=-0.28, shoulder_forward=-3.0, shoulder_up=2.0, rear_arm_bend=1.4, lead_arm_bend=2.4, lead_leg_forward=-2.0, rear_leg_forward=3.0, stretch=-0.5, head_forward=-1.0, sword_angle=-0.45, sword_offset=2.0)
        if self.state.endswith("_FEINT"):
            t = 1.0 - clamp01(self.feint_lockout_frames / max(1, HEAVY_FEINT_FRAMES))
            return blend_pose(
                Pose(crouch=4.0, lean=0.16, shoulder_forward=4.0, shoulder_up=0.5, rear_arm_bend=-0.5, lead_arm_bend=1.5, sword_angle=-1.2, sword_offset=-2.0),
                Pose(crouch=1.0, lean=-0.08, shoulder_forward=-1.0, shoulder_up=1.0, rear_arm_bend=0.8, lead_arm_bend=0.4, lead_leg_forward=-1.0, rear_leg_forward=1.0, sword_angle=-0.8, sword_offset=1.0),
                t,
            )
        if self.state == "PARRIED":
            return Pose(crouch=2.5, lean=-0.22, shoulder_forward=-5.0, shoulder_up=1.5, rear_arm_bend=-0.8, lead_arm_bend=-1.0, head_forward=-2.0, sword_angle=-2.2, sword_offset=-8.0)
        if self.state == "DEAD":
            return Pose(crouch=10.0, lean=0.6, shoulder_forward=6.0, shoulder_up=-3.0, rear_arm_bend=0.5, lead_arm_bend=0.5, lead_leg_forward=5.0, rear_leg_forward=2.0, stretch=-1.0, sword_angle=0.7, sword_offset=8.0)

        if self.attack_profile is not None:
            profile = self.attack_profile
            startup_end = profile.startup
            active_end = startup_end + profile.active
            if self.attack_frame <= startup_end:
                t = clamp01(self.attack_frame / max(1, startup_end))
                if profile.name == "LIGHT":
                    return blend_pose(
                        neutral,
                        Pose(
                            crouch=1.0,
                            lean=-0.06,
                            shoulder_forward=-3.0,
                            shoulder_up=0.5,
                            rear_arm_bend=1.0,
                            lead_arm_bend=1.8,
                            lead_leg_forward=0.5,
                            rear_leg_forward=-1.2,
                            stretch=0.2,
                            head_forward=-0.5,
                            sword_angle=-0.62,
                            sword_offset=-5.0,
                        ),
                        t,
                    )
                if profile.name == "MEDIUM":
                    return blend_pose(
                        neutral,
                        Pose(
                            crouch=2.5,
                            lean=-0.12,
                            shoulder_forward=-6.0,
                            shoulder_up=0.0,
                            rear_arm_bend=1.4,
                            lead_arm_bend=2.2,
                            lead_leg_forward=1.5,
                            rear_leg_forward=-2.0,
                            stretch=0.6,
                            head_forward=-1.0,
                            sword_angle=-0.88,
                            sword_offset=-9.0,
                        ),
                        t,
                    )
                return blend_pose(
                    neutral,
                    Pose(
                        crouch=4.0,
                        lean=-0.18,
                        shoulder_forward=-9.0,
                        shoulder_up=0.5,
                        rear_arm_bend=1.8,
                        lead_arm_bend=2.8,
                        lead_leg_forward=2.0,
                        rear_leg_forward=-3.0,
                        stretch=1.0,
                        head_forward=-1.5,
                        sword_angle=-1.08,
                        sword_offset=-13.0,
                    ),
                    t,
                )
            if self.attack_frame <= active_end:
                if profile.name == "LIGHT":
                    return Pose(crouch=0.0, lean=0.24, shoulder_forward=18.0, shoulder_up=-0.5, rear_arm_bend=-1.8, lead_arm_bend=-0.2, lead_leg_forward=2.5, rear_leg_forward=-1.5, stretch=1.0, head_forward=1.8, sword_angle=0.38, sword_offset=8.0)
                if profile.name == "MEDIUM":
                    return Pose(crouch=0.5, lean=0.32, shoulder_forward=24.0, shoulder_up=0.0, rear_arm_bend=-2.4, lead_arm_bend=-0.4, lead_leg_forward=3.8, rear_leg_forward=-2.8, stretch=1.8, head_forward=2.6, sword_angle=0.56, sword_offset=13.0)
                return Pose(crouch=1.0, lean=0.4, shoulder_forward=30.0, shoulder_up=0.5, rear_arm_bend=-3.0, lead_arm_bend=-0.6, lead_leg_forward=4.5, rear_leg_forward=-3.6, stretch=2.4, head_forward=3.2, sword_angle=0.72, sword_offset=18.0)
            recovery_total = profile.recovery
            t = clamp01((self.attack_frame - active_end) / max(1, recovery_total))
            return blend_pose(
                Pose(crouch=1.5, lean=0.12, shoulder_forward=8.0, shoulder_up=0.0, rear_arm_bend=-0.6, lead_arm_bend=0.8, lead_leg_forward=1.0, rear_leg_forward=-1.0, stretch=0.6, head_forward=0.8, sword_angle=0.18, sword_offset=5.0),
                neutral,
                t,
            )

        return pose


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("1SLASH Pygame Prototype")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.big_font = pygame.font.SysFont("consolas", 28, bold=True)

        self.p1 = Player(
            player_id=1,
            x=300,
            color=P1_COLOR,
            controls={
                "left": pygame.K_a,
                "right": pygame.K_d,
                "charge": pygame.K_j,
                "confirm": pygame.K_k,
                "parry": pygame.K_l,
            },
        )
        self.p2 = Player(
            player_id=2,
            x=920,
            color=P2_COLOR,
            controls={
                "left": pygame.K_LEFT,
                "right": pygame.K_RIGHT,
                "charge": pygame.K_KP1,
                "confirm": pygame.K_KP2,
                "parry": pygame.K_KP3,
            },
        )

        self.hitstop_frames = 0
        self.round_over_frames = 0
        self.winner_text = ""

    def run(self) -> None:
        while True:
            self.clock.tick(FPS)
            pressed_once = self.poll_events()
            keys = pygame.key.get_pressed()

            if self.round_over_frames > 0:
                self.round_over_frames -= 1
                if self.round_over_frames == 0:
                    self.start_new_round()
                self.draw()
                continue

            if self.hitstop_frames > 0:
                self.hitstop_frames -= 1
            else:
                self.p1.capture_input(keys, pressed_once)
                self.p2.capture_input(keys, pressed_once)

                self.p1.update(self.p2)
                self.p2.update(self.p1)

                self.resolve_punish_confirm()
                self.resolve_combat(self.p1, self.p2)
                self.resolve_combat(self.p2, self.p1)
                self.resolve_spacing()

                self.p1.clamp_to_stage()
                self.p2.clamp_to_stage()
                self.resolve_spacing()

            self.draw()

    def poll_events(self) -> set[int]:
        pressed_once: set[int] = set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                pressed_once.add(event.key)
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r:
                    self.start_new_round()
                    self.p1.rounds = 0
                    self.p2.rounds = 0
        return pressed_once

    def start_new_round(self) -> None:
        self.p1.reset_for_round()
        self.p2.reset_for_round()
        self.hitstop_frames = 0
        self.round_over_frames = 0
        self.winner_text = ""

    def get_distance_layer(self) -> str:
        gap = self.p1.distance_to(self.p2)
        if gap <= 55:
            return "POINT BLANK"
        if gap <= 90:
            return "EDGE RANGE"
        if gap <= 150:
            return "NEUTRAL PRESSURE"
        return "FAR"

    def resolve_combat(self, attacker: Player, defender: Player) -> None:
        hitbox = attacker.get_hitbox()
        if hitbox is None or attacker.attack_profile is None or attacker.attack_resolved or not defender.alive:
            return
        if not hitbox.colliderect(defender.rect):
            return

        if defender.is_parry_active():
            profile = attacker.attack_profile
            attacker.attack_profile = None
            attacker.attack_frame = 0
            attacker.attack_resolved = True
            attacker.parry_recovery_frames = 24
            attacker.state = "PARRIED"
            attacker.state_frame = 0

            if profile.parry_result == "pushback":
                defender.grant_dash()
                self.apply_pushback(attacker, defender)
            else:
                defender.start_punish_window()

            self.hitstop_frames = HITSTOP_FRAMES + 2
            return

        self.finish_round(attacker, defender, "CLEAN HIT")

    def resolve_punish_confirm(self) -> None:
        if self.p1.punish_window_frames > 0 and self.p1.confirm_pressed and self.can_punish_connect(self.p1, self.p2):
            self.finish_round(self.p1, self.p2, "PUNISH HIT")
            return
        if self.p2.punish_window_frames > 0 and self.p2.confirm_pressed and self.can_punish_connect(self.p2, self.p1):
            self.finish_round(self.p2, self.p1, "PUNISH HIT")

    def can_punish_connect(self, attacker: Player, defender: Player) -> bool:
        gap = attacker.distance_to(defender)
        return defender.alive and gap <= LIGHT_RANGE

    def resolve_spacing(self) -> None:
        left, right = (self.p1, self.p2) if self.p1.center_x <= self.p2.center_x else (self.p2, self.p1)
        min_right_x = left.x + PLAYER_WIDTH + MIN_SEPARATION
        if right.x < min_right_x:
            overlap = min_right_x - right.x
            if left.dash_travel_frames > 0:
                left.dash_travel_frames = 0
            if right.dash_travel_frames > 0:
                right.dash_travel_frames = 0
            left.x -= overlap / 2
            right.x += overlap / 2
            left.velocity_x = min(left.velocity_x, 0.0)
            right.velocity_x = max(right.velocity_x, 0.0)

    def apply_pushback(self, attacker: Player, defender: Player) -> None:
        distance = attacker.distance_to(defender)
        if distance <= 55:
            pushback = CLOSE_PUSHBACK
        elif distance <= 90:
            pushback = MID_PUSHBACK
        else:
            pushback = FAR_PUSHBACK

        half_push = pushback / 2
        if attacker.center_x <= defender.center_x:
            attacker.x -= half_push
            defender.x += half_push
        else:
            attacker.x += half_push
            defender.x -= half_push

    def finish_round(self, winner: Player, loser: Player, label: str) -> None:
        loser.knock_out()
        winner.rounds += 1
        self.winner_text = f"P{winner.player_id} {label}"
        self.round_over_frames = ROUND_RESET_FRAMES
        self.hitstop_frames = HITSTOP_FRAMES + 2

    def draw_afterimage(self, player: Player, body_color: tuple[int, int, int]) -> None:
        if player.state not in {"DASH_TRAVEL", "DASH_BRAKE"}:
            return
        for index, alpha_step in enumerate((0.45, 0.25, 0.12), start=1):
            offset = player.facing * -index * 10
            ghost_color = tuple(int(channel * (0.35 + alpha_step)) for channel in body_color)
            self.draw_stickman(player, ghost_color, x_offset=offset, y_offset=index, outline_only=True)

    def draw_stickman(
        self,
        player: Player,
        body_color: tuple[int, int, int],
        x_offset: float = 0.0,
        y_offset: float = 0.0,
        outline_only: bool = False,
    ) -> None:
        pose = player.get_pose()
        facing = player.facing
        root_x = player.center_x + x_offset
        foot_y = GROUND_Y - y_offset
        hip_y = foot_y - 22 - pose.crouch
        torso_top_y = hip_y - BODY_LENGTH - pose.stretch
        head_y = torso_top_y - HEAD_RADIUS - 6

        hip = pygame.Vector2(root_x, hip_y)
        chest = pygame.Vector2(root_x + pose.lean * 16 * facing, torso_top_y)
        head = pygame.Vector2(chest.x + pose.head_forward * facing, head_y)
        shoulder = pygame.Vector2(chest.x + pose.shoulder_forward * 0.35 * facing, chest.y - 1 - pose.shoulder_up)

        lead_hand = pygame.Vector2(
            shoulder.x + (ARM_LENGTH + pose.shoulder_forward) * facing,
            shoulder.y + pose.lead_arm_bend * 3,
        )
        rear_hand = pygame.Vector2(
            shoulder.x - (FOREARM_LENGTH * 0.7) * facing,
            shoulder.y + 4 + pose.rear_arm_bend * 3,
        )

        lead_knee = pygame.Vector2(hip.x + pose.lead_leg_forward * facing, hip.y + THIGH_LENGTH)
        rear_knee = pygame.Vector2(hip.x + pose.rear_leg_forward * facing, hip.y + THIGH_LENGTH)
        lead_foot = pygame.Vector2(lead_knee.x + 2.5 * facing, foot_y)
        rear_foot = pygame.Vector2(rear_knee.x - 2.5 * facing, foot_y)

        line_width = STICK_WIDTH if not outline_only else 2

        def line(a: pygame.Vector2, b: pygame.Vector2, color: tuple[int, int, int]) -> None:
            pygame.draw.line(self.screen, color, a, b, line_width)

        def circle(center: pygame.Vector2, radius: int, color: tuple[int, int, int]) -> None:
            width = 0 if not outline_only else 2
            pygame.draw.circle(self.screen, color, (int(center.x), int(center.y)), radius, width)

        def rotate_offset(length: float, angle: float) -> pygame.Vector2:
            return pygame.Vector2(math.cos(angle) * length * facing, math.sin(angle) * length)

        sword_base = lead_hand + rotate_offset(pose.sword_offset, pose.sword_angle)
        sword_tip = sword_base + rotate_offset(SWORD_LENGTH, pose.sword_angle)
        sword_cross = rotate_offset(SWORD_GUARD, pose.sword_angle + math.pi / 2)
        sword_handle_end = sword_base - rotate_offset(SWORD_HANDLE, pose.sword_angle)
        sheath_angle = 1.0
        sheath_base = pygame.Vector2(hip.x - 6 * facing, hip.y + 2)
        sheath_tip = sheath_base + rotate_offset(SWORD_LENGTH + 6, sheath_angle)
        sheath_cross = rotate_offset(SWORD_GUARD - 2, sheath_angle + math.pi / 2)
        sheath_handle_end = sheath_base - rotate_offset(SWORD_HANDLE - 2, sheath_angle)
        sword_drawn = not (player.state in {"IDLE", "MOVE"} and player.attack_profile is None and not player.charge_held and player.feint_lockout_frames <= 0 and player.dash_travel_frames <= 0 and player.dash_startup_frames <= 0 and player.dash_brake_lockout_frames <= 0 and not player.state.startswith("PARRY"))

        line(head, chest, body_color)
        line(chest, hip, body_color)
        line(shoulder, lead_hand, body_color)
        line(shoulder, rear_hand, body_color)
        line(hip, lead_knee, body_color)
        line(lead_knee, lead_foot, body_color)
        line(hip, rear_knee, body_color)
        line(rear_knee, rear_foot, body_color)
        circle(head, HEAD_RADIUS, body_color)

        if not outline_only:
            pygame.draw.line(self.screen, SHEATH_COLOR, sheath_base, sheath_tip, SWORD_WIDTH + 2)
            pygame.draw.line(self.screen, SHEATH_EDGE_COLOR, sheath_base, sheath_tip, 2)
            pygame.draw.line(self.screen, SHEATH_COLOR, sheath_base - sheath_cross, sheath_base + sheath_cross, 4)
            pygame.draw.line(self.screen, SHEATH_COLOR, sheath_base, sheath_handle_end, 4)
            pygame.draw.line(self.screen, SHEATH_EDGE_COLOR, hip, sheath_base, 2)

        if sword_drawn:
            if not outline_only:
                glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                pygame.draw.line(glow_surface, SWORD_GLOW_COLOR, sword_base, sword_tip, SWORD_WIDTH + 8)
                self.screen.blit(glow_surface, (0, 0))
                pygame.draw.line(self.screen, SWORD_COLOR, sword_base, sword_tip, SWORD_WIDTH)
                pygame.draw.line(self.screen, SWORD_EDGE_COLOR, sword_base, sword_tip, 2)
                pygame.draw.line(self.screen, SWORD_COLOR, sword_base - sword_cross, sword_base + sword_cross, 4)
                pygame.draw.line(self.screen, SWORD_COLOR, sword_base, sword_handle_end, 5)
                pommel = sword_handle_end - rotate_offset(2.5, pose.sword_angle)
                pygame.draw.circle(self.screen, SWORD_COLOR[:3], (int(pommel.x), int(pommel.y)), 3)
            else:
                pygame.draw.line(self.screen, SWORD_EDGE_COLOR[:3], sword_base, sword_tip, 2)

        if player.state == "PARRY_ACTIVE":
            guard_center = pygame.Vector2(chest.x + 12 * facing, chest.y - 4)
            pygame.draw.arc(
                self.screen,
                FLASH_COLOR,
                pygame.Rect(guard_center.x - 16, guard_center.y - 16, 32, 32),
                -0.8 if facing == 1 else math.pi - 2.3,
                0.8 if facing == 1 else math.pi + 0.8,
                3,
            )
            pygame.draw.circle(self.screen, FLASH_COLOR, (int(guard_center.x), int(guard_center.y)), 5, 1)

        if player.attack_profile is not None and player.state.endswith("_ACTIVE"):
            slash_start = pygame.Vector2(chest.x - 8 * facing, chest.y + 12)
            slash_end = pygame.Vector2(chest.x + (20 + (player.attack_profile.reach * 0.34)) * facing, chest.y - 8)
            pygame.draw.line(self.screen, HITBOX_COLOR, slash_start, slash_end, 3 if not outline_only else 2)
            if not outline_only:
                trail_color = (255, 160, 120) if player.attack_profile.name == "HEAVY" else (255, 210, 140)
                arc_width = 44 + player.attack_profile.reach * 0.58
                arc_height = 56 if player.attack_profile.name == "LIGHT" else 72 if player.attack_profile.name == "MEDIUM" else 92
                arc_left = min(slash_start.x, slash_end.x) - 10
                arc_top = chest.y - arc_height * 0.55
                sweep_rect = pygame.Rect(arc_left, arc_top, arc_width, arc_height)
                if facing == 1:
                    start_angle, end_angle = -1.65, 1.15
                else:
                    start_angle, end_angle = math.pi - 1.15, math.pi + 1.65
                pygame.draw.arc(self.screen, trail_color, sweep_rect, start_angle, end_angle, 4)

                inner_margin = 10
                inner_rect = pygame.Rect(
                    sweep_rect.x + inner_margin,
                    sweep_rect.y + inner_margin,
                    max(10, sweep_rect.width - inner_margin * 2),
                    max(10, sweep_rect.height - inner_margin * 2),
                )
                inner_color = (255, 235, 210) if player.attack_profile.name == "HEAVY" else (250, 228, 185)
                pygame.draw.arc(self.screen, inner_color, inner_rect, start_angle + 0.08, end_angle - 0.12, 2)

        if player.state == "PARRY_SUCCESS" and not outline_only:
            burst_center = pygame.Vector2(chest.x + 10 * facing, chest.y - 2)
            for ray in range(5):
                spread = -0.9 + ray * 0.45
                tip = burst_center + pygame.Vector2(math.cos(spread) * 22 * facing, math.sin(spread) * 14)
                pygame.draw.line(self.screen, FLASH_COLOR, burst_center, tip, 2)
            pygame.draw.circle(self.screen, FLASH_COLOR, (int(burst_center.x), int(burst_center.y)), 8, 2)

        if player.state == "DASH_BRAKE":
            skid_x = player.center_x - 12 * facing
            pygame.draw.line(self.screen, FLASH_COLOR, (skid_x, foot_y + 1), (skid_x - 14 * facing, foot_y - 5), 2)
            pygame.draw.line(self.screen, SUBTEXT_COLOR, (skid_x - 4 * facing, foot_y + 1), (skid_x - 18 * facing, foot_y + 2), 2)

    def draw_player(self, player: Player) -> None:
        rect = player.rect
        body_color = player.color

        if player.state.endswith("CHARGE"):
            body_color = HEAVY_CHARGE_COLOR if player.state.startswith("HEAVY") else CHARGE_COLOR
        elif player.is_parry_active() or player.state.startswith("PARRY") or player.state == "PARRY_SUCCESS":
            body_color = PARRY_COLOR
        elif player.state.startswith("DASH"):
            body_color = DASH_COLOR

        if not player.alive:
            body_color = (70, 70, 70)

        self.draw_afterimage(player, body_color)
        pygame.draw.rect(self.screen, HURTBOX_COLOR, rect, width=1, border_radius=4)
        self.draw_stickman(player, body_color)

        center_x = rect.centerx
        center_y = rect.top - 14
        end_x = center_x + 18 * player.facing
        pygame.draw.line(self.screen, (40, 90, 150), (center_x, center_y), (end_x, center_y), 2)

        hitbox = player.get_hitbox()
        if hitbox:
            pygame.draw.rect(self.screen, HITBOX_COLOR, hitbox, width=2)

        state_text = self.font.render(
            f"P{player.player_id} {player.state} vel={player.velocity_x:.2f}",
            True,
            TEXT_COLOR,
        )
        self.screen.blit(state_text, (rect.x - 30, rect.y - 32))

        debug_text = self.font.render(
            (
                f"charge={int(player.charge_ms)}ms parry={player.parry_active_frames} "
                f"punish={player.punish_window_frames} dash={player.dash_available_frames}"
            ),
            True,
            SUBTEXT_COLOR,
        )
        self.screen.blit(debug_text, (rect.x - 30, rect.y - 54))

    def draw_ui(self) -> None:
        title = self.big_font.render("1SLASH Prototype - Single File Testbed", True, TEXT_COLOR)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 18))

        score = self.big_font.render(f"P1 {self.p1.rounds}  -  {self.p2.rounds} P2", True, TEXT_COLOR)
        self.screen.blit(score, (SCREEN_WIDTH // 2 - score.get_width() // 2, 56))

        spacing = self.font.render(
            f"Spacing: {self.get_distance_layer()} | gap={self.p1.distance_to(self.p2):.1f}px",
            True,
            TEXT_COLOR,
        )
        self.screen.blit(spacing, (SCREEN_WIDTH // 2 - spacing.get_width() // 2, 92))

        help_lines = [
            "Light: tap confirm | Medium: hold 300ms+ then confirm | Heavy: hold 650ms+ then confirm",
            "Release charge without confirm = feint | Heavy parry gives pushback + dash re-engage",
            "Dash: press forward after heavy parry | press confirm during dash to brake, not attack",
            "P1: A/D move | J charge | K confirm | L parry",
            "P2: LEFT/RIGHT move | NUM1 charge | NUM2 confirm | NUM3 parry | R resets score",
        ]
        for index, line in enumerate(help_lines):
            surface = self.font.render(line, True, SUBTEXT_COLOR)
            self.screen.blit(surface, (24, 125 + 26 * index))

        if self.hitstop_frames > 0:
            hitstop_text = self.font.render(f"HITSTOP {self.hitstop_frames}", True, (140, 90, 30))
            self.screen.blit(hitstop_text, (SCREEN_WIDTH - 200, 28))

        if self.winner_text:
            overlay = self.big_font.render(self.winner_text, True, (120, 80, 20))
            self.screen.blit(overlay, (SCREEN_WIDTH // 2 - overlay.get_width() // 2, 118))

    def draw_stage(self) -> None:
        self.screen.fill(BG_COLOR)
        pygame.draw.line(self.screen, CENTER_LINE_COLOR, (SCREEN_WIDTH // 2, 0), (SCREEN_WIDTH // 2, SCREEN_HEIGHT), 1)
        pygame.draw.line(self.screen, (120, 120, 128), (0, GROUND_Y), (SCREEN_WIDTH, GROUND_Y), 2)

    def draw(self) -> None:
        self.draw_stage()
        self.draw_player(self.p1)
        self.draw_player(self.p2)
        self.draw_ui()
        if self.p1.state == "PARRY_SUCCESS" or self.p2.state == "PARRY_SUCCESS":
            parry_flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            parry_flash.fill((255, 250, 210, 24))
            self.screen.blit(parry_flash, (0, 0))
        if self.hitstop_frames > 0:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            alpha = 28 + self.hitstop_frames * 8
            flash.fill((255, 255, 255, min(alpha, 72)))
            self.screen.blit(flash, (0, 0))
        pygame.display.flip()


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()

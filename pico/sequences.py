"""
Compound moves. Edit / add freely.

Every sequence is an `async def fn(robot):` and gets registered at the bottom
of this file. Registered names become buttons on the web UI automatically.

Building blocks available on `robot`:
  motors:    robot.extension, robot.tilt, robot.scoop, robot.wheels
             .set(pwm)  .stop()  await .jolt(target)  await .ramp_to(t, ms)
             await .ramp_stop(ms)
  sensors:   robot.tof_rock, robot.tof_extension, robot.scoop_angle, robot.tilt_angle
             .read_mm() / .read_deg()
             await .wait_for_drop(mm, timeout_ms=...)
             await .wait_below(mm) / .wait_above(mm)
             await .wait_for_angle(deg) / .wait_past(deg, direction=+/-1)
  brake:     robot.tilt_brake.start() / .stop()
  pause:     await wait_ms(ms)

Safety:
  Every wait_* has a timeout. None means "didn't happen". Always check and
  decide whether to bail out — don't drive motors forever.
"""

import uasyncio as asyncio
from motors import PWM_MAX
from sensors import wait_ms
from robot import TiltBrake


# ----------------- tunables (tweak as you tune the robot)

EXT_SCOOP_PWM   = int(0.80 * PWM_MAX)
EXT_RETRACT_PWM = -int(0.50 * PWM_MAX)
TILT_PWM        = int(0.30 * PWM_MAX) * TiltBrake.LIFT_SIGN
SCOOP_PWM       = PWM_MAX

ROCK_DROP_MM      = 20        # TOF drop signalling rock under nozzle
SCOOP_DOWN_DEG    = 20        # arm angle for "down to ground"
SCOOP_UP_DEG      = 90        # arm angle to dump
SCOOP_CLOSED_DEG  = 0         # scoop pot at rest
SCOOP_OPEN_DEG    = 90        # scoop pot fully engaged


# ----------------- helpers used by sequences

async def _tilt_to(robot, target_deg, timeout_ms=4000):
    """Move tilt motor toward target_deg using jolt + ramp_stop.

    Releases the brake first; caller is responsible for re-engaging.
    """
    if robot.tilt_brake is not None:
        robot.tilt_brake.stop()
    cur = robot.tilt_angle.read_deg()
    direction = +1 if target_deg > cur else -1
    await robot.tilt.jolt(TILT_PWM * direction, jolt_ms=80)
    hit = await robot.tilt_angle.wait_past(target_deg, direction=direction,
                                           timeout_ms=timeout_ms)
    await robot.tilt.ramp_stop(200)
    return hit is not None


# ============================================================
#   SEQUENCES
# ============================================================

async def scoop_rock(robot):
    """Extend until rock detected, tilt down, run scoop, tilt back up."""
    print(">> scoop_rock")

    # 1. extend until TOF drops (rock spotted)
    await robot.extension.jolt(EXT_SCOOP_PWM, jolt_ms=80)
    hit = await robot.tof_rock.wait_for_drop(ROCK_DROP_MM, timeout_ms=10000)
    await robot.extension.ramp_stop(150)
    if hit is None:
        print("   no rock detected — aborting")
        return

    # 2. tilt down to ground
    if not await _tilt_to(robot, SCOOP_DOWN_DEG, timeout_ms=4000):
        print("   tilt-down timed out")
        return

    # 3. spin scoop until potentiometer reads OPEN angle
    await robot.scoop.jolt(SCOOP_PWM, jolt_ms=80)
    hit = await robot.scoop_angle.wait_past(SCOOP_OPEN_DEG, direction=+1,
                                            timeout_ms=4000)
    robot.scoop.stop()
    if hit is None:
        print("   scoop didn't reach open angle")

    await wait_ms(300)

    # 4. tilt back up to dump position, then engage brake to hold
    await _tilt_to(robot, SCOOP_UP_DEG, timeout_ms=4000)
    if robot.tilt_brake is not None:
        robot.tilt_brake.start()

    print(">> scoop_rock done")


async def retract_arm(robot):
    """Retract the extension fully. Timed since we don't have a retract sensor."""
    print(">> retract_arm")
    await robot.extension.jolt(EXT_RETRACT_PWM, jolt_ms=80)
    await wait_ms(4000)        # tune
    await robot.extension.ramp_stop(200)
    print(">> retract_arm done")


async def dump_load(robot):
    """Tilt up to dump, run scoop in reverse-ish, return to neutral."""
    print(">> dump_load")
    await _tilt_to(robot, SCOOP_UP_DEG + 10, timeout_ms=4000)
    # quick scoop oscillation to shake out rocks
    for _ in range(3):
        await robot.scoop.jolt(SCOOP_PWM, jolt_ms=60)
        await wait_ms(150)
        robot.scoop.stop()
        await wait_ms(150)
    await _tilt_to(robot, SCOOP_UP_DEG, timeout_ms=4000)
    if robot.tilt_brake is not None:
        robot.tilt_brake.start()
    print(">> dump_load done")


async def home_arm(robot):
    """Bring tilt to a known safe angle and stop scoop. Use after testing."""
    print(">> home_arm")
    await _tilt_to(robot, SCOOP_UP_DEG, timeout_ms=5000)
    robot.scoop.stop()
    if robot.tilt_brake is not None:
        robot.tilt_brake.start()
    print(">> home_arm done")


# ============================================================
#   REGISTRY  (names here become buttons on the web UI)
# ============================================================

def register_all(robot):
    robot.register("scoop_rock",  scoop_rock)
    robot.register("retract_arm", retract_arm)
    robot.register("dump_load",   dump_load)
    robot.register("home_arm",    home_arm)

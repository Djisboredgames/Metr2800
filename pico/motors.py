"""
Motor primitives for BTS7960 / TB6612 (2-pin mode).

Every motor exposes:
    set(signed_pwm)      -- instant set, -65535..65535
    stop()               -- coast to 0
    jolt(target_pwm)     -- short high-pwm kick, then drop to target  (async)
    ramp_to(target, ms)  -- linear ramp from current to target        (async)
    ramp_stop(ms)        -- linear ramp from current to 0             (async)

Direction sign convention is up to whoever wires the motor. If a motor
moves the wrong way, swap lpwm_pin / rpwm_pin at construction time.
"""

import uasyncio as asyncio
from machine import Pin, PWM


PWM_MAX = 65535


class Motor:
    def __init__(self, lpwm_pin, rpwm_pin, name="motor", freq=1000):
        self.lpwm = PWM(Pin(lpwm_pin))
        self.rpwm = PWM(Pin(rpwm_pin))
        self.lpwm.freq(freq)
        self.rpwm.freq(freq)
        self.lpwm.duty_u16(0)
        self.rpwm.duty_u16(0)
        self.current = 0
        self.name = name

    def set(self, signed_pwm):
        s = int(signed_pwm)
        if s > PWM_MAX:
            s = PWM_MAX
        elif s < -PWM_MAX:
            s = -PWM_MAX
        if s > 0:
            self.lpwm.duty_u16(0)
            self.rpwm.duty_u16(s)
        elif s < 0:
            self.rpwm.duty_u16(0)
            self.lpwm.duty_u16(-s)
        else:
            self.lpwm.duty_u16(0)
            self.rpwm.duty_u16(0)
        self.current = s

    def stop(self):
        self.set(0)

    async def jolt(self, target_pwm, jolt_pwm=None, jolt_ms=80):
        """Kick at jolt_pwm for jolt_ms then settle at target_pwm.

        Useful for breaking static friction on 3D printed drivetrains.
        jolt_pwm defaults to 80% in the direction of target_pwm.
        """
        target_pwm = int(target_pwm)
        if jolt_pwm is None:
            mag = int(0.8 * PWM_MAX)
            jolt_pwm = mag if target_pwm >= 0 else -mag
        self.set(jolt_pwm)
        await asyncio.sleep_ms(jolt_ms)
        self.set(target_pwm)

    async def ramp_to(self, target_pwm, duration_ms=400, step_ms=20):
        """Linearly ramp PWM from current to target over duration."""
        target_pwm = int(target_pwm)
        start = self.current
        if duration_ms <= 0 or start == target_pwm:
            self.set(target_pwm)
            return
        steps = max(1, duration_ms // step_ms)
        for i in range(1, steps + 1):
            t = i / steps
            self.set(int(start + (target_pwm - start) * t))
            await asyncio.sleep_ms(step_ms)

    async def ramp_stop(self, duration_ms=300):
        """Linearly ramp current PWM down to 0 — your 'soft brake'."""
        await self.ramp_to(0, duration_ms)


class MotorPair:
    """Two motors wired as a left/right pair (e.g. drive wheels).

    Convenience wrapper so you can call forward/back/turn from one object.
    """

    def __init__(self, left: Motor, right: Motor):
        self.left = left
        self.right = right

    def drive(self, l_pwm, r_pwm):
        self.left.set(l_pwm)
        self.right.set(r_pwm)

    def forward(self, speed=PWM_MAX):
        self.drive(speed, speed)

    def back(self, speed=PWM_MAX):
        self.drive(-speed, -speed)

    def turn_left(self, speed=PWM_MAX):
        self.drive(-speed, speed)

    def turn_right(self, speed=PWM_MAX):
        self.drive(speed, -speed)

    def stop(self):
        self.drive(0, 0)

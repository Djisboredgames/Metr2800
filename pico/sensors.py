"""
Sensor wrappers + async wait helpers.

The robot uses:
  - VL53L0X TOF (rock detection during extension)
  - VL53L0X TOF (extension length, optional second sensor)
  - Potentiometer on scoop output shaft (angle 0..180)
  - Potentiometer on tilt pivot (arm angle for brake feedback)

The TOF wrapper expects a sensor object exposing .read() returning mm.
Drop in a community VL53L0X driver as `vl53l0x.py` on the Pico and pass an
instance in (see main.py for wiring). If your driver names the method
differently, change _read_raw below.
"""

import time
import uasyncio as asyncio
from machine import ADC, Pin


# ---------------------------------------------------------------- TOF

class TOF:
    def __init__(self, sensor, name="tof"):
        self.sensor = sensor
        self.name = name
        self._last = 0

    def _read_raw(self):
        # vl53l0x.read() is the kevinmcaleer / uceeatz convention.
        return self.sensor.read()

    def read_mm(self):
        try:
            self._last = self._read_raw()
        except Exception as e:
            print(self.name, "read err:", e)
        return self._last

    async def wait_for_drop(self, drop_mm, timeout_ms=5000, poll_ms=20,
                            settle_samples=2):
        """Wait until the distance drops by `drop_mm` from the baseline.

        baseline = average of first few samples. Returns the triggering
        reading, or None on timeout.
        """
        samples = []
        for _ in range(3):
            samples.append(self.read_mm())
            await asyncio.sleep_ms(poll_ms)
        baseline = sum(samples) // len(samples)
        hits = 0
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            r = self.read_mm()
            if baseline - r >= drop_mm:
                hits += 1
                if hits >= settle_samples:
                    return r
            else:
                hits = 0
            await asyncio.sleep_ms(poll_ms)
        return None

    async def wait_below(self, threshold_mm, timeout_ms=5000, poll_ms=20):
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.read_mm() < threshold_mm:
                return self._last
            await asyncio.sleep_ms(poll_ms)
        return None

    async def wait_above(self, threshold_mm, timeout_ms=5000, poll_ms=20):
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            if self.read_mm() > threshold_mm:
                return self._last
            await asyncio.sleep_ms(poll_ms)
        return None


# ---------------------------------------------------------------- POT

class AnglePot:
    """Potentiometer mapped to a degree range. Tune raw_min / raw_max via the
    calibration helpers, or by reading the live value at the two endstops.
    """

    def __init__(self, adc_pin, raw_min=0, raw_max=65535,
                 deg_min=0.0, deg_max=180.0, name="pot"):
        self.adc = ADC(Pin(adc_pin))
        self.raw_min = raw_min
        self.raw_max = raw_max
        self.deg_min = deg_min
        self.deg_max = deg_max
        self.name = name

    def read_raw(self):
        return self.adc.read_u16()

    def read_deg(self):
        raw = self.read_raw()
        span = self.raw_max - self.raw_min
        if span == 0:
            return self.deg_min
        t = (raw - self.raw_min) / span
        if t < 0:
            t = 0
        elif t > 1:
            t = 1
        return self.deg_min + t * (self.deg_max - self.deg_min)

    async def wait_for_angle(self, target_deg, tolerance=2.0,
                             timeout_ms=5000, poll_ms=20):
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            cur = self.read_deg()
            if abs(cur - target_deg) <= tolerance:
                return cur
            await asyncio.sleep_ms(poll_ms)
        return None

    async def wait_past(self, target_deg, direction=1,
                        timeout_ms=5000, poll_ms=20):
        """Wait until angle moves PAST target_deg in the given direction.

        direction=+1 means waiting for angle >= target_deg.
        direction=-1 means waiting for angle <= target_deg.
        """
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            cur = self.read_deg()
            if direction >= 0 and cur >= target_deg:
                return cur
            if direction < 0 and cur <= target_deg:
                return cur
            await asyncio.sleep_ms(poll_ms)
        return None


# ---------------------------------------------------------------- helpers

async def wait_ms(ms):
    """Convenience: thin alias so sequences read naturally."""
    await asyncio.sleep_ms(ms)

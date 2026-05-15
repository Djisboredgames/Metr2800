"""
Robot facade + sequence runner + tilt brake.
"""

import uasyncio as asyncio

from motors import Motor, MotorPair, PWM_MAX


# ----------------------------------------------------------- Tilt brake

class TiltBrake:
    """Applies a fixed PWM to hold the tilt arm against gravity.

    No loop, no feedback, no async. PWM hardware holds the value once set.
    Tune BRAKE_PWM until the arm holds without drifting.
    If the arm moves DOWN when brake is on, make BRAKE_PWM negative.
    """

    BRAKE_PWM = 4000   # out of 65535 — tune this

    def __init__(self, motor: Motor):
        self.motor = motor
        self._active = False

    def start(self):
        self._active = True
        self.motor.set(self.BRAKE_PWM)

    def stop(self):
        self._active = False
        self.motor.stop()

    @property
    def active(self):
        return self._active


# ----------------------------------------------------------- Robot

class Robot:
    def __init__(self):
        self.wheels: MotorPair = None
        self.extension: Motor = None
        self.tilt: Motor = None
        self.scoop: Motor = None

        self.tof_rock = None
        self.tof_extension = None
        self.scoop_angle = None
        self.tilt_angle = None

        self.tilt_brake: TiltBrake = None

        self.sequences = {}

        self._seq_task = None
        self._seq_name = None
        self.status = "idle"
        self.last_error = ""

        self.scoop_on = False

    # ---------------- sequence runner

    def register(self, name, coro_fn):
        self.sequences[name] = coro_fn

    def is_running(self):
        return self._seq_task is not None

    def run_sequence(self, name):
        if name not in self.sequences:
            self.last_error = "unknown sequence: " + name
            return False
        if self.is_running():
            self.last_error = "busy: " + (self._seq_name or "")
            return False
        coro = self.sequences[name](self)
        self._seq_name = name
        self.status = name
        self._seq_task = asyncio.create_task(self._wrap(name, coro))
        return True

    async def _wrap(self, name, coro):
        try:
            await coro
            self.status = "idle"
        except asyncio.CancelledError:
            self.status = "cancelled:" + name
            self._all_stop()
            raise
        except Exception as e:
            print("sequence", name, "error:", e)
            self.last_error = str(e)
            self.status = "error:" + name
            self._all_stop()
        finally:
            self._seq_task = None
            self._seq_name = None

    # ---------------- E-stop

    def _all_stop(self):
        for m in (self.extension, self.tilt, self.scoop):
            if m is not None:
                m.stop()
        if self.wheels is not None:
            self.wheels.stop()

    def estop(self):
        if self.tilt_brake is not None:
            self.tilt_brake.stop()
        if self._seq_task is not None:
            self._seq_task.cancel()
        self._all_stop()
        self.scoop_on = False
        self.status = "ESTOPPED"

    # ---------------- manual controls

    def wheels_forward(self):  self.wheels.forward()
    def wheels_back(self):     self.wheels.back()
    def wheels_left(self):     self.wheels.turn_left()
    def wheels_right(self):    self.wheels.turn_right()
    def wheels_stop(self):     self.wheels.stop()

    def ext_forward(self):     self.extension.set(int(0.8 * PWM_MAX))
    def ext_back(self):        self.extension.set(-int(0.4 * PWM_MAX))
    def ext_stop(self):        self.extension.stop()

    def tilt_up(self):
        if self.tilt_brake is not None: self.tilt_brake.stop()
        self.tilt.set(int(0.3 * PWM_MAX))
    def tilt_down(self):
        if self.tilt_brake is not None: self.tilt_brake.stop()
        self.tilt.set(-int(0.3 * PWM_MAX))
    def tilt_stop(self):
        self.tilt.stop()

    def tilt_brake_on(self):
        if self.tilt_brake is not None: self.tilt_brake.start()
    def tilt_brake_off(self):
        if self.tilt_brake is not None: self.tilt_brake.stop()

    def scoop_toggle(self):
        self.scoop_on = not self.scoop_on
        if self.scoop_on:
            self.scoop.set(PWM_MAX)
        else:
            self.scoop.stop()

    # ---------------- status snapshot

    def snapshot(self):
        d = {
            "status": self.status,
            "seq": self._seq_name or "",
            "err": self.last_error,
            "brake": bool(self.tilt_brake and self.tilt_brake.active),
            "scoop_on": self.scoop_on,
        }
        try:
            if self.tof_rock is not None:
                d["tof_rock_mm"] = self.tof_rock.read_mm()
            if self.tof_extension is not None:
                d["tof_ext_mm"] = self.tof_extension.read_mm()
            if self.scoop_angle is not None:
                d["scoop_deg"] = round(self.scoop_angle.read_deg(), 1)
            if self.tilt_angle is not None:
                d["tilt_deg"] = round(self.tilt_angle.read_deg(), 1)
        except Exception as e:
            d["sensor_err"] = str(e)
        return d

# PicoBot — MicroPython framework

Async framework for the rock-scoop robot. Web UI for manual control + named
sequences. Built on `uasyncio` so the web server stays responsive while
sequences run.

## Files

| File           | Purpose                                                                 |
|----------------|-------------------------------------------------------------------------|
| `motors.py`    | `Motor` (BTS7960 / TB6612-2pin) + `jolt` + `ramp_to` + `ramp_stop`. `MotorPair` for wheels. |
| `sensors.py`   | `TOF` (VL53L0X wrapper) + `AnglePot` + async `wait_*` helpers. Every wait has a timeout. |
| `robot.py`     | `Robot` (facade), `TiltBrake` (feedforward + drift correction), sequence runner. |
| `sequences.py` | Compound moves — `scoop_rock`, `retract_arm`, `dump_load`, `home_arm`. Add freely; registered names auto-appear as buttons. |
| `main.py`      | Pin map, WiFi AP, async HTTP server, HTML UI.                            |

## Deploying

1. Copy all `.py` files to the Pico's flash.
2. Drop a VL53L0X MicroPython driver onto the Pico as `vl53l0x.py`
   (e.g. <https://github.com/kevinmcaleer/vl53l0x>). If yours has a different
   read method, fix `sensors.TOF._read_raw` in one line.
3. Reset the Pico. AP `PicoBot` / `robotsrule` comes up. Browse to the IP shown
   on serial (usually `192.168.4.1`).

## Adding a sequence

Edit `sequences.py`:

```python
async def my_move(robot):
    await robot.extension.jolt(int(0.7 * PWM_MAX))
    hit = await robot.tof_rock.wait_for_drop(20, timeout_ms=8000)
    await robot.extension.ramp_stop(150)
    if hit is None:
        print("nothing detected")
        return
    # ... more steps
```

Register it in `register_all`:

```python
robot.register("my_move", my_move)
```

Reset. Button appears.

## Safety model

- **E-stop**: cancels the running sequence task and zeroes every motor. Wired
  to both the web button and the physical button on `BTN_PIN`.
- **One sequence at a time**: starting a second is rejected; press E-stop first.
- **Timeouts everywhere**: every `wait_*` returns `None` if nothing happens
  within the window. Always check the return value and bail out.
- **Tab visibility**: if the phone screen locks or you switch tabs, the UI
  fires `/estop` automatically.

## Tilt brake

`TiltBrake` continuously applies a small PWM in the lift direction:

- **Feedforward**: a `(extension_mm → base_pwm)` table — bigger extension =
  more torque needed. Edit `TiltBrake.FF_TABLE` to match what you measure.
- **Feedback**: every 50 ms reads the tilt potentiometer. If the arm drops
  more than `DRIFT_DEG_PER_SAMPLE`, bumps PWM up by `BUMP_PWM`. Bleeds back
  down when stable.
- Sequences call `robot.tilt_brake.stop()` *before* tilting and
  `robot.tilt_brake.start()` after settling.

If positive PWM moves the arm *down* on your wiring, flip
`TiltBrake.LIFT_SIGN = -1`.

## Smooth motion primitives

```python
await motor.jolt(target_pwm, jolt_ms=80)   # 80% kick then settle to target
await motor.ramp_to(target, duration_ms)   # linear ramp from current
await motor.ramp_stop(duration_ms)         # linear ramp to 0 (soft brake)
```

Tune `jolt_ms` and ramp durations per motor — the defaults are starting points.

## Pin map

Defined at the top of `main.py`. Sensor pins (`I2C0`, `I2C1`, ADCs) are
placeholders — change to whatever you actually wire.

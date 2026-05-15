"""
Boot file: wires hardware, starts the WiFi AP, and runs the async web server.

Pin assignments below are placeholders for the new sensors — change them to
whatever you actually wire. The motor pins match the existing layout.

VL53L0X library: drop a community driver onto the Pico as `vl53l0x.py`.
The one this code targets exposes:
    sensor = VL53L0X(i2c)
    sensor.start()              # or .ping() / .init() depending on lib
    sensor.read()               # returns mm
If yours differs, edit sensors.TOF._read_raw or wrap your sensor in a tiny
class with a .read() method before passing it in.
"""

import network
import socket
import time
import uasyncio as asyncio
from machine import Pin, I2C

from motors import Motor, MotorPair
from sensors import TOF, AnglePot
from robot import Robot, TiltBrake
import sequences


# ======================== PIN ASSIGNMENTS ========================
# Wheels (BTS7960)
L_LPWM_PIN, L_RPWM_PIN = 3, 2
R_LPWM_PIN, R_RPWM_PIN = 4, 5

# Extension (BTS7960)
EXT_LPWM_PIN, EXT_RPWM_PIN = 6, 7

# Tilt (BTS7960)
TILT_LPWM_PIN, TILT_RPWM_PIN = 0, 1

# Scoop (TB6612 2-pin mode)
SCOOP_A1_PIN, SCOOP_A2_PIN = 20, 21

# Sensors  -- replace with whatever you actually wire
I2C0_SDA, I2C0_SCL = 16, 17   # bus for TOF #1 (rock detection)
I2C1_SDA, I2C1_SCL = 18, 19   # bus for TOF #2 (extension length, optional)
SCOOP_POT_PIN      = 26       # ADC0
TILT_POT_PIN       = 27       # ADC1

# Status LED + button
LED_PIN     = 9
BTN_LED_PIN = 10
BTN_PIN     = 11


# ======================== WIFI ========================
SSID     = "PicoBot"
PASSWORD = "robotsrule"


# ======================== HARDWARE BUILD ========================

def build_robot():
    r = Robot()

    r.wheels = MotorPair(
        Motor(L_LPWM_PIN, L_RPWM_PIN, "left"),
        Motor(R_LPWM_PIN, R_RPWM_PIN, "right"),
    )
    r.extension = Motor(EXT_LPWM_PIN, EXT_RPWM_PIN, "ext")
    r.tilt      = Motor(TILT_LPWM_PIN, TILT_RPWM_PIN, "tilt")
    # Scoop: drive() with both pins on a TB6612 in 2-pin mode behaves like
    # a BTS7960 — Motor is fine here. Pass (A2, A1) to match the original
    # spin direction in the legacy code.
    r.scoop = Motor(SCOOP_A2_PIN, SCOOP_A1_PIN, "scoop")

    # ---- sensors  (wrap in try so the robot still runs if a sensor is missing)
    try:
        import vl53l0x
        i2c0 = I2C(0, sda=Pin(I2C0_SDA), scl=Pin(I2C0_SCL), freq=400_000)
        tof0 = vl53l0x.VL53L0X(i2c0)
        try: tof0.start()
        except AttributeError: pass
        r.tof_rock = TOF(tof0, "tof_rock")
        print("tof_rock OK")
    except BaseException as e:
        print("tof_rock skipped:", e)

    try:
        import vl53l0x
        i2c1 = I2C(1, sda=Pin(I2C1_SDA), scl=Pin(I2C1_SCL), freq=400_000)
        tof1 = vl53l0x.VL53L0X(i2c1)
        try: tof1.start()
        except AttributeError: pass
        r.tof_extension = TOF(tof1, "tof_ext")
        print("tof_extension OK")
    except BaseException as e:
        print("tof_extension skipped:", e)

    try:
        r.scoop_angle = AnglePot(SCOOP_POT_PIN, name="scoop_pot",
                                 deg_min=0, deg_max=180)
        r.tilt_angle  = AnglePot(TILT_POT_PIN,  name="tilt_pot",
                                 deg_min=0, deg_max=180)
    except BaseException as e:
        print("pots skipped:", e)

    # ---- tilt brake (always available, no sensors required)
    r.tilt_brake = TiltBrake(r.tilt)

    sequences.register_all(r)
    return r


# ======================== HTML ========================

def render_html(robot):
    # Render sequence buttons dynamically from the registry
    seq_buttons = "\n".join(
        '  <button class="seq" onclick="cmd(\'seq/{0}\')">{1}</button>'.format(
            name, name.replace("_", " ").upper())
        for name in robot.sequences
    )

    return """<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PicoBot</title>
<style>
*{box-sizing:border-box}
body{font-family:sans-serif;background:#1a1a1a;color:#eee;margin:0 auto;padding:14px;max-width:480px}
h1{text-align:center;margin:6px 0 12px;font-size:20px}
h2{font-size:12px;color:#999;text-transform:uppercase;margin:16px 0 6px;letter-spacing:1.5px}
button{border:none;border-radius:10px;color:white;font-weight:bold;font-size:15px;padding:18px 0;cursor:pointer;user-select:none;-webkit-user-select:none;touch-action:manipulation}
button:active{opacity:.7}
button:disabled{opacity:.35}
.estop{width:100%;background:#cc2222;font-size:22px;padding:28px 0;margin-bottom:6px}
.pad{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px}
.pad>.spacer{visibility:hidden}
.row{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.full{width:100%}
.fwd{background:#2a8a4a}.back{background:#2a6a8a}.turn{background:#8a6a2a}
.stop{background:#aa3333}.toggle{background:#5a4a8a}
.hold{background:#4a6a8a;position:relative}
.hold::after{content:"HOLD";position:absolute;top:6px;right:10px;font-size:10px;opacity:.6;letter-spacing:1px}
.led{background:#8a6a4a}
.seq{background:#2a5a7a;width:100%;margin-bottom:4px}
.brake{background:#6a4a2a}
#status{background:#222;padding:8px;border-radius:6px;font-family:monospace;font-size:12px;margin-bottom:8px;white-space:pre-wrap;color:#9c9}
</style></head><body>
<h1>PicoBot</h1>
<button class="estop" onclick="cmd('estop')">E-STOP</button>
<div id="status">connecting...</div>

<section><h2>Sequences</h2>
""" + seq_buttons + """
</section>

<section><h2>Wheels</h2>
<div class="pad">
 <div class="spacer"></div>
 <button class="fwd"  onclick="cmd('wheels/forward')">FWD</button>
 <div class="spacer"></div>
 <button class="turn" onclick="cmd('wheels/left')">LEFT</button>
 <button class="stop" onclick="cmd('wheels/stop')">STOP</button>
 <button class="turn" onclick="cmd('wheels/right')">RIGHT</button>
 <div class="spacer"></div>
 <button class="back" onclick="cmd('wheels/back')">BACK</button>
 <div class="spacer"></div>
</div></section>

<section><h2>Scoop</h2>
<button class="toggle full" onclick="cmd('scoop/toggle')">SCOOP ON / OFF</button>
</section>

<section><h2>Extension</h2>
<div class="row">
 <button class="hold" data-action="extension/forward" data-stop="extension/stop">EXTEND</button>
 <button class="hold" data-action="extension/back"    data-stop="extension/stop">RETRACT</button>
</div></section>

<section><h2>Tilt</h2>
<div class="row">
 <button class="hold" data-action="tilt/up"   data-stop="tilt/stop">TILT UP</button>
 <button class="hold" data-action="tilt/down" data-stop="tilt/stop">TILT DOWN</button>
</div>
<div class="row" style="margin-top:6px">
 <button class="brake" onclick="cmd('brake/on')">BRAKE ON</button>
 <button class="brake" onclick="cmd('brake/off')">BRAKE OFF</button>
</div></section>

<section><h2>LED</h2>
<button class="led full" onclick="cmd('led/toggle')">LED ON / OFF</button>
</section>

<script>
function cmd(p){fetch('/'+p)}
document.querySelectorAll('.hold').forEach(b=>{
  const press=e=>{e.preventDefault();fetch('/'+b.dataset.action)};
  const release=()=>fetch('/'+b.dataset.stop);
  b.addEventListener('mousedown',press);
  b.addEventListener('mouseup',release);
  b.addEventListener('mouseleave',release);
  b.addEventListener('touchstart',press,{passive:false});
  b.addEventListener('touchend',release);
  b.addEventListener('touchcancel',release);
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)fetch('/estop')});
async function poll(){
  try{
    const r=await fetch('/status');
    const t=await r.text();
    document.getElementById('status').textContent=t;
  }catch(e){}
  setTimeout(poll,400);
}
poll();
</script>
</body></html>
"""


# ======================== ROUTING ========================

def build_routes(robot, led, btn_led_state_ref):
    """Returns a dict path -> callable(). Each callable returns optional text body."""

    def led_toggle():
        v = 1 - led.value()
        led.value(v)

    def status():
        s = robot.snapshot()
        return "\n".join("{}: {}".format(k, s[k]) for k in s)

    def seq_runner(name):
        def fn():
            ok = robot.run_sequence(name)
            return "started" if ok else "rejected: " + robot.last_error
        return fn

    routes = {
        "/wheels/forward":    robot.wheels_forward,
        "/wheels/back":       robot.wheels_back,
        "/wheels/left":       robot.wheels_left,
        "/wheels/right":      robot.wheels_right,
        "/wheels/stop":       robot.wheels_stop,
        "/extension/forward": robot.ext_forward,
        "/extension/back":    robot.ext_back,
        "/extension/stop":    robot.ext_stop,
        "/tilt/up":           robot.tilt_up,
        "/tilt/down":         robot.tilt_down,
        "/tilt/stop":         robot.tilt_stop,
        "/brake/on":          robot.tilt_brake_on,
        "/brake/off":         robot.tilt_brake_off,
        "/scoop/toggle":      robot.scoop_toggle,
        "/led/toggle":        led_toggle,
        "/estop":             robot.estop,
        "/status":            status,
    }
    for name in robot.sequences:
        routes["/seq/" + name] = seq_runner(name)
    return routes


# ======================== ASYNC HTTP SERVER ========================

async def handle_client(reader, writer, robot, routes, html_provider):
    try:
        req = await reader.readline()
        # drain headers
        while True:
            h = await reader.readline()
            if h == b"" or h == b"\r\n":
                break
        try:
            method, path, _ = req.decode().split(" ", 2)
        except Exception:
            path = "/"

        if path in routes:
            result = routes[path]()
            body = (result if isinstance(result, str) else "") or "ok"
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n"
                         b"Connection: close\r\n\r\n")
            writer.write(body.encode())
        else:
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n"
                         b"Connection: close\r\n\r\n")
            writer.write(html_provider().encode())
        await writer.drain()
    except Exception as e:
        print("http err:", e)
    finally:
        try:
            await writer.aclose()
        except Exception:
            pass


# ======================== MAIN ========================

async def amain():
    robot = build_robot()

    led = Pin(LED_PIN, Pin.OUT); led.value(0)
    btn_led = Pin(BTN_LED_PIN, Pin.OUT); btn_led.value(0)

    # physical button = hardware E-stop
    last_press = [0]
    def on_button(pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, last_press[0]) < 200:
            return
        last_press[0] = now
        btn_led.value(1)
        robot.estop()
    Pin(BTN_PIN, Pin.IN, Pin.PULL_UP).irq(
        trigger=Pin.IRQ_FALLING, handler=on_button)

    # bring up AP
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=SSID, password=PASSWORD)
    ap.active(True)
    while not ap.active():
        await asyncio.sleep_ms(50)
    print("AP up:", SSID, "->", ap.ifconfig()[0])

    routes = build_routes(robot, led, None)
    html_cached = render_html(robot)
    def html_provider():
        return html_cached

    async def client_cb(reader, writer):
        await handle_client(reader, writer, robot, routes, html_provider)

    server = await asyncio.start_server(client_cb, "0.0.0.0", 80)
    print("HTTP listening on :80")
    while True:
        await asyncio.sleep(3600)


def main():
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()

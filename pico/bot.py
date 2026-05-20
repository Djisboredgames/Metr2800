"""
bot.py — single-file Pico W robot controller
Flash this as main.py on the Pico.

WiFi AP:  PicoBot / robotsrule   →   http://192.168.4.1
"""

import network
import uasyncio as asyncio
from machine import Pin, PWM
import time

# ── Tunable constants ────────────────────────────────────────────────────
SSID            = "PicoBot"
PASSWORD        = "robotsrule"

TILT_SPEED      = 20_000        # PWM duty out of 65535 (~30%)
EXT_FWD_SPEED   = 52_000        # ~80%
EXT_BCK_SPEED   = 26_000        # ~40%
TILT_BRAKE_PWM  = 4_000         # holding force — increase if arm drops

PWM_FREQ        = 1_000         # Hz

# ── BTS7960 half-bridge driver ───────────────────────────────────────────
class BTS7960:
    def __init__(self, lpwm_pin, rpwm_pin):
        self.l = PWM(Pin(lpwm_pin), freq=PWM_FREQ, duty_u16=0)
        self.r = PWM(Pin(rpwm_pin), freq=PWM_FREQ, duty_u16=0)

    def forward(self, duty):
        self.l.duty_u16(0)
        self.r.duty_u16(min(duty, 65535))

    def backward(self, duty):
        self.r.duty_u16(0)
        self.l.duty_u16(min(duty, 65535))

    def brake(self, duty=65535):
        self.l.duty_u16(min(duty, 65535))
        self.r.duty_u16(min(duty, 65535))

    def coast(self):
        self.l.duty_u16(0)
        self.r.duty_u16(0)

# ── Hardware ─────────────────────────────────────────────────────────────
tilt = BTS7960(lpwm_pin=0, rpwm_pin=1)
ext  = BTS7960(lpwm_pin=6, rpwm_pin=7)

status_led = Pin(9,  Pin.OUT)
button_led = Pin(10, Pin.OUT)

# ── State ────────────────────────────────────────────────────────────────
brake_pwm = TILT_BRAKE_PWM      # mutable at runtime via slider

def tilt_cmd(cmd):
    if   cmd == "up":    tilt.forward(TILT_SPEED)
    elif cmd == "down":  tilt.backward(TILT_SPEED)
    elif cmd == "brake": tilt.brake(brake_pwm)
    else:                tilt.coast()

def ext_cmd(cmd):
    if   cmd == "fwd":  ext.forward(EXT_FWD_SPEED)
    elif cmd == "bck":  ext.backward(EXT_BCK_SPEED)
    else:               ext.coast()

def all_stop():
    tilt.brake(brake_pwm)
    ext.coast()

# Safe default on boot
all_stop()

# ── WiFi access point ────────────────────────────────────────────────────
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=SSID, password=PASSWORD)
while not ap.active():
    time.sleep(0.05)
print("AP up:", ap.ifconfig()[0])

# ── Web UI ───────────────────────────────────────────────────────────────
_HTML_TEMPLATE = b"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta charset="utf-8">
<title>PicoBot</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;padding:12px;background:#111;color:#eee;font-family:system-ui,sans-serif;text-align:center}
h1{margin:0 0 4px;font-size:1.4rem}
p.ip{margin:0 0 14px;font-size:.8rem;color:#666}
.card{background:#1e1e1e;border-radius:14px;padding:14px;margin-bottom:12px}
h2{margin:0 0 10px;font-size:.75rem;text-transform:uppercase;letter-spacing:.12em;color:#888}
.row{display:flex;gap:8px;justify-content:center}
button{
  flex:1;padding:20px 6px;font-size:1rem;border:none;border-radius:10px;
  background:#2a2a2a;color:#ddd;cursor:pointer;transition:background .08s;
  -webkit-user-select:none;user-select:none;touch-action:none
}
button:active,.lit{background:#0af!important;color:#000!important}
.brake-btn{background:#7a4a00}
.stop-btn{background:#5a0000;color:#f88;font-size:1.1rem;padding:22px;width:100%}
.stop-btn:active{background:#c00!important;color:#fff!important}
label{font-size:.85rem;color:#aaa}
input[type=range]{width:92%;accent-color:#0af;margin-top:6px}
#bval{color:#0af;font-weight:600}
</style>
</head>
<body>
<h1>PicoBot</h1>
<p class="ip">192.168.4.1</p>

<div class="card">
  <h2>Tilt</h2>
  <div class="row">
    <button id="tu" ontouchstart="go('tilt','up')"   ontouchend="go('tilt','brake')"
                    onmousedown="go('tilt','up')"     onmouseup="go('tilt','brake')"
                    onmouseleave="go('tilt','brake')">&#9650; Up</button>
    <button class="brake-btn" onclick="go('tilt','brake')">&#9646; Brake</button>
    <button id="td" ontouchstart="go('tilt','down')" ontouchend="go('tilt','brake')"
                    onmousedown="go('tilt','down')"   onmouseup="go('tilt','brake')"
                    onmouseleave="go('tilt','brake')">&#9660; Down</button>
  </div>
  <div style="margin-top:12px">
    <label>Brake PWM: <span id="bval">BPWM</span> / 65535</label>
    <input type="range" min="0" max="65535" step="100" value="BPWM"
      oninput="document.getElementById('bval').textContent=this.value"
      onchange="go('brake',this.value)">
  </div>
</div>

<div class="card">
  <h2>Extension</h2>
  <div class="row">
    <button ontouchstart="go('ext','fwd')" ontouchend="go('ext','stop')"
            onmousedown="go('ext','fwd')"  onmouseup="go('ext','stop')"
            onmouseleave="go('ext','stop')">&#9654; Out</button>
    <button ontouchstart="go('ext','bck')" ontouchend="go('ext','stop')"
            onmousedown="go('ext','bck')"  onmouseup="go('ext','stop')"
            onmouseleave="go('ext','stop')">&#9664; In</button>
  </div>
</div>

<div class="card">
  <h2>LEDs</h2>
  <div class="row">
    <button id="sl" onclick="led('sl','status')">Status LED</button>
    <button id="bl" onclick="led('bl','button')">Button LED</button>
  </div>
</div>

<div class="card">
  <button class="stop-btn" onclick="go('stop','all')">&#9940; STOP ALL</button>
</div>

<script>
const ls={sl:false,bl:false};
async function go(m,d){
  try{await fetch('/c?m='+m+'&d='+d,{method:'POST',keepalive:true})}catch(e){}
}
async function led(id,name){
  ls[id]=!ls[id];
  document.getElementById(id).classList.toggle('lit',ls[id]);
  try{await fetch('/led?n='+name+'&v='+(ls[id]?1:0),{method:'POST',keepalive:true})}catch(e){}
}
</script>
</body>
</html>"""

def _make_html():
    b = str(TILT_BRAKE_PWM).encode()
    return _HTML_TEMPLATE.replace(b"BPWM", b)

def _parse_qs(path):
    out = {}
    if b"?" in path:
        qs = path.split(b"?", 1)[1]
        for pair in qs.split(b"&"):
            if b"=" in pair:
                k, v = pair.split(b"=", 1)
                out[k] = v
    return out

_200 = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
_404 = b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"

async def _client(reader, writer):
    global brake_pwm
    try:
        line = await asyncio.wait_for(reader.readline(), 4)
        if not line:
            return
        # drain remaining headers (don't care about them)
        while True:
            h = await asyncio.wait_for(reader.readline(), 2)
            if h in (b"\r\n", b""):
                break

        parts = line.split(b" ")
        if len(parts) < 2:
            return
        path = parts[1]

        if path == b"/" or path == b"":
            body = _make_html()
            hdr = (
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() +
                b"\r\nConnection: close\r\n\r\n"
            )
            writer.write(hdr + body)

        elif path.startswith(b"/c"):
            p = _parse_qs(path)
            m = p.get(b"m", b"")
            d = p.get(b"d", b"").decode()
            if m == b"tilt":
                tilt_cmd(d)
            elif m == b"ext":
                ext_cmd(d)
            elif m == b"brake":
                brake_pwm = max(0, min(65535, int(d)))
                tilt.brake(brake_pwm)       # apply immediately if already braking
            elif m == b"stop":
                all_stop()
            writer.write(_200)

        elif path.startswith(b"/led"):
            p = _parse_qs(path)
            name = p.get(b"n", b"")
            val  = p.get(b"v", b"0") == b"1"
            if   name == b"status": status_led.value(val)
            elif name == b"button": button_led.value(val)
            writer.write(_200)

        else:
            writer.write(_404)

        await writer.drain()
    except Exception as e:
        print("ERR", e)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except:
            pass

async def main():
    server = await asyncio.start_server(_client, "0.0.0.0", 80, backlog=4)
    print("HTTP server on :80")
    while True:
        await asyncio.sleep(3600)

asyncio.run(main())

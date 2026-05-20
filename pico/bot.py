"""
bot.py — single-file Pico W robot controller
Flash this as main.py on the Pico.

WiFi AP:  PicoBot / robotsrule   →   http://192.168.4.1
"""

import network
import uasyncio as asyncio
from machine import Pin, PWM
import time

# ── Tunable defaults (all adjustable at runtime via sliders) ─────────────
SSID             = "PicoBot"
PASSWORD         = "robotsrule"

TILT_SPEED       = 20_000
EXT_FWD_SPEED    = 22_000
EXT_BCK_SPEED    = 26_000
SCOOP_FWD_SPEED  = 30_000
SCOOP_BCK_SPEED  = 30_000
TILT_BRAKE_PWM   = 6_000        # upward hold — increase if arm drops

JOLT_DUTY        = 35_000
JOLT_MS          = 70

PWM_FREQ         = 1_000

# ── BTS7960 driver ───────────────────────────────────────────────────────
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

    def coast(self):
        self.l.duty_u16(0)
        self.r.duty_u16(0)

# ── Hardware ─────────────────────────────────────────────────────────────
tilt  = BTS7960(lpwm_pin=0,  rpwm_pin=1)
ext   = BTS7960(lpwm_pin=6,  rpwm_pin=7)
scoop = BTS7960(lpwm_pin=20, rpwm_pin=21)  # ⚠ GP20/21 share PWM slice with GP4/5 (wheels)

status_led = Pin(9,  Pin.OUT)
button_led = Pin(10, Pin.OUT)

# ── Mutable speed state ──────────────────────────────────────────────────
spd = {
    "tilt_up":   TILT_SPEED,
    "ext_fwd":   EXT_FWD_SPEED,
    "ext_bck":   EXT_BCK_SPEED,
    "scoop_fwd": SCOOP_FWD_SPEED,
    "scoop_bck": SCOOP_BCK_SPEED,
    "brake":     TILT_BRAKE_PWM,
}

_tilt_task  = None
_ext_task   = None
_scoop_task = None

def _cancel(task):
    if task is not None:
        try: task.cancel()
        except: pass

async def _tilt_run():
    tilt.forward(JOLT_DUTY)
    await asyncio.sleep_ms(JOLT_MS)
    tilt.forward(spd["tilt_up"])
    await asyncio.sleep_ms(60_000)

async def _ext_run(direction):
    duty = spd["ext_fwd"] if direction == "fwd" else spd["ext_bck"]
    if direction == "fwd": ext.forward(JOLT_DUTY)
    else:                  ext.backward(JOLT_DUTY)
    await asyncio.sleep_ms(JOLT_MS)
    if direction == "fwd": ext.forward(duty)
    else:                  ext.backward(duty)
    await asyncio.sleep_ms(60_000)

async def _scoop_run(direction):
    duty = spd["scoop_fwd"] if direction == "fwd" else spd["scoop_bck"]
    if direction == "fwd": scoop.forward(JOLT_DUTY)
    else:                  scoop.backward(JOLT_DUTY)
    await asyncio.sleep_ms(JOLT_MS)
    if direction == "fwd": scoop.forward(duty)
    else:                  scoop.backward(duty)
    await asyncio.sleep_ms(60_000)

def tilt_cmd(cmd):
    global _tilt_task
    _cancel(_tilt_task); _tilt_task = None
    if cmd == "up":
        _tilt_task = asyncio.create_task(_tilt_run())
    elif cmd == "brake":
        tilt.forward(spd["brake"])
    else:  # "down" or "coast" — let gravity do the work
        tilt.coast()

def ext_cmd(cmd):
    global _ext_task
    _cancel(_ext_task); _ext_task = None
    if cmd in ("fwd", "bck"):
        _ext_task = asyncio.create_task(_ext_run(cmd))
    else:
        ext.coast()

def scoop_cmd(cmd):
    global _scoop_task
    _cancel(_scoop_task); _scoop_task = None
    if cmd in ("fwd", "bck"):
        _scoop_task = asyncio.create_task(_scoop_run(cmd))
    else:
        scoop.coast()

def all_stop():
    global _tilt_task, _ext_task, _scoop_task
    _cancel(_tilt_task);  _tilt_task  = None
    _cancel(_ext_task);   _ext_task   = None
    _cancel(_scoop_task); _scoop_task = None
    tilt.forward(spd["brake"])
    ext.coast()
    scoop.coast()

all_stop()

# ── WiFi AP ──────────────────────────────────────────────────────────────
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=SSID, password=PASSWORD)
while not ap.active():
    time.sleep(0.05)
print("AP up:", ap.ifconfig()[0])

# ── Web UI ───────────────────────────────────────────────────────────────
# Placeholders replaced at serve time: TSPD, EFSPD, EBSPD, BPWM
_HTML = b"""\
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
.row{display:flex;gap:8px;justify-content:center;margin-bottom:8px}
button{
  flex:1;padding:20px 6px;font-size:1rem;border:none;border-radius:10px;
  background:#2a2a2a;color:#ddd;cursor:pointer;transition:background .08s;
  -webkit-user-select:none;user-select:none;touch-action:none
}
button:active,.lit{background:#0af!important;color:#000!important}
.brake-btn{background:#7a4a00}
.stop-btn{background:#5a0000;color:#f88;font-size:1.1rem;padding:22px;width:100%}
.stop-btn:active{background:#c00!important;color:#fff!important}
.sl{display:flex;flex-direction:column;align-items:center;margin-top:6px;gap:2px}
.sl label{font-size:.8rem;color:#aaa}
.sl span{color:#0af;font-weight:600}
input[type=range]{width:92%;accent-color:#0af}
</style>
</head>
<body>
<h1>PicoBot</h1>
<p class="ip">192.168.4.1</p>

<div class="card">
  <h2>Tilt</h2>
  <div class="row">
    <button ontouchstart="go('tilt','up')"    ontouchend="go('tilt','brake')"
            onmousedown="go('tilt','up')"     onmouseup="go('tilt','brake')"
            onmouseleave="go('tilt','brake')">&#9650; Up</button>
    <button class="brake-btn" onclick="go('tilt','brake')">&#9646; Hold</button>
    <button onclick="go('tilt','down')">&#9660; Drop</button>
  </div>
  <div class="sl">
    <label>Up speed: <span id="tv">TSPD</span></label>
    <input type="range" min="0" max="65535" step="500" value="TSPD"
      oninput="document.getElementById('tv').textContent=this.value"
      onchange="setspd('tilt_up',this.value)">
  </div>
  <div class="sl">
    <label>Hold PWM: <span id="bv">BPWM</span></label>
    <input type="range" min="0" max="65535" step="500" value="BPWM"
      oninput="document.getElementById('bv').textContent=this.value"
      onchange="setspd('brake',this.value)">
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
  <div class="sl">
    <label>Out speed: <span id="efv">EFSPD</span></label>
    <input type="range" min="0" max="65535" step="500" value="EFSPD"
      oninput="document.getElementById('efv').textContent=this.value"
      onchange="setspd('ext_fwd',this.value)">
  </div>
  <div class="sl">
    <label>In speed: <span id="ebv">EBSPD</span></label>
    <input type="range" min="0" max="65535" step="500" value="EBSPD"
      oninput="document.getElementById('ebv').textContent=this.value"
      onchange="setspd('ext_bck',this.value)">
  </div>
</div>

<div class="card">
  <h2>Scoop</h2>
  <div class="row">
    <button ontouchstart="go('scoop','fwd')" ontouchend="go('scoop','stop')"
            onmousedown="go('scoop','fwd')"  onmouseup="go('scoop','stop')"
            onmouseleave="go('scoop','stop')">&#9654; Open</button>
    <button ontouchstart="go('scoop','bck')" ontouchend="go('scoop','stop')"
            onmousedown="go('scoop','bck')"  onmouseup="go('scoop','stop')"
            onmouseleave="go('scoop','stop')">&#9664; Close</button>
  </div>
  <div class="sl">
    <label>Open speed: <span id="sfv">SFSPD</span></label>
    <input type="range" min="0" max="65535" step="500" value="SFSPD"
      oninput="document.getElementById('sfv').textContent=this.value"
      onchange="setspd('scoop_fwd',this.value)">
  </div>
  <div class="sl">
    <label>Close speed: <span id="sbv">SBSPD</span></label>
    <input type="range" min="0" max="65535" step="500" value="SBSPD"
      oninput="document.getElementById('sbv').textContent=this.value"
      onchange="setspd('scoop_bck',this.value)">
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
async function setspd(k,v){
  try{await fetch('/spd?k='+k+'&v='+v,{method:'POST',keepalive:true})}catch(e){}
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
    h = _HTML
    h = h.replace(b"TSPD",  str(spd["tilt_up"]).encode())
    h = h.replace(b"EFSPD", str(spd["ext_fwd"]).encode())
    h = h.replace(b"EBSPD", str(spd["ext_bck"]).encode())
    h = h.replace(b"SFSPD", str(spd["scoop_fwd"]).encode())
    h = h.replace(b"SBSPD", str(spd["scoop_bck"]).encode())
    h = h.replace(b"BPWM",  str(spd["brake"]).encode())
    return h

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
    try:
        line = await asyncio.wait_for(reader.readline(), 4)
        if not line:
            return
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
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(body)).encode() +
                b"\r\nConnection: close\r\n\r\n" + body
            )

        elif path.startswith(b"/c"):
            p = _parse_qs(path)
            m = p.get(b"m", b"")
            d = p.get(b"d", b"").decode()
            if   m == b"tilt":  tilt_cmd(d)
            elif m == b"ext":   ext_cmd(d)
            elif m == b"scoop": scoop_cmd(d)
            elif m == b"stop":  all_stop()
            writer.write(_200)

        elif path.startswith(b"/spd"):
            p = _parse_qs(path)
            k = p.get(b"k", b"").decode()
            v = max(0, min(65535, int(p.get(b"v", b"0"))))
            if k in spd:
                spd[k] = v
                if k == "brake":
                    tilt.forward(v)     # apply new hold immediately
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
        try: await writer.wait_closed()
        except: pass

async def main():
    server = await asyncio.start_server(_client, "0.0.0.0", 80, backlog=4)
    print("HTTP server on :80")
    while True:
        await asyncio.sleep(3600)

asyncio.run(main())

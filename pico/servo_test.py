"""
servo_test.py — steps servo to 0°, 90°, 180° in a loop
Servo signal: GP15  (change SERVO_PIN if needed)
Servo power:  VBUS (pin 40) = 5V from USB  <-- use this, NOT 3.3V
Servo GND:    any GND pin
"""

from machine import Pin, PWM
import utime

SERVO_PIN = 15
MIN_US    = 500     # pulse for 0°   — widen toward 1000 if servo doesn't reach end
MAX_US    = 2500    # pulse for 180° — narrow toward 2000 if servo grinds at end

servo = PWM(Pin(SERVO_PIN), freq=50)

def move(deg):
    us   = MIN_US + (MAX_US - MIN_US) * deg // 180
    duty = int(us / 20_000 * 65535)
    servo.duty_u16(duty)
    print("angle:", deg, "  pulse us:", us)

while True:
    move(0)
    utime.sleep_ms(1000)
    move(90)
    utime.sleep_ms(1000)
    move(180)
    utime.sleep_ms(1000)

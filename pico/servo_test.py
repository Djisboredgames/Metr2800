"""
servo_test.py — sweeps a servo back and forth
Servo signal pin: GP15 (change SERVO_PIN if needed)
"""

from machine import Pin, PWM
import utime

SERVO_PIN = 15
PWM_FREQ  = 50       # Hz — standard servo frequency

# Pulse widths in microseconds
MIN_US = 500         # ~0°
MAX_US = 2500        # ~180°

servo = PWM(Pin(SERVO_PIN), freq=PWM_FREQ)

def set_us(us):
    # Convert microseconds to 16-bit duty cycle at 50Hz (period = 20000us)
    duty = int(us / 20_000 * 65535)
    servo.duty_u16(duty)

def set_angle(deg):
    us = MIN_US + (MAX_US - MIN_US) * deg // 180
    set_us(us)

# Sweep back and forth
while True:
    for angle in range(0, 181, 2):
        set_angle(angle)
        utime.sleep_ms(10)
    for angle in range(180, -1, -2):
        set_angle(angle)
        utime.sleep_ms(10)

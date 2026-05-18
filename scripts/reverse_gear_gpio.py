#!/usr/bin/env python3

import time
import RPi.GPIO as GPIO


REVERSE_PIN = 17


GPIO.setmode(GPIO.BCM)
GPIO.setup(REVERSE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)



try:
    while True:
        print("is r ?" + GPIO.input(REVERSE_PIN) == GPIO.LOW)
        time.sleep(1)
finally:
    GPIO.cleanup(REVERSE_PIN)

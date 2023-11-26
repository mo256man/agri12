import RPi.GPIO as GPIO
from time import sleep

relay_pin = 22
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.cleanup()
GPIO.setup(relay_pin, GPIO.OUT)
value = False

while True:
	GPIO.output(relay_pin, value)
	print(value)
	value = not value
	sleep(2)

import RPi.GPIO as GPIO
import dht11
import time

humi_pin = 14

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

humi_sensor = dht11.DHT11(pin=humi_pin)

try:
    while True:
        result = humi_sensor.read()
        if result.is_valid():
            temp = round(result.temperature, 1)		# 温度 小数第一位まで
            humi = round(result.humidity, 1)    	# 湿度 小数第一位まで
        else:
            temp = "N/A"
            humi = "N/A"
        print(f"温度: {temp}℃, 湿度: {humi}%")
        time.sleep(1)

except KeyboardInterrupt:
    print("end")
    GPIO.cleanup()
    time.sleep(3)

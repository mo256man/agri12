import time
import datetime
from gpiozero import MCP3004

Vref = 5

def analog_read(ch):
    adc = MCP3004(channel = ch, max_voltage=5)
    volt = adc.value * Vref
    return volt

def main():
    try:
        while True:
            val0 = analog_read(ch=0)
            val3 = analog_read(ch=3)
            now = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"{now} : ch3={val3:.2f}V, ch0={val0:.2f}V")
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()


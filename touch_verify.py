import spidev, RPi.GPIO as GPIO, json, time, os
from luma.core.interface.serial import bitbang
from luma.lcd.device import ili9341
from luma.core.render import canvas
from PIL import ImageFont

serial  = bitbang(SCLK=16, SDA=20, CE=21, DC=26, RST=19)
display = ili9341(serial, width=320, height=240, rotate=1)
DISP_W, DISP_H = display.size

try:
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
except:
    font = ImageFont.load_default()

T_IRQ = 27
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(T_IRQ, GPIO.IN)

spi = spidev.SpiDev()
spi.open(0, 1)
spi.max_speed_hz = 1_000_000
spi.mode = 0

cal = json.load(open("touch_calibration.json")) if os.path.exists(
    "touch_calibration.json") else {
    "x_min":593,"x_max":3497,"y_min":429,"y_max":3689,
    "swap_xy":False,"flip_x":True,"flip_y":False}

def read_raw():
    x = spi.xfer2([0xD0, 0x00, 0x00])
    y = spi.xfer2([0x90, 0x00, 0x00])
    return ((x[1]<<8)|x[2])>>3, ((y[1]<<8)|y[2])>>3

def is_touched():
    return GPIO.input(T_IRQ) == GPIO.LOW

def get_touch():
    if not is_touched(): return None
    samples = []
    for _ in range(5):
        if is_touched(): samples.append(read_raw())
        time.sleep(0.01)
    if not samples: return None
    rx = sum(s[0] for s in samples)//len(samples)
    ry = sum(s[1] for s in samples)//len(samples)
    if cal["swap_xy"]: rx, ry = ry, rx
    x = (rx-cal["x_min"])/max(cal["x_max"]-cal["x_min"],1)
    y = (ry-cal["y_min"])/max(cal["y_max"]-cal["y_min"],1)
    if cal["flip_x"]: x = 1.0-x
    if cal["flip_y"]: y = 1.0-y
    return int(max(0.0,min(1.0,x))*DISP_W), int(max(0.0,min(1.0,y))*DISP_H)

with canvas(display) as draw:
    draw.rectangle(display.bounding_box, fill="black")
    draw.text((10,10), "TOUCH ANYWHERE", font=font, fill="cyan")
    draw.text((10,35), "Ctrl+C to stop",  font=font, fill="grey")

print("Touch the screen. Ctrl+C to stop.")
try:
    while True:
        t = get_touch()
        if t:
            px, py = t
            print(f"X={px}, Y={py}")
            with canvas(display) as draw:
                draw.rectangle(display.bounding_box, fill="black")
                draw.ellipse((px-10,py-10,px+10,py+10), fill="lime")
                draw.text((8,8), f"X={px}  Y={py}", font=font, fill="white")
            while is_touched(): time.sleep(0.05)
            time.sleep(0.3)
        time.sleep(0.05)
except KeyboardInterrupt:
    print("Stopped.")
finally:
    spi.close()
    GPIO.cleanup()
import spidev, RPi.GPIO as GPIO, json, time

T_IRQ = 27
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(T_IRQ, GPIO.IN)

spi = spidev.SpiDev()
spi.open(0, 1)
spi.max_speed_hz = 1_000_000
spi.mode = 0

def read_raw():
    x = spi.xfer2([0xD0, 0x00, 0x00])
    y = spi.xfer2([0x90, 0x00, 0x00])
    return ((x[1]<<8)|x[2])>>3, ((y[1]<<8)|y[2])>>3

def is_touched():
    return GPIO.input(T_IRQ) == GPIO.LOW

def wait_touch():
    while not is_touched():
        time.sleep(0.05)
    samples = []
    for _ in range(20):
        if is_touched():
            samples.append(read_raw())
        time.sleep(0.02)
    while is_touched():
        time.sleep(0.05)
    if not samples:
        return None
    return (sum(s[0] for s in samples)//len(samples),
            sum(s[1] for s in samples)//len(samples))

print("=== TOUCH CALIBRATION ===")
results = {}
for corner in ["TOP-LEFT", "TOP-RIGHT", "BOTTOM-LEFT", "BOTTOM-RIGHT"]:
    print(f"Touch: {corner}")
    pt = wait_touch()
    results[corner] = pt
    print(f"  X={pt[0]}, Y={pt[1]}\n")
    time.sleep(0.5)

tl = results["TOP-LEFT"]
tr = results["TOP-RIGHT"]
bl = results["BOTTOM-LEFT"]
br = results["BOTTOM-RIGHT"]

cal = {
    "x_min":   min(tl[0], bl[0]),
    "x_max":   max(tr[0], br[0]),
    "y_min":   min(tl[1], tr[1]),
    "y_max":   max(bl[1], br[1]),
    "swap_xy": abs(tr[0]-tl[0]) < abs(tr[1]-tl[1]),
    "flip_x":  tl[0] > tr[0],
    "flip_y":  tl[1] > bl[1],
}

json.dump(cal, open("touch_calibration.json","w"), indent=2)
print("Saved to touch_calibration.json")
print(cal)
spi.close()
GPIO.cleanup()
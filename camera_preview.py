import time
from luma.core.interface.serial import bitbang
from luma.lcd.device import ili9341
from picamera2 import Picamera2
from PIL import Image, ImageDraw, ImageFont

serial  = bitbang(SCLK=16, SDA=20, CE=21, DC=26, RST=19)
display = ili9341(serial, width=320, height=240, rotate=1)
DISP_W, DISP_H = display.size

try:
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
except:
    font = ImageFont.load_default()

picam2 = Picamera2(0)
picam2.configure(picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"}))
picam2.start()
time.sleep(1)

print("Camera preview on display. Ctrl+C to stop.")
try:
    while True:
        frame = picam2.capture_array()
        img   = Image.fromarray(frame).convert("RGB")
        img   = img.rotate(90, expand=True).resize((DISP_W, DISP_H))
        draw  = ImageDraw.Draw(img)
        draw.rectangle((0,0,DISP_W,24), fill=(0,0,80))
        draw.text((5,4), "CAMERA PREVIEW", font=font, fill="cyan")
        display.display(img)
except KeyboardInterrupt:
    picam2.stop()
    print("Stopped.")
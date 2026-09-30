import time
from luma.core.interface.serial import bitbang
from luma.core.render import canvas
from luma.lcd.device import ili9341
from PIL import ImageFont

serial  = bitbang(SCLK=16, SDA=20, CE=21, DC=26, RST=19)
display = ili9341(serial, width=320, height=240, rotate=1)

try:
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font2 = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except:
    font = font2 = ImageFont.load_default()

with canvas(display) as draw:
    draw.rectangle(display.bounding_box, fill="black")
    draw.rectangle((0,0,240,40), fill=(0,30,60))
    draw.text((10,5),   "DISPLAY TEST",  font=font,  fill="cyan")
    draw.text((10,55),  "ILI9341 OK",    font=font2, fill="lime")
    draw.text((10,85),  "Software SPI",  font=font2, fill="white")
    draw.text((10,115), "240 x 320 px",  font=font2, fill="yellow")
    draw.rectangle((10,175,230,200), fill=(0,100,0))
    draw.text((70,180), "GREEN BAR",     font=font2, fill="white")
    draw.rectangle((10,210,230,235), fill=(100,0,0))
    draw.text((75,215), "RED BAR",       font=font2, fill="white")

print("Test screen shown. Ctrl+C to exit.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped.")
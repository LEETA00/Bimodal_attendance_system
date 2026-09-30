import time, json, pickle, numpy as np, os, sqlite3, spidev
from datetime import datetime
from luma.core.interface.serial import bitbang
from luma.lcd.device import ili9341
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO
from PIL import ImageFont, Image, ImageDraw as PILDraw
import face_recognition
from picamera2 import Picamera2
import gspread
from google.oauth2.service_account import Credentials

# ── Display ───────────────────────────────────────────────
serial  = bitbang(SCLK=16, SDA=20, CE=21, DC=26, RST=19)
display = ili9341(serial, width=320, height=240, rotate=1)
DISP_W, DISP_H = display.size

# ── Fonts ─────────────────────────────────────────────────
try:
    F22 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    F18 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    F16 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    F14 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except:
    F22 = F18 = F16 = F14 = ImageFont.load_default()

# ── Touch ─────────────────────────────────────────────────
T_IRQ = 27
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(T_IRQ, GPIO.IN)

touch_spi = spidev.SpiDev()
touch_spi.open(0, 1)
touch_spi.max_speed_hz = 1_000_000
touch_spi.mode = 0

CAL_FILE = "touch_calibration.json"
cal = json.load(open(CAL_FILE)) if os.path.exists(CAL_FILE) else {
    "x_min": 593, "x_max": 3497,
    "y_min": 429, "y_max": 3689,
    "swap_xy": False, "flip_x": True, "flip_y": False
}

def read_touch_raw():
    x = touch_spi.xfer2([0xD0, 0x00, 0x00])
    y = touch_spi.xfer2([0x90, 0x00, 0x00])
    return ((x[1] << 8) | x[2]) >> 3, ((y[1] << 8) | y[2]) >> 3

def is_touched():
    return GPIO.input(T_IRQ) == GPIO.LOW

def get_touch():
    if not is_touched():
        return None
    samples = []
    for _ in range(5):
        if is_touched():
            samples.append(read_touch_raw())
        time.sleep(0.01)
    if not samples:
        return None
    rx = sum(s[0] for s in samples) // len(samples)
    ry = sum(s[1] for s in samples) // len(samples)
    if cal["swap_xy"]:
        rx, ry = ry, rx
    x = (rx - cal["x_min"]) / max(cal["x_max"] - cal["x_min"], 1)
    y = (ry - cal["y_min"]) / max(cal["y_max"] - cal["y_min"], 1)
    if cal["flip_x"]: x = 1.0 - x
    if cal["flip_y"]: y = 1.0 - y
    return int(max(0.0, min(1.0, x)) * DISP_W), int(max(0.0, min(1.0, y)) * DISP_H)

def wait_for_touch(timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        t = get_touch()
        if t:
            while is_touched():
                time.sleep(0.05)
            return t
        time.sleep(0.05)
    return None

# ── RFID ──────────────────────────────────────────────────
reader = SimpleMFRC522()

# ── Google Sheets ─────────────────────────────────────────
SCOPES = ["https://spreadsheets.google.com/feeds",
          "https://www.googleapis.com/auth/drive"]
creds  = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheet  = client.open("Attendance Log").sheet1

# ── Database ──────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("attendance.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, name TEXT, mode TEXT, method TEXT)""")
    conn.commit()
    conn.close()

def already_logged(name, minutes=180):
    if minutes == 0:
        return False
    conn = sqlite3.connect("attendance.db")
    row  = conn.execute(
        "SELECT timestamp FROM attendance WHERE name=? ORDER BY id DESC LIMIT 1",
        (name,)).fetchone()
    conn.close()
    if not row:
        return False
    last = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    return (datetime.now() - last).total_seconds() / 60 < minutes

def log_local(name, mode, method):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("attendance.db")
    conn.execute(
        "INSERT INTO attendance (timestamp,name,mode,method) VALUES (?,?,?,?)",
        (ts, name, mode, method))
    conn.commit()
    conn.close()
    return ts

def log_sheets(ts, name, mode, method):
    try:
        sheet.append_row([ts, name, mode, method])
    except Exception as e:
        print(f"[Sheets] {e}")

def log_attendance(name, mode, method):
    ts = log_local(name, mode, method)
    log_sheets(ts, name, mode, method)
    print(f"[LOG] {ts} {name} {mode} {method}")

# ── Data ──────────────────────────────────────────────────
REGISTRY_FILE  = "card_registry.json"
ENCODINGS_FILE = "known_faces.pkl"

def load_registry():
    return json.load(open(REGISTRY_FILE)) if os.path.exists(REGISTRY_FILE) else {}

def save_registry(d):
    json.dump(d, open(REGISTRY_FILE, "w"), indent=2)

def load_faces():
    return pickle.load(open(ENCODINGS_FILE, "rb")) if os.path.exists(ENCODINGS_FILE) else {}

def save_faces(d):
    pickle.dump(d, open(ENCODINGS_FILE, "wb"))

card_registry = load_registry()
known_faces   = load_faces()

# ── Display Helpers ───────────────────────────────────────
def now_str():
    return datetime.now().strftime("%d %b %Y  %H:%M")

def show_screen(title, l1="", l2="", l3="", l4="", tc="green"):
    img  = Image.new("RGB", (DISP_W, DISP_H), (0, 0, 0))
    draw = PILDraw.Draw(img)
    draw.rectangle((0, 0, DISP_W, 40), fill=(0, 30, 60))
    draw.text((8, 8),   title, font=F22, fill=tc)
    draw.text((8, 50),  l1,    font=F18, fill="white")
    draw.text((8, 78),  l2,    font=F18, fill="cyan")
    draw.text((8, 106), l3,    font=F16, fill="yellow")
    draw.text((8, 130), l4,    font=F16, fill="grey")
    draw.rectangle((0, DISP_H-28, DISP_W, DISP_H), fill=(20, 20, 20))
    draw.text((8, DISP_H-22), now_str(), font=F16, fill="#666666")
    display.display(img)

def show_preview(picam2, countdown=None, prompt="Look at camera"):
    frame = picam2.capture_array()
    img   = Image.fromarray(frame).convert("RGB")
    img   = img.rotate(90, expand=True).resize((DISP_W, DISP_H))
    draw  = PILDraw.Draw(img)
    draw.rectangle((0, 0, DISP_W, 28), fill=(0, 0, 80))
    draw.text((5, 5), prompt, font=F16, fill="cyan")
    if countdown is not None:
        draw.text((DISP_W-30, 5), str(countdown), font=F16, fill="yellow")
    draw.rectangle((0, DISP_H-28, DISP_W, DISP_H), fill=(20, 20, 20))
    draw.text((5, DISP_H-22), now_str(), font=F16, fill="#666666")
    display.display(img)
    return frame

# ── Face Match ────────────────────────────────────────────
def match_face(frame, tolerance=0.5):
    encs = face_recognition.face_encodings(frame)
    if not encs:
        return None
    names = list(known_faces.keys())
    dists = face_recognition.face_distance(list(known_faces.values()), encs[0])
    best  = int(np.argmin(dists))
    return names[best] if dists[best] <= tolerance else None

# ── On-Screen Keyboard ────────────────────────────────────
KEYS = [
    ["A","B","C","D","E"],
    ["F","G","H","I","J"],
    ["K","L","M","N","O"],
    ["P","Q","R","S","T"],
    ["U","V","W","X","Y"],
    ["Z","SPC","DEL","-","OK"],
]
KB_Y  = 95
KEY_H = (DISP_H - KB_Y) // len(KEYS)
KEY_W = DISP_W // 5

def draw_keyboard(typed):
    img  = Image.new("RGB", (DISP_W, DISP_H), (0, 0, 0))
    draw = PILDraw.Draw(img)
    draw.rectangle((0, 0, DISP_W, KB_Y-2), fill=(0, 20, 50))
    draw.text((8, 5),  "Enter name:", font=F16, fill="cyan")
    draw.rectangle((4, 28, DISP_W-4, KB_Y-6), fill=(0, 40, 90))
    draw.text((8, 33), (typed+"|")[-16:], font=F18, fill="white")
    for ri, row in enumerate(KEYS):
        for ci, key in enumerate(row):
            x  = ci * KEY_W
            y  = KB_Y + ri * KEY_H
            bg = (0,90,0) if key=="OK" else (70,30,0) if key in ("DEL","SPC") else (25,25,65)
            draw.rectangle((x+1, y+1, x+KEY_W-2, y+KEY_H-2),
                           fill=bg, outline="#555555")
            draw.text((x+4, y+KEY_H//2-7), key, font=F14,
                      fill="lime" if key=="OK" else "white")
    display.display(img)

def on_screen_keyboard():
    typed = ""
    draw_keyboard(typed)
    while True:
        t = wait_for_touch(timeout=60)
        if t is None:
            return typed.strip()
        ty2 = t[1]
        if ty2 < KB_Y:
            continue
        row = (ty2 - KB_Y) // KEY_H
        col = t[0] // KEY_W
        if not (0 <= row < len(KEYS) and 0 <= col < 5):
            continue
        key = KEYS[row][col]
        if key == "DEL":
            typed = typed[:-1]
        elif key == "SPC":
            typed += " "
        elif key == "-":
            typed += "-"
        elif key == "OK":
            if typed.strip():
                return typed.strip()
        else:
            typed += key
        draw_keyboard(typed)

# ── Mode Menu ─────────────────────────────────────────────
MENU_BTNS = [
    ("Class Attendance", "class",    (0, 100, 30)),
    ("Exam Mode",        "exam",     (0, 60,  130)),
    ("Custom Mode",      "custom",   (90, 60, 0)),
    ("Register Person",  "register", (0, 90,  80)),
    ("Event Mode",       "event",    (90, 0,  90)),
]
BTN_Y0 = 45
BTN_H  = 48
BTN_G  = 4

def show_menu():
    img  = Image.new("RGB", (DISP_W, DISP_H), (0, 0, 0))
    draw = PILDraw.Draw(img)
    draw.rectangle((0, 0, DISP_W, BTN_Y0-2), fill=(0, 25, 60))
    draw.text((8, 5),  "ATTENDANCE", font=F22, fill="cyan")
    draw.text((8, 28), "SYSTEM",     font=F16, fill="#5588bb")
    for i, (label, mode, color) in enumerate(MENU_BTNS):
        y = BTN_Y0 + i * (BTN_H + BTN_G)
        draw.rectangle((4, y, DISP_W-4, y+BTN_H),
                       fill=color, outline="#888888")
        draw.text((12, y+BTN_H//2-9), label, font=F18, fill="white")
    draw.rectangle((0, DISP_H-28, DISP_W, DISP_H), fill=(20, 20, 20))
    draw.text((8, DISP_H-22), now_str(), font=F16, fill="#666666")
    display.display(img)

def get_mode():
    show_menu()
    while True:
        t = wait_for_touch(timeout=30)
        if t is None:
            show_menu()
            continue
        tx, ty = t
        for i, (label, mode, color) in enumerate(MENU_BTNS):
            y = BTN_Y0 + i * (BTN_H + BTN_G)
            if y <= ty <= y+BTN_H and 4 <= tx <= DISP_W-4:
                show_screen(f"Mode: {label}", "Loading...", "", "", "", "cyan")
                time.sleep(0.5)
                return mode

# ── Registration ──────────────────────────────────────────
def register_card_step(name):
    global card_registry
    show_screen("REGISTER CARD", f"Name: {name}",
                "Tap RFID card now", "Waiting 20s...", "", "lime")
    start = time.time()
    while time.time() - start < 20:
        card_id, _ = reader.read_no_block()
        if card_id:
            card_registry = load_registry()
            card_registry[str(card_id)] = name
            save_registry(card_registry)
            show_screen("CARD SAVED!", f"Name: {name}",
                        f"ID: {str(card_id)[:14]}", "", "", "lime")
            time.sleep(2)
            return True
        time.sleep(0.2)
    show_screen("TIMED OUT", "No card detected", "", "", "", "red")
    time.sleep(2)
    return False

def register_face_step(name):
    global known_faces
    picam2 = Picamera2(0)
    picam2.configure(picam2.create_video_configuration(
        main={"size": (320, 240), "format": "RGB888"}))
    picam2.start()
    time.sleep(1)
    start = time.time()
    while time.time() - start < 5:
        frame = picam2.capture_array()
        img   = Image.fromarray(frame).convert("RGB")
        img   = img.rotate(90, expand=True).resize((DISP_W, DISP_H))
        draw  = PILDraw.Draw(img)
        remaining = int(5 - (time.time() - start)) + 1
        draw.rectangle((0, 0, DISP_W, 30), fill=(0, 60, 0))
        draw.text((5, 7), f"Position face! Capturing in {remaining}s",
                  font=F14, fill="lime")
        draw.rectangle((0, DISP_H-28, DISP_W, DISP_H), fill=(20, 20, 20))
        draw.text((5, DISP_H-22), now_str(), font=F16, fill="#666666")
        display.display(img)
    picam2.stop()
    picam2.close()

    picam2 = Picamera2(0)
    picam2.configure(picam2.create_still_configuration(
        main={"size": (640, 480), "format": "RGB888"}))
    picam2.start()
    time.sleep(2)
    show_screen("CAPTURING", "Hold perfectly still!", "Processing...", "", "", "lime")
    frame = picam2.capture_array()
    picam2.stop()
    picam2.close()

    encodings = face_recognition.face_encodings(frame)
    if not encodings:
        show_screen("NO FACE FOUND", "Better lighting needed",
                    "Face camera directly", "", "", "red")
        time.sleep(3)
        return False

    known_faces = load_faces()
    known_faces[name] = encodings[0]
    save_faces(known_faces)
    show_screen("FACE SAVED!", f"{name} enrolled",
                "Face registered OK", "", "", "lime")
    time.sleep(2)
    return True

def run_registration():
    show_screen("REGISTRATION", "On-screen keyboard",
                "Type name then tap OK", "", "", "lime")
    time.sleep(1)
    name = on_screen_keyboard()
    if not name:
        show_screen("CANCELLED", "No name entered",
                    "Returning to menu", "", "", "grey")
        time.sleep(2)
        return

    show_screen("CONFIRM NAME?", name, "Tap screen = YES",
                "Wait 5s = CANCEL", "", "lime")
    if wait_for_touch(timeout=5) is None:
        show_screen("CANCELLED", "Returning to menu", "", "", "", "grey")
        time.sleep(2)
        return

    show_screen("STEP 1 / 2", "CARD REGISTRATION",
                f"Name: {name}", "Tap card now...", "", "lime")
    card_ok = register_card_step(name)
    if not card_ok:
        show_screen("CARD SKIPPED", "Continuing to face...",
                    "", "", "", "orange")
        time.sleep(1)

    show_screen("STEP 2 / 2", "FACE ENROLLMENT",
                f"Name: {name}", "Look at camera...", "", "lime")
    time.sleep(1)
    face_ok = register_face_step(name)

    if card_ok and face_ok:
        show_screen("COMPLETE!", name, "Card: OK", "Face: OK",
                    "Ready to attend!", "lime")
    elif card_ok:
        show_screen("PARTIAL", name, "Card: OK", "Face: FAILED",
                    "Re-enrol face later", "orange")
    elif face_ok:
        show_screen("PARTIAL", name, "Card: FAILED", "Face: OK",
                    "Re-register card later", "orange")
    else:
        show_screen("FAILED", name, "Both failed",
                    "Please try again", "", "red")
    time.sleep(3)

    show_screen("REGISTER ANOTHER?", "Tap screen = Yes",
                "Wait 5s = Exit", "", "", "cyan")
    if wait_for_touch(timeout=5):
        run_registration()

# ── Sequential Mode ───────────────────────────────────────
def run_sequential(mode_name, tolerance=0.5, dup_minutes=180):
    while True:
        show_screen("STEP 1 / 2", "Tap your RFID card",
                    "Waiting...", "Tap 3x fast to exit", "", "cyan")
        rfid_name = None
        start     = time.time()
        taps      = 0
        last_tap  = 0
        while time.time() - start < 15:
            card_id, _ = reader.read_no_block()
            if card_id and time.time() - last_tap > 0.4:
                taps    += 1
                last_tap = time.time()
                if taps == 1:
                    rfid_name = card_registry.get(str(card_id))
                if taps >= 3:
                    show_screen("Exiting...", "", "", "", "", "grey")
                    time.sleep(1)
                    return
            if rfid_name:
                break
            time.sleep(0.2)

        if not rfid_name:
            show_screen("TIMED OUT", "No card detected",
                        "Returning to menu", "", "", "red")
            time.sleep(2)
            return

        if already_logged(rfid_name, dup_minutes):
            show_screen("ALREADY LOGGED", rfid_name,
                        "Already marked", "Try again later", "", "orange")
            time.sleep(3)
            return

        show_screen("STEP 2 / 2", f"Hi {rfid_name}!",
                    "Look at the camera", "", "", "green")
        time.sleep(1)

        picam2 = Picamera2(0)
        picam2.configure(picam2.create_video_configuration(
            main={"size": (320, 240), "format": "RGB888"}))
        picam2.start()
        time.sleep(1)

        face_name  = None
        scan_start = time.time()
        timeout    = 10
        while time.time() - scan_start < timeout:
            remaining = int(timeout - (time.time() - scan_start))
            frame     = show_preview(picam2, countdown=remaining,
                                     prompt=f"Hi {rfid_name}! Look here")
            face_name = match_face(frame, tolerance)
            if face_name:
                break
            time.sleep(0.3)
        picam2.stop()
        picam2.close()

        if face_name == rfid_name:
            show_screen("WELCOME!", rfid_name,
                        f"{mode_name} recorded", "", "", "green")
            log_attendance(rfid_name, mode_name, "rfid+face")
            time.sleep(2)
            show_screen("NEXT?", "Tap screen = scan another",
                        "Wait 5s = exit mode", "", "", "cyan")
            if wait_for_touch(timeout=5) is None:
                return
        else:
            show_screen("FAILED", "Face does not match",
                        "card identity", "", "", "red")
            time.sleep(2)
            show_screen("RETRY?", "Tap screen = try again",
                        "Wait 5s = exit", "", "", "cyan")
            if wait_for_touch(timeout=5) is None:
                return

# ── Event Mode ────────────────────────────────────────────
def run_event():
    img  = Image.new("RGB", (DISP_W, DISP_H), (0, 0, 0))
    draw = PILDraw.Draw(img)
    draw.rectangle((0, 0, DISP_W, 40), fill=(0, 25, 60))
    draw.text((8, 8), "EVENT MODE", font=F22, fill="cyan")
    draw.text((8, 46), "Admin: Select method", font=F16, fill="white")
    draw.rectangle((8, 80, DISP_W-8, 155),
                   fill=(0, 90, 0), outline="#aaaaaa")
    draw.text((DISP_W//2-45, 108), "RFID Only", font=F18, fill="white")
    draw.rectangle((8, 165, DISP_W-8, 240),
                   fill=(0, 0, 120), outline="#aaaaaa")
    draw.text((DISP_W//2-45, 193), "Face Only", font=F18, fill="white")
    draw.rectangle((0, DISP_H-28, DISP_W, DISP_H), fill=(20, 20, 20))
    draw.text((8, DISP_H-22), now_str(), font=F16, fill="#666666")
    display.display(img)

    t = wait_for_touch(timeout=15)
    chosen = "rfid" if (t is None or t[1] < 165) else "face"
    show_screen("EVENT MODE", f"Method: {chosen.upper()}",
                "Attendees may begin", "Tap 3x card to exit", "", "cyan")
    time.sleep(1)

    while True:
        if chosen == "rfid":
            show_screen("EVENT", "Tap your RFID card",
                        "Tap 3x to exit", "", "", "cyan")
            start    = time.time()
            card_id  = None
            taps     = 0
            last_tap = 0
            while time.time() - start < 15:
                cid, _ = reader.read_no_block()
                if cid and time.time() - last_tap > 0.4:
                    taps    += 1
                    last_tap = time.time()
                    card_id  = cid
                    if taps >= 3:
                        return
                    break
                time.sleep(0.2)
            if card_id is None:
                return
            name = card_registry.get(str(card_id))
            if name:
                if already_logged(name, 0):
                    show_screen("ALREADY LOGGED", name, "", "", "", "orange")
                else:
                    show_screen("WELCOME!", name, "Event logged",
                                "", "", "green")
                    log_attendance(name, "event", "rfid")
            else:
                show_screen("UNKNOWN CARD", "Not registered",
                            "", "", "", "red")
            time.sleep(2)

        else:
            picam2 = Picamera2(0)
            picam2.configure(picam2.create_video_configuration(
                main={"size": (320, 240), "format": "RGB888"}))
            picam2.start()
            time.sleep(1)
            name       = None
            scan_start = time.time()
            timeout    = 8
            while time.time() - scan_start < timeout:
                remaining = int(timeout - (time.time() - scan_start))
                frame = show_preview(picam2, countdown=remaining,
                                     prompt="Look at camera")
                name = match_face(frame)
                if name:
                    break
                time.sleep(0.3)
            picam2.stop()
            picam2.close()
            if name:
                if already_logged(name, 0):
                    show_screen("ALREADY LOGGED", name, "", "", "", "orange")
                else:
                    show_screen("WELCOME!", name, "Event logged",
                                "", "", "green")
                    log_attendance(name, "event", "face")
                time.sleep(2)
            else:
                show_screen("NOT FOUND", "Face not recognised",
                            "Tap screen = retry", "Wait 5s = exit", "", "red")
                if wait_for_touch(timeout=5) is None:
                    return
                continue

        show_screen("NEXT?", "Tap screen = next attendee",
                    "Wait 5s = exit event", "", "", "cyan")
        if wait_for_touch(timeout=5) is None:
            return

# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("[SYSTEM] Started.")
    try:
        while True:
            mode = get_mode()
            print(f"[MODE] {mode}")
            if   mode == "class":    run_sequential("Class Attendance", 0.5, 180)
            elif mode == "exam":     run_sequential("Exam Mode",        0.4, 1440)
            elif mode == "custom":   run_sequential("Custom Mode",      0.5, 60)
            elif mode == "register": run_registration()
            elif mode == "event":    run_event()
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("[SYSTEM] Stopped.")
    finally:
        touch_spi.close()
        GPIO.cleanup()
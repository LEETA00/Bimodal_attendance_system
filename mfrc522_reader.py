import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time, json, os

REGISTRY_FILE = "card_registry.json"
reader = SimpleMFRC522()

def load_registry():
    return json.load(open(REGISTRY_FILE)) if os.path.exists(REGISTRY_FILE) else {}

print("=== RFID Reader Test ===")
print("Tap cards near the reader. Ctrl+C to stop.\n")

try:
    while True:
        card_id, _ = reader.read()
        registry = load_registry()
        name = registry.get(str(card_id), "UNREGISTERED")
        print(f"Card ID : {card_id}")
        print(f"Name    : {name}")
        print("-" * 30)
        time.sleep(2)
except KeyboardInterrupt:
    print("Stopped.")
finally:
    GPIO.cleanup()
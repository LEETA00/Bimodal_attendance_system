import json, os
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

REGISTRY_FILE = "card_registry.json"
reader = SimpleMFRC522()

def load_registry():
    return json.load(open(REGISTRY_FILE)) if os.path.exists(REGISTRY_FILE) else {}

def save_registry(d):
    json.dump(d, open(REGISTRY_FILE, "w"), indent=2)

try:
    name = input("Enter full name: ").strip()
    if not name:
        print("No name. Exiting.")
        exit()
    print(f"Tap RFID card for: {name}")
    card_id, _ = reader.read()
    print(f"Card ID: {card_id}")
    data = load_registry()
    if str(card_id) in data:
        print(f"Already registered to: {data[str(card_id)]}")
        if input("Overwrite? (y/n): ").strip().lower() != "y":
            exit()
    data[str(card_id)] = name
    save_registry(data)
    print(f"SUCCESS: {card_id} registered to {name}")
    print(f"All cards: {data}")
finally:
    GPIO.cleanup()
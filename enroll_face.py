import pickle, os, time
import face_recognition
from picamera2 import Picamera2

ENCODINGS_FILE = "known_faces.pkl"

def load_faces():
    return pickle.load(open(ENCODINGS_FILE,"rb")) if os.path.exists(ENCODINGS_FILE) else {}

def save_faces(d):
    pickle.dump(d, open(ENCODINGS_FILE,"wb"))

name = input("Enter full name: ").strip()
if not name:
    print("No name. Exiting.")
    exit()

print(f"Enrolling: {name}")
print("Live preview for 5 seconds — position face clearly...")

picam2 = Picamera2(0)
picam2.configure(picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"}))
picam2.start()
time.sleep(5)
picam2.stop()
picam2.close()

picam2 = Picamera2(0)
picam2.configure(picam2.create_still_configuration(
    main={"size": (640, 480), "format": "RGB888"}))
picam2.start()
time.sleep(2)
print("Capturing...")
frame = picam2.capture_array()
picam2.stop()
picam2.close()

encodings = face_recognition.face_encodings(frame)
if not encodings:
    print("ERROR: No face detected. Try better lighting.")
    exit()

faces = load_faces()
faces[name] = encodings[0]
save_faces(faces)
print(f"SUCCESS: {name} enrolled.")
print(f"All enrolled: {list(faces.keys())}")
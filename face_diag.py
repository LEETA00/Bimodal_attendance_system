import face_recognition, numpy as np, pickle, os, time
from picamera2 import Picamera2

ENCODINGS_FILE = "known_faces.pkl"
if not os.path.exists(ENCODINGS_FILE):
    print("ERROR: Run enroll_face.py first.")
    exit()

with open(ENCODINGS_FILE,"rb") as f:
    known_faces = pickle.load(f)

print(f"Enrolled: {list(known_faces.keys())}")
print("Look at camera for 15 seconds...\n")

picam2 = Picamera2(0)
picam2.configure(picam2.create_video_configuration(
    main={"size": (320, 240), "format": "RGB888"}))
picam2.start()
time.sleep(2)

start = time.time()
while time.time() - start < 15:
    frame = picam2.capture_array()
    encs  = face_recognition.face_encodings(frame)
    if encs:
        names = list(known_faces.keys())
        dists = face_recognition.face_distance(
            list(known_faces.values()), encs[0])
        best  = int(np.argmin(dists))
        status = "MATCH" if dists[best] <= 0.5 else "NO MATCH"
        print(f"[{status}] {names[best]}: distance={dists[best]:.4f}")
    else:
        print("No face detected")
    time.sleep(1)

picam2.stop()
print("Done.")
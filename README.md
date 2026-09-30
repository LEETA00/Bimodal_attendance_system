# Bimodal Attendance System Using Face Recognition and RFID

A standalone two-factor biometric attendance kiosk built on Raspberry Pi 4B.
Combines RFID card scanning and real-time facial recognition to eliminate
proxy attendance.

## Author
Abdulazeez Yusuff Olamilekan
B.Eng. Electrical and Electronic Engineering
LAUTECH, Ogbomoso, Nigeria — 2026

## Hardware
- Raspberry Pi 4B (8GB)
- MFRC522 RFID Reader (SPI CE0)
- Pi Camera Module v1.3 (CSI)
- ILI9341 2.8" TFT Display (Software SPI)
- XPT2046 Touch Controller (SPI CE1)
- Mifare Classic 1K Cards

## How It Works
1. User taps RFID card — system reads their name
2. Camera activates — user looks at camera
3. Face encoding compared to stored enrollment
4. Both must match the same person — attendance logged
5. Record saved to SQLite locally and Google Sheets remotely

## Attendance Modes
| Mode | Method | Duplicate Block |
|---|---|---|
| Class Attendance | RFID + Face | 3 hours |
| Exam Mode | RFID + Face (strict) | 24 hours |
| Event Mode | RFID only or Face only | None |
| Custom Mode | RFID + Face | 1 hour |
| Register Person | On-screen keyboard + Card + Face | — |

## Wiring Summary
| Module | Interface | Key Pins |
|---|---|---|
| ILI9341 Display | Software SPI | GPIO16/20/21/26/19 |
| MFRC522 RFID | Hardware SPI CE0 | GPIO8/11/10/9/25 |
| XPT2046 Touch | Hardware SPI CE1 | GPIO7/27 (shares SPI lines) |
| Pi Camera | CSI Ribbon | Dedicated port |

## Installation
```bash
sudo raspi-config  # Enable SPI
sudo usermod -a -G spi $USER
pip3 install -r requirements.txt --break-system-packages
python3 touch_calibrate.py
python3 attendance_app.py
# Robotic Hand — Real-Time Motion Mirroring

A robotic hand that copies a human hand in real time. A camera tracks the operator's hand with MediaPipe, the computer converts finger angles into servo commands, and an ESP32 drives the servos through a PCA9685 PWM driver.

> Status: **prototype, in progress.** All five fingers are tracked in software; the index finger is currently wired to a servo end-to-end. Built for the Iraqi Universities Robotics Competition.

---

## How it works

```
Webcam ──► MediaPipe Hand Landmarker (21 landmarks)
              │
              ▼
   Finger angle per joint (vector maths on landmarks)
              │   hysteresis: open > 130°, closed < 90°
              ▼
   Servo command (open / closed angle) ──USB serial 115200──► ESP32 ──I²C──► PCA9685 ──► Servos
```

1. **Tracking** — each frame is processed by the MediaPipe Hand Landmarker in video mode, giving 21 landmarks per hand.
2. **Angles** — for every finger the angle at the knuckle is computed from three landmarks (wrist → knuckle → fingertip; the thumb uses its own joints).
3. **Hysteresis** — a finger switches to *open* above 130° and to *closed* below 90°, so it does not flicker around a single threshold.
4. **Serial output** — when the command changes, it is sent to the ESP32 at most every 100 ms to keep the link smooth.
5. **HUD** — an on-screen panel shows each finger's angle and state live.

## Files

| File | Description |
|---|---|
| [`vision/hand_control.py`](vision/hand_control.py) | Current version: 5-finger tracking, angle-to-servo mapping, serial link to the ESP32, live HUD |
| [`vision/hand_tracking_basic.py`](vision/hand_tracking_basic.py) | First prototype: landmark tracking and FPS display |

## Hardware

| Component | Role |
|---|---|
| ESP32-S3 | Receives commands over USB serial |
| PCA9685 16-channel PWM driver | Drives the finger servos over I²C |
| DS3135 / MG995 servos | Finger actuators |
| External 5–6 V supply | Servo power (common ground with the ESP32) |

**Lesson learned:** servo jitter was traced to the PCA9685 **OE** (output-enable) pin being left floating; tying it to GND fixed it.

## Running

```bash
pip install opencv-python mediapipe numpy pyserial
# download hand_landmarker.task from Google's MediaPipe models page into vision/
python vision/hand_control.py
```

Set `SERIAL_PORT` (e.g. `COM6`) and the camera index at the top of the script.

## Next steps

- Wire the remaining four fingers and add proportional (not just open/closed) control.
- Add wrist and elbow motion using MediaPipe Pose.

## Author

**Yousif Ezzat Salih** — Computer Technology Engineering, Al-Bayan University, Baghdad

import cv2
import mediapipe as mp
import numpy as np
import math
import serial
import time

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

HAND_MODEL  = "hand_landmarker.task"
SERIAL_PORT = "COM6"
BAUD_RATE   = 115200

# نقاط معالم اليد (MediaPipe Landmarks)
WRIST       = 0
THUMB_CMC = 1;  THUMB_MCP = 2;  THUMB_TIP  = 4
INDEX_MCP = 5;  INDEX_TIP  = 8
MIDDLE_MCP= 9;  MIDDLE_TIP = 12
RING_MCP  = 13; RING_TIP   = 16
PINKY_MCP = 17; PINKY_TIP  = 20

def angle_between(a, b, c):
    a, b, c = np.array(a[:2]), np.array(b[:2]), np.array(c[:2])
    ba, bc = a - b, c - b
    cos_a = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return math.degrees(math.acos(np.clip(cos_a, -1.0, 1.0)))

def lm_xyz(lm): 
    return (lm.x, lm.y, lm.z)

# ── إعدادات الزوايا لجميع الأصابع ──────────────────────────────────────────────
OPEN_THRESHOLD   = 130   # زاوية أكبر من هذه تعني الإصبع مفتوح
CLOSED_THRESHOLD = 90    # زاوية أصغر من هذه تعني الإصبع مغلق

SERVO_OPEN   = 50        # الزاوية المرسلة للسيرفو عند الفتح
SERVO_CLOSED = 120       # الزاوية المرسلة للسيرفو عند الغلق

# الحالة الابتدائية لجميع الأصابع
finger_states = {"thumb": SERVO_OPEN, "index": SERVO_OPEN, "middle": SERVO_OPEN, "ring": SERVO_OPEN, "pinky": SERVO_OPEN}

def angle_to_servo_val(name, angle):
    global finger_states
    if angle > OPEN_THRESHOLD:
        finger_states[name] = SERVO_OPEN
    elif angle < CLOSED_THRESHOLD:
        finger_states[name] = SERVO_CLOSED
    return finger_states[name]

def process_all_fingers(hand_lms):
    L = [lm_xyz(lm) for lm in hand_lms]
    
    # حساب زاوية كل إصبع بالنسبة للمعصم (Wrist) والقاعدة والطرف
    angles = {
        "thumb" : angle_between(L[THUMB_CMC], L[THUMB_MCP], L[THUMB_TIP]),
        "index" : angle_between(L[WRIST],     L[INDEX_MCP], L[INDEX_TIP]),
        "middle": angle_between(L[WRIST],     L[MIDDLE_MCP], L[MIDDLE_TIP]),
        "ring"  : angle_between(L[WRIST],     L[RING_MCP],   L[RING_TIP]),
        "pinky" : angle_between(L[WRIST],     L[PINKY_MCP],  L[PINKY_TIP]),
    }
    
    # تحويل الزوايا إلى قيم السيرفو (فتح/غلق)
    return {k: angle_to_servo_val(k, v) for k, v in angles.items()}, angles

def draw_hud(frame, current_servos, current_angles):
    # رسم خلفية سوداء شفافة للبيانات
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (240, 160), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
    
    y = 25
    for name in ["thumb", "index", "middle", "ring", "pinky"]:
        val = current_servos[name]
        ang = current_angles[name]
        state_str = "OPEN" if val == SERVO_OPEN else "CLOSED"
        color = (0, 255, 180) if state_str == "OPEN" else (0, 100, 255)
        
        # تمييز إصبع السبابة لأنه هو الوحيد المتصل حالياً بالـ ESP
        prefix = "[Active] " if name == "index" else "         "
        
        cv2.putText(frame, f"{prefix}{name:<6}: {ang:>5.1f}* ({state_str})", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        y += 26

def main():
    ser = None
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("Connected to ESP32 successfully.")
    except Exception as e:
        print(f"No serial connection: {e}")

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=HAND_MODEL),
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        running_mode=vision.RunningMode.VIDEO,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(2, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    last_sent_val = -1
    last_send_time = 0
    SEND_INTERVAL = 0.1  # إرسال كل 100 ملي ثانية لزيادة السلاسة

    print("Running 5-Finger Tracking Window. (Q to quit)")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        frame = cv2.flip(frame, 1)
        h, w   = frame.shape[:2]
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img= mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts    = int(cap.get(cv2.CAP_PROP_POS_MSEC))

        result = landmarker.detect_for_video(mp_img, ts)

        # تحضير قيم افتراضية للعرض في حال عدم وجود يد
        display_servos = finger_states.copy()
        display_angles = {k: 0.0 for k in finger_states.keys()}

        if result.hand_landmarks:
            hand_lms = result.hand_landmarks[0]
            
            # معالجة وحساب زوايا الـ 5 أصابع كاملة
            display_servos, display_angles = process_all_fingers(hand_lms)
            
            # استخراج قيمة زاوية إصبع السبابة فقط لإرسالها
            index_servo_val = display_servos["index"]

            now = time.time()
            # التحقق من تغير القيمة ومرور الوقت المطلوب لمنع الضغط على المعالج
            if index_servo_val != last_sent_val and (now - last_send_time) > SEND_INTERVAL:
                last_sent_val = index_servo_val
                last_send_time = now
                
                # إرسال القيمة متبوعة بـ n\ لتتوافق مع كود الـ ESP32 الحالي الخاص بك
                packet = f"{index_servo_val}\n"
                print(f"Sending Index Command -> {index_servo_val}")
                
                if ser and ser.is_open:
                    try:
                        ser.write(packet.encode())
                    except Exception as e:
                        print(f"Serial write error: {e}")

            # رسم نقاط ميديا بايب الأساسية على اليد للكاميرا
            for lm in hand_lms:
                cv2.circle(frame, (int(lm.x*w), int(lm.y*h)), 4, (255, 255, 255), -1)

        # تحديث الشاشة بالبيانات الحية لجميع الأصابع الخمسة
        draw_hud(frame, display_servos, display_angles)
        cv2.imshow("5-Finger Data Window (Index Active)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if ser: ser.close()
    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()

if __name__ == "__main__":
    main()
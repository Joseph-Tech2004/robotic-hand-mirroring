import cv2
import mediapipe as mp
import time

# 1. إعدادات مكتبة MediaPipe
mp_hands = mp.solutions.hands
# ضبط التعرف على يد واحدة فقط لزيادة سرعة المعالجة (FPS)
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

# 2. اختيار الكاميرا (جرب 1 أو 2 لـ DroidCam عبر السلك)
# إذا ظهرت شاشة سوداء، قم بتغيير الرقم من 1 إلى 0 أو 2
cap = cv2.VideoCapture(1) 

p_time = 0 # لحساب عدد الفريمات (FPS)

print("--- جاري تشغيل النظام... اضغط 'q' للخروج ---")

while True:
    success, img = cap.read()
    if not success:
        print("خطأ: لم يتم العثور على كاميرا. تأكد من تشغيل DroidCam بالسلك.")
        break

    # تحويل الصورة من BGR إلى RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    # إذا تم رصد اليد
    if results.multi_hand_landmarks:
        for hand_lms in results.multi_hand_landmarks:
            # رسم الـ 21 نقطة والروابط بينها
            mp_draw.draw_landmarks(img, hand_lms, mp_hands.HAND_CONNECTIONS)
            
            # استخراج إحداثيات النقاط (لمعالجتها لاحقاً وإرسالها لـ ESP32)
            for id, lm in enumerate(hand_lms.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                
                # مثال: تلوين طرف الإبهام (النقطة 4) باللون الأصفر
                if id == 4:
                    cv2.circle(img, (cx, cy), 10, (0, 255, 255), cv2.FILLED)

    # حساب وعرض سرعة النظام (FPS)
    c_time = time.time()
    fps = 1 / (c_time - p_time)
    p_time = c_time
    cv2.putText(img, f'FPS: {int(fps)}', (10, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

    # عرض النافذة النهائية
    cv2.imshow("Bionic Arm AI - NURAI 2026", img)

    # الخروج عند ضغط مفتاح 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
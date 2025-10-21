import time
import requests
import board
import busio
import adafruit_vl53l0x
import RPi.GPIO as GPIO

SERVER_URL = "http://DESKTOP-R98PM6A.local:5173/api/camera"
DISTANCE_THRESHOLD = 500  # mm
NO_PERSON_TIMEOUT = 10    # seconds
LED_PIN = 17

# I2C sensor
i2c = busio.I2C(board.SCL, board.SDA)
vl53 = adafruit_vl53l0x.VL53L0X(i2c)

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)
GPIO.output(LED_PIN, GPIO.LOW)

camera_started = False
last_seen_time = 0

while True:
    try:
        distance = vl53.range
        now = time.time()
        print(f"Distance: {distance} mm")

        # Person detected
        if distance <= DISTANCE_THRESHOLD:
            last_seen_time = now
            if not camera_started:
                GPIO.output(LED_PIN, GPIO.HIGH)
                try:
                    requests.post(SERVER_URL, json={"action": "start_camera"}, timeout=5)
                except Exception as e:
                    print("⚠️ Failed to notify server:", e)
                camera_started = True

        # No person for timeout
        elif camera_started and (now - last_seen_time) > NO_PERSON_TIMEOUT:
            GPIO.output(LED_PIN, GPIO.LOW)
            try:
                requests.post(SERVER_URL, json={"action": "stop_camera"}, timeout=5)
            except Exception as e:
                print("⚠️ Failed to notify server:", e)
            camera_started = False

        time.sleep(0.5)

    except KeyboardInterrupt:
        GPIO.output(LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        break

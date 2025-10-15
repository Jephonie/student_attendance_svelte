from flask import Flask, jsonify
from flask_cors import CORS
import RPi.GPIO as GPIO
import cv2
import threading
import time

app = Flask(__name__)
CORS(app)

LED_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

camera = None
camera_thread_obj = None
is_running = False
lock = threading.Lock()

def safe_release_camera():
    global camera
    try:
        if camera and camera.isOpened():
            camera.release()
            print("[INFO] Camera released cleanly.")
    except Exception as e:
        print(f"[WARN] Error releasing camera: {e}")
    finally:
        camera = None

def camera_thread():
    global camera, is_running
    print("[INFO] Starting camera thread...")
    GPIO.output(LED_PIN, GPIO.HIGH)
    time.sleep(0.3)  # small delay for LED visibility

    # retry mechanism
    for attempt in range(3):
        camera = cv2.VideoCapture(0)
        if camera.isOpened():
            break
        print(f"[WARN] Camera failed to open (try {attempt+1}), retrying...")
        safe_release_camera()
        time.sleep(1)
    else:
        print("[ERROR] Camera could not start after retries.")
        GPIO.output(LED_PIN, GPIO.LOW)
        with lock:
            is_running = False
        return

    print("[INFO] Camera started successfully, LED ON")

    while True:
        with lock:
            if not is_running:
                break
        ret, frame = camera.read()
        if not ret:
            print("[WARN] Camera frame not captured.")
            break
        time.sleep(0.05)

    print("[INFO] Stopping camera...")
    safe_release_camera()
    GPIO.output(LED_PIN, GPIO.LOW)
    print("[INFO] Camera stopped, LED OFF")

@app.route("/start_camera", methods=["POST"])
def start_camera():
    global camera_thread_obj, is_running
    with lock:
        if is_running:
            return jsonify({"status": "ok", "message": "Camera already running"})
        is_running = True

    # Wait a bit to make sure previous thread finished
    time.sleep(0.5)
    safe_release_camera()

    camera_thread_obj = threading.Thread(target=camera_thread, daemon=True)
    camera_thread_obj.start()
    return jsonify({"status": "ok", "message": "Camera started"})

@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global is_running
    with lock:
        if not is_running:
            return jsonify({"status": "ok", "message": "Camera not running"})
        is_running = False
    return jsonify({"status": "ok", "message": "Camera stopping"})

@app.route("/reset", methods=["POST"])
def reset_all():
    global camera, is_running
    print("[INFO] Resetting system...")
    with lock:
        is_running = False
    safe_release_camera()
    GPIO.output(LED_PIN, GPIO.LOW)
    return jsonify({"status": "ok", "message": "System reset"})

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5001)
    finally:
        GPIO.cleanup()

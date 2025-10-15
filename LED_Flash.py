# camera_led_control.py
from flask import Flask, jsonify
import RPi.GPIO as GPIO
import cv2
import threading
import time

app = Flask(__name__)
LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

camera = None
is_running = False

def camera_thread():
    global camera, is_running
    GPIO.output(LED_PIN, GPIO.HIGH)
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        GPIO.output(LED_PIN, GPIO.LOW)
        is_running = False
        print("Camera failed to open.")
        return

    print("Camera started, LED ON")

    while is_running:
        ret, frame = camera.read()
        if not ret:
            break
        time.sleep(0.05)

    camera.release()
    GPIO.output(LED_PIN, GPIO.LOW)
    print("Camera stopped, LED OFF")

@app.route("/start_camera", methods=["POST"])
def start_camera():
    global is_running
    if is_running:
        return jsonify({"status": "ok", "message": "Camera already running"})
    is_running = True
    threading.Thread(target=camera_thread).start()
    return jsonify({"status": "ok", "message": "Camera started"})

@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global is_running
    if not is_running:
        return jsonify({"status": "ok", "message": "Camera not running"})
    is_running = False
    return jsonify({"status": "ok", "message": "Stopping camera"})

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5001)
    finally:
        GPIO.cleanup()

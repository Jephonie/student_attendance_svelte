from flask import Flask, jsonify
from flask_cors import CORS
import RPi.GPIO as GPIO
import threading
import time

app = Flask(__name__)
CORS(app)

LED_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

is_led_on = False
lock = threading.Lock()

@app.route("/start_led", methods=["POST"])
def start_led():
    global is_led_on
    with lock:
        if is_led_on:
            return jsonify({"status": "ok", "message": "LED already on"})
        GPIO.output(LED_PIN, GPIO.HIGH)
        is_led_on = True
    print("[INFO] LED turned ON")
    return jsonify({"status": "ok", "message": "LED turned on"})

@app.route("/stop_led", methods=["POST"])
def stop_led():
    global is_led_on
    with lock:
        if not is_led_on:
            return jsonify({"status": "ok", "message": "LED already off"})
        GPIO.output(LED_PIN, GPIO.LOW)
        is_led_on = False
    print("[INFO] LED turned OFF")
    return jsonify({"status": "ok", "message": "LED turned off"})

@app.route("/reset", methods=["POST"])
def reset_all():
    global is_led_on
    with lock:
        is_led_on = False
    GPIO.output(LED_PIN, GPIO.LOW)
    print("[INFO] System reset, LED OFF")
    return jsonify({"status": "ok", "message": "System reset"})

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5001)
    finally:
        GPIO.cleanup()

from flask import Flask, jsonify, request
import RPi.GPIO as GPIO
import time
from adafruit_vl53l0x import VL53L0X
import board, busio

# ---- Setup ----
i2c = busio.I2C(board.SCL, board.SDA)
sensor = VL53L0X(i2c)

LED_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

app = Flask(__name__)
last_seen = time.time()
LED_ON = False

@app.route("/start_camera", methods=["POST"])
def start_camera():
    GPIO.output(LED_PIN, GPIO.HIGH)
    global LED_ON
    LED_ON = True
    print("🎥 Camera started")
    return jsonify({"status": "camera_started"})

@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    GPIO.output(LED_PIN, GPIO.LOW)
    global LED_ON
    LED_ON = False
    print("🛑 Camera stopped")
    return jsonify({"status": "camera_stopped"})

# Background loop – auto stop if 10 s no person
@app.route("/sensor_loop", methods=["GET"])
def loop():
    global last_seen, LED_ON
    while True:
        distance = sensor.range
        print(f"Distance: {distance} mm")
        if distance < 500:  # person detected within 0.5 m
            last_seen = time.time()
            if not LED_ON:
                GPIO.output(LED_PIN, GPIO.HIGH)
                LED_ON = True
        elif time.time() - last_seen > 10:
            GPIO.output(LED_PIN, GPIO.LOW)
            LED_ON = False
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5001)
    except KeyboardInterrupt:
        GPIO.cleanup()

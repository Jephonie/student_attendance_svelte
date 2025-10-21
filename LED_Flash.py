from flask import Flask
import time, requests, board, busio, adafruit_vl53l0x

app = Flask(__name__)

# --- Setup I2C connection and sensor ---
i2c = busio.I2C(board.SCL, board.SDA)
vl53 = adafruit_vl53l0x.VL53L0X(i2c)

# --- Constants ---
ON_DISTANCE_MM = 500        # Person detected threshold
OFF_DELAY_SEC = 10          # Delay before turning off camera
CHECK_INTERVAL_SEC = 0.5    # How often to check the sensor

# --- State variables ---
person_present = False
last_seen_time = time.time()

@app.route("/sensor_loop")
def sensor_loop():
    global person_present, last_seen_time
    print("👀 VL53L0X distance monitoring started (10s delay)...")

    while True:
        distance = vl53.range  # in millimeters
        print(f"📏 Distance: {distance} mm")

        # --- Person detected ---
        if distance < ON_DISTANCE_MM:
            last_seen_time = time.time()
            if not person_present:
                person_present = True
                print("✅ Person detected — turning camera ON")
                try:
                    requests.post("http://localhost:5001/start_camera", timeout=3)
                except Exception as e:
                    print("⚠️ start_camera failed:", e)

        # --- Person not detected for 10s ---
        else:
            idle_time = time.time() - last_seen_time
            if person_present and idle_time > OFF_DELAY_SEC:
                person_present = False
                print(f"⏱️ No person for {OFF_DELAY_SEC}s — turning camera OFF")
                try:
                    requests.post("http://localhost:5001/stop_camera", timeout=3)
                except Exception as e:
                    print("⚠️ stop_camera failed:", e)

        time.sleep(CHECK_INTERVAL_SEC)

    return "Sensor loop running..."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)

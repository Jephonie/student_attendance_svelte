import RPi.GPIO as GPIO
import time

# --- Configuration ---
# Use the Broadcom SOC channel numbering (BCM mode)
# This refers to the GPIO number, not the physical pin number.
# GPIO 17 (Physical Pin 11) is a common choice for this simple example.
LED_PIN = 17 
BLINK_DELAY_SECONDS = 1.0

def setup():
    """Sets up the GPIO mode and configures the LED pin as an output."""
    # Set the GPIO numbering convention to use the BCM (Broadcom) pin numbers
    GPIO.setmode(GPIO.BCM)
    
    # Configure the chosen pin (GPIO 17) as an output pin
    GPIO.setup(LED_PIN, GPIO.OUT)
    print(f"GPIO setup complete. LED connected to GPIO {LED_PIN}.")

def loop():
    """The main loop that continuously blinks the LED."""
    print("Starting LED blink sequence. Press Ctrl+C to stop.")
    while True:
        # Turn the LED on (set the pin voltage to HIGH)
        GPIO.output(LED_PIN, GPIO.HIGH)
        # print("LED ON")
        time.sleep(BLINK_DELAY_SECONDS)
        
        # Turn the LED off (set the pin voltage to LOW)
        GPIO.output(LED_PIN, GPIO.LOW)
        # print("LED OFF")
        time.sleep(BLINK_DELAY_SECONDS)

def cleanup():
    """Ensures all GPIO pins are safely returned to input mode."""
    print("\nCleaning up GPIO settings...")
    GPIO.cleanup()
    print("Program terminated successfully.")

if __name__ == '__main__':
    try:
        setup()
        loop()
    except KeyboardInterrupt:
        # This catches the Ctrl+C input from the user
        cleanup()
    except Exception as e:
        # Catch any other unexpected errors and still clean up
        print(f"An error occurred: {e}")
        cleanup()

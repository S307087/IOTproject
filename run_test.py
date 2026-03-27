import subprocess
import time

print("Starting CatalogAPI...")
cat = subprocess.Popen(["python", "CatalogAPI.py"])
time.sleep(2)

print("Starting AlertSystem...")
alert = subprocess.Popen(["python", "AlertSystem.py"])
time.sleep(2)

print("Sending test RFID update...")
subprocess.run(["python", "test_alert.py"])

time.sleep(3)
print("Terminating services...")
cat.terminate()
alert.terminate()
print("Test complete.")

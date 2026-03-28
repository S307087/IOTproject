import subprocess
import time
import sys

scripts = [
    "CatalogAPI.py",
    "AlertSystem.py",
    "StaffBot.py",
    "UserBot.py",
    "CartBot.py"
]

processes = []

print("==============================================")
print("Starting all services in a single terminal")
print("==============================================\n")

try:
    for script in scripts:
        print(f"[*] Starting {script}...")
        # Popen starts the process in the background and output is visible in this terminal
        p = subprocess.Popen([sys.executable, script])
        processes.append((script, p))
        time.sleep(2)  # Small delay to start them in order without overlapping

    print("\n[+] All services are running!")
    print("[!] Press Ctrl+C at any time to gracefully stop all of them.\n")
    
    # Keeps the main script alive to catch Ctrl+C
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n\n[!] Ctrl+C detected. Shutting down all running processes...")
    for script, p in processes:
        print(f"[-] Stopping {script}...")
        p.terminate()  # Send termination signal
        p.wait()       # Wait for the process to actually close
    
    print("\n[+] All services have been successfully stopped.")

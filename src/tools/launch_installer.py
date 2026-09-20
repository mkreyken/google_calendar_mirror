import subprocess
import sys
import os

def install_task(task_name: str, script_path: str):
    python_exe = sys.executable  # full path to python.exe
    script_path = os.path.abspath(script_path)

    # Task Scheduler command
    cmd = [
        "schtasks",
        "/Create",
        "/TN", task_name,
        "/TR", f'"{python_exe}" "{script_path}"',
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
        "/F",  # force update if exists
    ]

    print("Creating scheduled task...")
    subprocess.run(" ".join(cmd), shell=True, check=True)

    # Configure restart-on-failure
    failure_cmd = [
        "schtasks",
        "/Change",
        "/TN", task_name,
        "/RI", "1",        # restart interval (minutes)
        "/DU", "9999",     # duration (minutes)
        "/F"
    ]

    print("Configuring restart-on-failure...")
    subprocess.run(" ".join(failure_cmd), shell=True, check=True)

    print(f"Task '{task_name}' installed successfully.")


if __name__ == "__main__":
    # Change this to your script
    install_task("MyAppAutoStart", "C:/path/to/your_app.py")

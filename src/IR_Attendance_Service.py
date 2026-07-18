import sys
import time
import json
import requests
import subprocess
import os
import ctypes
from pathlib import Path

# Hardcoded fallback credentials matching the main app
DEFAULT_DB_URL = "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/"
DEFAULT_SECRET = "apng5Iuu7ijd8QYZLTj9ZZ4UGsmYE6wLaenzhFRx"

def get_firebase_credentials():
    # Try to load from C:/IR Attendance if it exists (for future expandability)
    config_path = Path("C:/IR Attendance/firebase_config.json")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get("database_url", DEFAULT_DB_URL), data.get("api_secret", DEFAULT_SECRET)
        except:
            pass
    return DEFAULT_DB_URL, DEFAULT_SECRET

def is_window_running(window_title):
    """Check if a window with title exists using Win32 API"""
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        return hwnd != 0
    except:
        return False

def find_bas_exe():
    r"""Recursively search C:\BAS for BAS.exe"""
    bas_dir = Path("C:/BAS")
    if bas_dir.exists():
        direct = bas_dir / "BAS.exe"
        if direct.exists():
            return str(direct)
        for path in bas_dir.rglob("BAS.exe"):
            return str(path)
    return None

def is_process_running(process_name):
    """Check if a process is running using tasklist"""
    try:
        output = subprocess.check_output('tasklist', creationflags=subprocess.CREATE_NO_WINDOW)
        return process_name.lower().encode() in output.lower()
    except:
        return False

def launch_apps():
    """Launch the main IR Attendance app and the BAS software."""
    print("Launching applications...")
    
    # 1. Launch IR Attendance (Check if running first)
    if not is_process_running("IR_Attendance.exe") and not is_window_running("IR Attendance"):
        script_dir = Path(__file__).parent
        main_py_path = script_dir / "main.py"
        
        if main_py_path.exists():
            # Dev/Test mode: run main.py next to the service
            print(f"Starting dev mode main.py: {main_py_path}")
            python_exe = sys.executable
            if "python.exe" in python_exe:
                pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
            else:
                pythonw_exe = python_exe
            
            subprocess.Popen([pythonw_exe, str(main_py_path)],
                             creationflags=subprocess.CREATE_NEW_CONSOLE | 0x08000000)
        else:
            # Prod mode: run compiled exe
            ir_app_path = r"C:\Program Files\IR Attendance\IR_Attendance.exe"
            if os.path.exists(ir_app_path):
                print(f"Starting compiled app: {ir_app_path}")
                ctypes.windll.shell32.ShellExecuteW(None, "open", ir_app_path, None, None, 1)
            else:
                print("IR_Attendance.exe not found.")
    else:
        print("IR Attendance is already running.")

    # 2. Launch BAS Software
    if not is_process_running("BAS.exe"):
        bas_app_path = find_bas_exe()
        if bas_app_path and os.path.exists(bas_app_path):
            print(f"Starting BAS: {bas_app_path}")
            bas_dir_srv = os.path.dirname(bas_app_path)
            ctypes.windll.shell32.ShellExecuteW(None, "open", bas_app_path, None, bas_dir_srv, 1)
        else:
            print("BAS.exe not found in C:\\BAS.")
    else:
        print("BAS software is already running.")

def listen_for_commands():
    db_url, secret = get_firebase_credentials()
    # Listen to a specific node for global commands: /service_commands
    url = f"{db_url}/service_commands.json?auth={secret}"
    
    print(f"Starting IR Attendance Service Listener...")
    print("Listening for remote commands...")

    # For a lightweight script, we can use the Firebase REST Streaming API (SSE)
    headers = {'Accept': 'text/event-stream'}
    
    while True:
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=60)
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            data_str = decoded_line[6:]
                            if data_str != "null":
                                try:
                                    data = json.loads(data_str)
                                    # data has 'path' and 'data'
                                    # If the command is "start_apps"
                                    if data.get('data') == 'start_apps':
                                        launch_apps()
                                        
                                        # Clear the command so it doesn't trigger again immediately on restart (asynchronously)
                                        clear_url = f"{db_url}/service_commands/command.json?auth={secret}"
                                        import threading
                                        threading.Thread(target=requests.delete, args=(clear_url,), daemon=True).start()
                                except json.JSONDecodeError:
                                    pass
            else:
                print(f"Failed to connect to Firebase: {response.status_code}")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Connection lost, retrying in 5s... ({e})")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Hide console window if run directly (though pythonw.exe does this too)
    try:
        if sys.platform == 'win32':
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass
        
    listen_for_commands()

import requests
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

CURRENT_VERSION = "2.0"
# We can use the same Firebase DB to host a simple version string
VERSION_URL = "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/version_info.json"

class UpdateChecker:
    @staticmethod
    def check_for_updates(parent_window):
        """Check for updates in the background without freezing the app"""
        def _check():
            try:
                resp = requests.get(VERSION_URL, timeout=5)
                if resp.status_code == 200 and resp.json():
                    data = resp.json()
                    latest_version = data.get("version", CURRENT_VERSION)
                    download_url = data.get("download_url", "")
                    
                    if UpdateChecker._is_newer(CURRENT_VERSION, latest_version):
                        # Schedule the popup on the main thread
                        parent_window.after(1500, lambda: UpdateChecker._show_update_prompt(parent_window, latest_version, download_url))
            except Exception as e:
                print(f"[UpdateChecker] Failed to check for updates: {e}")
                
        threading.Thread(target=_check, daemon=True).start()
        
    @staticmethod
    def _is_newer(current, latest):
        """Compare two version strings (e.g. 2.0 vs 2.1)"""
        try:
            curr_parts = [int(x) for x in str(current).split('.')]
            latest_parts = [int(x) for x in str(latest).split('.')]
            
            # Pad with 0s to make lengths equal
            while len(curr_parts) < len(latest_parts): curr_parts.append(0)
            while len(latest_parts) < len(curr_parts): latest_parts.append(0)
            
            for c, l in zip(curr_parts, latest_parts):
                if l > c: return True
                if l < c: return False
            return False
        except Exception:
            # Fallback to simple string comparison if format is weird
            return str(latest) > str(current)

    @staticmethod
    def _show_update_prompt(parent, latest_version, download_url):
        answer = messagebox.askyesno(
            "Update Available", 
            f"A new version of IR Attendance (v{latest_version}) is available!\n\nWould you like to download it now?",
            parent=parent
        )
        if answer and download_url:
            webbrowser.open(download_url)

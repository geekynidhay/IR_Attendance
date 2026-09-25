import requests
import threading
import time

FIREBASE_URL = "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/sync_state"

class SyncManager:
    @staticmethod
    def push_state(username, settings_dict):
        """Push only the attendance state to the cloud, avoiding local paths."""
        if not username:
            return
            
        def _push():
            payload = {
                "subfolder_settings": settings_dict.get("subfolder_settings", {}),
                "success_folders": settings_dict.get("success_folders", []),
                "marked_folders": settings_dict.get("marked_folders", []),
                "not_working_folders": settings_dict.get("not_working_folders", []),
                "last_updated": time.time()
            }
            
            # Sanitize username just in case
            safe_user = username.replace('.', '_').replace('#', '_').replace('$', '_').replace('[', '_').replace(']', '_')
            url = f"{FIREBASE_URL}/{safe_user}.json"
            
            try:
                requests.put(url, json=payload, timeout=5)
                print(f"[Sync] Pushed state to cloud for user: {safe_user}")
            except Exception as e:
                print(f"[Sync] Failed to push state: {e}")
                
        threading.Thread(target=_push, daemon=True).start()
        
    @staticmethod
    def pull_state(username, callback):
        """Pull the attendance state from the cloud."""
        if not username:
            if callback: callback(False, None)
            return
            
        def _pull():
            safe_user = username.replace('.', '_').replace('#', '_').replace('$', '_').replace('[', '_').replace(']', '_')
            url = f"{FIREBASE_URL}/{safe_user}.json"
            
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200 and resp.json():
                    print(f"[Sync] Pulled state from cloud for user: {safe_user}")
                    if callback: callback(True, resp.json())
                else:
                    print(f"[Sync] No cloud state found for user: {safe_user}")
                    if callback: callback(False, None)
            except Exception as e:
                print(f"[Sync] Failed to pull state: {e}")
                if callback: callback(False, None)
                
        threading.Thread(target=_pull, daemon=True).start()

    @staticmethod
    def get_all_users(callback):
        """Fetch a list of all users who have synced state in the cloud."""
        def _get():
            # Use shallow=true to only fetch the user keys, not their entire data
            url = f"{FIREBASE_URL}.json?shallow=true"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200 and resp.json():
                    users = list(resp.json().keys())
                    # Convert safe underscores back to dots if needed (or just use as is)
                    if callback: callback(True, users)
                else:
                    if callback: callback(False, [])
            except Exception as e:
                print(f"[Sync] Failed to fetch users list: {e}")
                if callback: callback(False, [])
                
        threading.Thread(target=_get, daemon=True).start()

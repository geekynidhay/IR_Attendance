"""
License Manager for IR Attendance
Handles hardware ID generation, verification, and Firebase communication.
"""
import uuid
import hashlib
import platform
import json
import requests
import sys
from encryption_utils import EncryptionUtils

# Placeholder for User provided config. 
# In production, this would be encrypted or loaded securely.
FIREBASE_CONFIG_FILE = "firebase_config.json"

class LicenseManager:
    """Manages licensing, activation, and online checks"""
    
    def __init__(self, manual_config=None):
        self.machine_id = self.get_machine_id()
        self.encryption_key = None
        if manual_config:
            self.config = manual_config
        else:
            self.config = self.load_firebase_config()
            
        # EMBEDDED FALLBACK CREDENTIALS (Fixes 404 if config file missing)
        default_url = "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/"
        default_secret = "apng5Iuu7ijd8QYZLTj9ZZ4UGsmYE6wLaenzhFRx"
        
        self.database_url = self.config.get("database_url", default_url)
        self.api_secret = self.config.get("api_secret", default_secret)
        
        # Firebase Storage Bucket (Guess based on project ID)
        self.storage_bucket = self.config.get("storage_bucket", "attendance-68878.appspot.com")
        
    def get_machine_id(self):
        """Generate a unique ID based on hardware"""
        unique_str = ""
        # Primary: Windows MachineGuid (Highly stable across network changes)
        if platform.system() == "Windows":
            try:
                import winreg
                # WOW64_64KEY ensures we get the real registry key on 64-bit Windows
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                unique_str = str(guid)
            except Exception as e:
                print(f"Could not read MachineGuid: {e}")
                
        # Fallback to MAC address (Can fluctuate with VPNs/Virtual Adapters)
        if not unique_str:
            try:
                mac = uuid.getnode()
                system_info = f"{platform.node()}-{platform.system()}-{platform.processor()}"
                unique_str = f"{mac}-{system_info}"
            except Exception as e:
                print(f"Error generating Machine ID: {e}")
                return "UNKNOWN-MACHINE-ID"
                
        # Hash it to make it shorter and consistent
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16].upper()

    def load_firebase_config(self):
        """Load Firebase config from file"""
        from pathlib import Path
        
        # 1. Check next to script (dev mode in src/)
        config_path = Path(__file__).parent / FIREBASE_CONFIG_FILE
        
        # 2. Check in root (dev mode running from root)
        if not config_path.exists():
            config_path = Path(".") / FIREBASE_CONFIG_FILE
            
        # 3. Check in parent (dev mode script in src/, file in root)
        if not config_path.exists():
            config_path = Path(__file__).parent.parent / FIREBASE_CONFIG_FILE
            
        # 4. If frozen, look next to exe
        if getattr(sys, 'frozen', False):
            # Check internal bundled file
            bundled_path = Path(sys._MEIPASS) / FIREBASE_CONFIG_FILE if hasattr(sys, '_MEIPASS') else None
            if bundled_path and bundled_path.exists():
                config_path = bundled_path
            else:
                config_path = Path(sys.executable).parent / FIREBASE_CONFIG_FILE
            
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def generate_request_code(self, username):
        """Generate a request code containing User+Machine info"""
        # Format: BASE64(MachineID|Username) or just a concatenated string
        # For simplicity:
        raw_data = f"{self.machine_id}|{username}"
        # Simple obfuscation
        return raw_data

    def get_location_info(self):
        """Fetch tracking info (IP, City, Country)"""
        try:
            response = requests.get("http://ip-api.com/json", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": data.get("query", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", "Unknown")
                }
        except Exception:
            pass
        return {"ip": "Unknown", "city": "Unknown", "country": "Unknown"}

    def check_license_online(self, username):
        """
        Check if the user is authorized in Firebase.
        Updates Last Seen, IP, and Location if active.
        """
        if not self.database_url:
            return False, "Configuration Error: No Database URL"
            
        try:
            # Construct URL: licenses/<machine_id>.json
            url = f"{self.database_url}/licenses/{self.machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    # Check status
                    status = data.get("status", "inactive")
                    server_user = data.get("username", "")
                    
                    if status == "active":
                        if server_user == username:
                            self.encryption_key = data.get("encryption_key")
                            self.activation_code = data.get("activation_code")
                            # Update Telemetry (Last Seen, IP, Location)
                            try:
                                from datetime import datetime
                                loc_info = self.get_location_info()
                                update_data = {
                                    "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "ip": loc_info['ip'],
                                    "location": f"{loc_info['city']}, {loc_info['country']}"
                                }
                                requests.patch(url, json=update_data)
                            except Exception as e:
                                print(f"Telemetry update failed: {e}")
                                
                            return True, "Active"
                        else:
                            return False, "Username mismatch"
                    elif status == "revoked":
                        return False, "License Revoked by Admin"
                    else:
                        return False, "License Inactive"
                else:
                    return False, "License not found on server"
            else:
                return False, f"Server Error: {response.status_code}"
                
        except requests.RequestException as e:
            # Retry once before giving up
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        status = data.get("status", "inactive")
                        server_user = data.get("username", "")
                        if status == "active" and server_user == username:
                            self.encryption_key = data.get("encryption_key")
                            self.activation_code = data.get("activation_code")
                            return True, "Active"
                        elif status == "revoked":
                            return False, "License Revoked by Admin"
                        else:
                            return False, "License Inactive"
                    else:
                        return False, "License not found on server"
                else:
                    return False, f"Server Error: {response.status_code}"
            except requests.RequestException as e2:
                return False, f"Connection Error: {e2}"

    def activate_license(self, request_code, username):
        """
        Admin: Activate a license based on request code.
        Request Code format: MachineID|... or just MachineID
        """
        if not self.database_url:
            return False, "No Database URL"
            
        try:
            # Parse request code
            parts = request_code.split('|')
            machine_id = parts[0]
            
            # Generate a 6-digit PIN for Mobile App authentication
            import random
            pin_code = str(random.randint(100000, 999999))
            
            # Generate an encryption key
            encryption_key = EncryptionUtils.generate_key().decode()
            
            data = {
                "username": username,
                "status": "active",
                "last_seen": "never",
                "activation_code": pin_code, # Stored as the 6-digit PIN
                "encryption_key": encryption_key
            }
            
            url = f"{self.database_url}/licenses/{machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.put(url, json=data)
            
            if response.status_code == 200:
                return True, pin_code
            else:
                return False, f"Server Error: {response.text}"
        except Exception as e:
            return False, str(e)

    def revoke_license(self, machine_id):
        """Admin: Revoke a license (Permanently remove)"""
        if not self.database_url:
            return False, "No Database URL"
            
        try:
            url = f"{self.database_url}/licenses/{machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            # Use DELETE to remove the record completely as requested
            response = requests.delete(url)
            
            if response.status_code == 200:
                return True, "Removed from list"
            else:
                return False, f"Error: {response.text}"
        except Exception as e:
            return False, str(e)
            
    def update_license_key(self, machine_id, key):
        """Admin: Update an encryption key for an existing record"""
        if not self.database_url:
            return False, "No Database URL"
            
        try:
            url = f"{self.database_url}/licenses/{machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.patch(url, json={"encryption_key": key})
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def list_licenses(self):
        """Admin: List all licenses"""
        if not self.database_url:
            return {}
            
        try:
            url = f"{self.database_url}/licenses.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.get(url)
            if response.status_code == 200 and response.json():
                return response.json()
            return {}
        except Exception:
            return {}

    def submit_activation_request(self, username):
        """User: Submit a request for admin to activate this machine"""
        if not self.database_url:
            return False, "No Database URL"
            
        try:
            from datetime import datetime
            data = {
                "username": username,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "machine_id": self.machine_id,
                "status": "pending"
            }
            
            url = f"{self.database_url}/activation_requests/{self.machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.put(url, json=data)
            return response.status_code == 200, "Request sent to admin"
        except Exception as e:
            return False, str(e)

    def list_activation_requests(self):
        """Admin: List all pending activation requests"""
        if not self.database_url:
            return {}
            
        try:
            url = f"{self.database_url}/activation_requests.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.get(url)
            if response.status_code == 200 and response.json():
                return response.json()
            return {}
        except Exception:
            return {}

    def delete_activation_request(self, machine_id):
        """Admin: Delete a request after processing"""
        if not self.database_url:
            return False
            
        try:
            url = f"{self.database_url}/activation_requests/{machine_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            requests.delete(url)
            return True
        except Exception:
            return False

    def end_batch(self, pin, batch_id):
        """Admin: Mark a batch as ended so the client stops monitoring it."""
        if not self.database_url:
            return False, "No Database URL"
            
        try:
            url = f"{self.database_url}/sessions/{pin}/ended_batches/{batch_id}.json"
            if self.api_secret:
                url += f"?auth={self.api_secret}"
                
            response = requests.put(url, json=True, timeout=5)
            if response.status_code == 200:
                return True, "Batch marked as ended"
            return False, f"Server error: {response.status_code}"
        except Exception as e:
            return False, str(e)


"""
System utilities for IR Attendance application
Handles IP address, username, and internet connection checks
"""
import socket
import os
import platform
import subprocess

class SystemUtils:
    """Utilities for system information"""
    
    @staticmethod
    def get_ip_address():
        """Get local IP address"""
        try:
            # Connect to a public DNS to identify the preferred interface IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def get_username():
        """Get current system username"""
        try:
            return os.getlogin()
        except:
            return "User"
            
    @staticmethod
    def check_internet_connection():
        """Check if internet is connected"""
        try:
            # Simple ping check to Google DNS
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '8.8.8.8']
            result = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Connected" if result == 0 else "Disconnected"
        except:
            return "Unknown"
    
    @staticmethod
    def get_license_info():
        """Get license information"""
        # This is a placeholder as per requirements
        return "Standard License"

    @staticmethod
    def resource_path(relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        import sys
        from pathlib import Path
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            # In dev mode, if running from src, icon is in parent
            # If running from root, icon is current dir
            base_path = os.path.abspath(".")
            # Check for standard C:/IR Attendance first
            if os.path.exists("C:/IR Attendance") and relative_path in os.listdir("C:/IR Attendance"):
                 return os.path.join("C:/IR Attendance", relative_path)
            # Check parent if not found in current (assuming script in src/)
            if not (Path(base_path) / relative_path).exists():
                 parent_path = Path(base_path).parent
                 if (parent_path / relative_path).exists():
                     base_path = str(parent_path)
                 # One more check if running directly inside src
                 elif (Path(__file__).parent.parent / relative_path).exists():
                     base_path = str(Path(__file__).parent.parent)

        return os.path.join(base_path, relative_path)

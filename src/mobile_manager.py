import subprocess
import threading
import os
import sys
import time
from pathlib import Path

class MobileManager:
    """
    Handles communication with the mobile device via ADB.
    """
    
    @staticmethod
    def _run_adb_command(args):
        """Run an ADB command and return the output."""
        try:
            adb_cmd = "adb"
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Check if 'adb' is in PATH
            in_path = False
            try:
                subprocess.run(["adb", "version"], capture_output=True, startupinfo=startupinfo)
                in_path = True
            except (FileNotFoundError, subprocess.SubprocessError):
                pass

            if not in_path:
                # Common ADB locations on Windows
                possible_paths = [
                    os.path.join(os.environ.get('LOCALAPPDATA', ''), r"Android\Sdk\platform-tools\adb.exe"),
                    r"C:\platform-tools\adb.exe",
                    r"C:\adb\adb.exe"
                ]
                for p in possible_paths:
                    if p and os.path.exists(p):
                        adb_cmd = p
                        break

            command = [adb_cmd] + args
                
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                startupinfo=startupinfo,
                timeout=5
            )
            return result.stdout.strip()
        except Exception as e:
            print(f"ADB Error: {e}")
            return None

    @staticmethod
    def launch_mirror_app():
        """
        Attempts to launch the Mobile Mirror app (com.nidhay.irmirror) 
        on connected Android devices.
        """
        def _launch():
            print("Attempting to auto-launch mobile app...")
            
            # 1. Check for devices
            devices_output = MobileManager._run_adb_command(["devices"])
            if not devices_output or "device" not in devices_output.split('\n', 1)[-1]:
                print("No Android device connected/authorized.")
                return

            # 2. Wake up device (optional, but good)
            MobileManager._run_adb_command(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
            
            # 3. Launch App using Monkey (works without knowing exact Activity name)
            # -p package_name
            # -c android.intent.category.LAUNCHER
            # 1 (event count)
            # This is a standard trick to launch an app by package name
            package_name = "com.nidhay.irmirror"
            cmd = ["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"]
            
            output = MobileManager._run_adb_command(cmd)
            print(f"Launch Output: {output}")

        # Run in a separate thread to not block the UI
        threading.Thread(target=_launch, daemon=True).start()

    @staticmethod
    def get_scrcpy_path():
        """Find the scrcpy executable."""
        # 1. Check project platform-tools
        local_scrcpy = Path("platform-tools/scrcpy.exe").resolve()
        if local_scrcpy.exists():
            return str(local_scrcpy)
            
        # 2. Check system PATH
        import shutil
        sys_scrcpy = shutil.which("scrcpy")
        if sys_scrcpy:
            return sys_scrcpy
            
        # 3. Common installation paths
        common_paths = [
            r"C:\scrcpy\scrcpy.exe",
            r"C:\platform-tools\scrcpy.exe",
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
                
        return None

    @staticmethod
    def start_mirroring(ip=None):
        """
        Launch scrcpy screen mirroring.
        If IP is provided, it tries to connect wirelessly first.
        """
        scrcpy_exe = MobileManager.get_scrcpy_path()
        if not scrcpy_exe:
            print("Error: scrcpy.exe not found. Please place it in platform-tools/ or system PATH.")
            return False, "scrcpy not found"

        # If IP is provided, try to connect wirelessly
        target = None
        if ip:
            print(f"Connecting wirelessly to {ip}:5555...")
            # Ensure port is appended
            full_ip = ip if ":" in ip else f"{ip}:5555"
            MobileManager._run_adb_command(["connect", full_ip])
            target = full_ip

        # Build scrcpy command
        # --always-on-top: Keep mirror window visible
        # --turn-screen-off: Save phone battery while mirroring
        cmd = [scrcpy_exe, "--always-on-top"]
        if target:
            cmd.extend(["--serial", target])
            
        try:
            # Launch scrcpy as a separate process
            flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0) if os.name == 'nt' else 0
            subprocess.Popen(cmd, creationflags=flags)
            return True, "Mirroring started"
        except Exception as e:
            print(f"Failed to launch scrcpy: {e}")
            return False, str(e)

    @staticmethod
    def setup_wireless_connection():
        """
        Automates USB to WiFi handshake:
        1. Find USB device
        2. Get its IP
        3. Enable TCP/IP on 5555
        4. Connect to IP
        """
        # 1. Check for USB devices
        devices_output = MobileManager._run_adb_command(["devices"])
        if not devices_output: return False, "No devices found"
        
        lines = [l.strip() for l in devices_output.split('\n') if l.strip() and not l.startswith('List of')]
        usb_devices = [l.split('\t')[0] for l in lines if l.endswith('\tdevice') and ':' not in l]
        
        if not usb_devices:
            # Maybe already connected wirelessly?
            if any(':' in l for l in lines if l.endswith('\tdevice')):
                return True, "Already connected wirelessly"
            return False, "No USB device found for handshake"
            
        serial = usb_devices[0]
        print(f"Handshaking with USB device: {serial}")
        
        # 2. Get IP
        ip_out = MobileManager._run_adb_command(["-s", serial, "shell", "ip", "addr", "show", "wlan0"])
        import re
        match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ip_out or "")
        if not match:
            # Try eth0 if wlan0 fails
            ip_out = MobileManager._run_adb_command(["-s", serial, "shell", "ip", "addr", "show", "eth0"])
            match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ip_out or "")
            
        if not match:
            return False, "Could not find device IP address"
            
        device_ip = match.group(1)
        print(f"Found IP: {device_ip}")
        
        # 3. Enable TCP/IP
        MobileManager._run_adb_command(["-s", serial, "tcpip", "5555"])
        time.sleep(2) # Give it a moment
        
        # 4. Connect
        conn_out = MobileManager._run_adb_command(["connect", f"{device_ip}:5555"])
        print(f"Connect result: {conn_out}")
        
        import server
        server.registered_phone_ip = device_ip
        
        return True, f"Wireless setup successful: {device_ip}"

    @staticmethod
    def get_status_info():
        """Get device connection status and IP."""
        import server
        phone_ip = server.registered_phone_ip
        
        devices_output = MobileManager._run_adb_command(["devices"])
        if not devices_output:
            return "❌ Disconnected", phone_ip or "Not registered"
            
        # Parse lines, skipping header
        lines = [l.strip() for l in devices_output.split('\n') if l.strip() and not l.startswith('List of')]
        
        # Filter for actual 'device' status (ignore 'offline', 'unauthorized', etc.)
        active_devices = [l for l in lines if l.endswith('\tdevice') or ' device' in l]
        
        if not active_devices:
            status = "❌ Disconnected"
            if phone_ip:
                status = f"❌ Offline ({phone_ip})"
            return status, phone_ip or "Not registered"
            
        # Check if any active device is wireless (has an IP in its ID)
        is_wireless = any(':' in l for l in active_devices)
        
        if is_wireless:
            return "✅ Connected (Wireless)", phone_ip or "Unknown IP"
        else:
            return "✅ Connected (USB)", phone_ip or "Not registered"

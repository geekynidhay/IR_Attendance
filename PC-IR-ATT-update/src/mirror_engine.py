
import subprocess
import threading
import time
import os
import win32gui
import win32con
from mobile_manager import MobileManager

class MirrorEngine:
    """
    Embedded Scrcpy Mirroring Engine.
    Uses win32gui to reparent scrcpy window into a Tkinter frame.
    """
    def __init__(self, target_container):
        self.container = target_container
        self.running = False
        self.process = None
        self.scrcpy_hwnd = None
        self.session_title = f"IR_Mirror_{int(time.time())}"
        
    def start(self, phone_ip=None):
        """Start scrcpy and embed it."""
        if self.running: return True
        
        scrcpy_exe = MobileManager.get_scrcpy_path()
        if not scrcpy_exe:
            print("[Mirror] scrcpy.exe not found!")
            return False
            
        # Build scrcpy command
        # --window-title: set unique title to find it later
        # --window-borderless: remove borders for cleaner embedding
        # --always-on-top: helps in some cases
        # --stay-awake: keep phone on
        cmd = [
            scrcpy_exe,
            "--window-title", self.session_title,
            "--window-borderless",
            "--always-on-top",
            "--stay-awake",
            "--no-audio",
            "--max-size", "1024",
            "--video-bit-rate", "2M",
            "--max-fps", "30"
        ]
        
        if phone_ip:
            target = phone_ip if ":" in phone_ip else f"{phone_ip}:5555"
            cmd.extend(["--serial", target])
            
        try:
            # Start scrcpy hidden initially if possible, or just start it
            self.process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            self.running = True
            
            # Start embedding thread
            threading.Thread(target=self._embedding_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[Mirror] Failed to launch scrcpy: {e}")
            return False

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            self.process = None
        self.scrcpy_hwnd = None

    def _embedding_loop(self):
        """Wait for scrcpy window to appear and then embed it."""
        start_wait = time.time()
        while self.running and time.time() - start_wait < 10:
            hwnd = win32gui.FindWindow(None, self.session_title)
            if hwnd:
                self.scrcpy_hwnd = hwnd
                self._embed_window()
                break
            time.sleep(0.5)

    def _embed_window(self):
        """Reparent and style the scrcpy window."""
        if not self.scrcpy_hwnd: return
        
        try:
            # 1. Get container HWND
            container_hwnd = self.container.winfo_id()
            
            # 2. Set Parent
            win32gui.SetParent(self.scrcpy_hwnd, container_hwnd)
            
            # 3. Modify style: Remove title bar, borders, etc.
            style = win32gui.GetWindowLong(self.scrcpy_hwnd, win32con.GWL_STYLE)
            style = style & ~win32con.WS_CAPTION & ~win32con.WS_THICKFRAME
            win32gui.SetWindowLong(self.scrcpy_hwnd, win32con.GWL_STYLE, style)
            
            # 4. Initial resize
            self.update_layout()
            
            # 5. Bind resize event to container
            self.container.bind("<Configure>", lambda e: self.update_layout())
            
        except Exception as e:
            print(f"[Mirror] Embedding error: {e}")

    def update_layout(self):
        """Update scrcpy window position and size to match container."""
        if not self.scrcpy_hwnd or not self.running: return
        
        try:
            # Get container dimensions
            w = self.container.winfo_width()
            h = self.container.winfo_height()
            
            if w < 10 or h < 10: return
            
            # Move and resize scrcpy window
            win32gui.MoveWindow(self.scrcpy_hwnd, 0, 0, w, h, True)
        except:
            pass

"""
Window management utilities for IR Attendance application
Handles window focus, always-on-top functionality, and global hotkeys
"""
import tkinter as tk
import threading
import keyboard

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("Warning: pywin32 not available. Some window management features may not work.")

class WindowManager:
    """Manages window focus and global hotkeys"""
    
    def __init__(self, root):
        self.root = root
        self.hwnd = None
        self.hotkey_registered = False
        
        # Get window handle after window is created
        self.root.after(100, self._get_window_handle)
    
    def _get_window_handle(self):
        """Get the window handle for win32 operations"""
        if HAS_WIN32:
            try:
                # Get the window handle
                self.hwnd = int(self.root.wm_frame(), 16) if hasattr(self.root, 'wm_frame') else None
                if not self.hwnd:
                    # Alternative method
                    self.root.update()
                    title = self.root.title()
                    self.hwnd = win32gui.FindWindow(None, title)
            except Exception as e:
                print(f"Could not get window handle: {e}")
    
    def set_always_on_top(self, on_top=True):
        """Set the window to always be on top"""
        if on_top:
            self.root.attributes('-topmost', True)
        else:
            self.root.attributes('-topmost', False)
    
    def bring_to_front(self):
        """Bring the window to the front and give it focus"""
        try:
            # Tkinter methods
            self.root.lift()
            self.root.focus_force()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
            
            # Win32 methods for better control
            if HAS_WIN32 and self.hwnd:
                tup = win32gui.GetWindowPlacement(self.hwnd)
                if tup[1] == win32con.SW_SHOWMINIMIZED:
                    win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(self.hwnd)
        except Exception as e:
            print(f"Error bringing window to front: {e}")

    def list_open_windows(self):
        """List all visible window titles"""
        if not HAS_WIN32:
            return []
        
        windows = []
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append(title)
        
        try:
            win32gui.EnumWindows(enum_handler, None)
        except Exception as e:
            print(f"Error listing windows: {e}")
            
        return sorted(list(set(windows)))

    def switch_to_window(self, window_title):
        """Switch focus to another window by title"""
        if not HAS_WIN32:
            return False
            
        try:
            hwnd = win32gui.FindWindow(None, window_title)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return True
        except Exception as e:
            print(f"Error switching to window '{window_title}': {e}")
        
        return False
    
    def register_hotkey(self, hotkey='ctrl+space', callback=None):
        """Register a global hotkey to bring window to focus"""
        if self.hotkey_registered:
            return
        
        try:
            if callback is None:
                callback = self.bring_to_front
            
            # Register the hotkey in a separate thread to avoid blocking
            def hotkey_listener():
                keyboard.add_hotkey(hotkey, callback, suppress=False)
                keyboard.wait()  # Keep the listener running
            
            hotkey_thread = threading.Thread(target=hotkey_listener, daemon=True)
            hotkey_thread.start()
            self.hotkey_registered = True
            print(f"Global hotkey registered: {hotkey}")
        except Exception as e:
            print(f"Error registering hotkey: {e}")
    
    def unregister_hotkey(self):
        """Unregister all hotkeys"""
        try:
            keyboard.unhook_all()
            self.hotkey_registered = False
        except Exception as e:
            print(f"Error unregistering hotkey: {e}")

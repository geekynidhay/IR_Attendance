"""
Footer component for IR Attendance application
Displays system information at the bottom of the screen
"""
import tkinter as tk
from tkinter import ttk
from system_utils import SystemUtils
import threading

class Footer:
    """Standard footer with system info"""
    
    def __init__(self, parent):
        self.frame = ttk.Frame(parent, relief=tk.SUNKEN, padding=(5, 2))
        
        # Left side - License and IP
        self.left_frame = ttk.Frame(self.frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        license_info = SystemUtils.get_license_info()
        self.license_label = ttk.Label(self.left_frame, text=f"Software Licensed to: {license_info}", font=('Arial', 8))
        self.license_label.pack(anchor=tk.W)
        
        self.ip_label = ttk.Label(self.left_frame, text="IP Address: Loading...", font=('Arial', 8))
        self.ip_label.pack(anchor=tk.W)
        
        # Right side - Status and User
        self.right_frame = ttk.Frame(self.frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        self.internet_label = ttk.Label(self.right_frame, text="Internet Connection Status: Loading...", font=('Arial', 8))
        self.internet_label.pack(anchor=tk.E)
        
        user_info = SystemUtils.get_username()
        self.user_label = ttk.Label(self.right_frame, text=f"UserName: {user_info}", font=('Arial', 8))
        self.user_label.pack(anchor=tk.E)
        
        # Start background update
        self.update_thread = threading.Thread(target=self.update_info, daemon=True)
        self.update_thread.start()
        
    def update_info(self):
        """Update system info in background"""
        ip = SystemUtils.get_ip_address()
        internet = SystemUtils.check_internet_connection()
        
        # Schedule UI update on main thread
        self.frame.after(0, lambda: self.ip_label.config(text=f"IP Address: {ip}"))
        self.frame.after(0, lambda: self.internet_label.config(text=f"Internet Connection Status: {internet}"))
    
    def pack(self, **kwargs):
        """Pack the footer frame"""
        self.frame.pack(**kwargs)

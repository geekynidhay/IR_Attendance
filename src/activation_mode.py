"""
Activation UI for IR Attendance
Shown when no valid license is found.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import threading
from license_manager import LicenseManager

class ActivationMode:
    def __init__(self, root, on_success_callback):
        self.root = root
        self.on_success_callback = on_success_callback
        self.license_manager = LicenseManager()
        self.frame = ttk.Frame(root)
        
        self.create_ui()
        
    def create_ui(self):
        # Header
        ttk.Label(self.frame, text="Software Activation", 
                 font=('Arial', 18, 'bold')).pack(pady=20)
        
        container = ttk.Frame(self.frame, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Step 1: Username
        ttk.Label(container, text="Step 1: Enter Username", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(container, textvariable=self.username_var, width=40)
        self.username_entry.pack(anchor=tk.W, pady=(0, 10))
        self.username_entry.bind('<KeyRelease>', self.update_request_code)
        
        # Step 2: Request Code
        ttk.Label(container, text="Step 2: Send this Request Code to Admin", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        
        req_frame = ttk.Frame(container)
        req_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.request_code_var = tk.StringVar(value="Enter username first...")
        self.req_entry = ttk.Entry(req_frame, textvariable=self.request_code_var, state='readonly')
        self.req_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(req_frame, text="Copy", command=self.copy_request).pack(side=tk.LEFT, padx=5)
        
        # Step 3: Activation Code
        ttk.Label(container, text="Step 3: Enter Activation Code", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        self.activation_code_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.activation_code_var, width=50).pack(anchor=tk.W, pady=(0, 20))
        
        # Activate Button
        self.activate_btn = ttk.Button(container, text="Activate Software", 
                                      command=self.on_activate, style='Accent.TButton')
        self.activate_btn.pack(fill=tk.X, pady=10)
        
        # Status
        self.status_label = ttk.Label(container, text="", foreground="red")
        self.status_label.pack()

        # Alternative: Direct Approval
        ttk.Separator(container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        ttk.Label(container, text="Alternative: Get Activation through Mobile", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        self.direct_name_var = tk.StringVar()
        self.direct_entry = ttk.Entry(container, textvariable=self.direct_name_var, width=40)
        self.direct_entry.pack(anchor=tk.W, pady=5)
        
        self.direct_btn = ttk.Button(container, text="Send to Admin for Approval", 
                                    command=self.on_direct_request)
        self.direct_btn.pack(fill=tk.X, pady=5)
        
        self.polling = False

    def update_request_code(self, event=None):
        username = self.username_var.get().strip()
        if username:
            code = self.license_manager.generate_request_code(username)
            self.request_code_var.set(code)
        else:
            self.request_code_var.set("Enter username first...")

    def copy_request(self):
        code = self.request_code_var.get()
        if code and "Enter username" not in code:
            pyperclip.copy(code)
            messagebox.showinfo("Copied", "Request code copied to clipboard!")

    def on_activate(self):
        username = self.username_var.get().strip()
        act_code = self.activation_code_var.get().strip()
        
        if not username or not act_code:
            self.status_label.config(text="Please fill all fields")
            return
            
        self.activate_btn.config(state='disabled', text="Verifying...")
        
        # Verify in background
        threading.Thread(target=self.verify_activation, args=(username, act_code), daemon=True).start()

    def verify_activation(self, username, code):
        # Online Verification
        is_valid, message = self.license_manager.check_license_online(username)
        
        def update_ui():
            self.activate_btn.config(state='normal', text="Activate Software")
            if is_valid:
                messagebox.showinfo("Success", "Activation Successful!")
                # Save license locally (simulated by config or separate file)
                # For now just callback
                self.on_success_callback(username)
            else:
                self.status_label.config(text=f"Activation Failed: {message}")
                messagebox.showerror("Activation Failed", message)
        
        self.root.after(0, update_ui)

    def on_direct_request(self):
        name = self.direct_name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Please enter your name")
            return
            
        self.direct_btn.config(state='disabled', text="Sending...")
        success, msg = self.license_manager.submit_activation_request(name)
        
        if success:
            self.status_label.config(text="Request sent! Waiting for admin approval...", foreground="blue")
            self.direct_btn.config(text="Waiting for Admin...")
            self.polling = True
            self.poll_for_activation(name)
        else:
            self.status_label.config(text=f"Error: {msg}", foreground="red")
            self.direct_btn.config(state='normal', text="Send to Admin for Approval")

    def poll_for_activation(self, username):
        if not self.polling:
            return
            
        # Check license online
        is_valid, msg = self.license_manager.check_license_online(username)
        
        if is_valid:
            self.polling = False
            messagebox.showinfo("Success", "Activation Approved by Admin!")
            self.on_success_callback(username)
        else:
            # Re-poll in 5 seconds
            self.root.after(5000, lambda: self.poll_for_activation(username))

    def show(self):
        self.frame.pack(fill=tk.BOTH, expand=True)

    def hide(self):
        self.polling = False
        self.frame.pack_forget()

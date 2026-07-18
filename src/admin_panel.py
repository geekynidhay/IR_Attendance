"""
Admin Panel for IR Attendance
Manage licenses, generate codes, revoke access, and view user attendance reports.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import sys
import threading
from license_manager import LicenseManager
from system_utils import SystemUtils
from encryption_utils import EncryptionUtils
from pathlib import Path
from drive_manager import drive_manager


class AdminPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("IR Attendance - Admin Panel")
        self.root.geometry("900x650")
        
        # Set Icon
        try:
            icon_path = SystemUtils.resource_path("Admin Icon.png")
            if Path(icon_path).exists():
                icon_img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_img)
        except Exception as e:
            print(f"Icon Load fail: {e}")
            
        # Password Protection
        self.ask_password()
        
        # Theme initialization
        style = ttk.Style()
            
        # Fix font sizes for high-DPI / macOS
        default_font = ("Arial", 13)
        style.configure(".", font=default_font)
        style.configure("TButton", font=default_font)
        style.configure("TNotebook.Tab", font=default_font, padding=[10, 2])
        style.configure("Treeview", font=("Arial", 12), rowheight=28)
        style.configure("Treeview.Heading", font=("Arial", 13, "bold"))

        
        # Hardcoded Credentials for Portability
        admin_config = {
            "database_url": "https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/",
            "api_secret": "apng5Iuu7ijd8QYZLTj9ZZ4UGsmYE6wLaenzhFRx"
        }
        self.lm = LicenseManager(manual_config=admin_config)
        
        self.create_ui()
        self.refresh_list()
        
        # Start Drive sync on startup (non-blocking)
        self.root.after(1500, self._start_drive_sync)
        
    def ask_password(self):
        """Prompt for password before showing UI"""
        self.root.withdraw()
        from tkinter import simpledialog
        password = simpledialog.askstring("Login", "Enter Admin Password:", show='*')
        if password == "Nidhay@2003":
            self.root.deiconify()
        else:
            messagebox.showerror("Error", "Incorrect Password")
            sys.exit(0)
        
    def create_ui(self):
        # ── Drive status bar (top of window) ─────────────────────────────
        self.drive_status_frame = ttk.Frame(self.root, height=36)
        self.drive_status_frame.pack(fill=tk.X, side=tk.TOP, pady=4)
        self.drive_status_frame.pack_propagate(False)

        self._drive_dot = tk.Canvas(self.drive_status_frame, width=14, height=14, highlightthickness=0)
        self._drive_dot.pack(side=tk.LEFT, padx=(10, 4), pady=10)
        self._drive_dot_item = self._drive_dot.create_oval(2, 2, 12, 12, fill="#888888", outline="")

        self._drive_status_lbl = ttk.Label(self.drive_status_frame, text="Google Drive: Not Connected", font=("Arial", 13))
        self._drive_status_lbl.pack(side=tk.LEFT)

        self._drive_email_lbl = ttk.Label(self.drive_status_frame, text="", font=("Arial", 13, "italic"), foreground="#007acc")
        self._drive_email_lbl.pack(side=tk.LEFT, padx=8)

        self._drive_progress = ttk.Progressbar(self.drive_status_frame, mode="indeterminate", length=120)

        ttk.Button(self.drive_status_frame, text="Connect Google Drive",
                  command=self._connect_drive).pack(side=tk.RIGHT, padx=6, pady=4)

        ttk.Button(self.drive_status_frame, text="↺ Sync",
                  command=lambda: threading.Thread(target=self._drive_sync_worker, daemon=True).start()
                  ).pack(side=tk.RIGHT, padx=(0, 4), pady=4)

        ttk.Button(self.drive_status_frame, text="Switch Account",
                  command=self._switch_account).pack(side=tk.RIGHT, padx=(0, 4), pady=4)

        # ── Notebook ──────────────────────────────────────────────────────
        tab_control = ttk.Notebook(self.root)
        
        self.tab_generate = ttk.Frame(tab_control)
        self.tab_users = ttk.Frame(tab_control)
        self.tab_requests = ttk.Frame(tab_control)
        self.tab_userdata = ttk.Frame(tab_control)

        tab_control.add(self.tab_requests,  text='Pending Requests')
        tab_control.add(self.tab_generate,  text='Generate Activation')
        tab_control.add(self.tab_users,     text='Manage Users')
        tab_control.add(self.tab_userdata,  text='📊 User Data')
        tab_control.pack(expand=1, fill="both")
        
        self.setup_requests_tab()
        self.setup_generate_tab()
        self.setup_users_tab()
        self.setup_userdata_tab()
        
    def setup_requests_tab(self):
        frame = ttk.Frame(self.tab_requests, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh Requests", command=self.refresh_requests).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Approve Selected", command=self.approve_direct_request).pack(side=tk.LEFT, padx=10)
        
        columns = ('machine_id', 'username', 'timestamp')
        self.req_tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.req_tree.heading('machine_id', text='Machine ID')
        self.req_tree.heading('username', text='Username / Name')
        self.req_tree.heading('timestamp', text='Time')
        
        self.req_tree.column('machine_id', width=150)
        self.req_tree.column('username', width=150)
        self.req_tree.column('timestamp', width=150)
        
        self.req_tree.pack(fill=tk.BOTH, expand=True)
        
    def setup_generate_tab(self):
        frame = ttk.Frame(self.tab_generate, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Generate Activation Code", font=('Arial', 14, 'bold')).pack(pady=10)
        
        ttk.Label(frame, text="Username (as received):").pack(anchor=tk.W)
        self.user_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.user_var, width=40).pack(anchor=tk.W, pady=5)
        
        ttk.Label(frame, text="Request Code (from Client):").pack(anchor=tk.W)
        self.req_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.req_var, width=60).pack(anchor=tk.W, pady=5)
        
        ttk.Button(frame, text="Generate & Activate", command=self.generate_code).pack(pady=20)
        
        ttk.Label(frame, text="Activation Code to Send:").pack(anchor=tk.W)
        self.result_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.result_var, width=40, font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=5)
        
    def setup_users_tab(self):
        frame = ttk.Frame(self.tab_users, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh List", command=self.refresh_list).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Revoke Selected", command=self.revoke_user).pack(side=tk.LEFT, padx=10)
        
        columns = ('machine_id', 'pin', 'username', 'status', 'last_seen', 'ip', 'location')
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading('machine_id', text='Machine ID')
        self.tree.heading('pin', text='PIN')
        self.tree.heading('username', text='Username')
        self.tree.heading('status', text='Status')
        self.tree.heading('last_seen', text='Last Seen')
        self.tree.heading('ip', text='IP Address')
        self.tree.heading('location', text='Location')
        
        self.tree.column('machine_id', width=100)
        self.tree.column('pin', width=80)
        self.tree.column('username', width=100)
        self.tree.column('status', width=70)
        self.tree.column('last_seen', width=130)
        self.tree.column('ip', width=100)
        self.tree.column('location', width=150)
        
        self.tree.pack(fill=tk.BOTH, expand=True)

    def setup_userdata_tab(self):
        """User Data tab — lists all users with View Report button."""
        frame = ttk.Frame(self.tab_userdata, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Header controls
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(ctrl, text="↺  Refresh Users", command=self.refresh_userdata_list).pack(side=tk.LEFT)
        ttk.Label(ctrl, text="Click 'View Report' to see a user's attendance data from Google Drive.",
                  font=("Arial", 9), foreground="gray").pack(side=tk.LEFT, padx=12)

        # Treeview
        cols = ("machine_id", "username", "pin", "status")
        sb = ttk.Scrollbar(frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.userdata_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                           yscrollcommand=sb.set, selectmode="browse")
        sb.config(command=self.userdata_tree.yview)

        self.userdata_tree.heading("machine_id", text="Machine ID")
        self.userdata_tree.heading("username",   text="Username")
        self.userdata_tree.heading("pin",        text="PIN")
        self.userdata_tree.heading("status",     text="Status")

        self.userdata_tree.column("machine_id", width=160)
        self.userdata_tree.column("username",   width=160)
        self.userdata_tree.column("pin",        width=80, anchor=tk.CENTER)
        self.userdata_tree.column("status",     width=100, anchor=tk.CENTER)

        self.userdata_tree.pack(fill=tk.BOTH, expand=True)

        # Action button below list
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="📊  View Report", command=self._open_user_report).pack(side=tk.LEFT)
        ttk.Label(btn_row, text="(Select a user first)", font=("Arial", 9), foreground="gray").pack(side=tk.LEFT, padx=8)

    def refresh_userdata_list(self):
        """Populate the User Data tab's treeview from Firebase license list."""
        self.userdata_tree.delete(*self.userdata_tree.get_children())
        data = self.lm.list_licenses()
        if data:
            for mid, info in data.items():
                self.userdata_tree.insert("", tk.END, iid=mid, values=(
                    mid,
                    info.get("username", "N/A"),
                    info.get("activation_code", "N/A"),
                    info.get("status", "Unknown"),
                ))

    def _open_user_report(self):
        """Open the UserReportWindow for the selected user."""
        sel = self.userdata_tree.selection()
        if not sel:
            messagebox.showwarning("Select User", "Please select a user to view their report.", parent=self.root)
            return

        mid = sel[0]
        item = self.userdata_tree.item(mid)
        vals = item["values"]
        username = vals[1] if vals else "Unknown"
        pin = vals[2] if vals else ""

        if not drive_manager.is_authenticated():
            messagebox.showwarning(
                "Not Connected",
                "Please connect Google Drive first using the 'Connect Google Drive' button at the top.",
                parent=self.root
            )
            return

        from user_report_window import UserReportWindow
        UserReportWindow(self.root, drive_manager, username, pin)

    # ── Google Drive helpers ────────────────────────────────────────────────

    def _connect_drive(self):
        """Authenticate with Google Drive using Service Account JSON."""
        from tkinter import filedialog
        
        sa_path = None
        # If we don't already have a saved key, ask the user to provide one
        import os
        if not os.path.exists(drive_manager.sa_path):
            sa_path = filedialog.askopenfilename(
                parent=self.root,
                title="Select Service Account JSON Key",
                filetypes=[("JSON Files", "*.json")]
            )
            if not sa_path:
                return  # User cancelled

        self._drive_status_lbl.config(text="Connecting to Google Drive…", foreground="#007acc")
        self._drive_progress.pack(side=tk.LEFT, padx=8, pady=6)
        self._drive_progress.start(12)

        def _worker():
            ok, msg = drive_manager.authenticate(sa_json_path=sa_path)
            def _done():
                self._drive_progress.stop()
                self._drive_progress.pack_forget()
                if ok:
                    self._drive_dot.itemconfig(self._drive_dot_item, fill="#43a047")
                    self._drive_status_lbl.config(text="Google Drive: Connected", foreground="#2e7d32")
                    self._drive_email_lbl.config(text=f"({drive_manager.connected_email})")
                else:
                    self._drive_dot.itemconfig(self._drive_dot_item, fill="#e53935")
                    self._drive_status_lbl.config(text=f"Drive Error: {msg}", foreground="#c62828")
            self.root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _switch_account(self):
        """Revoke token and re-authenticate with a new Google account."""
        if messagebox.askyesno("Switch Account",
                               "This will disconnect the current Service Account.\n"
                               "You will be asked to provide a new JSON key file.\n\nContinue?",
                               parent=self.root):
            drive_manager.revoke_and_disconnect()
            self._drive_email_lbl.config(text="")
            self._drive_dot.itemconfig(self._drive_dot_item, fill="#888888")
            self._drive_status_lbl.config(text="Google Drive: Disconnected", foreground="#666666")
            self._connect_drive()

    def _start_drive_sync(self):
        """Auto-sync Drive cache on startup if already authenticated."""
        import os
        if os.path.exists(drive_manager.sa_path):
            self._connect_drive()  # This will also trigger sync via the worker

    def _drive_sync_worker(self):
        """Background thread: download all user files from Drive to local cache."""
        if not drive_manager.is_authenticated():
            return

        def _progress(current, total, msg):
            def _ui():
                self._drive_status_lbl.config(
                    text=f"Syncing: {msg} ({current}/{total})", foreground="#007acc")
            self.root.after(0, _ui)

        drive_manager.sync_all_to_cache(progress_cb=_progress)

        def _done():
            self._drive_status_lbl.config(text="Google Drive: Synced ✓", foreground="#2e7d32")
            # Also refresh the user data tab
            self.refresh_userdata_list()
        self.root.after(0, _done)

    # ── Existing methods ────────────────────────────────────────────────────

    def generate_code(self):
        user = self.user_var.get().strip()
        req = self.req_var.get().strip()
        
        if not user or not req:
            messagebox.showwarning("Error", "Fill all fields")
            return
            
        success, result = self.lm.activate_license(req, user)
        if success:
            self.result_var.set(result)
            messagebox.showinfo("Success", f"Activation Code Generated: {result}")
            self.refresh_list()
        else:
            messagebox.showerror("Error", result)
            
    def refresh_list(self):
        self.refresh_users()
        self.refresh_requests()
        self.refresh_userdata_list()

    def refresh_users(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        data = self.lm.list_licenses()
        if data:
            for mid, info in data.items():
                self.tree.insert('', tk.END, values=(
                    mid,
                    info.get('activation_code', 'N/A'),
                    info.get('username', 'N/A'),
                    info.get('status', 'Unknown'),
                    info.get('last_seen', 'Never'),
                    info.get('ip', 'Unknown'),
                    info.get('location', 'Unknown')
                ))
                
    def revoke_user(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        mid = item['values'][0]
        
        if messagebox.askyesno("Confirm", f"Revoke license for {mid}?"):
            success, msg = self.lm.revoke_license(mid)
            if success:
                messagebox.showinfo("Success", "User permanently removed from list")
                self.refresh_list()
            else:
                messagebox.showerror("Error", msg)

    def refresh_requests(self):
        for i in self.req_tree.get_children():
            self.req_tree.delete(i)
            
        data = self.lm.list_activation_requests()
        if data:
            for mid, info in data.items():
                self.req_tree.insert('', tk.END, values=(
                    mid,
                    info.get('username', 'N/A'),
                    info.get('timestamp', 'N/A')
                ))

    def approve_direct_request(self):
        selected = self.req_tree.selection()
        if not selected:
            return
            
        item = self.req_tree.item(selected[0])
        mid = item['values'][0]
        username = item['values'][1]
        
        if messagebox.askyesno("Confirm", f"Approve activation for {username} ({mid})?"):
            success, result = self.lm.activate_license(mid, username)
            if success:
                self.lm.delete_activation_request(mid)
                messagebox.showinfo("Success", f"User {username} Activated!")
                self.refresh_list()
            else:
                messagebox.showerror("Error", result)


if __name__ == "__main__":
    root = tk.Tk()
    app = AdminPanel(root)
    root.mainloop()

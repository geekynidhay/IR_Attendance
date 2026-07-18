import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import webbrowser
import sys
import os

# Ensure we can import sync_website
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from sync_website import run_sync

COLORS = {
    "default": "#c5c6c7",
    "error":   "#ff6b6b",
    "warning": "#ffa94d",
    "skip":    "#adb5bd",
    "success": "#66fcf1",
    "header":  "#66fcf1",
}

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IR Attendance - Web Sync")
        self.root.geometry("640x480")
        self.root.configure(bg="#0b0c10")
        self._jwt_error_shown = False

        # Style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TFrame", background="#0b0c10")
        style.configure("TButton", background="#1f2833", foreground="#66fcf1",
                        font=("Inter", 10, "bold"), padding=10)
        style.map("TButton",
                  background=[("active", "#66fcf1")],
                  foreground=[("active", "#0b0c10")])
        style.configure("TLabel", background="#0b0c10", foreground="#c5c6c7", font=("Inter", 12))

        # Main Frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="IR Attendance — Web Sync",
                  font=("Inter", 16, "bold"), foreground="#66fcf1").pack(pady=(0, 15))

        # Log area
        self.log_area = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, width=70, height=14,
            bg="#1f2833", fg="#c5c6c7", font=("Menlo", 10),
            borderwidth=0, selectbackground="#66fcf1", selectforeground="#0b0c10"
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Configure colour tags
        for tag, color in COLORS.items():
            self.log_area.tag_config(tag, foreground=color)
        self.log_area.config(state=tk.DISABLED)

        # Short status bar
        self.status_var = tk.StringVar(value="Starting sync…")
        tk.Label(main_frame, textvariable=self.status_var,
                 bg="#0b0c10", fg="#adb5bd",
                 font=("Inter", 10), anchor="w").pack(fill=tk.X, pady=(0, 5))

        # Button Frame (hidden until sync finishes)
        self.btn_frame = ttk.Frame(main_frame)
        ttk.Button(self.btn_frame, text="Open Website", command=self.open_website).pack(side=tk.LEFT, padx=10)
        ttk.Button(self.btn_frame, text="Close", command=self.root.destroy).pack(side=tk.LEFT, padx=10)

        # Start sync
        self.root.after(500, self.start_sync)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _classify(self, msg):
        low = msg.lower()
        if "invalid jwt" in low or "invalid_grant" in low or "refresherror" in low:
            return "error"
        if "failed to fetch" in low or "❌" in low:
            return "error"
        if "skipped" in low or "warning" in low or "⚠" in low:
            return "warning"
        if "✅" in low or "published" in low or "authenticated" in low or "generated" in low:
            return "success"
        if "=====" in msg:
            return "header"
        return "default"

    def log(self, msg):
        """Thread-safe coloured log. Suppresses raw Python tracebacks."""
        # Suppress raw Python exception stack lines — we show a cleaner message
        skip_patterns = [
            "Traceback", "File \"", "raise ", "googleapiclient",
            "google.auth", "google.oauth2", "_client.py", "httplib2",
            "http.py", "credentials.py", "service_account.py",
            "During handling", "error_description", "'error':",
        ]
        if any(p in msg for p in skip_patterns):
            return

        # One-time friendly JWT error explanation
        if "invalid jwt" in msg.lower() or "invalid_grant" in msg.lower():
            if not self._jwt_error_shown:
                self._jwt_error_shown = True
                self._append(
                    "\n🔑  SERVICE ACCOUNT KEY IS INVALID\n"
                    "   Your Google Drive key needs to be regenerated.\n\n"
                    "   Steps to fix:\n"
                    "   1. Go to console.cloud.google.com\n"
                    "   2. IAM & Admin → Service Accounts\n"
                    "   3. Click your service account → Keys tab\n"
                    "   4. Delete the old key → Add Key → Create new key (JSON)\n"
                    "   5. Replace the service_account.json file with the new one\n\n"
                    "   ✅ Your website content was NOT deleted — all pages preserved.\n",
                    "warning"
                )
            return

        tag = self._classify(msg)
        self._append(msg, tag)

        # Update status bar
        low = msg.lower()
        if "fetching" in low:
            self.root.after(0, lambda m=msg: self.status_var.set(m.strip()))
        elif "skipped" in low:
            self.root.after(0, lambda: self.status_var.set("Pages preserved (Drive unreachable)"))
        elif "pushing" in low:
            self.root.after(0, lambda: self.status_var.set("Pushing to GitHub…"))

    def _append(self, msg, tag="default"):
        def _do():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, msg + "\n", tag)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        self.root.after(0, _do)

    # ── sync lifecycle ─────────────────────────────────────────────────────────

    def start_sync(self):
        def worker():
            success = run_sync(log_cb=self.log)
            self.root.after(0, self.on_sync_complete, success)
        threading.Thread(target=worker, daemon=True).start()

    def on_sync_complete(self, success):
        self.btn_frame.pack(pady=15)
        if success:
            self._append("\n✅  Sync complete! Website is up to date.", "success")
            self.status_var.set("Done ✅")
        else:
            self._append("\n❌  Sync failed. See log above.", "error")
            self.status_var.set("Failed ❌")

    def open_website(self):
        webbrowser.open("https://geekynidhay.github.io/IR_Attendance/")


if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (640 // 2)
    y = (root.winfo_screenheight() // 2) - (480 // 2)
    root.geometry(f"+{x}+{y}")
    root.mainloop()

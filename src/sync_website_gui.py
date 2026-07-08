import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import webbrowser
import sys
import os

# Ensure we can import sync_website
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from sync_website import run_sync

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IR Attendance - Web Sync")
        self.root.geometry("600x400")
        self.root.configure(bg="#0b0c10")
        
        # Style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TFrame", background="#0b0c10")
        style.configure("TButton", background="#1f2833", foreground="#66fcf1", font=("Inter", 10, "bold"), padding=10)
        style.map("TButton", background=[("active", "#66fcf1")], foreground=[("active", "#0b0c10")])
        style.configure("TLabel", background="#0b0c10", foreground="#c5c6c7", font=("Inter", 12))

        # Main Frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Syncing Entire Website...", font=("Inter", 16, "bold"), foreground="#66fcf1")
        title_label.pack(pady=(0, 15))

        # Progress Text
        self.log_area = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, width=60, height=12,
            bg="#1f2833", fg="#c5c6c7", font=("Menlo", 10), borderwidth=0
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=10)
        self.log_area.config(state=tk.DISABLED)

        # Button Frame (hidden initially)
        self.btn_frame = ttk.Frame(main_frame)
        
        self.btn_open = ttk.Button(self.btn_frame, text="Open Website", command=self.open_website)
        self.btn_open.pack(side=tk.LEFT, padx=10)
        
        self.btn_close = ttk.Button(self.btn_frame, text="Close", command=self.root.destroy)
        self.btn_close.pack(side=tk.LEFT, padx=10)

        # Start sync process
        self.root.after(500, self.start_sync)

    def log(self, msg):
        """Thread-safe way to update the text area"""
        def update_text():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        self.root.after(0, update_text)

    def start_sync(self):
        def worker():
            success = run_sync(log_cb=self.log)
            self.root.after(0, self.on_sync_complete, success)
            
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def on_sync_complete(self, success):
        self.btn_frame.pack(pady=15)
        if success:
            self.log("\n✅ SYNC COMPLETE! Changes have been published.")
        else:
            self.log("\n❌ SYNC FAILED. Please check the logs above.")

    def open_website(self):
        webbrowser.open("https://geekynidhay.github.io/IR_Attendance/")

if __name__ == "__main__":
    root = tk.Tk()
    app = SyncApp(root)
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (600 // 2)
    y = (root.winfo_screenheight() // 2) - (400 // 2)
    root.geometry(f"+{x}+{y}")
    root.mainloop()

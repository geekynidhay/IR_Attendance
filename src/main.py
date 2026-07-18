"""
IR Attendance - Main Application
Entry point for the Image Splitter and Image Viewer application
"""
import ctypes
try:
    # Set process DPI awareness to Per Monitor v2 (2) or fallback to System (1)
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
from pathlib import Path

# Add pyperclip fallback
try:
    import pyperclip
except ImportError:
    print("Warning: pyperclip not available. Clipboard functionality will use tkinter.")


# Global variables to hold the loaded modules
WindowManager = None
SplitterMode = None
ViewerMode = None
ExtractorMode = None
PdfExtractorMode = None
AIAttendanceMode = None
MobileAttendanceMode = None
Image = None
ImageTk = None
MirrorEngine = None
Footer = None
MobileManager = None
config = None
LicenseManager = None
ActivationMode = None
server = None

def do_heavy_imports(progress_callback):
    global WindowManager, SplitterMode, ViewerMode, ExtractorMode, PdfExtractorMode
    global AIAttendanceMode, MobileAttendanceMode, Image, ImageTk
    global MirrorEngine, Footer, MobileManager, config, LicenseManager, ActivationMode, server
    
    progress_callback(10, "Loading UI components...")
    import window_manager
    WindowManager = window_manager.WindowManager
    import footer
    Footer = footer.Footer
    import config as cfg
    config = cfg.config
    
    progress_callback(30, "Loading image processing components...")
    from PIL import Image as PILImage, ImageTk as PILImageTk
    Image = PILImage
    ImageTk = PILImageTk
    import splitter_mode
    SplitterMode = splitter_mode.SplitterMode
    import viewer_mode
    ViewerMode = viewer_mode.ViewerMode
    import extractor_mode
    ExtractorMode = extractor_mode.ExtractorMode
    
    progress_callback(50, "Loading AI attendance modes...")
    import ai_attendance_mode
    AIAttendanceMode = ai_attendance_mode.AIAttendanceMode
    import mobile_attendance_mode
    MobileAttendanceMode = mobile_attendance_mode.MobileAttendanceMode
    
    progress_callback(70, "Loading mobile manager and mirror engine...")
    import mirror_engine
    MirrorEngine = mirror_engine.MirrorEngine
    import mobile_manager
    MobileManager = mobile_manager.MobileManager
    
    progress_callback(85, "Loading backend server and license manager...")
    import server as srv
    server = srv
    import license_manager
    LicenseManager = license_manager.LicenseManager
    import activation_mode
    ActivationMode = activation_mode.ActivationMode
    import pdf_extractor_mode
    PdfExtractorMode = pdf_extractor_mode.PdfExtractorMode
    
    progress_callback(100, "Ready!")

class LoadingScreen:
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        
        self.frame = tk.Frame(self.root, bg='#121212')
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        container = tk.Frame(self.frame, bg='#121212')
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.title_lbl = tk.Label(container, text="IR Attendance", font=('Segoe UI', 36, 'bold'), fg='#00D4FF', bg='#121212')
        self.title_lbl.pack(pady=20)
        
        self.status_lbl = tk.Label(container, text="Starting...", font=('Segoe UI', 12), fg='#AAAAAA', bg='#121212')
        self.status_lbl.pack(pady=5)
        
        style = ttk.Style()
        try:
            style.theme_use('default')
        except:
            pass
        style.configure("TProgressbar", thickness=10, background='#00D4FF', troughcolor='#333333', bordercolor='#121212', lightcolor='#00D4FF', darkcolor='#00D4FF')
        
        self.progress = ttk.Progressbar(container, style="TProgressbar", length=400, mode='determinate')
        self.progress.pack(pady=10)
        
        self.root.after(100, self.start_loading)
        
    def start_loading(self):
        def update_progress(val, text):
            self.progress['value'] = val
            self.status_lbl.config(text=text)
            self.root.update()
            
        try:
            do_heavy_imports(update_progress)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules:\\n{e}")
            sys.exit(1)
            
        self.root.after(200, self.finish)
        
    def finish(self):
        self.frame.destroy()
        self.on_complete()

class GifLabel(tk.Label):
    def __init__(self, master, filename, delay=50):
        self.filename = filename
        self.delay = delay
        self.frames = []
        try:
            img = Image.open(filename)
            # Resize if too big, the new icon gif is usually small but let's be safe
            for i in range(getattr(img, 'n_frames', 1)):
                # Resize to be visible but not overwhelming
                frame = img.copy().convert('RGBA')
                frame.thumbnail((80, 40), Image.Resampling.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(frame))
        except Exception as e:
            print(f"Error loading gif: {e}")
            
        super().__init__(master, image=self.frames[0] if self.frames else None)
        try:
            # Try to match the background color if possible
            bg = master.cget('background')
            self.config(background=bg)
        except:
            pass
            
        self.idx = 0
        if len(self.frames) > 1:
            self.animate()
            
    def animate(self):
        self.idx = (self.idx + 1) % len(self.frames)
        self.config(image=self.frames[self.idx])
        self.after(self.delay, self.animate)
import os
import socket
import re

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # In dev mode, if running from src, icon is in parent
        # If running from root, icon is current dir
        base_path = os.path.abspath(".")
        # Check parent if not found in current (assuming script in src/)
        if not (Path(base_path) / relative_path).exists():
             parent_path = Path(base_path).parent
             if (parent_path / relative_path).exists():
                 base_path = str(parent_path)
             # One more check if running directly inside src
             elif (Path(__file__).parent.parent / relative_path).exists():
                 base_path = str(Path(__file__).parent.parent)

    return os.path.join(base_path, relative_path)

class WelcomeScreen:
    """Welcome screen that fades into the main application"""
    def __init__(self, root, username, on_complete):
        self.root = root
        self.username = username
        self.on_complete = on_complete
        
        # Main container
        self.frame = tk.Frame(root) 
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Centering container
        container = tk.Frame(self.frame)
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Greeting label parts
        hi_label = tk.Label(container, text="Hi, ", font=('Segoe UI', 32))
        hi_label.pack(side=tk.LEFT)
        
        # User Name in bold
        name_label = tk.Label(container, text=username, font=('Segoe UI', 32, 'bold'), 
                             fg='#0078D7')
        name_label.pack(side=tk.LEFT)
        
        # Start timer for 3 seconds
        self.root.after(3000, self.start_fade)

    def start_fade(self):
        self.alpha = 1.0
        self.fade_step()

    def fade_step(self):
        if self.alpha > 0.1:
            self.alpha -= 0.05
            self.root.attributes("-alpha", self.alpha)
            self.root.after(20, self.fade_step)
        else:
            self.frame.destroy()
            # Instantly restore full opacity before building the main application UI
            self.root.attributes("-alpha", 1.0)
            self.on_complete()

class ModernButton(tk.Label):
    """A beautiful, platform-independent flat button with hover effects based on tk.Label."""
    def __init__(self, master, text, command, bg='#1976D2', fg='white', hover_bg='#1565C0', font=('Segoe UI', 11, 'bold'), width=25, height=2, **kwargs):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, width=width, height=height, cursor='hand2', relief=tk.FLAT, bd=0, **kwargs)
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
    def on_enter(self, e):
        self.config(bg=self.hover_bg)
        
    def on_leave(self, e):
        self.config(bg=self.bg)
        
    def on_click(self, e):
        self.command()

class IRAttendanceApp:
    """Main application class"""
    
    def __init__(self, root, license_manager=None):
        self.root = root
        self.lm = license_manager # Store the license manager instance
        # Initialize window manager
        self.window_manager = WindowManager(self.root)
        
        # Register global hotkey (Ctrl+Space) to bring window to focus
        self.window_manager.register_hotkey('ctrl+space')
        
        # Current mode
        self.current_mode = None
        self.mirror_engine = None
        self.last_detected_devices = []
        self._handshake_in_progress = False
        
        # Configure style
        self.setup_style()
        
        # Create main menu
        self.create_menu()
        
        # Mode instances (created on demand)
        self.splitter_mode = None
        self.viewer_mode = None
        self.extractor_mode = None
        self.pdf_extractor_mode = None
        self.ai_attendance_mode = None
        self.mobile_attendance_mode = None

        
        # Ensure default directory exists
        from config import DATA_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start background service listener
        self.start_background_service()

    def start_background_service(self):
        """Launches IR_Attendance_Service.py in the background if it's not already running."""
        try:
            import subprocess
            import sys
            
            script_path = Path(__file__).parent / "IR_Attendance_Service.py"
            if script_path.exists():
                python_exe = sys.executable
                if "python.exe" in python_exe:
                    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
                else:
                    pythonw_exe = python_exe
                
                # Start it windowless, redirecting std streams so it detaches completely
                kwargs = {}
                if sys.platform == "win32":
                    kwargs["creationflags"] = 0x08000000
                subprocess.Popen([pythonw_exe, str(script_path)], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL,
                                 **kwargs)
                print("[Main] Started background service listener.")
        except Exception as e:
            print(f"[Main] Failed to start background service: {e}")

    def on_closing(self):
        """Cleanup resources and exit"""
        try:
            self.window_manager.unregister_hotkey()
        except Exception:
            pass
        if self.mirror_engine:
            try:
                self.mirror_engine.stop()
            except Exception:
                pass
        self.root.destroy()

    def setup_style(self):
        """Configure application style"""
        style = ttk.Style()
        
        # Try to use a modern theme
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')

        # Fix Treeview tag colors
        style.configure("Treeview", 
                        background="white",
                        foreground="black",
                        fieldbackground="white",
                        font=('Segoe UI', 10))
        style.map("Treeview", 
                  foreground=[('selected', '#ffffff')],
                  background=[('selected', '#0078D7')])
    
    def create_menu(self):
        """Create the main menu screen"""
        self.menu_frame = ttk.Frame(self.root)
        self.menu_frame.pack(fill=tk.BOTH, expand=True)
        
        # Center container
        center_frame = ttk.Frame(self.menu_frame)
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Title
        ttk.Label(center_frame, text="IR Attendance", 
                 style='Title.TLabel').pack(pady=20)
                 
        self.dashboard_frame = ttk.Frame(center_frame)
        self.dashboard_frame.pack(pady=10, fill=tk.X)
        
        # Mobile Status Bar
        self.mobile_status_frame = ttk.Frame(center_frame, padding=(10, 5))
        self.mobile_status_frame.pack(fill=tk.X)
        self.mobile_status_label = ttk.Label(self.mobile_status_frame, text="Phone Status: Checking...", font=('Segoe UI', 10, 'bold'))
        self.mobile_status_label.pack()
        
        # Eye Mirror Server Status
        ip_list = server.start_server()
        ip_str = ip_list[0] if ip_list else "Unknown"
        self.eye_mirror_label = ttk.Label(self.mobile_status_frame, text=f"Eye Mirror IP: {ip_str} (Waiting...)", font=('Segoe UI', 14, 'bold'), foreground='orange')
        self.eye_mirror_label.pack(pady=(5, 0))
        
        # Share Screen Prompt (Prominent Location)
        self.share_prompt_frame = ttk.Frame(center_frame, padding=10)
        self.share_btn = ModernButton(self.share_prompt_frame, text="📲 CLICK HERE TO SHARE SCREEN", 
                                      command=self.launch_native_mirror,
                                      bg='#FF9800', hover_bg='#F57C00', fg='white',
                                      width=35, height=2)
        self.share_btn.pack()
        
        self.update_dashboard()
        self.periodic_mobile_check() # Start status loop
        
        # Google Drive Integration Button
        self.cloud_sync_frame = ttk.Frame(center_frame, padding=10)
        self.cloud_sync_frame.pack()
        self.btn_cloud = ModernButton(self.cloud_sync_frame, text="☁ Connect Google Drive (JSON Key)", 
                                      command=self.upload_drive_key,
                                      bg='#2196F3', hover_bg='#1976D2', fg='white',
                                      width=35, height=2)
        self.btn_cloud.pack()
        
        # Import Batch Button
        self.import_batch_frame = ttk.Frame(center_frame, padding=5)
        self.import_batch_frame.pack()
        self.btn_import = ModernButton(self.import_batch_frame, text="📥 Import Batch (Archive)", 
                                      command=self.import_batch,
                                      bg='#8E24AA', hover_bg='#7B1FA2', fg='white',
                                      width=35, height=2)
        self.btn_import.pack()
        
        ttk.Label(center_frame, text="Select a mode to begin",
                 style='Subtitle.TLabel').pack(pady=10)
        
        # Mode buttons
        button_frame = ttk.Frame(center_frame)
        button_frame.pack(pady=30)
        
        manual_btn = ModernButton(button_frame, text="Manual Mode",
                                  command=self.open_manual_menu,
                                  bg='#4CAF50', hover_bg='#43A047', fg='white', width=25, height=2)
        manual_btn.pack(pady=10)
 
        auto_btn = ModernButton(button_frame, text="Automatic Mode",
                                command=self.open_auto_menu,
                                bg='#1976D2', hover_bg='#1565C0', fg='white', width=25, height=2)
        auto_btn.pack(pady=10)
        
        admin_btn = ModernButton(button_frame, text="Admin Mode",
                                 command=self.open_admin_modes,
                                 bg='#37474F', hover_bg='#2C3E50', fg='white', width=25, height=2)
        admin_btn.pack(pady=10)
        
        # Info
        info_text = """
JPG Splitter: Split images vertically with custom crop areas
JPG Extraction: Batch extract sub-images from JPGs
PDF Extraction: Extract images from PDF reports with OCR
Computer Attendance: Navigate and view images and mark attendance
 
Hotkey: Ctrl+Space to bring window to focus from any application
        """
        ttk.Label(center_frame, text=info_text, justify=tk.CENTER,
                 font=('Segoe UI', 9), foreground='#888888').pack(pady=20)
        
        # Footer
        self.footer = Footer(self.menu_frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
    
    def upload_drive_key(self):
        from tkinter import filedialog, messagebox
        import sys
        # ensure drive_manager is imported correctly from src
        try:
            from drive_manager import drive_manager
        except ImportError:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from drive_manager import drive_manager
            
        filepath = filedialog.askopenfilename(
            title="Select Service Account JSON Key",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return
            
        success, msg = drive_manager.authenticate(filepath)
        if success:
            messagebox.showinfo("Success", "Google Drive connected successfully for automatic sync!")
        else:
            messagebox.showerror("Error", f"Failed to connect: {msg}")
            
    def import_batch(self):
        """Import a batch archive from IR Admin Utility"""
        from tkinter import filedialog, messagebox
        import threading
        import sys
        
        try:
            from system_utils import SystemUtils
        except ImportError:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from system_utils import SystemUtils
            
        filepath = filedialog.askopenfilename(
            title="Select Batch Archive (Output from Admin Utility)",
            filetypes=[
                ("Archive files", "*.zip *.rar *.7z *.tar *.gz *.tgz *.bz2 *.xz"),
                ("All files", "*.*")
            ]
        )
        if not filepath:
            return
            
        # Temporarily disable button
        original_text = self.btn_import.cget("text")
        self.btn_import.config(text="⏳ Extracting... Please wait", state=tk.DISABLED)
        
        def _extract():
            try:
                # Use standard target directory consistent with config
                from config import DATA_DIR
                dest_dir = str(DATA_DIR)
                
                SystemUtils.extract_archive(filepath, dest_dir)
                
                # Re-enable button in main thread
                self.root.after(0, lambda: self.btn_import.config(text=original_text, state=tk.NORMAL))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Batch successfully imported into your database!\nIt will now appear in your Mode dropdowns."))
            except Exception as e:
                self.root.after(0, lambda: self.btn_import.config(text=original_text, state=tk.NORMAL))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to import batch:\n{e}"))
                
        threading.Thread(target=_extract, daemon=True).start()
    def open_manual_menu(self):
        """Open Manual Mode selection screen"""
        self.menu_frame.pack_forget()
        
        if hasattr(self, 'manual_frame'):
            self.manual_frame.destroy()
            
        self.manual_frame = ttk.Frame(self.root)
        self.manual_frame.pack(fill=tk.BOTH, expand=True)
        
        center = ttk.Frame(self.manual_frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        ttk.Label(center, text="Manual Mode", font=('Segoe UI', 18, 'bold'), foreground='#00D4FF').pack(pady=20)
        
        ModernButton(center, text="💻 Computer Attendance", 
                     command=lambda: [self.manual_frame.pack_forget(), self.open_viewer_mode(is_auto=False, return_screen='manual')],
                     bg='#4CAF50', hover_bg='#43A047', fg='white', width=25, height=2).pack(pady=10)
                   
        ModernButton(center, text="📱 Mobile Attendance", 
                     command=lambda: [self.manual_frame.pack_forget(), self.open_mobile_attendance_mode(return_screen='manual')],
                     bg='#00897B', hover_bg='#00695C', fg='white', width=25, height=2).pack(pady=10)
                   
        ModernButton(center, text="← Back to Menu", 
                     command=lambda: [self.manual_frame.pack_forget(), self.menu_frame.pack(fill=tk.BOTH, expand=True)],
                     bg='#37474F', hover_bg='#2C3E50', fg='white', width=25, height=2).pack(pady=20)

    def open_auto_menu(self):
        """Open Automatic Mode selection screen"""
        self.menu_frame.pack_forget()
        
        if hasattr(self, 'auto_frame'):
            self.auto_frame.destroy()
            
        self.auto_frame = ttk.Frame(self.root)
        self.auto_frame.pack(fill=tk.BOTH, expand=True)
        
        center = ttk.Frame(self.auto_frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        ttk.Label(center, text="Automatic Mode", font=('Segoe UI', 18, 'bold'), foreground='#00D4FF').pack(pady=20)
        
        ModernButton(center, text="💻 Computer Attendance", 
                     command=lambda: [self.auto_frame.pack_forget(), self.open_viewer_mode(is_auto=True, return_screen='auto')],
                     bg='#4CAF50', hover_bg='#43A047', fg='white', width=25, height=2).pack(pady=10)
                   
        # New Icon GIF on the RIGHT of the button inside a frame
        ai_row = ttk.Frame(center)
        ai_row.pack(fill=tk.X, pady=10)
        
        btn = ModernButton(ai_row, text="📱 Mobile Attendance", 
                           command=lambda: [self.auto_frame.pack_forget(), self.open_ai_attendance_mode(return_screen='auto')],
                           bg='#1976D2', hover_bg='#1565C0', fg='white', width=25, height=2)
        btn.pack(anchor=tk.CENTER)
        
        gif_path = Path(__file__).parent / "new_icon.gif"
        if gif_path.exists():
            self.new_gif = GifLabel(ai_row, str(gif_path))
            self.new_gif.place(relx=0.5, rely=0.5, x=160, anchor=tk.CENTER)
                   
        ModernButton(center, text="← Back to Menu", 
                     command=lambda: [self.auto_frame.pack_forget(), self.menu_frame.pack(fill=tk.BOTH, expand=True)],
                     bg='#37474F', hover_bg='#2C3E50', fg='white', width=25, height=2).pack(pady=20)

    def open_admin_modes(self):
        """Open Admin Modes selection screen"""
        self.menu_frame.pack_forget()
        
        if hasattr(self, 'admin_frame'):
            self.admin_frame.destroy()
            
        self.admin_frame = ttk.Frame(self.root)
        self.admin_frame.pack(fill=tk.BOTH, expand=True)
        
        # Center content
        center = ttk.Frame(self.admin_frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        ttk.Label(center, text="Admin Modes", font=('Segoe UI', 18, 'bold'), foreground='#00D4FF').pack(pady=20)
        
        ModernButton(center, text="JPG Splitter", 
                     command=lambda: [self.admin_frame.pack_forget(), self.open_splitter_mode()],
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=25, height=2).pack(pady=10)
                   
        ModernButton(center, text="JPG Extraction", 
                     command=lambda: [self.admin_frame.pack_forget(), self.open_extractor_mode()],
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=25, height=2).pack(pady=10)
                   
        ModernButton(center, text="PDF Extraction", 
                     command=lambda: [self.admin_frame.pack_forget(), self.open_pdf_extractor_mode()],
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=25, height=2).pack(pady=10)
 
                   
        ModernButton(center, text="← Back to Menu", 
                     command=lambda: [self.admin_frame.pack_forget(), self.menu_frame.pack(fill=tk.BOTH, expand=True)],
                     bg='#37474F', hover_bg='#2C3E50', fg='white', width=25, height=2).pack(pady=20)

    def open_splitter_mode(self):
        """Open Image Splitter mode"""
        self.menu_frame.pack_forget()
        
        if not self.splitter_mode:
            self.splitter_mode = SplitterMode(self.root, self.return_to_menu)
        
        self.splitter_mode.show()
        self.current_mode = 'splitter'
    
    def open_extractor_mode(self):
        """Open Image Extractor mode"""
        self.menu_frame.pack_forget()
        
        if not self.extractor_mode:
            self.extractor_mode = ExtractorMode(self.root, self.return_to_menu)
            
        self.extractor_mode.show()
        self.current_mode = 'extractor'
        
    def open_viewer_mode(self, is_auto=True, return_screen=None):
        """Open Image Viewer mode"""
        self.menu_frame.pack_forget()
        self.last_submenu = return_screen
        
        if not self.viewer_mode or self.viewer_mode.is_auto != is_auto:
            if self.viewer_mode:
                self.viewer_mode.frame.destroy()
            self.viewer_mode = ViewerMode(self.root, self.return_to_menu, self.window_manager, self.lm, is_auto=is_auto)
        
        self.viewer_mode.show()
        self.current_mode = 'viewer'

    def open_pdf_extractor_mode(self):
        """Open PDF Extractor mode"""
        self.menu_frame.pack_forget()
        
        if not self.pdf_extractor_mode:
            self.pdf_extractor_mode = PdfExtractorMode(self.root, self.return_to_menu)
            
        self.pdf_extractor_mode.show()
        self.current_mode = 'pdf_extractor'


    def open_ai_attendance_mode(self, return_screen=None):
        """Open AI Attendance automation mode"""
        self.menu_frame.pack_forget()
        self.last_submenu = return_screen
        
        if not self.ai_attendance_mode:
            self.ai_attendance_mode = AIAttendanceMode(
                self.root, self.return_to_menu, self.window_manager, self.lm)
        
        self.ai_attendance_mode.show()
        self.current_mode = 'ai_attendance'

    def open_mobile_attendance_mode(self, return_screen=None):
        """Open Mobile Attendance mode — sends ID to phone numpad"""
        self.menu_frame.pack_forget()
        self.last_submenu = return_screen

        if not self.mobile_attendance_mode:
            self.mobile_attendance_mode = MobileAttendanceMode(
                self.root, self.return_to_menu, self.window_manager, self.lm)

        self.mobile_attendance_mode.show()
        self.current_mode = 'mobile_attendance'

    def launch_screen_mirror(self):
        """Launch scrcpy screen mirroring"""
        import server
        ip = server.registered_phone_ip
        success, msg = MobileManager.start_mirroring(ip)
        if not success:
            messagebox.showerror("Mirror Error", f"Failed to start screen mirror:\n{msg}")
        else:
            print(f"Screen mirror launched: {msg}")

    def launch_native_mirror(self):
        """Launch integrated scrcpy mirroring."""
        self.share_prompt_frame.pack_forget()
        
        mirror_win = tk.Toplevel(self.root)
        mirror_win.title("Integrated Smartphone Mirror")
        mirror_win.geometry("450x800")
        mirror_win.configure(bg='black')
        
        # Container frame for the embedded window
        mirror_container = tk.Frame(mirror_win, bg='black')
        mirror_container.pack(fill=tk.BOTH, expand=True)
        
        import server
        ip = server.registered_phone_ip
        
        self.mirror_engine = MirrorEngine(mirror_container)
        started = self.mirror_engine.start(ip)
        
        if not started:
            messagebox.showerror("Mirror Error", "scrcpy.exe not found! Please place it in the platform-tools folder.")
            mirror_win.destroy()
            return
            
        def on_close():
            if self.mirror_engine:
                self.mirror_engine.stop()
                self.mirror_engine = None
            mirror_win.destroy()
        
        mirror_win.protocol("WM_DELETE_WINDOW", on_close)

    def periodic_mobile_check(self):
        """Periodically update the mobile connection status and check for new devices"""
        if hasattr(self, 'mobile_status_label') and self.mobile_status_label.winfo_exists():
            status_text, phone_ip = MobileManager.get_status_info()
            self.mobile_status_label.config(text=f"Phone Status: {status_text}")
            
            # Show/Hide share prompt
            if "Connected" in status_text:
                self.mobile_status_label.config(foreground='#2E7D32') # Green
                
                # Auto-wireless handshake if USB
                if "USB" in status_text and not self._handshake_in_progress:
                    self._handshake_in_progress = True
                    def _do_handshake():
                        MobileManager.setup_wireless_connection()
                        self._handshake_in_progress = False
                    threading.Thread(target=_do_handshake, daemon=True).start()

                # Show button only if mirror is NOT already open
                if self.mirror_engine is None or not self.mirror_engine.running:
                    self.share_prompt_frame.pack(pady=5)
                else:
                    self.share_prompt_frame.pack_forget()
            else:
                self.mobile_status_label.config(foreground='#C62828') # Red
                self.share_prompt_frame.pack_forget()
                # If it was disconnected while running, stop engine
                if self.mirror_engine:
                    self.mirror_engine.stop()
                    self.mirror_engine = None
                    
        # Update Eye Mirror Status
        if server.is_phone_connected():
            self.eye_mirror_label.config(text=f"Eye Mirror IP: {server.start_server()[0]} (Connected)", foreground='green')
        else:
            self.eye_mirror_label.config(text=f"Eye Mirror IP: {server.start_server()[0]} (Waiting...)", foreground='orange')
                
        # Update every 3 seconds for better responsiveness
        self.root.after(3000, self.periodic_mobile_check)
    
    def return_to_menu(self):
        """Return to main menu or previous submenu"""
        if self.current_mode == 'splitter' and self.splitter_mode:
            self.splitter_mode.hide()
        elif self.current_mode == 'viewer' and self.viewer_mode:
            self.viewer_mode.hide()
        elif self.current_mode == 'extractor' and self.extractor_mode:
            self.extractor_mode.hide()
        elif self.current_mode == 'pdf_extractor' and self.pdf_extractor_mode:
            self.pdf_extractor_mode.hide()
        elif self.current_mode == 'ai_attendance' and self.ai_attendance_mode:
            self.ai_attendance_mode.hide()
        elif self.current_mode == 'mobile_attendance' and self.mobile_attendance_mode:
            self.mobile_attendance_mode.hide()

        self.current_mode = None
        server.update_image(None)
        
        if hasattr(self, 'last_submenu') and self.last_submenu == 'manual':
            if hasattr(self, 'manual_frame'):
                self.manual_frame.pack(fill=tk.BOTH, expand=True)
            else:
                self.menu_frame.pack(fill=tk.BOTH, expand=True)
        elif hasattr(self, 'last_submenu') and self.last_submenu == 'auto':
            if hasattr(self, 'auto_frame'):
                self.auto_frame.pack(fill=tk.BOTH, expand=True)
            else:
                self.menu_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.menu_frame.pack(fill=tk.BOTH, expand=True)
            self.update_dashboard()

    def update_dashboard(self):
        for w in self.dashboard_frame.winfo_children():
            w.destroy()
            
        
def main():
    """Main entry point"""
    try:
        root = tk.Tk()
        root.title("IR Attendance")
        root.geometry("1200x800")
        root.configure(bg='#121212')
        
        # Set window icon
        try:
            icon_path = resource_path("Icon.png")
            if Path(icon_path).exists():
                icon_img = tk.PhotoImage(file=icon_path)
                root.iconphoto(True, icon_img)
        except Exception as e:
            print(f"Failed to load icon: {e}")

        def launch_app(lm, username=None):
            if username:
                config.set("license_user", username)
            
            for widget in root.winfo_children():
                widget.destroy()
            
            MobileManager.launch_mirror_app()
            
            # Auto-launch BAS when IR Attendance is opened
            try:
                import subprocess
                import ctypes
                bas_path = r"C:\BAS\BAS.exe"
                if os.path.exists(bas_path):
                    # Check if running
                    output = subprocess.check_output('tasklist', creationflags=subprocess.CREATE_NO_WINDOW)
                    if b"bas.exe" not in output.lower():
                        ctypes.windll.shell32.ShellExecuteW(None, "open", bas_path, None, None, 1)
            except Exception as e:
                print(f"Failed to auto-launch BAS: {e}")
                
            user_name = config.get("license_user") or "User"
            if "--auto" in sys.argv:
                app = IRAttendanceApp(root, lm)
                if hasattr(app, 'menu_frame') and app.menu_frame:
                    app.menu_frame.pack_forget()
                app.open_viewer_mode(is_auto=True, return_screen='auto')
            else:
                WelcomeScreen(root, user_name, lambda: IRAttendanceApp(root, lm))

        def check_license():
            saved_user = config.get("license_user")
            lm = LicenseManager()
            if saved_user:
                is_valid, msg = lm.check_license_online(saved_user)
                if is_valid:
                    launch_app(lm)
                elif "Connection Error" in msg or "Server Error" in msg:
                    print(f"[License] Warning: Could not reach server ({msg}). Allowing offline use.")
                    launch_app(lm)
                else:
                    config.set("license_user", "")
                    msg = f"License Error: {msg}"
                    am = ActivationMode(root, lambda u: launch_app(lm, u))
                    am.status_label.config(text=msg)
                    am.show()
            else:
                am = ActivationMode(root, lambda u: launch_app(lm, u))
                am.show()

        def on_loading_complete():
            check_license()

        # Start with the Loading Screen!
        LoadingScreen(root, on_loading_complete)
            
        root.mainloop()

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

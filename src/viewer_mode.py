"""
Image Viewer Mode for IR Attendance application
Main viewer interface with folder navigation, image display, and controls
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import pyperclip
from config import config
from folder_navigator import FolderNavigator
from image_controls import ImageControls, ImageDisplay
import time
import keyboard
import platform
ALT_KEY = 'command' if platform.system() == 'Darwin' else 'alt'
import os
import shutil
import server  # Import the new server module
import pyautogui
import attendance_report  # Daily log writer + midnight push
from PIL import Image, ImageTk

from footer import Footer

class BrightnessDialog(tk.Toplevel):
    """Custom dialog to adjust brightness with forced focus and dark theme"""
    def __init__(self, parent, title, prompt):
        super().__init__(parent)
        self.title(title)
        self.configure(bg="#1a1a2e")
        self.resizable(False, False)
        
        # Center of the screen
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 300, 110
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.attributes("-topmost", True)
        
        # UI Elements
        tk.Label(self, text=prompt, fg="white", bg="#1a1a2e", font=("Arial", 11, "bold")).pack(pady=(15, 5))
        
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.entry_var, font=("Arial", 12), width=10, justify="center")
        self.entry.pack(pady=5)
        
        tk.Label(self, text="Press Enter to OK  |  Esc to Cancel", fg="#8888aa", bg="#1a1a2e", font=("Arial", 8)).pack(pady=2)
        
        self.result = None
        
        # Bind keys
        self.entry.bind("<Return>", self.on_ok)
        self.bind("<Escape>", self.on_cancel)
        
        # Force map window to create OS HWND immediately
        try:
            self.update()
        except:
            pass
            
        # Force grab and focus
        self.grab_set()
        
        # Deferred focus force to guarantee focus over other active apps
        self.after(20, self.force_entry_focus)
        self.after(100, self.force_entry_focus)
        self.after(250, self.force_entry_focus)
        
        self.wait_window()
        
    def force_entry_focus(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            hwnd = self.winfo_id()
            parent_hwnd = user32.GetParent(hwnd)
            target_hwnd = parent_hwnd if parent_hwnd else hwnd
            
            # Get foreground window and attach thread input to bypass OS focus stealing block
            fore_hwnd = user32.GetForegroundWindow()
            if fore_hwnd and fore_hwnd != target_hwnd:
                fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
                curr_thread = kernel32.GetCurrentThreadId()
                
                # Attach thread input
                user32.AttachThreadInput(curr_thread, fore_thread, True)
                
                # Set foreground focus
                user32.SetForegroundWindow(target_hwnd)
                user32.SetActiveWindow(target_hwnd)
                
                # Detach thread input
                user32.AttachThreadInput(curr_thread, fore_thread, False)
            else:
                user32.SetForegroundWindow(target_hwnd)
                user32.SetActiveWindow(target_hwnd)
        except Exception as e:
            print(f"[Focus] Thread attach error: {e}")
            
        try:
            self.entry.focus_force()
            self.entry.focus_set()
        except:
            pass
            
    def on_ok(self, event=None):
        val = self.entry_var.get().strip()
        if val.isdigit():
            self.result = int(val)
        self.destroy()
        
    def on_cancel(self, event=None):
        self.result = None
        self.destroy()

class ViewerMode:
    """Image Viewer Mode UI and logic"""
    
    def __init__(self, parent, on_back_callback, window_manager, license_manager, is_auto=True):
        self.on_back_callback = on_back_callback
        self.parent = parent
        self.window_manager = window_manager
        self.lm = license_manager
        self.is_auto = is_auto
        self.frame = ttk.Frame(parent)
        
        # Default Data Directory
        self.data_dir = Path("C:/IR Attendance")
        if not self.data_dir.exists():
            try:
                self.data_dir.mkdir(parents=True, exist_ok=True)
            except:
                pass
        
        # State
        self.current_images = []
        self.current_image_index = -1
        self.current_brightness = 100
        self.current_zoom = 100
        self.target_window = None
        self.is_auto_running = False
        self.auto_job = None
        self.subfolder_statuses = {}
        # Opening/closing timestamps per subfolder: {path: {"opening": "HH:MM:SS", "closing": "HH:MM:SS"}}
        self._attendance_times = {}
        # HUD bar state
        self.hud_bar = None
        
        # Store default ttk style colors
        self.style = ttk.Style()
        self.style_defaults = {
            'TFrame': {'background': self.style.lookup('TFrame', 'background')},
            'TLabel': {'background': self.style.lookup('TLabel', 'background'), 'foreground': self.style.lookup('TLabel', 'foreground')},
            'TLabelframe': {'background': self.style.lookup('TLabelframe', 'background'), 'foreground': self.style.lookup('TLabelframe', 'foreground')},
            'TLabelframe.Label': {'background': self.style.lookup('TLabelframe.Label', 'background'), 'foreground': self.style.lookup('TLabelframe.Label', 'foreground')},
            'TButton': {'background': self.style.lookup('TButton', 'background'), 'foreground': self.style.lookup('TButton', 'foreground')},
            'Treeview': {'background': self.style.lookup('Treeview', 'background'), 'foreground': self.style.lookup('Treeview', 'foreground'), 'fieldbackground': self.style.lookup('Treeview', 'fieldbackground')}
        }

        # Start the local server for mobile mirroring
        self.server_ip = server.start_server()
        
        self.create_ui()
        
        # Bind keyboard events
        self._bind_keys()
        
        # Start Firebase Sync
        self.start_firebase_sync()
        
        # Build the floating HUD bar (hidden until auto starts)
        self._hud_bar_create()
        
    def start_firebase_sync(self):
        """Starts a background thread to sync live viewer data to Firebase"""
        if not hasattr(self.lm, 'activation_code') or not self.lm.activation_code:
            print("Firebase Sync Disabled: No activation PIN found.")
            return
            
        import threading
        self._firebase_sync_running = True
        
        # Setup event and buffer for async non-blocking status writing
        self._sync_event = threading.Event()
        self._pending_payload = None
        
        self._writer_thread = threading.Thread(target=self._firebase_write_worker, daemon=True)
        self._writer_thread.start()
        
        self._sync_thread = threading.Thread(target=self._firebase_sync_loop, daemon=True)
        self._sync_thread.start()
        
        # Start command listener too
        self._cmd_thread = threading.Thread(target=self._firebase_command_listener, daemon=True)
        self._cmd_thread.start()
        
    def _firebase_write_worker(self):
        """Asynchronously writes the pending state payload to Firebase to avoid blocking state detection"""
        import requests
        
        pin = self.lm.activation_code
        url = f"{self.lm.database_url}/sessions/{pin}.json?auth={self.lm.api_secret}"
        
        while getattr(self, '_firebase_sync_running', False):
            # Wait for either a new state update or the 1-second heartbeat limit
            self._sync_event.wait(timeout=1.0)
            if not getattr(self, '_firebase_sync_running', False):
                break
                
            payload = self._pending_payload
            if payload is not None:
                self._pending_payload = None
                self._sync_event.clear()
                try:
                    requests.put(url, json=payload, timeout=5)
                except Exception as e:
                    print(f"Firebase async write error: {e}")
        
    def _firebase_sync_loop(self):
        """Pushes the current state of the viewer to Firebase with change detection for zero latency"""
        import json
        
        last_payload_str = None
        last_write_time = 0
        
        while getattr(self, '_firebase_sync_running', False):
            try:
                folders = []
                total = 0
                success_cnt = 0
                fail_cnt = 0
                skip_cnt = 0
                
                # Determine current index
                current_selected = self.folder_tree.selection()
                current_id = current_selected[0] if current_selected else None
                current_index = -1
                
                children = self.folder_tree.get_children()
                if current_id in children:
                    current_index = children.index(current_id)
 
                for idx, item in enumerate(children):
                    total += 1
                    text = self.folder_tree.item(item, 'text')
                    tags = self.folder_tree.item(item, 'tags')
                    
                    if 'marked' in tags:
                        status = 'fail'
                        fail_cnt += 1
                    elif 'not_working' in tags:
                        status = 'skip'
                        skip_cnt += 1
                    elif 'success' in tags:
                        status = 'success'
                        success_cnt += 1
                    elif current_index != -1 and idx < current_index:
                        status = 'success'
                        success_cnt += 1
                    else:
                        status = 'pending'
                        
                    folders.append({"name": text, "status": status})
                    
                selected = self.folder_tree.selection()
                current_item = self.folder_tree.item(selected[0], 'text') if selected else ""
                
                # Construct payload (ignoring timestamp for comparison)
                payload = {
                    "batch_name": self.batch_var.get(),
                    "available_batches": list(self.batch_combo.cget('values')),
                    "global_default_brightness": self.default_brightness_var.get(),
                    "current_folder": current_item,
                    "is_auto_running": getattr(self, 'is_auto_running', False),
                    "stats": {
                        "total": total,
                        "success": success_cnt,
                        "fail": fail_cnt,
                        "skip": skip_cnt
                    },
                    "folders": folders
                }
                
                current_payload_str = json.dumps(payload, sort_keys=True)
                now = time.time()
                
                # Delegate to async worker if payload changed OR if 1.0 second has passed (heartbeat)
                if current_payload_str != last_payload_str or (now - last_write_time >= 1.0):
                    # Add timestamp to actual sent payload
                    sent_payload = payload.copy()
                    sent_payload["timestamp"] = now
                    
                    self._pending_payload = sent_payload
                    self._sync_event.set()
                    
                    last_payload_str = current_payload_str
                    last_write_time = now
                
                # Small sleep to keep CPU usage low while maintaining fast response (50ms)
                time.sleep(0.05)
            except Exception as e:
                print(f"Firebase sync error: {e}")
                time.sleep(0.5)
                
    def _firebase_command_listener(self):
        """Listens for remote START/STOP commands"""
        import requests
        import json
        
        pin = self.lm.activation_code
        url = f"{self.lm.database_url}/sessions/{pin}/command.json?auth={self.lm.api_secret}"
        
        headers = {'Accept': 'text/event-stream'}
        
        while getattr(self, '_firebase_sync_running', False):
            try:
                response = requests.get(url, headers=headers, stream=True, timeout=60)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if not getattr(self, '_firebase_sync_running', False):
                            break
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith('data: '):
                                data_str = decoded[6:]
                                if data_str != "null":
                                    try:
                                        cmd_data = json.loads(data_str)
                                        # Expected structure is SSE: cmd_data could be {'path': '/', 'data': 'start'}
                                        if isinstance(cmd_data, dict) and 'data' in cmd_data:
                                            action = cmd_data['data']
                                            if isinstance(action, dict) and 'action' in action:
                                                action = action['action']
                                            
                                            if action == "start":
                                                self.parent.after(0, self.start_auto_attendance)
                                            elif action == "stop":
                                                self.parent.after(0, self.stop_auto_attendance)
                                            elif action == "load_batch":
                                                target_batch = cmd_data['data'].get('batch_name', '')
                                                if target_batch:
                                                    self.parent.after(0, lambda b=target_batch: [self.batch_var.set(b), self.load_selected_batch()])
                                            elif action == "set_brightness":
                                                target_val = cmd_data['data'].get('value', '')
                                                if str(target_val):
                                                    self.parent.after(0, lambda v=target_val: self.default_brightness_var.set(str(v)))
                                                
                                            # Clear the command to prevent looping asynchronously
                                            import threading
                                            threading.Thread(target=requests.delete, args=(url,), daemon=True).start()
                                    except Exception as e:
                                        print(f"Cmd parse error: {e}")
                else:
                    time.sleep(1)
            except Exception as e:
                print(f"Firebase cmd listener error: {e}")
                time.sleep(1)
    
    def create_ui(self):
        """Create the viewer mode UI matching the layout"""
        # Main container with footer
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        self.footer = Footer(self.frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Header
        header_frame = ttk.Frame(self.content_container)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(header_frame, text="💻 Computer Attendance", 
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        # Server Info Label
        ips = " / ".join(self.server_ip) if isinstance(self.server_ip, list) else self.server_ip
        ttk.Label(header_frame, text=f"Mirror IPs: {ips}", 
                 font=('Arial', 10), foreground='blue').pack(side=tk.LEFT, padx=20)
        
        ttk.Button(header_frame, text="← Back to Menu", 
                  command=self.on_back_callback).pack(side=tk.RIGHT)
        
        # Batch Selection Dropdown
        batch_sel_frame = ttk.Frame(header_frame)
        batch_sel_frame.pack(side=tk.RIGHT, padx=20)
        
        ttk.Label(batch_sel_frame, text="Select Batch:").pack(side=tk.LEFT, padx=5)
        self.batch_var = tk.StringVar()
        self.batch_combo = ttk.Combobox(batch_sel_frame, textvariable=self.batch_var, width=20, state='readonly')
        self.batch_combo.pack(side=tk.LEFT, padx=5)
        self.batch_combo.bind('<<ComboboxSelected>>', lambda e: self.load_selected_batch())
        
        ttk.Button(batch_sel_frame, text="↺", width=3, command=self.refresh_batch_list).pack(side=tk.LEFT)
        
        ttk.Label(batch_sel_frame, text="  |  ").pack(side=tk.LEFT)
        ttk.Button(batch_sel_frame, text="⬆ Import", command=self._import_settings, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(batch_sel_frame, text="⬇ Export", command=self._export_settings, width=8).pack(side=tk.LEFT, padx=2)
        
        # ── Batch Information Header ---
        self.batch_info_frame = ttk.Frame(self.content_container, padding=(10, 0))
        self.batch_info_frame.pack(fill=tk.X)
        
        # Using a distinct style for the batch info
        info_inner = ttk.Frame(self.batch_info_frame, borderwidth=1, relief="solid", padding=5)
        info_inner.pack(fill=tk.X)
        
        self.lbl_batch_id = ttk.Label(info_inner, text="Batch ID: ---", font=('Arial', 12, 'bold'))
        self.lbl_batch_id.pack(side=tk.LEFT, padx=10)
        
        # Pack In/Out times to the RIGHT
        self.lbl_batch_out = ttk.Label(info_inner, text="Out Time: --:--", font=('Arial', 11))
        self.lbl_batch_out.pack(side=tk.RIGHT, padx=10)
        
        self.lbl_to_sep = ttk.Label(info_inner, text="To", font=('Arial', 11))
        self.lbl_to_sep.pack(side=tk.RIGHT, padx=5)
        
        self.lbl_batch_in = ttk.Label(info_inner, text="In Time: --:--", font=('Arial', 11))
        self.lbl_batch_in.pack(side=tk.RIGHT, padx=10)
        
        self.lbl_time_sep = ttk.Label(info_inner, text="|", font=('Arial', 12))
        self.lbl_time_sep.pack(side=tk.RIGHT, padx=5)
        
        # Center Attendance ID Label with bigger text
        self.lbl_attendance_id_top = ttk.Label(info_inner, text="Attendance ID: ---", font=('Arial', 16, 'bold'), foreground='#1976D2')
        self.lbl_attendance_id_top.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_attendance_id_top.config(anchor=tk.CENTER)
        
        # ── Auto Attendance Control Panel ──────────────────────────────────────
        if self.is_auto:
            self.acp = ttk.Frame(self.content_container, padding=(10, 5))
            self.acp.pack(fill=tk.X)
            
            ttk.Label(self.acp, text="Auto Attendance:").pack(side=tk.LEFT, padx=(10, 5))
            self.auto_status_var = tk.StringVar(value="OFF")
            self.auto_status_lbl = tk.Label(self.acp, textvariable=self.auto_status_var, 
                                            fg="red", font=('Arial', 12, 'bold'))
            self.auto_status_lbl.pack(side=tk.LEFT)
            
            # T&C Consent Checkbutton
            self.tnc_var = tk.BooleanVar(value=config.get('pc_tnc_enabled', False))
            self.chk_tnc = ttk.Checkbutton(self.acp, text="T&C", variable=self.tnc_var, 
                                           command=lambda: config.set('pc_tnc_enabled', self.tnc_var.get()))
            self.chk_tnc.pack(side=tk.LEFT, padx=15)
            
            # Calibrate button
            self.btn_calib_pc = ttk.Button(self.acp, text="📍 Calibrate PC T&C", command=self.calibrate_pc_tnc)
            self.btn_calib_pc.pack(side=tk.LEFT, padx=5)
            
            self.auto_guideline = ttk.Label(self.acp, text="To start the auto attendance please press A", 
                                            font=('Arial', 10, 'bold'), foreground='blue')
            self.auto_guideline.pack(side=tk.RIGHT, padx=10)

        # --- Instructions ---
        inst_frame = ttk.Frame(self.content_container)
        inst_frame.pack(fill=tk.X, padx=10, pady=5)
        
        inst_text = "Navigation: ↓ Next | ↑ Prev | → Next Img | ← Prev Img | Ctrl+Scroll: Zoom | Ctrl+Space: Focus"
        if self.is_auto:
            inst_text += " | Ctrl+Enter: Auto-Type | A: Auto Mode"
        else:
            inst_text += " | Enter: Auto-Type"
            
        ttk.Label(inst_frame, 
                 text=inst_text,
                 font=('Arial', 9)).pack()
        
        # Main content area
        main_frame = ttk.Frame(self.content_container)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left panel: Folder tree
        left_frame = ttk.LabelFrame(main_frame, text="Folders", width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        # Filter Toggle
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(2, 5))
        self.show_marked_only_var = tk.BooleanVar(value=False)
        self.toggle_btn = tk.Button(filter_frame, text="Show Marked Only: OFF", bg='gray', fg='white', 
                                    font=('Arial', 9, 'bold'), relief=tk.FLAT, command=self.toggle_marked_filter)
        self.toggle_btn.pack(fill=tk.X, padx=5)
        
        # Folder tree with scrollbar
        tree_scroll = ttk.Scrollbar(left_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.folder_tree = ttk.Treeview(left_frame, yscrollcommand=tree_scroll.set)
        self.folder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.folder_tree.yview)

        # Bind Left/Right on Treeview to prevent naive selection change (Jumping to top)
        self.folder_tree.bind('<Left>', lambda e: self.block_tree_nav(e, 'left'))
        self.folder_tree.bind('<Right>', lambda e: self.block_tree_nav(e, 'right'))
        # Intercept Up/Down on Treeview — route through our navigator to prevent skipping
        self.folder_tree.bind('<Up>', lambda e: self._tree_navigate_up(e))
        self.folder_tree.bind('<Down>', lambda e: self._tree_navigate_down(e))

        
        # Initialize folder navigator
        self.navigator = FolderNavigator(self.folder_tree, self.on_subfolder_change)
        
        # Macro button
        copy_btn_frame = ttk.Frame(left_frame)
        copy_btn_frame.pack(fill=tk.X, pady=5)
        
        btn_text = "Run Macro (Ctrl+Enter)" if self.is_auto else "Run Macro (Enter)"
        ttk.Button(copy_btn_frame, text=btn_text, 
                  command=self.execute_macro).pack(fill=tk.X, padx=2)
        
        # Center-left panel: Brightness control (vertical)
        brightness_frame = ttk.LabelFrame(main_frame, text="Brightness", width=100)
        brightness_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        brightness_frame.pack_propagate(False)
        
        # Vertical brightness control
        bright_controls = ttk.Frame(brightness_frame)
        bright_controls.pack(expand=True)
        
        # Default Brightness Field
        ttk.Label(bright_controls, text="Default").pack(pady=(0, 2))
        self.default_brightness_var = tk.StringVar(value=config.get("global_default_brightness", ""))
        self.default_brightness_entry = ttk.Entry(bright_controls, textvariable=self.default_brightness_var, width=5)
        self.default_brightness_entry.pack(pady=(0, 10))
        self.default_brightness_var.trace_add("write", self.on_default_brightness_change)

        tk.Button(bright_controls, text="+", font=('Arial', 12, 'bold'), width=3, relief=tk.RAISED,
                  command=self.increase_brightness).pack(pady=5)
        
        self.brightness_var = tk.IntVar(value=100)
        self.brightness_slider = ttk.Scale(bright_controls, from_=200, to=0,
                                          orient=tk.VERTICAL, variable=self.brightness_var,
                                          command=self.on_brightness_change, length=300)
        self.brightness_slider.pack(pady=5)
        
        tk.Button(bright_controls, text="-", font=('Arial', 14, 'bold'), width=3, relief=tk.RAISED,
                  command=self.decrease_brightness).pack(pady=5)
        
        self.brightness_label = ttk.Label(bright_controls, text="100%")
        self.brightness_label.pack(pady=5)
        
        # Right panel: Preview and Image display
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Info section (Batch ID, Attendance ID, Sr No)
        info_wrapper = ttk.Frame(right_frame)
        info_wrapper.pack(fill=tk.X, pady=(0, 5))
        
        # Row 2 Wrapper for Attendance ID and Sr No
        row2_frame = ttk.Frame(info_wrapper)
        row2_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Sr No
        sr_frame = ttk.LabelFrame(row2_frame, text="Sr No")
        sr_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.sr_label = tk.Label(sr_frame, text="---", font=('Arial', 12, 'bold'), anchor=tk.CENTER)
        self.sr_label.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Attendance ID
        attendance_frame = ttk.LabelFrame(row2_frame, text="Attendance ID")
        attendance_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.preview_label = tk.Label(attendance_frame, text="---", font=('Arial', 14, 'bold'), anchor=tk.CENTER)
        self.preview_label.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Marked Counter
        marked_counter_frame = ttk.LabelFrame(row2_frame, text="Marked")
        marked_counter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.marked_count_label = tk.Label(marked_counter_frame, text="0", font=('Arial', 12, 'bold'), anchor=tk.CENTER)
        self.marked_count_label.pack(fill=tk.BOTH, expand=True, pady=10)

        # Cut Counter
        cut_counter_frame = ttk.LabelFrame(row2_frame, text="Cut")
        cut_counter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.cut_count_label = tk.Label(cut_counter_frame, text="0", font=('Arial', 12, 'bold'), anchor=tk.CENTER)
        self.cut_count_label.pack(fill=tk.BOTH, expand=True, pady=10)

        # Success Counter
        success_counter_frame = ttk.LabelFrame(row2_frame, text="Success")
        success_counter_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.success_count_label = tk.Label(success_counter_frame, text="0", font=('Arial', 12, 'bold'), fg='green', anchor=tk.CENTER)
        self.success_count_label.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Row 3 Wrapper for Live Status Display
        row3_frame = ttk.LabelFrame(info_wrapper, text="Attendance Status")
        row3_frame.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        self.status_display_label = tk.Label(
            row3_frame, 
            text="IDLE", 
            font=('Arial', 12, 'bold'), 
            anchor=tk.CENTER
        )
        self.status_display_label.pack(fill=tk.BOTH, expand=True, pady=8)
        
        # Main image display
        image_frame = ttk.LabelFrame(right_frame, text="Image")
        image_frame.pack(fill=tk.BOTH, expand=True)
        
        self.image_canvas = tk.Canvas(image_frame, bg='gray')
        self.image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ── Full Screen Auto Overlay ──────────────────────────────────────────
        if self.is_auto:
            self.auto_overlay = tk.Toplevel(self.parent)
            self.auto_overlay.withdraw()
            self.auto_overlay.overrideredirect(True)
            self.auto_overlay.transient(self.parent)
            self.auto_overlay.attributes("-topmost", False)
            self.auto_overlay.attributes("-alpha", 0.85)
            self.auto_overlay.config(bg='#000000')
            
            self.overlay_status_lbl = tk.Label(self.auto_overlay, text="IDLE", font=('Arial', 24, 'bold'), fg='#888888', bg='#000000')
            self.overlay_status_lbl.pack(pady=(60, 5))
            
            # Sr. No displayed on overlay
            self.overlay_srno_lbl = tk.Label(self.auto_overlay, text="", font=('Arial', 18), fg='#888888', bg='#000000')
            self.overlay_srno_lbl.pack(pady=(0, 5))
            
            self.overlay_id_lbl = tk.Label(self.auto_overlay, text="---", font=('Arial', 80, 'bold'), fg='white', bg='#000000')
            self.overlay_id_lbl.pack(pady=10)
            
            self.overlay_timer_lbl = tk.Label(self.auto_overlay, text="---", font=('Arial', 120, 'bold'), fg='#4CAF50', bg='#000000')
            self.overlay_timer_lbl.pack(pady=(10, 0))
            
            self.overlay_progress_canvas = tk.Canvas(self.auto_overlay, height=20, bg='#222222', highlightthickness=0)
            self.overlay_progress_canvas.pack(fill=tk.X, padx=100, pady=20)
            self.overlay_progress_bar = self.overlay_progress_canvas.create_rectangle(0, 0, 0, 20, fill='#4CAF50')
            
            tk.Label(self.auto_overlay, text="Press 'A' to Emergency Stop", font=('Arial', 14), fg='#555555', bg='#000000').pack(side=tk.BOTTOM, pady=50)
        
        # Initialize image display with encryption key
        key = self.lm.encryption_key if self.lm else None
        self.image_display = ImageDisplay(self.image_canvas, self.preview_label, 
                                         on_view_change=self.update_server_image,
                                         encryption_key=key)
        
        # Current image info
        info_frame = ttk.Frame(self.content_container)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.info_label = ttk.Label(info_frame, text="No image loaded", font=('Arial', 9))
        self.info_label.pack()
        
        # Register the dropdown refresh (MUST BE AT THE END)
        self.refresh_batch_list()

    def _export_settings(self):
        """Export config.json to a user-selected location."""
        import shutil
        if not config.config_file.exists():
            messagebox.showwarning("Warning", "No config file to export yet.", parent=self.parent)
            return
            
        save_path = filedialog.asksaveasfilename(
            parent=self.parent,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            initialfile="IR_Attendance_Settings.json",
            title="Export Settings"
        )
        if save_path:
            try:
                shutil.copy2(config.config_file, save_path)
                messagebox.showinfo("Success", f"Settings exported to:\n{save_path}", parent=self.parent)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export settings:\n{e}", parent=self.parent)

    def _import_settings(self):
        """Import config.json from a user-selected location."""
        import shutil
        open_path = filedialog.askopenfilename(
            parent=self.parent,
            filetypes=[("JSON Files", "*.json")],
            title="Import Settings"
        )
        if open_path:
            try:
                # Merge the imported settings into the existing config
                with open(open_path, 'r', encoding='utf-8') as f:
                    imported_settings = json.load(f)
                
                # Update current config in memory and save
                config.settings.update(imported_settings)
                config.save_config()
                
                messagebox.showinfo("Success", "Settings imported successfully!", parent=self.parent)
                
                # Optionally refresh UI values
                self.default_brightness_var.set(config.get("global_default_brightness", ""))
                self.refresh_batch_list()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import settings:\n{e}", parent=self.parent)

    def refresh_batch_list(self, force_load=False):
        """Scan C:/IR Attendance for folders and update dropdown"""
        if not self.data_dir.exists():
            self.batch_combo['values'] = []
            return
            
        def _fetch_and_update():
            ended_batches = {}
            if self.lm and getattr(self.lm, 'database_url', None) and getattr(self.lm, 'activation_code', None):
                try:
                    import requests
                    url = f"{self.lm.database_url}/sessions/{self.lm.activation_code}/ended_batches.json"
                    if self.lm.api_secret:
                        url += f"?auth={self.lm.api_secret}"
                    resp = requests.get(url, timeout=3)
                    if resp.status_code == 200 and resp.json():
                        ended_batches = resp.json()
                except Exception as e:
                    print(f"Failed to fetch ended batches: {e}")

            def _ui_update():
                marked_folders = config.get('marked_folders', [])
                display_folders = []
                
                for folder in self.data_dir.iterdir():
                    if folder.is_dir():
                        name = folder.name
                        if name == 'Reports':
                            continue
                        # Skip if this batch has been ended by admin
                        batch_id = name.split(' - ')[0].strip() if ' - ' in name else name
                        if ended_batches.get(batch_id):
                            continue
                            
                        # Check if any subfolder is marked
                        has_marked = False
                        try:
                            for subfolder in folder.iterdir():
                                if subfolder.is_dir() and str(subfolder) in marked_folders:
                                    has_marked = True
                                    break
                        except:
                            pass
                        
                        if has_marked:
                            display_folders.append(f"{name} 🔴")
                        else:
                            display_folders.append(name)
                
                folders = sorted(display_folders)
                self.batch_combo['values'] = folders
                
                # Auto-select last one or first one
                last_batch = config.get('last_batch_path', '')
                if last_batch:
                    last_name = Path(last_batch).name
                    # Find matching display name (with or without indicator)
                    match = next((f for f in folders if f.startswith(last_name)), None)
                    if match:
                        self.batch_var.set(match)
                        if force_load or not hasattr(self, '_first_load_done'):
                            self._first_load_done = True
                            self.load_selected_batch()
            
            self.parent.after(0, _ui_update)

        import threading
        threading.Thread(target=_fetch_and_update, daemon=True).start()

    def load_selected_batch(self):
        """Load the folder selected in the dropdown and parse its name"""
        batch_display_name = self.batch_var.get()
        if not batch_display_name:
            return
            
        # Strip indicator if present
        batch_name = batch_display_name.replace(" 🔴", "").replace(" [M]", "")
        folder_path = self.data_dir / batch_name
        if folder_path.exists():
            # Parse folder name: "45741 - 09.30 To 18.30"
            try:
                # 1. Get Batch ID (before first hyphen)
                parts = batch_name.split(' - ')
                batch_id = parts[0].strip()
                self.lbl_batch_id.config(text=f"Batch ID: {batch_id}")
                if hasattr(self, '_hud_batch_lbl') and self._hud_batch_lbl:
                    self._hud_batch_lbl.config(text=f"Batch: {batch_id}")
                
                # 2. Get Times
                if len(parts) > 1:
                    time_part = parts[1] # "09.30 To 18.30"
                    time_parts = time_part.lower().split(' to ')
                    if len(time_parts) == 2:
                        self.lbl_batch_in.config(text=f"In Time: {time_parts[0].strip()}")
                        self.lbl_batch_out.config(text=f"Out Time: {time_parts[1].strip()}")
                    else:
                        self.lbl_batch_in.config(text=f"Time: {time_part}")
                        self.lbl_batch_out.config(text="")
                else:
                    self.lbl_batch_in.config(text="")
                    self.lbl_batch_out.config(text="")
            except Exception as e:
                print(f"Error parsing folder name: {e}")
                self.lbl_batch_id.config(text=f"Batch: {batch_name}")
                if hasattr(self, '_hud_batch_lbl') and self._hud_batch_lbl:
                    self._hud_batch_lbl.config(text=f"Batch: {batch_name}")
            
            # Save as last used
            config.set('last_batch_path', str(folder_path))
            
            # Load the folder into the navigator
            self.navigator.load_folder(str(folder_path), show_marked_only=self.show_marked_only_var.get())
            
            # Auto-select first item and focus tree
            children = self.folder_tree.get_children()
            if children:
                self.folder_tree.selection_set(children[0])
                self.folder_tree.focus(children[0])
                self.folder_tree.focus_set() # Focus the tree for arrow navigation
                # The selection_set above will trigger on_tree_select -> on_subfolder_change automatically
            else:
                if hasattr(self, 'lbl_attendance_id_top'):
                    self.lbl_attendance_id_top.config(text="Attendance ID: ---")


    def browse_folder(self):
        """REMOVED: Using dropdown instead"""
        pass
    
    def load_folder(self):
        """REMOVED: Using load_selected_batch instead"""
        pass
    
    def on_subfolder_change(self, subfolder_path):
        """Handle subfolder selection change"""
        if not subfolder_path:
            return
            
        # Load images from subfolder
        self.current_images = self.navigator.get_images_in_current_subfolder()
        self.current_image_index = -1
        
        # Update Subfolder Name Label
        subfolder_name = subfolder_path.name
        self.image_display.update_subfolder_label(subfolder_name)
        if hasattr(self, 'lbl_attendance_id_top'):
            self.lbl_attendance_id_top.config(text=f"Attendance ID: {subfolder_name}")
        
        # Check marked state
        subfolder_str = str(subfolder_path)
        marked_folders = config.get('marked_folders', [])
        
        # Check not_working state
        not_working_folders = config.get('not_working_folders', [])
        is_not_working = subfolder_str in not_working_folders
        self.update_not_working_ui_state(is_not_working)
        
        self.update_ui_marked_state(subfolder_str in marked_folders)
        
        # Update Sr No Label
        try:
            total = len(self.navigator.subfolders)
            current = self.navigator.subfolders.index(subfolder_path) + 1
            self.sr_label.config(text=f"{current} / {total}")
        except ValueError:
            self.sr_label.config(text="---")
            
        # Update Counters
        self.update_marked_count()
        self.update_cut_count()
        self.update_success_count()
        
        # Update Status Display Label individually
        status_info = getattr(self, 'subfolder_statuses', {}).get(subfolder_str)
        if status_info:
            status_text, fg_color = status_info
            try:
                self.status_display_label.config(text=status_text, fg=fg_color)
            except:
                try:
                    self.status_display_label.config(text=status_text, fg="black")
                except:
                    pass
        else:
            try:
                self.status_display_label.config(text="IDLE", fg="SystemButtonText" if not is_not_working else "#888888")
            except:
                try:
                    self.status_display_label.config(text="IDLE", fg="black")
                except:
                    pass
        
        # ── PERSISTENCE: Restore per-subfolder brightness & image index ──
        saved = config.get_subfolder_settings(subfolder_name)
        global_val = self.default_brightness_var.get().strip()
        
        if global_val:
            try:
                self.current_brightness = int(global_val)
            except ValueError:
                self.current_brightness = 100
        else:
            has_override = saved.get('has_override', False)
            if has_override:
                self.current_brightness = saved.get('brightness', 100)
            else:
                self.current_brightness = 100
                
        self.current_zoom = saved.get('zoom', 100)
        saved_index = saved.get('image_index', 0)
        
        self._updating_brightness = True
        try:
            if hasattr(self, 'brightness_slider'):
                self.brightness_slider.configure(command="")
            try:
                self.brightness_var.set(self.current_brightness)
                self.brightness_label.config(text=f"{self.current_brightness}%")
            finally:
                if hasattr(self, 'brightness_slider'):
                    self.brightness_slider.configure(command=self.on_brightness_change)
        finally:
            self._updating_brightness = False
        
        # Load saved image (or first image as fallback)
        if self.current_images:
            self.current_image_index = min(saved_index, len(self.current_images) - 1)
            self.load_current_image()
        else:
            self.image_display.clear()
            self.info_label.config(text=f"Subfolder: {subfolder_name} (No images)")
            server.update_image(None)  # Clear server image
    
    def load_current_image(self):
        """Load and display the current image"""
        if self.current_image_index < 0 or self.current_image_index >= len(self.current_images):
            return
        
        image_path = self.current_images[self.current_image_index]
        success = self.image_display.load_image(image_path, self.current_brightness, 
                                               self.current_zoom)
        
        if success:
            subfolder_name = self.navigator.get_current_subfolder_name()
            self.info_label.config(
                text=f"Subfolder: {subfolder_name} | Image: {image_path.name} | "
                     f"{self.current_image_index + 1}/{len(self.current_images)}"
            )
            # Update server with new loaded image
            server.update_image(self.image_display.current_image)
            # Update PIP window image if active
            self.update_pip_image()
    
    def navigate_left(self, event=None):
        """Navigate to previous image (Left arrow)"""
        import time
        if time.time() - getattr(self, '_last_nav_time', 0) < 0.2:
            return
        self._last_nav_time = time.time()

        if not self.current_images:
            return
        
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_current_image()
            self._save_current_subfolder_state()
    
    def navigate_right(self, event=None):
        """Navigate to next image (Right arrow)"""
        import time
        if time.time() - getattr(self, '_last_nav_time', 0) < 0.2:
            return
        self._last_nav_time = time.time()

        if not self.current_images:
            return
        
        if self.current_image_index < len(self.current_images) - 1:
            self.current_image_index += 1
            self.load_current_image()
            self._save_current_subfolder_state()
    
    def navigate_up(self, event=None):
        """Navigate to previous subfolder (Up arrow)"""
        self.navigator.navigate_up()
    
    def navigate_down(self, event=None):
        """Navigate to next subfolder (Down arrow)"""
        self.navigator.navigate_down()

    def _tree_navigate_up(self, event):
        """Intercept Treeview Up key — use our index-based navigator to avoid skipping folders."""
        import platform
        if not (platform.system() == 'Windows' and getattr(self, 'is_auto', False)):
            self.navigator.navigate_up()
        return 'break'

    def _tree_navigate_down(self, event):
        """Intercept Treeview Down key — use our index-based navigator to avoid skipping folders."""
        import platform
        if not (platform.system() == 'Windows' and getattr(self, 'is_auto', False)):
            self.navigator.navigate_down()
        return 'break'
    
    def increase_brightness(self):
        """Increase brightness by 1%"""
        new_value = min(200, self.current_brightness + 1)
        self.brightness_var.set(new_value)
        self.on_brightness_change(new_value)
    
    def decrease_brightness(self):
        """Decrease brightness by 1%"""
        new_value = max(0, self.current_brightness - 1)
        self.brightness_var.set(new_value)
        self.on_brightness_change(new_value)
    
    def adjust_brightness(self, val):
        """Update brightness and redraw image"""
        try:
            new_brightness = int(float(val))
            self.current_brightness = new_brightness
            self.brightness_label.config(text=f"{new_brightness}%")
            
            # Apply to current image
            self.image_display.set_brightness(new_brightness)
            
            # Update server with modified image
            server.update_image(self.image_display.current_image)
            
            # Update PIP image if active
            self.update_pip_image()
            
            # Save to config for this subfolder
            subfolder_name = self.navigator.get_current_subfolder_name()
            if subfolder_name:
                config.set_subfolder_settings(subfolder_name, new_brightness, self.current_zoom, has_override=True)
        except:
            pass

    def on_brightness_change(self, value):
        """Handle brightness slider change"""
        new_brightness = int(float(value))
        self.current_brightness = new_brightness
        self.brightness_label.config(text=f"{new_brightness}%")
        
        # Apply to current image
        self.image_display.set_brightness(new_brightness)
        
        # Update server with modified image
        server.update_image(self.image_display.current_image)
        
        # Update PIP image if active
        self.update_pip_image()
        
        # Save to config for this subfolder (including current image index)
        if not getattr(self, '_updating_brightness', False):
            self._save_current_subfolder_state(override=True)

    def on_default_brightness_change(self, *args):
        """Handle global default brightness entry change"""
        val = self.default_brightness_var.get().strip()
        config.set("global_default_brightness", val)
        
        sf_name = self.navigator.get_current_subfolder_name()
        if not sf_name: return
        
        if val:
            try:
                new_val = int(val)
                self.current_brightness = new_val
                self._updating_brightness = True
                try:
                    if hasattr(self, 'brightness_slider'):
                        self.brightness_slider.configure(command="")
                    try:
                        self.brightness_var.set(new_val)
                        self.brightness_label.config(text=f"{new_val}%")
                    finally:
                        if hasattr(self, 'brightness_slider'):
                            self.brightness_slider.configure(command=self.on_brightness_change)
                    if hasattr(self, 'image_display'):
                        self.image_display.set_brightness(new_val)
                    self.update_server_image()
                    # Update PIP image if active
                    self.update_pip_image()
                finally:
                    self._updating_brightness = False
            except ValueError:
                pass
        else:
            self.current_brightness = 100
            self._updating_brightness = True
            try:
                if hasattr(self, 'brightness_slider'):
                    self.brightness_slider.configure(command="")
                try:
                    self.brightness_var.set(100)
                    self.brightness_label.config(text="100%")
                finally:
                    if hasattr(self, 'brightness_slider'):
                        self.brightness_slider.configure(command=self.on_brightness_change)
                if hasattr(self, 'image_display'):
                    self.image_display.set_brightness(100)
                self.update_server_image()
                # Update PIP image if active
                self.update_pip_image()
            finally:
                self._updating_brightness = False
    
    def on_zoom_change(self, value):
        """Handle zoom change"""
        self.current_zoom = int(float(value))
        
        # Apply to current image
        self.image_display.set_zoom(self.current_zoom)
        
        # Update server with modified image (visible portion)
        self.update_server_image()
        
        # Save to config for this subfolder
        subfolder_name = self.navigator.get_current_subfolder_name()
        if subfolder_name:
            config.set_subfolder_settings(subfolder_name, self.current_brightness, self.current_zoom)

    def zoom_in(self, event=None):
        """Increase zoom by 10%"""
        self.on_zoom_change(self.current_zoom + 10)

    def zoom_out(self, event=None):
        """Decrease zoom by 10%"""
        self.on_zoom_change(self.current_zoom - 10)

    def reset_zoom(self, event=None):
        """Reset zoom to 100%"""
        self.on_zoom_change(100)

    def on_mouse_wheel(self, event):
        """Handle Ctrl+MouseWheel for zoom"""
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def prompt_zoom(self, event=None):
        """Prompt user for absolute zoom percentage"""
        from tkinter import simpledialog
        val = simpledialog.askinteger("Zoom", "Enter zoom percentage:", 
                                     parent=self.frame, minvalue=5, maxvalue=2000)
        if val is not None:
            self.on_zoom_change(val)
        
        # Restore focus to navigation
        self.parent.focus_force()
        self.folder_tree.focus_set()
        selection = self.folder_tree.selection()
        if selection:
            self.folder_tree.focus(selection[0])
        return 'break'
    
    def execute_macro(self, event=None):
        """
        Execute Data Entry Macro:
        1. Alt+Tab to switch to previous window (Data Entry App)
        2. Type subfolder name
        3. Bring this window back to front
        """
        if getattr(self, 'is_auto_running', False):
            return 'break'
        subfolder_name = self.navigator.get_current_subfolder_name()
        if not subfolder_name:
            messagebox.showwarning("Warning", "No subfolder selected")
            return
            
        subfolder_path_str = str(self.navigator.current_subfolder) if self.navigator.current_subfolder else ""
        if subfolder_path_str:
            self.set_status_processing(subfolder_path_str)
            
        try:
            if self.is_auto:
                # 1. Switch to previous window (Alt+Tab)
                keyboard.press(ALT_KEY)
                keyboard.press('tab')
                time.sleep(0.05)
                keyboard.release('tab')
                keyboard.release(ALT_KEY)
                
                # Wait for switch (User requested 0.5-0.6s)
                time.sleep(0.6)
                
                # 2. Type the number (auto-submitted)
                keyboard.write(subfolder_name, delay=0.05)
                time.sleep(0.2)
                
                # 4. Switch back to this window
                keyboard.press(ALT_KEY)
                keyboard.press('tab')
                time.sleep(0.05)
                keyboard.release('tab')
                keyboard.release(ALT_KEY)
                
                time.sleep(0.5)
                
                # 5. Bring this window back to front and FOCUS THE TREE
                self.window_manager.bring_to_front()
                self.parent.focus_force()          # Force OS-level focus to our window
                self.folder_tree.focus_set()       # Then give tree keyboard focus
                # Also ensure a student is selected to keep navigation active
                selection = self.folder_tree.selection()
                if selection:
                    self.folder_tree.focus(selection[0])
            else:
                # Manual Macro: Alt+Tab -> Type ID -> Alt+Tab back
                keyboard.press(ALT_KEY)
                keyboard.press('tab')
                time.sleep(0.05)
                keyboard.release('tab')
                keyboard.release(ALT_KEY)
                
                time.sleep(0.6)
                
                keyboard.write(subfolder_name, delay=0.05)
                time.sleep(0.2)
                
                # Switch back
                keyboard.press(ALT_KEY)
                keyboard.press('tab')
                time.sleep(0.05)
                keyboard.release('tab')
                keyboard.release(ALT_KEY)
                
                time.sleep(0.5)
                
                self.window_manager.bring_to_front()
                self.parent.focus_force()
                self.folder_tree.focus_set()
                selection = self.folder_tree.selection()
                if selection:
                    self.folder_tree.focus(selection[0])
            
        except Exception as e:
            messagebox.showerror("Error", f"Macro failed: {e}")
        return 'break'
            
    def update_ui_marked_state(self, is_marked):
        """Change UI colors to indicate marked state"""
        is_not_working = False
        if hasattr(self, 'navigator') and self.navigator.current_subfolder:
            is_not_working = str(self.navigator.current_subfolder) in config.get('not_working_folders', [])
        
        default_fg = 'SystemButtonText'
        if hasattr(self, 'style_defaults') and 'TLabel' in self.style_defaults and self.style_defaults['TLabel'].get('foreground'):
            style_fg = self.style_defaults['TLabel']['foreground']
            if style_fg:
                default_fg = style_fg
        
        if is_not_working:
            default_fg = '#888888'
            
        color = 'red' if is_marked else default_fg
        ttk_color = 'red' if is_marked else default_fg
        bg_color = 'black' if is_not_working else ('#4a0000' if is_marked else 'gray')
        
        try:
            self.preview_label.config(foreground=color)
        except:
            pass
        try:
            self.lbl_batch_id.config(foreground=ttk_color)
        except:
            pass
        try:
            self.sr_label.config(foreground=color)
        except:
            pass
        try:
            self.marked_count_label.config(foreground=color)
        except:
            pass
        try:
            self.image_canvas.config(bg=bg_color)
        except:
            pass
        
        # Update labels in the info_inner frame too
        for child in self.batch_info_frame.winfo_children():
            if isinstance(child, ttk.Frame): # inner frame
                for inner_child in child.winfo_children():
                    if isinstance(inner_child, ttk.Label):
                        try:
                            # Use style if it's a themed widget, or just foreground
                            inner_child.configure(foreground=ttk_color)
                        except:
                            pass

    def prompt_brightness(self, event=None):
        """Prompt user for absolute brightness percentage"""
        if getattr(self, '_dialog_open', False):
            return 'break'
        self._dialog_open = True
        
        prev_hwnd = None
        try:
            import ctypes
            prev_hwnd = ctypes.windll.user32.GetForegroundWindow()
        except:
            pass

        try:
            # DO NOT deiconify, lift, or change topmost of the main parent window!
            # Just run update to process pending tkinter events.
            self.parent.update()
        except:
            pass
            
        dialog = BrightnessDialog(self.parent, "Brightness", "Enter brightness percentage:")
        val = dialog.result
        
        if val is not None:
            self.default_brightness_var.set(str(val))
            self.brightness_var.set(val)
            self.on_brightness_change(val)

        # Restore focus to previous foreground window (e.g. BAS / Browser)
        if prev_hwnd:
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(prev_hwnd)
            except:
                pass
        else:
            # Fallback: Restore focus to navigation
            try:
                self.parent.focus_force()
                self.folder_tree.focus_set()
                selection = self.folder_tree.selection()
                if selection:
                    self.folder_tree.focus(selection[0])
            except:
                pass
                
        self._dialog_open = False
        return 'break'
            
    def toggle_mark(self, event=None):
        """Toggle mark state for current subfolder"""
        if not self.navigator.current_subfolder:
            return
            
        subfolder_str = str(self.navigator.current_subfolder)
        marked_folders = config.get('marked_folders', [])
        
        if subfolder_str in marked_folders:
            marked_folders.remove(subfolder_str)
            is_marked = False
        else:
            marked_folders.append(subfolder_str)
            is_marked = True
            
        config.set('marked_folders', marked_folders)
        
        # Find tree item and update tags preserving others
        for child in self.folder_tree.get_children(''):
            values = self.folder_tree.item(child, 'values')
            if values and values[0] == subfolder_str:
                tags = list(self.folder_tree.item(child, 'tags'))
                if is_marked:
                    if 'marked' not in tags:
                        tags.append('marked')
                else:
                    if 'marked' in tags:
                        tags.remove('marked')
                self.folder_tree.item(child, tags=tuple(tags))
                self.folder_tree.see(child)
                break
        
        # Update UI colors immediately
        self.update_ui_marked_state(is_marked)
        self.update_marked_count()
        
        # Refresh dropdown to show/hide 🔴 WITHOUT disturbing the tree selection
        self._refresh_batch_dropdown_only()
        return 'break'

    def toggle_marked_filter(self):
        """Toggle the marked-only filter for the tree"""
        new_val = not self.show_marked_only_var.get()
        self.show_marked_only_var.set(new_val)
        
        if new_val:
            self.toggle_btn.config(text="Show Marked Only: ON", bg='#e53935')
        else:
            self.toggle_btn.config(text="Show Marked Only: OFF", bg='gray')
            
        # Reload current batch
        batch_display_name = self.batch_var.get()
        if batch_display_name:
            self.load_selected_batch()

    def update_marked_count(self):
        """Update the counter showing how many folders in current batch are marked"""
        if not hasattr(self.navigator, 'subfolders') or not self.navigator.subfolders:
            self.marked_count_label.config(text="0")
            return
            
        marked_folders = config.get('marked_folders', [])
        count = sum(1 for subfolder in self.navigator.subfolders if str(subfolder) in marked_folders)
        self.marked_count_label.config(text=str(count))

    def check_success_folders_reset(self):
        """Reset success folders if the day has changed (resets at midnight)"""
        import datetime
        today_str = datetime.date.today().isoformat()
        last_date = config.get('success_folders_date', '')
        if last_date != today_str:
            config.set('success_folders', [])
            config.set('success_folders_date', today_str)
            if hasattr(self, 'subfolder_statuses'):
                self.subfolder_statuses.clear()
            # Remove success tags from Treeview items
            for child in self.folder_tree.get_children(''):
                tags = list(self.folder_tree.item(child, 'tags'))
                if 'success' in tags:
                    tags.remove('success')
                    self.folder_tree.item(child, tags=tuple(tags))
            self.update_success_count()

    def update_success_count(self):
        """Update the counter showing how many folders in current batch are successful (green)"""
        if not hasattr(self, 'success_count_label'):
            return
        if not hasattr(self, 'navigator') or not self.navigator.subfolders:
            self.success_count_label.config(text="0")
            return
            
        self.check_success_folders_reset()
        success_folders = config.get('success_folders', [])
        count = sum(1 for subfolder in self.navigator.subfolders if str(subfolder) in success_folders)
        self.success_count_label.config(text=str(count))

    def update_cut_count(self):
        """Update the counter showing how many folders in current batch are marked as not working (Cut)"""
        if not hasattr(self, 'cut_count_label'):
            return
        if not hasattr(self, 'navigator') or not self.navigator.subfolders:
            self.cut_count_label.config(text="0")
            return
            
        not_working_folders = config.get('not_working_folders', [])
        count = sum(1 for subfolder in self.navigator.subfolders if str(subfolder) in not_working_folders)
        self.cut_count_label.config(text=str(count))

    def mark_subfolder_success(self, path_str):
        """Mark a subfolder as successful (turns green in tree)"""
        self.check_success_folders_reset()
        
        # Remove from marked_folders if it's there
        marked_folders = config.get('marked_folders', [])
        if path_str in marked_folders:
            marked_folders.remove(path_str)
            config.set('marked_folders', marked_folders)
            
        success_folders = config.get('success_folders', [])
        if path_str not in success_folders:
            success_folders.append(path_str)
            config.set('success_folders', success_folders)
            
            # Find tree item and update tags
            for child in self.folder_tree.get_children(''):
                values = self.folder_tree.item(child, 'values')
                if values and values[0] == path_str:
                    tags = list(self.folder_tree.item(child, 'tags'))
                    if 'success' not in tags:
                        tags.append('success')
                    if 'marked' in tags:
                        tags.remove('marked')
                    self.folder_tree.item(child, tags=tuple(tags))
                    break
            
            self.update_success_count()
            self._refresh_batch_dropdown_only()
            
        self.update_marked_count()

    def unmark_subfolder_success(self, path_str):
        """Remove success tag from a subfolder (reset to black/normal)"""
        self.check_success_folders_reset()
        success_folders = config.get('success_folders', [])
        if path_str in success_folders:
            success_folders.remove(path_str)
            config.set('success_folders', success_folders)
            
            # Find tree item and update tags
            for child in self.folder_tree.get_children(''):
                values = self.folder_tree.item(child, 'values')
                if values and values[0] == path_str:
                    tags = list(self.folder_tree.item(child, 'tags'))
                    if 'success' in tags:
                        tags.remove('success')
                    self.folder_tree.item(child, tags=tuple(tags))
                    break
            
            self.update_success_count()
            self._refresh_batch_dropdown_only()

    def update_attendance_status(self, is_success, message=None, folder_path=None, attendance_type=None):
        """
        Update the live status display bar below the counters.
        attendance_type: "opening" | "closing" | None
        """
        import datetime
        if not hasattr(self, 'status_display_label'):
            return
            
        if folder_path is None:
            if hasattr(self, 'navigator') and self.navigator.current_subfolder:
                folder_path = str(self.navigator.current_subfolder)
            else:
                folder_path = ""
        else:
            folder_path = str(folder_path)

        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        if is_success:
            # Track opening/closing times per subfolder
            if not hasattr(self, '_attendance_times'):
                self._attendance_times = {}
            times = self._attendance_times.get(folder_path, {})

            if attendance_type == "opening":
                times["opening"] = current_time
                times.pop("closing", None)  # reset closing if re-opened
                status_text = f"Opening : {current_time}"
                fg_color = "green"
            elif attendance_type == "closing":
                times["closing"] = current_time
                opening_t = times.get("opening", "—")
                status_text = f"Opening : {opening_t}  →  Closing : {current_time}"
                fg_color = "#888888"
            else:
                status_text = f"Success : {current_time}"
                fg_color = "green"

            if folder_path:
                self._attendance_times[folder_path] = times
        else:
            err_msg = message if message else "Failed"
            if err_msg.startswith("Opening"):
                status_text = err_msg
            else:
                status_text = f"Failed : {err_msg}"
            fg_color = "red"
            
        if folder_path:
            if not hasattr(self, 'subfolder_statuses'):
                self.subfolder_statuses = {}
            self.subfolder_statuses[folder_path] = (status_text, fg_color)
            
        current_sel_path = str(self.navigator.current_subfolder) if (hasattr(self, 'navigator') and self.navigator.current_subfolder) else ""
        if folder_path == current_sel_path or not folder_path:
            try:
                self.status_display_label.config(
                    text=status_text, 
                    fg=fg_color
                )
            except:
                pass

    def set_status_processing(self, folder_path):
        """Set the status of a subfolder to 'Processing...'"""
        path_str = str(folder_path)
        if not hasattr(self, 'subfolder_statuses'):
            self.subfolder_statuses = {}
        self.subfolder_statuses[path_str] = ("Processing...", "orange")
        
        current_sel_path = str(self.navigator.current_subfolder) if (hasattr(self, 'navigator') and self.navigator.current_subfolder) else ""
        if path_str == current_sel_path:
            try:
                self.status_display_label.config(text="Processing...", fg="orange")
            except:
                pass
    
    def show(self):
        """Show the viewer mode frame"""
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.check_success_folders_reset()
        self.refresh_batch_list(force_load=True)
        self._bind_keys()
        # Ensure keyboard bindings are active
        self.parent.focus_set()
        
        # Add global hotkeys for Auto Mode (work even when BAS window is focused)
        if self.is_auto:
            # Global hotkeys for brightness (work only in auto mode)
            try:
                keyboard.add_hotkey('b', lambda: self.parent.after(1, self.prompt_brightness))
            except:
                pass
            try:
                keyboard.add_hotkey('B', lambda: self.parent.after(1, self.prompt_brightness))
            except:
                pass

            try:
                keyboard.add_hotkey('a', lambda: self.parent.after(1, self.toggle_auto_attendance))
            except:
                pass
            try:
                keyboard.add_hotkey('right', lambda: self.parent.after(1, self.navigate_right))
            except:
                pass
            try:
                keyboard.add_hotkey('left', lambda: self.parent.after(1, self.navigate_left))
            except:
                pass
            try:
                keyboard.add_hotkey('up', lambda: self.parent.after(1, self.navigate_up))
            except:
                pass
            try:
                keyboard.add_hotkey('down', lambda: self.parent.after(1, self.navigate_down))
            except:
                pass
        # Start midnight push worker for Google Drive
        try:
            _username = config.get("license_user") or (self.lm.username if hasattr(self.lm, 'username') and self.lm.username else "default")
            def _get_dm():
                try:
                    from drive_manager import drive_manager
                    return drive_manager
                except Exception:
                    return None
            attendance_report.start_midnight_push_worker(_username, _get_dm)
        except Exception as _mpe:
            print(f"[MidnightPush] Could not start worker: {_mpe}")
    
    def hide(self):
        """Hide the viewer mode UI and gracefully stop sync"""
        self._firebase_sync_running = False
        self._unbind_keys()
        self.apply_layout_theme(False)
        self.frame.pack_forget()
        
        # Remove global hotkeys for Auto Mode
        if self.is_auto:
            try:
                keyboard.remove_hotkey('b')
            except:
                pass
            try:
                keyboard.remove_hotkey('B')
            except:
                pass
            try:
                keyboard.remove_hotkey('a')
            except:
                pass
            try:
                keyboard.remove_hotkey('right')
            except:
                pass
            try:
                keyboard.remove_hotkey('left')
            except:
                pass
            try:
                keyboard.remove_hotkey('up')
            except:
                pass
            try:
                keyboard.remove_hotkey('down')
            except:
                pass
                
        # Withdraw/destroy PIP window if active
        if hasattr(self, 'pip_window') and self.pip_window:
            try:
                self.pip_window.destroy()
            except:
                pass
            self.pip_window = None

    def _bind_keys(self):
        if self.is_auto:
            self.parent.bind('<Control-Return>', self.execute_macro)
            self.parent.bind('<Return>', lambda e: 'break')
            
            # Bind local brightness keys ONLY in auto mode
            self.parent.bind('<Key-b>', self.prompt_brightness)
            self.parent.bind('<Key-B>', self.prompt_brightness)
            self.folder_tree.bind('<Key-b>', self.prompt_brightness)
            self.folder_tree.bind('<Key-B>', self.prompt_brightness)
            if hasattr(self, 'image_canvas'):
                self.image_canvas.bind('<Key-b>', self.prompt_brightness)
                self.image_canvas.bind('<Key-B>', self.prompt_brightness)
        else:
            self.parent.bind('<Return>', self.execute_macro)
            
        self.parent.bind('<Key-m>', self.toggle_mark)
        self.parent.bind('<Key-M>', self.toggle_mark)
        self.parent.bind('<Key-n>', self.toggle_not_working)
        self.parent.bind('<Key-N>', self.toggle_not_working)
        
        self.folder_tree.bind('<Key-m>', self.toggle_mark)
        self.folder_tree.bind('<Key-M>', self.toggle_mark)
        self.folder_tree.bind('<Key-n>', self.toggle_not_working)
        self.folder_tree.bind('<Key-N>', self.toggle_not_working)
        
        if hasattr(self, 'image_canvas'):
            self.image_canvas.bind('<Key-m>', self.toggle_mark)
            self.image_canvas.bind('<Key-M>', self.toggle_mark)
            self.image_canvas.bind('<Key-n>', self.toggle_not_working)
            self.image_canvas.bind('<Key-N>', self.toggle_not_working)

        if platform.system() == 'Darwin':
            self.parent.bind('<Key-a>', self.toggle_auto_attendance)
            self.parent.bind('<Key-A>', self.toggle_auto_attendance)
            self.parent.bind('<Right>', lambda e: self.navigate_right())
            self.parent.bind('<Left>', lambda e: self.navigate_left())
            self.parent.bind('<Up>', lambda e: self.navigate_up())
            self.parent.bind('<Down>', lambda e: self.navigate_down())
            
            self.folder_tree.bind('<Key-a>', self.toggle_auto_attendance)
            self.folder_tree.bind('<Key-A>', self.toggle_auto_attendance)
            
            if hasattr(self, 'image_canvas'):
                self.image_canvas.bind('<Key-a>', self.toggle_auto_attendance)
                self.image_canvas.bind('<Key-A>', self.toggle_auto_attendance)
                self.image_canvas.bind('<Right>', lambda e: self.navigate_right())
                self.image_canvas.bind('<Left>', lambda e: self.navigate_left())


    def _unbind_keys(self):
        sequences = ('<Return>', '<Control-Return>', '<Key-b>', '<Key-B>', '<Key-m>', '<Key-M>', '<Key-n>', '<Key-N>', '<Key-a>', '<Key-A>')
        for seq in sequences:
            try:
                self.parent.unbind(seq)
            except Exception:
                pass

    def toggle_not_working(self, event=None):
        if not hasattr(self, 'navigator') or not self.navigator.current_subfolder:
            return 'break'
            
        subfolder_str = str(self.navigator.current_subfolder)
        not_working_folders = config.get('not_working_folders', [])
        
        if subfolder_str in not_working_folders:
            not_working_folders.remove(subfolder_str)
            is_not_working = False
        else:
            not_working_folders.append(subfolder_str)
            is_not_working = True
            
        config.set('not_working_folders', not_working_folders)
        
        # Update treeview tag
        for child in self.folder_tree.get_children(''):
            values = self.folder_tree.item(child, 'values')
            if values and values[0] == subfolder_str:
                tags = list(self.folder_tree.item(child, 'tags'))
                if is_not_working:
                    if 'not_working' not in tags:
                        tags.append('not_working')
                else:
                    if 'not_working' in tags:
                        tags.remove('not_working')
                self.folder_tree.item(child, tags=tuple(tags))
                break
                
        # Update theme layout
        self.update_not_working_ui_state(is_not_working)
        self.update_cut_count()
        return 'break'

    def update_not_working_ui_state(self, is_not_working):
        self.apply_layout_theme(is_not_working)

    def apply_layout_theme(self, is_black):
        """Toggle between black layout theme and default theme"""
        if not hasattr(self, 'style_defaults'):
            return
        bg = "black" if is_black else self.style_defaults['TFrame']['background']
        fg = "#888888" if is_black else self.style_defaults['TLabel']['foreground']
        
        # Configure ttk styles
        self.style.configure('TFrame', background=bg)
        self.style.configure('TLabel', background=bg, foreground=fg)
        self.style.configure('TLabelframe', background=bg, foreground=fg)
        self.style.configure('TLabelframe.Label', background=bg, foreground=fg)
        self.style.configure('TButton', background=bg, foreground=fg)
        
        # Configure Treeview style
        tree_bg = "black" if is_black else self.style_defaults['Treeview']['background']
        tree_fg = "#888888" if is_black else self.style_defaults['Treeview']['foreground']
        tree_fieldbg = "black" if is_black else self.style_defaults['Treeview']['fieldbackground']
        self.style.configure('Treeview', background=tree_bg, foreground=tree_fg, fieldbackground=tree_fieldbg)
        
        # Recursively update standard tk widgets inside the main frame
        self._update_tk_widgets_recursive(self.frame, is_black)

    def toggle_mark_force_red(self):
        if not self.navigator.current_subfolder:
            return
            
        subfolder_str = str(self.navigator.current_subfolder)
        marked_folders = config.get('marked_folders', [])
        
        if subfolder_str not in marked_folders:
            marked_folders.append(subfolder_str)
            config.set('marked_folders', marked_folders)
            
            # Find tree item and update tags
            for child in self.folder_tree.get_children(''):
                values = self.folder_tree.item(child, 'values')
                if values and values[0] == subfolder_str:
                    tags = list(self.folder_tree.item(child, 'tags'))
                    if 'marked' not in tags:
                        tags.append('marked')
                    if 'success' in tags:
                        tags.remove('success')
                    self.folder_tree.item(child, tags=tuple(tags))
                    break
            
            self.update_ui_marked_state(True)
            self.update_marked_count()
            self._refresh_batch_dropdown_only()

    def toggle_mark_force_normal(self):
        if not self.navigator.current_subfolder:
            return
            
        subfolder_str = str(self.navigator.current_subfolder)
        marked_folders = config.get('marked_folders', [])
        
        if subfolder_str in marked_folders:
            marked_folders.remove(subfolder_str)
            config.set('marked_folders', marked_folders)
            
            # Find tree item and update tags
            for child in self.folder_tree.get_children(''):
                values = self.folder_tree.item(child, 'values')
                if values and values[0] == subfolder_str:
                    tags = list(self.folder_tree.item(child, 'tags'))
                    if 'marked' in tags:
                        tags.remove('marked')
                    self.folder_tree.item(child, tags=tuple(tags))
                    break
            
            self.update_ui_marked_state(False)
            self.update_marked_count()
            self._refresh_batch_dropdown_only()

    def _update_tk_widgets_recursive(self, widget, is_black):
        bg = "black" if is_black else None
        fg = "#888888" if is_black else None
        w_class = widget.winfo_class()
        
        if not w_class.startswith('T') or w_class in ('Canvas', 'Listbox', 'Text', 'Entry'):
            try:
                if w_class == 'Canvas':
                    if widget == getattr(self, 'image_canvas', None):
                        if is_black:
                            widget.config(bg='black')
                        else:
                            is_marked = False
                            if hasattr(self, 'navigator') and self.navigator.current_subfolder:
                                is_marked = str(self.navigator.current_subfolder) in config.get('marked_folders', [])
                            widget.config(bg='#4a0000' if is_marked else 'gray')
                    else:
                        widget.config(bg='black' if is_black else '#222222')
                elif w_class in ('Label', 'Button', 'Frame', 'Labelframe'):
                    if is_black:
                        widget.config(bg='black')
                        if w_class in ('Label', 'Button'):
                            widget.config(fg='#888888')
                    else:
                        if w_class == 'Button':
                            if widget == getattr(self, 'toggle_btn', None):
                                is_on = self.show_marked_only_var.get()
                                widget.config(bg='#e53935' if is_on else 'gray', fg='white')
                            else:
                                widget.config(bg='SystemButtonFace', fg='SystemButtonText')
                        elif w_class == 'Label':
                            if widget == getattr(self, 'auto_status_lbl', None):
                                is_on = self.auto_status_var.get() == "ON"
                                widget.config(bg='SystemButtonFace', fg='green' if is_on else 'red')
                            elif widget == getattr(self, 'success_count_label', None):
                                widget.config(bg='SystemButtonFace', fg='green')
                            elif widget == getattr(self, 'status_display_label', None):
                                # Preserve current text color (green for success, red for fail)
                                widget.config(bg='SystemButtonFace')
                            elif widget in (getattr(self, 'preview_label', None), getattr(self, 'sr_label', None), getattr(self, 'marked_count_label', None)):
                                is_marked = False
                                if hasattr(self, 'navigator') and self.navigator.current_subfolder:
                                    is_marked = str(self.navigator.current_subfolder) in config.get('marked_folders', [])
                                widget.config(bg='SystemButtonFace', fg='red' if is_marked else 'SystemButtonText')
                            else:
                                widget.config(bg='SystemButtonFace', fg='SystemButtonText')
                        elif w_class in ('Frame', 'Labelframe'):
                            widget.config(bg='SystemButtonFace')
            except Exception:
                pass
                
        for child in widget.winfo_children():
            if isinstance(child, tk.Toplevel):
                continue
            self._update_tk_widgets_recursive(child, is_black)

    def block_tree_nav(self, event, direction):
        """Handle tree navigation to prevent default behavior"""
        import platform
        if platform.system() == 'Windows' and getattr(self, 'is_auto', False):
            return 'break'
            
        if direction == 'left':
            self.navigate_left(event)
        else:
            self.navigate_right(event)
        return 'break' # Stop event propagation

    def update_server_image(self):
        """Update the server with the full brightness-adjusted image (no zoom/crop)"""
        if hasattr(self, 'image_display') and self.image_display:
            # Send processed_image (brightness applied, full resolution) for clean mirror
            server.update_image(self.image_display.current_image)
            # Update PIP window image if active
            self.update_pip_image()

    def _save_current_subfolder_state(self, override=None):
        """Persist current brightness, zoom, and image index for the active subfolder"""
        subfolder_name = self.navigator.get_current_subfolder_name()
        if subfolder_name:
            config.set_subfolder_settings(
                subfolder_name,
                self.current_brightness,
                self.current_zoom,
                self.current_image_index,
                override
            )

    def _refresh_batch_dropdown_only(self):
        """Refresh the batch dropdown display names without triggering tree reload"""
        if not self.data_dir.exists():
            return
        marked_folders = config.get('marked_folders', [])
        display_folders = []
        for folder in self.data_dir.iterdir():
            if folder.is_dir():
                name = folder.name
                has_marked = False
                try:
                    for subfolder in folder.iterdir():
                        if subfolder.is_dir() and str(subfolder) in marked_folders:
                            has_marked = True
                            break
                except:
                    pass
                display_folders.append(f"{name} 🔴" if has_marked else name)
        folders = sorted(display_folders)
        current_val = self.batch_var.get()
        self.batch_combo['values'] = folders
        # Re-select the current batch by matching the base name
        base = current_val.replace(" 🔴", "").replace(" [M]", "").strip()
        match = next((f for f in folders if f.startswith(base)), None)
        if match:
            self.batch_var.set(match)

    # ── Auto Attendance Methods ──────────────────────────────────────────────
    def toggle_auto_attendance(self, event=None):
        if self.is_auto_running:
            self.stop_auto_attendance()
        else:
            self.start_auto_attendance()

    def start_auto_attendance(self):
        self.full_auto = True
        self.is_auto_running = True
        self.auto_status_var.set("ON")
        self.auto_status_lbl.config(fg="green")
        self._hud_show()
        # Create and display the PIP window
        if not hasattr(self, 'pip_window') or not self.pip_window:
            self.create_pip_window()
        self.update_pip_image()
        self.run_auto_step()

    def stop_auto_attendance(self):
        self.is_auto_running = False
        self.auto_status_var.set("OFF")
        self.auto_status_lbl.config(fg="red")
        if self.auto_job:
            self.parent.after_cancel(self.auto_job)
            self.auto_job = None
        self.auto_overlay.withdraw()
        self._hud_hide()
        # Withdraw the PIP window
        if hasattr(self, 'pip_window') and self.pip_window:
            try:
                self.pip_window.withdraw()
            except:
                pass

    def create_pip_window(self):
        """Create the borderless PIP window for auto attendance mode"""
        if not self.is_auto:
            return
        try:
            self.pip_window = tk.Toplevel(self.parent)
            self.pip_window.title("PIP Mode")
            self.pip_window.overrideredirect(True)
            self.pip_window.attributes("-topmost", True)
            
            # Container for image
            self.pip_label = tk.Label(self.pip_window, bg="black")
            self.pip_label.pack(fill=tk.BOTH, expand=True)
            
            # Default geometry
            sw = self.parent.winfo_screenwidth()
            sh = self.parent.winfo_screenheight()
            self.pip_window.geometry(f"300x200+{sw-320}+{sh-260}")
            self.pip_window.withdraw()
            
            # Bind drag events
            self.pip_label.bind("<ButtonPress-1>", self.start_pip_drag)
            self.pip_label.bind("<B1-Motion>", self.drag_pip)
        except Exception as e:
            print(f"[PIP] Create error: {e}")
            self.pip_window = None

    def start_pip_drag(self, event):
        self.pip_drag_x = event.x
        self.pip_drag_y = event.y

    def drag_pip(self, event):
        if not self.pip_window:
            return
        dx = event.x - self.pip_drag_x
        dy = event.y - self.pip_drag_y
        x = self.pip_window.winfo_x() + dx
        y = self.pip_window.winfo_y() + dy
        self.pip_window.geometry(f"+{x}+{y}")

    def update_pip_image(self):
        """Update the image in the PIP window, scaled to 60%"""
        if not hasattr(self, 'pip_window') or not self.pip_window or not self.is_auto_running:
            return
        try:
            img = self.image_display.current_image
            if not img:
                self.pip_label.config(image='')
                self._pip_photo = None
                return
                
            w, h = img.size
            pip_w = max(1, int(w * 0.6))
            pip_h = max(1, int(h * 0.6))
            
            # Resize image to 60%
            resized_img = img.resize((pip_w, pip_h), Image.Resampling.LANCZOS)
            self._pip_photo = ImageTk.PhotoImage(resized_img)
            self.pip_label.config(image=self._pip_photo)
            self.pip_label.image = self._pip_photo # Prevent garbage collection on widget level
            
            sw = self.parent.winfo_screenwidth()
            sh = self.parent.winfo_screenheight()
            
            # Set geometry relative to current position or bottom-right default
            x = self.pip_window.winfo_x()
            y = self.pip_window.winfo_y()
            if x <= 0 or y <= 0 or x > sw or y > sh:
                x = sw - pip_w - 20
                y = sh - pip_h - 80
                
            self.pip_window.geometry(f"{pip_w}x{pip_h}+{x}+{y}")
            self.pip_window.deiconify()
            self.pip_window.lift()
            
            # Force window update to redraw the updated brightness instantly
            try:
                self.pip_window.update_idletasks()
                self.pip_window.update()
            except:
                pass
        except Exception as e:
            print(f"[PIP] Update error: {e}")

    def sync_overlay(self):
        try:
            x = self.parent.winfo_rootx()
            y = self.parent.winfo_rooty()
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()
            self.auto_overlay.geometry(f"{w}x{h}+{x}+{y}")
        except:
            pass

    def run_auto_step(self):
        if not self.is_auto_running:
            return
            
        current_selection = self.folder_tree.selection()
        if not current_selection:
            self.stop_auto_attendance()
            return
            
        item = current_selection[0]
        values = self.folder_tree.item(item, "values")
        if values:
            subfolder_path = values[0]
            not_working_folders = config.get('not_working_folders', [])
            if subfolder_path in not_working_folders:
                # Skip this subfolder!
                old_selection = self.folder_tree.selection()
                self.navigator.navigate_down()
                new_selection = self.folder_tree.selection()
                if old_selection and new_selection and old_selection[0] == new_selection[0]:
                    self.stop_auto_attendance()
                    self.parent.after(100, lambda: messagebox.showinfo("Success", "All attendance have been marked successfully!"))
                    return
                self.parent.after(300, self.run_auto_step)
                return

        subfolder_name = self.folder_tree.item(item, "text")
        subfolder_path_str = ""
        values = self.folder_tree.item(item, "values")
        if values:
            subfolder_path_str = values[0]
            
        if subfolder_path_str:
            self.set_status_processing(subfolder_path_str)
        
        # Update Sr. No on overlay
        try:
            total = len(self.navigator.subfolders)
            values = self.folder_tree.item(item, "values")
            if values:
                from pathlib import Path
                sf_path = Path(values[0])
                current_num = self.navigator.subfolders.index(sf_path) + 1
                srno_text = f"Sr. No:  {current_num} / {total}"
            else:
                srno_text = ""
                current_num = 0
                total = 0
        except (ValueError, Exception):
            srno_text = ""
            current_num = 0
            total = 0

        # Update HUD
        self._hud_update(subfolder_name, current_num, total)
        
        if getattr(self, 'full_auto', False):
            self.overlay_status_lbl.config(text="FULL AUTO MODE", fg="#00E5FF")
        else:
            self.overlay_status_lbl.config(text="CURRENTLY TYPING", fg="#FFC107")
        self.overlay_srno_lbl.config(text=srno_text)
        self.overlay_id_lbl.config(text=subfolder_name)
        self.overlay_timer_lbl.config(text="...")
        self.overlay_progress_canvas.coords(self.overlay_progress_bar, 0, 0, 0, 20)
        self.sync_overlay()
        self.auto_overlay.deiconify()
        
        import threading
        threading.Thread(target=self.threaded_execute_macro_ocr, args=(subfolder_name, subfolder_path_str), daemon=True).start()

    def threaded_execute_macro(self, subfolder_name):
        try:
            # 1. Switch to previous window (Alt+Tab)
            keyboard.press(ALT_KEY)
            keyboard.press('tab')
            time.sleep(0.05)
            keyboard.release('tab')
            keyboard.release(ALT_KEY)
            
            # Wait for switch (User requested 0.5-0.6s)
            time.sleep(0.6)
            
            # 2. Type the number (auto-submitted)
            keyboard.write(subfolder_name, delay=0.05)
            time.sleep(0.2)
            
            # 4. Switch back to this window
            keyboard.press(ALT_KEY)
            keyboard.press('tab')
            time.sleep(0.05)
            keyboard.release('tab')
            keyboard.release(ALT_KEY)
            
            time.sleep(0.5)
            
            # 5. Wait slightly before showing countdown
            self.parent.after(0, self.start_countdown_for_next)
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Error", f"Macro failed: {e}"))
            self.parent.after(0, self.stop_auto_attendance)

    def safe_withdraw_overlay(self):
        if hasattr(self, 'auto_overlay'):
            self.auto_overlay.withdraw()

    def safe_deiconify_overlay(self):
        if hasattr(self, 'auto_overlay') and self.is_auto_running:
            self.auto_overlay.deiconify()

    def trigger_fullscreen_blink(self, color):
        """Flash the entire Windows screen with a semi-transparent colored overlay.
        2 long pulses over exactly 3 seconds. Non-blocking — must be called from main thread."""
        try:
            screen_w = self.parent.winfo_screenwidth()
            screen_h = self.parent.winfo_screenheight()

            blink_win = tk.Toplevel(self.parent)
            blink_win.overrideredirect(True)
            blink_win.geometry(f"{screen_w}x{screen_h}+0+0")
            blink_win.attributes("-topmost", True)
            blink_win.attributes("-alpha", 0.5)
            blink_win.attributes("-disabled", True)  # click-through, no focus steal
            blink_win.config(bg=color)
            blink_win.update_idletasks()

            # 2 pulses: ON 1s → OFF 0.5s → ON 1s → OFF 0.5s  (total = 3s)
            def _off():
                try: blink_win.attributes("-alpha", 0.0)
                except: pass
            def _on():
                try: blink_win.attributes("-alpha", 0.5)
                except: pass
            def _destroy():
                try: blink_win.destroy()
                except: pass

            blink_win.after(1000, _off)   # 1st pulse ends
            blink_win.after(1500, _on)    # 2nd pulse starts
            blink_win.after(2500, _off)   # 2nd pulse ends
            blink_win.after(3000, _destroy)
        except Exception as e:
            print(f"Blink overlay error: {e}")
        pass

    def grab_bas_screenshot(self):
        """Grabs a screenshot focused on the BAS window or popup to maximize OCR accuracy and speed"""
        try:
            import win32gui
            from PIL import ImageGrab
            
            # Get current foreground window
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) if hwnd else ""
            
            # If foreground window is target, crop to it
            is_target = (
                "biometric attendance system" in title.lower() or
                "device id" in title.lower() or
                title.startswith("PAID")
            )
            
            if not is_target:
                # Search visible windows for the BAS app window or popup
                target_hwnd = None
                def enum_handler(h, ctx):
                    nonlocal target_hwnd
                    if win32gui.IsWindowVisible(h):
                        t = win32gui.GetWindowText(h)
                        if "biometric attendance system" in t.lower() or "device id" in t.lower() or t.startswith("PAID"):
                            target_hwnd = h
                win32gui.EnumWindows(enum_handler, None)
                if target_hwnd:
                    hwnd = target_hwnd
                    is_target = True
            
            if is_target and hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                if rect[2] > rect[0] and rect[3] > rect[1]:
                    # Return cropped screenshot of the specific window
                    return ImageGrab.grab(bbox=rect)
        except Exception as e:
            print(f"Focused grab error: {e}")
        
        # Fallback to full screen
        from PIL import ImageGrab
        return ImageGrab.grab()

    def threaded_execute_macro_ocr(self, subfolder_name, subfolder_path=None):
        try:
            import pytesseract
            from PIL import ImageGrab
            
            path_str = str(subfolder_path) if subfolder_path else (str(self.navigator.current_subfolder) if self.navigator.current_subfolder else "")
            
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

            # When running from the installed EXE (PyInstaller bundle), Tesseract is bundled
            # inside _internal\Tesseract-OCR\ — NOT in C:\Program Files\Tesseract-OCR\
            import sys, os
            if hasattr(sys, '_MEIPASS'):
                _bundled_tess = os.path.join(sys._MEIPASS, 'Tesseract-OCR', 'tesseract.exe')
                if os.path.isfile(_bundled_tess):
                    pytesseract.pytesseract.tesseract_cmd = _bundled_tess
                    # Also tell Tesseract where to find language data files
                    os.environ['TESSDATA_PREFIX'] = os.path.join(sys._MEIPASS, 'Tesseract-OCR', 'tessdata')

            # Refined keywords to prevent false positives from static main window or file lists
            ERROR_KEYWORDS = [
                "error code", "error message", "error_:", "error:", 
                "enor", "egor", "biometric data", "try again", "fluctuation", 
                "invalid", "exist", "mismatch", "internal server error", "आंतरिक सर्वर त्रुटि",
                "deseriali", "deserialization", "deserialisation"
            ]

            # ──────────────────────────────────────────────────────────────────
            #  FULL AUTOMATIC MODE (no timer)
            # ──────────────────────────────────────────────────────────────────
            if getattr(self, 'full_auto', False):
                for attempt in range(1, 2):  # 1 attempt only
                    if not self.is_auto_running:
                        return

                    # 1. Switch to target window
                    keyboard.press(ALT_KEY)
                    keyboard.press('tab')
                    time.sleep(0.05)
                    keyboard.release('tab')
                    keyboard.release(ALT_KEY)
                    time.sleep(0.6)

                    # Always clear input field first to prevent double-typing or leftovers
                    keyboard.send('esc')
                    time.sleep(0.15)
                    keyboard.press('ctrl')
                    keyboard.send('a')
                    keyboard.release('ctrl')
                    time.sleep(0.1)
                    keyboard.send('backspace')
                    time.sleep(0.15)

                    # 2. Type the student ID
                    keyboard.write(subfolder_name, delay=0.05)
                    time.sleep(0.2)

                    # 2.5 Handle T&C automation if enabled
                    if config.get('pc_tnc_enabled', False):
                        pc_coords = config.get('pc_tnc_coords', {})
                        if pc_coords and "checkbox" in pc_coords:
                            # Wait for the T&C consent popup (1.2 seconds)
                            time.sleep(1.2)
                            # Click checkbox
                            import pyautogui
                            pyautogui.click(pc_coords['checkbox']['x'], pc_coords['checkbox']['y'])
                            time.sleep(0.5)
                            # Press enter to confirm yes
                            keyboard.send('enter')
                            time.sleep(0.3)

                    # 3.5 After 5.5 seconds, increase brightness by 1% to refresh RD service display
                    brightness_adjusted = False
                    type_done_time = time.time()

                    # 4. Poll INDEFINITELY until popup appears (success or error)
                    #    No time limit — we wait as long as it takes.
                    found_success = False
                    found_error = False

                    while self.is_auto_running:
                        # Increase brightness after 5.5 seconds if not done yet
                        if not brightness_adjusted and (time.time() - type_done_time > 5.5):
                            self.parent.after(0, self.increase_brightness)
                            brightness_adjusted = True

                        try:
                            # Grab focused window screenshot for maximum OCR speed/accuracy
                            screenshot = self.grab_bas_screenshot()
                            processed_img = screenshot.convert('L')
                            screenshot.close()
                            screenshot = None
                        except Exception as img_e:
                            print(f"Screenshot error: {img_e}")
                            time.sleep(0.4)
                            continue

                        try:
                            text = pytesseract.image_to_string(processed_img).lower()
                            processed_img.close()
                            processed_img = None
                            
                            is_pid_xml_error = (
                                ("pid" in text and "xml" in text) or
                                "deseriali" in text or
                                "deserialization" in text or
                                "deserialisation" in text
                            )
                            
                            if "attendance type" in text:
                                found_success = True
                                break
                            if is_pid_xml_error or any(kw in text for kw in ERROR_KEYWORDS):
                                found_error = True
                                break
                        except Exception as ocr_err:
                            try:
                                processed_img.close()
                            except:
                                pass
                            if "tesseract is not installed" in str(ocr_err).lower() or "not found" in str(ocr_err).lower():
                                self.parent.after(0, lambda: messagebox.showerror("Tesseract Missing", "Tesseract-OCR is not installed in C:\\Program Files\\Tesseract-OCR\\tesseract.exe. Please install it."))
                                self.parent.after(0, self.stop_auto_attendance)
                                return
                            print(f"OCR error: {ocr_err}")

                        # Short pause before next screenshot check
                        time.sleep(0.2)

                    if not self.is_auto_running:
                        if brightness_adjusted:
                            self.parent.after(0, self.decrease_brightness)
                        return

                    # Always restore brightness after success or failure
                    if brightness_adjusted:
                        self.parent.after(0, self.decrease_brightness)

                    # ── SUCCESS ──────────────────────────────────────────────
                    if found_success:
                        import datetime as _dt
                        _evt_time = _dt.datetime.now().strftime("%H:%M:%S")
                        # Determine if opening or closing
                        already_marked = path_str in config.get('success_folders', [])
                        clean_text = "".join(text.split())
                        is_opening = False
                        is_closing = False
                        
                        # Explicit keyword matching without spacing
                        if "attendancetype:closing" in clean_text or "type:closing" in clean_text or "typeclosing" in clean_text:
                            is_closing = True
                        elif "attendancetype:opening" in clean_text or "type:opening" in clean_text or "typeopening" in clean_text:
                            is_opening = True
                            
                        # If still not detected, check proximity (next 15 chars after label)
                        if not is_opening and not is_closing:
                            if "attendancetype" in clean_text:
                                idx = clean_text.find("attendancetype")
                                val_part = clean_text[idx + len("attendancetype"):idx + len("attendancetype") + 15]
                                if "closing" in val_part or "close" in val_part:
                                    is_closing = True
                                elif "opening" in val_part or "open" in val_part:
                                    is_opening = True
                                    
                        if not is_opening and not is_closing:
                            if "type" in clean_text:
                                idx = clean_text.find("type")
                                val_part = clean_text[idx + len("type"):idx + len("type") + 15]
                                if "closing" in val_part or "close" in val_part:
                                    is_closing = True
                                elif "opening" in val_part or "open" in val_part:
                                    is_opening = True
                                
                        if not is_opening and not is_closing:
                            has_close = "closing" in text or "close" in text
                            has_open = "opening" in text or "open" in text
                            if has_close and has_open:
                                is_closing = True
                            elif has_close:
                                is_closing = True
                            elif has_open:
                                is_opening = True
                            else:
                                if already_marked:
                                    is_closing = True
                                else:
                                    is_opening = True
                                
                        att_type = "opening" if is_opening else ("closing" if is_closing else None)
                        if is_opening:
                            self.parent.after(0, lambda p=path_str: self.mark_subfolder_success(p))
                        elif is_closing:
                            self.parent.after(0, lambda p=path_str: self.unmark_subfolder_success(p))

                        # Write to local daily log
                        try:
                            _batch_name = self.batch_var.get().replace(" 🔴", "").strip() if hasattr(self, 'batch_var') else ""
                            _batch_id_raw = _batch_name.split(" - ")[0].strip() if " - " in _batch_name else _batch_name
                            _in_t = self.lbl_batch_in.cget("text").replace("In Time: ", "").strip() if hasattr(self, 'lbl_batch_in') else ""
                            _out_t = self.lbl_batch_out.cget("text").replace("Out Time: ", "").strip() if hasattr(self, 'lbl_batch_out') else ""
                            _total = len(self.navigator.subfolders) if hasattr(self, 'navigator') and self.navigator.subfolders else 0
                            _username = config.get("license_user") or (self.lm.username if hasattr(self.lm, 'username') and self.lm.username else "default")
                            attendance_report.log_attendance_event(
                                attendance_id=subfolder_name,
                                batch_id=_batch_id_raw,
                                batch_name=_batch_name,
                                event_type=att_type or "opening",
                                timestamp=_evt_time,
                                in_time=_in_t,
                                out_time=_out_t,
                                total_students=_total,
                                username=_username
                            )
                        except Exception as _log_err:
                            print(f"[Log] Write error: {_log_err}")

                        # Update live status display
                        self.parent.after(0, lambda p=path_str, at=att_type: self.update_attendance_status(True, folder_path=p, attendance_type=at))

                        # Wait 0.6 seconds on target window for attendance to process & allow validation
                        time.sleep(0.6)
                        # Press Enter to close the success popup
                        keyboard.send('enter')
                        time.sleep(0.3)
                        # Switch back to IR Attendance directly (don't rely on alt+tab)
                        self.parent.after(0, self.window_manager.bring_to_front)
                        time.sleep(0.4)

                        # Always remove M mark on success (opening → green, closing → default).
                        # This applies whether "Show Marked Only" toggle is ON or OFF.
                        self.parent.after(0, self.toggle_mark_force_normal)
                        time.sleep(0.1)

                        # Navigate to next student immediately (no countdown)
                        self.parent.after(0, self.navigate_and_continue_full_auto)
                        return

                    # ── ERROR ─────────────────────────────────────────────────
                    # Determine error message
                    err_msg = "Failed"
                    if is_pid_xml_error:
                        err_msg = "PID XML deserialization error"
                    else:
                        for kw in ERROR_KEYWORDS:
                            if kw in text:
                                if "mismatch" in kw:
                                    err_msg = "Mismatch"
                                elif "try again" in kw:
                                    err_msg = "Try Again"
                                elif "invalid" in kw:
                                    err_msg = "Invalid"
                                elif "exist" in kw:
                                    err_msg = "Already Exists"
                                elif "internal server error" in kw or "आंतरिक" in kw:
                                    err_msg = "Internal Server Error"
                                else:
                                    err_msg = kw.title()
                                break
                    was_already_success = path_str in config.get('success_folders', [])
                    if was_already_success:
                        times = getattr(self, '_attendance_times', {}).get(path_str, {})
                        op_time = times.get('opening', '')
                        msg = f"Opening : {op_time}" if op_time else "Opening : —"
                        self.parent.after(0, lambda txt=msg, p=path_str: self.update_attendance_status(False, message=txt, folder_path=p))
                    else:
                        self.parent.after(0, lambda m=err_msg, p=path_str: self.update_attendance_status(False, m, folder_path=p))

                    # ── Dismiss the error popup ──────────────────────────────────
                    if is_pid_xml_error:
                        self._dismiss_pid_xml_error()
                    elif err_msg == "Internal Server Error":
                        # Try Esc first to close the inner error dialog
                        keyboard.send('esc')
                        time.sleep(0.4)
                        keyboard.send('enter')
                        time.sleep(0.4)
                        # One more Esc in case a secondary dialog appeared
                        keyboard.send('esc')
                        time.sleep(0.5)
                    else:
                        keyboard.send('enter')
                        time.sleep(0.3)
                        keyboard.send('esc')
                        time.sleep(0.3)
                    # Switch back to IR Attendance directly using Win32
                    self.parent.after(0, self.window_manager.bring_to_front)
                    time.sleep(0.4)

                # Attempt exhausted — mark folder red and move to next
                was_already_success = path_str in config.get('success_folders', [])
                if not found_success and not found_error:
                    if was_already_success:
                        times = getattr(self, '_attendance_times', {}).get(path_str, {})
                        op_time = times.get('opening', '')
                        msg = f"Opening : {op_time}" if op_time else "Opening : —"
                        self.parent.after(0, lambda txt=msg, p=path_str: self.update_attendance_status(False, message=txt, folder_path=p))
                    else:
                        self.parent.after(0, lambda p=path_str: self.update_attendance_status(False, "Timeout / Device Not Responding", folder_path=p))
                self.parent.after(0, self.toggle_mark_force_red)
                # PID XML needs the longest settle — the BAS RD service must fully
                # recover before the next OCR cycle, otherwise the lingering exception
                # dialog text immediately triggers another found_error on the next student.
                # ISE needs 1.2s. PID XML needs 2.5s for the same reason but worse.
                if is_pid_xml_error:
                    _settle = 2.5
                elif err_msg == "Internal Server Error":
                    _settle = 1.2
                else:
                    _settle = 0.1
                time.sleep(_settle)
                self.parent.after(200, self.navigate_and_continue_full_auto)
                return

            # ──────────────────────────────────────────────────────────────────
            #  NORMAL MODE (timer is set) — original OCR + countdown flow
            # ──────────────────────────────────────────────────────────────────
            else:
                success = False
                found_error = False
                for attempt in range(1, 4):
                    if not self.is_auto_running:
                        return
                        
                    # 1. Switch to previous window (Alt+Tab)
                    keyboard.press(ALT_KEY)
                    keyboard.press('tab')
                    time.sleep(0.05)
                    keyboard.release('tab')
                    keyboard.release(ALT_KEY)
                    
                    # Wait for switch
                    time.sleep(0.6)
                    
                    # Always clear input field first to prevent double-typing or leftovers
                    keyboard.send('esc')
                    time.sleep(0.15)
                    keyboard.press('ctrl')
                    keyboard.send('a')
                    keyboard.release('ctrl')
                    time.sleep(0.1)
                    keyboard.send('backspace')
                    time.sleep(0.15)
                    
                    # 2. Type the student ID
                    keyboard.write(subfolder_name, delay=0.05)
                    time.sleep(0.2)

                    # 2.5 Handle T&C automation if enabled
                    if config.get('pc_tnc_enabled', False):
                        pc_coords = config.get('pc_tnc_coords', {})
                        if pc_coords and "checkbox" in pc_coords:
                            # Wait for the T&C consent popup (1.2 seconds)
                            time.sleep(1.2)
                            # Click checkbox
                            import pyautogui
                            pyautogui.click(pc_coords['checkbox']['x'], pc_coords['checkbox']['y'])
                            time.sleep(0.5)
                            # Press enter to confirm yes
                            keyboard.send('enter')
                            time.sleep(0.3)
                    
                    # 3. Poll for success (checks for "Attendance type") or error
                    start_poll = time.time()
                    # Poll for up to 6.0 seconds to give the hardware plenty of time to process
                    while time.time() - start_poll < 6.0:
                        if not self.is_auto_running:
                            return
                            
                        try:
                            # Grab focused window screenshot for maximum OCR speed/accuracy
                            screenshot = self.grab_bas_screenshot()
                            processed_img = screenshot.convert('L')
                            screenshot.close()
                        except Exception as img_e:
                            print(f"Screenshot error: {img_e}")
                            time.sleep(0.4)
                            continue
                        
                        try:
                            text = pytesseract.image_to_string(processed_img).lower()
                            processed_img.close()
                            
                            is_pid_xml_error = (
                                ("pid" in text and "xml" in text) or
                                "deseriali" in text or
                                "deserialization" in text or
                                "deserialisation" in text
                            )
                            
                            if "attendance type" in text:
                                success = True
                                break
                            if is_pid_xml_error or any(kw in text for kw in ERROR_KEYWORDS):
                                found_error = True
                                break
                        except Exception as ocr_err:
                            print(f"OCR error: {ocr_err}")
                            
                        time.sleep(0.4)
                    
                    if success or found_error:
                        break
                        
                if success:
                    import datetime as _dt2
                    _evt_time2 = _dt2.datetime.now().strftime("%H:%M:%S")
                    already_marked = path_str in config.get('success_folders', [])
                    clean_text2 = "".join(text.split())
                    is_opening = False
                    is_closing = False
                    
                    # Explicit keyword matching without spacing
                    if "attendancetype:closing" in clean_text2 or "type:closing" in clean_text2 or "typeclosing" in clean_text2:
                        is_closing = True
                    elif "attendancetype:opening" in clean_text2 or "type:opening" in clean_text2 or "typeopening" in clean_text2:
                        is_opening = True
                        
                    # If still not detected, check proximity (next 15 chars after label)
                    if not is_opening and not is_closing:
                        if "attendancetype" in clean_text2:
                            idx = clean_text2.find("attendancetype")
                            val_part = clean_text2[idx + len("attendancetype"):idx + len("attendancetype") + 15]
                            if "closing" in val_part or "close" in val_part:
                                is_closing = True
                            elif "opening" in val_part or "open" in val_part:
                                is_opening = True
                                
                    if not is_opening and not is_closing:
                        if "type" in clean_text2:
                            idx = clean_text2.find("type")
                            val_part = clean_text2[idx + len("type"):idx + len("type") + 15]
                            if "closing" in val_part or "close" in val_part:
                                is_closing = True
                            elif "opening" in val_part or "open" in val_part:
                                is_opening = True
                            
                    if not is_opening and not is_closing:
                        has_close = "closing" in text or "close" in text
                        has_open = "opening" in text or "open" in text
                        if has_close and has_open:
                            is_closing = True
                        elif has_close:
                            is_closing = True
                        elif has_open:
                            is_opening = True
                        else:
                            if already_marked:
                                is_closing = True
                            else:
                                is_opening = True
                                
                    att_type2 = "opening" if is_opening else ("closing" if is_closing else None)
                    if is_opening:
                        self.parent.after(0, lambda p=path_str: self.mark_subfolder_success(p))
                    elif is_closing:
                        self.parent.after(0, lambda p=path_str: self.unmark_subfolder_success(p))

                    # Write to local daily log
                    try:
                        _batch_name2 = self.batch_var.get().replace(" 🔴", "").strip() if hasattr(self, 'batch_var') else ""
                        _batch_id_raw2 = _batch_name2.split(" - ")[0].strip() if " - " in _batch_name2 else _batch_name2
                        _in_t2 = self.lbl_batch_in.cget("text").replace("In Time: ", "").strip() if hasattr(self, 'lbl_batch_in') else ""
                        _out_t2 = self.lbl_batch_out.cget("text").replace("Out Time: ", "").strip() if hasattr(self, 'lbl_batch_out') else ""
                        _total2 = len(self.navigator.subfolders) if hasattr(self, 'navigator') and self.navigator.subfolders else 0
                        _username2 = config.get("license_user") or (self.lm.username if hasattr(self.lm, 'username') and self.lm.username else "default")
                        attendance_report.log_attendance_event(
                            attendance_id=subfolder_name,
                            batch_id=_batch_id_raw2,
                            batch_name=_batch_name2,
                            event_type=att_type2 or "opening",
                            timestamp=_evt_time2,
                            in_time=_in_t2,
                            out_time=_out_t2,
                            total_students=_total2,
                            username=_username2
                        )
                    except Exception as _log_err2:
                        print(f"[Log] Write error: {_log_err2}")

                    self.parent.after(0, lambda p=path_str, at=att_type2: self.update_attendance_status(True, folder_path=p, attendance_type=at))
                    # Always remove M mark on success (opening → green, closing → default).
                    # This applies whether "Show Marked Only" toggle is ON or OFF.
                    self.parent.after(0, self.toggle_mark_force_normal)
                    # If it was an error, close the popup first
                    err_msg = "Failed"
                    was_already_success = path_str in config.get('success_folders', [])
                    if found_error:
                        if is_pid_xml_error:
                            err_msg = "PID XML deserialization error"
                        else:
                            for kw in ERROR_KEYWORDS:
                                if kw in text:
                                    if "mismatch" in kw:
                                        err_msg = "Mismatch"
                                    elif "try again" in kw:
                                        err_msg = "Try Again"
                                    elif "invalid" in kw:
                                        err_msg = "Invalid"
                                    elif "exist" in kw:
                                        err_msg = "Already Exists"
                                    elif "internal server error" in kw or "आंतरिक" in kw:
                                        err_msg = "Internal Server Error"
                                    else:
                                        err_msg = kw.title()
                                    break
                        
                        if was_already_success:
                            times = getattr(self, '_attendance_times', {}).get(path_str, {})
                            op_time = times.get('opening', '')
                            msg = f"Opening : {op_time}" if op_time else "Opening : —"
                            self.parent.after(0, lambda txt=msg, p=path_str: self.update_attendance_status(False, message=txt, folder_path=p))
                        else:
                            self.parent.after(0, lambda m=err_msg, p=path_str: self.update_attendance_status(False, m, folder_path=p))
                        
                        # Aggressive dismiss for PID XML error or standard dismiss
                        if is_pid_xml_error:
                            self._dismiss_pid_xml_error()
                        else:
                            keyboard.send('enter')
                            time.sleep(0.3)
                            keyboard.send('esc')
                            time.sleep(0.3)
                    else:
                        if was_already_success:
                            times = getattr(self, '_attendance_times', {}).get(path_str, {})
                            op_time = times.get('opening', '')
                            msg = f"Opening : {op_time}" if op_time else "Opening : —"
                            self.parent.after(0, lambda txt=msg, p=path_str: self.update_attendance_status(False, message=txt, folder_path=p))
                        else:
                            self.parent.after(0, lambda p=path_str: self.update_attendance_status(False, "Timeout / Device Not Responding", folder_path=p))

                    # Force a red mark (failed)
                    self.parent.after(0, self.toggle_mark_force_red)
                    
                # Switch back to our window
                keyboard.press(ALT_KEY)
                keyboard.press('tab')
                time.sleep(0.05)
                keyboard.release('tab')
                keyboard.release(ALT_KEY)
                
                time.sleep(0.2)  # Fast transition
                
                # Continue with normal countdown
                self.parent.after(0, self.start_countdown_for_next)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Error", f"Macro failed: {e}"))
            self.parent.after(0, self.stop_auto_attendance)

    def _dismiss_pid_xml_error(self):
        """Dismiss the PID XML error dialog by pressing enter and alt-tabbing back to IR Attendance"""
        import time
        import keyboard
        import platform
        print("[Macro] Dismissing PID XML error dialog (pressing enter)...")
        keyboard.send('enter')
        time.sleep(0.3)
        
        # Press Alt+Tab to switch back to IR Attendance
        keyboard.press(ALT_KEY)
        keyboard.press('tab')
        time.sleep(0.05)
        keyboard.release('tab')
        keyboard.release(ALT_KEY)
        time.sleep(0.4)
        
        # Ensure our window is properly focused using Win32
        self.parent.after(0, self.window_manager.bring_to_front)
        time.sleep(0.2)

    def navigate_and_continue_full_auto(self):
        """Full Auto Mode: immediately navigate to next subfolder and trigger next step."""
        if not self.is_auto_running:
            return

        # Force our window to front using Win32 — reliable across all PCs/resolutions
        self.window_manager.bring_to_front()
        self.parent.focus_force()
        self.parent.update()  # Process pending events so focus takes effect
        self.folder_tree.focus_set()

        # If tree has no selection, the window may not have focus yet — retry after short delay
        selection = self.folder_tree.selection()
        if not selection:
            # Retry once after 300ms to let window finish focusing
            self.parent.after(300, self.navigate_and_continue_full_auto)
            return

        self.folder_tree.focus(selection[0])

        old_selection = self.folder_tree.selection()
        self.navigator.navigate_down()
        new_selection = self.folder_tree.selection()

        if old_selection and new_selection and old_selection[0] == new_selection[0]:
            self.stop_auto_attendance()
            self.parent.after(100, lambda: messagebox.showinfo("Success", "All attendance have been marked successfully!"))
            return

        # Immediately trigger next step — no countdown
        self.parent.after(400, self.run_auto_step)

    def start_countdown_for_next(self):
        if not self.is_auto_running:
            return
            
        self.window_manager.bring_to_front()
        self.parent.focus_force()
        self.folder_tree.focus_set()
        selection = self.folder_tree.selection()
        if selection:
            self.folder_tree.focus(selection[0])
            
        current_selection = self.folder_tree.selection()
        if current_selection:
            item = current_selection[0]
            subfolder_name = self.folder_tree.item(item, "text")
            
            self.overlay_status_lbl.config(text="WAITING / NEXT", fg="#888888")
            self.overlay_id_lbl.config(text=subfolder_name)
            self.sync_overlay()
            self.auto_overlay.deiconify()
            
            try:
                delay = int(float(self.timer_var.get())) if hasattr(self, 'timer_var') else 5
            except:
                delay = 5
                
            self.countdown_val = float(delay)
            self.countdown_start = float(delay)
            self.last_update_time = time.time()
            self._brought_front_this_step = False
            self.update_countdown()

    def update_countdown(self):
        if not self.is_auto_running:
            return
            
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now
        self.countdown_val -= dt
        
        display_sec = max(0, int(self.countdown_val) + 1)
        self.overlay_timer_lbl.config(text=str(display_sec))
        
        # update progress bar
        canvas_width = self.overlay_progress_canvas.winfo_width()
        if canvas_width > 1:
            ratio = max(0, self.countdown_val / self.countdown_start) if self.countdown_start > 0 else 0
            bar_width = int(canvas_width * ratio)
            self.overlay_progress_canvas.coords(self.overlay_progress_bar, 0, 0, bar_width, 20)
        
        if self.countdown_val <= 0:
            self.overlay_timer_lbl.config(text="0")
            self.overlay_progress_canvas.coords(self.overlay_progress_bar, 0, 0, 0, 20)
            
            old_selection = self.folder_tree.selection()
            self.navigator.navigate_down()
            new_selection = self.folder_tree.selection()
            
            if old_selection and new_selection and old_selection[0] == new_selection[0]:
                self.stop_auto_attendance()
                self.parent.after(100, lambda: messagebox.showinfo("Success", "All attendance have been marked successfully!"))
                return
                
            # Wait briefly after navigation for the image to load
            self.parent.after(300, self.run_auto_step)
        else:
            if self.countdown_val <= 1.0 and not getattr(self, '_brought_front_this_step', False):
                try:
                    pyautogui.press('enter')
                    time.sleep(0.05)
                except:
                    pass
                self.window_manager.bring_to_front()
                self.parent.focus_force()
                self.countdown_val = 0.2
                self._brought_front_this_step = True
            
            # Smooth update (~30fps)
            self.auto_job = self.parent.after(33, self.update_countdown)

    # ── Floating HUD Bar (Voice Access style) ────────────────────────────────
    def _hud_bar_create(self):
        """Create the slim always-on-top HUD bar shown during auto attendance."""
        if not self.is_auto:
            return
        try:
            sw = self.parent.winfo_screenwidth()
            self.hud_bar = tk.Toplevel(self.parent)
            self.hud_bar.overrideredirect(True)
            self.hud_bar.attributes("-topmost", True)
            self.hud_bar.geometry(f"{sw}x38+0+0")
            self.hud_bar.configure(bg="#1a1a2e")
            self.hud_bar.withdraw()  # hidden until auto starts

            # Make click-through on Windows so it doesn't steal focus
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.hud_bar.winfo_id())
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            except Exception:
                pass

            # ── Left section ─────────────────────────────────────
            left_frame = tk.Frame(self.hud_bar, bg="#1a1a2e")
            left_frame.pack(side=tk.LEFT, padx=(8, 0), pady=4)

            # Status indicator dot (canvas circle)
            self._hud_dot_canvas = tk.Canvas(left_frame, width=18, height=18,
                                             bg="#1a1a2e", highlightthickness=0)
            self._hud_dot_canvas.pack(side=tk.LEFT, padx=(0, 6))
            self._hud_dot = self._hud_dot_canvas.create_oval(2, 2, 16, 16, fill="#e53935", outline="")

            # Batch ID label on left of HUD
            self._hud_batch_lbl = tk.Label(left_frame, text="Batch: ---", font=("Arial", 11, "bold"),
                                           fg="#aaaaaa", bg="#1a1a2e")
            self._hud_batch_lbl.pack(side=tk.LEFT, padx=(5, 10))

            # ── Right section ────────────────────────────────────
            right_frame = tk.Frame(self.hud_bar, bg="#1a1a2e")
            right_frame.pack(side=tk.RIGHT, padx=(0, 14), pady=4)

            self._hud_stats_lbl = tk.Label(right_frame, text="M: 0  |  N: 0  |  ✓: 0  |  Total: 0  |  #0",
                                            font=("Arial", 10), fg="#aaaaaa", bg="#1a1a2e")
            self._hud_stats_lbl.pack(side=tk.RIGHT)

            # ── Center section ───────────────────────────────────
            center_frame = tk.Frame(self.hud_bar, bg="#1a1a2e")
            center_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

            # Attendance ID label centered with bigger text
            self._hud_id_lbl = tk.Label(center_frame, text="—", font=("Arial", 18, "bold"),
                                         fg="#00E5FF", bg="#1a1a2e", anchor=tk.CENTER)
            self._hud_id_lbl.pack(fill=tk.X, expand=True)

        except Exception as e:
            print(f"[HUD] Create error: {e}")
            self.hud_bar = None

    def _hud_show(self):
        """Show the HUD bar and set indicator to green."""
        if not self.hud_bar:
            return
        try:
            sw = self.parent.winfo_screenwidth()
            self.hud_bar.geometry(f"{sw}x38+0+0")
            self._hud_dot_canvas.itemconfig(self._hud_dot, fill="#43a047")
            self.hud_bar.deiconify()
            self.hud_bar.lift()
        except Exception as e:
            print(f"[HUD] Show error: {e}")

    def _hud_hide(self):
        """Hide the HUD bar."""
        if not self.hud_bar:
            return
        try:
            self.hud_bar.withdraw()
        except Exception:
            pass

    def _hud_update(self, attendance_id=None, current_num=0, total=0):
        """Refresh HUD labels with current attendance ID and counters."""
        if not self.hud_bar or not self.is_auto_running:
            return
        try:
            if attendance_id:
                self._hud_id_lbl.config(text=str(attendance_id))

            # Read counters from labels
            try:
                m_count = self.marked_count_label.cget("text")
            except Exception:
                m_count = "0"
            try:
                n_count = self.cut_count_label.cget("text")
            except Exception:
                n_count = "0"
            try:
                s_count = self.success_count_label.cget("text")
            except Exception:
                s_count = "0"

            sr_text = f"#{current_num}" if current_num else "#—"
            stats = f"M: {m_count}  |  N: {n_count}  |  ✓: {s_count}  |  Total: {total}  |  {sr_text}"
            self._hud_stats_lbl.config(text=stats)
        except Exception as e:
            print(f"[HUD] Update error: {e}")

    def calibrate_pc_tnc(self):
        # 1. We check if there is a student ID selected
        current_selection = self.folder_tree.selection()
        if not current_selection:
            messagebox.showwarning("Warning", "Please select a student folder/ID first so we can type it for calibration.")
            return
        
        student_id = self.folder_tree.item(current_selection[0], 'text')
        
        # 2. Inform the user and start countdown/preparation
        ans = messagebox.askokcancel("Calibrate PC T&C", 
            f"We will now:\n1. Switch to the BAS software window (Alt+Tab)\n2. Type the ID: {student_id}\n3. Show the calibration screen after the popup appears.\n\nMake sure the BAS software input field is focused, then click OK to start.")
        if not ans:
            return
            
        # Run the typing and calibration launch in a background thread so we don't block Tkinter UI
        import threading
        threading.Thread(target=self._run_pc_tnc_calibration_flow, args=(student_id,), daemon=True).start()

    def _run_pc_tnc_calibration_flow(self, student_id):
        try:
            # 1. Switch to previous window (Alt+Tab)
            keyboard.press(ALT_KEY)
            keyboard.press('tab')
            time.sleep(0.05)
            keyboard.release('tab')
            keyboard.release(ALT_KEY)
            
            # Wait for switch
            time.sleep(0.8)
            
            # 2. Type the student ID
            keyboard.write(student_id, delay=0.05)
            # Wait for the Aadhaar Consent popup to appear (1.5 seconds)
            time.sleep(1.5)
            
            # 3. Open the calibration window on the main thread
            self.parent.after(0, self._open_pc_tnc_calibration_window)
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Error", f"Calibration flow failed: {e}"))

    def _open_pc_tnc_calibration_window(self):
        PcTncCalibrationWindow(self.parent, on_close_cb=self._on_pc_tnc_calibrated)
        
    def _on_pc_tnc_calibrated(self):
        # Restore focus back to our main window
        self.window_manager.bring_to_front()
        self.parent.focus_force()
        messagebox.showinfo("Success", "PC T&C calibration saved successfully!")


class PcTncCalibrationWindow(tk.Toplevel):
    """Full-screen transparent window to click directly on the Windows monitor for PC T&C calibration."""
    def __init__(self, parent, on_close_cb):
        super().__init__(parent)
        self.on_close_cb = on_close_cb
        self.coords = config.get("pc_tnc_coords", {})
        if not isinstance(self.coords, dict):
            self.coords = {}
        
        self.steps = ["checkbox"]
        self.step_descriptions = {
            "checkbox": "Click exactly on the T&C Checkbox"
        }
        self.current_step_idx = 0
        
        # Make fullscreen and semi-transparent
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.5)
        self.attributes('-topmost', True)
        self.configure(cursor='crosshair', bg='black')
 
        self.lbl = tk.Label(self, text=self.step_descriptions[self.steps[0]], 
                            font=('Arial', 24, 'bold'), fg='red', bg='black')
        self.lbl.pack(pady=50)
        
        tk.Label(self, text="Press ESC to cancel calibration", font=('Arial', 14), fg='white', bg='black').pack()
 
        self.bind("<Button-1>", self.on_click)
        self.bind("<Escape>", lambda e: self.destroy())
 
    def on_click(self, event):
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        step_key = self.steps[self.current_step_idx]
        
        self.coords[step_key] = {"x": x, "y": y}
        
        # Draw visual feedback indicator on the overlay
        canvas = tk.Canvas(self, width=40, height=40, bg='black', highlightthickness=0)
        canvas.place(x=x-20, y=y-20)
        canvas.create_oval(10, 10, 30, 30, outline='lime', width=3)
        canvas.create_text(20, 20, text=str(self.current_step_idx + 1), fill='lime', font=('Arial', 10, 'bold'))
        self.update()
        
        # Programmatically click this on the real window underneath
        self.withdraw()
        self.update()
        time.sleep(0.1)
        
        import pyautogui
        pyautogui.click(x, y)
        
        # Wait slightly differently depending on the action
        if step_key == "confirm_btn":
            time.sleep(1.2)
        else:
            time.sleep(0.4)
            
        self.deiconify()
        self.update()
        
        # Move to next step
        self.current_step_idx += 1
        if self.current_step_idx < len(self.steps):
            self.lbl.config(text=self.step_descriptions[self.steps[self.current_step_idx]])
        else:
            self.lbl.config(text="Calibration complete! Saving...", fg='green')
            config.set("pc_tnc_coords", self.coords)
            self.after(500, self._finish)

    def _finish(self):
        if self.on_close_cb:
            self.on_close_cb()
        self.destroy()

"""
Mobile Attendance Mode — same as Mark Attendance but sends the
Attendance ID to the mobile phone numpad instead of Alt+Tab macro.

Keyboard:
  ↑ / ↓       — prev / next subfolder
  ← / →       — prev / next image in subfolder
  Enter        — send current ID to mobile phone (taps digits on numpad)
  Ctrl+Enter   — legacy Alt+Tab macro fallback
  b            — prompt brightness
  m            — toggle mark
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import threading
import time
import io
import queue

import keyboard
import server
import adb_utils

from PIL import Image, ImageTk, ImageEnhance
from config import config
from folder_navigator import FolderNavigator
from image_controls import ImageDisplay
from footer import Footer
from encryption_utils import EncryptionUtils


class MobileAttendanceMode:
    """Mobile Attendance Mode — sends attendance ID to phone numpad."""

    # ── Construction ────────────────────────────────────────────────────────────

    def __init__(self, parent, on_back_callback, window_manager, license_manager):
        self.parent           = parent
        self.on_back_callback = on_back_callback
        self.window_manager   = window_manager
        self.lm               = license_manager

        self.frame    = ttk.Frame(parent)
        self.data_dir = Path("C:/IR Attendance")

        # Image state
        self.current_images      = []
        self.current_image_index = -1
        self.current_brightness  = 100
        self.current_zoom        = 100
        self._photo              = None        # keep PhotoImage alive
        self._current_pil_img    = None        # brightness-adjusted PIL image

        # Mobile status state
        self._mobile_status    = "Idle"
        self._last_acked_id    = "—"
        self._pending_id       = "—"
        self._mobile_ui_queue  = queue.Queue()

        # ADB phone IP (user enters once)
        self._phone_ip = config.get('mobile_phone_ip', '')

        # Server (shared singleton)
        self.server_ip = server.start_server()

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

        self.create_ui()
        self._bind_keys()
        self._poll_mobile_ui_queue()

    # ── UI ───────────────────────────────────────────────────────────────────────

    def create_ui(self):
        c = ttk.Frame(self.frame)
        c.pack(fill=tk.BOTH, expand=True)
        self.content_container = c
        Footer(self.frame).pack(side=tk.BOTTOM, fill=tk.X)

        # ── Header ──────────────────────────────────────────────────────────────
        hdr = ttk.Frame(c)
        hdr.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(hdr, text="📱 Mobile Attendance",
                  font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        ips = " / ".join(self.server_ip) if isinstance(self.server_ip, list) else self.server_ip
        ttk.Label(hdr, text=f"Mirror IPs: {ips}",
                  font=('Arial', 10), foreground='blue').pack(side=tk.LEFT, padx=20)

        ttk.Button(hdr, text="← Back to Menu",
                   command=self._safe_back).pack(side=tk.RIGHT)

        bsf = ttk.Frame(hdr)
        bsf.pack(side=tk.RIGHT, padx=20)
        ttk.Label(bsf, text="Select Batch:").pack(side=tk.LEFT, padx=5)
        self.batch_var   = tk.StringVar()
        self.batch_combo = ttk.Combobox(bsf, textvariable=self.batch_var,
                                        width=20, state='readonly')
        self.batch_combo.pack(side=tk.LEFT, padx=5)
        self.batch_combo.bind('<<ComboboxSelected>>',
                              lambda e: self.load_selected_batch())
        ttk.Button(bsf, text="↺", width=3,
                   command=self.refresh_batch_list).pack(side=tk.LEFT)

        # ── Batch info strip ────────────────────────────────────────────────────
        bi  = ttk.Frame(c, padding=(10, 0))
        bi.pack(fill=tk.X)
        inn = ttk.Frame(bi, borderwidth=1, relief="solid", padding=5)
        inn.pack(fill=tk.X)
        self.lbl_batch_id  = ttk.Label(inn, text="Batch ID: ---",
                                       font=('Arial', 12, 'bold'))
        self.lbl_batch_id.pack(side=tk.LEFT, padx=10)
        ttk.Label(inn, text="|", font=('Arial', 12)).pack(side=tk.LEFT)
        self.lbl_batch_in  = ttk.Label(inn, text="In Time: --:--",
                                       font=('Arial', 11))
        self.lbl_batch_in.pack(side=tk.LEFT, padx=10)
        ttk.Label(inn, text="To", font=('Arial', 11)).pack(side=tk.LEFT)
        self.lbl_batch_out = ttk.Label(inn, text="Out Time: --:--",
                                       font=('Arial', 11))
        self.lbl_batch_out.pack(side=tk.LEFT, padx=10)

        # ── Instructions ────────────────────────────────────────────────────────
        inst = ttk.Frame(c)
        inst.pack(fill=tk.X, padx=10, pady=3)
        ttk.Label(inst,
                  text="Navigation: ↓ Next | ↑ Prev | → Next Img | ← Prev Img  |  "
                       "Enter: Send to Mobile  |  Ctrl+Enter: Legacy Alt+Tab  |  "
                       "b: Brightness  |  m: Mark",
                  font=('Arial', 9)).pack()

        # ── Info row (Sr / Attendance ID / Marked) ──────────────────────────────
        ir = ttk.Frame(c)
        ir.pack(fill=tk.X, padx=10)
        for lbl_text, attr in [("Sr No", "sr_label"),
                                ("Attendance ID", "att_id_label"),
                                ("Marked", "marked_count_label")]:
            frm = ttk.LabelFrame(ir, text=lbl_text)
            frm.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            lbl = ttk.Label(frm, text="---", font=('Arial', 12, 'bold'),
                            anchor=tk.CENTER)
            lbl.pack(fill=tk.BOTH, expand=True, pady=6)
            setattr(self, attr, lbl)

        # ── Main three-column area ───────────────────────────────────────────────
        main = ttk.Frame(c)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # LEFT: folder tree ──────────────────────────────────────────────────────
        lf = ttk.LabelFrame(main, text="Folders", width=200)
        lf.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        lf.pack_propagate(False)
        
        # Filter Toggle
        filter_frame = ttk.Frame(lf)
        filter_frame.pack(fill=tk.X, pady=(2, 5))
        self.show_marked_only_var = tk.BooleanVar(value=False)
        self.toggle_btn = tk.Button(filter_frame, text="Show Marked Only: OFF", bg='gray', fg='white', 
                                    font=('Arial', 9, 'bold'), relief=tk.FLAT, command=self.toggle_marked_filter)
        self.toggle_btn.pack(fill=tk.X, padx=5)
        
        ts = ttk.Scrollbar(lf)
        ts.pack(side=tk.RIGHT, fill=tk.Y)
        self.folder_tree = ttk.Treeview(lf, yscrollcommand=ts.set)
        self.folder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ts.config(command=self.folder_tree.yview)
        self.navigator = FolderNavigator(self.folder_tree, self._on_subfolder_change)

        # Macro / Run button under tree
        btn_frame = ttk.Frame(lf)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Send to Mobile (Enter)",
                   command=self._send_to_mobile_threaded).pack(fill=tk.X, padx=2)

        # Block left/right from changing tree selection
        self.folder_tree.bind('<Left>',  lambda e: (self._prev_image(), 'break')[1])
        self.folder_tree.bind('<Right>', lambda e: (self._next_image(), 'break')[1])

        # CENTER: Brightness ─────────────────────────────────────────────────────
        bf = ttk.LabelFrame(main, text="Brightness", width=100)
        bf.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        bf.pack_propagate(False)
        bc = ttk.Frame(bf)
        bc.pack(expand=True)

        ttk.Label(bc, text="Default").pack(pady=(0, 2))
        self.default_brightness_var = tk.StringVar(
            value=config.get("global_default_brightness", ""))
        self.default_brightness_entry = ttk.Entry(bc, textvariable=self.default_brightness_var,
                  width=5)
        self.default_brightness_entry.pack(pady=(0, 10))
        self.default_brightness_var.trace_add("write",
                                              self._on_default_brightness_change)

        tk.Button(bc, text="+", font=('Arial', 12, 'bold'), width=3, relief=tk.RAISED,
                   command=self._increase_brightness).pack(pady=5)
        self.brightness_var = tk.IntVar(value=100)
        ttk.Scale(bc, from_=200, to=0, orient=tk.VERTICAL,
                  variable=self.brightness_var,
                  command=self._on_brightness_change,
                  length=300).pack(pady=5)
        tk.Button(bc, text="-", font=('Arial', 14, 'bold'), width=3, relief=tk.RAISED,
                   command=self._decrease_brightness).pack(pady=5)
        self.brightness_label = ttk.Label(bc, text="100%")
        self.brightness_label.pack(pady=5)

        # RIGHT: image + mobile status ───────────────────────────────────────────
        rf = ttk.Frame(main)
        rf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Image frame (takes most space)
        img_frame = ttk.LabelFrame(rf, text="Eye Image")
        img_frame.pack(fill=tk.BOTH, expand=True)
        self.image_canvas = tk.Canvas(img_frame, bg='gray')
        self.image_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_canvas.bind('<Configure>', lambda e: self._redraw_preview())

        # Initialize ImageDisplay with encryption key
        key = self.lm.encryption_key if self.lm else None
        self.image_display = ImageDisplay(
            self.image_canvas, self.att_id_label,
            on_view_change=self._update_server_image,
            encryption_key=key
        )

        # Image index info
        nav_row = ttk.Frame(img_frame)
        nav_row.pack(fill=tk.X, padx=4, pady=(0, 3))
        ttk.Button(nav_row, text="◀", width=3,
                   command=self._prev_image).pack(side=tk.LEFT)
        self.img_idx_var = tk.StringVar(value="0 / 0")
        ttk.Label(nav_row, textvariable=self.img_idx_var,
                  width=8, anchor=tk.CENTER).pack(side=tk.LEFT, padx=4)
        ttk.Button(nav_row, text="▶", width=3,
                   command=self._next_image).pack(side=tk.LEFT)

        # Mobile status panel
        ms = ttk.LabelFrame(rf, text="📱 Mobile / ADB Status")
        ms.pack(fill=tk.X, pady=(4, 0))
        ms_inner = ttk.Frame(ms, padding=6)
        ms_inner.pack(fill=tk.X)

        self.mobile_pending_var = tk.StringVar(value="Pending: —")
        self.mobile_status_var  = tk.StringVar(value="Status: Idle")
        self.mobile_acked_var   = tk.StringVar(value="Last: —")

        ttk.Label(ms_inner, textvariable=self.mobile_pending_var,
                  font=('Arial', 11, 'bold'), width=22).pack(side=tk.LEFT, padx=5)
        self.mobile_status_lbl = ttk.Label(ms_inner,
                                           textvariable=self.mobile_status_var,
                                           font=('Arial', 11), width=20)
        self.mobile_status_lbl.pack(side=tk.LEFT, padx=5)
        ttk.Label(ms_inner, textvariable=self.mobile_acked_var,
                  font=('Arial', 10), width=20).pack(side=tk.LEFT, padx=5)

        # Auto-Tap Settings strip
        tap_f = ttk.LabelFrame(rf, text="Auto-Tap Settings")
        tap_f.pack(fill=tk.X, pady=(4, 0))
        tap_row = ttk.Frame(tap_f, padding=4)
        tap_row.pack(fill=tk.X)

        self.btn_calib = ttk.Button(tap_row, text="📍 Calibrate PC Screen", command=self._calibrate_method)
        self.btn_calib.pack(side=tk.LEFT, padx=4)

        self.calib_status_var = tk.StringVar(value="Calib: not loaded")
        self.lbl_calib = ttk.Label(tap_row, textvariable=self.calib_status_var,
                  font=('Arial', 9), foreground='gray')
        self.lbl_calib.pack(side=tk.LEFT, padx=10)

        self.tnc_var = tk.BooleanVar(value=config.get('mobile_tnc_enabled', False))
        self.chk_tnc = ttk.Checkbutton(tap_row, text="T&C", variable=self.tnc_var, command=lambda: config.set('mobile_tnc_enabled', self.tnc_var.get()))
        self.chk_tnc.pack(side=tk.LEFT, padx=5)

        ttk.Label(tap_row, text="User:").pack(side=tk.LEFT, padx=(10, 2))
        self.user_var = tk.StringVar(value=config.get('mobile_tap_user', 'SEH'))
        self.user_combo = ttk.Combobox(tap_row, textvariable=self.user_var, values=["SEH", "UJN"], state='readonly', width=5)
        self.user_combo.pack(side=tk.LEFT, padx=2)

        self.hold_var = tk.StringVar(value=str(config.get('ujn_hold_time', 0.15)))
        self.delay_var = tk.StringVar(value=str(config.get('ujn_delay_time', 0.35)))
        
        self.lbl_hold = ttk.Label(tap_row, text="Hold(s):")
        self.ent_hold = ttk.Entry(tap_row, textvariable=self.hold_var, width=5)
        self.lbl_delay = ttk.Label(tap_row, text="Delay(s):")
        self.ent_delay = ttk.Entry(tap_row, textvariable=self.delay_var, width=5)

        def _on_user_change(e):
            val = self.user_var.get()
            config.set('mobile_tap_user', val)
            if val == "UJN":
                self.lbl_hold.pack(side=tk.LEFT, padx=(10, 2))
                self.ent_hold.pack(side=tk.LEFT, padx=2)
                self.lbl_delay.pack(side=tk.LEFT, padx=(10, 2))
                self.ent_delay.pack(side=tk.LEFT, padx=2)
            else:
                self.lbl_hold.pack_forget()
                self.ent_hold.pack_forget()
                self.lbl_delay.pack_forget()
                self.ent_delay.pack_forget()

        self.user_combo.bind('<<ComboboxSelected>>', _on_user_change)
        
        def _save_delays(*args):
            try:
                config.set('ujn_hold_time', float(self.hold_var.get()))
                config.set('ujn_delay_time', float(self.delay_var.get()))
            except ValueError:
                pass
                
        self.hold_var.trace_add('write', _save_delays)
        self.delay_var.trace_add('write', _save_delays)

        _on_user_change(None)

        self._check_calibration()

        # Info label at bottom
        self.info_label = ttk.Label(c, text="No image loaded", font=('Arial', 9))
        self.info_label.pack(fill=tk.X, padx=10, pady=3)

        self.refresh_batch_list()

    def _calibrate_method(self):
        ScreenCalibrationWindow(self.parent, self._check_calibration)

    # ── Key bindings ─────────────────────────────────────────────────────────────

    def _bind_keys(self):
        self.parent.bind('<Return>',         self._on_enter)
        self.parent.bind('<Key-b>',          self._prompt_brightness)
        self.parent.bind('<Key-B>',          self._prompt_brightness)
        self.parent.bind('<Key-m>',          self._toggle_mark)
        self.parent.bind('<Key-M>',          self._toggle_mark)
        self.parent.bind('<Key-n>',          self._toggle_not_working)
        self.parent.bind('<Key-N>',          self._toggle_not_working)
        self.folder_tree.bind('<Key-m>',     self._toggle_mark)
        self.folder_tree.bind('<Key-M>',     self._toggle_mark)
        self.folder_tree.bind('<Key-b>',     self._prompt_brightness)
        self.folder_tree.bind('<Key-B>',     self._prompt_brightness)
        self.folder_tree.bind('<Key-n>',     self._toggle_not_working)
        self.folder_tree.bind('<Key-N>',     self._toggle_not_working)
        if hasattr(self, 'image_canvas'):
            self.image_canvas.bind('<Key-m>', self._toggle_mark)
            self.image_canvas.bind('<Key-M>', self._toggle_mark)
            self.image_canvas.bind('<Key-b>', self._prompt_brightness)
            self.image_canvas.bind('<Key-B>', self._prompt_brightness)
            self.image_canvas.bind('<Key-n>', self._toggle_not_working)
            self.image_canvas.bind('<Key-N>', self._toggle_not_working)

    def _unbind_keys(self):
        for seq in ('<Return>', '<Key-b>', '<Key-B>', '<Key-m>', '<Key-M>', '<Key-n>', '<Key-N>'):
            try:
                self.parent.unbind(seq)
            except Exception:
                pass

    # ── Batch loading ────────────────────────────────────────────────────────────

    def refresh_batch_list(self, force_load=False):
        if not self.data_dir.exists():
            self.batch_combo['values'] = []
            return
        folders = sorted(f.name for f in self.data_dir.iterdir() if f.is_dir())
        self.batch_combo['values'] = folders
        last = config.get('last_batch_path', '')
        if last:
            name = Path(last).name
            if name in folders:
                self.batch_var.set(name)
                if force_load or not hasattr(self, '_first_load_done'):
                    self._first_load_done = True
                    self.load_selected_batch()

    def load_selected_batch(self):
        name = self.batch_var.get()
        if not name:
            return
        path = self.data_dir / name
        if not path.exists():
            return
        try:
            parts = name.split(' - ')
            self.lbl_batch_id.config(text=f"Batch ID: {parts[0].strip()}")
            if len(parts) > 1:
                tp = parts[1].lower().split(' to ')
                if len(tp) == 2:
                    self.lbl_batch_in.config(text=f"In Time: {tp[0].strip()}")
                    self.lbl_batch_out.config(text=f"Out Time: {tp[1].strip()}")
        except Exception:
            self.lbl_batch_id.config(text=f"Batch: {name}")
        config.set('last_batch_path', str(path))
        self.navigator.load_folder(str(path), show_marked_only=self.show_marked_only_var.get())
        children = self.folder_tree.get_children()
        if children:
            self.folder_tree.selection_set(children[0])
            self.folder_tree.focus(children[0])
            self.folder_tree.focus_set()

    # ── Subfolder / image navigation ─────────────────────────────────────────────

    def _on_subfolder_change(self, subfolder_path):
        if not subfolder_path:
            return
        name = subfolder_path.name
        self.att_id_label.config(text=name)

        try:
            total   = len(self.navigator.subfolders)
            current = self.navigator.subfolders.index(subfolder_path) + 1
            self.sr_label.config(text=f"{current} / {total}")
        except ValueError:
            self.sr_label.config(text="---")

        # Load image list
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.ira'}
        try:
            self.current_images = sorted(
                f for f in subfolder_path.iterdir()
                if f.is_file() and f.suffix.lower() in exts)
        except Exception:
            self.current_images = []

        # Restore brightness / image index
        saved = config.get_subfolder_settings(name)
        global_val = self.default_brightness_var.get().strip()
        
        has_override = saved.get('has_override', False)
        if has_override:
            self.current_brightness = saved.get('brightness', 100)
        else:
            if global_val:
                try:
                    self.current_brightness = int(global_val)
                except ValueError:
                    self.current_brightness = 100
            else:
                self.current_brightness = 100
                
        self.current_zoom = saved.get('zoom', 100)
        saved_index = saved.get('image_index', 0)
        
        self._updating_brightness = True
        try:
            self.brightness_var.set(self.current_brightness)
            self.brightness_label.config(text=f"{self.current_brightness}%")
        finally:
            self._updating_brightness = False

        # Check marked state
        subfolder_str = str(subfolder_path)
        marked_folders = config.get('marked_folders', [])
        
        # Check not_working state
        not_working_folders = config.get('not_working_folders', [])
        is_not_working = subfolder_str in not_working_folders
        self.apply_layout_theme(is_not_working)
        
        self._update_ui_marked_state(subfolder_str in marked_folders)
        self._update_marked_count()

        if self.current_images:
            self.current_image_index = min(saved_index,
                                           len(self.current_images) - 1)
            self._load_current_image()
        else:
            self._current_pil_img = None
            self.image_canvas.delete('all')
            self.img_idx_var.set("0 / 0")
            self.info_label.config(
                text=f"Subfolder: {name} (No images)")
            server.update_image(None)

    def _load_current_image(self):
        if (self.current_image_index < 0 or
                self.current_image_index >= len(self.current_images)):
            return
        image_path = self.current_images[self.current_image_index]
        success = self.image_display.load_image(
            image_path, self.current_brightness, self.current_zoom)
        if success:
            sf_name = self.navigator.get_current_subfolder_name()
            self.img_idx_var.set(
                f"{self.current_image_index + 1}/{len(self.current_images)}")
            self.info_label.config(
                text=f"Subfolder: {sf_name} | Image: {image_path.name} | "
                     f"{self.current_image_index + 1}/{len(self.current_images)}")
            server.update_image(self.image_display.current_image)

    def _prev_image(self, event=None):
        if self.current_images and self.current_image_index > 0:
            self.current_image_index -= 1
            self._load_current_image()
            self._save_state()

    def _next_image(self, event=None):
        if (self.current_images and
                self.current_image_index < len(self.current_images) - 1):
            self.current_image_index += 1
            self._load_current_image()
            self._save_state()

    def _save_state(self, override=None):
        sf_name = self.navigator.get_current_subfolder_name()
        if sf_name:
            config.set_subfolder_settings(
                sf_name, self.current_brightness,
                self.current_zoom, self.current_image_index, override)

    # ── Brightness ───────────────────────────────────────────────────────────────

    def _on_brightness_change(self, value):
        new_val = int(float(value))
        self.current_brightness = new_val
        self.brightness_label.config(text=f"{new_val}%")
        self.image_display.set_brightness(new_val)
        server.update_image(self.image_display.current_image)
        if not getattr(self, '_updating_brightness', False):
            self._save_state(override=True)

    def _increase_brightness(self):
        new = min(200, self.current_brightness + 1)
        self.brightness_var.set(new)
        self._on_brightness_change(new)

    def _decrease_brightness(self):
        new = max(0, self.current_brightness - 1)
        self.brightness_var.set(new)
        self._on_brightness_change(new)

    def _on_default_brightness_change(self, *args):
        val = self.default_brightness_var.get().strip()
        config.set("global_default_brightness", val)
        
        sf_name = self.navigator.get_current_subfolder_name()
        if not sf_name: return
        saved = config.get_subfolder_settings(sf_name)
        
        if not saved.get('has_override', False):
            if val:
                try:
                    new_val = int(val)
                    self.current_brightness = new_val
                    self._updating_brightness = True
                    try:
                        self.brightness_var.set(new_val)
                        self.brightness_label.config(text=f"{new_val}%")
                    finally:
                        self._updating_brightness = False
                    if hasattr(self, 'image_display'):
                        self.image_display.set_brightness(new_val)
                        server.update_image(self.image_display.current_image)
                except ValueError:
                    pass
            else:
                self.current_brightness = 100
                self._updating_brightness = True
                try:
                    self.brightness_var.set(100)
                    self.brightness_label.config(text="100%")
                finally:
                    self._updating_brightness = False
                if hasattr(self, 'image_display'):
                    self.image_display.set_brightness(100)
                    server.update_image(self.image_display.current_image)

    def _prompt_brightness(self, event=None):
        from tkinter import simpledialog
        val = simpledialog.askinteger(
            "Brightness", "Enter brightness percentage:",
            parent=self.frame, minvalue=0, maxvalue=500)
        if val is not None:
            self.brightness_var.set(val)
            self._on_brightness_change(val)
        self.parent.focus_force()
        self.folder_tree.focus_set()
        return 'break'

    # ── Mark ────────────────────────────────────────────────────────────────────

    def _toggle_mark(self, event=None):
        if not self.navigator.current_subfolder:
            return 'break'
        subfolder_str = str(self.navigator.current_subfolder)
        marked_folders = config.get('marked_folders', [])
        if subfolder_str in marked_folders:
            marked_folders.remove(subfolder_str)
            is_marked = False
        else:
            marked_folders.append(subfolder_str)
            is_marked = True
        config.set('marked_folders', marked_folders)
        self._update_ui_marked_state(is_marked)
        self._update_marked_count()
        
        # Update Treeview tags safely
        sel = self.folder_tree.selection()
        if sel:
            item = sel[0]
            tags = self.folder_tree.item(item, 'tags')
            if isinstance(tags, str):
                tags = (tags,) if tags else ()
            tags_list = list(tags)
            if is_marked and 'marked' not in tags_list:
                tags_list.append('marked')
            elif not is_marked and 'marked' in tags_list:
                tags_list.remove('marked')
            self.folder_tree.item(item, tags=tags_list)
            
        return 'break'

    def toggle_marked_filter(self):
        new_val = not self.show_marked_only_var.get()
        self.show_marked_only_var.set(new_val)
        
        if new_val:
            self.toggle_btn.config(text="Show Marked Only: ON", bg='#e53935')
        else:
            self.toggle_btn.config(text="Show Marked Only: OFF", bg='gray')
            
        name = self.batch_var.get()
        if name:
            self.load_selected_batch()

    def _update_ui_marked_state(self, is_marked):
        is_not_working = False
        if hasattr(self, 'navigator') and self.navigator.current_subfolder:
            is_not_working = str(self.navigator.current_subfolder) in config.get('not_working_folders', [])
        color    = 'red' if is_marked else ''
        bg_color = 'black' if is_not_working else ('#4a0000' if is_marked else 'gray')
        self.att_id_label.config(foreground=color)
        self.sr_label.config(foreground=color)
        self.marked_count_label.config(foreground=color)
        self.image_canvas.config(bg=bg_color)
        
        # Update labels in the info_inner frame too
        for child in self.lbl_batch_id.master.winfo_children():
            if isinstance(child, ttk.Label):
                try:
                    child.configure(foreground=color)
                except:
                    pass

    def _update_marked_count(self):
        if not hasattr(self.navigator, 'subfolders') or not self.navigator.subfolders:
            self.marked_count_label.config(text="0")
            return
        marked_folders = config.get('marked_folders', [])
        count = sum(1 for sf in self.navigator.subfolders
                    if str(sf) in marked_folders)
        self.marked_count_label.config(text=str(count))

    # ── Image drawing ────────────────────────────────────────────────────────────

    def _redraw_preview(self):
        """Redraw the eye image in the canvas (called on resize)."""
        if hasattr(self, 'image_display') and self.image_display.current_image:
            cw = self.image_canvas.winfo_width()
            ch = self.image_canvas.winfo_height()
            if cw < 2 or ch < 2:
                return
            img = self.image_display.current_image.copy()
            img.thumbnail((cw, ch), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self.image_canvas.delete('all')
            self.image_canvas.create_image(
                cw // 2, ch // 2, anchor=tk.CENTER, image=self._photo)

    def _update_server_image(self):
        if hasattr(self, 'image_display') and self.image_display:
            server.update_image(self.image_display.current_image)

    # ── Enter key — Send to Mobile ───────────────────────────────────────────────

    def _on_enter(self, event=None):
        """Enter pressed — auto-type current attendance ID and return focus."""
        focused = self.parent.focus_get()
        if isinstance(focused, ttk.Entry) or isinstance(focused, tk.Entry):
            return

        self._send_to_mobile_threaded()
        return 'break'

    def _send_to_mobile_threaded(self):
        """Kick off tap sequence in a daemon thread."""
        subfolder_name = self.navigator.get_current_subfolder_name()
        if not subfolder_name:
            return

        self._mobile_ui_queue.put(('status', '⏳ PC Screen tapping ID…'))
        self._mobile_ui_queue.put(('pending', subfolder_name))
        current_user = self.user_var.get()
        try:
            custom_hold = float(self.hold_var.get())
            custom_delay = float(self.delay_var.get())
        except ValueError:
            custom_hold = 0.15
            custom_delay = 0.35
            
        t = threading.Thread(target=self._send_to_mobile_worker,
                             args=(subfolder_name, current_user, custom_hold, custom_delay), daemon=True)
        t.start()

    def _send_to_mobile_worker(self, subfolder_name, current_user="SEH", custom_hold=0.15, custom_delay=0.35):
        """Background: Tap each digit using calibrated screen coordinates."""
        coords = config.get("screen_digit_coords", {})
        if not coords:
            self._mobile_ui_queue.put(('status', '❌ Not calibrated — Click Calibrate'))
            return
            
        # Clean the ID to only include digits (e.g., if there are spaces or dashes)
        clean_id = "".join(filter(str.isdigit, str(subfolder_name)))
        if not clean_id:
            self._mobile_ui_queue.put(('status', '❌ No digits in ID'))
            return

        missing = [d for d in clean_id if d not in coords]
        if missing:
            self._mobile_ui_queue.put(('status', f'❌ No coords for digit(s): {set(missing)}'))
            return
            
        tnc_enabled = config.get('mobile_tnc_enabled', False)
        if tnc_enabled and "TC" not in coords:
            self._mobile_ui_queue.put(('status', '❌ T&C Not Calibrated'))
            return

        def _progress(digit, idx, total):
            self._mobile_ui_queue.put(('status', f'🔢 Tapping {digit} ({idx+1}/{total})'))

        ok = True
        import pyautogui
        # Prevent PyAutoGUI from moving too fast and throwing errors
        pyautogui.PAUSE = 0.05
        
        if current_user == "UJN":
            hold_time = custom_hold
            tap_delay = custom_delay
        else:
            hold_time = 0.05
            tap_delay = 0.35
            
        if tnc_enabled:
            _progress("T&C", 0, len(clean_id))
            c = coords["TC"]
            try:
                pyautogui.moveTo(x=c['x'], y=c['y'])
                time.sleep(0.02)
                pyautogui.mouseDown()
                time.sleep(hold_time)
                pyautogui.mouseUp()
                time.sleep(tap_delay)
            except Exception as e:
                print(f"PyAutoGUI error: {e}")
                self._mobile_ui_queue.put(('status', '⚠ T&C tap failed'))
                return
        
        for i, digit in enumerate(clean_id):
            _progress(digit, i, len(clean_id))
            c = coords[digit]
            try:
                # Move to the coordinate first and let it settle
                pyautogui.moveTo(x=c['x'], y=c['y'])
                time.sleep(0.02)
                
                # Perform the tap without coordinates so it stays exactly in place
                pyautogui.mouseDown()
                time.sleep(hold_time)
                pyautogui.mouseUp()
                
                # Wait before the next digit
                time.sleep(tap_delay)
            except Exception as e:
                print(f"PyAutoGUI error: {e}")
                ok = False
                break

        if ok:
            self._mobile_ui_queue.put(('status', '✅ ID Typed'))
            self._mobile_ui_queue.put(('focus', None))
        else:
            self._mobile_ui_queue.put(('status', '⚠ Some taps failed'))
    def _check_calibration(self):
        """Refresh calibration status label."""
        coords = config.get("screen_digit_coords", {})

        if coords:
            # We don't care about OK anymore, just count digits
            digits = [d for d in coords.keys() if d != "OK"]
            self.calib_status_var.set(f"Calibrated: {len(digits)}/10 digits")
        else:
            self.calib_status_var.set("Calib: not loaded")

    def _poll_mobile_ui_queue(self):
        try:
            while True:
                action, payload = self._mobile_ui_queue.get_nowait()
                if action == 'pending':
                    self.mobile_pending_var.set(f"Pending: {payload}")
                elif action == 'status':
                    self.mobile_status_var.set(f"Status: {payload}")
                    # Color coding
                    color = ('#2E7D32' if '✅' in payload
                             else '#E65100' if '⚠' in payload
                             else '#C62828' if '❌' in payload
                             else '#1565C0')
                    self.mobile_status_lbl.config(foreground=color)
                elif action == 'acked':
                    self.mobile_acked_var.set(f"Last ✅: {payload}")
                elif action == 'navigate_down':
                    self.navigator.navigate_down()
                    # Re-focus tree so arrow keys work
                    self.folder_tree.focus_set()
                    sel = self.folder_tree.selection()
                    if sel:
                        self.folder_tree.focus(sel[0])
                elif action == 'focus':
                    self.window_manager.bring_to_front()
                    self.parent.focus_force()
                    self.folder_tree.focus_set()
        except queue.Empty:
            pass
        self.parent.after(100, self._poll_mobile_ui_queue)

    # ── Show / hide ──────────────────────────────────────────────────────────────

    def show(self):
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.refresh_batch_list(force_load=True)
        self._bind_keys()
        self.parent.focus_set()

    def hide(self):
        self._unbind_keys()
        self.apply_layout_theme(False)
        self.frame.pack_forget()

    def _safe_back(self):
        self._unbind_keys()
        self.apply_layout_theme(False)
        self.on_back_callback()

    def _toggle_not_working(self, event=None):
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
        self.apply_layout_theme(is_not_working)
        self._update_ui_marked_state(subfolder_str in config.get('marked_folders', []))
        return 'break'

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
                            widget.config(bg='SystemButtonFace', fg='SystemButtonText')
                        elif w_class in ('Frame', 'Labelframe'):
                            widget.config(bg='SystemButtonFace')
            except Exception:
                pass
                
        for child in widget.winfo_children():
            if isinstance(child, tk.Toplevel):
                continue
            self._update_tk_widgets_recursive(child, is_black)

class CalibrationWindow(tk.Toplevel):
    """Popup window to calibrate phone numpad coordinates on PC."""
    def __init__(self, parent, phone_ip, on_close_cb):
        super().__init__(parent)
        self.title("Calibrate via ADB Screencap")
        self.phone_ip = phone_ip
        self.on_close_cb = on_close_cb
        self.geometry("600x800")
        self.transient(parent)
        self.grab_set()

        self.coords = config.get("adb_digit_coords", {})
        self.current_digit = 0
        self.scale_factor = 1.0

        # UI
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)
        self.lbl_inst = ttk.Label(top, text="Fetching screenshot...", font=('Arial', 14, 'bold'))
        self.lbl_inst.pack()
        ttk.Button(top, text="Cancel", command=self.destroy).pack(pady=5)

        self.canvas = tk.Canvas(self, bg='black', cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_click)

        # Start fetch
        self.after(100, self.fetch_screencap)

    def fetch_screencap(self):
        img_bytes = adb_utils.adb_screencap(self.phone_ip)
        if not img_bytes:
            messagebox.showerror("Error", "Failed to fetch screencap. Ensure ADB is connected.")
            self.destroy()
            return
        try:
            pil_img = Image.open(io.BytesIO(img_bytes))
            self.orig_width, self.orig_height = pil_img.size

            # Scale to fit window
            win_w = 600
            win_h = 700
            w_ratio = win_w / self.orig_width
            h_ratio = win_h / self.orig_height
            self.scale_factor = min(w_ratio, h_ratio)
            
            new_w = int(self.orig_width * self.scale_factor)
            new_h = int(self.orig_height * self.scale_factor)
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.tk_img = ImageTk.PhotoImage(pil_img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
            self.update_instruction()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")
            self.destroy()

    def update_instruction(self):
        if self.current_digit <= 9:
            self.lbl_inst.config(text=f"Click on the number {self.current_digit}", foreground="red")
        else:
            self.lbl_inst.config(text="All done! Saving...", foreground="green")
            config.set("adb_digit_coords", self.coords)
            messagebox.showinfo("Success", "Calibration saved successfully!")
            self.on_close_cb()
            self.destroy()

    def on_click(self, event):
        if self.current_digit > 9:
            return
        
        # Convert window click to original phone resolution
        real_x = int(event.x / self.scale_factor)
        real_y = int(event.y / self.scale_factor)
        
        self.coords[str(self.current_digit)] = {"x": real_x, "y": real_y}
        
        # Draw a dot
        r = 5
        self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, fill='lime')
        self.canvas.create_text(event.x+10, event.y-10, text=str(self.current_digit), fill='lime', font=('Arial', 12, 'bold'))

        self.current_digit += 1
        self.update_instruction()

class PairingWindow(tk.Toplevel):
    """Popup window for ADB Pairing over WiFi."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Pair Device")
        self.geometry("380x250")
        self.transient(parent)
        self.grab_set()

        lbl = ttk.Label(self, text="Wi-Fi Pairing Setup", font=('Arial', 14, 'bold'))
        lbl.pack(pady=(15, 5))

        desc = ttk.Label(self, text="Enter the Pairing IP:Port and 6-digit code\nshown in 'Pair device with pairing code'.", justify=tk.CENTER)
        desc.pack(pady=(0, 15))

        f = ttk.Frame(self)
        f.pack(padx=20, fill=tk.X)

        ttk.Label(f, text="IP address & Port:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ip_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.ip_var, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(f, text="6-digit Pairing Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.code_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.code_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        btn_f = ttk.Frame(self)
        btn_f.pack(pady=20)
        
        ttk.Button(btn_f, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_f, text="Pair", command=self.do_pair).pack(side=tk.LEFT, padx=10)

    def do_pair(self):
        ip_port = self.ip_var.get().strip()
        code = self.code_var.get().strip()

        if not ip_port or not code:
            messagebox.showwarning("Error", "Please fill in both fields.", parent=self)
            return

        ok, msg = adb_utils.adb_pair(ip_port, code)
        if ok:
            messagebox.showinfo("Success", f"✅ {msg}", parent=self)
            self.destroy()
        else:
            messagebox.showerror("Failed", f"❌ {msg}", parent=self)

class ScreenCalibrationWindow(tk.Toplevel):
    """Full-screen transparent window to click directly on the Windows monitor."""
    def __init__(self, parent, on_close_cb):
        super().__init__(parent)
        self.on_close_cb = on_close_cb
        self.coords = config.get("screen_digit_coords", {})
        
        self.tnc_enabled = config.get('mobile_tnc_enabled', False)
        self.current_step = "TC" if self.tnc_enabled else 0
        
        # Make fullscreen and semi-transparent
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.5)
        self.attributes('-topmost', True)
        self.configure(cursor='crosshair', bg='black')

        if self.current_step == "TC":
            text = "Click exactly on the T&C Checkbox"
        else:
            text = f"Click exactly on the number {self.current_step}"

        self.lbl = tk.Label(self, text=text, 
                            font=('Arial', 24, 'bold'), fg='red', bg='black')
        self.lbl.pack(pady=50)
        
        tk.Label(self, text="Press ESC to cancel", font=('Arial', 14), fg='white', bg='black').pack()

        self.bind("<Button-1>", self.on_click)
        self.bind("<Escape>", lambda e: self.destroy())

    def on_click(self, event):
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        
        if self.current_step == "TC":
            key = "TC"
            self.coords[key] = {"x": x, "y": y}
            self.current_step = 0
            
            # Visual feedback
            r = 10
            canvas = tk.Canvas(self, width=40, height=40, bg='black', highlightthickness=0)
            canvas.place(x=x-20, y=y-20)
            canvas.create_oval(10, 10, 30, 30, outline='lime', width=3)
            canvas.create_text(20, 20, text=key, fill='lime', font=('Arial', 10, 'bold'))

            self.lbl.config(text=f"Click exactly on the number {self.current_step}")
            return

        if isinstance(self.current_step, int):
            if self.current_step > 9:
                return
            
            key = str(self.current_step)
            self.coords[key] = {"x": x, "y": y}
            
            # Visual feedback
            r = 10
            canvas = tk.Canvas(self, width=40, height=40, bg='black', highlightthickness=0)
            canvas.place(x=x-20, y=y-20)
            canvas.create_oval(10, 10, 30, 30, outline='lime', width=3)
            canvas.create_text(20, 20, text=key, fill='lime', font=('Arial', 10, 'bold'))
    
            self.current_step += 1
            
            if self.current_step <= 9:
                self.lbl.config(text=f"Click exactly on the number {self.current_step}")
            else:
                self.lbl.config(text="Calibration complete! Saving...", fg='green')
                # Remove OK if it was saved previously
                if "OK" in self.coords:
                    del self.coords["OK"]
                config.set("screen_digit_coords", self.coords)
                self.after(500, self._finish)

    def _finish(self):
        self.on_close_cb()
        self.destroy()

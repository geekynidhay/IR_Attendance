"""
Facial Data Mode for IR Attendance application.
Processes images to create realistic 3D-like blinking videos with black backgrounds.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from pathlib import Path
import threading
import os
import cv2

from config import config
from footer import Footer
from face_processor import FaceProcessor

class FacialDataMode:
    """Facial Data Mode UI and logic"""
    
    def __init__(self, parent, on_back_callback):
        self.parent = parent
        self.on_back_callback = on_back_callback
        self.frame = ttk.Frame(parent)
        self.processor = None
        self.tk_images = []  # Prevention of garbage collection
        
        self.create_ui()
        
    def create_ui(self):
        """Create the facial data mode UI"""
        # Main container
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        self.footer = Footer(self.frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Header
        header_frame = ttk.Frame(self.content_container)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="Facial Data - 3D Blink Mode", 
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back to Menu", 
                  command=self.on_back_callback).pack(side=tk.RIGHT)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.content_container, text="Batch Process Settings", padding=15)
        settings_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Raw data folder
        raw_frame = ttk.Frame(settings_frame)
        raw_frame.pack(fill=tk.X, pady=5)
        ttk.Label(raw_frame, text="Raw Data:", width=12).pack(side=tk.LEFT)
        self.raw_folder_var = tk.StringVar(value=config.get('last_raw_data_path', ''))
        ttk.Entry(raw_frame, textvariable=self.raw_folder_var, width=50).pack(side=tk.LEFT, padx=10)
        ttk.Button(raw_frame, text="Browse", command=self.browse_raw_folder).pack(side=tk.LEFT)
        
        # Output folder
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill=tk.X, pady=5)
        ttk.Label(output_frame, text="Final Data:", width=12).pack(side=tk.LEFT)
        self.output_folder_var = tk.StringVar(value=config.get('last_facial_data_path', ''))
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=50).pack(side=tk.LEFT, padx=10)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_folder).pack(side=tk.LEFT)
        
        # Process button & Progress
        process_frame = ttk.Frame(settings_frame)
        process_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(process_frame, text="Start Generation", 
                                   command=self.start_batch_thread, style='Accent.TButton')
        self.start_btn.pack(side=tk.LEFT)
                   
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(process_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.progress_label = ttk.Label(process_frame, text="Ready")
        self.progress_label.pack(side=tk.LEFT)
        
        # Live Preview Frame
        self.preview_frame = ttk.LabelFrame(self.content_container, text="Generation Preview", padding=10)
        self.preview_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.id_label = ttk.Label(self.preview_frame, text="Current ID: None", font=('Arial', 14, 'bold'))
        self.id_label.pack(side=tk.TOP, pady=5)
        
        self.canvas = tk.Canvas(self.preview_frame, bg='#121212')
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=5)
        
    def browse_raw_folder(self):
        folder = filedialog.askdirectory(title="Select Raw Data Folder")
        if folder:
            self.raw_folder_var.set(folder)
            config.set('last_raw_data_path', folder)
    
    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Final Data Folder")
        if folder:
            self.output_folder_var.set(folder)
            config.set('last_facial_data_path', folder)

    def update_visuals(self, extracted_number, image_path, video_path):
        """Update live preview canvas"""
        self.id_label.config(text=f"Current ID: {extracted_number}")
        
        self.canvas.delete("all")
        self.tk_images = []
        
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w < 100 or canvas_h < 100:
            return
            
        # Draw original image
        try:
            pil_img = Image.open(image_path)
            w, h = pil_img.size
            scale = min((canvas_w // 2 - 20) / w, (canvas_h - 40) / h)
            nw, nh = int(w * scale), int(h * scale)
            disp_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(disp_img)
            self.tk_images.append(tk_img)
            self.canvas.create_image(canvas_w // 4, canvas_h // 2, image=tk_img, anchor=tk.CENTER)
            self.canvas.create_text(canvas_w // 4, canvas_h - 20, text="Original", fill="white")
            
            # Since showing a video in canvas is hard, we'll just show a "Processing..." text or a thumbnail
            self.canvas.create_rectangle(canvas_w // 2 + 20, 40, canvas_w - 20, canvas_h - 40, outline="green", width=2)
            self.canvas.create_text(3 * canvas_w // 4, canvas_h // 2, text="MP4 Generated\nSuccess ✅", fill="#00FF00", font=('Arial', 14, 'bold'), justify=tk.CENTER)
            self.canvas.create_text(3 * canvas_w // 4, canvas_h - 20, text=f"Saved to {extracted_number}/", fill="white")
        except:
            pass
            
        self.frame.update()

    def start_batch_thread(self):
        """Run batch process in a separate thread to keep UI responsive"""
        raw_folder = self.raw_folder_var.get()
        output_folder = self.output_folder_var.get()
        
        if not raw_folder or not Path(raw_folder).exists():
            messagebox.showerror("Error", "Please select a valid Raw Data folder")
            return
        
        if not output_folder:
            messagebox.showerror("Error", "Please select an Output folder")
            return
            
        self.start_btn.config(state=tk.DISABLED)
        self.progress_label.config(text="Initializing...")
        
        thread = threading.Thread(target=self.process_batch, args=(raw_folder, output_folder))
        thread.daemon = True
        thread.start()

    def process_batch(self, raw_folder, output_folder):
        try:
            if self.processor is None:
                self.processor = FaceProcessor()
                
            def update_progress(current, total, message):
                progress = (current / total * 100) if total > 0 else 0
                self.parent.after(0, lambda: self.update_ui_progress(progress, message))

            def visual_update(id, img, vid):
                self.parent.after(0, lambda: self.update_visuals(id, img, vid))

            results = self.processor.batch_process(
                raw_folder, output_folder, update_progress, visual_update
            )
            
            self.parent.after(0, lambda: self.finish_process(results))
            
        except Exception as e:
            self.parent.after(0, lambda: messagebox.showerror("Error", f"Processing failed: {e}"))
            self.parent.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

    def update_ui_progress(self, progress, message):
        self.progress_var.set(progress)
        self.progress_label.config(text=message)

    def finish_process(self, results):
        self.start_btn.config(state=tk.NORMAL)
        self.progress_label.config(text="Complete")
        
        msg = f"Processed: {results['processed']} / {results['total']} images.\nCandidates: {results['candidates']}"
        if results['errors']:
            msg += f"\n\nErrors encountered in {len(results['errors'])} files."
            
        messagebox.showinfo("Process Complete", msg)

    def show(self):
        self.frame.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        self.frame.pack_forget()

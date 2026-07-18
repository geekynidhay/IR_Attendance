"""
Image Extractor Mode for IR Attendance application
Allows user to batch process JPEG files, extracting a top number using OCR and sub-images.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from pathlib import Path
from config import config
from image_processor import ImageProcessor
from footer import Footer

class ExtractorMode:
    """Image Extractor Mode UI and logic"""
    
    def __init__(self, parent, on_back_callback):
        self.parent = parent
        self.on_back_callback = on_back_callback
        self.frame = ttk.Frame(parent)
        self.tk_images = []  # To prevent garbage collection of live previews
        
        self.create_ui()
    
    def create_ui(self):
        """Create the extractor mode UI"""
        # Main container
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        self.footer = Footer(self.frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Header
        header_frame = ttk.Frame(self.content_container)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="JPG Extraction", 
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back to Menu", 
                  command=self.on_back_callback).pack(side=tk.RIGHT)
        
        # Process settings frame
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
        ttk.Label(output_frame, text="Output:", width=12).pack(side=tk.LEFT)
        self.output_folder_var = tk.StringVar(value=config.get('last_batch_path', ''))
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=50).pack(side=tk.LEFT, padx=10)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_folder).pack(side=tk.LEFT)
        
        # Process button & Progress
        process_frame = ttk.Frame(settings_frame)
        process_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(process_frame, text="Start Extraction", 
                  command=self.process_batch, style='Accent.TButton').pack(side=tk.LEFT)
                  
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(process_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.progress_label = ttk.Label(process_frame, text="Ready")
        self.progress_label.pack(side=tk.LEFT)
        
        # Live Preview Frame
        self.preview_frame = ttk.LabelFrame(self.content_container, text="Live Vision Preview", padding=10)
        self.preview_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.id_label = ttk.Label(self.preview_frame, text="Current ID: None", font=('Arial', 14, 'bold'))
        self.id_label.pack(side=tk.TOP, pady=5)
        
        self.canvas = tk.Canvas(self.preview_frame, bg='#1e1e1e')
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=5)

    def browse_raw_folder(self):
        folder = filedialog.askdirectory(title="Select Raw Data Folder")
        if folder:
            self.raw_folder_var.set(folder)
            config.set('last_raw_data_path', folder)
    
    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder_var.set(folder)
            config.set('last_batch_path', folder)
            
    def update_visuals(self, extracted_number, header_img, crop_imgs):
        """Update live preview canvas with current extractions"""
        self.id_label.config(text=f"Current ID: {extracted_number}")
        
        self.canvas.delete("all")
        self.tk_images = []
        
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        if canvas_w < 100 or canvas_h < 100:
            return  # Not fully drawn yet
            
        # Draw header number
        if header_img:
            hw, hh = header_img.size
            scale = min(200 / max(1, hw), 50 / max(1, hh))
            nhw, nhh = max(1, int(hw * scale)), max(1, int(hh * scale))
            h_im = header_img.resize((nhw, nhh), Image.Resampling.LANCZOS)
            tk_h = ImageTk.PhotoImage(h_im)
            self.tk_images.append(tk_h)
            self.canvas.create_image(canvas_w // 2, 30, image=tk_h, anchor=tk.CENTER)
            
        # Draw horizontal crops
        if crop_imgs:
            num_crops = len(crop_imgs)
            # Allocate space horizontally
            padding = 10
            avail_w = canvas_w - (padding * (num_crops + 1))
            thumb_max_w = avail_w // max(1, num_crops)
            thumb_max_h = canvas_h - 100
            
            x_offset = padding
            y_offset = 80
            
            # Center the row of eyes if there's extra space
            total_crop_w = num_crops * thumb_max_w + (num_crops - 1) * padding
            start_x = max(padding, (canvas_w - total_crop_w) // 2)
            x_offset = start_x
            
            for crop in crop_imgs:
                cw, ch = crop.size
                scale = min(thumb_max_w / max(1, cw), thumb_max_h / max(1, ch))
                ncw, nch = max(1, int(cw * scale)), max(1, int(ch * scale))
                
                c_im = crop.resize((ncw, nch), Image.Resampling.LANCZOS)
                tk_c = ImageTk.PhotoImage(c_im)
                self.tk_images.append(tk_c)
                
                # Draw thumb and bounding box
                self.canvas.create_rectangle(x_offset-2, y_offset-2, x_offset+ncw+2, y_offset+nch+2, outline='#00ff00', width=2)
                self.canvas.create_image(x_offset, y_offset, image=tk_c, anchor=tk.NW)
                
                x_offset += ncw + padding
                
        self.frame.update()
            
    def process_batch(self):
        raw_folder = self.raw_folder_var.get()
        output_folder = self.output_folder_var.get()
        
        if not raw_folder or not Path(raw_folder).exists():
            messagebox.showerror("Error", "Please select a valid Raw Data folder")
            return
        
        if not output_folder:
            messagebox.showerror("Error", "Please select an Output folder")
            return
            
        def update_progress(current, total, message):
            progress = (current / total * 100) if total > 0 else 0
            self.progress_var.set(progress)
            self.progress_label.config(text=message)
            self.frame.update()

        self.canvas.delete("all")
        self.id_label.config(text="Current ID: None")
        self.progress_label.config(text="Initializing Extraction...")
        self.frame.update()
        
        results = ImageProcessor.batch_extract_images(
            raw_folder, output_folder, update_progress, self.update_visuals
        )
        
        if results.get('error'):
            messagebox.showerror("Error", f"Failed to initialize: {results.get('error')}\nPlease check requirements.")
            return

        # Show results in requested format
        main_folder_name = Path(output_folder).name
        message = f"Total Candidates in Batch '{main_folder_name}': {results['candidates']}"
        
        if results['errors'] or results['processed'] == 0:
            message += f"\n\nNote: {results['processed']} images processed successfully."
            if results['errors']:
                message += f"\nErrors occurred in {len(results['errors'])} sections."
        
        messagebox.showinfo("Extraction Complete", message)
    
    def show(self):
        self.frame.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        self.frame.pack_forget()

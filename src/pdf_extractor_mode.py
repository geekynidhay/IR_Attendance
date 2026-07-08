import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from pathlib import Path
from config import config
from image_processor import ImageProcessor
from pdf_processor import PdfProcessor
from footer import Footer
import time
import threading

class PdfExtractorMode:
    """PDF Image Extractor Mode UI and logic"""
    
    def __init__(self, parent, on_back_callback):
        self.parent = parent
        self.on_back_callback = on_back_callback
        self.frame = ttk.Frame(parent)
        self.tk_images = []  
        self.is_processing = False
        
        self.scan_line_y = 0
        self.create_ui()
    
    def create_ui(self):
        """Create the PDF extractor mode UI"""
        # Main container
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(self.content_container, padding=10)
        header_frame.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Label(header_frame, text="PDF Report Extraction", 
                 font=('Segoe UI', 18, 'bold'), foreground='#00D4FF').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back to Menu", 
                  command=self.on_back_callback).pack(side=tk.RIGHT)
        
        # Settings
        settings_frame = ttk.LabelFrame(self.content_container, text="Extraction Settings", padding=15)
        settings_frame.pack(side=tk.TOP, fill=tk.X, padx=20, pady=10)
        
        # PDF File
        pdf_frame = ttk.Frame(settings_frame)
        pdf_frame.pack(fill=tk.X, pady=5)
        ttk.Label(pdf_frame, text="Target PDF:", width=12).pack(side=tk.LEFT)
        self.pdf_path_var = tk.StringVar(value=config.get('last_pdf_path', ''))
        ttk.Entry(pdf_frame, textvariable=self.pdf_path_var, width=60).pack(side=tk.LEFT, padx=10)
        ttk.Button(pdf_frame, text="Browse PDF", command=self.browse_pdf).pack(side=tk.LEFT)
        
        # Output folder
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill=tk.X, pady=5)
        ttk.Label(output_frame, text="Output:", width=12).pack(side=tk.LEFT)
        self.output_folder_var = tk.StringVar(value=config.get('last_batch_path', ''))
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=60).pack(side=tk.LEFT, padx=10)
        ttk.Button(output_frame, text="Browse Folder", command=self.browse_output_folder).pack(side=tk.LEFT)
        
        # Process button & Progress
        process_frame = ttk.Frame(settings_frame)
        process_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(process_frame, text="⚡ START SCANNING", 
                                   command=self.start_extraction, style='Accent.TButton')
        self.start_btn.pack(side=tk.LEFT)
                  
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(process_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)
        
        self.progress_label = ttk.Label(process_frame, text="Ready", font=('Consolas', 10))
        self.progress_label.pack(side=tk.LEFT)
        
        # Live Vision Preview (Dark / Cyberpunk style)
        self.preview_frame = ttk.LabelFrame(self.content_container, text="Live Vision Feed", padding=10)
        self.preview_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.status_bar = ttk.Frame(self.preview_frame)
        self.status_bar.pack(fill=tk.X, pady=5)
        
        self.id_label = ttk.Label(self.status_bar, text="SYSTEM ID: ACTIVE", 
                                font=('Consolas', 14, 'bold'), foreground='#00FF00')
        self.id_label.pack(side=tk.LEFT)
        
        self.page_label = ttk.Label(self.status_bar, text="PAGE: 0/0", 
                                  font=('Consolas', 12))
        self.page_label.pack(side=tk.RIGHT)
        
        self.canvas = tk.Canvas(self.preview_frame, bg='#0A0A0A', highlightthickness=1, highlightbackground='#222')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        self.footer = Footer(self.frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)

    def browse_pdf(self):
        file = filedialog.askopenfilename(title="Select PDF Report", filetypes=[("PDF files", "*.pdf")])
        if file:
            self.pdf_path_var.set(file)
            config.set('last_pdf_path', file)
    
    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder_var.set(folder)
            config.set('last_batch_path', folder)

    def update_visuals(self, extracted_number, header_img, crop_imgs):
        """Update live preview canvas with fancy visuals"""
        self.id_label.config(text=f"DETECTED ID: {extracted_number}")
        
        self.canvas.delete("all")
        self.tk_images = []
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100: return
        
        # Background Grid (Subtle)
        grid_size = 50
        for i in range(0, w, grid_size):
            self.canvas.create_line(i, 0, i, h, fill='#111')
        for i in range(0, h, grid_size):
            self.canvas.create_line(0, i, w, i, fill='#111')
            
        # Draw Header
        if header_img:
            hw, hh = header_img.size
            scale = min(300/hw, 80/hh)
            nhw, nhh = int(hw*scale), int(hh*scale)
            h_im = header_img.resize((nhw, nhh), Image.Resampling.LANCZOS)
            tk_h = ImageTk.PhotoImage(h_im)
            self.tk_images.append(tk_h)
            self.canvas.create_image(w//2, 50, image=tk_h)
            # Glowing border for ID
            self.canvas.create_rectangle(w//2 - nhw//2 - 5, 50 - nhh//2 - 5, 
                                       w//2 + nhw//2 + 5, 50 + nhh//2 + 5, 
                                       outline='#00D4FF', width=2)

        # Draw Crops with "glitch" or "scanner" look
        if crop_imgs:
            num = len(crop_imgs)
            padding = 20
            avail_w = w - (padding * (num + 1))
            tw = avail_w // max(1, num)
            th = h - 200
            
            x_start = (w - (num * tw + (num-1)*padding)) // 2
            
            for i, crop in enumerate(crop_imgs):
                cw, ch = crop.size
                scale = min(tw/cw, th/ch)
                ncw, nch = int(cw*scale), int(ch*scale)
                c_im = crop.resize((ncw, nch), Image.Resampling.LANCZOS)
                tk_c = ImageTk.PhotoImage(c_im)
                self.tk_images.append(tk_c)
                
                cx = x_start + i * (tw + padding)
                cy = 150
                
                # Draw Box
                self.canvas.create_rectangle(cx-2, cy-2, cx+ncw+2, cy+nch+2, outline='#00FF00', width=1)
                # Outer glow effect (simulated with 2 rectangles)
                self.canvas.create_rectangle(cx-4, cy-4, cx+ncw+4, cy+nch+4, outline='#005500', width=1)
                
                self.canvas.create_image(cx, cy, image=tk_c, anchor=tk.NW)
                
                # Corners (Cyberpunk style)
                clense = 15
                self.canvas.create_line(cx-5, cy-5, cx-5+clense, cy-5, fill='#00FF00', width=3)
                self.canvas.create_line(cx-5, cy-5, cx-5, cy-5+clense, fill='#00FF00', width=3)
                
                self.canvas.create_line(cx+ncw+5, cy+nch+5, cx+ncw+5-clense, cy+nch+5, fill='#00FF00', width=3)
                self.canvas.create_line(cx+ncw+5, cy+nch+5, cx+ncw+5, cy+nch+5-clense, fill='#00FF00', width=3)

        self.frame.update()

    def start_extraction(self):
        pdf_path = self.pdf_path_var.get()
        out_folder = self.output_folder_var.get()
        
        if not pdf_path or not Path(pdf_path).exists():
            messagebox.showerror("Error", "Select a valid PDF file")
            return
        if not out_folder:
            messagebox.showerror("Error", "Select output folder")
            return
            
        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.progress_label.config(text="Initializing Scanner...")
        
        # Run in thread to keep UI alive
        threading.Thread(target=self.process_pdf_thread, args=(pdf_path, out_folder), daemon=True).start()

    def process_pdf_thread(self, pdf_path, out_folder):
        try:
            pages = PdfProcessor.pdf_to_images(pdf_path)
            total_pages = len(pages)
            id_counters = {}
            total_processed = 0
            
            for i, page_img in enumerate(pages):
                self.parent.after(0, lambda p=i+1, t=total_pages: self.page_label.config(text=f"SCANNING PAGE: {p}/{t}"))
                self.parent.after(0, lambda p=i, t=total_pages: self.progress_var.set((p/t)*100))
                self.parent.after(0, lambda p=i+1: self.progress_label.config(text=f"Processing Page {p}..."))
                
                # Visual callback wrapper to ensure it runs in main thread
                def v_callback(num, head, crops):
                    self.parent.after(0, lambda: self.update_visuals(num, head, crops))
                
                sub_results = ImageProcessor.extract_from_pil_image(
                    page_img, out_folder, None, v_callback, id_counters
                )
                total_processed += sub_results['processed']
                time.sleep(0.5) # Time for user to see the "cool visuals"
                
            self.parent.after(0, lambda: self.on_finish(total_pages, total_processed, len(id_counters), out_folder))
            
        except Exception as e:
            self.parent.after(0, lambda e=e: messagebox.showerror("Process Error", str(e)))
            self.parent.after(0, self.reset_ui)

    def on_finish(self, pages, count, candidates, out_folder):
        self.progress_var.set(100)
        self.progress_label.config(text="SCAN COMPLETE")
        
        # Show results in requested format
        main_folder_name = Path(out_folder).name
        message = f"Total Candidates in Batch '{main_folder_name}': {candidates}"
        
        # Add summary info
        message += f"\n\nTotal pages processed: {pages}"
        message += f"\nTotal images extracted: {count}"
        
        messagebox.showinfo("Extraction Success", message)
        self.reset_ui()
        
    def reset_ui(self):
        self.is_processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.scan_line_y = 0
        self.canvas.delete("all")

    def show(self):
        self.frame.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        self.frame.pack_forget()

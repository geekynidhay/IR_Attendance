"""
Image Splitter Mode for IR Attendance application
Allows user to set split position and crop area, then batch process images
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from pathlib import Path
from config import config
from image_processor import ImageProcessor

from footer import Footer

class SplitterMode:
    """Image Splitter Mode UI and logic"""
    
    def __init__(self, parent, on_back_callback):
        self.parent = parent
        self.on_back_callback = on_back_callback
        self.frame = ttk.Frame(parent)
        
        # State variables
        self.sample_image_path = None
        self.original_image = None
        self.display_image = None
        self.canvas_image = None
        self.split_line = None
        self.split_position_percent = config.get('split_position_percent', 50)
        self.tk_images = []
        
        # Crop rectangle handles
        self.crop_rect = None
        self.crop_handles = []
        self.crop_enabled = config.get('crop_settings', {}).get('enabled', False)
        self.crop_coords = {  # Percentages
            'left': 0,
            'top': 0,
            'right': 100,
            'bottom': 100
        }
        
        # Dragging state
        self.dragging_split = False
        self.dragging_handle = None
        
        self.create_ui()
    
    def create_ui(self):
        """Create the splitter mode UI"""
        # Main container with footer
        self.content_container = ttk.Frame(self.frame)
        self.content_container.pack(fill=tk.BOTH, expand=True)
        
        # Footer
        self.footer = Footer(self.frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Header
        header_frame = ttk.Frame(self.content_container)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        ttk.Label(header_frame, text="JPG Splitter", 
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="← Back to Menu", 
                  command=self.on_back_callback).pack(side=tk.RIGHT)
        
        # --- BOTTOM SECTION (Batch Process) ---
        # Pack this first (with side=BOTTOM) so it stays at the bottom
        batch_frame = ttk.LabelFrame(self.content_container, text="Step 3: Batch Process", padding=5)
        batch_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        # Raw data folder
        raw_frame = ttk.Frame(batch_frame)
        raw_frame.pack(fill=tk.X, pady=2)
        ttk.Label(raw_frame, text="Raw Data Folder:").pack(side=tk.LEFT)
        self.raw_folder_var = tk.StringVar(value=config.get('last_raw_data_path', ''))
        ttk.Entry(raw_frame, textvariable=self.raw_folder_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(raw_frame, text="Browse", command=self.browse_raw_folder).pack(side=tk.LEFT)
        
        # Output folder
        output_frame = ttk.Frame(batch_frame)
        output_frame.pack(fill=tk.X, pady=2)
        ttk.Label(output_frame, text="Output Folder:").pack(side=tk.LEFT, padx=(0, 18))
        self.output_folder_var = tk.StringVar(value=config.get('last_batch_path', ''))
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_folder).pack(side=tk.LEFT)
        
        # Process button
        process_frame = ttk.Frame(batch_frame)
        process_frame.pack(fill=tk.X, pady=5)
        ttk.Button(process_frame, text="Process All Images", 
                  command=self.process_batch, style='Accent.TButton').pack()
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(batch_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(batch_frame, text="")
        self.progress_label.pack()

        # --- TOP SECTION (Instructions & Settings) ---
        # Instructions
        instructions = "Instructions: 1. Select Sample Image 2. Drag red split line 3. Set Crop (optional) 4. Process Batch"
        
        inst_frame = ttk.Frame(self.content_container)
        inst_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))
        ttk.Label(inst_frame, text=instructions, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Sample image selection
        sample_frame = ttk.LabelFrame(self.content_container, text="Step 1: Select Sample Image", padding=5)
        sample_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        ttk.Button(sample_frame, text="Browse Sample Image", 
                  command=self.load_sample_image).pack(side=tk.LEFT, padx=5)
        
        self.sample_label = ttk.Label(sample_frame, text="No image selected")
        self.sample_label.pack(side=tk.LEFT, padx=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.content_container, text="Step 2: Adjust Settings", padding=5)
        settings_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Split position
        split_frame = ttk.Frame(settings_frame)
        split_frame.pack(fill=tk.X, pady=2)
        ttk.Label(split_frame, text="Split Position:").pack(side=tk.LEFT)
        self.split_label = ttk.Label(split_frame, text=f"{self.split_position_percent}%")
        self.split_label.pack(side=tk.LEFT, padx=5)
        ttk.Label(split_frame, text="(Drag red line)").pack(side=tk.LEFT, padx=5)
        
        # Crop checkbox
        self.crop_var = tk.BooleanVar(value=self.crop_enabled)
        crop_check = ttk.Checkbutton(settings_frame, text="Enable Crop", 
                                     variable=self.crop_var, command=self.toggle_crop)
        crop_check.pack(side=tk.LEFT, padx=20)
        
        # --- MIDDLE SECTION (Canvas) ---
        # Canvas for image display
        # Pack this LAST with expand=True. It will take remaining space.
        canvas_frame = ttk.LabelFrame(self.content_container, text="Preview & Edit", padding=5)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
    
    def load_sample_image(self):
        """Load a sample image to set split position and crop"""
        file_path = filedialog.askopenfilename(
            title="Select Sample Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        
        if file_path:
            try:
                self.sample_image_path = file_path
                self.original_image = Image.open(file_path)
                self.sample_label.config(text=Path(file_path).name)
                self.display_sample_image()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")
    
    def display_sample_image(self):
        """Display the sample image on the canvas with split line and crop rectangle"""
        if not self.original_image:
            return
        
        # Get canvas size
        self.canvas.update()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Resize image to fit canvas while maintaining aspect ratio
        img_width, img_height = self.original_image.size
        scale = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        self.display_image = self.original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.canvas_image = ImageTk.PhotoImage(self.display_image)
        
        # Clear canvas
        self.canvas.delete('all')
        
        # Display image centered
        x = (canvas_width - new_width) // 2
        y = (canvas_height - new_height) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.canvas_image, tags='image')
        
        # Store image position for later calculations
        self.image_x = x
        self.image_y = y
        self.image_width = new_width
        self.image_height = new_height
        
        # Draw split line
        split_x = x + int(new_width * self.split_position_percent / 100)
        self.split_line = self.canvas.create_line(
            split_x, y, split_x, y + new_height,
            fill='red', width=3, tags='split_line'
        )
        
        # Draw crop rectangle if enabled
        if self.crop_var.get():
            self.draw_crop_rectangle()
    
    def draw_crop_rectangle(self):
        """Draw the crop rectangle with draggable corners"""
        if not self.display_image:
            return
        
        # Delete existing crop elements
        self.canvas.delete('crop')
        self.crop_handles = []
        
        # Calculate crop rectangle position
        left = self.image_x + int(self.image_width * self.crop_coords['left'] / 100)
        top = self.image_y + int(self.image_height * self.crop_coords['top'] / 100)
        right = self.image_x + int(self.image_width * self.crop_coords['right'] / 100)
        bottom = self.image_y + int(self.image_height * self.crop_coords['bottom'] / 100)
        
        # Draw rectangle
        self.crop_rect = self.canvas.create_rectangle(
            left, top, right, bottom,
            outline='green', width=2, tags='crop'
        )
        
        # Draw corner handles
        handle_size = 8
        corners = [
            (left, top, 'nw'),
            (right, top, 'ne'),
            (left, bottom, 'sw'),
            (right, bottom, 'se')
        ]
        
        for x, y, corner_id in corners:
            handle = self.canvas.create_rectangle(
                x - handle_size, y - handle_size,
                x + handle_size, y + handle_size,
                fill='green', outline='white', tags=('crop', f'handle_{corner_id}')
            )
            self.crop_handles.append((handle, corner_id))
    
    def toggle_crop(self):
        """Toggle crop rectangle visibility"""
        if self.crop_var.get():
            self.draw_crop_rectangle()
        else:
            self.canvas.delete('crop')
    
    def on_canvas_click(self, event):
        """Handle canvas click to start dragging"""
        # Check if clicking on split line
        if self.split_line:
            coords = self.canvas.coords(self.split_line)
            if abs(event.x - coords[0]) < 10:  # Within 10 pixels of the line
                self.dragging_split = True
                return
        
        # Check if clicking on a crop handle
        if self.crop_var.get():
            for handle, corner_id in self.crop_handles:
                coords = self.canvas.coords(handle)
                if (coords[0] <= event.x <= coords[2] and 
                    coords[1] <= event.y <= coords[3]):
                    self.dragging_handle = corner_id
                    return
    
    def on_canvas_drag(self, event):
        """Handle canvas drag for split line or crop handles"""
        if self.dragging_split:
            # Constrain to image bounds
            new_x = max(self.image_x, min(event.x, self.image_x + self.image_width))
            
            # Update split line position
            self.canvas.coords(self.split_line, 
                             new_x, self.image_y, 
                             new_x, self.image_y + self.image_height)
            
            # Update split position percentage
            self.split_position_percent = int(((new_x - self.image_x) / self.image_width) * 100)
            self.split_label.config(text=f"{self.split_position_percent}%")
        
        elif self.dragging_handle:
            # Constrain to image bounds
            new_x = max(self.image_x, min(event.x, self.image_x + self.image_width))
            new_y = max(self.image_y, min(event.y, self.image_y + self.image_height))
            
            # Calculate percentage
            x_percent = ((new_x - self.image_x) / self.image_width) * 100
            y_percent = ((new_y - self.image_y) / self.image_height) * 100
            
            # Update crop coordinates based on which handle is being dragged
            if 'n' in self.dragging_handle:
                self.crop_coords['top'] = min(y_percent, self.crop_coords['bottom'] - 5)
            if 's' in self.dragging_handle:
                self.crop_coords['bottom'] = max(y_percent, self.crop_coords['top'] + 5)
            if 'w' in self.dragging_handle:
                self.crop_coords['left'] = min(x_percent, self.crop_coords['right'] - 5)
            if 'e' in self.dragging_handle:
                self.crop_coords['right'] = max(x_percent, self.crop_coords['left'] + 5)
            
            # Redraw crop rectangle
            self.draw_crop_rectangle()
    
    def on_canvas_release(self, event):
        """Handle mouse release to stop dragging"""
        self.dragging_split = False
        self.dragging_handle = None
    
    def browse_raw_folder(self):
        """Browse for raw data folder"""
        folder = filedialog.askdirectory(title="Select Raw Data Folder")
        if folder:
            self.raw_folder_var.set(folder)
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder_var.set(folder)
    
    def process_batch(self):
        """Process all images in the raw data folder"""
        raw_folder = self.raw_folder_var.get()
        output_folder = self.output_folder_var.get()
        
        if not raw_folder or not Path(raw_folder).exists():
            messagebox.showerror("Error", "Please select a valid Raw Data folder")
            return
        
        if not output_folder:
            messagebox.showerror("Error", "Please select an Output folder")
            return
        
        # Save paths to config
        config.set('last_raw_data_path', raw_folder)
        config.set('last_batch_path', output_folder)
        config.set('split_position_percent', self.split_position_percent)
        
        # Save crop settings
        crop_settings = {
            'enabled': self.crop_var.get(),
            'left': self.crop_coords['left'],
            'top': self.crop_coords['top'],
            'right': self.crop_coords['right'],
            'bottom': self.crop_coords['bottom']
        }
        config.set('crop_settings', crop_settings)
        
        # Progress callback
        def update_progress(current, total, message):
            progress = (current / total * 100) if total > 0 else 0
            self.progress_var.set(progress)
            self.progress_label.config(text=message)
            self.frame.update_idletasks()
        
        # Process images
        results = ImageProcessor.batch_split_images(
            raw_folder, output_folder, self.split_position_percent,
            crop_settings if crop_settings['enabled'] else None,
            update_progress, self.update_visuals
        )
        
        # Show results in requested format
        main_folder_name = Path(output_folder).name
        message = f"Total Candidates in Batch '{main_folder_name}': {results['candidates']}"
        
        if results['errors']:
            message += f"\n\nNote: {results['processed']} images processed successfully."
            message += f"\nErrors occurred in {len(results['errors'])} files."
        
        messagebox.showinfo("Batch Processing Complete", message)

    def update_visuals(self, folder_name, left_img, right_img):
        """Update live preview canvas with current split components"""
        self.canvas.delete("all")
        self.tk_images = []
        
        c_w = self.canvas.winfo_width()
        c_h = self.canvas.winfo_height()
        
        if c_w < 100 or c_h < 100:
            return
            
        # Draw header text
        self.canvas.create_text(c_w // 2, 20, text=f"Processing: {folder_name}", fill="#ffffff", font=('Arial', 14, 'bold'))
        
        target_w = (c_w // 2) - 20
        target_h = c_h - 60
        
        # Draw left image
        if left_img:
            lw, lh = left_img.size
            if lw > 0 and lh > 0:
                scale_l = min(target_w / lw, target_h / lh)
                nlw, nlh = max(1, int(lw * scale_l)), max(1, int(lh * scale_l))
                l_disp = left_img.resize((nlw, nlh), Image.Resampling.LANCZOS)
                tk_l = ImageTk.PhotoImage(l_disp)
                self.tk_images.append(tk_l)
                
                cx = c_w // 4
                cy = (c_h // 2) + 10
                self.canvas.create_image(cx, cy, image=tk_l, anchor=tk.CENTER)
                self.canvas.create_rectangle(cx-(nlw//2)-2, cy-(nlh//2)-2, cx+(nlw//2)+2, cy+(nlh//2)+2, outline='#00ff00', width=2)
                
        # Draw right image
        if right_img:
            rw, rh = right_img.size
            if rw > 0 and rh > 0:
                scale_r = min(target_w / rw, target_h / rh)
                nrw, nrh = max(1, int(rw * scale_r)), max(1, int(rh * scale_r))
                r_disp = right_img.resize((nrw, nrh), Image.Resampling.LANCZOS)
                tk_r = ImageTk.PhotoImage(r_disp)
                self.tk_images.append(tk_r)
                
                cx = 3 * c_w // 4
                cy = (c_h // 2) + 10
                self.canvas.create_image(cx, cy, image=tk_r, anchor=tk.CENTER)
                self.canvas.create_rectangle(cx-(nrw//2)-2, cy-(nrh//2)-2, cx+(nrw//2)+2, cy+(nrh//2)+2, outline='#00ff00', width=2)
                
        self.frame.update()
    
    def show(self):
        """Show the splitter mode frame"""
        self.frame.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        """Hide the splitter mode frame"""
        self.frame.pack_forget()

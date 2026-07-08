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
        self.extracted_dir = None
        self.selected_dir_path = None
        
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
        
        # Auto-extract and load last Zip file if exists
        saved_zip = config.get('last_zip_file_path', '')
        if saved_zip and Path(saved_zip).exists():
            self.parent.after(100, lambda: self.load_and_extract_zip(saved_zip))
    
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
        
        # Input Archive file
        zip_frame = ttk.Frame(batch_frame)
        zip_frame.pack(fill=tk.X, pady=2)
        ttk.Label(zip_frame, text="Input Archive:").pack(side=tk.LEFT, padx=(0, 20))
        self.zip_file_var = tk.StringVar(value=config.get('last_zip_file_path', ''))
        ttk.Entry(zip_frame, textvariable=self.zip_file_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(zip_frame, text="Browse", command=self.browse_zip_file).pack(side=tk.LEFT)
        
        # Output folder
        output_frame = ttk.Frame(batch_frame)
        output_frame.pack(fill=tk.X, pady=2)
        ttk.Label(output_frame, text="Output Folder:").pack(side=tk.LEFT, padx=(0, 18))
        self.output_folder_var = tk.StringVar(value=config.get('last_batch_path', ''))
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_folder).pack(side=tk.LEFT)
        
        # Timing Configuration
        timing_frame = ttk.LabelFrame(batch_frame, text="Timing Configuration", padding=5)
        timing_frame.pack(fill=tk.X, pady=5)
        
        self.timing_mode_var = tk.StringVar(value=config.get('last_timing_mode', 'string'))
        
        # Option 1: String Parsing
        str_radio = ttk.Radiobutton(timing_frame, text="Parse Timing String", variable=self.timing_mode_var, value="string", command=self.toggle_timing_fields)
        str_radio.grid(row=0, column=0, sticky=tk.W, pady=2)
        
        self.timing_str_var = tk.StringVar(value=config.get('last_timing_str', 'Batch Timings - 13:30:00-19:30:00'))
        self.timing_str_entry = ttk.Entry(timing_frame, textvariable=self.timing_str_var, width=40)
        self.timing_str_entry.grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5, pady=2)
        
        # Option 2: Manual Entry
        manual_radio = ttk.Radiobutton(timing_frame, text="Manual Time Entry", variable=self.timing_mode_var, value="manual", command=self.toggle_timing_fields)
        manual_radio.grid(row=1, column=0, sticky=tk.W, pady=2)
        
        ttk.Label(timing_frame, text="Start (HH:MM):").grid(row=1, column=1, sticky=tk.W, padx=(5, 2), pady=2)
        self.start_time_var = tk.StringVar(value=config.get('last_start_time', '13:30'))
        self.start_time_entry = ttk.Entry(timing_frame, textvariable=self.start_time_var, width=8)
        self.start_time_entry.grid(row=1, column=2, sticky=tk.W, padx=2, pady=2)
        
        ttk.Label(timing_frame, text="End (HH:MM):").grid(row=1, column=3, sticky=tk.W, padx=(10, 2), pady=2)
        self.end_time_var = tk.StringVar(value=config.get('last_end_time', '19:30'))
        self.end_time_entry = ttk.Entry(timing_frame, textvariable=self.end_time_var, width=8)
        self.end_time_entry.grid(row=1, column=4, sticky=tk.W, padx=2, pady=2)
        
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
        
        self.toggle_timing_fields()
 
        # --- TOP SECTION (Instructions & Settings) ---
        # Instructions
        instructions = "Instructions: 1. Select Input Archive (zip/rar/7z/tar) 2. Click an image in the Directory tree as reference 3. Drag red split line & Set Crop (optional) 4. Process Batch"
        
        inst_frame = ttk.Frame(self.content_container)
        inst_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))
        ttk.Label(inst_frame, text=instructions, font=('Arial', 9)).pack(anchor=tk.W)
        
        # Reference image selection info
        sample_frame = ttk.LabelFrame(self.content_container, text="Step 1: Reference Image Information", padding=5)
        sample_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        self.sample_label = ttk.Label(sample_frame, text="Select an archive file first, then click an image from the directory tree below.")
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
        
        # --- MIDDLE SECTION (Canvas & Treeview) ---
        middle_container = ttk.Frame(self.content_container)
        middle_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left pane: Directory Structure of Archive
        tree_frame = ttk.LabelFrame(middle_container, text="Archive Directory", padding=5, width=280)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        tree_frame.pack_propagate(False)
        
        self.zip_tree = ttk.Treeview(tree_frame, selectmode='browse')
        self.zip_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.zip_tree.yview)
        self.zip_tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.zip_tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        # Right pane: Canvas for preview/editing
        canvas_frame = ttk.LabelFrame(middle_container, text="Preview & Edit", padding=5)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_release)
    
    def browse_zip_file(self):
        """Browse for input archive file (zip, rar, 7z, tar, etc.) and extract it"""
        file_path = filedialog.askopenfilename(
            title="Select Input Archive File",
            filetypes=[
                ("Archive files", "*.zip *.rar *.7z *.tar *.gz *.tgz *.bz2 *.xz"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.zip_file_var.set(file_path)
            self.load_and_extract_zip(file_path)

    def extract_archive(self, archive_path, dest_dir):
        """Generic extractor supporting zip, rar, 7z, and tar formats"""
        import shutil
        import os
        from pathlib import Path
        
        archive_path = Path(archive_path)
        dest_dir = Path(dest_dir)
        suffix = archive_path.suffix.lower()
        
        if suffix == '.zip':
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    filename = member.filename
                    if '..' in filename or filename.startswith('/'):
                        continue
                    target_path = dest_dir / filename
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zip_ref.open(member) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                            
        elif suffix == '.7z':
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode='r') as sz_ref:
                sz_ref.extractall(path=str(dest_dir))
                
        elif suffix == '.rar':
            import rarfile
            try:
                with rarfile.RarFile(archive_path) as rf:
                    rf.extractall(path=str(dest_dir))
            except Exception as rar_err:
                print(f"rarfile library failed, attempting fallback: {rar_err}")
                # Fallback to macOS native tar command (bsdtar) which supports RAR extraction
                import subprocess
                try:
                    subprocess.run(['tar', '-xf', str(archive_path), '-C', str(dest_dir)], check=True)
                except Exception as fb_err:
                    raise Exception(f"Failed to extract RAR file. Please ensure unrar command-line tool is installed. (Lib error: {rar_err}, Tar error: {fb_err})")
                    
        elif suffix in ['.tar', '.gz', '.tgz', '.bz2', '.tbz', '.xz', '.txz']:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                for member in tar_ref.getmembers():
                    if '..' in member.name or member.name.startswith('/'):
                        continue
                    tar_ref.extract(member, path=str(dest_dir))
                    
        else:
            # Fallback to shutil
            shutil.unpack_archive(str(archive_path), str(dest_dir))

    def load_and_extract_zip(self, zip_path):
        """Extract archive contents to a temp folder and populate the tree"""
        import shutil
        
        zip_path = Path(zip_path)
        zip_name = zip_path.stem
        
        # Define extraction target directory inside the workspace
        workspace_dir = Path(__file__).parent.parent
        self.extracted_dir = workspace_dir / "temp_zip_extracted" / zip_name
        
        # Clear existing extracted files for this archive to be clean
        if self.extracted_dir.exists():
            try:
                shutil.rmtree(self.extracted_dir)
            except Exception as e:
                print(f"Error removing existing extracted dir: {e}")
                
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract files
        try:
            self.extract_archive(zip_path, self.extracted_dir)
                            
            # Clear Treeview
            for item in self.zip_tree.get_children():
                self.zip_tree.delete(item)
                
            # Populate Treeview
            self.populate_tree('', self.extracted_dir)
            
            # Select first file if any
            self.select_first_image_in_tree()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract archive: {e}")

    def populate_tree(self, parent_id, path):
        """Recursively populate the directory tree with folders and image files"""
        try:
            for p in sorted(path.iterdir()):
                if p.is_dir():
                    folder_id = self.zip_tree.insert(parent_id, 'end', text=p.name, open=True, values=(str(p), 'dir'))
                    self.populate_tree(folder_id, p)
                elif p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}:
                    self.zip_tree.insert(parent_id, 'end', text=p.name, values=(str(p), 'file'))
        except Exception as e:
            print(f"Error populating tree: {e}")

    def select_first_image_in_tree(self):
        """Find and select the first image file in the Treeview"""
        def search_item(item_id):
            values = self.zip_tree.item(item_id, 'values')
            if values and values[1] == 'file':
                self.zip_tree.selection_set(item_id)
                self.zip_tree.see(item_id)
                return True
            for child in self.zip_tree.get_children(item_id):
                if search_item(child):
                    return True
            return False
            
        for item in self.zip_tree.get_children(''):
            if search_item(item):
                break

    def on_tree_select(self, event):
        """Handle image or folder selection from directory tree"""
        selected_items = self.zip_tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        values = self.zip_tree.item(item_id, 'values')
        if values:
            path_str = values[0]
            path_type = values[1]
            if path_type == 'file':
                self.selected_dir_path = Path(path_str).parent
                try:
                    self.sample_image_path = path_str
                    self.original_image = Image.open(path_str)
                    self.sample_label.config(text=f"Selected Reference: {Path(path_str).name} (Folder: {self.selected_dir_path.name})")
                    self.display_sample_image()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load image: {e}")
            elif path_type == 'dir':
                self.selected_dir_path = Path(path_str)
                self.sample_label.config(text=f"Selected Folder: {self.selected_dir_path.name} (Select an image inside for preview)")
    
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
            if coords and len(coords) > 0 and abs(event.x - coords[0]) < 10:  # Within 10 pixels of the line
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
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder_var.set(folder)
    
    def process_batch(self):
        """Process all images in the extracted zip directory"""
        import re
        
        zip_file = self.zip_file_var.get()
        output_folder = self.output_folder_var.get()
        
        if not zip_file or not Path(zip_file).exists():
            messagebox.showerror("Error", "Please select a valid Input Archive File")
            return
            
        if not self.extracted_dir or not self.extracted_dir.exists():
            messagebox.showerror("Error", "No extracted data found. Please select/re-load a valid Archive.")
            return
        
        if not output_folder:
            messagebox.showerror("Error", "Please select an Output folder")
            return
            
        # Determine raw folder to process based on active Treeview selection
        target_process_dir = self.selected_dir_path if self.selected_dir_path else self.extracted_dir
        if not target_process_dir or not Path(target_process_dir).exists():
            messagebox.showerror("Error", "No valid folder selected in the tree view.")
            return
            
        # Determine start/end timings
        start_time = ""
        end_time = ""
        mode = self.timing_mode_var.get()
        
        if mode == "string":
            timing_str = self.timing_str_var.get().strip()
            # Match HH:MM or HH:MM:SS separated by a dash
            match = re.search(r'(\d{1,2}:\d{2})(?::\d{2})?\s*-\s*(\d{1,2}:\d{2})(?::\d{2})?', timing_str)
            if not match:
                messagebox.showerror("Error", "Invalid timing string format.\nExpected format like: 'Batch Timings - 13:30:00-19:30:00'")
                return
            start_time = match.group(1)
            end_time = match.group(2)
        else:
            start_time = self.start_time_var.get().strip()
            end_time = self.end_time_var.get().strip()
            
            time_pattern = r'^\d{1,2}:\d{2}$'
            if not re.match(time_pattern, start_time) or not re.match(time_pattern, end_time):
                messagebox.showerror("Error", "Manual times must be in HH:MM format (e.g., 13:30).")
                return
                
        # Normalize to HH:MM format
        def normalize_time(t):
            parts = t.split(':')
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            
        try:
            start_time = normalize_time(start_time)
            end_time = normalize_time(end_time)
        except Exception:
            messagebox.showerror("Error", "Failed to parse timings. Please verify HH:MM format.")
            return
            
        # Determine target subfolder named after Zip and timings: {Zip Name} - Start Time To End Time (using HH.MM with dot format)
        # Note: If this output base folder already exists, new items will merge/save into it without creating a new folder
        zip_name = Path(zip_file).stem
        start_time_formatted = start_time.replace(':', '.')
        end_time_formatted = end_time.replace(':', '.')
        output_folder_name = f"{zip_name} - {start_time_formatted} To {end_time_formatted}"
        output_base_folder = Path(output_folder) / output_folder_name
        output_base_folder.mkdir(parents=True, exist_ok=True)
        
        # Save paths and timing settings to config
        config.set('last_zip_file_path', zip_file)
        config.set('last_batch_path', output_folder)
        config.set('split_position_percent', self.split_position_percent)
        config.set('last_timing_mode', mode)
        config.set('last_timing_str', self.timing_str_var.get())
        config.set('last_start_time', start_time)
        config.set('last_end_time', end_time)
        
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
        
        # Process images from target_process_dir only
        results = ImageProcessor.batch_split_images(
            str(target_process_dir), str(output_base_folder), self.split_position_percent,
            crop_settings if crop_settings['enabled'] else None,
            update_progress, self.update_visuals
        )
        
        # Show results in requested format
        message = f"Total Candidates in Batch '{zip_name}': {results['candidates']}"
        
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
    
    def toggle_timing_fields(self):
        """Enable/disable input fields based on selected timing mode"""
        mode = self.timing_mode_var.get()
        if mode == "string":
            self.timing_str_entry.config(state='normal')
            self.start_time_entry.config(state='disabled')
            self.end_time_entry.config(state='disabled')
        else:
            self.timing_str_entry.config(state='disabled')
            self.start_time_entry.config(state='normal')
            self.end_time_entry.config(state='normal')

    def show(self):
        """Show the splitter mode frame"""
        self.frame.pack(fill=tk.BOTH, expand=True)
    
    def hide(self):
        """Hide the splitter mode frame"""
        self.frame.pack_forget()

"""
Image Controls for Image Viewer Mode
Handles brightness and zoom adjustments
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageEnhance
import io
from encryption_utils import EncryptionUtils

class ImageControls:
    """Custom control widget with slider and +/- buttons"""
    
    def __init__(self, parent, label, min_val, max_val, default_val, on_change=None):
        self.frame = ttk.Frame(parent)
        self.min_val = min_val
        self.max_val = max_val
        self.value = default_val
        self.on_change = on_change
        
        # Label
        ttk.Label(self.frame, text=label).pack(side=tk.LEFT, padx=5)
        
        # Minus button
        self.minus_btn = ttk.Button(self.frame, text="-", width=3, 
                                    command=self.decrease)
        self.minus_btn.pack(side=tk.LEFT, padx=2)
        
        # Slider
        self.slider_var = tk.IntVar(value=default_val)
        self.slider = ttk.Scale(self.frame, from_=min_val, to=max_val, 
                               orient=tk.HORIZONTAL, variable=self.slider_var,
                               command=self.on_slider_change)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Plus button
        self.plus_btn = ttk.Button(self.frame, text="+", width=3,
                                   command=self.increase)
        self.plus_btn.pack(side=tk.LEFT, padx=2)
        
        # Value label
        self.value_label = ttk.Label(self.frame, text=f"{default_val}%", width=6)
        self.value_label.pack(side=tk.LEFT, padx=5)
    
    def decrease(self):
        """Decrease value by 1"""
        new_value = max(self.min_val, self.value - 1)
        self.set_value(new_value)
    
    def increase(self):
        """Increase value by 1"""
        new_value = min(self.max_val, self.value + 1)
        self.set_value(new_value)
    
    def on_slider_change(self, value):
        """Handle slider value change"""
        new_value = int(float(value))
        self.set_value(new_value)
    
    def set_value(self, value):
        """Set the value and trigger callback"""
        self.value = value
        self.slider_var.set(value)
        self.value_label.config(text=f"{value}%")
        
        if self.on_change:
            self.on_change(value)
    
    def get_value(self):
        """Get current value"""
        return self.value
    
    def pack(self, **kwargs):
        """Pack the control frame"""
        self.frame.pack(**kwargs)


class ImageDisplay:
    """Handles image display with brightness and zoom controls"""
    
    def __init__(self, canvas, preview_label, on_view_change=None, encryption_key=None):
        self.canvas = canvas
        self.preview_label = preview_label 
        self.on_view_change = on_view_change # Callback for server updates
        self.encryption_key = encryption_key
        
        self.original_image = None
        self.processed_image = None
        self.display_image = None
        self.canvas_image = None
        self.photo_image = None
        
        self.brightness = 100
        self.zoom = 100
        
        # Panning State
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Resize State
        self.last_canvas_width = 0
        self.last_canvas_height = 0
        
        # Canvas image ID
        self.canvas_image_id = None
        
        # Bind Mouse Events for Panning
        self.canvas.bind('<ButtonPress-1>', self.start_pan)
        self.canvas.bind('<B1-Motion>', self.pan_image)
        self.canvas.bind('<ButtonRelease-1>', self.end_pan) # Update on release
        self.canvas.bind('<Configure>', self.on_canvas_resize)
    
    def on_canvas_resize(self, event):
        if abs(self.last_canvas_width - event.width) > 5 or abs(self.last_canvas_height - event.height) > 5:
            self.last_canvas_width = event.width
            self.last_canvas_height = event.height
            if self.original_image:
                self.update_display()
                
    def start_pan(self, event):
        """Record start position for dragging"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        
    def pan_image(self, event):
        """Move the image based on drag"""
        if not self.canvas_image_id:
            return
            
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        
        # Update offsets
        self.pan_offset_x += dx
        self.pan_offset_y += dy
        
        # Move image
        self.canvas.move(self.canvas_image_id, dx, dy)
        
        # Update start position for smooth dragging
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def end_pan(self, event):
        """Called when panning finishes"""
        if self.on_view_change:
            self.on_view_change()
    
    def load_image(self, image_path, brightness=100, zoom=100):
        """Load and display an image with brightness and zoom"""
        try:
            if EncryptionUtils.is_encrypted(image_path):
                if not self.encryption_key:
                    print("Cannot load encrypted image: No key provided")
                    return False
                
                decrypted_data = EncryptionUtils.decrypt_to_bytes(image_path, self.encryption_key.encode())
                if not decrypted_data:
                    return False
                self.original_image = Image.open(io.BytesIO(decrypted_data))
            else:
                self.original_image = Image.open(image_path)
                
            self.brightness = brightness
            self.zoom = zoom
            self.pan_offset_x = 0 # Reset pan on new image
            self.pan_offset_y = 0
            
            # Apply adjustments and display
            self.update_display()
            
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def update_display(self):
        """Update the main image display with current brightness and zoom"""
        if not self.original_image:
            return
        
        # Apply brightness
        self.processed_image = self.apply_brightness(self.original_image, self.brightness)
        
        # Get canvas size
        self.canvas.update_idletasks() # Ensure dimensions are up to date
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        img_width, img_height = self.processed_image.size
        
        # Fit to screen logic
        if canvas_width > 10 and canvas_height > 10:
            width_ratio = canvas_width / float(img_width)
            height_ratio = canvas_height / float(img_height)
            fit_ratio = min(width_ratio, height_ratio) * 0.95 # 5% margin for a compact look
        else:
            fit_ratio = 1.0
            
        zoom_factor = fit_ratio * (self.zoom / 100.0)
        
        new_width = max(1, int(img_width * zoom_factor))
        new_height = max(1, int(img_height * zoom_factor))
        
        self.display_image = self.processed_image.resize((new_width, new_height), 
                                                        Image.Resampling.LANCZOS)
        
        # Create PhotoImage
        self.photo_image = ImageTk.PhotoImage(self.display_image)
        
        # Clear canvas but keep background
        self.canvas.delete('all')
        
        # Display image centered + offset
        x = (canvas_width // 2) + self.pan_offset_x
        y = (canvas_height // 2) + self.pan_offset_y
        
        self.canvas_image_id = self.canvas.create_image(x, y, anchor=tk.CENTER, 
                                                       image=self.photo_image)
        
        if self.on_view_change:
            self.on_view_change()

    def update_subfolder_label(self, text):
        """Update the label that replaced the preview"""
        if self.preview_label:
            self.preview_label.config(text=text, image='', font=('Arial', 14, 'bold'))

    def apply_brightness(self, image, brightness_percent):
        """Apply brightness adjustment to an image"""
        if brightness_percent == 100:
            return image
        
        try:
            enhancer = ImageEnhance.Brightness(image)
            # Apply quadratic mapping: UI 100->1.0, UI 101->1.02, UI 200->4.0
            factor = (brightness_percent / 100.0) ** 2
            return enhancer.enhance(factor)
        except Exception as e:
            print(f"Error applying brightness: {e}")
            return image
    
    def set_brightness(self, brightness):
        """Set brightness and update display"""
        self.brightness = brightness
        self.update_display()
    
    def set_zoom(self, zoom):
        """Set zoom and update display (constrained between 5% and 2000%)"""
        self.zoom = max(5, min(2000, zoom))
        self.update_display()
    
    def clear(self):
        """Clear the display"""
        self.canvas.delete('all')
        self.update_subfolder_label("No Subfolder")
        self.original_image = None
        self.processed_image = None
        self.display_image = None
        self.canvas_image = None
        self.photo_image = None
        # Reset server image too?
        if self.on_view_change:
            self.on_view_change()

    @property
    def current_image(self):
        """Get the current processed PIL image"""
        return self.processed_image

    def get_visible_image(self):
        """Returns the portion of the image currently visible on the canvas"""
        if not self.display_image:
            return None

        # Canvas Dimensions
        c_width = self.canvas.winfo_width()
        c_height = self.canvas.winfo_height()
        
        # Image Dimensions
        i_width, i_height = self.display_image.size
        
        # Image Center Position (where it's drawn)
        # x = (c_width // 2) + self.pan_offset_x
        # y = (c_height // 2) + self.pan_offset_y
        
        # Top-Left of Image relative to Canvas
        img_x = (c_width // 2) + self.pan_offset_x - (i_width // 2)
        img_y = (c_height // 2) + self.pan_offset_y - (i_height // 2)
        
        # Calculate Intersection (Crop Box relative to Image)
        # We want the part of image that overlaps with Canvas(0,0, c_width, c_height)
        
        # Convert Canvas Rect to Image Coords
        # Canvas(0,0) -> Image(0 - img_x, 0 - img_y)
        crop_x1 = max(0, 0 - img_x)
        crop_y1 = max(0, 0 - img_y)
        crop_x2 = min(i_width, c_width - img_x)
        crop_y2 = min(i_height, c_height - img_y)
        
        # If no overlap
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            # Return full black? or just the image? 
            # If image is off screen, return whole image? No, return None or black.
            # But let's return the display_image if logic fails, to be safe.
             return self.display_image
             
        return self.display_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))



"""
Folder Navigator for Image Viewer Mode
Handles folder tree display and navigation state
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path

class FolderNavigator:
    """Manages folder tree navigation"""
    
    def __init__(self, tree_widget, on_subfolder_change=None):
        self.tree = tree_widget
        self.on_subfolder_change = on_subfolder_change
        
        self.root_folder = None
        self.current_subfolder = None
        self.subfolders = []
        
        # Configure tree
        self.tree.configure(show='tree')
        self.tree.tag_configure('marked', foreground='red', font=('Arial', 10, 'bold'))
        self.tree.tag_configure('not_working', foreground='#777777', font=('Arial', 10, 'overstrike'))
        self.tree.tag_configure('success', foreground='green', font=('Arial', 10, 'bold'))
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
    
    def load_folder(self, folder_path, show_marked_only=False):
        """Load a folder structure into the tree"""
        self.root_folder = Path(folder_path)
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add subfolders directly to root
        self.subfolders = []
        try:
            from config import config
            import datetime
            
            # Daily reset check for success folders at midnight/loading
            today_str = datetime.date.today().isoformat()
            last_date = config.get('success_folders_date', '')
            if last_date != today_str:
                config.set('success_folders', [])
                config.set('success_folders_date', today_str)
                
            marked_folders = config.get('marked_folders', [])
            not_working_folders = config.get('not_working_folders', [])
            success_folders = config.get('success_folders', [])
            
            normalized_marked = [Path(p).as_posix().lower() for p in marked_folders]
            normalized_not_working = [Path(p).as_posix().lower() for p in not_working_folders]
            normalized_success = [Path(p).as_posix().lower() for p in success_folders]
            
            for subfolder in sorted(self.root_folder.iterdir()):
                if subfolder.is_dir():
                    normalized_sub = subfolder.as_posix().lower()
                    if show_marked_only and normalized_sub not in normalized_marked:
                        continue
                        
                    # Check if this folder contains images (include encrypted .ira)
                    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.ira'}
                    has_images = any(f.suffix.lower() in image_extensions 
                                   for f in subfolder.iterdir() if f.is_file())
                    
                    if has_images:
                        self.subfolders.append(subfolder)
                        tags = ['subfolder']
                        if normalized_sub in normalized_marked:
                            tags.append('marked')
                        if normalized_sub in normalized_not_working:
                            tags.append('not_working')
                        if normalized_sub in normalized_success:
                            tags.append('success')
                        self.tree.insert('', 'end', text=subfolder.name,
                                       values=(str(subfolder), 'subfolder'), tags=tuple(tags))
        except Exception as e:
            print(f"Error loading subfolders: {e}")
        
        # Select first subfolder if available
        if self.subfolders:
            children = self.tree.get_children('')
            if children:
                self.tree.selection_set(children[0])
                self.tree.see(children[0])
    
    def on_tree_select(self, event):
        """Handle tree selection change"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            values = self.tree.item(item, 'values')
            if values and values[1] == 'subfolder':
                subfolder_path = Path(values[0])
                if subfolder_path != self.current_subfolder:
                    self.current_subfolder = subfolder_path
                    if self.on_subfolder_change:
                        self.on_subfolder_change(subfolder_path)
    
    def navigate_down(self):
        """Navigate to next subfolder (Down arrow key)"""
        if not self.current_subfolder:
            # If nothing selected, select first subfolder
            children = self.tree.get_children('')
            if children:
                self.tree.selection_set(children[0])
                self.tree.see(children[0])
            return
        
        # Get current index
        try:
            current_index = self.subfolders.index(self.current_subfolder)
            if current_index < len(self.subfolders) - 1:
                # Move to next subfolder
                next_index = current_index + 1
                
                # Find and select the corresponding tree item
                children = self.tree.get_children('')
                if next_index < len(children):
                    self.tree.selection_set(children[next_index])
                    self.tree.see(children[next_index])
        except ValueError:
            pass
    
    def navigate_up(self):
        """Navigate to previous subfolder (Up arrow key)"""
        if not self.current_subfolder:
            return
        
        # Get current index
        try:
            current_index = self.subfolders.index(self.current_subfolder)
            if current_index > 0:
                # Move to previous subfolder
                prev_index = current_index - 1
                
                # Find and select the corresponding tree item
                children = self.tree.get_children('')
                if prev_index < len(children):
                    self.tree.selection_set(children[prev_index])
                    self.tree.see(children[prev_index])
        except ValueError:
            pass
    
    def get_current_subfolder_name(self):
        """Get the name of the current subfolder"""
        if self.current_subfolder:
            return self.current_subfolder.name
        return ""
    
    def get_images_in_current_subfolder(self):
        """Get list of image files in current subfolder"""
        if not self.current_subfolder:
            return []
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.ira'}
        images = []
        
        try:
            for file in sorted(self.current_subfolder.iterdir()):
                if file.is_file() and file.suffix.lower() in image_extensions:
                    images.append(file)
        except Exception as e:
            print(f"Error getting images: {e}")
        
        return images

"""
IR Attendance Admin Utility
Standalone entry point for Admin tools only (Splitter, Extraction, PDF Extraction).
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from pathlib import Path

# Add src to system path if needed
sys.path.append(str(Path(__file__).parent))

# Load PIL safely
try:
    from PIL import Image, ImageTk
except ImportError:
    print("Warning: Pillow not found. Image previews may fail.")

# Load modules
import config as cfg
config = cfg.config
import window_manager
import footer
import splitter_mode
import extractor_mode
import pdf_extractor_mode

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

class IRAdminApp:
    def __init__(self, root):
        self.root = root
        self.current_mode = None
        
        # Initialize sub-modes
        self.splitter_mode = None
        self.extractor_mode = None
        self.pdf_extractor_mode = None
        
        self.setup_style()
        self.create_menu()
        
    def setup_style(self):
        style = ttk.Style()
        
        # Apply dark theme style
        bg_color = '#121212'
        fg_color = '#E0E0E0'
        accent_color = '#00D4FF'
        card_bg = '#1E1E1E'
        
        style.configure('.', background=bg_color, foreground=fg_color)
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('Title.TLabel', font=('Segoe UI', 26, 'bold'), foreground=accent_color, background=bg_color)
        style.configure('Subtitle.TLabel', font=('Segoe UI', 11), foreground='#AAAAAA', background=bg_color)
        
        # Configure input fields (avoid white-on-white text)
        style.configure('TEntry', foreground='#000000', fieldbackground='#ffffff', insertcolor='#000000')
        style.configure('TCombobox', foreground='#000000', fieldbackground='#ffffff', insertcolor='#000000')
        style.configure('TSpinbox', foreground='#000000', fieldbackground='#ffffff', insertcolor='#000000')
        
        # Treeview style for dark theme
        style.configure('Treeview', background='#1E1E1E', foreground='#E0E0E0', fieldbackground='#1E1E1E')
        style.map('Treeview', background=[('selected', '#1976D2')], foreground=[('selected', '#FFFFFF')])
        
        style.configure('TLabelframe', background=bg_color, bordercolor='#333333')
        style.configure('TLabelframe.Label', background=bg_color, foreground=accent_color, font=('Segoe UI', 11, 'bold'))

    def create_menu(self):
        """Create clean Admin dashboard menu"""
        self.menu_frame = ttk.Frame(self.root)
        self.menu_frame.pack(fill=tk.BOTH, expand=True)
        
        center_frame = ttk.Frame(self.menu_frame)
        center_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Title
        ttk.Label(center_frame, text="IR Attendance Admin Utility", style='Title.TLabel').pack(pady=20)
        ttk.Label(center_frame, text="Select an administrative tool to begin", style='Subtitle.TLabel').pack(pady=10)
        
        # Mode buttons container
        button_frame = ttk.Frame(center_frame)
        button_frame.pack(pady=30)
        
        ModernButton(button_frame, text="JPG Splitter", 
                     command=self.open_splitter_mode,
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=28, height=2).pack(pady=10)
                     
        ModernButton(button_frame, text="JPG Extraction", 
                     command=self.open_extractor_mode,
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=28, height=2).pack(pady=10)
                     
        ModernButton(button_frame, text="PDF Extraction", 
                     command=self.open_pdf_extractor_mode,
                     bg='#1976D2', hover_bg='#1565C0', fg='white', width=28, height=2).pack(pady=10)
        
        # Instructions/Summary
        info_text = """
JPG Splitter: Split images vertically with custom crop configurations
JPG Extraction: Batch extract sub-images from JPG scan sheets
PDF Extraction: Extract images from PDF reports using Tesseract OCR
        """
        ttk.Label(center_frame, text=info_text, justify=tk.CENTER,
                 font=('Segoe UI', 9), foreground='#888888').pack(pady=20)
        
        # Footer
        self.footer = footer.Footer(self.menu_frame)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)

    def open_splitter_mode(self):
        self.menu_frame.pack_forget()
        if not self.splitter_mode:
            self.splitter_mode = splitter_mode.SplitterMode(self.root, self.return_to_menu)
        self.splitter_mode.show()
        self.current_mode = 'splitter'
        
    def open_extractor_mode(self):
        self.menu_frame.pack_forget()
        if not self.extractor_mode:
            self.extractor_mode = extractor_mode.ExtractorMode(self.root, self.return_to_menu)
        self.extractor_mode.show()
        self.current_mode = 'extractor'
        
    def open_pdf_extractor_mode(self):
        self.menu_frame.pack_forget()
        if not self.pdf_extractor_mode:
            self.pdf_extractor_mode = pdf_extractor_mode.PdfExtractorMode(self.root, self.return_to_menu)
        self.pdf_extractor_mode.show()
        self.current_mode = 'pdf_extractor'
        
    def return_to_menu(self):
        if self.current_mode == 'splitter' and self.splitter_mode:
            self.splitter_mode.hide()
        elif self.current_mode == 'extractor' and self.extractor_mode:
            self.extractor_mode.hide()
        elif self.current_mode == 'pdf_extractor' and self.pdf_extractor_mode:
            self.pdf_extractor_mode.hide()
            
        self.current_mode = None
        self.menu_frame.pack(fill=tk.BOTH, expand=True)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
        # Check if running directly inside src or root
        if not (Path(base_path) / relative_path).exists():
             parent_path = Path(base_path).parent
             if (parent_path / relative_path).exists():
                 base_path = str(parent_path)
             elif (Path(__file__).parent.parent / relative_path).exists():
                 base_path = str(Path(__file__).parent.parent)
             elif (Path(__file__).parent / relative_path).exists():
                 base_path = str(Path(__file__).parent)

    return os.path.join(base_path, relative_path)

def main():
    try:
        root = tk.Tk()
        root.title("IR Attendance Admin Utility")
        root.geometry("1200x800")
        root.configure(bg='#121212')
        
        # Set icon if exists
        icon_path = Path(resource_path("Icon.png"))
        if icon_path.exists():
            try:
                icon_img = tk.PhotoImage(file=str(icon_path))
                root.iconphoto(True, icon_img)
            except Exception:
                pass
                
        IRAdminApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

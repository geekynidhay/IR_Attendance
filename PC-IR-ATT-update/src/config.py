"""
Configuration management for IR Attendance application
"""
import json
import os
from pathlib import Path

class Config:
    """Manages application configuration and settings"""
    
    def __init__(self):
        import sys
        
        # Ensure default directory exists and is writable
        os.makedirs("C:/IR Attendance", exist_ok=True)
        
        # Store config in the guaranteed writable folder instead of Program Files
        self.base_path = Path("C:/IR Attendance")
        self.config_file = self.base_path / "config.json"
        
        self.settings = self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file"""
        default_config = {
            "last_raw_path": "",
            "last_batch_path": "C:/IR Attendance",
            "last_pdf_path": "",
            "split_pos": 50,
            "brightness": 100,
            "crop_enabled": False,
            "crop_left": 0,
            "crop_top": 0,
            "crop_right": 100,
            "crop_bottom": 100,
            "license_user": "",
            "global_default_brightness": "",
            "subfolder_settings": {}  # Store brightness/zoom per subfolder
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return default_config
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Set a configuration value and save"""
        self.settings[key] = value
        self.save_config()
    
    def get_subfolder_settings(self, subfolder_name):
        """Get brightness, zoom, and last image index for a specific subfolder"""
        subfolder_settings = self.settings.get("subfolder_settings", {})
        return subfolder_settings.get(subfolder_name, {
            "brightness": 100,
            "zoom": 100,
            "image_index": 0,
            "has_override": False
        })
    
    def set_subfolder_settings(self, subfolder_name, brightness, zoom, image_index=None, has_override=None):
        """Save brightness, zoom, and last image index for a specific subfolder"""
        if "subfolder_settings" not in self.settings:
            self.settings["subfolder_settings"] = {}
        
        existing = self.settings["subfolder_settings"].get(subfolder_name, {})
        self.settings["subfolder_settings"][subfolder_name] = {
            "brightness": brightness,
            "zoom": zoom,
            "image_index": image_index if image_index is not None else existing.get("image_index", 0),
            "has_override": has_override if has_override is not None else existing.get("has_override", False)
        }
        self.save_config()

# Global config instance
config = Config()

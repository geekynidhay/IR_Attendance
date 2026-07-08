"""
System utilities for IR Attendance application
Handles IP address, username, and internet connection checks
"""
import socket
import os
import platform
import subprocess

class SystemUtils:
    """Utilities for system information"""
    
    @staticmethod
    def get_ip_address():
        """Get local IP address"""
        try:
            # Connect to a public DNS to identify the preferred interface IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def get_username():
        """Get current system username"""
        try:
            return os.getlogin()
        except:
            return "User"
            
    @staticmethod
    def check_internet_connection():
        """Check if internet is connected"""
        try:
            # Simple ping check to Google DNS
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '8.8.8.8']
            result = subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "Connected" if result == 0 else "Disconnected"
        except:
            return "Unknown"
    
    @staticmethod
    def get_license_info():
        """Get license information"""
        # This is a placeholder as per requirements
        return "Standard License"

    @staticmethod
    def resource_path(relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        import sys
        from pathlib import Path
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            # In dev mode, if running from src, icon is in parent
            # If running from root, icon is current dir
            base_path = os.path.abspath(".")
            # Check for standard DATA_DIR first
            from config import DATA_DIR
            if os.path.exists(DATA_DIR) and relative_path in os.listdir(DATA_DIR):
                 return os.path.join(DATA_DIR, relative_path)
            # Check parent if not found in current (assuming script in src/)
            if not (Path(base_path) / relative_path).exists():
                 parent_path = Path(base_path).parent
                 if (parent_path / relative_path).exists():
                     base_path = str(parent_path)
                 # One more check if running directly inside src
                 elif (Path(__file__).parent.parent / relative_path).exists():
                     base_path = str(Path(__file__).parent.parent)

        return os.path.join(base_path, relative_path)

    @staticmethod
    def extract_archive(archive_path, dest_dir):
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

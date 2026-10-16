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

class DesktopBlackoutManager:
    """Manages hiding desktop icons and changing wallpaper for OCR accuracy on Windows"""
    _original_wallpaper = None
    _is_blackout_active = False
    _black_image_path = None

    @staticmethod
    def _get_storage_dir():
        import sys
        from pathlib import Path
        if sys.platform == "win32":
            p = Path("C:/IR Attendance")
        else:
            try:
                from config import DATA_DIR
                p = Path(DATA_DIR)
            except Exception:
                p = Path(__file__).resolve().parent.parent / "IRIS Data"
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return p

    @staticmethod
    def _get_backup_image_path():
        return DesktopBlackoutManager._get_storage_dir() / "original_wallpaper_backup.jpg"

    @staticmethod
    def _get_backup_text_path():
        return DesktopBlackoutManager._get_storage_dir() / "original_wallpaper_path.txt"

    @staticmethod
    def _get_active_flag_path():
        return DesktopBlackoutManager._get_storage_dir() / "blackout_active.flag"

    @staticmethod
    def _write_active_flag(active: bool):
        try:
            flag = DesktopBlackoutManager._get_active_flag_path()
            if active:
                with open(flag, "w", encoding="utf-8") as f:
                    f.write("active")
            else:
                if flag.exists():
                    flag.unlink(missing_ok=True)
        except Exception:
            pass

    @staticmethod
    def _find_defview():
        import sys
        if sys.platform != "win32":
            return None
        import ctypes
        user32 = ctypes.windll.user32

        # 1. Check Progman directly
        progman = user32.FindWindowW("Progman", "Program Manager")
        if not progman:
            progman = user32.FindWindowW("Progman", None)
        if progman:
            defview = user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None)
            if defview:
                return defview

        # 2. Check all WorkerW windows
        worker = user32.FindWindowExW(0, 0, "WorkerW", None)
        while worker:
            defview = user32.FindWindowExW(worker, 0, "SHELLDLL_DefView", None)
            if defview:
                return defview
            worker = user32.FindWindowExW(0, worker, "WorkerW", None)

        # 3. If not found, send 0x052C to Progman to prompt WorkerW creation, then search again
        if progman:
            try:
                res = ctypes.c_ulong()
                user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(res))
                worker = user32.FindWindowExW(0, 0, "WorkerW", None)
                while worker:
                    defview = user32.FindWindowExW(worker, 0, "SHELLDLL_DefView", None)
                    if defview:
                        return defview
                    worker = user32.FindWindowExW(0, worker, "WorkerW", None)
            except Exception:
                pass

        return None

    @staticmethod
    def are_desktop_icons_hidden():
        import sys
        if sys.platform != "win32":
            return False
        # Check Explorer registry setting
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced") as key:
                val, _ = winreg.QueryValueEx(key, "HideIcons")
                return int(val) == 1
        except Exception:
            pass

        # Check window visibility
        try:
            import ctypes
            defview = DesktopBlackoutManager._find_defview()
            if defview:
                user32 = ctypes.windll.user32
                syslist = user32.FindWindowExW(defview, 0, "SysListView32", None)
                target = syslist if syslist else defview
                return not bool(user32.IsWindowVisible(target))
        except Exception:
            pass
        return False

    @staticmethod
    def set_desktop_icons_hidden(hide: bool):
        import sys
        if sys.platform != "win32":
            return
        try:
            current_hidden = DesktopBlackoutManager.are_desktop_icons_hidden()
            if current_hidden == hide:
                return  # Already in desired state!

            defview = DesktopBlackoutManager._find_defview()
            if defview:
                import ctypes
                # 0x7402 is the toggle command
                ctypes.windll.user32.SendMessageW(defview, 0x0111, 0x7402, 0)
                
                # Update registry so Explorer's state stays in sync
                try:
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", 0, winreg.KEY_SET_VALUE) as key:
                        winreg.SetValueEx(key, "HideIcons", 0, winreg.REG_DWORD, 1 if hide else 0)
                except Exception:
                    pass
        except Exception as e:
            print(f"Failed to set desktop icons state: {e}")

    @staticmethod
    def _query_current_wallpaper():
        """Returns the current wallpaper path if it's not black and exists on disk."""
        import sys
        if sys.platform != "win32":
            return None
        import os
        import ctypes
        import winreg

        # 1. SPI_GETDESKWALLPAPER (0x0073)
        try:
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.user32.SystemParametersInfoW(0x0073, 512, buf, 0):
                path = buf.value.strip()
                if path and "ir_black_bg" not in path.lower() and os.path.isfile(path):
                    return path
        except Exception:
            pass

        # 2. Registry Control Panel\\Desktop\\Wallpaper
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
                val, _ = winreg.QueryValueEx(key, "Wallpaper")
                val = val.strip().strip('"')
                if val and "ir_black_bg" not in val.lower() and os.path.isfile(val):
                    return val
        except Exception:
            pass

        # 3. Registry TranscodedImageCache
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
                cache_data, _ = winreg.QueryValueEx(key, "TranscodedImageCache")
                if isinstance(cache_data, (bytes, bytearray)) and len(cache_data) > 24:
                    raw_str = cache_data[24:].decode('utf-16le', errors='ignore')
                    path = raw_str.split('\x00')[0].strip()
                    if path and "ir_black_bg" not in path.lower() and os.path.isfile(path):
                        return path
        except Exception:
            pass

        # 4. TranscodedWallpaper file (cached user wallpaper)
        try:
            tw = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper")
            if os.path.isfile(tw) and os.path.getsize(tw) > 1000:
                return tw
        except Exception:
            pass

        # 5. Windows default wallpaper fallback
        for candidate in [
            r"C:\Windows\Web\Wallpaper\Windows\img0.jpg",
            r"C:\Windows\Web\4K\Wallpaper\Windows\img0_1920x1080.jpg",
            r"C:\Windows\Web\4K\Wallpaper\Windows\img0_3840x2160.jpg"
        ]:
            if os.path.isfile(candidate):
                return candidate

        return None

    @staticmethod
    def _ensure_original_wallpaper_saved():
        """Saves current wallpaper path and an image copy to disk before turning black."""
        import sys
        if sys.platform != "win32":
            return
        import os
        import shutil

        backup_img = DesktopBlackoutManager._get_backup_image_path()
        backup_txt = DesktopBlackoutManager._get_backup_text_path()

        # Query what's currently active on the desktop
        current_wp = DesktopBlackoutManager._query_current_wallpaper()

        if current_wp and "ir_black_bg" not in current_wp.lower():
            # Real wallpaper found! Update in-memory and persistent backups
            DesktopBlackoutManager._original_wallpaper = current_wp
            try:
                with open(backup_txt, "w", encoding="utf-8") as f:
                    f.write(current_wp)
            except Exception:
                pass

            try:
                # Copy the file to backup_img so we have an exact persistent copy
                if os.path.isfile(current_wp):
                    shutil.copyfile(current_wp, backup_img)
            except Exception as e:
                print(f"Failed to copy original wallpaper to backup: {e}")
        else:
            # Current wallpaper is black or cannot be queried.
            # Check if we already have a saved backup on disk.
            if backup_img.exists() and backup_img.stat().st_size > 500:
                DesktopBlackoutManager._original_wallpaper = str(backup_img)
            elif backup_txt.exists():
                try:
                    with open(backup_txt, "r", encoding="utf-8") as f:
                        saved = f.read().strip()
                    if saved and "ir_black_bg" not in saved.lower() and os.path.isfile(saved):
                        DesktopBlackoutManager._original_wallpaper = saved
                        shutil.copyfile(saved, backup_img)
                except Exception:
                    pass

    @staticmethod
    def _restore_original_wallpaper():
        import sys
        if sys.platform != "win32":
            return
        import os
        import ctypes
        import shutil

        restore_candidate = None
        backup_img = DesktopBlackoutManager._get_backup_image_path()
        backup_txt = DesktopBlackoutManager._get_backup_text_path()

        # 1. In-memory path if valid and not black
        if DesktopBlackoutManager._original_wallpaper:
            p = str(DesktopBlackoutManager._original_wallpaper).strip()
            if p and "ir_black_bg" not in p.lower() and os.path.isfile(p):
                restore_candidate = p

        # 2. Dedicated backup image on disk
        if not restore_candidate and backup_img.exists() and backup_img.stat().st_size > 500:
            restore_candidate = str(backup_img)

        # 3. Path from saved text file
        if not restore_candidate and backup_txt.exists():
            try:
                with open(backup_txt, "r", encoding="utf-8") as f:
                    txt_p = f.read().strip()
                if txt_p and "ir_black_bg" not in txt_p.lower() and os.path.isfile(txt_p):
                    restore_candidate = txt_p
            except Exception:
                pass

        # 4. TranscodedWallpaper (copy with .jpg extension as user32 requires an extension)
        if not restore_candidate:
            tw = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Themes\TranscodedWallpaper")
            if os.path.isfile(tw) and os.path.getsize(tw) > 1000:
                try:
                    shutil.copyfile(tw, backup_img)
                    restore_candidate = str(backup_img)
                except Exception:
                    pass

        # 5. Windows default wallpaper fallback
        if not restore_candidate:
            for candidate in [
                r"C:\Windows\Web\Wallpaper\Windows\img0.jpg",
                r"C:\Windows\Web\4K\Wallpaper\Windows\img0_1920x1080.jpg"
            ]:
                if os.path.isfile(candidate):
                    restore_candidate = candidate
                    break

        if restore_candidate and os.path.isfile(restore_candidate):
            try:
                SPI_SETDESKWALLPAPER = 20
                SPIF_UPDATEINIFILE = 1
                SPIF_SENDWININICHANGE = 2
                res = ctypes.windll.user32.SystemParametersInfoW(
                    SPI_SETDESKWALLPAPER, 0, str(restore_candidate),
                    SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
                )
                print(f"[BlackoutManager] Restored wallpaper to: {restore_candidate} (result: {res})")
            except Exception as e:
                print(f"[BlackoutManager] Wallpaper restore failed: {e}")

    @staticmethod
    def enable_blackout():
        import sys
        if sys.platform != "win32":
            return

        try:
            from config import config
            black_enabled = config.get("black_screen_enabled", True)
            icons_enabled = config.get("hide_desktop_icons", True)

            if not black_enabled and not icons_enabled:
                return

            import ctypes
            import tempfile
            import os

            # 1. Wallpaper Blackout
            if black_enabled:
                DesktopBlackoutManager._ensure_original_wallpaper_saved()

                try:
                    from PIL import Image
                    DesktopBlackoutManager._black_image_path = os.path.join(tempfile.gettempdir(), "ir_black_bg.bmp")
                    img = Image.new('RGB', (1, 1), color='black')
                    img.save(DesktopBlackoutManager._black_image_path)
                except Exception:
                    DesktopBlackoutManager._black_image_path = ""

                if DesktopBlackoutManager._black_image_path and os.path.isfile(DesktopBlackoutManager._black_image_path):
                    SPI_SETDESKWALLPAPER = 20
                    SPIF_UPDATEINIFILE = 1
                    SPIF_SENDWININICHANGE = 2
                    ctypes.windll.user32.SystemParametersInfoW(
                        SPI_SETDESKWALLPAPER, 0, DesktopBlackoutManager._black_image_path,
                        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE
                    )

            # 2. Hide Desktop Icons
            if icons_enabled:
                DesktopBlackoutManager.set_desktop_icons_hidden(True)

            DesktopBlackoutManager._is_blackout_active = True
            DesktopBlackoutManager._write_active_flag(True)
        except Exception as e:
            print(f"Blackout enable failed: {e}")

    @staticmethod
    def disable_blackout():
        import sys
        if sys.platform != "win32":
            return

        try:
            # 1. Restore wallpaper
            DesktopBlackoutManager._restore_original_wallpaper()

            # 2. Show desktop icons
            DesktopBlackoutManager.set_desktop_icons_hidden(False)

            DesktopBlackoutManager._is_blackout_active = False
            DesktopBlackoutManager._write_active_flag(False)
        except Exception as e:
            print(f"Blackout disable failed: {e}")

    @staticmethod
    def restore_if_needed():
        """Called at app launch to auto-restore desktop if a previous session crashed."""
        import sys
        if sys.platform != "win32":
            return
        try:
            flag_exists = DesktopBlackoutManager._get_active_flag_path().exists()
            curr_wp = DesktopBlackoutManager._query_current_wallpaper()
            # If current wallpaper is black or cannot be queried, or flag exists
            is_black_wp = (curr_wp is None or "ir_black_bg" in str(curr_wp).lower())
            icons_hidden = DesktopBlackoutManager.are_desktop_icons_hidden()

            if flag_exists or is_black_wp or icons_hidden:
                print("[BlackoutManager] Restoring desktop state from previous session...")
                DesktopBlackoutManager.disable_blackout()
        except Exception as e:
            print(f"[BlackoutManager] Startup recovery check failed: {e}")


class AlarmSoundPlayer:
    """Manages playing and stopping emergency/mismatch alarm audio across platforms."""
    _current_proc = None
    _is_playing = False

    @classmethod
    def get_alarm_path(cls):
        import sys
        import os
        from pathlib import Path
        filename = "mixkit-retro-game-emergency-alarm-1000.wav"

        # 1. PyInstaller _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            p = Path(sys._MEIPASS) / filename
            if p.is_file():
                return str(p)

        # 2. Local src directory
        p = Path(__file__).resolve().parent / filename
        if p.is_file():
            return str(p)

        # 3. Project root directory
        p = Path(__file__).resolve().parent.parent / filename
        if p.is_file():
            return str(p)

        # 4. Standard data dir C:/IR Attendance
        p = Path("C:/IR Attendance") / filename
        if p.is_file():
            return str(p)

        return filename

    @classmethod
    def play(cls, sound_path=None):
        import sys
        import os
        cls.stop()

        path = sound_path or cls.get_alarm_path()
        if not path or not os.path.isfile(path):
            print(f"[AlarmPlayer] Sound file not found: {path}")
            return

        cls._is_playing = True

        # Windows: Use native winsound (asynchronous loop)
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
                print(f"[AlarmPlayer] Playing alarm via winsound: {path}")
                return
            except Exception as e:
                print(f"[AlarmPlayer] winsound failed: {e}")

        # macOS / Linux: Use native CLI players in subprocess
        try:
            import subprocess
            if sys.platform == "darwin":
                cls._current_proc = subprocess.Popen(["afplay", str(path)])
                print(f"[AlarmPlayer] Playing alarm via afplay: {path}")
            elif sys.platform.startswith("linux"):
                cls._current_proc = subprocess.Popen(["aplay", str(path)])
        except Exception as e:
            print(f"[AlarmPlayer] Subprocess play failed: {e}")

    @classmethod
    def stop(cls):
        import sys
        # Windows: stop any winsound audio immediately
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

        # Subprocess cleanup for macOS / Linux
        if cls._current_proc:
            try:
                cls._current_proc.terminate()
                cls._current_proc.kill()
            except Exception:
                pass
            cls._current_proc = None

        cls._is_playing = False
        print("[AlarmPlayer] Alarm stopped.")


# Auto-register cleanup hook when Python process exits
try:
    import atexit
    atexit.register(DesktopBlackoutManager.disable_blackout)
    atexit.register(AlarmSoundPlayer.stop)
except Exception:
    pass

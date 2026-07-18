import subprocess
import shutil
import time
import os
from pathlib import Path

def _adb():
    """Find adb executable."""
    local_adb = Path("platform-tools/adb.exe").resolve()
    if local_adb.exists():
        return str(local_adb)
    return shutil.which('adb') or 'adb'

def _get_target(phone_ip: str) -> str:
    """Format the target IP, appending :5555 if no port is specified."""
    phone_ip = phone_ip.strip()
    if ':' in phone_ip:
        return phone_ip
    return f"{phone_ip}:5555"

def check_adb(phone_ip: str) -> tuple[bool, str]:
    """Try to connect to phone via ADB over WiFi. Returns (ok, message)."""
    target = _get_target(phone_ip)
    try:
        r = subprocess.run(
            [_adb(), 'connect', target],
            capture_output=True, text=True, timeout=15
        )
        out = (r.stdout + r.stderr).lower()
        if 'connected' in out or 'already connected' in out:
            return True, f"ADB connected to {target}"
        return False, f"ADB connect failed: {r.stdout.strip()}"
    except FileNotFoundError:
        return False, "adb not found — install Android platform-tools and add to PATH"
    except Exception as e:
        return False, str(e)

def adb_pair(pairing_ip_port: str, pairing_code: str) -> tuple[bool, str]:
    """Pair ADB with phone using 6-digit code."""
    try:
        r = subprocess.run(
            [_adb(), 'pair', pairing_ip_port, pairing_code],
            capture_output=True, text=True, timeout=20
        )
        out = (r.stdout + r.stderr).lower()
        if 'successfully paired' in out:
            return True, f"Successfully paired to {pairing_ip_port}"
        return False, f"Pairing failed: {r.stdout.strip()}"
    except FileNotFoundError:
        return False, "adb not found"
    except Exception as e:
        return False, str(e)

def adb_tap(phone_ip: str, x: int, y: int) -> bool:
    """Tap absolute screen coordinate on phone via ADB."""
    target = _get_target(phone_ip)
    try:
        r = subprocess.run(
            [_adb(), '-s', target, 'shell', 'input', 'tap', str(x), str(y)],
            capture_output=True, text=True, timeout=4
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[ADB] tap error: {e}")
        return False

def adb_tap_sequence(phone_ip: str, digit_coords: dict, id_string: str,
                     delay_ms: int = 150,
                     progress_cb=None) -> bool:
    """
    Tap the digits of id_string using stored calibration coords.
    digit_coords = {'0': {'x': 540, 'y': 1200}, '1': ..., ...}
    progress_cb(digit, index, total) called before each tap.
    Returns True if all taps succeeded.
    """
    digits = str(id_string).strip()
    total  = len(digits)
    ok     = True
    for i, d in enumerate(digits):
        coord = digit_coords.get(d)
        if not coord:
            print(f"[ADB] No calibration for digit '{d}' — skipping")
            continue
        if progress_cb:
            progress_cb(d, i, total)
        success = adb_tap(phone_ip, int(coord['x']), int(coord['y']))
        if not success:
            ok = False
        time.sleep(delay_ms / 1000.0)
    return ok

def adb_screencap(phone_ip: str) -> bytes:
    """Take a screenshot of the phone and return raw bytes."""
    target = _get_target(phone_ip)
    try:
        r = subprocess.run(
            [_adb(), '-s', target, 'exec-out', 'screencap', '-p'],
            capture_output=True, timeout=10
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
        return None
    except Exception as e:
        print(f"[ADB] screencap error: {e}")
        return None

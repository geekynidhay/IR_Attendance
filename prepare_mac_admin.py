"""
Helper script to package all necessary files for building the IR Admin Panel on macOS.
Run this script on Windows: python prepare_mac_admin.py
It will create a zip archive named mac_admin_package.zip.
"""
import os
import shutil
import zipfile
from pathlib import Path

def package_mac_admin():
    print("Preparing macOS Admin Panel Package...")
    
    # Define source and destination directories
    base_dir = Path(__file__).parent.absolute()
    pkg_dir = base_dir / "mac_admin_package"
    
    # Recreate package directory
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir / "src", exist_ok=True)
    
    # List of files to copy to root of package
    root_files = [
        "build_admin_mac.sh",
        "IR Admin Panel.spec",
        "Admin Icon.png",
        "firebase_config.json",
    ]
    
    # List of files to copy to src/ of package
    src_files = [
        "admin_panel.py",
        "drive_manager.py",
        "encryption_utils.py",
        "license_manager.py",
        "user_report_window.py",
        "system_utils.py",
    ]
    
    # Copy root files
    print("\nCopying root assets...")
    for filename in root_files:
        src_path = base_dir / filename
        if src_path.exists():
            shutil.copy2(src_path, pkg_dir / filename)
            print(f"  [OK] {filename}")
        else:
            print(f"  [WARN] {filename} not found!")

    # Copy src files
    print("\nCopying source code...")
    for filename in src_files:
        src_path = base_dir / "src" / filename
        if src_path.exists():
            shutil.copy2(src_path, pkg_dir / "src" / filename)
            print(f"  [OK] src/{filename}")
        else:
            print(f"  [WARN] src/{filename} not found!")

    # Create Zip File
    zip_path = base_dir / "mac_admin_package.zip"
    if zip_path.exists():
        os.remove(zip_path)
        
    print("\nCreating ZIP archive...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(pkg_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(pkg_dir)
                zipf.write(file_path, arcname)
                
    # Clean up directory, leave only the ZIP
    shutil.rmtree(pkg_dir)
    print(f"\nSUCCESS! Package created at:\n  {zip_path}")
    print("\nTransfer this ZIP file to your Mac, extract it, and run:\n  bash build_admin_mac.sh")

if __name__ == "__main__":
    package_mac_admin()

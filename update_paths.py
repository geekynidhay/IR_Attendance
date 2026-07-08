import os
import glob

src_dir = '/Users/nidhay/Desktop/PC-IR-ATT (2)/PC-IR-ATT/src'
files = glob.glob(os.path.join(src_dir, '*.py'))

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the Windows paths with the Mac Desktop path
    new_content = content.replace('C:/IR Attendance', '/Users/nidhay/Desktop/IRIS Data')
    new_content = new_content.replace('C:\\\\IR Attendance', '/Users/nidhay/Desktop/IRIS Data')
    new_content = new_content.replace('C:\\IR Attendance', '/Users/nidhay/Desktop/IRIS Data')
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated paths in {os.path.basename(filepath)}")

# -*- mode: python ; coding: utf-8 -*-
import os

# Collect Tesseract binaries and tessdata from the installed location
tesseract_dir = r'C:\Program Files\Tesseract-OCR'
tesseract_binaries = []
tesseract_datas = []

if os.path.isdir(tesseract_dir):
    # Collect all DLLs and EXEs from Tesseract root
    for fname in os.listdir(tesseract_dir):
        fpath = os.path.join(tesseract_dir, fname)
        if os.path.isfile(fpath) and fname.lower().endswith(('.dll', '.exe')):
            tesseract_binaries.append((fpath, 'Tesseract-OCR'))
    # Collect tessdata (language files) - only eng needed
    tessdata_dir = os.path.join(tesseract_dir, 'tessdata')
    if os.path.isdir(tessdata_dir):
        for fname in os.listdir(tessdata_dir):
            fpath = os.path.join(tessdata_dir, fname)
            if os.path.isfile(fpath):
                tesseract_datas.append((fpath, r'Tesseract-OCR\tessdata'))

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=tesseract_binaries,
    datas=[
        ('Icon.png', '.'),
        ('firebase_config.json', '.'),
        ('src/new_icon.gif', '.'),
        ('src/error_cross.png', '.'),
        ('src/ok_btn.png', '.'),
        ('src/ir-attendance-497712-b3ae57837200.json', '.'),
        ('src/*.py', '.'),
    ] + tesseract_datas,
    hiddenimports=[
        'fitz',
        'pymupdf',
        'cv2',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'pytesseract',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageEnhance',
        'PIL.ImageGrab',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'flask',
        'flask.templating',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.exceptions',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.primitives',
        'win32api',
        'win32con',
        'win32gui',
        'pywintypes',
        'keyboard',
        'pyperclip',
        'requests',
        'pyautogui',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'pathlib',
        'threading',
        'json',
        'io',
        'time',
        'sys',
        'os',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['soundcard', 'torch', 'torchvision', 'mediapipe', 'rembg', 'albumentations', 'numba'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir mode
    name='IR_Attendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll'],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['vcruntime140.dll', 'msvcp140.dll'],
    name='IR_Attendance'
)

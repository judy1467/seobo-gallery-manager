# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for servo-gallery-manager
# Build: pyinstaller --clean build_windows.spec
#

import os
import sys

block_cipher = None

a = Analysis(
    ["gallery_manager.py"],
    pathex=[os.path.abspath(SPECPATH)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "paramiko",
        "cryptography",
        "bcrypt",
        "nacl",
        "PIL",
        "PIL.Image",
        "PIL.ImageOps",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "notebook",
        "IPython",
        "test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SeoboGalleryManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SeoboGalleryManager",
)

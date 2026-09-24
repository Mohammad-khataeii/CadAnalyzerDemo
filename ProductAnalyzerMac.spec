# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["app/main.py"],
    pathex=[],
    binaries=[],
    datas=[("data/input", "data/input"), ("TechnicalDesigns", "TechnicalDesigns")],
    hiddenimports=collect_submodules("sklearn") + collect_submodules("PySide6"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ProductAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
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
    upx=True,
    upx_exclude=[],
    name="ProductAnalyzer",
)
app = BUNDLE(
    coll,
    name="ProductAnalyzer.app",
    icon=None,
    bundle_identifier="com.demo.productanalyzer",
    info_plist={
        "CFBundleName": "ProductAnalyzer",
        "CFBundleDisplayName": "Product Analyzer",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)

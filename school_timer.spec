from __future__ import annotations

# PyInstaller spec for macOS .app bundle (onedir).
# Build: pyinstaller -y school_timer.spec

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules("comcigan")

a = Analysis(
    ["tray.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Use onedir mode for macOS app bundles (avoids onefile+bundle issues).
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SchoolTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 메뉴바 앱: 터미널 창 없이 실행
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="SchoolTimer",
)

app = BUNDLE(
    coll,
    name="SchoolTimer.app",
    bundle_identifier="edu.hobinuniversity.schooltimer",
    info_plist={
        "CFBundleName": "SchoolTimer",
        "CFBundleDisplayName": "SchoolTimer",
        "NSHumanReadableCopyright": "by Hobin University",
        # Menu bar app (no Dock icon)
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)

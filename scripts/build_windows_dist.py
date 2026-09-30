#!/usr/bin/env python3
"""
Quran Video Studio - Windows Executable (.exe) and Portable Release Builder
Packages:
  1. Quran Video Studio.exe (Standalone 1-click self-extracting Windows executable)
  2. QuranVideoStudio-v1.4.0-Windows-Portable.zip (Zero-install portable zip)
Places artifacts in dist/ and copies to ~/Desktop/
"""

import os
import sys
import shutil
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(DIST_DIR, "build_win")
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
SFX_BIN = os.path.join(ASSETS_DIR, "7zS.sfx")
VERSION = "1.4.0"
DESKTOP_DIR = os.path.expanduser("~/Desktop")

def find_seven_zip():
    candidates = [
        shutil.which("7zz"),
        shutil.which("7z"),
        shutil.which("7z.exe"),
        "/opt/homebrew/bin/7zz",
        "/usr/local/bin/7zz",
        "/usr/bin/7z"
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return "7zz"

SEVEN_ZIP = find_seven_zip()

def create_windows_launchers(target_dir):
    # 1. Windows VBScript Launcher (Silent launch with no cmd window flicker)
    vbs_path = os.path.join(target_dir, "launcher.vbs")
    vbs_content = '''Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' 1. Start Python Studio Backend Server silently
strPyCmd = "cmd.exe /c cd /d """ & strDir & """ && python server.py 8765"
objShell.Run strPyCmd, 0, False

' 2. Give server 1.5 seconds to bind
WScript.Sleep 1500

' 3. Find Edge or Chrome to launch in clean App Mode
appUrl = "http://localhost:8765"
userDataDir = objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\\QuranVideoStudio\\User Data")

browserPath = ""
edgePaths = Array( _
    objShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe"), _
    objShell.ExpandEnvironmentStrings("%ProgramFiles%\\Microsoft\\Edge\\Application\\msedge.exe") _
)
For Each p In edgePaths
    If objFSO.FileExists(p) Then
        browserPath = p
        Exit For
    End If
Next

If browserPath = "" Then
    chromePaths = Array( _
        objShell.ExpandEnvironmentStrings("%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe"), _
        objShell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\\Google\\Chrome\\Application\\chrome.exe"), _
        objShell.ExpandEnvironmentStrings("%LocalAppData%\\Google\\Chrome\\Application\\chrome.exe") _
    )
    For Each p In chromePaths
        If objFSO.FileExists(p) Then
            browserPath = p
            Exit For
        End If
    Next
End If

If browserPath <> "" Then
    cmd = """" & browserPath & """ --app=""" & appUrl & """ --window-size=1560,980 --user-data-dir=""" & userDataDir & """ --no-first-run --no-default-browser-check"
    objShell.Run cmd, 1, False
Else
    objShell.Run "rundll32.exe url.dll,FileProtocolHandler """ & appUrl & """", 1, False
End If
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    # 2. Windows Batch Launcher (Visible troubleshooting alternative)
    bat_path = os.path.join(target_dir, "Run_Quran_Video_Studio.bat")
    bat_content = '''@echo off
title Quran Video Studio v1.4.0
cd /d "%~dp0"

echo ====================================================
echo Starting Quran Video Studio v1.4.0...
echo ====================================================

:: Prefer silent VBS launcher if wscript is available
if exist "%SystemRoot%\\System32\\wscript.exe" (
    "%SystemRoot%\\System32\\wscript.exe" //nologo "%~dp0launcher.vbs"
    exit /b 0
)

start "" /b python server.py 8765
timeout /t 2 /nobreak >nul

set "APP_URL=http://localhost:8765"
set "USER_DATA=%LOCALAPPDATA%\\QuranVideoStudio\\User Data"

if exist "%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe" (
    start "" "%ProgramFiles(x86)%\\Microsoft\\Edge\\Application\\msedge.exe" --app="%APP_URL%" --window-size=1560,980 --user-data-dir="%USER_DATA%"
    exit /b 0
)
if exist "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" (
    start "" "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" --app="%APP_URL%" --window-size=1560,980 --user-data-dir="%USER_DATA%"
    exit /b 0
)

start "" "%APP_URL%"
exit /b 0
'''
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

def build_windows_dist():
    print("=" * 65)
    print(f"Building Quran Video Studio Windows Distribution v{VERSION}")
    print("=" * 65)

    if not os.path.exists(SFX_BIN):
        print(f"Error: SFX binary not found at {SFX_BIN}")
        return None, None

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    pkg_root = os.path.join(BUILD_DIR, "QuranVideoStudio")
    os.makedirs(pkg_root, exist_ok=True)

    # 1. Copy core files
    print("[1/6] Gathering studio core application files...")
    core_files = [
        "index.html",
        "server.py",
        "studio_video_generator.py",
        "wbw_aligner.py",
        "render_slides_fast.mjs",
        "template_manager.py"
    ]
    for cf in core_files:
        src = os.path.join(PROJECT_ROOT, cf)
        if os.path.exists(src):
            shutil.copy2(src, pkg_root)

    # Optional python modules
    if os.path.exists(os.path.join(PROJECT_ROOT, "audio_dsp_engine.py")):
        shutil.copy2(os.path.join(PROJECT_ROOT, "audio_dsp_engine.py"), pkg_root)
    if os.path.exists(os.path.join(PROJECT_ROOT, "custom_layouts.json")):
        shutil.copy2(os.path.join(PROJECT_ROOT, "custom_layouts.json"), pkg_root)

    # Copy video_render essential html
    vr_dir = os.path.join(pkg_root, "video_render")
    os.makedirs(vr_dir, exist_ok=True)
    shutil.copy2(os.path.join(PROJECT_ROOT, "video_render", "render_studio_slide.html"), vr_dir)

    # Copy templates & profiles
    for folder in ["templates", "audio_profiles", "assets"]:
        src_f = os.path.join(PROJECT_ROOT, folder)
        if os.path.exists(src_f):
            shutil.copytree(src_f, os.path.join(pkg_root, folder))

    # 2. Add Windows Launchers
    print("[2/6] Writing Windows launchers (launcher.vbs & Run_Quran_Video_Studio.bat)...")
    create_windows_launchers(pkg_root)

    # 3. Add Windows Readme
    readme_win = os.path.join(pkg_root, "README_WINDOWS.txt")
    with open(readme_win, "w", encoding="utf-8") as f:
        f.write(f"""=====================================================
Quran Video Studio v{VERSION} - Windows Release
=====================================================

Quran Video Studio runs on Windows 11, 10, 8, and 7!

How to Launch:
1. Double-click "Quran Video Studio.exe" OR "Run_Quran_Video_Studio.bat".
2. The studio will open in a native desktop window.
3. Default Surah Hamd (Al-Fatihah) will be active.
4. Customize Tilawat & Translations positioning, Sadaqah Jariyah dedications,
   audio waveforms, and render Ultra-HD 4K & 1080p videos.

Requirements:
- Python 3.10+ installed and added to PATH (https://www.python.org/downloads/)
- Google Chrome or Microsoft Edge installed (for ultra-fast slide rendering).
""")

    # 4. Create Standalone Windows Executable (.exe) via 7z SFX
    print("[3/6] Compressing package into 7z payload...")
    payload_7z = os.path.join(BUILD_DIR, "payload.7z")
    subprocess.check_call([
        SEVEN_ZIP, "a", "-t7z", "-mx=9", "-mfb=64", "-md=32m", "-ms=on",
        payload_7z, f"{pkg_root}/*"
    ])

    sfx_cfg = os.path.join(BUILD_DIR, "sfx_config.txt")
    with open(sfx_cfg, "wb") as f:
        f.write(f';!@Install@!UTF-8!\r\nTitle="Quran Video Studio v{VERSION}"\r\nRunProgram="wscript.exe //nologo launcher.vbs"\r\n;!@InstallEnd@!\r\n'.encode('utf-8'))

    exe_name = "Quran Video Studio.exe"
    out_exe = os.path.join(DIST_DIR, exe_name)
    if os.path.exists(out_exe):
        os.remove(out_exe)

    print(f"[4/6] Assembling standalone PE executable: {exe_name}...")
    with open(out_exe, "wb") as dst:
        with open(SFX_BIN, "rb") as s:
            dst.write(s.read())
        with open(sfx_cfg, "rb") as s:
            dst.write(s.read())
        with open(payload_7z, "rb") as s:
            dst.write(s.read())

    exe_size_mb = os.path.getsize(out_exe) / (1024 * 1024)
    print(f"[SUCCESS] Standalone Windows Executable created: {out_exe} ({exe_size_mb:.2f} MB)")

    # 5. Create Standalone Portable ZIP
    zip_name = f"QuranVideoStudio-v{VERSION}-Windows-Portable.zip"
    out_zip = os.path.join(DIST_DIR, zip_name)
    if os.path.exists(out_zip):
        os.remove(out_zip)

    # Include .exe inside the portable zip
    shutil.copy2(out_exe, pkg_root)

    print(f"[5/6] Packaging complete portable ZIP: {zip_name}...")
    subprocess.check_call([
        SEVEN_ZIP, "a", "-tzip", "-mx=9",
        out_zip, f"{pkg_root}/*"
    ])
    zip_size_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[SUCCESS] Windows Portable ZIP created: {out_zip} ({zip_size_mb:.2f} MB)")

    # 6. Copy to Desktop
    if os.path.exists(DESKTOP_DIR):
        try:
            desktop_exe = os.path.join(DESKTOP_DIR, exe_name)
            desktop_zip = os.path.join(DESKTOP_DIR, zip_name)
            shutil.copy2(out_exe, desktop_exe)
            shutil.copy2(out_zip, desktop_zip)
            print(f"[6/6] Copied release artifacts to Desktop:")
            print(f"  * {desktop_exe}")
            print(f"  * {desktop_zip}")
        except Exception as e:
            print(f"  * Desktop copy notice: {e}")

    # Clean up staging directory
    shutil.rmtree(BUILD_DIR)
    return out_exe, out_zip

if __name__ == "__main__":
    build_windows_dist()

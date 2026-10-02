#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( cd "$DIR/.." && pwd )"
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

echo "=== Building Quran Video Studio macOS App & DMG v1.4.0 ==="

# 1. Generate AppIcon.icns
echo "--> Generating App Icon..."
if [ ! -f "$DIR/AppIcon.icns" ]; then
    "$CHROME_BIN" --headless --disable-gpu --hide-scrollbars --window-size=1024,1024 --screenshot="$DIR/icon_1024.png" "file://$DIR/icon.html"

    ICONSET="$DIR/AppIcon.iconset"
    rm -rf "$ICONSET"
    mkdir -p "$ICONSET"

    sips -z 16 16     "$DIR/icon_1024.png" --out "$ICONSET/icon_16x16.png" > /dev/null
    sips -z 32 32     "$DIR/icon_1024.png" --out "$ICONSET/icon_16x16@2x.png" > /dev/null
    sips -z 32 32     "$DIR/icon_1024.png" --out "$ICONSET/icon_32x32.png" > /dev/null
    sips -z 64 64     "$DIR/icon_1024.png" --out "$ICONSET/icon_32x32@2x.png" > /dev/null
    sips -z 128 128   "$DIR/icon_1024.png" --out "$ICONSET/icon_128x128.png" > /dev/null
    sips -z 256 256   "$DIR/icon_1024.png" --out "$ICONSET/icon_128x128@2x.png" > /dev/null
    sips -z 256 256   "$DIR/icon_1024.png" --out "$ICONSET/icon_256x256.png" > /dev/null
    sips -z 512 512   "$DIR/icon_1024.png" --out "$ICONSET/icon_256x256@2x.png" > /dev/null
    sips -z 512 512   "$DIR/icon_1024.png" --out "$ICONSET/icon_512x512.png" > /dev/null
    cp "$DIR/icon_1024.png" "$ICONSET/icon_512x512@2x.png"

    iconutil -c icns "$ICONSET" -o "$DIR/AppIcon.icns"
    rm -rf "$ICONSET" "$DIR/icon_1024.png"
    echo "Icon created: $DIR/AppIcon.icns"
fi

# 2. Compile Native Swift Application
echo "--> Compiling Swift macOS Native Binary..."
APP_BUNDLE="$BASE_DIR/QuranVideoStudio.app"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

swiftc -O -target arm64-apple-macos12.0 "$DIR/main.swift" -o "$APP_BUNDLE/Contents/MacOS/QuranVideoStudio"

# 3. Assemble App Bundle
echo "--> Bundling Resources and Metadata..."
cp "$DIR/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
cp "$DIR/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"

# Copy web studio files into App Resources
cp "$BASE_DIR/server.py" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/studio_video_generator.py" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/audio_dsp_engine.py" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/template_manager.py" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/wbw_aligner.py" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/index.html" "$APP_BUNDLE/Contents/Resources/"
cp "$BASE_DIR/render_slides_fast.mjs" "$APP_BUNDLE/Contents/Resources/"
mkdir -p "$APP_BUNDLE/Contents/Resources/video_render"
cp "$BASE_DIR/video_render/render_studio_slide.html" "$APP_BUNDLE/Contents/Resources/video_render/"
if [ -d "$BASE_DIR/templates" ]; then cp -R "$BASE_DIR/templates" "$APP_BUNDLE/Contents/Resources/"; fi
if [ -d "$BASE_DIR/custom_backgrounds" ]; then cp -R "$BASE_DIR/custom_backgrounds" "$APP_BUNDLE/Contents/Resources/"; fi
if [ -d "$BASE_DIR/fonts" ]; then cp -R "$BASE_DIR/fonts" "$APP_BUNDLE/Contents/Resources/"; fi
if [ -d "$BASE_DIR/audio" ]; then cp -R "$BASE_DIR/audio" "$APP_BUNDLE/Contents/Resources/"; fi
if [ -d "$BASE_DIR/audio_profiles" ]; then cp -R "$BASE_DIR/audio_profiles" "$APP_BUNDLE/Contents/Resources/"; fi
if [ -f "$BASE_DIR/custom_layouts.json" ]; then cp "$BASE_DIR/custom_layouts.json" "$APP_BUNDLE/Contents/Resources/"; fi

chmod -R 755 "$APP_BUNDLE"
chmod +x "$APP_BUNDLE/Contents/MacOS/QuranVideoStudio"

# Sign bundle and clear quarantine
echo "--> Codesigning App Bundle..."
xattr -cr "$APP_BUNDLE" 2>/dev/null || true
codesign --force --deep --sign - "$APP_BUNDLE"

echo "App Bundle created and signed successfully: $APP_BUNDLE"

# 4. Package into .DMG Installer
echo "--> Creating Drag-and-Drop macOS DMG Installer..."
DMG_ROOT="$DIR/dmg_root"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"

cp -R "$APP_BUNDLE" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"

DMG_OUT="$BASE_DIR/QuranVideoStudio.dmg"
rm -f "$DMG_OUT"

hdiutil create -volname "Quran Video Studio v1.4.0" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_OUT"
rm -rf "$DMG_ROOT"
xattr -cr "$DMG_OUT" 2>/dev/null || true

echo "=== SUCCESS! DMG Created at: $DMG_OUT ==="

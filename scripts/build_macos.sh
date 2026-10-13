#!/bin/zsh
set -euo pipefail

ROOT_DIR="${0:A:h:h}"
BUILD_DIR="$ROOT_DIR/build"
APP_DIR="$BUILD_DIR/LauraPhysics 开源参赛版.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR/static" "$RESOURCES_DIR/data"

SWIFT_MODULECACHE_PATH="$ROOT_DIR/tmp/swift-cache" swiftc -module-cache-path "$ROOT_DIR/tmp/swift-cache" \
  -O \
  -framework Cocoa \
  -framework WebKit \
  "$ROOT_DIR/native/main.swift" \
  -o "$MACOS_DIR/LauraPhysicsOpen"

cp "$ROOT_DIR/native/Info.plist" "$CONTENTS_DIR/Info.plist"
cp "$ROOT_DIR/server.py" "$RESOURCES_DIR/server.py"
cp "$ROOT_DIR/exam_pdf.py" "$RESOURCES_DIR/exam_pdf.py"
cp "$ROOT_DIR/core_server.py" "$RESOURCES_DIR/core_server.py"
cp "$ROOT_DIR/ai_workflows.py" "$RESOURCES_DIR/ai_workflows.py"
cp "$ROOT_DIR/question_pool.py" "$RESOURCES_DIR/question_pool.py"
cp "$ROOT_DIR/environment_check.py" "$RESOURCES_DIR/environment_check.py"
mkdir -p "$RESOURCES_DIR/scripts"
cp "$ROOT_DIR/scripts/run_web.py" "$ROOT_DIR/scripts/setup_environment.py" "$ROOT_DIR/scripts/bootstrap_assets.py" "$ROOT_DIR/scripts/evaluate_marking.py" "$RESOURCES_DIR/scripts/"
if [[ -d "$ROOT_DIR/vendor" ]]; then
  mkdir -p "$RESOURCES_DIR/vendor"
  cp -R "$ROOT_DIR/vendor/." "$RESOURCES_DIR/vendor/"
fi
cp "$ROOT_DIR/requirements.txt" "$RESOURCES_DIR/requirements.txt"
cp "$ROOT_DIR/requirements-tested.txt" "$RESOURCES_DIR/requirements-tested.txt"
cp "$ROOT_DIR/README.md" "$ROOT_DIR/CONTRIBUTING.md" "$ROOT_DIR/CHANGELOG.md" "$ROOT_DIR/THIRD_PARTY_NOTICES.md" "$ROOT_DIR/LICENSE" "$ROOT_DIR/CONTENT_LICENSES.md" "$RESOURCES_DIR/"
mkdir -p "$RESOURCES_DIR/docs"
cp -R "$ROOT_DIR/docs/." "$RESOURCES_DIR/docs/"
cp -R "$ROOT_DIR/static/." "$RESOURCES_DIR/static/"
cp -R "$ROOT_DIR/data/." "$RESOURCES_DIR/data/"
cp "$ROOT_DIR/assets/LauraPhysicsOpen.icns" "$RESOURCES_DIR/LauraPhysicsOpen.icns"

codesign --force --deep --sign - "$APP_DIR"
echo "$APP_DIR"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ "${SKIP_APP_BUILD:-0}" != "1" ]; then
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi

  . .venv/bin/activate
  python -m pip install -r requirements.txt
  python -m PyInstaller --clean --noconfirm ProductAnalyzerMac.spec
fi

DMG_ROOT="$(mktemp -d "$ROOT_DIR/build/dmg-root.XXXXXX")"
DMG_PATH="dist/ProductAnalyzer-mac.dmg"
trap 'rm -rf "$DMG_ROOT"' EXIT
rm -f "$DMG_PATH"
cp -R "dist/ProductAnalyzer.app" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"

hdiutil create \
  -volname "Product Analyzer" \
  -srcfolder "$DMG_ROOT" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Created $DMG_PATH"

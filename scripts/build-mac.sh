#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv가 필요합니다. https://docs.astral.sh/uv/ 참고"
  exit 1
fi

echo "Installing build dependencies (pyinstaller)..."
uv sync --extra dev

echo "Checking Xcode Command Line Tools license..."
if ! xcrun --find install_name_tool >/dev/null 2>&1; then
  echo
  echo "Xcode 라이선스 동의가 필요합니다. 아래를 실행한 뒤 다시 빌드하세요:"
  echo "  sudo xcodebuild -license"
  exit 1
fi

echo "Building macOS .app with PyInstaller..."
uv run pyinstaller -y school_timer.spec

echo
echo "Done:"
echo "  dist/SchoolTimer.app"


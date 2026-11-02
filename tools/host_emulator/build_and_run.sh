#!/usr/bin/env bash
# Збирає НЕЗМІНЕНИЙ sketch.ino на host-моделі ESP32 Arduino API і відкриває virtual serial (pty).
# Usage: ./build_and_run.sh path/to/sketch.ino /tmp/ttyFW [trace.log]
#        export DEVICE_PORT=/tmp/ttyFW && cd ../../automation && pytest -v
# Env:   EMU_TEMP=24.5 (за замовчуванням) | EMU_TEMP=nan — датчик недоступний
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp "$1" "$here/.sketch.cpp"
g++ -std=c++17 -O1 -Wall -I"$here" -o "$here/.fw" "$here/host_main.cpp" "$here/.sketch.cpp"
exec "$here/.fw" "$2" "${3:-/dev/null}"

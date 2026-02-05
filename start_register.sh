#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv || true
fi

if [ ! -f ".venv/bin/activate" ]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "== 安装 python3-venv =="
    apt-get update -y
    apt-get install -y python3-venv
    python3 -m venv .venv
  else
    echo "ERROR: .venv/bin/activate not found and apt-get unavailable"
    exit 1
  fi
fi

source ".venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v apt-get >/dev/null 2>&1; then
  echo "== 安装 Chromium =="
  apt-get update -y
  apt-get install -y chromium || apt-get install -y chromium-browser
fi

if command -v chromium >/dev/null 2>&1; then
  export CHROME_BINARY="$(command -v chromium)"
elif command -v chromium-browser >/dev/null 2>&1; then
  export CHROME_BINARY="$(command -v chromium-browser)"
elif command -v google-chrome >/dev/null 2>&1; then
  export CHROME_BINARY="$(command -v google-chrome)"
fi

if [ -n "${CHROME_BINARY:-}" ]; then
  CHROME_VERSION_RAW="$("$CHROME_BINARY" --version || true)"
  CHROME_VERSION_MAIN="$(echo "$CHROME_VERSION_RAW" | grep -oE '[0-9]+' | head -n 1 || true)"
  if [ -n "$CHROME_VERSION_MAIN" ]; then
    export CHROME_VERSION="$CHROME_VERSION_MAIN"
  fi
fi

echo "== 测试代理IP获取与使用 =="
python test_proxy_ip_usage.py

echo "== 启动注册流程 =="
python register_with_proxy.py

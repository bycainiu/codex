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

echo "== 测试代理IP获取与使用 =="
python test_proxy_ip_usage.py

echo "== 启动注册流程 =="
python register_with_proxy.py

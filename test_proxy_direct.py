#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接测试快代理隧道连接
"""

import requests
import config

print("="*60)
print("快代理隧道连接测试")
print("="*60)

# 构建代理URL
proxy_url = f"http://{config.PROXY_USERNAME}:{config.PROXY_PASSWORD}@{config.PROXY_HOST}:{config.PROXY_PORT}"
proxies = {
    "http": proxy_url,
    "https": proxy_url
}

print(f"\n代理配置:")
print(f"  主机: {config.PROXY_HOST}")
print(f"  端口: {config.PROXY_PORT}")
print(f"  用户: {config.PROXY_USERNAME}")

# 测试目标URL
test_urls = [
    "https://ipinfo.io/ip",
    "https://api.ipify.org",
    "https://httpbin.org/ip",
]

print(f"\n测试连接...")

for url in test_urls:
    try:
        print(f"\n  测试: {url}")
        response = requests.get(url, proxies=proxies, timeout=30, verify=False)
        print(f"    状态: {response.status_code}")
        print(f"    响应: {response.text[:100]}")
    except Exception as e:
        print(f"    错误: {e}")

# 也测试不使用代理（走系统全局代理）
print(f"\n\n不使用显式代理（走系统全局代理）:")
for url in test_urls[:1]:
    try:
        print(f"\n  测试: {url}")
        response = requests.get(url, timeout=30, verify=False)
        print(f"    状态: {response.status_code}")
        print(f"    响应: {response.text[:100]}")
    except Exception as e:
        print(f"    错误: {e}")

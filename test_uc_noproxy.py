#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 undetected_chromedriver - 排除localhost代理
"""

import os
import undetected_chromedriver as uc

# 设置环境变量排除localhost代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

print("="*60)
print("undetected_chromedriver test (NO_PROXY set)")
print("="*60)
print(f"NO_PROXY={os.environ.get('NO_PROXY')}")

print("\n1. Creating options...")
options = uc.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
# 添加忽略证书错误
options.add_argument('--ignore-certificate-errors')
options.add_argument('--ignore-ssl-errors')

print("\n2. Initializing driver...")
try:
    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
        version_main=143
    )
    
    print("\n3. Navigating to test page...")
    driver.get("https://ipinfo.io/ip")
    
    print(f"\n4. Page title: {driver.title}")
    print(f"   Page content: {driver.page_source[:200]}")
    
    driver.quit()
    print("\nSUCCESS!")
    
except Exception as e:
    print(f"\nFAILED: {e}")
    import traceback
    traceback.print_exc()

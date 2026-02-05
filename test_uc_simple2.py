#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试 undetected_chromedriver - 不使用 webdriver_manager
"""

import undetected_chromedriver as uc

print("="*60)
print("undetected_chromedriver test (no webdriver_manager)")
print("="*60)

print("\n1. Creating options...")
options = uc.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

print("\n2. Initializing driver (let uc manage driver)...")
try:
    # 不指定 driver_executable_path，让 uc 自己管理
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

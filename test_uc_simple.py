#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单测试 undetected_chromedriver
"""

import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager

print("="*60)
print("undetected_chromedriver 简单测试")
print("="*60)

print("\n1. 创建选项...")
options = uc.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

print("\n2. 初始化驱动...")
try:
    driver = uc.Chrome(
        options=options,
        driver_executable_path=ChromeDriverManager().install(),
        use_subprocess=True,
        version_main=143
    )
    
    print("\n3. 访问测试页面...")
    driver.get("https://ipinfo.io/ip")
    
    print(f"\n4. 页面标题: {driver.title}")
    print(f"   页面内容: {driver.page_source[:200]}")
    
    driver.quit()
    print("\n✅ 测试成功!")
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

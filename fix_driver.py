#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""临时脚本：移除webdriver_manager依赖"""

import re

with open('register_with_proxy.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除导入语句
content = re.sub(
    r'from webdriver_manager\.chrome import ChromeDriverManager\n?',
    '# webdriver_manager removed - uc auto manages driver\n',
    content
)

# 移除ChromeDriverManager().install()那一行
content = re.sub(
    r'"driver_executable_path":\s*ChromeDriverManager\(\)\.install\(\),?\s*\n?',
    '',
    content
)

with open('register_with_proxy.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done: removed webdriver_manager import and ChromeDriverManager().install() line")

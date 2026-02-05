#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置文件
集中管理所有配置项
"""

import os

# ==================== 注册配置 ====================
TOTAL_ACCOUNTS = 4  # 批量注册账号数量

# ==================== DuckMail 临时邮箱配置 ====================
DUCKMAIL_API_URL = "https://api.duckmail.sbs"  # DuckMail API地址（注意末尾无斜杠）
DUCKMAIL_API_KEY = "dk_5d6a4a76d3a70d8980a27c9101553ecfff7b949ab991cc0d769ddb8cb27ee07c"  # DuckMail API密钥
DUCKMAIL_DOMAIN = "ldhub.shop"   # 私有域名
DUCKMAIL_USE_LOCAL_PROXY = False
DUCKMAIL_LOCAL_PROXY_URL = "http://127.0.0.1:7890"

# ==================== OpenAI OAuth 配置 ====================
OAUTH_ISSUER = "https://auth.openai.com"
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_REDIRECT_URI = "http://localhost:1455/auth/callback"

# ==================== 代理配置 ====================
# 是否为Selenium配置代理
USE_PROXY = True

# 代理IP获取方式（走系统全局代理去获取）
USE_PROXY_API = True
PROXY_API_URL = "https://fps.kdlapi.com/api/getfps"
PROXY_API_PARAMS = {
    "secret_id": "ow216ubbxv5v873728rn",
    "signature": "m5ax4786mzy4q5zed0t4f9io8m34rerl",
    "num": 1
}
PROXY_API_RETRIES = 3
PROXY_API_RETRY_DELAY = 2  # 秒
PROXY_API_USE_LOCAL_PROXY = False
PROXY_API_LOCAL_PROXY_URL = "http://127.0.0.1:7890"

# 备用固定代理（当不使用API时）
PROXY_HOST = "k263.kdlfps.com"
PROXY_PORT = 18866
PROXY_USERNAME = "f2320674627"
PROXY_PASSWORD = "06xv9rd2"

# requests请求走系统全局代理（默认空代理字典）
REQUESTS_USE_PROXY = False

# 是否强制Selenium必须使用代理（获取不到则终止当前账号）
REQUIRE_SELENIUM_PROXY = True

# ==================== 输出文件配置 ====================
ACCOUNTS_FILE = "accounts.txt"
AK_FILE = "ak.txt"
RK_FILE = "rk.txt"

# ==================== 浏览器配置 ====================
HEADLESS_MODE = False
WINDOW_SIZE = "1920,1080"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
CHROME_VERSION = 143  # Chrome主版本号（运行命令检测：chrome --version）

# ==================== 超时配置 ====================
EMAIL_VERIFICATION_TIMEOUT = 120
OAUTH_CALLBACK_TIMEOUT = 60
PAGE_LOAD_TIMEOUT = 30

# ==================== 重试配置 ====================
MAX_ERROR_RETRIES = 5
MAX_OAUTH_RETRIES = 3

# ==================== 批量注册配置 ====================
MIN_WAIT_BETWEEN_ACCOUNTS = 5
MAX_WAIT_BETWEEN_ACCOUNTS = 15

# ==================== 测试模式 ====================
TEST_MODE = False
SAVE_SCREENSHOTS = True

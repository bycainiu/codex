#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI账号注册机 - 集成代理版本
支持批量注册、代理切换、邮箱验证、OAuth认证
"""

import os
import shutil
import subprocess
# 排除localhost代理，防止系统全局代理影响ChromeDriver通信
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
import random
import string
import re
import json
import base64
import secrets
import hashlib
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict
import urllib3

# 导入自定义模块
from proxy_manager import ProxyManager
import config

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('register.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class OpenAIRegistrationBot:
    """OpenAI注册机器人"""
    
    def __init__(self, use_proxy: bool = True):
        """
        初始化注册机器人
        
        Args:
            use_proxy: 是否使用代理
        """
        self.use_proxy = use_proxy
        self.proxy_manager = None
        
        if self.use_proxy:
            # 创建代理管理器
            self.proxy_manager = ProxyManager(
                proxy_host=config.PROXY_HOST,
                proxy_port=config.PROXY_PORT,
                username=config.PROXY_USERNAME,
                password=config.PROXY_PASSWORD,
                requests_use_proxy=config.REQUESTS_USE_PROXY,
                use_proxy_api=getattr(config, "USE_PROXY_API", False),
                proxy_api_url=getattr(config, "PROXY_API_URL", ""),
                proxy_api_params=getattr(config, "PROXY_API_PARAMS", {})
            )
            
            # 测试网络连接（走系统全局代理）
            if self.proxy_manager.test_connection():
                logger.info("✅ 网络连接正常")
            else:
                logger.warning("⚠️ 网络连接测试失败，请检查全局代理是否开启")
    
    def get_driver(self, selenium_proxy: Optional[str] = None) -> uc.Chrome:
        """
        创建并配置Chrome驱动
        
        Returns:
            配置好的Chrome驱动实例
        """
        options = uc.ChromeOptions()

        chrome_binary = None
        if getattr(config, "CHROME_BINARY", ""):
            chrome_binary = config.CHROME_BINARY
        else:
            chrome_binary = self.detect_chrome_binary()

        if chrome_binary:
            options.binary_location = chrome_binary
        else:
            raise RuntimeError("Chrome binary not found. Please install Chrome/Chromium or set CHROME_BINARY.")
        
        # 基础配置
        headless = config.HEADLESS_MODE
        if not headless:
            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                headless = True
                logger.info("ℹ️ 未检测到显示环境，自动启用headless模式")

        if headless:
            options.add_argument('--headless=new')  # 新版headless模式
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--window-size={config.WINDOW_SIZE}')
        options.add_argument(f'--user-agent={config.USER_AGENT}')
        
        # 配置代理（使用获取到的代理IP）
        if self.use_proxy and self.proxy_manager:
            if not selenium_proxy:
                selenium_proxy = self.proxy_manager.get_selenium_proxy(
                    retries=config.PROXY_API_RETRIES,
                    delay=config.PROXY_API_RETRY_DELAY,
                    local_proxy_url=(
                        config.PROXY_API_LOCAL_PROXY_URL
                        if getattr(config, "PROXY_API_USE_LOCAL_PROXY", False)
                        else None
                    )
                )
            if selenium_proxy:
                options.add_argument(f'--proxy-server=http://{selenium_proxy}')
                options.add_argument('--proxy-bypass-list=<-loopback>')
                logger.info(f"🌐 Selenium使用代理IP: {selenium_proxy}")
            else:
                logger.warning("⚠️ 未获取到代理IP，Selenium将直连")
        
        logger.info("🚀 正在初始化Chrome驱动...")
        version_main = self.detect_chrome_version_main(chrome_binary)
        driver_kwargs = {
            "options": options,
            "driver_executable_path": ChromeDriverManager().install(),
            "use_subprocess": True
        }
        if version_main:
            driver_kwargs["version_main"] = version_main

        driver = uc.Chrome(**driver_kwargs)
        
        return driver

    @staticmethod
    def detect_chrome_binary() -> Optional[str]:
        """检测Chrome/Chromium二进制路径"""
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser"
        ]
        for name in candidates:
            path = shutil.which(name)
            if path:
                return path
        # 常见路径
        common_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser"
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def detect_chrome_version_main(binary_path: Optional[str]) -> Optional[int]:
        """检测Chrome主版本号"""
        if isinstance(getattr(config, "CHROME_VERSION", None), int) and config.CHROME_VERSION > 0:
            return config.CHROME_VERSION

        if not binary_path:
            return None

        try:
            out = subprocess.check_output([binary_path, "--version"], stderr=subprocess.STDOUT, text=True)
            match = re.search(r"(\d+)\.", out)
            if match:
                return int(match.group(1))
        except Exception:
            return None

        return None
    
    def get_proxies_dict(self) -> Dict[str, str]:
        """
        获取用于requests的代理字典
        
        Returns:
            代理字典
        """
        if self.use_proxy and self.proxy_manager:
            proxies = self.proxy_manager.get_proxies_dict()
            return proxies
        return {}

    def get_duckmail_proxies(self) -> Dict[str, str]:
        """DuckMail请求代理配置（优先使用本地代理）"""
        if getattr(config, "DUCKMAIL_USE_LOCAL_PROXY", False):
            local_proxy = getattr(config, "DUCKMAIL_LOCAL_PROXY_URL", "")
            if local_proxy:
                return {"http": local_proxy, "https": local_proxy}
        return self.get_proxies_dict()

    @staticmethod
    def build_proxy_dict(proxy_addr: Optional[str]) -> Dict[str, str]:
        """根据代理地址构造requests代理字典"""
        if not proxy_addr:
            return {}
        proxy_url = f"http://{proxy_addr}"
        return {"http": proxy_url, "https": proxy_url}
    
    @staticmethod
    def generate_random_password(length: int = 16) -> str:
        """
        生成随机密码
        
        Args:
            length: 密码长度
            
        Returns:
            随机密码
        """
        chars = string.ascii_letters + string.digits + "!@#$%"
        password = "".join(random.choice(chars) for _ in range(length))
        password = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.ascii_lowercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + password[4:]
        )
        logger.info(f"✅ 生成密码: {password}")
        return password
    
    def create_temp_email(
        self,
        proxies: Optional[Dict[str, str]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        创建临时邮箱
        
        Returns:
            (邮箱地址, JWT Token)
        """
        logger.info("📧 正在创建临时邮箱...")
        
        try:
            # 生成随机邮箱名称
            letters1 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 6)))
            numbers = ''.join(random.choices(string.digits, k=random.randint(1, 3)))
            letters2 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(0, 5)))
            random_name = letters1 + numbers + letters2
            email_address = f"{random_name}@{config.DUCKMAIL_DOMAIN}"
            email_password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            
            # 获取代理
            if proxies is None:
                proxies = self.get_duckmail_proxies()
            
            session = requests.Session()
            session.trust_env = False

            # 创建邮箱账户
            res = session.post(
                f"{config.DUCKMAIL_API_URL}/accounts",
                json={
                    "address": email_address,
                    "password": email_password,
                },
                headers={
                    'Authorization': f'Bearer {config.DUCKMAIL_API_KEY}',
                    "Content-Type": "application/json"
                },
                timeout=10,
                verify=False,
                proxies=proxies
            )
            
            if res.status_code != 201:
                logger.error(f"❌ 创建邮箱失败: {res.status_code} - {res.text}")
                return None, None
            
            # 获取认证Token
            token_res = session.post(
                f"{config.DUCKMAIL_API_URL}/token",
                json={
                    "address": email_address,
                    "password": email_password,
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
                verify=False,
                proxies=proxies
            )
            
            if token_res.status_code == 200:
                token_data = token_res.json()
                jwt_token = token_data.get('token')
                logger.info(f"✅ 邮箱创建成功: {email_address}")
                return email_address, jwt_token
            else:
                logger.error(f"❌ 获取Token失败: {token_res.status_code} - {token_res.text}")
                
        except Exception as e:
            logger.error(f"❌ 邮箱创建异常: {e}")
        
        return None, None
    
    def fetch_emails(
        self,
        email: str,
        jwt_token: str,
        proxies: Optional[Dict[str, str]] = None
    ) -> list:
        """
        获取邮箱中的邮件列表
        
        Args:
            email: 邮箱地址
            jwt_token: JWT认证令牌
            
        Returns:
            邮件列表
        """
        try:
            if proxies is None:
                proxies = self.get_duckmail_proxies()

            session = requests.Session()
            session.trust_env = False
            
            res = session.get(
                f"{config.DUCKMAIL_API_URL}/messages",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Content-Type": "application/json"
                },
                verify=False,
                proxies=proxies
            )
            
            if res.status_code == 200:
                data = res.json()
                members = data.get("hydra:member", [])
                if members:
                    logger.info(f"📬 收到 {len(members)} 封邮件")
                return members
            else:
                logger.error(f"❌ 获取邮件失败: HTTP {res.status_code}")
                
        except Exception as e:
            logger.error(f"❌ 获取邮件异常: {e}")
        
        return []
    
    @staticmethod
    def extract_verification_code(email_content: str) -> Optional[str]:
        """
        从邮件内容中提取验证码
        
        Args:
            email_content: 邮件内容
            
        Returns:
            验证码
        """
        if not email_content:
            return None
        
        patterns = [
            r"代码为\s*(\d{6})",
            r"code is\s*(\d{6})",
            r"(\d{6})",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, email_content)
            if matches:
                code = matches[0]
                logger.info(f"✅ 提取到验证码: {code}")
                return code
        
        return None
    
    def wait_for_verification_email(
        self,
        email: str,
        jwt_token: str,
        timeout: int = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        等待验证邮件并提取验证码
        
        Args:
            email: 邮箱地址
            jwt_token: JWT令牌
            timeout: 超时时间（秒）
            
        Returns:
            验证码
        """
        if timeout is None:
            timeout = config.EMAIL_VERIFICATION_TIMEOUT
        
        logger.info(f"⏳ 等待验证邮件（最长 {timeout}秒）...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            emails = self.fetch_emails(email, jwt_token, proxies=proxies)
            
            if emails:
                # 按创建时间倒序排序
                sorted_emails = sorted(
                    emails, 
                    key=lambda x: x.get("createdAt", ""), 
                    reverse=True
                )
                
                for email_item in sorted_emails:
                    if not isinstance(email_item, dict):
                        continue
                    
                    # 获取发件人
                    from_field = email_item.get("from", {})
                    if isinstance(from_field, dict):
                        sender = from_field.get("address", "").lower()
                    elif isinstance(from_field, str):
                        sender = from_field.lower()
                    else:
                        sender = ""
                    
                    subject = email_item.get("subject", "").lower()
                    
                    # 检查是否是OpenAI邮件
                    if "openai" in sender or "openai" in subject:
                        logger.info(f"📧 找到OpenAI邮件")
                        
                        # 从主题提取验证码
                        subject_full = email_item.get("subject", "")
                        code = self.extract_verification_code(subject_full)
                        if code:
                            return code
                        
                        # 从邮件正文提取
                        download_url = email_item.get("downloadUrl", "")
                        if download_url:
                            try:
                                if download_url.startswith("/"):
                                    full_url = f"{config.DUCKMAIL_API_URL}{download_url}"
                                else:
                                    full_url = download_url
                                
                                if proxies is None:
                                    proxies = self.get_duckmail_proxies()

                                session = requests.Session()
                                session.trust_env = False
                                res = session.get(
                                    full_url,
                                    headers={"Authorization": f"Bearer {jwt_token}"},
                                    verify=False,
                                    proxies=proxies
                                )
                                
                                if res.status_code == 200:
                                    code = self.extract_verification_code(res.text)
                                    if code:
                                        return code
                            except Exception as e:
                                logger.error(f"❌ 获取邮件内容失败: {e}")
            
            elapsed = int(time.time() - start_time)
            print(f"  等待中... ({elapsed}秒)", end="\r")
            time.sleep(3)
        
        logger.warning("⏰ 等待验证邮件超时")
        return None
    
    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """
        生成PKCE参数
        
        Returns:
            (code_verifier, code_challenge)
        """
        code_verifier_bytes = secrets.token_bytes(64)
        code_verifier = base64.urlsafe_b64encode(code_verifier_bytes).rstrip(b'=').decode('ascii')
        
        digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
        
        return code_verifier, code_challenge
    
    @staticmethod
    def generate_state() -> str:
        """生成随机state参数"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('ascii')
    
    @staticmethod
    def build_authorize_url(code_challenge: str, state: str) -> str:
        """构造OAuth授权URL"""
        params = {
            "response_type": "code",
            "client_id": config.OAUTH_CLIENT_ID,
            "redirect_uri": config.OAUTH_REDIRECT_URI,
            "scope": "openid profile email offline_access",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        query = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
        return f"{config.OAUTH_ISSUER}/oauth/authorize?{query}"
    
    def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
        proxies: Optional[Dict[str, str]] = None
    ) -> Optional[Dict]:
        """
        用authorization code换取tokens
        
        Args:
            code: 授权码
            code_verifier: PKCE验证码
            
        Returns:
            包含tokens的字典
        """
        try:
            if proxies is None:
                proxies = self.get_proxies_dict()
            
            session = requests.Session()
            session.trust_env = False
            response = session.post(
                f"{config.OAUTH_ISSUER}/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": config.OAUTH_REDIRECT_URI,
                    "client_id": config.OAUTH_CLIENT_ID,
                    "code_verifier": code_verifier,
                },
                proxies=proxies,
                verify=False,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"❌ Token交换失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Token交换异常: {e}")
        
        return None
    
    def wait_for_callback_url(
        self, 
        driver: uc.Chrome, 
        expected_state: str, 
        timeout: int = None
    ) -> Optional[str]:
        """
        等待OAuth回调URL
        
        Args:
            driver: Chrome驱动
            expected_state: 期望的state参数
            timeout: 超时时间
            
        Returns:
            回调URL
        """
        if timeout is None:
            timeout = config.OAUTH_CALLBACK_TIMEOUT
        
        logger.info(f"⏳ 等待OAuth回调（最长 {timeout}秒）...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_url = driver.current_url
            
            if "callback" in current_url and "code=" in current_url:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                state = params.get("state", [None])[0]
                
                if state == expected_state:
                    logger.info("✅ 收到OAuth回调")
                    return current_url

            # 如果停留在授权页，尝试点击“继续/允许”按钮触发回调
            self.try_click_oauth_consent(driver)
            
            time.sleep(1)
        
        logger.warning("⏰ 等待OAuth回调超时")
        return None

    def try_click_oauth_consent(self, driver: uc.Chrome) -> bool:
        """尝试点击OAuth授权页面的继续/允许按钮"""
        selectors = [
            'button[type="submit"]',
            'button[data-testid*="confirm"]',
            'button[data-testid*="allow"]'
        ]
        keywords = ["继续", "允许", "同意", "authorize", "allow", "continue", "accept"]

        for selector in selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    text = (btn.text or "").strip().lower()
                    if not text:
                        continue
                    if any(k in text for k in keywords):
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
                        return True
            except Exception:
                continue

        return False
    
    def check_and_handle_error(self, driver: uc.Chrome, max_retries: int = None) -> bool:
        """
        检查并处理错误页面
        
        Args:
            driver: Chrome驱动
            max_retries: 最大重试次数
            
        Returns:
            是否处理了错误
        """
        if max_retries is None:
            max_retries = config.MAX_ERROR_RETRIES
        
        for attempt in range(max_retries):
            try:
                page_source = driver.page_source.lower()
                error_keywords = [
                    "出错", "error", "timed out", 
                    "operation timeout", "route error", "invalid content"
                ]
                
                has_error = any(keyword in page_source for keyword in error_keywords)
                
                if has_error:
                    try:
                        retry_btn = driver.find_element(
                            By.CSS_SELECTOR, 'button[data-dd-action-name="Try again"]'
                        )
                        logger.warning(
                            f"⚠️ 检测到错误页面，点击重试（{attempt + 1}/{max_retries}）..."
                        )
                        driver.execute_script("arguments[0].click();", retry_btn)
                        wait_time = 5 + (attempt * 2)
                        time.sleep(wait_time)
                        return True
                    except Exception:
                        time.sleep(2)
                        continue
                
                return False
                
            except Exception as e:
                logger.error(f"❌ 错误检查异常: {e}")
                return False
        
        return False
    
    def save_account(self, email: str, password: str):
        """保存账号到文件"""
        with open(config.ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{email}:{password}\n")
        logger.info(f"✅ 账号已保存到 {config.ACCOUNTS_FILE}")
    
    def save_tokens(self, access_token: str, refresh_token: str = None):
        """保存tokens到文件"""
        if access_token:
            with open(config.AK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{access_token}\n")
            logger.info(f"✅ Access token已保存到 {config.AK_FILE}")
        
        if refresh_token:
            with open(config.RK_FILE, "a", encoding="utf-8") as f:
                f.write(f"{refresh_token}\n")
            logger.info(f"✅ Refresh token已保存到 {config.RK_FILE}")
    
    def save_account_json(
        self, 
        email: str, 
        password: str, 
        access_token: str, 
        refresh_token: str = None, 
        id_token: str = None
    ):
        """保存账号信息到JSON文件"""
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        expired = now + timedelta(days=10)
        
        # 解析account_id
        account_id = ""
        try:
            payload = access_token.split('.')[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            auth_info = decoded.get("https://api.openai.com/auth", {})
            account_id = auth_info.get("chatgpt_account_id", "")
        except:
            pass
        
        filename = f"codex-{email}.json"
        data = {
            "access_token": access_token,
            "account_id": account_id,
            "email": email,
            "expired": expired.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "id_token": id_token or "",
            "last_refresh": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "refresh_token": refresh_token or "",
            "type": "codex"
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 账号JSON已保存到 {filename}")
    
    def perform_oauth_login(
        self,
        driver: uc.Chrome,
        email: str,
        password: str,
        jwt_token: str = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> Optional[Dict]:
        """
        执行OAuth登录并获取tokens
        
        Args:
            driver: Chrome驱动
            email: 邮箱
            password: 密码
            jwt_token: 邮箱JWT令牌
            
        Returns:
            包含tokens的字典
        """
        logger.info("🔐 开始OAuth登录流程...")
        
        code_verifier, code_challenge = self.generate_pkce()
        state = self.generate_state()
        auth_url = self.build_authorize_url(code_challenge, state)
        
        # 在新标签页打开
        original_window = driver.current_window_handle
        driver.execute_script("window.open('', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(auth_url)
        time.sleep(3)
        
        try:
            # 输入邮箱
            logger.info("📧 输入邮箱...")
            email_input = WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'input[type="email"], input[name="email"], input[id="email"]')
                )
            )
            email_input.clear()
            time.sleep(0.3)
            for char in email:
                email_input.send_keys(char)
                time.sleep(0.03)
            
            # 点击继续
            continue_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            driver.execute_script("arguments[0].click();", continue_btn)
            time.sleep(3)
            
            # 输入密码
            logger.info("🔑 输入密码...")
            password_input = WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'input[type="password"], input[name="password"]')
                )
            )
            password_input.clear()
            time.sleep(0.3)
            for char in password:
                password_input.send_keys(char)
                time.sleep(0.03)
            
            # 点击继续
            continue_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            driver.execute_script("arguments[0].click();", continue_btn)
            time.sleep(3)
            
            # 检查是否需要二次验证
            current_url = driver.current_url
            if "email-verification" in current_url and jwt_token:
                logger.info("🔐 检测到二次邮箱验证...")
                verification_code = self.wait_for_verification_email(
                    email,
                    jwt_token,
                    proxies=proxies
                )
                
                if verification_code:
                    logger.info(f"✅ 获取到验证码: {verification_code}")
                    try:
                        code_inputs = driver.find_elements(
                            By.CSS_SELECTOR, 
                            'input[type="text"], input[inputmode="numeric"]'
                        )
                        
                        if len(code_inputs) >= 6:
                            for i, digit in enumerate(verification_code[:6]):
                                code_inputs[i].send_keys(digit)
                                time.sleep(0.1)
                        elif code_inputs:
                            code_inputs[0].clear()
                            code_inputs[0].send_keys(verification_code)
                        
                        time.sleep(2)
                        
                        try:
                            continue_btn = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
                            )
                            driver.execute_script("arguments[0].click();", continue_btn)
                            time.sleep(3)
                        except:
                            pass
                    except Exception as e:
                        logger.error(f"❌ 输入验证码失败: {e}")
            
            # 等待回调
            callback_url = self.wait_for_callback_url(driver, state)
            
            # 关闭标签页
            driver.close()
            driver.switch_to.window(original_window)
            
            if not callback_url:
                logger.error("❌ 未收到OAuth回调")
                return None
            
            # 提取code并交换tokens
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            
            if code:
                tokens = self.exchange_code_for_tokens(code, code_verifier, proxies=proxies)
                if tokens:
                    logger.info("✅ OAuth登录成功，已获取tokens")
                    return tokens
            
        except Exception as e:
            logger.error(f"❌ OAuth登录异常: {e}")
            try:
                driver.close()
                driver.switch_to.window(original_window)
            except:
                pass
        
        return None
    
    def register_one_account(
        self, 
        email: str = None, 
        password: str = None
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        注册一个账号
        
        Args:
            email: 邮箱（可选，不提供则自动创建）
            password: 密码（可选，不提供则自动生成）
            
        Returns:
            (邮箱, 密码, 是否成功)
        """
        driver = None
        success = False
        cf_token = None
        
        try:
            # 获取Selenium代理（每个账号固定一个代理）
            selenium_proxy = None
            if self.use_proxy and self.proxy_manager:
                selenium_proxy = self.proxy_manager.get_selenium_proxy(
                    retries=config.PROXY_API_RETRIES,
                    delay=config.PROXY_API_RETRY_DELAY,
                    local_proxy_url=(
                        config.PROXY_API_LOCAL_PROXY_URL
                        if getattr(config, "PROXY_API_USE_LOCAL_PROXY", False)
                        else None
                    )
                )
                if config.REQUIRE_SELENIUM_PROXY and not selenium_proxy:
                    logger.error("❌ 未获取到代理IP，终止当前账号注册")
                    return None, None, False

            request_proxies = self.build_proxy_dict(selenium_proxy)

            # 创建邮箱和密码
            if not email or not password:
                email, cf_token = self.create_temp_email(proxies=request_proxies)
                if not email:
                    logger.error("❌ 邮箱创建失败，终止注册")
                    return None, None, False

                password = self.generate_random_password()

            # 创建驱动
            driver = self.get_driver(selenium_proxy=selenium_proxy)
            
            # 访问OpenAI
            url = "https://chat.openai.com/chat"
            logger.info(f"🌐 访问 {url}...")
            driver.get(url)
            time.sleep(3)
            
            if config.SAVE_SCREENSHOTS:
                driver.save_screenshot("page_start.png")
            
            # 点击注册按钮
            logger.info("🖱️ 点击注册按钮...")
            signup_button = WebDriverWait(driver, 60).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="signup-button"]'))
            )
            signup_button.click()
            time.sleep(2)
            
            # 输入邮箱
            logger.info("📧 输入邮箱...")
            email_input = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((By.ID, "email"))
            )
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(1)
            
            # 点击继续
            continue_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            continue_btn.click()
            time.sleep(2)
            
            # 输入密码
            logger.info("🔑 输入密码...")
            password_input = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'input[autocomplete="new-password"]')
                )
            )
            password_input.clear()
            time.sleep(0.5)
            for char in password:
                password_input.send_keys(char)
                time.sleep(0.05)
            time.sleep(2)
            
            # 点击继续
            for attempt in range(3):
                try:
                    continue_btn = WebDriverWait(driver, 30).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
                    )
                    driver.execute_script("arguments[0].click();", continue_btn)
                    break
                except:
                    time.sleep(2)
            
            time.sleep(3)
            self.check_and_handle_error(driver)
            
            # 等待验证码
            logger.info("⏳ 等待邮件验证码...")
            verification_code = self.wait_for_verification_email(
                email,
                cf_token,
                proxies=request_proxies
            )
            
            if not verification_code:
                verification_code = input("请手动输入验证码: ").strip()
            
            if not verification_code:
                logger.error("❌ 未获取到验证码")
                return email, password, False
            
            # 输入验证码
            logger.info("🔢 输入验证码...")
            self.check_and_handle_error(driver)
            
            code_input = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'input[name="code"], input[placeholder*="代码"]')
                )
            )
            code_input.clear()
            time.sleep(0.5)
            for char in verification_code:
                code_input.send_keys(char)
                time.sleep(0.1)
            time.sleep(2)
            
            # 点击继续
            for attempt in range(3):
                try:
                    continue_btn = WebDriverWait(driver, 30).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
                    )
                    driver.execute_script("arguments[0].click();", continue_btn)
                    break
                except:
                    time.sleep(2)
            
            time.sleep(3)
            self.check_and_handle_error(driver)
            
            # 输入姓名
            logger.info("👤 输入姓名...")
            name_input = None
            name_selectors = [
                'input[name="name"]',
                'input[autocomplete="name"]',
                'input[type="text"]'
            ]
            
            for selector in name_selectors:
                try:
                    name_input = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if name_input:
                name_input.clear()
                time.sleep(0.5)
                for char in "John Doe":
                    name_input.send_keys(char)
                    time.sleep(0.05)
                time.sleep(1)
            
            # 输入生日
            logger.info("🎂 输入生日...")
            try:
                year_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-type="year"]'))
                )
                
                actions = ActionChains(driver)
                actions.click(year_input).perform()
                time.sleep(0.3)
                year_input.send_keys(Keys.CONTROL + "a")
                for char in "1990":
                    year_input.send_keys(char)
                    time.sleep(0.1)
                
                month_input = driver.find_element(By.CSS_SELECTOR, '[data-type="month"]')
                actions.click(month_input).perform()
                time.sleep(0.3)
                month_input.send_keys(Keys.CONTROL + "a")
                for char in "05":
                    month_input.send_keys(char)
                    time.sleep(0.1)
                
                day_input = driver.find_element(By.CSS_SELECTOR, '[data-type="day"]')
                actions.click(day_input).perform()
                time.sleep(0.3)
                day_input.send_keys(Keys.CONTROL + "a")
                for char in "12":
                    day_input.send_keys(char)
                    time.sleep(0.1)
                
                logger.info("✅ 生日输入完成: 1990/05/12")
            except Exception as e:
                logger.warning(f"⚠️ 生日输入失败: {e}")
                if config.SAVE_SCREENSHOTS:
                    driver.save_screenshot("birthday_error.png")
            
            time.sleep(1)
            
            # 点击最后的继续按钮
            continue_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            continue_btn.click()
            time.sleep(5)
            
            logger.info("✅ 注册流程完成，开始OAuth认证...")
            
            # 关闭当前驱动，创建新的驱动进行OAuth
            driver.quit()
            driver = None
            
            # 执行OAuth登录
            for retry in range(config.MAX_OAUTH_RETRIES):
                try:
                    driver = self.get_driver(selenium_proxy=selenium_proxy)
                    tokens = self.perform_oauth_login(
                        driver,
                        email,
                        password,
                        cf_token,
                        proxies=request_proxies
                    )
                    driver.quit()
                    driver = None
                    
                    if tokens:
                        break
                except Exception as e:
                    logger.error(f"❌ OAuth登录失败（{retry+1}/{config.MAX_OAUTH_RETRIES}）: {e}")
                    if driver:
                        driver.quit()
                        driver = None
                    time.sleep(2)
            
            if tokens:
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                id_token = tokens.get("id_token")
                
                # 保存账号信息
                self.save_account(email, password)
                self.save_tokens(access_token, refresh_token)
                self.save_account_json(email, password, access_token, refresh_token, id_token)
                
                logger.info("\n" + "=" * 60)
                logger.info("🎉 注册成功!")
                logger.info(f"📧 邮箱: {email}")
                logger.info(f"🔑 密码: {password}")
                logger.info(f"🎫 Access Token: {access_token[:20]}...")
                if refresh_token:
                    logger.info(f"🔄 Refresh Token: {refresh_token[:20]}...")
                logger.info("=" * 60)
                
                success = True
            else:
                logger.error("❌ 未能获取OAuth tokens")
                self.save_account(email, password)
        
        except Exception as e:
            logger.error(f"❌ 注册过程发生异常: {e}")
            if email and password:
                self.save_account(email, password)
        
        finally:
            if driver:
                driver.quit()
        
        return email, password, success
    
    def run_batch(self, total_accounts: int = None):
        """
        批量注册账号
        
        Args:
            total_accounts: 注册账号数量
        """
        if total_accounts is None:
            total_accounts = config.TOTAL_ACCOUNTS
        
        logger.info("\n" + "=" * 70)
        logger.info(f"🚀 开始批量注册，目标账号数: {total_accounts}")
        logger.info("=" * 70 + "\n")
        
        success_count = 0
        fail_count = 0
        registered_accounts = []
        
        for i in range(total_accounts):
            logger.info("\n" + "#" * 70)
            logger.info(f"📝 正在注册第 {i + 1}/{total_accounts} 个账号")
            logger.info("#" * 70 + "\n")
            
            email, password, success = self.register_one_account()
            
            if success:
                success_count += 1
                registered_accounts.append((email, password))
            else:
                fail_count += 1
            
            logger.info("\n" + "-" * 50)
            logger.info(f"📊 当前进度: {i + 1}/{total_accounts}")
            logger.info(f"   ✅ 成功: {success_count}")
            logger.info(f"   ❌ 失败: {fail_count}")
            logger.info("-" * 50)
            
            # 账号之间的等待
            if i < total_accounts - 1:
                wait_time = random.randint(
                    config.MIN_WAIT_BETWEEN_ACCOUNTS,
                    config.MAX_WAIT_BETWEEN_ACCOUNTS
                )
                logger.info(f"\n⏳ 等待 {wait_time}秒后继续...")
        
        # 最终统计
        logger.info("\n" + "=" * 70)
        logger.info("🏁 批量注册完成!")
        logger.info("=" * 70)
        logger.info(f"总计: {total_accounts} 个账号")
        logger.info(f"✅ 成功: {success_count} 个")
        logger.info(f"❌ 失败: {fail_count} 个")
        logger.info(f"📈 成功率: {success_count/total_accounts*100:.1f}%")
        logger.info("\n结果保存位置:")
        logger.info(f"  📄 账号密码: {config.ACCOUNTS_FILE}")
        logger.info(f"  🎫 Access Tokens: {config.AK_FILE}")
        logger.info(f"  🔄 Refresh Tokens: {config.RK_FILE}")
        logger.info(f"  📋 JSON文件: codex-*.json")
        logger.info("=" * 70)


def main():
    """主函数"""
    logger.info("=" * 70)
    logger.info("OpenAI 账号注册机 - 集成代理版本")
    logger.info("=" * 70 + "\n")
    
    # 创建注册机器人
    bot = OpenAIRegistrationBot(use_proxy=config.USE_PROXY)
    
    # 执行批量注册
    if config.TEST_MODE:
        logger.info("⚠️ 测试模式：只注册1个账号")
        bot.run_batch(total_accounts=1)
    else:
        bot.run_batch()


if __name__ == "__main__":
    main()

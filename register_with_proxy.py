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
from selenium.common.exceptions import TimeoutException, WebDriverException
# webdriver_manager removed - uc manages its own driver
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
            
            # 先获取代理IP，再通过代理测试连接
            test_proxy = self.proxy_manager.get_selenium_proxy(retries=2, delay=2)
            if test_proxy:
                if self.proxy_manager.test_connection(proxy_address=test_proxy):
                    logger.info("✅ 代理连接测试通过")
                else:
                    logger.warning("⚠️ 代理连接测试失败，请检查代理是否可用")
            else:
                logger.warning("⚠️ 未能获取代理IP")
    
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

    def _find_visible_in_frames(self, driver, by, selector):
        """在主文档及iframe中查找可见元素。"""
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

        try:
            el = driver.find_element(by, selector)
            if el.is_displayed():
                return el
        except Exception:
            pass

        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            iframes = []

        for frame in iframes:
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(frame)
                el = driver.find_element(by, selector)
                if el.is_displayed():
                    return el
            except Exception:
                continue
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

        return None

    def wait_for_any_visible(self, driver, selectors, timeout=60, poll=0.5):
        """等待多个选择器之一可见，支持iframe。"""
        end_time = time.time() + timeout
        last_error = None
        while time.time() < end_time:
            for by, selector in selectors:
                try:
                    el = self._find_visible_in_frames(driver, by, selector)
                    if el:
                        return el
                except Exception as e:
                    last_error = e
            time.sleep(poll)
        selector_str = ", ".join([f"{by}={sel}" for by, sel in selectors])
        raise TimeoutException(f"等待元素超时: {selector_str}") from last_error

    def click_first_clickable(self, driver, selectors, timeout=30, poll=0.5):
        """点击首个可点击的元素，失败则抛出TimeoutException。"""
        end_time = time.time() + timeout
        last_error = None
        while time.time() < end_time:
            for by, selector in selectors:
                try:
                    el = self._find_visible_in_frames(driver, by, selector)
                    if not el:
                        continue
                    if el.is_enabled():
                        try:
                            driver.execute_script(
                                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                                el,
                            )
                        except Exception:
                            pass
                        try:
                            el.click()
                        except WebDriverException:
                            driver.execute_script("arguments[0].click();", el)
                        return True
                except Exception as e:
                    last_error = e
            time.sleep(poll)
        selector_str = ", ".join([f"{by}={sel}" for by, sel in selectors])
        raise TimeoutException(f"点击元素超时: {selector_str}") from last_error

    def fill_input(self, driver, element, value, char_delay=0.05):
        """稳健输入：优先逐字输入，失败则用JS赋值并触发事件。"""
        try:
            element.click()
        except Exception:
            pass

        try:
            element.clear()
        except Exception:
            pass

        try:
            for char in value:
                element.send_keys(char)
                time.sleep(char_delay)
            return True
        except WebDriverException:
            pass

        try:
            driver.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                element,
                value,
            )
            return True
        except Exception:
            return False
    
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
    
    def _input_birthday_method1(self, driver: uc.Chrome) -> bool:
        """生日输入方式1: data-type属性选择器"""
        try:
            # 尝试找到年份输入框
            year_selectors = [
                '[data-type="year"]',
                'input[name="year"]',
                'input[placeholder*="年"]',
                'input[placeholder*="YYYY"]',
                'input[aria-label*="year"]',
            ]
            
            year_input = None
            for selector in year_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            year_input = el
                            logger.info(f"📅 找到年份输入框: {selector}")
                            break
                    if year_input:
                        break
                except Exception:
                    continue
            
            if not year_input:
                return False
            
            # 清空并输入年份
            self._safe_input_date_field(driver, year_input, "1990")
            time.sleep(0.3)
            
            # 找月份输入框
            month_selectors = [
                '[data-type="month"]',
                'input[name="month"]',
                'input[placeholder*="月"]',
                'input[placeholder*="MM"]',
                'input[aria-label*="month"]',
            ]
            
            month_input = None
            for selector in month_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            month_input = el
                            break
                    if month_input:
                        break
                except Exception:
                    continue
            
            if month_input:
                self._safe_input_date_field(driver, month_input, "05")
                time.sleep(0.3)
            
            # 找日期输入框
            day_selectors = [
                '[data-type="day"]',
                'input[name="day"]',
                'input[placeholder*="日"]',
                'input[placeholder*="DD"]',
                'input[aria-label*="day"]',
            ]
            
            day_input = None
            for selector in day_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            day_input = el
                            break
                    if day_input:
                        break
                except Exception:
                    continue
            
            if day_input:
                self._safe_input_date_field(driver, day_input, "12")
            
            return True
            
        except Exception as e:
            logger.debug(f"生日方式1失败: {e}")
            return False
    
    def _input_birthday_method2(self, driver: uc.Chrome) -> bool:
        """生日输入方式2: 查找所有数字输入框"""
        try:
            # 查找页面上所有可能的日期输入框
            inputs = driver.find_elements(
                By.CSS_SELECTOR,
                'input[type="text"], input[type="number"], input[inputmode="numeric"]'
            )
            
            visible_inputs = [inp for inp in inputs if inp.is_displayed()]
            
            # 如果有3个可见的数字输入框，可能是年/月/日
            if len(visible_inputs) >= 3:
                logger.info(f"📅 找到 {len(visible_inputs)} 个可见输入框，尝试按顺序填入")
                
                # 尝试识别哪个是年/月/日
                date_values = {
                    "year": "1990",
                    "month": "05", 
                    "day": "12"
                }
                
                filled_count = 0
                for inp in visible_inputs[:3]:
                    try:
                        placeholder = inp.get_attribute("placeholder") or ""
                        name = inp.get_attribute("name") or ""
                        aria_label = inp.get_attribute("aria-label") or ""
                        data_type = inp.get_attribute("data-type") or ""
                        
                        # 根据属性判断类型
                        field_info = (placeholder + name + aria_label + data_type).lower()
                        
                        if "year" in field_info or "年" in field_info or "yyyy" in field_info:
                            self._safe_input_date_field(driver, inp, date_values["year"])
                            filled_count += 1
                        elif "month" in field_info or "月" in field_info or "mm" in field_info:
                            self._safe_input_date_field(driver, inp, date_values["month"])
                            filled_count += 1
                        elif "day" in field_info or "日" in field_info or "dd" in field_info:
                            self._safe_input_date_field(driver, inp, date_values["day"])
                            filled_count += 1
                        
                        time.sleep(0.2)
                    except Exception:
                        continue
                
                # 如果没有通过属性识别成功，按顺序填入（月/日/年 或 年/月/日）
                if filled_count == 0:
                    logger.info("📅 按顺序填入日期...")
                    # 假设是 月/日/年 格式（美国格式）
                    try:
                        self._safe_input_date_field(driver, visible_inputs[0], "05")
                        time.sleep(0.2)
                        self._safe_input_date_field(driver, visible_inputs[1], "12")
                        time.sleep(0.2)
                        self._safe_input_date_field(driver, visible_inputs[2], "1990")
                        return True
                    except Exception:
                        pass
                
                return filled_count > 0
            
            return False
            
        except Exception as e:
            logger.debug(f"生日方式2失败: {e}")
            return False
    
    def _input_birthday_method3(self, driver: uc.Chrome) -> bool:
        """生日输入方式3: 下拉选择框"""
        try:
            # 查找 select 元素
            selects = driver.find_elements(By.TAG_NAME, "select")
            visible_selects = [s for s in selects if s.is_displayed()]
            
            if len(visible_selects) >= 3:
                logger.info(f"📅 找到 {len(visible_selects)} 个下拉框，尝试选择日期")
                
                from selenium.webdriver.support.ui import Select
                
                for sel in visible_selects:
                    try:
                        name = sel.get_attribute("name") or ""
                        aria_label = sel.get_attribute("aria-label") or ""
                        field_id = sel.get_attribute("id") or ""
                        field_info = (name + aria_label + field_id).lower()
                        
                        select_obj = Select(sel)
                        
                        if "year" in field_info or "年" in field_info:
                            select_obj.select_by_value("1990")
                        elif "month" in field_info or "月" in field_info:
                            select_obj.select_by_value("5")
                        elif "day" in field_info or "日" in field_info:
                            select_obj.select_by_value("12")
                        
                        time.sleep(0.2)
                    except Exception:
                        continue
                
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"生日方式3失败: {e}")
            return False
    
    def _input_birthday_method4(self, driver: uc.Chrome) -> bool:
        """生日输入方式4: 单个日期输入框 (date picker)"""
        try:
            # 查找 date 类型输入框
            date_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="date"]')
            
            for date_input in date_inputs:
                if date_input.is_displayed():
                    logger.info("📅 找到日期选择器")
                    try:
                        # 格式: YYYY-MM-DD
                        driver.execute_script(
                            "arguments[0].value = '1990-05-12';"
                            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                            date_input
                        )
                        return True
                    except Exception:
                        pass
            
            # 查找单个文本框可能用于完整日期
            single_date_selectors = [
                'input[placeholder*="birthday"]',
                'input[placeholder*="生日"]',
                'input[placeholder*="date of birth"]',
                'input[name*="birthday"]',
                'input[name*="dob"]',
            ]
            
            for selector in single_date_selectors:
                try:
                    inputs = driver.find_elements(By.CSS_SELECTOR, selector)
                    for inp in inputs:
                        if inp.is_displayed():
                            self.fill_input(driver, inp, "05/12/1990", char_delay=0.05)
                            return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"生日方式4失败: {e}")
            return False
    
    def _safe_input_date_field(self, driver: uc.Chrome, element, value: str):
        """安全地输入日期字段值"""
        try:
            # 先点击元素
            try:
                element.click()
            except Exception:
                driver.execute_script("arguments[0].click();", element)
            time.sleep(0.1)
            
            # 尝试清空
            try:
                element.clear()
            except Exception:
                pass
            
            # 尝试全选 (三击)
            try:
                actions = ActionChains(driver)
                actions.triple_click(element).perform()
                time.sleep(0.1)
            except Exception:
                pass
            
            # 逐字输入
            try:
                for char in value:
                    element.send_keys(char)
                    time.sleep(0.05)
                return True
            except Exception:
                pass
            
            # 如果 send_keys 失败，用 JS
            try:
                driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    element,
                    value
                )
                return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            logger.debug(f"日期字段输入失败: {e}")
            return False
    
    def _debug_page_elements(self, driver: uc.Chrome, step_name: str):
        """调试：打印页面关键元素信息"""
        try:
            logger.info(f"🔍 调试 [{step_name}] 页面元素...")
            
            # 当前URL
            logger.info(f"   URL: {driver.current_url}")
            
            # 查找所有输入框
            inputs = driver.find_elements(By.TAG_NAME, "input")
            visible_inputs = [inp for inp in inputs if inp.is_displayed()]
            logger.info(f"   可见输入框数量: {len(visible_inputs)}")
            
            for i, inp in enumerate(visible_inputs[:10]):  # 最多显示10个
                try:
                    inp_type = inp.get_attribute("type") or "text"
                    inp_name = inp.get_attribute("name") or ""
                    inp_id = inp.get_attribute("id") or ""
                    inp_placeholder = inp.get_attribute("placeholder") or ""
                    inp_data_type = inp.get_attribute("data-type") or ""
                    inp_aria = inp.get_attribute("aria-label") or ""
                    
                    logger.info(
                        f"   输入框{i+1}: type={inp_type}, name={inp_name}, "
                        f"id={inp_id}, placeholder={inp_placeholder}, "
                        f"data-type={inp_data_type}, aria-label={inp_aria}"
                    )
                except Exception:
                    pass
            
            # 查找所有按钮
            buttons = driver.find_elements(By.TAG_NAME, "button")
            visible_buttons = [btn for btn in buttons if btn.is_displayed()]
            logger.info(f"   可见按钮数量: {len(visible_buttons)}")
            
            for i, btn in enumerate(visible_buttons[:5]):  # 最多显示5个
                try:
                    btn_text = btn.text or ""
                    btn_type = btn.get_attribute("type") or ""
                    logger.info(f"   按钮{i+1}: text={btn_text}, type={btn_type}")
                except Exception:
                    pass
            
            # 查找下拉框
            selects = driver.find_elements(By.TAG_NAME, "select")
            visible_selects = [s for s in selects if s.is_displayed()]
            if visible_selects:
                logger.info(f"   可见下拉框数量: {len(visible_selects)}")
            
            # 保存页面源码片段
            if config.SAVE_SCREENSHOTS:
                try:
                    with open(f"debug_{step_name}_page.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    logger.info(f"   页面HTML已保存到 debug_{step_name}_page.html")
                except Exception:
                    pass
                    
        except Exception as e:
            logger.debug(f"调试输出失败: {e}")

    
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

    def _navigate_to_cpa_oauth_page(self, driver: uc.Chrome, max_attempts: int = 6) -> bool:
        for _ in range(max_attempts):
            try:
                driver.get(config.CPA_MANAGEMENT_URL)
            except Exception:
                pass
            time.sleep(2)
            if driver.find_elements(By.CSS_SELECTOR, "div.card"):
                return True

            try:
                nav_candidates = driver.find_elements(
                    By.XPATH,
                    "//a[contains(., 'OAuth') or contains(., 'oauth') or contains(., '授权') or contains(., '认证')] | "
                    "//button[contains(., 'OAuth') or contains(., 'oauth') or contains(., '授权') or contains(., '认证')]",
                )
                for el in nav_candidates:
                    if not el.is_displayed():
                        continue
                    try:
                        driver.execute_script("arguments[0].click();", el)
                    except Exception:
                        el.click()
                    time.sleep(1)
            except Exception:
                pass

            if driver.find_elements(By.CSS_SELECTOR, "div.card"):
                return True

        return False

    def login_cpa_panel(self, driver: uc.Chrome) -> bool:
        if not self._navigate_to_cpa_oauth_page(driver):
            logger.error("❌ 打开CPA面板失败")
            return False

        if not config.CPA_PASSWORD:
            return True

        try:
            pwd_input = self.wait_for_any_visible(
                driver,
                [(By.CSS_SELECTOR, 'input[type="password"]')],
                timeout=8,
            )
            self.fill_input(driver, pwd_input, config.CPA_PASSWORD, char_delay=0.02)
            login_selectors = [
                (By.CSS_SELECTOR, "button.btn.btn-primary"),
                (By.XPATH, "//button[contains(., 'Login') or contains(., '登录') or contains(., 'Sign in')]"),
            ]
            self.click_first_clickable(driver, login_selectors, timeout=8)
            time.sleep(2)
            return self._navigate_to_cpa_oauth_page(driver)
        except TimeoutException:
            # 可能已登录
            return True
        except Exception as e:
            logger.error(f"❌ CPA登录失败: {e}")
            return False

    def _get_cpa_oauth_card(self, driver: uc.Chrome):
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.card, .card")
            for card in cards:
                text = (card.text or "").lower()
                if "codex" in text or "openai" in text:
                    return card
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_auth_url_from_text(text: str) -> Optional[str]:
        if not text:
            return None
        urls = re.findall(
            r'https://auth\.openai\.com/(?:oauth/)?authorize[^\s<>"\')]+',
            text,
        )
        if urls:
            return urls[0].replace("&amp;", "&")
        return None

    def _extract_auth_url_from_card(self, driver: uc.Chrome, card) -> Optional[str]:
        try:
            try:
                link = card.find_element(By.CSS_SELECTOR, 'a[href*="auth.openai.com"]')
                href = link.get_attribute("href")
                if href:
                    return href.replace("&amp;", "&")
            except Exception:
                pass

            card_text = card.text
            auth_url = self._extract_auth_url_from_text(card_text)
            if auth_url:
                return auth_url

            page_source = driver.page_source
            return self._extract_auth_url_from_text(page_source)
        except Exception:
            return None

    def get_cpa_auth_link(self, driver: uc.Chrome) -> Optional[str]:
        logger.info("🔗 获取CPA OAuth链接...")
        if not self.login_cpa_panel(driver):
            return None

        card = self._get_cpa_oauth_card(driver)
        if not card:
            logger.error("❌ 未找到CPA OAuth卡片")
            return None

        auth_url = self._extract_auth_url_from_card(driver, card)
        if auth_url:
            return auth_url

        # 尝试点击卡片中的登录/授权按钮以生成链接
        try:
            login_btns = card.find_elements(
                By.XPATH,
                ".//button[contains(., 'Login') or contains(., '登录') or contains(., '授权') or contains(., 'Authorize')] | "
                ".//a[contains(., 'Login') or contains(., '登录') or contains(., '授权') or contains(., 'Authorize')]",
            )
            for btn in login_btns:
                if not btn.is_displayed():
                    continue
                try:
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    btn.click()
                time.sleep(1)
        except Exception:
            pass

        for _ in range(10):
            time.sleep(1)
            card = self._get_cpa_oauth_card(driver)
            if not card:
                continue
            auth_url = self._extract_auth_url_from_card(driver, card)
            if auth_url:
                return auth_url

        return None

    def perform_openai_oauth_login_in_new_window(
        self,
        driver: uc.Chrome,
        auth_link: str,
        email: str,
        password: str,
    ) -> Optional[str]:
        logger.info("🌐 在新窗口执行OAuth授权...")
        original_window = driver.current_window_handle
        driver.execute_script("window.open('', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(auth_link)
        time.sleep(3)

        start_time = time.time()
        callback_url = None
        email_entered = False
        password_entered = False

        while time.time() - start_time < config.CPA_OAUTH_TIMEOUT:
            try:
                current_url = driver.current_url
                # 检测成功回调：必须包含 code= 参数
                if ("localhost" in current_url or "127.0.0.1" in current_url):
                    if "code=" in current_url:
                        logger.info(f"✅ 获取CPA回调URL: {current_url[:60]}...")
                        callback_url = current_url
                        break

                # 可能已经显示成功页
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    if "Authentication successful" in body_text or "Token saved" in body_text:
                        logger.info("✅ 检测到认证成功页面")
                        callback_url = current_url
                        break
                except Exception:
                    pass

                # 邮箱输入（使用与注册流程一致的方式）
                if not email_entered:
                    email_selectors = [
                        (By.CSS_SELECTOR, 'input[type="email"]'),
                        (By.CSS_SELECTOR, 'input[name="email"]'),
                        (By.ID, "email"),
                        (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
                    ]
                    for by, selector in email_selectors:
                        try:
                            email_input = self._find_visible_in_frames(driver, by, selector)
                            if email_input and email_input.is_displayed():
                                logger.info("📧 CPA OAuth: 输入邮箱...")
                                self.fill_input(driver, email_input, email, char_delay=0.03)
                                time.sleep(1)
                                
                                # 点击继续按钮
                                continue_selectors = [
                                    (By.CSS_SELECTOR, 'button[type="submit"]'),
                                    (By.XPATH, "//button[contains(., 'Continue') or contains(., '继续')]"),
                                ]
                                try:
                                    self.click_first_clickable(driver, continue_selectors, timeout=5)
                                except TimeoutException:
                                    try:
                                        email_input.send_keys(Keys.ENTER)
                                    except Exception:
                                        pass
                                
                                email_entered = True
                                time.sleep(3)
                                break
                        except Exception:
                            continue

                # 密码输入（使用与注册流程一致的方式）
                if email_entered and not password_entered:
                    password_selectors = [
                        (By.CSS_SELECTOR, 'input[type="password"]'),
                        (By.CSS_SELECTOR, 'input[name="password"]'),
                        (By.CSS_SELECTOR, 'input[autocomplete="current-password"]'),
                    ]
                    for by, selector in password_selectors:
                        try:
                            password_input = self._find_visible_in_frames(driver, by, selector)
                            if password_input and password_input.is_displayed():
                                logger.info("🔑 CPA OAuth: 输入密码...")
                                self.fill_input(driver, password_input, password, char_delay=0.03)
                                time.sleep(1)
                                
                                # 点击继续按钮
                                continue_selectors = [
                                    (By.CSS_SELECTOR, 'button[type="submit"]'),
                                    (By.XPATH, "//button[contains(., 'Continue') or contains(., '继续')]"),
                                ]
                                try:
                                    self.click_first_clickable(driver, continue_selectors, timeout=5)
                                except TimeoutException:
                                    try:
                                        password_input.send_keys(Keys.ENTER)
                                    except Exception:
                                        pass
                                
                                password_entered = True
                                time.sleep(3)
                                break
                        except Exception:
                            continue

                # 授权/继续按钮（使用与注册流程一致的方式）
                keywords = [
                    "continue", "authorize", "allow", "yes", "accept", "confirm",
                    "继续", "授权", "允许", "确定", "确认", "接受",
                ]
                try:
                    btns = driver.find_elements(By.CSS_SELECTOR, "button")
                    for btn in btns:
                        try:
                            if not btn.is_displayed():
                                continue
                            text = (btn.text or "").lower()
                            # 跳过登录/注册按钮
                            if any(x in text for x in ["login", "sign up", "登录", "注册"]):
                                continue
                            if any(k in text for k in keywords):
                                logger.info(f"🔘 点击按钮: {btn.text}")
                                try:
                                    driver.execute_script("arguments[0].click();", btn)
                                except Exception:
                                    btn.click()
                                time.sleep(1)
                        except Exception:
                            continue
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"CPA OAuth流程循环异常: {e}")

            time.sleep(1)

        try:
            driver.close()
            driver.switch_to.window(original_window)
        except Exception:
            pass

        return callback_url

    def submit_cpa_callback_via_api(self, callback_url: str) -> bool:
        logger.info("📡 提交CPA回调...")
        try:
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            state = params.get("state", [None])[0]
            if not state:
                logger.info("✅ 未找到state参数，视为授权已完成")
                return True

            api_endpoint = f"{config.CPA_API_BASE}/v0/management/oauth-callback"
            payload = {"provider": "codex", "redirect_url": callback_url, "state": state}
            headers = {"Content-Type": "application/json"}
            if config.CPA_PASSWORD:
                headers["Authorization"] = f"Bearer {config.CPA_PASSWORD}"
                headers["X-Management-Key"] = config.CPA_PASSWORD

            session = requests.Session()
            session.trust_env = False
            res = session.post(api_endpoint, json=payload, headers=headers, timeout=30)
            if res.status_code == 200 and res.json().get("status") == "ok":
                logger.info("✅ CPA回调提交成功")
                return True
            if res.status_code == 404 and "expired" in res.text.lower():
                logger.info("✅ CPA提示state已过期，可能已自动完成授权")
                return True
            logger.error(f"❌ CPA回调提交失败: {res.status_code} - {res.text[:200]}")
        except Exception as e:
            logger.error(f"❌ CPA回调提交异常: {e}")
        return False

    def import_to_cpa(self, driver: uc.Chrome, email: str, password: str) -> bool:
        auth_link = self.get_cpa_auth_link(driver)
        if not auth_link:
            logger.error("❌ 获取CPA授权链接失败")
            return False

        callback_url = self.perform_openai_oauth_login_in_new_window(
            driver,
            auth_link,
            email,
            password,
        )
        if not callback_url:
            logger.error("❌ 未获取CPA回调URL")
            return False

        return self.submit_cpa_callback_via_api(callback_url)
    
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
        
        start_time = time.time()
        max_wait = config.OAUTH_CALLBACK_TIMEOUT
        callback_url = None
        email_entered = False
        password_entered = False
        verification_handled = False  # 防止重复处理二次验证
        
        try:
            while time.time() - start_time < max_wait:
                try:
                    current_url = driver.current_url
                    
                    # 检查是否已经回调
                    if "callback" in current_url and "code=" in current_url:
                        parsed = urlparse(current_url)
                        params = parse_qs(parsed.query)
                        url_state = params.get("state", [None])[0]
                        if url_state == state:
                            logger.info("✅ 收到OAuth回调")
                            callback_url = current_url
                            break
                    
                    # 输入邮箱（使用与注册流程一致的方式）
                    if not email_entered:
                        email_selectors = [
                            (By.CSS_SELECTOR, 'input[type="email"]'),
                            (By.CSS_SELECTOR, 'input[name="email"]'),
                            (By.ID, "email"),
                            (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
                        ]
                        for by, selector in email_selectors:
                            try:
                                email_input = self._find_visible_in_frames(driver, by, selector)
                                if email_input and email_input.is_displayed():
                                    logger.info("📧 输入邮箱...")
                                    self.fill_input(driver, email_input, email, char_delay=0.03)
                                    time.sleep(1)
                                    
                                    # 点击继续按钮
                                    continue_selectors = [
                                        (By.CSS_SELECTOR, 'button[type="submit"]'),
                                        (By.XPATH, "//button[contains(., 'Continue') or contains(., '继续')]"),
                                    ]
                                    try:
                                        self.click_first_clickable(driver, continue_selectors, timeout=5)
                                    except TimeoutException:
                                        try:
                                            email_input.send_keys(Keys.ENTER)
                                        except Exception:
                                            pass
                                    
                                    email_entered = True
                                    time.sleep(3)
                                    break
                            except Exception:
                                continue
                    
                    # 输入密码（使用与注册流程一致的方式）
                    if email_entered and not password_entered:
                        password_selectors = [
                            (By.CSS_SELECTOR, 'input[type="password"]'),
                            (By.CSS_SELECTOR, 'input[name="password"]'),
                            (By.CSS_SELECTOR, 'input[autocomplete="current-password"]'),
                        ]
                        for by, selector in password_selectors:
                            try:
                                password_input = self._find_visible_in_frames(driver, by, selector)
                                if password_input and password_input.is_displayed():
                                    logger.info("🔑 输入密码...")
                                    self.fill_input(driver, password_input, password, char_delay=0.03)
                                    time.sleep(1)
                                    
                                    # 点击继续按钮
                                    continue_selectors = [
                                        (By.CSS_SELECTOR, 'button[type="submit"]'),
                                        (By.XPATH, "//button[contains(., 'Continue') or contains(., '继续')]"),
                                    ]
                                    try:
                                        self.click_first_clickable(driver, continue_selectors, timeout=5)
                                    except TimeoutException:
                                        try:
                                            password_input.send_keys(Keys.ENTER)
                                        except Exception:
                                            pass
                                    
                                    password_entered = True
                                    time.sleep(3)
                                    break
                            except Exception:
                                continue
                    
                    # 检查是否需要二次邮箱验证（只处理一次）
                    current_url = driver.current_url
                    if "email-verification" in current_url and jwt_token and not verification_handled:
                        logger.info("🔐 检测到二次邮箱验证...")
                        verification_handled = True  # 标记已处理，防止重复
                        verification_code = self.wait_for_verification_email(
                            email,
                            jwt_token,
                            timeout=60,
                            proxies=proxies
                        )
                        
                        if verification_code:
                            logger.info(f"✅ 获取到验证码: {verification_code}")
                            code_selectors = [
                                (By.CSS_SELECTOR, 'input[name="code"]'),
                                (By.CSS_SELECTOR, 'input[inputmode="numeric"]'),
                                (By.CSS_SELECTOR, 'input[type="text"]'),
                            ]
                            for by, selector in code_selectors:
                                try:
                                    code_inputs = driver.find_elements(by, selector)
                                    if len(code_inputs) >= 6:
                                        # 多个输入框，逐个填入
                                        for i, digit in enumerate(verification_code[:6]):
                                            self.fill_input(driver, code_inputs[i], digit, char_delay=0.05)
                                            time.sleep(0.1)
                                        break
                                    elif code_inputs:
                                        # 单个输入框
                                        self.fill_input(driver, code_inputs[0], verification_code, char_delay=0.05)
                                        break
                                except Exception:
                                    continue
                            
                            time.sleep(2)
                            # 尝试点击继续按钮
                            try:
                                continue_selectors = [
                                    (By.CSS_SELECTOR, 'button[type="submit"]'),
                                ]
                                self.click_first_clickable(driver, continue_selectors, timeout=5)
                            except TimeoutException:
                                pass
                            time.sleep(3)
                        else:
                            logger.warning("⚠️ 未获取到二次验证码")
                    
                    # 尝试点击授权/继续按钮
                    self.try_click_oauth_consent(driver)
                    
                except Exception as e:
                    logger.debug(f"OAuth流程循环异常: {e}")
                
                time.sleep(1)
            
            # 关闭标签页
            try:
                driver.close()
                driver.switch_to.window(original_window)
            except Exception:
                pass
            
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
            signup_selectors = [
                (By.CSS_SELECTOR, '[data-testid="signup-button"]'),
                (By.XPATH, "//a[contains(., 'Sign up') or contains(., '注册') or contains(., 'Sign Up')]"),
                (By.XPATH, "//button[contains(., 'Sign up') or contains(., '注册') or contains(., 'Sign Up')]"),
            ]
            try:
                self.click_first_clickable(driver, signup_selectors, timeout=20)
                time.sleep(2)
            except TimeoutException:
                logger.warning("⚠️ 未找到注册按钮，尝试直接打开注册页...")
                driver.get("https://chat.openai.com/auth/signup")
                time.sleep(2)
            
            # 输入邮箱
            logger.info("📧 输入邮箱...")
            email_selectors = [
                (By.ID, "email"),
                (By.CSS_SELECTOR, 'input[type="email"]'),
                (By.CSS_SELECTOR, 'input[name="email"]'),
                (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
            ]
            email_input = self.wait_for_any_visible(driver, email_selectors, timeout=60)
            self.fill_input(driver, email_input, email, char_delay=0.03)
            time.sleep(1)
            
            # 点击继续
            continue_selectors = [
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.XPATH, "//button[contains(., 'Continue') or contains(., 'Next') or contains(., '继续') or contains(., '下一步')]"),
            ]
            self.click_first_clickable(driver, continue_selectors, timeout=30)
            time.sleep(2)
            
            # 输入密码
            logger.info("🔑 输入密码...")
            password_selectors = [
                (By.CSS_SELECTOR, 'input[autocomplete="new-password"]'),
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.CSS_SELECTOR, 'input[name="password"]'),
            ]
            password_input = self.wait_for_any_visible(driver, password_selectors, timeout=60)
            time.sleep(0.3)
            self.fill_input(driver, password_input, password, char_delay=0.03)
            time.sleep(2)
            
            # 点击继续
            for attempt in range(3):
                try:
                    self.click_first_clickable(driver, continue_selectors, timeout=30)
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
            
            code_selectors = [
                (By.CSS_SELECTOR, 'input[name="code"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="代码"]'),
                (By.CSS_SELECTOR, 'input[inputmode="numeric"]'),
            ]
            code_input = self.wait_for_any_visible(driver, code_selectors, timeout=60)
            time.sleep(0.3)
            self.fill_input(driver, code_input, verification_code, char_delay=0.05)
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
            birthday_success = False
            try:
                # 保存当前页面截图用于调试
                if config.SAVE_SCREENSHOTS:
                    driver.save_screenshot("birthday_before.png")
                
                # 打印页面HTML片段用于调试
                try:
                    page_source = driver.page_source
                    logger.debug(f"页面长度: {len(page_source)}")
                except Exception:
                    pass
                
                # 尝试多种生日输入方式
                birthday_success = self._input_birthday_method1(driver)
                
                if not birthday_success:
                    logger.info("🔄 尝试备选方案2...")
                    birthday_success = self._input_birthday_method2(driver)
                
                if not birthday_success:
                    logger.info("🔄 尝试备选方案3 (下拉选择)...")
                    birthday_success = self._input_birthday_method3(driver)
                
                if not birthday_success:
                    logger.info("🔄 尝试备选方案4 (日期选择器)...")
                    birthday_success = self._input_birthday_method4(driver)
                
                if birthday_success:
                    logger.info("✅ 生日输入完成: 1990/05/12")
                else:
                    logger.warning("⚠️ 所有生日输入方式都失败，尝试继续...")
                    
            except Exception as e:
                logger.warning(f"⚠️ 生日输入失败: {e}")
                if config.SAVE_SCREENSHOTS:
                    driver.save_screenshot("birthday_error.png")
                # 尝试截取页面元素信息
                self._debug_page_elements(driver, "birthday")
            
            time.sleep(1)
            
            # 点击最后的继续按钮
            continue_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
            )
            continue_btn.click()
            time.sleep(5)
            
            logger.info("✅ 注册流程完成")

            if config.USE_CPA_IMPORT:
                logger.info("🔗 开始导入CPA...")
                try:
                    if self.import_to_cpa(driver, email, password):
                        logger.info("✅ CPA导入成功")
                    else:
                        logger.warning("⚠️ CPA导入失败")
                except Exception as e:
                    logger.error(f"❌ CPA导入异常: {e}")

            logger.info("🔐 开始OAuth认证...")
            
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
            if config.SAVE_SCREENSHOTS and driver:
                try:
                    driver.save_screenshot("register_error.png")
                except Exception:
                    pass
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


def debug_registration_flow():
    """
    调试模式：打开浏览器手动检查各个注册步骤的页面元素
    用于分析页面结构和提取选择器
    """
    import sys
    
    logger.info("=" * 70)
    logger.info("🔍 调试模式 - 检查注册流程页面元素")
    logger.info("=" * 70 + "\n")
    
    bot = OpenAIRegistrationBot(use_proxy=config.USE_PROXY)
    driver = None
    
    try:
        driver = bot.get_driver()
        
        # 步骤1: 访问主页
        logger.info("\n" + "=" * 50)
        logger.info("📌 步骤1: 访问 ChatGPT 主页")
        logger.info("=" * 50)
        driver.get("https://chat.openai.com/chat")
        time.sleep(5)
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step1_homepage.png")
        bot._debug_page_elements(driver, "step1_homepage")
        
        input("\n按 Enter 继续到步骤2（点击注册）...")
        
        # 步骤2: 点击注册按钮
        logger.info("\n" + "=" * 50)
        logger.info("📌 步骤2: 点击注册按钮")
        logger.info("=" * 50)
        
        signup_selectors = [
            (By.CSS_SELECTOR, '[data-testid="signup-button"]'),
            (By.XPATH, "//a[contains(., 'Sign up') or contains(., '注册')]"),
            (By.XPATH, "//button[contains(., 'Sign up') or contains(., '注册')]"),
        ]
        try:
            bot.click_first_clickable(driver, signup_selectors, timeout=10)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"点击注册按钮失败: {e}")
            driver.get("https://chat.openai.com/auth/signup")
            time.sleep(3)
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step2_signup.png")
        bot._debug_page_elements(driver, "step2_signup")
        
        input("\n按 Enter 继续到步骤3（输入邮箱后）...")
        
        # 步骤3: 邮箱输入页面
        logger.info("\n" + "=" * 50)
        logger.info("📌 步骤3: 邮箱输入页面")
        logger.info("=" * 50)
        
        # 尝试输入测试邮箱
        email_selectors = [
            (By.ID, "email"),
            (By.CSS_SELECTOR, 'input[type="email"]'),
            (By.CSS_SELECTOR, 'input[name="email"]'),
        ]
        try:
            email_input = bot.wait_for_any_visible(driver, email_selectors, timeout=10)
            bot.fill_input(driver, email_input, "test@example.com", char_delay=0.02)
            
            # 点击继续
            continue_selectors = [
                (By.CSS_SELECTOR, 'button[type="submit"]'),
            ]
            bot.click_first_clickable(driver, continue_selectors, timeout=5)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"邮箱输入失败: {e}")
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step3_email.png")
        bot._debug_page_elements(driver, "step3_email")
        
        input("\n按 Enter 继续到步骤4（密码输入后）...")
        
        # 步骤4: 密码输入页面
        logger.info("\n" + "=" * 50)
        logger.info("📌 步骤4: 密码输入页面")
        logger.info("=" * 50)
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step4_password.png")
        bot._debug_page_elements(driver, "step4_password")
        
        # 手动等待用户操作
        logger.info("\n⚠️ 请手动完成以下步骤：")
        logger.info("   1. 输入密码并点击继续")
        logger.info("   2. 输入邮箱验证码")
        logger.info("   3. 等待进入姓名/生日页面")
        input("\n当到达姓名/生日页面时，按 Enter 继续...")
        
        # 步骤5: 姓名/生日页面
        logger.info("\n" + "=" * 50)
        logger.info("📌 步骤5: 姓名/生日页面 (关键步骤)")
        logger.info("=" * 50)
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step5_birthday.png")
        bot._debug_page_elements(driver, "step5_birthday")
        
        # 详细分析生日相关元素
        logger.info("\n🎂 详细分析生日输入元素...")
        
        # 查找所有可能的日期相关输入
        date_selectors = [
            '[data-type="year"]',
            '[data-type="month"]',
            '[data-type="day"]',
            'input[name*="year"]',
            'input[name*="month"]',
            'input[name*="day"]',
            'input[name*="birth"]',
            'input[name*="date"]',
            'input[type="date"]',
            'input[inputmode="numeric"]',
            'input[placeholder*="YYYY"]',
            'input[placeholder*="MM"]',
            'input[placeholder*="DD"]',
            'input[placeholder*="年"]',
            'input[placeholder*="月"]',
            'input[placeholder*="日"]',
            'select[name*="year"]',
            'select[name*="month"]',
            'select[name*="day"]',
        ]
        
        for selector in date_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.info(f"   ✅ 找到 '{selector}': {len(elements)} 个元素")
                    for i, el in enumerate(elements):
                        if el.is_displayed():
                            tag = el.tag_name
                            attrs = {
                                "type": el.get_attribute("type"),
                                "name": el.get_attribute("name"),
                                "id": el.get_attribute("id"),
                                "placeholder": el.get_attribute("placeholder"),
                                "value": el.get_attribute("value"),
                            }
                            logger.info(f"      元素{i+1}: <{tag}> {attrs}")
            except Exception:
                pass
        
        # 保存完整页面HTML
        try:
            with open("debug_birthday_page_full.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("\n📄 完整页面HTML已保存到 debug_birthday_page_full.html")
        except Exception:
            pass
        
        input("\n按 Enter 继续测试生日输入...")
        
        # 尝试各种生日输入方法
        logger.info("\n🔧 测试生日输入方法...")
        
        if bot._input_birthday_method1(driver):
            logger.info("✅ 方法1成功")
        elif bot._input_birthday_method2(driver):
            logger.info("✅ 方法2成功")
        elif bot._input_birthday_method3(driver):
            logger.info("✅ 方法3成功")
        elif bot._input_birthday_method4(driver):
            logger.info("✅ 方法4成功")
        else:
            logger.warning("❌ 所有方法都失败")
        
        if config.SAVE_SCREENSHOTS:
            driver.save_screenshot("debug_step5_birthday_after.png")
        
        input("\n按 Enter 结束调试...")
        
    except Exception as e:
        logger.error(f"调试过程出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            driver.quit()
    
    logger.info("\n调试完成！请检查生成的截图和HTML文件。")


def main():
    """主函数"""
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--debug", "-d", "debug"]:
            debug_registration_flow()
            return
        elif sys.argv[1] in ["--help", "-h"]:
            print("用法:")
            print("  python register_with_proxy.py          # 正常注册模式")
            print("  python register_with_proxy.py --debug  # 调试模式，检查页面元素")
            return
    
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
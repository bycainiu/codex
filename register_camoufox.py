#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI账号注册机 - Camoufox 版本
使用 Camoufox 反检测浏览器自动化注册，有效绕过 Cloudflare 验证
"""

import os
import asyncio
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
from typing import Optional, Tuple, Dict, List
import urllib3

# 导入 Camoufox
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, BrowserContext, TimeoutError as PlaywrightTimeoutError

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
        logging.FileHandler('register_camoufox.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CamoufoxRegistrationBot:
    """使用 Camoufox 的 OpenAI 注册机器人"""
    
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
    
    def get_camoufox_proxy(self, proxy_address: str) -> Optional[Dict]:
        """
        将代理地址转换为 Camoufox/Playwright 格式
        
        Args:
            proxy_address: 代理地址 (host:port 格式)
            
        Returns:
            Playwright 代理配置字典
        """
        if not proxy_address:
            return None
        
        # 解析代理地址
        if '@' in proxy_address:
            # 带认证的代理: user:pass@host:port
            auth_part, server_part = proxy_address.rsplit('@', 1)
            username, password = auth_part.split(':', 1)
            host, port = server_part.rsplit(':', 1)
            return {
                "server": f"http://{host}:{port}",
                "username": username,
                "password": password
            }
        else:
            # 不带认证的代理: host:port
            return {
                "server": f"http://{proxy_address}"
            }
    
    def get_proxy_ip(self, proxy_address: str) -> Optional[str]:
        """
        从代理地址中提取IP地址
        
        Args:
            proxy_address: 代理地址
            
        Returns:
            IP地址
        """
        if not proxy_address:
            return None
        
        # 移除认证部分
        if '@' in proxy_address:
            proxy_address = proxy_address.split('@')[1]
        
        # 提取host
        host = proxy_address.split(':')[0]
        
        # 如果是域名，尝试解析IP
        try:
            import socket
            ip = socket.gethostbyname(host)
            return ip
        except Exception:
            return host
    
    async def wait_for_selector_any(
        self, 
        page: Page, 
        selectors: List[str], 
        timeout: int = 30000
    ) -> Optional[any]:
        """
        等待多个选择器中任意一个出现
        
        Args:
            page: Playwright 页面对象
            selectors: 选择器列表
            timeout: 超时时间（毫秒）
            
        Returns:
            找到的元素
        """
        start_time = time.time()
        timeout_sec = timeout / 1000
        
        while time.time() - start_time < timeout_sec:
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        return element
                except Exception:
                    continue
            await asyncio.sleep(0.5)
        
        return None
    
    async def safe_fill(
        self, 
        page: Page, 
        selector: str, 
        value: str, 
        delay: int = 30
    ) -> bool:
        """
        安全地填充输入框
        
        Args:
            page: Playwright 页面对象
            selector: 选择器
            value: 要输入的值
            delay: 每个字符之间的延迟（毫秒）
            
        Returns:
            是否成功
        """
        try:
            element = page.locator(selector).first
            await element.click()
            await asyncio.sleep(0.1)
            await element.fill("")  # 清空
            await element.type(value, delay=delay)
            return True
        except Exception as e:
            logger.debug(f"填充输入框失败 ({selector}): {e}")
            return False
    
    async def click_first_visible(
        self, 
        page: Page, 
        selectors: List[str], 
        timeout: int = 30
    ) -> bool:
        """
        点击第一个可见的元素
        
        Args:
            page: Playwright 页面对象
            selectors: 选择器列表
            timeout: 超时时间（秒）
            
        Returns:
            是否成功点击
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        await element.click()
                        return True
                except Exception:
                    continue
            await asyncio.sleep(0.5)
        
        return False
    
    async def wait_for_cloudflare(self, page: Page, timeout: int = 60) -> bool:
        """
        等待 Cloudflare 验证完成
        
        Args:
            page: Playwright 页面对象
            timeout: 超时时间（秒）
            
        Returns:
            是否检测到并等待了验证
        """
        logger.info("🔒 检查 Cloudflare 验证...")
        start_time = time.time()
        detected = False
        
        # #region agent log
        import json as _json
        _log_path = r"d:\projects\codex\.cursor\debug.log"
        def _dbg(loc, msg, data, hyp):
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}) + "\n")
        # #endregion
        
        while time.time() - start_time < timeout:
            try:
                page_content = await page.content()
                page_content_lower = page_content.lower()
                current_url = page.url
                
                # 检测 Cloudflare 特征
                cf_indicators = [
                    "challenge-running",
                    "cf-turnstile",
                    "challenge-platform",
                    "just a moment",
                    "checking your browser",
                    "verify you are human",
                    "ray id",
                ]
                
                matched_indicators = [ind for ind in cf_indicators if ind in page_content_lower]
                is_cf_page = len(matched_indicators) > 0
                
                # #region agent log
                _dbg("wait_for_cloudflare:loop", "CF检测循环", {"url": current_url, "is_cf_page": is_cf_page, "matched_indicators": matched_indicators, "elapsed": int(time.time() - start_time), "detected": detected}, "C")
                # #endregion
                
                if is_cf_page:
                    if not detected:
                        logger.info("⏳ 检测到 Cloudflare 验证，等待完成...")
                        detected = True
                    
                    # 尝试点击 Turnstile checkbox（如果存在）
                    click_result = await self.try_click_turnstile(page)
                    
                    # #region agent log
                    _dbg("wait_for_cloudflare:turnstile_click", "尝试点击Turnstile", {"click_result": click_result}, "B")
                    # #endregion
                    
                    await asyncio.sleep(2)
                else:
                    if detected:
                        logger.info("✅ Cloudflare 验证已完成")
                        # #region agent log
                        _dbg("wait_for_cloudflare:completed", "CF验证完成", {"elapsed": int(time.time() - start_time)}, "C")
                        # #endregion
                        return True
                    else:
                        # 没有检测到 CF 验证
                        # #region agent log
                        _dbg("wait_for_cloudflare:no_cf", "未检测到CF验证", {"url": current_url}, "C")
                        # #endregion
                        return False
                        
            except Exception as e:
                logger.debug(f"Cloudflare 检测异常: {e}")
                # #region agent log
                _dbg("wait_for_cloudflare:exception", "检测异常", {"error": str(e)}, "C")
                # #endregion
                await asyncio.sleep(1)
        
        if detected:
            logger.warning("⚠️ Cloudflare 验证等待超时")
            # #region agent log
            _dbg("wait_for_cloudflare:timeout", "CF验证超时", {"timeout": timeout}, "C")
            # #endregion
        return detected
    
    async def try_click_turnstile(self, page: Page) -> bool:
        """
        尝试点击 Cloudflare Turnstile 验证框
        
        Args:
            page: Playwright 页面对象
            
        Returns:
            是否成功点击
        """
        # #region agent log
        import json as _json
        _log_path = r"d:\projects\codex\.cursor\debug.log"
        def _dbg(loc, msg, data, hyp):
            with open(_log_path, "a", encoding="utf-8") as _f:
                _f.write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}) + "\n")
        # #endregion
        
        try:
            # Turnstile iframe 选择器
            turnstile_selectors = [
                'iframe[src*="turnstile"]',
                'iframe[src*="challenges.cloudflare.com"]',
                'iframe[title*="Cloudflare"]',
                'iframe[title*="Widget"]',
            ]
            
            # #region agent log
            _dbg("try_click_turnstile:start", "开始查找Turnstile iframe", {"selectors": turnstile_selectors}, "B")
            # #endregion
            
            for selector in turnstile_selectors:
                try:
                    iframe_count = await page.locator(selector).count()
                    # #region agent log
                    _dbg("try_click_turnstile:selector_check", f"检查选择器: {selector}", {"selector": selector, "iframe_count": iframe_count}, "B")
                    # #endregion
                    
                    if iframe_count > 0:
                        iframe = page.frame_locator(selector).first
                        # 尝试点击 checkbox
                        checkbox = iframe.locator('input[type="checkbox"]')
                        checkbox_count = await checkbox.count()
                        
                        # #region agent log
                        _dbg("try_click_turnstile:checkbox_check", "检查checkbox", {"selector": selector, "checkbox_count": checkbox_count}, "B")
                        # #endregion
                        
                        if checkbox_count > 0:
                            await checkbox.click()
                            logger.info("🔘 点击了 Turnstile checkbox")
                            # #region agent log
                            _dbg("try_click_turnstile:clicked", "成功点击checkbox", {"selector": selector}, "B")
                            # #endregion
                            return True
                        
                        # 尝试点击 iframe 内的其他可点击元素
                        clickable = iframe.locator('[role="checkbox"], .ctp-checkbox-label, label')
                        clickable_count = await clickable.count()
                        # #region agent log
                        _dbg("try_click_turnstile:clickable_check", "检查其他可点击元素", {"clickable_count": clickable_count}, "B")
                        # #endregion
                        
                        if clickable_count > 0:
                            await clickable.first.click()
                            logger.info("🔘 点击了 Turnstile 可点击元素")
                            return True
                            
                except Exception as e:
                    # #region agent log
                    _dbg("try_click_turnstile:selector_error", f"选择器错误", {"selector": selector, "error": str(e)}, "B")
                    # #endregion
                    continue
            
            # 备用方案：直接在页面坐标点击
            # Turnstile 通常出现在页面中央偏上的位置
            try:
                # 获取视口大小
                viewport = page.viewport_size
                # #region agent log
                _dbg("try_click_turnstile:viewport_click", "尝试坐标点击", {"viewport": viewport}, "B")
                # #endregion
                
                if viewport:
                    # 尝试在常见的 Turnstile 位置点击
                    await page.mouse.click(viewport['width'] // 2 - 100, 300)
                    await asyncio.sleep(0.5)
            except Exception as e:
                # #region agent log
                _dbg("try_click_turnstile:viewport_error", "坐标点击失败", {"error": str(e)}, "B")
                # #endregion
                pass
                
        except Exception as e:
            logger.debug(f"点击 Turnstile 失败: {e}")
            # #region agent log
            _dbg("try_click_turnstile:fatal_error", "严重错误", {"error": str(e)}, "B")
            # #endregion
        
        return False
    
    def get_proxies_dict(self) -> Dict[str, str]:
        """
        获取用于requests的代理字典
        
        Returns:
            代理字典
        """
        if self.use_proxy and self.proxy_manager:
            return self.proxy_manager.get_proxies_dict()
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
        """根据代理地址构造requests代理字典（包含认证信息）"""
        if not proxy_addr:
            return {}
        
        # 如果代理地址已经包含认证信息（user:pass@host:port），直接使用
        if '@' in proxy_addr:
            proxy_url = f"http://{proxy_addr}"
        else:
            # 从 config 获取认证信息
            username = getattr(config, "PROXY_USERNAME", "")
            password = getattr(config, "PROXY_PASSWORD", "")
            if username and password:
                proxy_url = f"http://{username}:{password}@{proxy_addr}"
            else:
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
    
    async def input_birthday(self, page: Page) -> bool:
        """
        输入生日
        
        Args:
            page: Playwright 页面对象
            
        Returns:
            是否成功
        """
        logger.info("🎂 输入生日...")
        
        # 方法1: data-type 属性选择器
        try:
            year_selectors = [
                '[data-type="year"]',
                'input[name="year"]',
                'input[placeholder*="YYYY"]',
            ]
            month_selectors = [
                '[data-type="month"]',
                'input[name="month"]',
                'input[placeholder*="MM"]',
            ]
            day_selectors = [
                '[data-type="day"]',
                'input[name="day"]',
                'input[placeholder*="DD"]',
            ]
            
            for selector in year_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        await element.click()
                        await element.fill("1990")
                        logger.info("📅 年份已填入")
                        break
                except Exception:
                    continue
            
            for selector in month_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        await element.click()
                        await element.fill("05")
                        break
                except Exception:
                    continue
            
            for selector in day_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible():
                        await element.click()
                        await element.fill("12")
                        break
                except Exception:
                    continue
            
            return True
            
        except Exception as e:
            logger.debug(f"生日输入方法1失败: {e}")
        
        # 方法2: 查找所有数字输入框
        try:
            inputs = await page.locator('input[type="text"], input[type="number"], input[inputmode="numeric"]').all()
            visible_inputs = []
            for inp in inputs:
                if await inp.is_visible():
                    visible_inputs.append(inp)
            
            if len(visible_inputs) >= 3:
                # 假设是 月/日/年 格式
                await visible_inputs[0].fill("05")
                await asyncio.sleep(0.2)
                await visible_inputs[1].fill("12")
                await asyncio.sleep(0.2)
                await visible_inputs[2].fill("1990")
                return True
                
        except Exception as e:
            logger.debug(f"生日输入方法2失败: {e}")
        
        # 方法3: 日期选择器
        try:
            date_input = page.locator('input[type="date"]').first
            if await date_input.is_visible():
                await date_input.fill("1990-05-12")
                return True
        except Exception:
            pass
        
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
    
    async def perform_oauth_login(
        self,
        browser_context: BrowserContext,
        email: str,
        password: str,
        jwt_token: str = None,
        proxies: Optional[Dict[str, str]] = None
    ) -> Optional[Dict]:
        """
        执行OAuth登录并获取tokens
        
        Args:
            browser_context: 浏览器上下文
            email: 邮箱
            password: 密码
            jwt_token: 邮箱JWT令牌
            
        Returns:
            包含tokens的字典
        """
        logger.info("🔐 开始OAuth登录流程...")
        
        # #region agent log
        import json as _json
        _log_path = r"d:\projects\codex\.cursor\debug.log"
        def _dbg_oauth(loc, msg, data, hyp):
            try:
                with open(_log_path, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}) + "\n")
            except: pass
        # #endregion
        
        code_verifier, code_challenge = self.generate_pkce()
        state = self.generate_state()
        auth_url = self.build_authorize_url(code_challenge, state)
        
        # #region agent log
        _dbg_oauth("perform_oauth_login:start", "OAuth参数生成完成", {"auth_url": auth_url, "state": state[:20], "proxies": str(proxies)}, "A")
        # #endregion
        
        # 创建新页面
        page = None
        try:
            # #region agent log
            _dbg_oauth("perform_oauth_login:before_new_page", "准备创建新页面", {"browser_context_type": str(type(browser_context))}, "C")
            # #endregion
            
            page = await browser_context.new_page()
            
            # #region agent log
            _dbg_oauth("perform_oauth_login:page_created", "新页面已创建", {"page_url": page.url}, "C")
            # #endregion
        except Exception as e:
            # #region agent log
            _dbg_oauth("perform_oauth_login:new_page_failed", "创建新页面失败", {"error": str(e), "error_type": type(e).__name__}, "C")
            # #endregion
            logger.error(f"❌ 创建新页面失败: {e}")
            return None
        
        try:
            # #region agent log
            _dbg_oauth("perform_oauth_login:before_goto", "准备导航到OAuth URL", {"auth_url": auth_url}, "A")
            # #endregion
            
            await page.goto(auth_url, timeout=60000)
            
            # #region agent log
            _dbg_oauth("perform_oauth_login:after_goto", "导航成功", {"current_url": page.url}, "A")
            # #endregion
            
            await asyncio.sleep(3)
            
            # 等待 Cloudflare
            await self.wait_for_cloudflare(page, timeout=30)
            
            start_time = time.time()
            max_wait = config.OAUTH_CALLBACK_TIMEOUT
            callback_url = None
            email_entered = False
            password_entered = False
            verification_handled = False
            
            while time.time() - start_time < max_wait:
                try:
                    current_url = page.url
                    
                    # 检查是否已经回调
                    if "callback" in current_url and "code=" in current_url:
                        parsed = urlparse(current_url)
                        params = parse_qs(parsed.query)
                        url_state = params.get("state", [None])[0]
                        if url_state == state:
                            logger.info("✅ 收到OAuth回调")
                            callback_url = current_url
                            break
                    
                    # 输入邮箱
                    if not email_entered:
                        email_selectors = [
                            'input[type="email"]',
                            'input[name="email"]',
                            '#email',
                            'input[autocomplete="username"]',
                        ]
                        for selector in email_selectors:
                            try:
                                element = page.locator(selector).first
                                if await element.is_visible():
                                    logger.info("📧 输入邮箱...")
                                    await element.fill(email)
                                    await asyncio.sleep(1)
                                    
                                    # 点击继续
                                    continue_btn = page.locator('button[type="submit"]').first
                                    if await continue_btn.is_visible():
                                        await continue_btn.click()
                                    
                                    email_entered = True
                                    await asyncio.sleep(3)
                                    break
                            except Exception:
                                continue
                    
                    # 输入密码
                    if email_entered and not password_entered:
                        password_selectors = [
                            'input[type="password"]',
                            'input[name="password"]',
                            'input[autocomplete="current-password"]',
                        ]
                        for selector in password_selectors:
                            try:
                                element = page.locator(selector).first
                                if await element.is_visible():
                                    logger.info("🔑 输入密码...")
                                    await element.fill(password)
                                    await asyncio.sleep(1)
                                    
                                    # 点击继续
                                    continue_btn = page.locator('button[type="submit"]').first
                                    if await continue_btn.is_visible():
                                        await continue_btn.click()
                                    
                                    password_entered = True
                                    await asyncio.sleep(3)
                                    break
                            except Exception:
                                continue
                    
                    # 检查二次邮箱验证
                    current_url = page.url
                    if "email-verification" in current_url and jwt_token and not verification_handled:
                        logger.info("🔐 检测到二次邮箱验证...")
                        verification_handled = True
                        verification_code = self.wait_for_verification_email(
                            email,
                            jwt_token,
                            timeout=60,
                            proxies=proxies
                        )
                        
                        if verification_code:
                            logger.info(f"✅ 获取到验证码: {verification_code}")
                            code_input = page.locator('input[name="code"], input[inputmode="numeric"]').first
                            if await code_input.is_visible():
                                await code_input.fill(verification_code)
                                await asyncio.sleep(2)
                                
                                continue_btn = page.locator('button[type="submit"]').first
                                if await continue_btn.is_visible():
                                    await continue_btn.click()
                                await asyncio.sleep(3)
                    
                    # 尝试点击授权按钮
                    authorize_keywords = ["continue", "authorize", "allow", "继续", "授权", "允许"]
                    buttons = await page.locator('button').all()
                    for btn in buttons:
                        try:
                            if await btn.is_visible():
                                text = (await btn.text_content() or "").lower()
                                if any(k in text for k in authorize_keywords):
                                    await btn.click()
                                    await asyncio.sleep(1)
                                    break
                        except Exception:
                            continue
                    
                except Exception as e:
                    logger.debug(f"OAuth流程循环异常: {e}")
                
                await asyncio.sleep(1)
            
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
            # #region agent log
            import traceback as _tb
            _dbg_oauth("perform_oauth_login:exception", "OAuth登录异常", {
                "error": str(e), 
                "error_type": type(e).__name__,
                "traceback": _tb.format_exc(),
                "current_url": page.url if page else "N/A"
            }, "A")
            # #endregion
            logger.error(f"❌ OAuth登录异常: {e}")
        finally:
            if page:
                await page.close()
        
        return None
    
    async def register_one_account_async(
        self, 
        email: str = None, 
        password: str = None
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        异步注册一个账号
        
        Args:
            email: 邮箱（可选，不提供则自动创建）
            password: 密码（可选，不提供则自动生成）
            
        Returns:
            (邮箱, 密码, 是否成功)
        """
        success = False
        jwt_token = None
        
        # 获取代理
        selenium_proxy = None
        proxy_config = None
        geoip_target = None
        
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
            
            if selenium_proxy:
                proxy_config = self.get_camoufox_proxy(selenium_proxy)
                geoip_target = self.get_proxy_ip(selenium_proxy)
                logger.info(f"🌐 使用代理: {selenium_proxy}")
                if geoip_target:
                    logger.info(f"🌍 GeoIP目标: {geoip_target}")
        
        request_proxies = self.build_proxy_dict(selenium_proxy)
        
        # 创建邮箱和密码
        if not email or not password:
            email, jwt_token = self.create_temp_email(proxies=request_proxies)
            if not email:
                logger.error("❌ 邮箱创建失败，终止注册")
                return None, None, False
            
            password = self.generate_random_password()
        
        # #region agent log
        import json as _json
        import os as _os
        _log_path = "/tmp/camoufox_debug.log" if _os.name != "nt" else r"d:\projects\codex\.cursor\debug.log"
        def _dbg(loc, msg, data, hyp):
            try:
                with open(_log_path, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps({"location": loc, "message": msg, "data": data, "hypothesisId": hyp, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}) + "\n")
            except: pass
        # #endregion
        
        try:
            # Camoufox 配置 - 参考 codex.py 的简单配置
            camoufox_kwargs = {
                "headless": getattr(config, "CAMOUFOX_HEADLESS", config.HEADLESS_MODE),
                "geoip": True,  # 参考 codex.py: 使用 True 自动检测
            }
            
            # 添加代理
            if proxy_config:
                camoufox_kwargs["proxy"] = proxy_config
            
            # #region agent log
            _dbg("register:camoufox_config", "Camoufox配置", {"kwargs": {k: str(v) if k == "proxy" else v for k, v in camoufox_kwargs.items()}, "original_geoip_target": geoip_target}, "A")
            # #endregion
            
            logger.info("🚀 正在初始化 Camoufox 浏览器...")
            
            async with AsyncCamoufox(**camoufox_kwargs) as browser:
                page = await browser.new_page()
                
                # #region agent log
                _dbg("register:browser_started", "浏览器已启动", {}, "D")
                # #endregion
                
                # 访问 ChatGPT - 参考 codex.py
                url = "https://chat.openai.com/chat"
                logger.info(f"🌐 访问 {url}...")
                await page.goto(url)
                
                # #region agent log
                initial_url = page.url
                _dbg("register:page_loaded", "页面加载完成", {"url": initial_url}, "E")
                # #endregion
                
                await asyncio.sleep(3)
                
                if config.SAVE_SCREENSHOTS:
                    await page.screenshot(path="camoufox_page_start.png")
                    logger.info("📸 截图已保存")
                
                # 参考 codex.py: 直接等待注册按钮出现（长超时）
                logger.info("🖱️ 等待注册按钮出现...")
                
                try:
                    signup_button = await page.wait_for_selector(
                        '[data-testid="signup-button"]',
                        state="visible",
                        timeout=180000  # 3 分钟
                    )
                    
                    # #region agent log
                    _dbg("register:signup_button_found", "注册按钮已找到", {"url": page.url}, "E")
                    # #endregion
                    
                    logger.info("✅ 注册按钮已出现，点击...")
                    await signup_button.click()
                    logger.info("✅ 已点击注册按钮")
                    
                except Exception as e:
                    logger.warning(f"⚠️ 等待注册按钮失败: {e}")
                    # #region agent log
                    _dbg("register:signup_button_timeout", "注册按钮等待失败", {"error": str(e), "url": page.url}, "E")
                    # #endregion
                    
                    # 尝试其他选择器
                    signup_selectors = [
                        '[data-testid="sign-up-button"]',
                        'a[href*="signup"]',
                        'a[href*="sign-up"]',
                    ]
                    signup_clicked = await self.click_first_visible(page, signup_selectors, timeout=20)
                    
                    if not signup_clicked:
                        # 直接访问注册页面
                        logger.info("🔗 直接访问注册页面...")
                        await page.goto("https://chatgpt.com/auth/signup")
                        await asyncio.sleep(5)
                
                await asyncio.sleep(3)
                
                # 输入邮箱
                logger.info("📧 输入邮箱...")
                
                email_selectors = [
                    '#email',
                    '#email-input',
                    'input[type="email"]',
                    'input[name="email"]',
                    'input[name="username"]',
                    'input[autocomplete="username"]',
                    'input[autocomplete="email"]',
                ]
                
                email_input = await self.wait_for_selector_any(page, email_selectors, timeout=60000)
                if email_input:
                    await email_input.fill(email)
                    await asyncio.sleep(1)
                else:
                    logger.error("❌ 未找到邮箱输入框")
                    return email, password, False
                
                # 点击继续（输入邮箱后）
                try:
                    continue_btn = page.locator('button[type="submit"]').first
                    await continue_btn.click()
                    logger.info("✅ 邮箱输入后点击继续")
                except Exception as e:
                    logger.debug(f"点击继续按钮异常（可能页面已导航）: {e}")
                
                # 等待页面导航完成
                await asyncio.sleep(3)
                
                # 等待页面稳定（检查是否有加载指示器）
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass
                
                # 输入密码
                logger.info("🔑 输入密码...")
                
                # 先检查当前页面状态
                current_url = page.url
                logger.info(f"📍 当前页面: {current_url}")
                
                # #region agent log
                _dbg("register:before_password", "准备输入密码", {"url": current_url}, "F")
                # #endregion
                
                password_selectors = [
                    'input[autocomplete="new-password"]',
                    'input[type="password"]',
                    'input[name="password"]',
                ]
                
                password_input = await self.wait_for_selector_any(page, password_selectors, timeout=60000)
                if password_input:
                    await password_input.fill(password)
                    await asyncio.sleep(2)
                else:
                    # 诊断：保存截图和页面内容
                    logger.error("❌ 未找到密码输入框")
                    current_url = page.url
                    page_content = await page.content()
                    logger.error(f"📍 当前URL: {current_url}")
                    logger.error(f"📄 页面内容长度: {len(page_content)}")
                    
                    # 保存截图用于诊断
                    try:
                        await page.screenshot(path="debug_no_password_input.png")
                        logger.error("📸 已保存诊断截图: debug_no_password_input.png")
                    except: pass
                    
                    # 检查是否有错误提示
                    error_indicators = ["error", "invalid", "already", "exists", "taken"]
                    page_lower = page_content.lower()
                    matched_errors = [e for e in error_indicators if e in page_lower]
                    if matched_errors:
                        logger.error(f"⚠️ 页面可能包含错误: {matched_errors}")
                    
                    # #region agent log
                    _dbg("register:password_not_found", "密码框未找到", {"url": current_url, "content_preview": page_content[:500], "matched_errors": matched_errors}, "F")
                    # #endregion
                    
                    return email, password, False
                
                # 点击继续（输入密码后）- 重新获取按钮！
                try:
                    continue_btn = page.locator('button[type="submit"]').first
                    # 等待按钮可点击
                    await continue_btn.wait_for(state="visible", timeout=10000)
                    await continue_btn.click()
                    logger.info("✅ 密码输入后点击继续")
                except Exception as e:
                    # 如果点击失败，检查是否已经导航到验证码页面
                    logger.debug(f"点击继续按钮异常: {e}")
                    current_url = page.url
                    if "email-verification" in current_url or "verify" in current_url:
                        logger.info("✅ 页面已导航到验证码页面")
                    else:
                        logger.warning(f"⚠️ 页面状态未知: {current_url}")
                
                await asyncio.sleep(3)
                
                # 等待验证码
                logger.info("⏳ 等待邮件验证码...")
                verification_code = self.wait_for_verification_email(
                    email,
                    jwt_token,
                    proxies=request_proxies
                )
                
                if not verification_code:
                    verification_code = input("请手动输入验证码: ").strip()
                
                if not verification_code:
                    logger.error("❌ 未获取到验证码")
                    return email, password, False
                
                # 输入验证码
                logger.info("🔢 输入验证码...")
                code_selectors = [
                    'input[name="code"]',
                    'input[inputmode="numeric"]',
                ]
                
                code_input = await self.wait_for_selector_any(page, code_selectors, timeout=60000)
                if code_input:
                    await code_input.fill(verification_code)
                    await asyncio.sleep(2)
                else:
                    logger.warning("⚠️ 未找到验证码输入框，检查页面状态...")
                
                # 点击继续（验证码后）
                try:
                    continue_btn = page.locator('button[type="submit"]').first
                    await continue_btn.wait_for(state="visible", timeout=10000)
                    await continue_btn.click()
                    logger.info("✅ 验证码输入后点击继续")
                except Exception as e:
                    logger.debug(f"点击继续按钮异常（可能页面已导航）: {e}")
                await asyncio.sleep(3)
                
                # 输入姓名
                logger.info("👤 输入姓名...")
                try:
                    name_input = await self.wait_for_selector_any(
                        page, 
                        ['input[name="name"]', 'input[autocomplete="name"]'], 
                        timeout=30000
                    )
                    if name_input:
                        await name_input.fill("John Doe")
                        await asyncio.sleep(1)
                        logger.info("✅ 姓名已输入")
                except Exception as e:
                    logger.debug(f"姓名输入失败（可能已跳过）: {e}")
                
                # 输入生日
                await self.input_birthday(page)
                await asyncio.sleep(1)
                
                # 点击最后的继续按钮
                try:
                    continue_btn = page.locator('button[type="submit"]').first
                    await continue_btn.wait_for(state="visible", timeout=10000)
                    await continue_btn.click()
                    logger.info("✅ 最后的继续按钮已点击")
                except Exception as e:
                    logger.debug(f"点击最后继续按钮异常（可能页面已导航）: {e}")
                await asyncio.sleep(5)
                
                logger.info("✅ 注册流程完成")
                
                # OAuth 登录获取 tokens
                logger.info("🔐 开始OAuth认证...")
                
                # #region agent log
                # 测试网络连通性（通过requests检测代理是否可用）
                _proxy_test_result = "N/A"
                try:
                    _test_session = requests.Session()
                    _test_session.trust_env = False
                    _test_resp = _test_session.get("https://auth.openai.com", proxies=request_proxies, timeout=10, verify=False)
                    _proxy_test_result = f"HTTP {_test_resp.status_code}"
                except Exception as _pe:
                    _proxy_test_result = f"FAILED: {type(_pe).__name__}: {str(_pe)}"
                
                _dbg("register:before_oauth", "准备调用OAuth登录", {
                    "browser_type": str(type(browser)),
                    "browser_connected": browser.is_connected() if hasattr(browser, 'is_connected') else "N/A",
                    "email": email,
                    "request_proxies": str(request_proxies),
                    "proxy_connectivity_test": _proxy_test_result
                }, "A")
                # #endregion
                
                tokens = await self.perform_oauth_login(
                    browser,
                    email,
                    password,
                    jwt_token,
                    proxies=request_proxies
                )
                
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
            import traceback
            traceback.print_exc()
            if email and password:
                self.save_account(email, password)
        
        return email, password, success
    
    def register_one_account(
        self, 
        email: str = None, 
        password: str = None
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        注册一个账号（同步包装器）
        
        Args:
            email: 邮箱（可选）
            password: 密码（可选）
            
        Returns:
            (邮箱, 密码, 是否成功)
        """
        return asyncio.run(self.register_one_account_async(email, password))
    
    def run_batch(self, total_accounts: int = None):
        """
        批量注册账号
        
        Args:
            total_accounts: 注册账号数量
        """
        if total_accounts is None:
            total_accounts = config.TOTAL_ACCOUNTS
        
        logger.info("\n" + "=" * 70)
        logger.info(f"🚀 开始批量注册 (Camoufox)，目标账号数: {total_accounts}")
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
                time.sleep(wait_time)
        
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
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print("用法:")
            print("  python register_camoufox.py          # 正常注册模式")
            print("  python register_camoufox.py --test   # 测试模式，只注册1个账号")
            return
        elif sys.argv[1] in ["--test", "-t"]:
            config.TEST_MODE = True
    
    logger.info("=" * 70)
    logger.info("OpenAI 账号注册机 - Camoufox 版本")
    logger.info("使用 Camoufox 反检测浏览器，有效绕过 Cloudflare 验证")
    logger.info("=" * 70 + "\n")
    
    # 创建注册机器人
    bot = CamoufoxRegistrationBot(use_proxy=config.USE_PROXY)
    
    # 执行批量注册
    if config.TEST_MODE:
        logger.info("⚠️ 测试模式：只注册1个账号")
        bot.run_batch(total_accounts=1)
    else:
        bot.run_batch()


if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理管理模块

requests请求：走系统全局代理
Selenium浏览器：使用获取到的代理IP
"""

import requests
import logging
import urllib3
from typing import Optional
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProxyManager:
    """代理管理器"""
    
    def __init__(self,
                 proxy_host: str = "",
                 proxy_port: int = 0,
                 username: str = "",
                 password: str = "",
                 requests_use_proxy: bool = False,
                 use_proxy_api: bool = False,
                 proxy_api_url: str = "",
                 proxy_api_params: Optional[dict] = None):
        """
        初始化
        
        Args:
            proxy_host: 快代理主机
            proxy_port: 快代理端口
            username: 用户名
            password: 密码
            requests_use_proxy: requests是否使用代理
            use_proxy_api: 是否使用API获取代理IP
            proxy_api_url: 代理API地址
            proxy_api_params: 代理API参数
        """
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.username = username
        self.password = password
        self.requests_use_proxy = requests_use_proxy
        self.use_proxy_api = use_proxy_api
        self.proxy_api_url = proxy_api_url
        self.proxy_api_params = proxy_api_params or {}
        
        if self.use_proxy_api and self.proxy_api_url:
            logger.info("✅ 代理API已配置，将通过系统全局代理获取IP")
        elif proxy_host:
            logger.info(f"✅ 固定代理已配置: {proxy_host}:{proxy_port}")

        if not requests_use_proxy:
            logger.info("   requests请求走系统全局代理")
    
    def get_proxies_dict(self):
        """获取requests代理字典（走全局代理则返回空）"""
        if not self.requests_use_proxy:
            return {}
        
        if self.username and self.password:
            proxy_url = f"http://{self.username}:{self.password}@{self.proxy_host}:{self.proxy_port}"
        else:
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        
        return {"http": proxy_url, "https": proxy_url}

    def fetch_proxy_ip(
        self,
        retries: int = 1,
        delay: int = 2,
        local_proxy_url: Optional[str] = None
    ) -> Optional[str]:
        """通过API获取代理IP（不使用系统代理）"""
        if not self.use_proxy_api or not self.proxy_api_url:
            return None

        def _normalize_urls(base_url: str) -> list[str]:
            if base_url.startswith("https://"):
                return [base_url, "http://" + base_url[len("https://"):]]
            if base_url.startswith("http://"):
                return [base_url, "https://" + base_url[len("http://"):]]
            return ["https://" + base_url, "http://" + base_url]

        urls = _normalize_urls(self.proxy_api_url)
        headers = {"User-Agent": "Mozilla/5.0"}
        proxies = None
        if local_proxy_url:
            proxies = {"http": local_proxy_url, "https": local_proxy_url}

        for attempt in range(max(1, retries)):
            for url in urls:
                try:
                    logger.info(f"🌐 正在通过API获取代理IP: {url}")
                    response = requests.get(
                        url,
                        params=self.proxy_api_params,
                        headers=headers,
                        timeout=15,
                        verify=False,
                        proxies=proxies,
                        trust_env=False
                    )

                    if response.status_code != 200:
                        logger.warning(f"⚠️ 代理API返回: HTTP {response.status_code}")
                        continue

                    text = (response.text or "").strip()
                    if not text:
                        logger.warning("⚠️ 代理API返回为空")
                        continue

                    proxy_ip = text.splitlines()[0].strip()
                    if proxy_ip:
                        logger.info(f"✅ 获取到代理IP: {proxy_ip}")
                        return proxy_ip

                except Exception as e:
                    logger.error(f"❌ 获取代理IP异常: {e}")

            if attempt < retries - 1:
                time.sleep(delay)

        return None

    def get_selenium_proxy(
        self,
        retries: int = 1,
        delay: int = 2,
        local_proxy_url: Optional[str] = None
    ) -> Optional[str]:
        """获取用于Selenium的代理地址"""
        if self.use_proxy_api:
            return self.fetch_proxy_ip(
                retries=retries,
                delay=delay,
                local_proxy_url=local_proxy_url
            )

        if self.proxy_host and self.proxy_port:
            return f"{self.proxy_host}:{self.proxy_port}"

        return None
    
    def test_connection(self, test_url: str = "https://ipinfo.io/") -> bool:
        """测试网络连接"""
        try:
            logger.info(f"🔍 测试网络连接...")
            response = requests.get(test_url, timeout=15, verify=False)
            
            if response.status_code == 200:
                logger.info(f"✅ 网络连接正常!")
                logger.info(f"📍 当前IP: {response.text[:100]}...")
                return True
            else:
                logger.warning(f"⚠️ 返回: HTTP {response.status_code}")
                return response.status_code < 500
                
        except Exception as e:
            logger.error(f"❌ 连接测试异常: {e}")
            return False


def test_proxy_manager():
    """测试"""
    import config
    
    pm = ProxyManager(
        proxy_host=config.PROXY_HOST,
        proxy_port=config.PROXY_PORT,
        username=config.PROXY_USERNAME,
        password=config.PROXY_PASSWORD,
        requests_use_proxy=config.REQUESTS_USE_PROXY,
        use_proxy_api=getattr(config, "USE_PROXY_API", False),
        proxy_api_url=getattr(config, "PROXY_API_URL", ""),
        proxy_api_params=getattr(config, "PROXY_API_PARAMS", {})
    )
    
    pm.test_connection()
    pm.get_selenium_proxy()


if __name__ == "__main__":
    test_proxy_manager()

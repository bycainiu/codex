#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试代理IP获取与使用
"""

import sys
import requests
import config
from proxy_manager import ProxyManager


def main() -> int:
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

    proxy_ip = pm.get_selenium_proxy(
        retries=getattr(config, "PROXY_API_RETRIES", 1),
        delay=getattr(config, "PROXY_API_RETRY_DELAY", 1),
        local_proxy_url=(
            config.PROXY_API_LOCAL_PROXY_URL
            if getattr(config, "PROXY_API_USE_LOCAL_PROXY", False)
            else None
        )
    )

    if not proxy_ip:
        print("ERROR: 未获取到代理IP")
        return 1

    proxies = {
        "http": f"http://{proxy_ip}",
        "https": f"http://{proxy_ip}"
    }

    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(
            "https://ipinfo.io/ip",
            proxies=proxies,
            timeout=20,
            verify=False
        )
        if res.status_code != 200:
            print(f"ERROR: 代理请求失败 HTTP {res.status_code}")
            return 1
        print(f"OK: 代理IP测试成功: {res.text.strip()}")
        return 0
    except Exception as e:
        print(f"ERROR: 代理请求异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

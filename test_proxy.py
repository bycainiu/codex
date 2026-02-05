#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理测试脚本
用于测试代理连接和IP切换功能
"""

import time
import json
import requests
from proxy_manager import ProxyManager
import config


def test_proxy_basic():
    """测试基础代理功能"""
    print("=" * 70)
    print("测试1: 基础代理功能")
    print("=" * 70)
    
    pm = ProxyManager(
        tunnel=config.PROXY_TUNNEL,
        username=config.PROXY_USERNAME,
        password=config.PROXY_PASSWORD,
        use_api=config.USE_PROXY_API
    )
    
    # 获取代理信息
    proxy = pm.get_proxy()
    if proxy:
        print(f"\n✅ 代理信息:")
        print(f"   隧道: {proxy.tunnel}")
        print(f"   用户名: {proxy.username}")
        print(f"   HTTP代理: {proxy.http_proxy}")
        print(f"   HTTPS代理: {proxy.https_proxy}")
        return pm
    else:
        print("❌ 获取代理失败")
        return None


def test_proxy_connection(pm):
    """测试代理连接"""
    print("\n" + "=" * 70)
    print("测试2: 代理连接测试")
    print("=" * 70)
    
    if pm.test_proxy():
        print("✅ 代理连接正常")
    else:
        print("❌ 代理连接失败")


def test_ip_switching(pm):
    """测试IP切换功能"""
    print("\n" + "=" * 70)
    print("测试3: IP自动切换测试（隧道模式）")
    print("=" * 70)
    print("\n说明: 隧道代理会在每次请求时自动切换IP\n")
    
    ips = []
    
    for i in range(5):
        print(f"第 {i+1} 次请求:")
        try:
            proxies = pm.get_proxies_dict()
            response = requests.get(
                "https://ipinfo.io/",
                proxies=proxies,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    ip_info = json.loads(response.text)
                    ip = ip_info.get('ip', 'N/A')
                    city = ip_info.get('city', 'N/A')
                    country = ip_info.get('country', 'N/A')
                    org = ip_info.get('org', 'N/A')
                    
                    print(f"  ✅ IP: {ip}")
                    print(f"     城市: {city}")
                    print(f"     国家: {country}")
                    print(f"     运营商: {org}")
                    
                    ips.append(ip)
                except Exception as e:
                    print(f"  ⚠️ 解析响应失败: {e}")
                    print(f"  响应内容: {response.text[:100]}")
            else:
                print(f"  ❌ 请求失败: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"  ❌ 请求异常: {e}")
        
        print()
        
        # 最后一次不等待
        if i < 4:
            time.sleep(2)
    
    # 统计IP切换情况
    unique_ips = set(ips)
    print("-" * 70)
    print(f"📊 统计结果:")
    print(f"   总请求数: {len(ips)}")
    print(f"   不同IP数: {len(unique_ips)}")
    print(f"   切换成功率: {len(unique_ips)/len(ips)*100:.1f}%")
    print(f"   使用的IP: {', '.join(unique_ips)}")


def test_requests_with_proxy(pm):
    """测试requests库使用代理"""
    print("\n" + "=" * 70)
    print("测试4: Requests库代理使用")
    print("=" * 70)
    
    proxies = pm.get_proxies_dict()
    
    test_urls = [
        "https://httpbin.org/ip",
        "https://api.ipify.org?format=json",
        "https://ipinfo.io/json"
    ]
    
    for url in test_urls:
        print(f"\n测试URL: {url}")
        try:
            response = requests.get(
                url,
                proxies=proxies,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                print(f"  ✅ 成功")
                print(f"  响应: {response.text[:150]}")
            else:
                print(f"  ❌ 失败: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"  ❌ 异常: {e}")


def test_selenium_proxy_format(pm):
    """测试Selenium代理格式"""
    print("\n" + "=" * 70)
    print("测试5: Selenium代理格式")
    print("=" * 70)
    
    proxy_string = pm.get_selenium_proxy_arg()
    print(f"\n✅ Selenium代理参数:")
    print(f"   {proxy_string}")
    print(f"\n使用方法:")
    print(f"   options.add_argument('--proxy-server={proxy_string}')")


def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("🔍 代理功能测试工具")
    print("=" * 70 + "\n")
    
    # 测试1: 基础功能
    pm = test_proxy_basic()
    if not pm:
        print("\n❌ 代理管理器初始化失败，测试终止")
        return
    
    # 测试2: 连接测试
    test_proxy_connection(pm)
    
    # 测试3: IP切换
    test_ip_switching(pm)
    
    # 测试4: Requests使用
    test_requests_with_proxy(pm)
    
    # 测试5: Selenium格式
    test_selenium_proxy_format(pm)
    
    print("\n" + "=" * 70)
    print("✅ 所有测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()

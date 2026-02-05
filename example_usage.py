#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用示例
演示如何使用注册框架的各个组件
"""

import logging
from proxy_manager import ProxyManager
from register_with_proxy import OpenAIRegistrationBot
import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_proxy_manager():
    """示例1: 使用代理管理器"""
    print("\n" + "=" * 70)
    print("示例1: 代理管理器基础使用")
    print("=" * 70 + "\n")
    
    # 创建代理管理器
    pm = ProxyManager(
        tunnel=config.PROXY_TUNNEL,
        username=config.PROXY_USERNAME,
        password=config.PROXY_PASSWORD,
        use_api=False  # 使用固定隧道，不调用API
    )
    
    # 获取代理信息
    proxy = pm.get_proxy()
    if proxy:
        print(f"✅ 代理隧道: {proxy.tunnel}")
        print(f"✅ HTTP代理: {proxy.http_proxy}")
    
    # 测试代理连接
    if pm.test_proxy():
        print("✅ 代理连接成功")
    
    # 获取用于requests的代理字典
    proxies = pm.get_proxies_dict()
    print(f"\n用于Requests库:")
    print(f"  {proxies}")
    
    # 获取用于Selenium的代理参数
    selenium_proxy = pm.get_selenium_proxy_arg()
    print(f"\n用于Selenium:")
    print(f"  options.add_argument('--proxy-server={selenium_proxy}')")


def example_2_single_registration():
    """示例2: 注册单个账号"""
    print("\n" + "=" * 70)
    print("示例2: 注册单个账号")
    print("=" * 70 + "\n")
    
    # 创建注册机器人（启用代理）
    bot = OpenAIRegistrationBot(use_proxy=True)
    
    # 注册一个账号
    email, password, success = bot.register_one_account()
    
    if success:
        print(f"\n✅ 注册成功!")
        print(f"   邮箱: {email}")
        print(f"   密码: {password}")
    else:
        print(f"\n❌ 注册失败")


def example_3_batch_registration():
    """示例3: 批量注册账号"""
    print("\n" + "=" * 70)
    print("示例3: 批量注册账号")
    print("=" * 70 + "\n")
    
    # 创建注册机器人
    bot = OpenAIRegistrationBot(use_proxy=True)
    
    # 批量注册3个账号
    bot.run_batch(total_accounts=3)


def example_4_custom_config():
    """示例4: 自定义配置"""
    print("\n" + "=" * 70)
    print("示例4: 自定义配置使用")
    print("=" * 70 + "\n")
    
    # 临时修改配置
    original_timeout = config.EMAIL_VERIFICATION_TIMEOUT
    config.EMAIL_VERIFICATION_TIMEOUT = 180  # 增加超时时间到180秒
    
    print(f"✅ 邮件验证超时时间已修改为: {config.EMAIL_VERIFICATION_TIMEOUT}秒")
    
    # 创建注册机器人
    bot = OpenAIRegistrationBot(use_proxy=True)
    
    # 注册账号...
    # bot.register_one_account()
    
    # 恢复原配置
    config.EMAIL_VERIFICATION_TIMEOUT = original_timeout
    print(f"✅ 配置已恢复为: {config.EMAIL_VERIFICATION_TIMEOUT}秒")


def example_5_without_proxy():
    """示例5: 不使用代理"""
    print("\n" + "=" * 70)
    print("示例5: 不使用代理（直连）")
    print("=" * 70 + "\n")
    
    # 创建注册机器人（禁用代理）
    bot = OpenAIRegistrationBot(use_proxy=False)
    
    print("✅ 注册机器人已创建（不使用代理）")
    
    # 注册账号...
    # email, password, success = bot.register_one_account()


def example_6_proxy_with_api():
    """示例6: 使用API获取代理信息"""
    print("\n" + "=" * 70)
    print("示例6: 通过API获取代理信息")
    print("=" * 70 + "\n")
    
    # 创建代理管理器（启用API）
    pm = ProxyManager(
        api_url=config.PROXY_API_URL,
        secret_id=config.PROXY_SECRET_ID,
        signature=config.PROXY_SIGNATURE,
        tunnel=config.PROXY_TUNNEL,
        username=config.PROXY_USERNAME,
        password=config.PROXY_PASSWORD,
        use_api=True  # 启用API
    )
    
    # 获取代理信息（会调用API）
    proxy = pm.get_proxy()
    if proxy:
        print(f"✅ 已通过API获取代理信息")
        print(f"   隧道: {proxy.tunnel}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🎯 OpenAI注册机使用示例")
    print("=" * 70)
    
    print("\n请选择要运行的示例:")
    print("1. 代理管理器基础使用")
    print("2. 注册单个账号")
    print("3. 批量注册账号")
    print("4. 自定义配置")
    print("5. 不使用代理")
    print("6. 通过API获取代理信息")
    print("0. 退出")
    
    choice = input("\n请输入选项 (0-6): ").strip()
    
    examples = {
        "1": example_1_proxy_manager,
        "2": example_2_single_registration,
        "3": example_3_batch_registration,
        "4": example_4_custom_config,
        "5": example_5_without_proxy,
        "6": example_6_proxy_with_api,
    }
    
    if choice == "0":
        print("\n👋 再见!")
        return
    
    if choice in examples:
        examples[choice]()
    else:
        print("\n❌ 无效的选项")


if __name__ == "__main__":
    main()

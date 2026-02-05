# 架构设计文档

## 📐 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenAI 注册机系统                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │      OpenAIRegistrationBot (主控)        │
        │  • 流程编排                              │
        │  • 账号注册                              │
        │  • OAuth 认证                            │
        └──────────┬──────────────────────────────┘
                   │
         ┌─────────┴─────────────────┐
         │                            │
         ▼                            ▼
┌─────────────────┐         ┌──────────────────┐
│  ProxyManager   │         │  邮箱服务模块      │
│  (代理管理)      │         │  (DuckMail)       │
│  • IP获取        │         │  • 邮箱创建        │
│  • 代理切换      │         │  • 验证码获取      │
│  • 连接测试      │         │  • 邮件接收        │
└─────────────────┘         └──────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐         ┌──────────────────┐
│  快代理服务      │         │  DuckMail API     │
│  • 隧道服务      │         │  • REST API       │
│  • IP池管理      │         │  • JWT认证        │
└─────────────────┘         └──────────────────┘
         │                            │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │    浏览器自动化层       │
         │  • Selenium             │
         │  • undetected-chrome    │
         │  • WebDriver            │
         └────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │    OpenAI 网站          │
         │  • 注册页面             │
         │  • OAuth 认证           │
         └────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │    存储层               │
         │  • accounts.txt         │
         │  • ak.txt / rk.txt      │
         │  • JSON文件             │
         │  • 日志文件             │
         └────────────────────────┘
```

## 🏗️ 模块设计

### 1. 配置模块 (config.py)

**职责**: 集中管理所有配置参数

**主要配置项**:
- 注册配置（账号数量、模式等）
- 邮箱服务配置（DuckMail API）
- 代理配置（隧道、认证等）
- OAuth 配置（OpenAI）
- 超时和重试配置
- 浏览器配置

**设计理念**:
- 单一配置源
- 易于修改
- 支持环境变量
- 配置与代码分离

### 2. 代理管理模块 (proxy_manager.py)

**核心类**: `ProxyManager`

**主要功能**:
```python
class ProxyManager:
    • __init__()          # 初始化配置
    • fetch_proxy_from_api()   # 从API获取代理
    • create_proxy_info()      # 创建代理信息
    • get_proxy()              # 获取当前代理
    • get_proxies_dict()       # Requests格式
    • get_selenium_proxy_arg() # Selenium格式
    • test_proxy()             # 测试连接
    • refresh_proxy()          # 刷新代理
```

**数据结构**:
```python
@dataclass
class ProxyInfo:
    tunnel: str           # 隧道地址
    username: str         # 用户名
    password: str         # 密码
    http_proxy: str       # HTTP代理URL
    https_proxy: str      # HTTPS代理URL
    created_at: float     # 创建时间
```

**代理模式**:

1. **隧道模式（推荐）**
   - 固定隧道地址
   - 自动切换IP
   - 无需管理IP池
   - 高可用性

2. **API模式**
   - 动态获取代理
   - 灵活控制
   - 需要额外API调用

### 3. 注册机器人模块 (register_with_proxy.py)

**核心类**: `OpenAIRegistrationBot`

**主要方法**:

```python
class OpenAIRegistrationBot:
    # 初始化
    • __init__(use_proxy)
    
    # 驱动管理
    • get_driver()
    • get_proxies_dict()
    
    # 工具方法
    • generate_random_password()
    • generate_pkce()
    • generate_state()
    
    # 邮箱操作
    • create_temp_email()
    • fetch_emails()
    • extract_verification_code()
    • wait_for_verification_email()
    
    # OAuth 流程
    • build_authorize_url()
    • exchange_code_for_tokens()
    • wait_for_callback_url()
    • perform_oauth_login()
    
    # 注册流程
    • register_one_account()
    • run_batch()
    
    # 错误处理
    • check_and_handle_error()
    
    # 数据保存
    • save_account()
    • save_tokens()
    • save_account_json()
```

## 🔄 工作流程

### 注册流程详细设计

```
开始
  │
  ├─► 1. 初始化
  │   ├─ 创建 ProxyManager
  │   ├─ 测试代理连接
  │   └─ 初始化日志
  │
  ├─► 2. 创建临时邮箱
  │   ├─ 生成随机邮箱名
  │   ├─ 调用 DuckMail API
  │   ├─ 获取 JWT Token
  │   └─ 返回邮箱和Token
  │
  ├─► 3. 启动浏览器
  │   ├─ 配置 ChromeOptions
  │   ├─ 设置代理参数
  │   ├─ 创建 Chrome Driver
  │   └─ 访问 OpenAI
  │
  ├─► 4. 注册表单填写
  │   ├─ 点击注册按钮
  │   ├─ 输入邮箱
  │   ├─ 生成并输入密码
  │   └─ 提交表单
  │
  ├─► 5. 邮箱验证
  │   ├─ 等待验证邮件
  │   ├─ 提取验证码
  │   ├─ 输入验证码
  │   └─ 确认验证
  │
  ├─► 6. 完善信息
  │   ├─ 输入姓名
  │   ├─ 输入生日
  │   └─ 提交信息
  │
  ├─► 7. OAuth 认证
  │   ├─ 生成 PKCE 参数
  │   ├─ 构造授权 URL
  │   ├─ 在新标签页打开
  │   ├─ 输入邮箱密码
  │   ├─ 等待回调 URL
  │   ├─ 提取 auth code
  │   └─ 交换 tokens
  │
  ├─► 8. 保存结果
  │   ├─ 保存账号密码
  │   ├─ 保存 tokens
  │   ├─ 生成 JSON 文件
  │   └─ 记录日志
  │
  └─► 9. 清理资源
      ├─ 关闭浏览器
      ├─ 释放连接
      └─ 完成
```

### 批量注册流程

```
开始批量注册
  │
  ├─► for i in range(total_accounts):
  │     │
  │     ├─► 注册单个账号
  │     │   └─ (见上方注册流程)
  │     │
  │     ├─► 统计结果
  │     │   ├─ 成功 +1
  │     │   └─ 失败 +1
  │     │
  │     ├─► 随机等待
  │     │   └─ 5-15秒
  │     │
  │     └─► 刷新代理
  │         └─ 准备下次注册
  │
  └─► 输出最终报告
      ├─ 总数量
      ├─ 成功数量
      ├─ 失败数量
      └─ 成功率
```

## 🔐 OAuth 认证流程

```
OAuth 流程开始
  │
  ├─► 1. 生成 PKCE 参数
  │   ├─ code_verifier (随机64字节)
  │   └─ code_challenge (SHA256哈希)
  │
  ├─► 2. 生成 state 参数
  │   └─ 32字节随机数
  │
  ├─► 3. 构造授权 URL
  │   ├─ response_type=code
  │   ├─ client_id
  │   ├─ redirect_uri
  │   ├─ scope
  │   ├─ code_challenge
  │   └─ state
  │
  ├─► 4. 浏览器授权
  │   ├─ 打开授权页面
  │   ├─ 用户登录
  │   └─ 确认授权
  │
  ├─► 5. 获取 callback URL
  │   ├─ 监听 redirect_uri
  │   ├─ 验证 state
  │   └─ 提取 code
  │
  ├─► 6. 交换 tokens
  │   ├─ POST /oauth/token
  │   ├─ 提交 code + code_verifier
  │   └─ 获取响应
  │
  └─► 7. 返回 tokens
      ├─ access_token
      ├─ refresh_token
      └─ id_token
```

## 💾 数据存储设计

### 存储文件

1. **accounts.txt**
   ```
   格式: email:password
   用途: 账号密码明文存储
   示例: user@domain.com:Pass123!
   ```

2. **ak.txt**
   ```
   格式: 每行一个token
   用途: Access Token列表
   特点: JWT格式，10天有效期
   ```

3. **rk.txt**
   ```
   格式: 每行一个token
   用途: Refresh Token列表
   特点: 用于刷新access_token
   ```

4. **codex-{email}.json**
   ```json
   {
     "access_token": "...",
     "account_id": "...",
     "email": "...",
     "expired": "2024-02-15T10:30:00+08:00",
     "id_token": "...",
     "last_refresh": "2024-02-05T10:30:00+08:00",
     "refresh_token": "...",
     "type": "codex"
   }
   ```

5. **register.log**
   ```
   格式: 时间戳 - 级别 - 消息
   用途: 完整日志记录
   特点: 支持调试和追踪
   ```

## ⚡ 性能优化策略

### 1. 代理优化
- 使用隧道代理，减少连接开销
- 代理连接复用
- 失败自动重试
- 连接池管理

### 2. 并发优化
- 异步操作（邮箱、代理）
- 非阻塞等待
- 智能超时控制
- 资源及时释放

### 3. 浏览器优化
- 无头模式运行
- 禁用不必要的功能
- 智能等待策略
- 截图按需保存

### 4. 错误处理
- 多层重试机制
- 错误页面自动恢复
- 部分失败继续执行
- 完善的日志记录

## 🛡️ 安全设计

### 1. 配置安全
- 敏感信息独立配置
- 支持环境变量
- 不提交到版本控制

### 2. 网络安全
- HTTPS 通信
- SSL 证书验证（可选）
- 代理加密传输

### 3. 数据安全
- 本地文件存储
- 访问权限控制
- 日志脱敏处理

### 4. 反检测
- undetected-chromedriver
- 随机等待时间
- 真实浏览器指纹
- IP自动切换

## 🔧 扩展性设计

### 1. 模块化
- 各模块独立
- 低耦合设计
- 接口清晰
- 易于替换

### 2. 配置化
- 所有参数可配置
- 支持运行时修改
- 灵活的开关控制

### 3. 可扩展点
- 自定义邮箱服务
- 自定义代理服务
- 自定义存储方式
- 自定义通知方式

## 📊 监控与日志

### 日志级别
- **INFO**: 正常流程信息
- **WARNING**: 警告信息（不影响执行）
- **ERROR**: 错误信息（可能影响结果）

### 关键监控点
- 代理连接状态
- 邮箱创建成功率
- 验证码获取成功率
- OAuth认证成功率
- 整体注册成功率

### 日志输出
- 控制台实时输出
- 文件持久化存储
- 结构化日志格式
- 支持日志分析

## 🎯 设计原则

1. **单一职责**: 每个模块只负责一个功能
2. **开闭原则**: 对扩展开放，对修改关闭
3. **依赖倒置**: 依赖抽象而非具体实现
4. **配置优先**: 通过配置而非代码控制行为
5. **失败快速**: 快速发现问题，及时处理
6. **日志完善**: 关键步骤全程记录
7. **优雅降级**: 部分失败不影响整体

## 📈 未来优化方向

1. **多线程/协程**: 提升批量注册效率
2. **分布式部署**: 支持多机器协同
3. **图形界面**: 提供 GUI 操作界面
4. **实时监控**: Dashboard 实时显示状态
5. **智能重试**: 基于失败原因智能重试
6. **代理池管理**: 自动管理多个代理源
7. **通知系统**: 完成后邮件/消息通知
8. **数据统计**: 详细的统计分析功能

---

该架构设计注重**模块化**、**可扩展性**和**可维护性**，确保系统稳定高效运行。

# OpenAI 账号注册机 - 集成代理版本

一个功能完善的 OpenAI 账号批量注册工具，集成海外代理支持，实现自动化注册、邮箱验证和 OAuth 认证。

## ✨ 主要特性

- 🌐 **代理支持**: 集成快代理隧道服务，自动切换IP
- 📧 **自动邮箱**: 使用 DuckMail 临时邮箱服务
- 🔐 **OAuth 认证**: 自动完成 OAuth 流程，获取 access_token 和 refresh_token
- 🔄 **批量注册**: 支持批量注册多个账号
- 📊 **详细日志**: 完整的日志记录，方便调试和追踪
- 🎯 **高成功率**: 完善的错误处理和重试机制
- 🏗️ **模块化设计**: 清晰的代码结构，易于维护和扩展

## 📁 项目结构

```
codex/
├── config.py                 # 配置文件
├── proxy_manager.py          # 代理管理模块
├── register_with_proxy.py    # 主注册程序
├── requirements.txt          # Python依赖
├── README.md                 # 使用说明
├── accounts.txt              # 注册的账号密码（自动生成）
├── ak.txt                    # Access Tokens（自动生成）
├── rk.txt                    # Refresh Tokens（自动生成）
└── codex-*.json              # 账号详细信息（自动生成）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置参数

编辑 `config.py` 文件，配置以下参数：

#### DuckMail 邮箱配置
```python
DUCKMAIL_API_URL = "你的DuckMail API地址"
DUCKMAIL_API_KEY = "你的API密钥"
DUCKMAIL_DOMAIN = "你的私有域名"
```

#### 代理配置（已包含示例）
```python
USE_PROXY = True  # 是否启用代理
PROXY_TUNNEL = "k263.kdlfps.com:18866"
PROXY_USERNAME = "f2320674627"
PROXY_PASSWORD = "06xv9rd2"
```

### 3. 运行程序

#### 批量注册（默认4个账号）
```bash
python register_with_proxy.py
```

#### 测试模式（只注册1个账号）
```python
# 在 config.py 中设置
TEST_MODE = True
```

#### 测试代理连接
```bash
python proxy_manager.py
```

## 📝 配置说明

### 核心配置

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `TOTAL_ACCOUNTS` | 批量注册账号数量 | 4 |
| `USE_PROXY` | 是否启用代理 | True |
| `HEADLESS_MODE` | 是否使用无头模式 | True |
| `TEST_MODE` | 测试模式（只注册1个） | False |

### 代理配置

| 配置项 | 说明 |
|-------|------|
| `PROXY_API_URL` | 快代理API地址 |
| `PROXY_SECRET_ID` | API密钥ID |
| `PROXY_SIGNATURE` | API签名 |
| `PROXY_TUNNEL` | 隧道地址 |
| `PROXY_USERNAME` | 隧道用户名 |
| `PROXY_PASSWORD` | 隧道密码 |
| `USE_PROXY_API` | 是否调用API获取代理信息 |

### 超时配置

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `EMAIL_VERIFICATION_TIMEOUT` | 等待邮件验证码超时 | 120秒 |
| `OAUTH_CALLBACK_TIMEOUT` | 等待OAuth回调超时 | 60秒 |
| `PAGE_LOAD_TIMEOUT` | 页面加载超时 | 30秒 |

### 重试配置

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `MAX_ERROR_RETRIES` | 错误页面最大重试次数 | 5次 |
| `MAX_OAUTH_RETRIES` | OAuth登录最大重试次数 | 3次 |

## 🔧 代理管理模块

### ProxyManager 类

代理管理器提供以下功能：

- **自动获取代理**: 支持从API获取代理信息或使用固定隧道
- **代理测试**: 测试代理连接是否正常
- **自动刷新**: 定期刷新代理连接
- **多格式支持**: 同时支持 Selenium 和 Requests 库

### 代理模式说明

#### 隧道模式（推荐）
使用固定的隧道地址，每次请求自动切换IP，无需手动管理IP池。

```python
# 配置
USE_PROXY_API = False  # 不调用API
PROXY_TUNNEL = "k263.kdlfps.com:18866"
```

#### API模式
通过API获取代理IP信息，适合需要获取特定代理信息的场景。

```python
# 配置
USE_PROXY_API = True
PROXY_API_URL = "https://fps.kdlapi.com/api/getfps"
```

### 代理使用示例

```python
from proxy_manager import ProxyManager

# 创建代理管理器
pm = ProxyManager()

# 获取requests格式的代理
proxies = pm.get_proxies_dict()
response = requests.get("https://ipinfo.io/", proxies=proxies)

# 获取Selenium格式的代理参数
proxy_arg = pm.get_selenium_proxy_arg()
options.add_argument(f'--proxy-server={proxy_arg}')

# 测试代理
pm.test_proxy()

# 刷新代理
pm.refresh_proxy()
```

## 📊 输出文件说明

### accounts.txt
账号密码列表，格式：
```
email1@domain.com:password1
email2@domain.com:password2
```

### ak.txt
Access Token列表，每行一个token

### rk.txt
Refresh Token列表，每行一个token

### codex-*.json
每个账号的完整信息，格式：
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

## 🔍 日志说明

程序会生成两种日志：

1. **控制台输出**: 实时显示注册进度
2. **register.log**: 完整的日志文件，包含所有详细信息

日志级别：
- ✅ INFO: 正常流程信息
- ⚠️ WARNING: 警告信息
- ❌ ERROR: 错误信息

## ⚙️ 工作流程

### 单账号注册流程

1. **创建临时邮箱**
   - 通过 DuckMail API 创建临时邮箱
   - 获取邮箱的 JWT Token

2. **访问 OpenAI**
   - 使用代理访问 chat.openai.com
   - 点击注册按钮

3. **填写注册信息**
   - 输入邮箱地址
   - 生成并输入密码
   - 等待邮件验证码
   - 输入验证码
   - 填写姓名和生日

4. **OAuth 认证**
   - 在新标签页完成 OAuth 流程
   - 输入邮箱和密码
   - 处理二次验证（如果需要）
   - 获取 authorization code
   - 交换 access_token 和 refresh_token

5. **保存账号信息**
   - 保存账号密码到 accounts.txt
   - 保存 tokens 到 ak.txt 和 rk.txt
   - 保存完整信息到 JSON 文件

### 批量注册流程

1. 循环注册指定数量的账号
2. 每个账号注册完成后等待随机时间（5-15秒）
3. 自动刷新代理连接
4. 统计成功和失败数量
5. 输出最终报告

## 🛠️ 高级功能

### 错误处理

程序包含完善的错误处理机制：

- **错误页面自动重试**: 检测到错误页面自动点击重试按钮
- **超时重试**: 超时操作自动重试
- **异常恢复**: 即使部分流程失败，也会保存已获取的信息

### 代理自动切换

- 使用隧道代理，每次请求自动切换IP
- 支持手动刷新代理连接
- 代理连接失败自动重试

### 灵活配置

- 所有配置集中在 `config.py`
- 支持开启/关闭各种功能
- 可自定义超时时间、重试次数等

## 📈 性能优化

- **并发处理**: 代理管理和浏览器操作异步进行
- **智能等待**: 动态调整等待时间，避免被检测
- **资源管理**: 及时释放浏览器资源
- **代理复用**: 隧道连接可复用，减少连接开销

## ⚠️ 注意事项

1. **代理配置**
   - 确保代理隧道可用
   - 建议使用隧道模式，IP自动切换
   - 代理账户需要有足够的流量

2. **邮箱服务**
   - 需要配置有效的 DuckMail API
   - 确保私有域名可用

3. **浏览器驱动**
   - 程序会自动下载 ChromeDriver
   - 首次运行可能需要较长时间

4. **运行环境**
   - Python 3.8+
   - 稳定的网络连接
   - 建议在服务器上运行

5. **合规使用**
   - 仅供学习和研究使用
   - 遵守相关服务条款
   - 注意使用频率，避免被限制

## 🐛 故障排查

### 问题1: 代理连接失败
```
解决方案:
1. 检查代理隧道地址是否正确
2. 检查用户名和密码
3. 运行 proxy_manager.py 测试代理连接
4. 查看代理账户余额和流量
```

### 问题2: 邮箱创建失败
```
解决方案:
1. 检查 DuckMail API 配置
2. 确认 API 密钥有效
3. 检查私有域名设置
```

### 问题3: ChromeDriver 错误
```
解决方案:
1. 删除已下载的 ChromeDriver
2. 重新运行程序自动下载
3. 检查 Chrome 浏览器版本
```

### 问题4: 验证码获取失败
```
解决方案:
1. 增加 EMAIL_VERIFICATION_TIMEOUT 时间
2. 检查邮箱API是否正常
3. 手动输入验证码（程序支持）
```

### 问题5: OAuth 失败
```
解决方案:
1. 检查代理是否正常
2. 增加重试次数 MAX_OAUTH_RETRIES
3. 查看 register.log 日志定位问题
```

## 📚 技术栈

- **Python 3.8+**
- **Selenium**: 浏览器自动化
- **undetected-chromedriver**: 反检测
- **Requests**: HTTP请求
- **DuckMail**: 临时邮箱服务
- **快代理**: 海外代理服务

## 🔐 安全建议

1. 不要将配置文件提交到公共仓库
2. 定期更换代理密码
3. 使用环境变量存储敏感信息
4. 限制日志文件的访问权限

## 📄 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题，请提交 Issue。

---

**祝您使用愉快！** 🎉

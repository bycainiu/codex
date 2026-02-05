from camoufox.sync_api import Camoufox
from playwright.sync_api import Page
import time
import requests
import random
import string
import re
from urllib.parse import urlparse, parse_qs
import secrets
import hashlib
import urllib3
import base64
import os
import faker
import random
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

TOTAL_ACCOUNTS = int(os.getenv("ACCOUNTS", 1000))
# Cloudflare 临时邮箱配置
CF_WORKER_DOMAIN = os.getenv("CF_WORKER_DOMAIN")
CF_EMAIL_DOMAIN = os.getenv("CF_EMAIL_DOMAIN")
CF_ADMIN_PASSWORD = os.getenv("CF_ADMIN_PASSWORD")

# OpenAI OAuth 配置
OAUTH_ISSUER = "https://auth.openai.com"
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_REDIRECT_URI = "http://localhost:1455/auth/callback"

# Output files
ACCOUNTS_FILE = "accounts.txt"
AK_FILE = "ak.txt"
RK_FILE = "rk.txt"

PROXY = os.getenv("OAI_PROXY")


def extract_code_from_url(url: str):
    if not url:
        return None
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        return code
    except Exception as e:
        print(f"❌ Failed to parse URL: {e}")
        return None


def generate_pkce():
    """生成 PKCE code_verifier 和 code_challenge"""
    code_verifier_bytes = secrets.token_bytes(64)
    code_verifier = base64.urlsafe_b64encode(code_verifier_bytes).rstrip(b'=').decode('ascii')

    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    
    return code_verifier, code_challenge


def generate_state():
    """生成随机 state 参数"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('ascii')


def build_authorize_url(code_challenge, state):
    """构造 OAuth 授权 URL"""
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": "openid profile email offline_access",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    query = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
    return f"{OAUTH_ISSUER}/oauth/authorize?{query}"


def exchange_code_for_tokens(code, code_verifier):
    """用 authorization code 换取 tokens"""
    response = requests.post(
        f"{OAUTH_ISSUER}/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "client_id": OAUTH_CLIENT_ID,
            "code_verifier": code_verifier,
        },
        proxies={
            "http": PROXY,
            "https": PROXY,
        } if PROXY else {},
        verify=False,
        timeout=30
    )

    if response.status_code == 200:
        return response.json()  # {id_token, access_token, refresh_token}
    else:
        print(f"[-] Exchange code for tokens failed: {response.status_code} - {response.text}")
        return None


def wait_for_callback_url(page: Page, expected_state, timeout=60):
    print(f"Waiting for callback URL (max {timeout}s)...")
    """等待 OAuth callback URL"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_url = page.evaluate("window.location.href")
        print(f"Current URL: {current_url}")
        if "callback" in current_url and "code=" in current_url:
            # 检查 state 是否匹配
            parsed = urlparse(current_url)
            params = parse_qs(parsed.query)
            state = params.get("state", [None])[0]
            if state == expected_state:
                return current_url
        time.sleep(1)
    return None


def perform_openai_oauth_login(page: Page, email: str, password: str):
    """执行 OAuth 登录并获取 tokens"""
    code_verifier, code_challenge = generate_pkce()
    state = generate_state()
    auth_url = build_authorize_url(code_challenge, state)
    print(f"Auth URL: {auth_url}")

    print("\n🌐 Performing OpenAI OAuth login...")

    # 在新标签页打开授权链接
    new_page = page.context.browser.new_page()
    new_page.goto(auth_url)
    time.sleep(3)

    try:
        print("📧 Entering email for OAuth...")
        email_input = new_page.wait_for_selector(
            'input[type="email"], input[name="email"], input[id="email"]',
            state="visible",
            timeout=30000
        )
        email_input.fill("")
        time.sleep(0.3)
        email_input.type(email, delay=30)
        print(f"   Entered email: {email}")
        time.sleep(1)

        print("   Clicking Continue...")
        continue_btn = new_page.wait_for_selector('button[type="submit"]', state="visible", timeout=10000)
        continue_btn.click()
        time.sleep(3)
    except Exception as e:
        print(f"⚠️ Email input step error: {e}")

    try:
        print("🔑 Entering password...")
        password_input = new_page.wait_for_selector(
            'input[type="password"], input[name="password"]',
            state="visible",
            timeout=30000
        )
        password_input.fill("")
        time.sleep(0.3)
        password_input.type(password, delay=30)
        print("   Entered password")
        time.sleep(1)

        print("   Clicking Continue...")
        continue_btn = new_page.wait_for_selector('button[type="submit"]', state="visible", timeout=10000)
        continue_btn.click()
        time.sleep(3)
    except Exception as e:
        print(f"⚠️ Password input step error: {e}")
        new_page.close()
        raise e
    
    callback_url = None
    try:
        print("   Clicking Continue...")
        continue_btn = new_page.wait_for_selector('button[type="submit"]', state="visible", timeout=10000)
        continue_btn.click()
        time.sleep(6)

        print("   Clicking Continue...")
        continue_btn = new_page.wait_for_selector('button[type="submit"]', state="visible", timeout=30000)
        continue_btn.click()
        time.sleep(3)

        # 等待 callback URL
        callback_url = wait_for_callback_url(new_page, state)
    finally:
        # 关闭标签页
        new_page.close()

    if not callback_url:
        print("\n⏰ Timeout waiting for callback")
        return None

    # 提取 code 并换取 tokens
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    code = params.get("code", [None])[0]

    if code:
        tokens = exchange_code_for_tokens(code, code_verifier)
        if tokens:
            print("✅ Successfully obtained OAuth tokens")
            return tokens
    return None

def get_random_user_agent():
    return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

def generate_random_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%"
    password = "".join(random.choice(chars) for _ in range(length))
    password = (
        random.choice(string.ascii_uppercase)
        + random.choice(string.ascii_lowercase)
        + random.choice(string.digits)
        + random.choice("!@#$%")
        + password[4:]
    )
    print(f"✅ Generated password: {password}")
    return password



def create_temp_email():
    print("Creating temporary email via Cloudflare...")

    url = f"https://{CF_WORKER_DOMAIN}/admin/new_address"
    try:
        # 生成随机邮箱名称
        letters1 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(4, 6)))
        numbers = ''.join(random.choices(string.digits, k=random.randint(1, 3)))
        letters2 = ''.join(random.choices(string.ascii_lowercase, k=random.randint(0, 5)))
        random_name = letters1 + numbers + letters2

        res = requests.post(
            url,
            json={
                "enablePrefix": True,
                "name": random_name,
                "domain": CF_EMAIL_DOMAIN,
            },
            headers={
                'x-admin-auth': CF_ADMIN_PASSWORD,
                "Content-Type": "application/json"
            },
            timeout=10,
            verify=False
        )
        if res.status_code == 200:
            data = res.json()
            cf_token = data.get('jwt')
            cf_email = data.get('address')
            if cf_email:
                print(f"✅ Email created: {cf_email}, token: {cf_token}")
                return cf_email, cf_token
            else:
                print("[-] 创建邮箱响应中缺少地址")
        else:
            print(f"[-] 创建邮箱接口返回错误: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Email creation error: {e}")
    return None, None


def fetch_emails(email: str, cf_token: str):
    try:
        limit = 10
        offset = 0
        res = requests.get(
            f"https://{CF_WORKER_DOMAIN}/api/mails",
            params={
                "limit": limit,
                "offset": offset,
            },
            headers={
                "Authorization": f"Bearer {cf_token}",
                "Content-Type": "application/json"
            },
            verify=False,
        )

        if res.status_code == 200:
            data = res.json()
            if data["results"]:
                return data["results"]
            return []
        else:
            print(f"  Fetch emails failed: HTTP {res.status_code}")
    except Exception as e:
        print(f"  Fetch emails error: {e}")
    return None


def extract_verification_code(email_content: str):
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
            print(f"  ✅ Extracted code: {code}")
            return code
    return None


def wait_for_verification_email(email: str, cf_token: str, timeout: int = 120):
    print(f"Waiting for verification email (max {timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        emails = fetch_emails(email, cf_token)
        if emails and len(emails) > 0:
            for email_item in emails:
                if not isinstance(email_item, dict):
                    continue

                # CF 邮箱格式：检查 sender 和 subject
                sender = email_item.get("source", "").lower()

                if "openai" in sender:
                    # 获取邮件内容
                    raw_content = email_item.get("raw", "")
                    code = extract_verification_code(raw_content)
                    if code:
                        return code
                else:
                    print(f"  Email from {sender} is not from OpenAI")
                    continue
        elapsed = int(time.time() - start_time)
        print(f"  Waiting... ({elapsed}s)", end="\r")
        time.sleep(3)
    print("\n⏰ Timeout waiting for email")
    return None


def save_account(email: str, password: str):
    """保存账号密码到 accounts.txt"""
    with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{email}:{password}\n")
    print(f"✅ Account saved to {ACCOUNTS_FILE}")


def save_tokens(access_token: str, refresh_token: str = None):
    """保存 token 到对应文件"""
    if access_token:
        with open(AK_FILE, "a", encoding="utf-8") as f:
            f.write(f"{access_token}\n")
        print(f"✅ Access token saved to {AK_FILE}")
    if refresh_token:
        with open(RK_FILE, "a", encoding="utf-8") as f:
            f.write(f"{refresh_token}\n")
        print(f"✅ Refresh token saved to {RK_FILE}")


def check_and_handle_error(page: Page, max_retries=5):
    for attempt in range(max_retries):
        try:
            page_source = page.content().lower()
            error_keywords = [
                "出错",
                "error",
                "timed out",
                "operation timeout",
                "route error",
                "invalid content",
            ]
            has_error = any(keyword in page_source for keyword in error_keywords)
            if has_error:
                try:
                    retry_btn = page.query_selector('button[data-dd-action-name="Try again"]')
                    if retry_btn:
                        print(
                            f"⚠️ Error page detected, clicking retry (attempt {attempt + 1}/{max_retries})..."
                        )
                        retry_btn.click()
                        wait_time = 5 + (attempt * 2)
                        print(f"  Waiting {wait_time}s before continuing...")
                        time.sleep(wait_time)
                        return True
                except Exception:
                    time.sleep(2)
                    continue
            return False
        except Exception as e:
            print(f"  Error check exception: {e}")
            return False
    return False

def get_browser():
    print("Initializing Camoufox browser...")
    config = {
        "headless": True,
        "proxy": {"server": PROXY} if PROXY else None,
        "geoip": True,
    }
    return Camoufox(**config)

def register_one_account(email: str = None, password: str = None):
    browser_context = get_browser()
    success = False

    try:
        with browser_context as browser:
            page = browser.new_page()
            if not email or not password:
                email, cf_token = create_temp_email()
                if not email:
                    print("Failed to get email, aborting.")
                    return None, None, False

                password = generate_random_password()
                url = "https://chat.openai.com/chat"
                print(f"Navigating to {url}...")
                page.goto(url)
                time.sleep(3)
                # screenshot the page
                page.screenshot(path="page.png")
                print("Screenshot saved to page.png")

                print("Waiting for signup button...")
                signup_button = page.wait_for_selector('[data-testid="signup-button"]', state="visible", timeout=600000)
                signup_button.click()
                print("Clicked signup button.")

                print("Waiting for email input...")
                email_input = page.wait_for_selector("#email", state="visible", timeout=120000)
                email_input.fill("")
                email_input.type(email, delay=30)
                print(f"Entered email: {email}")

                print("Clicking Continue button...")
                continue_btn = page.wait_for_selector('button[type="submit"]', state="visible")
                continue_btn.click()
                print("Clicked Continue.")
                time.sleep(2)

                print("Waiting for password input...")
                password_input = page.wait_for_selector('input[autocomplete="new-password"]', state="visible", timeout=120000)
                password_input.fill("")
                time.sleep(0.5)
                password_input.type(password, delay=50)
                print(f"Entered password.")
                time.sleep(2)

                print("Clicking Continue button...")
                for attempt in range(3):
                    try:
                        continue_btn = page.wait_for_selector('button[type="submit"]', state="visible", timeout=30000)
                        continue_btn.click()
                        print("Clicked Continue.")
                        break
                    except Exception as e:
                        print(f"  Attempt {attempt + 1} failed, retrying...")
                        time.sleep(2)

                time.sleep(3)
                while check_and_handle_error(page):
                    time.sleep(2)

                time.sleep(5)
                verification_code = wait_for_verification_email(email, cf_token)

                if not verification_code:
                    verification_code = input(
                        "Please enter the verification code manually: "
                    ).strip()

                if not verification_code:
                    print("❌ No verification code, aborting.")
                    return email, password, False

                print("Entering verification code...")
                while check_and_handle_error(page):
                    time.sleep(2)

                code_input = page.wait_for_selector('input[name="code"], input[placeholder*="代码"], input[aria-label*="代码"]', state="visible", timeout=60000)
                code_input.fill("")
                time.sleep(0.5)
                code_input.type(verification_code, delay=100)
                print(f"Entered code: {verification_code}")
                time.sleep(2)

                print("Clicking Continue button...")
                for attempt in range(3):
                    try:
                        continue_btn = page.wait_for_selector('button[type="submit"]', state="visible", timeout=30000)
                        continue_btn.click()
                        print("Clicked Continue.")
                        break
                    except Exception as e:
                        print(f"  Attempt {attempt + 1} failed, retrying...")
                        time.sleep(2)

                time.sleep(3)
                while check_and_handle_error(page):
                    time.sleep(2)

                print("Waiting for name input...")
                name_input = page.wait_for_selector('input[name="name"], input[autocomplete="name"]', state="visible", timeout=60000)
                name_input.fill("")
                time.sleep(0.5)
                name = faker.Faker("en_US").name()
                name_input.type(name, delay=50)
                print(f"Entered name: {name}")
                time.sleep(1)

                print("Entering birthday...")
                time.sleep(1)

                page.evaluate("document.querySelector('[id$=\"birthday\"]').click()")
                year_input = page.wait_for_selector('[data-type="year"]', state="attached", timeout=30000)
                year_input.scroll_into_view_if_needed()
                time.sleep(0.5)

                year_input.click()
                time.sleep(0.3)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.1)
                year = str(random.randint(1990, 2005))
                year_input.type(year, delay=100)
                time.sleep(0.5)

                month_input = page.query_selector('[data-type="month"]')
                month_input.click()
                time.sleep(0.3)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.1)
                month = str(random.randint(1, 12)).zfill(2)
                month_input.type(month, delay=100)
                time.sleep(0.5)

                day_input = page.query_selector('[data-type="day"]')
                day_input.click()
                time.sleep(0.3)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.1)
                day = str(random.randint(1, 28)).zfill(2)
                day_input.type(day, delay=100)

                print(f"Entered birthday: {year}/{month}/{day}")
                time.sleep(1)

                print("Clicking final Continue button...")
                continue_btn = page.wait_for_selector('button[type="submit"]', state="visible")
                continue_btn.click()
                print("Clicked Continue.")
            
            print("\n🔐 Performing OAuth login to get access token...")
            while True:
                try:
                    tokens = perform_openai_oauth_login(page, email, password)
                    break
                except Exception as e:
                    print(f"[-] OAuth login failed: {e}, retrying...")
                    time.sleep(1)
                    continue

            if tokens:
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")

                save_account(email, password)
                save_tokens(access_token, refresh_token)

                print("\n" + "=" * 50)
                print("🎉 Registration & OAuth completed!")
                print(f"Email: {email}")
                print(f"Password: {password}")
                print(f"Access Token: {access_token[:20]}...")
                if refresh_token:
                    print(f"Refresh Token: {refresh_token[:20]}...")
                print("=" * 50)

                success = True
            else:
                print("❌ Failed to obtain OAuth tokens")
                save_account(email, password)  # 保存账号即使 OAuth 失败

            print("Waiting before closing...")
            time.sleep(5)

    except Exception as e:
        print(f"An error occurred: {e}")
        if email and password:
            save_account(email, password)
    finally:
        print("Closing browser...")

    return email, password, success


def run_batch():
    print("\n" + "=" * 60)
    print(f"🚀 Starting batch registration for {TOTAL_ACCOUNTS} accounts")
    print("=" * 60 + "\n")

    success_count = 0
    fail_count = 0
    registered_accounts = []

    for i in range(TOTAL_ACCOUNTS):
        print("\n" + "#" * 60)
        print(f"📝 Registering account {i + 1}/{TOTAL_ACCOUNTS}")
        print("#" * 60 + "\n")

        email, password, success = register_one_account()

        if success:
            success_count += 1
            registered_accounts.append((email, password))
        else:
            fail_count += 1

        print("\n" + "-" * 40)
        print(f"📊 Progress: {i + 1}/{TOTAL_ACCOUNTS}")
        print(f"   ✅ Success: {success_count}")
        print(f"   ❌ Failed: {fail_count}")
        print("-" * 40)

        if i < TOTAL_ACCOUNTS - 1:
            wait_time = random.randint(5, 15)
            print(f"\n⏳ Waiting {wait_time}s before next registration...")
            time.sleep(wait_time)

    print("\n" + "=" * 60)
    print("🏁 BATCH REGISTRATION COMPLETED")
    print("=" * 60)
    print(f"Total: {TOTAL_ACCOUNTS}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print("\nResults saved to:")
    print(f"  - {ACCOUNTS_FILE} (email:password)")
    print(f"  - {AK_FILE} (access tokens)")
    print(f"  - {RK_FILE} (refresh tokens)")
    print("=" * 60)


if __name__ == "__main__":
    run_batch()

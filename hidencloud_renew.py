import json
import logging
import os
import re
import time
import base64
from bs4 import BeautifulSoup
from curl_cffi import requests

# 为了加密 GitHub Secret
try:
    from nacl import encoding, public
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HidenCloud:
    def __init__(self, cookie_str, tg_config=None):
        self.base_url = "https://hidencloud.com"
        self.cookie_str = cookie_str
        self.tg_config = tg_config
        self.session = requests.Session(impersonate="chrome110")
        self.username = "Unknown"
        self.balance = "未知"
        self.updated_cookies = False
        self.parse_and_set_cookies()

    def parse_and_set_cookies(self):
        """解析 Cookie 字符串并设置到 Session"""
        if not self.cookie_str:
            return
        
        cookies = {}
        for item in self.cookie_str.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        self.session.cookies.update(cookies)

    def get_cookie_string(self):
        """获取当前的 Cookie 字符串"""
        return "; ".join([f"{k}={v}" for k, v in self.session.cookies.get_dict().items()])

    def update_github_secret(self, new_cookie):
        """自动更新 GitHub Secret"""
        gh_pat = os.environ.get("GH_PAT")
        repo = os.environ.get("GITHUB_REPOSITORY")
        secret_name = "HIDEN_COOKIE"

        if not gh_pat or not repo:
            logger.warning("未找到 GH_PAT 或 GITHUB_REPOSITORY，跳过 Secret 更新")
            return

        if not HAS_NACL:
            logger.error("未安装 pynacl 库，无法加密并更新 Secret")
            return

        logger.info(f"正在尝试更新 GitHub Secret: {secret_name}")
        headers = {
            "Authorization": f"token {gh_pat}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            # 1. 获取公钥
            pub_key_resp = requests.get(
                f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                headers=headers
            )
            if pub_key_resp.status_code != 200:
                logger.error(f"获取公钥失败: {pub_key_resp.text}")
                return
            
            pub_key_data = pub_key_resp.json()
            public_key = pub_key_data['key']
            key_id = pub_key_data['key_id']

            # 2. 加密 Secret
            def encrypt(public_key: str, secret_value: str) -> str:
                public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
                sealed_box = public.SealedBox(public_key)
                encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
                return base64.b64encode(encrypted).decode("utf-8")

            encrypted_value = encrypt(public_key, new_cookie)

            # 3. 提交更新
            put_resp = requests.put(
                f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}",
                headers=headers,
                json={
                    "encrypted_value": encrypted_value,
                    "key_id": key_id
                }
            )
            if put_resp.status_code in [201, 204]:
                logger.info(f"✅ GitHub Secret {secret_name} 更新成功！")
            else:
                logger.error(f"❌ 更新 Secret 失败: {put_resp.text}")

        except Exception as e:
            logger.error(f"更新 Secret 过程出错: {e}")

    def get_hitokoto(self):
        """获取每日一言"""
        try:
            resp = requests.get("https://v1.hitokoto.cn/?encode=json", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return f"『{data['hitokoto']}』—— {data['from']}"
        except Exception:
            pass
        return "保持热爱，奔赴山海。"

    def send_tg_notification(self, message):
        """发送 Telegram 通知"""
        if not self.tg_config or not self.tg_config.get("bot_token") or not self.tg_config.get("chat_id"):
            return

        url = f"https://api.telegram.org/bot{self.tg_config['bot_token']}/sendMessage"
        
        hitokoto = self.get_hitokoto()
        # 优化通知排版
        formatted_message = (
            f"☁️ **HidenCloud 自动续费任务**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 **账号**: `{self.username}`\n"
            f"💰 **余额**: `{self.balance}`\n"
            f"🕒 **时间**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{message}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 **每日一言**:\n_{hitokoto}_"
        )

        payload = {
            "chat_id": self.tg_config["chat_id"],
            "text": formatted_message,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram 通知发送成功")
            else:
                logger.error(f"Telegram 通知发送失败: {resp.text}")
        except Exception as e:
            logger.error(f"发送 Telegram 通知出错: {e}")

    def get_csrf_token(self, url):
        """从页面中提取 CSRF Token"""
        try:
            resp = self.session.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, 'html.parser')
            token_meta = soup.find('meta', attrs={'name': 'csrf-token'})
            if token_meta:
                return token_meta.get('content')
            
            token_input = soup.find('input', attrs={'name': '_token'})
            if token_input:
                return token_input.get('value')
        except Exception as e:
            logger.error(f"获取 CSRF Token 失败: {e}")
        return None

    def check_login(self):
        """检查登录状态并获取用户名"""
        try:
            resp = self.session.get(f"{self.base_url}/dashboard", timeout=20, allow_redirects=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 提取用户名
                email_tag = soup.find('span', string=re.compile(r'.+@.+\..+'))
                if email_tag:
                    self.username = email_tag.get_text().strip()
                
                # 提取余额
                balance_tag = soup.find('h4', string=re.compile(r'¥|余额'))
                if balance_tag:
                    self.balance = balance_tag.get_text().strip()
                else:
                    # 尝试寻找包含金额的元素
                    amount_tag = soup.find(string=re.compile(r'¥\s*\d+\.\d+'))
                    if amount_tag:
                        self.balance = amount_tag.strip()
                
                return True
        except Exception as e:
            logger.error(f"登录状态检查异常: {e}")
        return False

    def get_service_ids(self):
        """获取所有服务 ID"""
        logger.info("正在获取服务列表...")
        try:
            resp = self.session.get(f"{self.base_url}/dashboard", timeout=20)
            ids = re.findall(r'service/(\d+)/manage', resp.text)
            return list(set(ids))
        except Exception as e:
            logger.error(f"获取服务 ID 失败: {e}")
            return []

    def renew_service(self, service_id):
        """对指定服务进行续期"""
        logger.info(f"正在为服务 {service_id} 申请续期...")
        manage_url = f"{self.base_url}/service/{service_id}/manage"
        token = self.get_csrf_token(manage_url)
        if not token:
            return False, "获取续期 Token 失败"

        renew_url = f"{self.base_url}/service/{service_id}/renew"
        data = {
            "_token": token,
            "days": "7"
        }
        headers = {"referer": manage_url}

        try:
            resp = self.session.post(renew_url, data=data, headers=headers, timeout=20)
            if resp.status_code == 200 or "payment" in resp.url or "invoice" in resp.url:
                return True, "申请成功"
            else:
                return False, f"续期请求失败: {resp.status_code}"
        except Exception as e:
            return False, f"续期异常: {e}"

    def pay_unpaid_invoices(self, service_id):
        """检测并支付未支付订单"""
        logger.info(f"正在检查服务 {service_id} 的未支付订单...")
        invoice_url = f"{self.base_url}/service/{service_id}/invoices?where=unpaid"
        try:
            resp = self.session.get(invoice_url, timeout=20)
            payment_ids = re.findall(r'payment/(\d+)', resp.text)
            if not payment_ids:
                return True, "无待支付订单"

            success_count = 0
            for p_id in payment_ids:
                p_url = f"{self.base_url}/payment/{p_id}"
                token = self.get_csrf_token(p_url)
                if not token: continue
                
                pay_resp = self.session.post(p_url, data={"_token": token}, timeout=20)
                if "成功" in pay_resp.text or pay_resp.status_code == 200:
                    success_count += 1
                else:
                    logger.warning(f"订单 {p_id} 支付失败，可能是余额不足")

            return True, f"支付完成 ({success_count}/{len(payment_ids)} 成功)"
        except Exception as e:
            return False, f"支付异常: {e}"

    def run_task(self):
        """运行完整续费任务"""
        if not self.check_login():
            logger.error("❌ Cookie 已失效或无法访问 Dashboard")
            self.send_tg_notification("❌ Cookie 已失效，请重新提取并更新 GitHub Secrets")
            return

        logger.info(f"账号 {self.username} 登录验证通过，开始执行任务...")
        service_ids = self.get_service_ids()
        if not service_ids:
            logger.warning("未找到任何活跃服务")
            return

        results = []
        success_count = 0
        fail_count = 0
        
        for s_id in service_ids:
            r_success, r_msg = self.renew_service(s_id)
            p_success, p_msg = self.pay_unpaid_invoices(s_id)
            
            status_icon = "✅" if r_success and p_success else "❌"
            results.append(f"{status_icon} **服务 {s_id}**\n   └ 续期: `{r_msg}`\n   └ 支付: `{p_msg}`")
            
            if r_success and p_success:
                success_count += 1
            else:
                fail_count += 1

        summary = f"📊 **执行统计**: 成功 `{success_count}` | 失败 `{fail_count}`\n\n"
        report = summary + "\n".join(results)
        
        logger.info(f"任务完成报告:\n{report}")
        self.send_tg_notification(report)

        # 检查并更新 Cookie
        new_cookie_str = self.get_cookie_string()
        if new_cookie_str != self.cookie_str:
            logger.info("检测到 Cookie 已刷新，准备同步到 GitHub Secrets")
            self.update_github_secret(new_cookie_str)

def main():
    config = {}
    # 按照参考项目逻辑：从环境变量 HIDEN_COOKIE 读取
    env_cookies = os.environ.get("HIDEN_COOKIE")
    
    # 兼容本地 config.json
    config_cookies = []
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, "config.json")
    
    if env_cookies:
        logger.info("从环境变量 HIDEN_COOKIE 加载账号信息")
        # 支持 & 或 换行符 分隔多账号
        account_cookies = re.split(r'[&\n]', env_cookies)
    elif os.path.exists(config_path):
        logger.info("从本地 config.json 加载账号信息")
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                accounts = config.get("accounts", [])
                account_cookies = []
                for acc in accounts:
                    if acc.get("cookies"):
                        # 将字典格式的 cookie 转回字符串
                        c_str = "; ".join([f"{k}={v}" for k, v in acc["cookies"].items()])
                        account_cookies.append(c_str)
        except Exception as e:
            logger.error(f"读取 config.json 失败: {e}")
            return
    else:
        logger.error("未找到 HIDEN_COOKIE 环境变量或 config.json")
        return

    # TG 配置
    tg_config = {
        "bot_token": os.environ.get("TG_BOT_TOKEN") or config.get("telegram", {}).get("bot_token"),
        "chat_id": os.environ.get("TG_CHAT_ID") or config.get("telegram", {}).get("chat_id")
    }

    for cookie_str in account_cookies:
        if not cookie_str.strip(): continue
        try:
            bot = HidenCloud(cookie_str, tg_config)
            bot.run_task()
        except Exception as e:
            logger.error(f"处理账号时发生异常: {e}")

if __name__ == "__main__":
    main()

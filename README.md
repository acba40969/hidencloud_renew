# HidenCloud 自动续费

<p align="left">
  <img src="https://img.shields.io/github/stars/SunshineList/hidencloud_renew?style=flat-square&logo=github" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/SunshineList/hidencloud_renew?style=flat-square&logo=github" alt="GitHub forks">
  <img src="https://img.shields.io/github/actions/workflow/status/SunshineList/hidencloud_renew/hidencloud_renew.yml?style=flat-square&logo=github-actions" alt="GitHub workflow status">
  <img src="https://img.shields.io/github/license/SunshineList/hidencloud_renew?style=flat-square" alt="GitHub license">
</p>

HidenCloud 自动续费脚本，支持多账号、TG 通知、Cookie 自动更新。

## 核心功能

- **自动续期**：默认续期 7 天。
- **自动扣费**：检测到未支付订单时自动用账户余额支付。
- **TG 推送**：包含账号、余额、执行结果及每日一言。
- **持久化**：配合 GitHub PAT 可自动回写 Cookie，不用频繁手动更新 Secret。
- **代理出口**：支持配置 SOCKS5 代理作为请求出口 IP（GitHub Actions 服务器 IP 段容易被风控时很有用）。

-----

## 快速配置 (GitHub Actions)

### 1. 获取 Cookie

1. 浏览器登录 [HidenCloud](https://hidencloud.com)。
1. 按 `F12` 打开开发者工具，点击 `Network` (网络) 标签。
1. 刷新页面，找到任意一个请求，在 `Request Headers` (请求头) 中找到 `cookie` 字段。
1. 复制那一长串内容（包含 `hidencloud_session` 等）。

### 2. 设置 Secrets

在 GitHub 仓库的 `Settings` -> `Secrets and variables` -> `Actions` 下添加：

- **`HIDEN_COOKIE`**: 刚才复制的 Cookie。如果要跑多账号，用 `&` 或换行符隔开。
- **`TG_BOT_TOKEN`**: 联系 [@BotFather](https://t.me/BotFather) 创建机器人获取。
- **`TG_CHAT_ID`**: 给 [@userinfobot](https://t.me/userinfobot) 发消息获取。
- **`GH_PAT`**: (可选) [在此生成](https://github.com/settings/tokens)，勾选 `repo` 权限。用于让脚本自动更新 Cookie。
- **`SOCKS_PROXY`**: (可选) 用于指定出口 IP 的 SOCKS5 代理，格式示例：
  - 无认证：`socks5h://1.2.3.4:1080`
  - 带账号密码：`socks5h://user:pass@1.2.3.4:1080`
  
  推荐使用 `socks5h://`（而非 `socks5://`），让 DNS 解析也通过代理完成，避免本地 DNS 泄露真实出口信息。所有访问 HidenCloud 的请求都会走该代理；Telegram 通知、每日一言、GitHub Secret 更新等辅助请求不受影响，仍直连。

-----

## 本地运行

如果想先在本地跑一下：

1. 安装依赖：
   
   ```bash
   pip install curl_cffi beautifulsoup4 pynacl pysocks
   ```
1. 修改 `config.json` 填入信息（如需代理，可在根节点加一行 `"proxy": "socks5h://user:pass@1.2.3.4:1080"`，环境变量 `SOCKS_PROXY` 优先级更高）。
1. 执行：
   
   ```bash
   python hidencloud_renew.py
   ```

-----

## 常见问题

- **为什么登录失败？**
  脚本目前不走账号密码登录（为了绕过 Cloudflare 验证码），只认 Cookie。如果提示失效，请按照上面的步骤重新抓取。
- **GitHub Actions 没跑？**
  确认 `.github/workflows` 文件夹在项目最根部，不要塞进子文件夹里。
- **Cookie 自动更新不生效？**
  检查 `GH_PAT` 是否配置正确且具备 `repo` 权限。
- **代理不生效或报错 `Missing dependencies for SOCKS support`？**
  确认依赖里装了 `pysocks`（`pip install pysocks`），GitHub Actions workflow 中已默认包含。
- **想验证代理是否真的生效？**
  可临时把 `manage_url` 替换为 `https://api.ipify.org`、跑一次脚本看返回的出口 IP 是否变化，确认后再恢复。

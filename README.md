<div align="center">

# 📱 WorkBuddy 云端签到助手

**没有电脑，也能每天自动领 WorkBuddy 积分**

[![License: MIT](https://img.shields.io/badge/License-MIT-8B5CF6?style=flat&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x%20标准库-1F6FEB?style=flat&logo=python&logoColor=white)]()
[![Platform](https://img.shields.io/badge/适用-云端沙箱%20%7C%20手机%20App%20%7C%20小程序-10B981?style=flat)]()

</div>

> 你只需要做一件事：**复制下面那段话，发给 WorkBuddy**。剩下的它自己做。
>
> 全程不用懂代码、不用装东西、不用有电脑。

---

## 🚀 复制这段，发给 WorkBuddy

在 WorkBuddy 的 App 或小程序里，把下面这一整段粘贴发送：

```text
帮我在这个环境里配置 WorkBuddy 每日自动签到（每天 00:05 自动领积分）。按下面做：

0. 先自检：执行 which codebuddy; python3 --version; git --version
   三个都得有。缺 codebuddy 就直接告诉我，别往下做。

1. 取脚本：
   git clone https://gh-proxy.com/https://github.com/88lin/workbuddy-auto-signin.git /workspace/workbuddy-auto-signin

2. 拿登录凭据（关键，别跳步）：
   这台机器的登录态是平台注入的，CLI 不会写凭据文件，所以脚本会报 NO_AUTH。必须让 CLI 走授权流程：
   - 用 Python 的 pty 模块在伪终端里启动 codebuddy（不能用 -p 模式，那样 /login 不生效）
   - 启动前 unset：ACC_PRODUCT_CONFIG_V2、ACC_PRODUCT_CONFIG_V3、X_IDE_AUTH_PROXY、IDE_EDITOR_SERVER_AUTH_TYPE
   - 伪终端窗口设成 250 列，否则登录链接会被折行截断，拿到的是半截
   - 检测到「trust the files」就发 \r 确认；再发 /login\r；检测到「Select login method」再发 \r 选「中国站」
   - 按键一律用 \r（不是 \n）
   - 从输出里正则提取完整的 https://copilot.tencent.com/login?... 链接发给我
   - 进程保持运行等我授权，轮询 ~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info 是否生成（且非空）
   拿到登录链接后停下来等我，不要自己空转重试。

3. 我登录完你再继续：
   python3 /workspace/workbuddy-auto-signin/signin.py doctor
   python3 /workspace/workbuddy-auto-signin/signin.py auto
   doctor 里 credential_format 必须是 plaintext；auto 实跑一次确认积分到账。

4. 建定时任务（建两条）：
   这台机器没有 crontab、systemd 也起不来，只能用 WorkBuddy 的自动化功能，不要尝试系统定时任务。
   - 第一条「每日自动领 WorkBuddy 积分」：每天执行，Cron 0 5 0 * * *（每天 00:05），时区 Asia/Shanghai
   - 第二条「WorkBuddy 签到轮询兜底」：按间隔执行，Cron 0 0 */4 * * *（每 4 小时）
   两条的执行指令都用：运行 python3 /workspace/workbuddy-auto-signin/signin.py auto，把命令输出的 JSON 里 report 字段的内容，直接一句话汇报给我。若 JSON 的 needs_attention 为 true 或命令退出码非 0，额外提醒我处理。
   第二条也用 auto、不要用 silent-poll：它会先看签到状态、没签才补，能兜住 00:05 那次没跑成的情况；已签过只是一次查询，不会重复领取。
```

---

## ⚠️ 中途你需要动手一次（就一次）

跑到一半，它会发给你一个链接，长这样：

```
https://copilot.tencent.com/login?platform=CLI&state=...
```

这时候请：

1. **把这个链接发到微信聊天框**（发给自己或文件传输助手都行）
2. **从微信里点开它**，登录你的 WorkBuddy 账号
3. 登录完，它会自动接着把剩下的做完

> [!IMPORTANT]
> **一定要从微信里点开。** 用手机浏览器或 Edge 打开会被跳转到小程序、授权走不完，
> 表现为它一直显示 `Waiting for auth...` 却始终没反应。实测：微信点开 2 分 38 秒成功，
> 浏览器打开失败。

> [!TIP]
> 全部跑完后，去 App / 小程序的**自动化任务列表**，点进那两条任务，**编辑 → 选模型 hy3**（免费）。
> 创建任务的接口没有模型参数，模型只能在界面上选。

**这就是全部了。** 之后每天 00:05 它会自动签到，你什么都不用管。

---

## ❓ 这是干嘛的 / 我为什么需要它

[workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin) 是一个自动领
WorkBuddy 每日签到积分的脚本。它在 Windows 和 macOS 上装好桌面端就能跑，但**云端沙箱
（手机 App / 小程序背后那台 Linux 服务器）没有桌面端**，登录凭据不会自动写到文件里，
脚本就一直报 `NO_AUTH`。

这个仓库补的就是那一步：帮你在这类环境里拿到登录凭据，然后把每日任务建好。

**如果你有装了 WorkBuddy 桌面端的电脑，你不需要这个仓库**，直接用主仓库就行。

---

## 🛠️ 想自己跑脚本

```bash
python3 scripts/cli_login.py                       # 默认中国站，等 25 分钟
python3 scripts/cli_login.py --site international  # 国际站
python3 scripts/cli_login.py --wait 600            # 只等 10 分钟
python3 scripts/cli_login.py --log /tmp/tui.log    # TUI 原始输出落盘，方便排查
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--wait` | 1500 | 等你授权的秒数 |
| `--cwd` | `/workspace/workbuddy-auto-signin` | 仓库目录，必须已存在 |
| `--cred` | `~/.local/share/CodeBuddyExtension/.../Tencent-Cloud.coding-copilot.info` | 期待落地的凭据路径 |
| `--site` | `china` | 登录站点：`china` / `international` / `enterprise` / `ioa` |
| `--log` | 无 | 把 TUI 原始输出写到文件 |

输出三行之一：`LOGIN_URL=...`（发给用户去点）、`CREDENTIAL_READY=...`（成功）、
`ERROR=...`（失败原因，人类可读）。退出码 0 成功 / 1 失败。

脚本靠**检测屏幕文字**决定什么时候按键（不再靠写死的秒数），每一步都有超时，
失败会说清楚卡在哪一步。进程退出时按进程组回收，不留残留。

---

## 📋 已知限制

- 这套方案依赖平台的内部实现（TUI 交互、注入变量、微信跳转），**平台改版就可能失效**。
  失效的话到主仓库看有没有更新。
- 云端沙箱没有 `crontab`、`systemd` 也起不来，所以定时只能走 WorkBuddy 自动化，
  每次会消耗一次模型调用（选 hy3 可免）。
- 只适用于云端沙箱 / 手机 App。装了桌面端的 Win / macOS 用户请用主仓库。

---

## 🙏 相关

- 主仓库（签到脚本本体）：[88lin/workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin)
- 国内镜像（GitHub 慢时用）：`https://gh-proxy.com/` + 原链接

## 📄 协议

[MIT](LICENSE)

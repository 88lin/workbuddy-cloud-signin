---
name: workbuddy-linux-signin
description: "在 Linux / 云端沙箱 / 手机 App 环境里配置 WorkBuddy 每日自动签到。当用户要在没有图形界面的 Linux 或 WorkBuddy 手机 App 所连的云端沙箱上跑 workbuddy-auto-signin、遇到 NO_AUTH 找不到登录凭据、或要给没有电脑的人设置自动签到时使用。关键词：WorkBuddy 签到、自动签到、NO_AUTH、凭据找不到、Linux 签到、手机 App 签到、每日积分"
version: "1.0.0"
author: "88lin"
created: "2026-10-11"
updated: "2026-10-11"
---

# WorkBuddy 每日签到（Linux / 云端沙箱 / 手机 App）

让 [workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin) 在没有
WorkBuddy 桌面端的环境里跑起来。脚本本身是纯 Python 标准库，Linux 上直接能跑，
**唯一的卡点是登录凭据**——本技能解决的就是这件事。

## 适用判断

先确认环境，再决定路线：

```bash
python3 --version                    # 3.x 即可，无第三方依赖
curl -s -o /dev/null -w '%{http_code}' https://copilot.tencent.com   # 200 说明通的
which crontab; systemctl status       # 大概率：crontab 不存在、systemd 起不来
python3 /workspace/workbuddy-auto-signin/signin.py doctor   # 报 NO_AUTH 就继续往下走
```

| 能力 | 结论 |
|---|---|
| 脚本在 Linux 运行 | 支持，纯标准库 |
| 凭据探测 | 支持，读 `~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info` |
| 系统级定时（cron / systemd） | **不支持**，仓库没提供，容器里也没有 |
| 定时方式 | 只能用**模式 A：WorkBuddy 自动化**（README 里唯一标注支持 Linux 的方式） |

## 流程

### 1. 取脚本（两个仓库）

```bash
git clone https://gh-proxy.com/https://github.com/88lin/workbuddy-auto-signin.git /workspace/workbuddy-auto-signin
git clone https://gh-proxy.com/https://github.com/88lin/workbuddy-cloud-signin.git /workspace/workbuddy-cloud-signin
```

第二个仓库提供登录脚本。**必须走现成脚本，不要让 AI 自己写 pty 脚本**——
坑位 1–5 全在里面，现场写必然重蹈覆辙。

### 2. 拿登录凭据（核心）

云端沙箱的登录态是平台用 `ACC_PRODUCT_CONFIG_V2/V3`（`type=custom-token`）注入的，
CLI 走注入模式，**不会把凭据写成文件**，所以脚本报 `NO_AUTH`。

脚本会把注入摘掉、让 CLI 退回 `cli-external-link` 流程
（生成登录 URL → 微信授权 → 写凭据文件）：

```bash
python3 /workspace/workbuddy-cloud-signin/scripts/cli_login.py --wait 1500 --cwd /workspace/workbuddy-auto-signin
```

常用参数：`--wait` 等待秒数（默认 1500）、`--cwd` 仓库目录（必须已存在）、
`--site` 登录站点（`china` 默认 / `international` / `enterprise` / `ioa`）、
`--log` 把 TUI 原始输出落盘排查。
脚本靠**检测屏幕文字**决定何时按键（不再靠写死的秒数），每一步都有超时，
失败会打印 `ERROR=<卡在哪一步>`，前置检查失败也会友好报错而不是抛堆栈。

脚本会打印一行 `LOGIN_URL=https://copilot.tencent.com/login?platform=CLI&state=...`，
**把这一行原样发给用户，让他把链接发到微信聊天框、从微信里点开登录**（见坑位 6）。
进程在后台等回调，授权成功后打印 `CREDENTIAL_READY=<路径>` 并退出。

用户的授权动作必须由人完成，AI 代劳不了——拿到 URL 后停下来等用户，不要空转重试。

### 3. 验证

```bash
python3 /workspace/workbuddy-auto-signin/signin.py doctor
# 期望：{"result": "AUTH_READY", "credential_format": "plaintext", ...}
python3 /workspace/workbuddy-auto-signin/signin.py auto    # 实跑一次，确认积分到账
```

`credential_format` 必须是 `plaintext`。若是 `sym-v1` 说明拿到的是桌面端加密凭据，
解密要调 WorkBuddy 客户端的 Electron 运行时，Linux 上没有，只能换一份明文凭据。

### 4. 建定时任务（建两条）

只能用**模式 A**（WorkBuddy 自动化），不能用 cron/systemd。用「自动化任务」功能按下面
参数建，Cron 是 6 位（`秒 分 时 日 月 周`）：

**任务一 · 每日签到（主力）**

| 参数 | 值 |
|---|---|
| 名称 | 每日自动领 WorkBuddy 积分 |
| 频率 | 每天执行（daily） |
| Cron | `0 5 0 * * *`（每天 00:05） |
| 时区 | Asia/Shanghai |
| 超时 | 300 秒（脚本自设预算 420 秒，够用） |

**任务二 · 每 4 小时轮询（兜底）**

| 参数 | 值 |
|---|---|
| 名称 | WorkBuddy 签到轮询兜底 |
| 频率 | 按间隔执行（interval） |
| Cron | `0 0 */4 * * *`（每 4 小时） |
| 时区 | Asia/Shanghai |

两条任务的执行指令都用这一句：

```text
运行 python3 /workspace/workbuddy-auto-signin/signin.py auto，
把命令输出的 JSON 里 report 字段的内容，直接一句话汇报给我。
若 JSON 的 needs_attention 为 true 或命令退出码非 0，额外提醒我处理。
```

**轮询也用 `auto`，不要用 `silent-poll`**：`auto` 会先查签到状态、未签才补，
所以它能兜住 00:05 那次没跑成的情况；已签过时只是一次查询，不会重复领取。

> **关于模型**：创建任务的接口只有 `--name` / `--cron` / `--prompt`
> / `--frequency-type` / `--timezone` / `--timeout` / `--retry-count` 等参数，
> **没有模型参数**，脚本侧指定不了。
> 但**模型可以在 App / 小程序的任务界面里选**——建完任务后点进任务编辑，
> 把模型选成 hy3（免费）即可，这一步要提醒用户自己做。

## 坑位清单

这 6 条都是实测踩出来的，写提示词时务必带上，否则 AI 会反复试错：

1. **`-p` 模式下 `/login` 不生效**。`codebuddy -p "/login"` 只回一句
   "Authentication required. Please use /login"，必须在 TUI 里敲斜杠命令，
   所以要用伪终端（`pty`）驱动。
2. **按键要用 `\r` 不是 `\n`**。TUI 认 `\r` 为回车，管道喂 `\n` 完全没反应。
3. **先过「是否信任此目录」提示**。TUI 启动后卡在信任确认，不先回车就到不了登录界面。
   按**屏幕出现的文字**触发，别用写死的秒数（慢机器会错过）：
   看到 `trust the files` 发 `\r` → 发 `/login\r` → 看到 `Select login method` 发 `\r`。
4. **终端窗口要够宽**。默认 80 列会把登录 URL 折行截断，拿到的是半截链接。
   设 250 列（`TIOCSWINSZ`）。
5. **必须摘掉注入变量**。`ACC_PRODUCT_CONFIG_V2`、`ACC_PRODUCT_CONFIG_V3`、
   `X_IDE_AUTH_PROXY`、`IDE_EDITOR_SERVER_AUTH_TYPE`，不摘就永远走 custom-token，
   生成不出登录 URL。
6. **登录链接要从微信里点开，不要用系统浏览器**。实测两种方式：
   用系统浏览器打开会被劫持跳转到 WorkBuddy 小程序、授权流程中断；
   把链接发到微信聊天框、再从微信里点开登录，才能走完授权（实测 2 分 38 秒落地）。
   登录途中跳转到小程序是正常的，走完即可。
   无论哪种方式，只要 CLI 一直刷 `Waiting for auth...` 且凭据文件不生成，
   就是授权没走完，换另一种打开方式重试。

## 实测记录

2026-10-11 在 WorkBuddy 手机 App 所连的云端沙箱（`CLIENT_INFO_IDE_TYPE=WorkBuddy_APP`）
完整跑通：生成链接 → 链接发到微信聊天框、从微信点开登录 → 约 2 分 38 秒凭据落地 →
`doctor` 返回 `plaintext` → `auto` 返回 `ALREADY`（今日已签，今日 +100、连续 12 天、
累计 1200 积分，均真实数据）。
同一链接用系统浏览器打开则失败（被劫持跳小程序）。
CLI 等待授权用的是**服务端轮询**，不是本地端口回调，所以沙箱无需开放入站端口。

（更早一次尝试曾出现：微信点开后停在小程序、授权没走完、干等 6 分钟无果。
因此两种打开方式都可能失败，判定标准是凭据文件是否生成，不是打开方式。）

## 凭据格式

脚本要的 JSON 结构（明文）：

```json
{
  "auth":    {"accessToken": "<字符串>", "domain": "..."},
  "account": {"uid": "...", "enterpriseId": "..."}
}
```

`accessToken` 是**字符串**才是明文可用；是 `{"$wbEncrypted":1,"envelope":...}`
这种对象就是 `sym-v1` 加密的，Linux 解不开。桌面端写的 `workbuddy-desktop.info`
多半是加密的，CodeBuddy CLI / VS Code 扩展写的
`Tencent-Cloud.coding-copilot.info` 才是明文。

## 排错

| 现象 | 处理 |
|---|---|
| `NO_AUTH` | 走第 2 步重新授权 |
| `credential_format: sym-v1` | 换明文凭据，别用桌面端加密那份 |
| `AUTH_REJECTED` / HTTP 401 | 登录态过期，重新授权 |
| URL 只拿到半截 | 终端窗口太窄，见坑位 4 |
| `/login` 界面不出来 | 按键用了 `\n`，或没先过信任提示，见坑位 2、3 |

> 给朋友直接用：整段复制，粘贴到她的 WorkBuddy App 里发送即可。
> 她不需要有电脑，全程在手机上完成（最后一步点链接登录）。

---

帮我在这个环境里配置 WorkBuddy 每日自动签到（每天 00:05 自动领积分）。按下面做：

**0. 先自检（5 秒，不行就直接告诉我，别硬做）**

```
which codebuddy; python3 --version; git --version
```

三个都得有。缺 `codebuddy` 就跑不了第 2 步的登录流程，直接告诉我，我换别的办法给你凭据。

**1. 取脚本**

```
git clone https://gh-proxy.com/https://github.com/88lin/workbuddy-auto-signin.git /workspace/workbuddy-auto-signin
```

**2. 拿登录凭据（关键，别跳步）**

这台机器的登录态是平台注入的，CLI 不会写凭据文件，所以脚本会报 `NO_AUTH`。必须让 CLI 走浏览器授权流程：

- 用 Python 的 `pty` 模块在伪终端里启动 `codebuddy`（**不能用 `-p` 模式**，那样 `/login` 不生效）
- 启动前 unset 这几个环境变量：`ACC_PRODUCT_CONFIG_V2`、`ACC_PRODUCT_CONFIG_V3`、`X_IDE_AUTH_PROXY`、`IDE_EDITOR_SERVER_AUTH_TYPE`
- 伪终端窗口设成 250 列，否则登录链接会被折行截断，拿到的是半截
- 按键一律用 `\r`（**不是 `\n`**），**按屏幕出现的文字触发**，别用写死的秒数：看到「trust the files」发 `\r` 确认信任 → 接着发 `/login\r` → 看到「Select login method」再发 `\r` 选「中国站」
- 从输出里正则提取完整的 `https://copilot.tencent.com/login?...` 链接发给我
- **把这个链接发到微信聊天框，再从微信里点开登录**。已实测：系统浏览器打开会被劫持跳到 WorkBuddy 小程序、授权中断；从微信点开才能走完（2 分 38 秒落地）。登录途中跳小程序是正常的，走完即可
- 进程保持运行等我授权，轮询 `~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info` 是否生成
- 判断依据：CLI 显示 `Waiting for auth... (Press ESC to cancel)` 是正常等待，不是卡死；只有授权真完成才会生成凭据文件

**拿到登录链接后停下来等我，不要自己空转重试。**

**3. 我登录完你再继续**

```
python3 /workspace/workbuddy-auto-signin/signin.py doctor
python3 /workspace/workbuddy-auto-signin/signin.py auto
```

`doctor` 里 `credential_format` 必须是 `plaintext`；`auto` 实跑一次确认积分到账。

**4. 建定时任务（建两条）**

这台机器没有 crontab、systemd 也起不来，**只能用 WorkBuddy 的自动化功能**，不要尝试系统定时任务。

- 第一条「每日自动领 WorkBuddy 积分」：每天执行，Cron `0 5 0 * * *`（每天 00:05），时区 Asia/Shanghai
- 第二条「WorkBuddy 签到轮询兜底」：按间隔执行，Cron `0 0 */4 * * *`（每 4 小时）

两条的执行指令都用：

```
运行 python3 /workspace/workbuddy-auto-signin/signin.py auto，把命令输出的 JSON 里 report 字段的内容，直接一句话汇报给我。若 JSON 的 needs_attention 为 true 或命令退出码非 0，额外提醒我处理。
```

第二条也用 `auto`、不要用 `silent-poll`：它会先看签到状态、没签才补，能兜住 00:05 那次没跑成的情况；已签过只是一次查询，不会重复领取。

**建完后还有一步别漏**：创建任务的接口没有模型参数，模型只能在界面上选。去 App / 小程序的自动化任务列表，点进这两条任务编辑，把模型选成 **hy3**（免费）。时间和频率也能在那儿改。

**注意**：`credential_format` 若是 `sym-v1`，说明拿到的是桌面端加密凭据，解密要调 WorkBuddy 客户端，Linux 上解不开，需要换一份明文凭据。

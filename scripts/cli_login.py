#!/usr/bin/env python3
"""在伪终端里驱动 codebuddy 的 /login，拿到登录 URL 并等待授权回调。

为什么需要这个脚本
------------------
云端沙箱的登录态是平台用 ACC_PRODUCT_CONFIG_V2/V3（type=custom-token）注入的，
CLI 走注入模式，不会把凭据写进文件，签到脚本因此报 NO_AUTH。
把这两个变量摘掉后，CLI 会退回 product.json 里的 cli-external-link 流程：
生成登录 URL -> 用户在微信里授权 -> 凭据落到
~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info

为什么必须用伪终端
------------------
`codebuddy -p "/login"` 只会回一句 "Authentication required. Please use /login"，
登录命令在非交互模式下不生效，必须进 TUI 敲斜杠命令。

用法
----
    python3 cli_login.py                      # 默认中国站，等 25 分钟
    python3 cli_login.py --site international # 国际站
    python3 cli_login.py --wait 600           # 只等 10 分钟

输出（stdout，逐行）：
    LOGIN_URL=<完整登录链接>      发给用户，让他在微信里点开登录
    CREDENTIAL_READY=<路径>       授权成功、凭据已落地
    ERROR=<原因>                  前置检查失败等，人类可读

退出码：0 成功拿到凭据 / 1 超时或失败
"""

import argparse
import fcntl
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import time

DEFAULT_CRED = os.path.expanduser(
    "~/.local/share/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info")
DEFAULT_CWD = "/workspace/workbuddy-auto-signin"
# 平台注入的登录态变量，摘掉才会走正常的授权流程
DROP_ENV = ("ACC_PRODUCT_CONFIG_V2", "ACC_PRODUCT_CONFIG_V3", "X_IDE_AUTH_PROXY",
            "IDE_EDITOR_SERVER_AUTH_TYPE")
COLS = 250  # 窗口太窄会把登录 URL 折行截断
ROWS = 60

# 按键一律用 \r —— 这是 TUI 认的回车键，\n 无效
ENTER = b"\r"
DOWN = b"\x1b[B"

# 登录方式在菜单里的顺序：中国站 / 国际站 / 企业域名 / iOA
SITE_STEPS = {"china": 0, "international": 1, "enterprise": 2, "ioa": 3}

# TUI 里等待出现的标志文字（中英文都认）
RE_TRUST = re.compile(r"trust the files|信任", re.IGNORECASE)
RE_METHOD = re.compile(r"select login method|登录方式", re.IGNORECASE)
# 登录链接可能出现的域名
RE_URL = re.compile(
    r"https://[\w.-]*(?:copilot\.tencent\.com|copilot\.qq\.com|codebuddy\.cn"
    r"|codebuddy\.ai|workbuddy\.cn)/[^\s]*login\?[^\s]*", re.IGNORECASE)
RE_ANSI = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]")


def die(reason):
    print("ERROR=%s" % reason, flush=True)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="驱动 codebuddy 登录并等待授权回调")
    ap.add_argument("--wait", type=float, default=1500.0, help="等待用户授权的秒数")
    ap.add_argument("--cwd", default=DEFAULT_CWD, help="codebuddy 的工作目录")
    ap.add_argument("--cred", default=DEFAULT_CRED, help="期望落地的凭据文件路径")
    ap.add_argument("--site", default="china", choices=sorted(SITE_STEPS),
                    help="登录站点，决定在菜单里往下按几次方向键")
    ap.add_argument("--log", default=None, help="TUI 原始输出落盘路径，默认不写文件")
    args = ap.parse_args()

    # 前置检查：不检查的话会直接抛 FileNotFoundError 堆栈
    if not os.path.isdir(args.cwd):
        die("工作目录不存在：%s（先 clone 仓库，或用 --cwd 指定）" % args.cwd)
    if shutil.which("codebuddy") is None:
        die("PATH 里找不到 codebuddy 命令，本环境不适用此方案")
    cred_dir = os.path.dirname(args.cred) or "."
    if not os.path.isdir(cred_dir):
        os.makedirs(cred_dir, exist_ok=True)

    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    try:
        proc = subprocess.Popen(["codebuddy"], stdin=slave, stdout=slave, stderr=slave,
                                env=env, cwd=args.cwd, start_new_session=True)
    except OSError as exc:
        die("启动 codebuddy 失败：%s" % exc)
    os.close(slave)

    log = open(args.log, "wb", buffering=0) if args.log else None
    started = time.time()
    buf = b""
    url = None
    sent_trust = sent_login = sent_method = False
    # 每步的耐心上限：没等到标志文字就报错，而不是干等到总超时
    step_deadline = started + 90.0

    print("PID=%s cwd=%s site=%s waiting up to %.0fs"
          % (proc.pid, args.cwd, args.site, args.wait), flush=True)

    try:
        while time.time() - started < args.wait:
            ready, _, _ = select.select([master], [], [], 0.5)
            if ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                if log:
                    log.write(data)
                step_deadline = time.time() + 60.0  # 有输出就续命

            text = RE_ANSI.sub(b"", buf).decode("utf-8", "ignore")

            # 第 1 步：过「是否信任此目录」
            if not sent_trust and RE_TRUST.search(text):
                os.write(master, ENTER)
                sent_trust = True
                buf = b""
                time.sleep(1.5)
                continue

            # 第 2 步：敲 /login（信任确认后界面已就绪）
            if sent_trust and not sent_login:
                os.write(master, b"/login" + ENTER)
                sent_login = True
                buf = b""
                step_deadline = time.time() + 60.0
                continue

            # 第 3 步：选登录站点
            if sent_login and not sent_method and RE_METHOD.search(text):
                steps = SITE_STEPS[args.site]
                os.write(master, DOWN * steps + ENTER if steps else ENTER)
                sent_method = True
                buf = b""
                step_deadline = time.time() + 90.0
                continue

            # 第 4 步：提取登录链接
            if url is None:
                found = RE_URL.findall(text)
                if found:
                    url = max(found, key=len)
                    print("LOGIN_URL=%s" % url, flush=True)

            # 第 5 步：等凭据落地，且必须非空
            if os.path.isfile(args.cred) and os.path.getsize(args.cred) > 0:
                print("CREDENTIAL_READY=%s" % args.cred, flush=True)
                return 0

            if time.time() > step_deadline:
                stage = ("等待信任提示" if not sent_trust else
                         "等待 /login 生效" if not sent_login else
                         "等待登录方式菜单" if not sent_method else
                         "等待登录链接" if url is None else "等待授权回调")
                print("ERROR=%s超时（%.0fs）。TUI 可能界面有变，可用 --log 落盘排查"
                      % (stage, time.time() - started), flush=True)
                return 1

        print("ERROR=总超时 %.0fs，未拿到凭据。url=%s" % (args.wait, bool(url)), flush=True)
        return 1
    finally:
        if log:
            log.close()
        # start_new_session 会把进程放进新会话，按组回收避免残留
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())

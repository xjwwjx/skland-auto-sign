#!/usr/bin/env python3
"""
森空岛自动签到脚本
支持明日方舟（角色签到）+ 明日方舟：终末地（角色签到 + 登岛检票）

签名流程: path + body/query + timestamp + headerCA_json → HMAC-SHA256 → MD5
参考: https://github.com/bwmgd/skyland-auto-sign
"""

import requests
import os
import sys
import json
import hashlib
import hmac
import time
import uuid
import base64
import ctypes
from urllib.parse import urlparse
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  常量配置
# ═══════════════════════════════════════════════════════════════

SK_BASE = "https://zonai.skland.com"
SK_API = f"{SK_BASE}/api/v1"
SK_WEB = f"{SK_BASE}/web/v1"
AS_BASE = "https://as.hypergryph.com"

TIMEOUT = 15
APP_CODE = "4ca99fa6b56cc2ba"
UA = "Skland/1.5.1 (com.hypergryph.skland; build:100501001; Android 34; ) Okhttp/4.11.0"

# 不同游戏的签名参数（dId=None 表示使用随机值）
SIGN_PROFILES = {
    "default":  {"platform": "1", "vName": "1.5.1", "dId": None},   # 明日方舟
    "endfield": {"platform": "3", "vName": "1.0.0", "dId": ""},     # 终末地
}

# 登岛检票 gameId 映射
CHECKIN_MAP = {"arknights": "1", "endfield": "3"}

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sign_log.txt")

_CACHED_DID = None  # 缓存随机 dId
_TIME_OFFSET = 0   # 本地与服务器时间偏差（秒），启动时自动校准


def sync_time_offset():
    """校准本地时间与森空岛服务器的时间偏差"""
    global _TIME_OFFSET
    try:
        from email.utils import parsedate_to_datetime
        resp = requests.get(SK_BASE, timeout=TIMEOUT)
        date_str = resp.headers.get("Date", "")
        if date_str:
            server_dt = parsedate_to_datetime(date_str)
            server_ts = int(server_dt.timestamp())
            local_ts = int(time.time())
            _TIME_OFFSET = server_ts - local_ts
            if abs(_TIME_OFFSET) > 5:
                log(f"  时间校准: 本地与服务器偏差 {_TIME_OFFSET} 秒，已自动修正", False)
    except Exception as e:
        log(f"  时间校准失败: {e}", False)


def now_ts():
    """返回校准后的秒级时间戳"""
    return str(int(time.time()) + _TIME_OFFSET)


# ═══════════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════════

def get_did():
    """生成设备标识 dId（base64 编码的随机 UUID）"""
    global _CACHED_DID
    if _CACHED_DID is None:
        raw = str(uuid.uuid4()).replace("-", "")[:32]
        _CACHED_DID = base64.b64encode(raw.encode()).decode().rstrip("=")
    return _CACHED_DID


def log(msg, to_file=False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    if to_file:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def load_config():
    """加载 config.json 运行配置（非敏感信息）"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_tokens():
    """
    加载 token（鹰角通行证 token，非 cred）
    优先级: 环境变量 SKLAND_TOKENS > creds.txt
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tokens = []

    # 环境变量（多个 token 用逗号分隔）
    env = os.getenv("SKLAND_TOKENS", "").strip()
    if env:
        tokens = [t.strip() for t in env.split(",") if t.strip()]

    # creds.txt（每行一个 token，# 开头为注释）
    if not tokens:
        creds_path = os.path.join(script_dir, "creds.txt")
        if os.path.exists(creds_path):
            with open(creds_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tokens.append(line)

    return [t for t in tokens if len(t) >= 10]


# ═══════════════════════════════════════════════════════════════
#  签名 & 请求
# ═══════════════════════════════════════════════════════════════

def compute_sign(sign_token, path, body_str, profile="default"):
    """
    签名: sign = MD5(HMAC_SHA256(sign_token, path + body + timestamp + headerCA))
    不同游戏通过 profile 切换签名参数
    """
    t = now_ts()
    p = SIGN_PROFILES[profile]
    did = get_did() if p["dId"] is None else p["dId"]

    header_ca = {"platform": p["platform"], "timestamp": t, "dId": did, "vName": p["vName"]}
    ca_str = json.dumps(header_ca, separators=(",", ":"))
    message = path + body_str + t + ca_str

    hmac_hex = hmac.new(
        sign_token.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hashlib.md5(hmac_hex.encode("utf-8")).hexdigest(), header_ca


def signed_request(cred, sign_token, url, method="POST", body=None,
                   profile="default", extra_headers=None):
    """
    统一签名请求: 计算签名 → 构造 header → 发送请求
    body 通过 data= 预序列化发送（确保与签名内容一致）
    """
    path = urlparse(url).path
    body_str = json.dumps(body, separators=(",", ":")) if body else ""
    sign, ca = compute_sign(sign_token, path, body_str, profile)

    headers = {
        "cred": cred,
        "User-Agent": UA,
        "Accept-Encoding": "gzip",
        "Connection": "close",
        "platform": ca["platform"],
        "timestamp": ca["timestamp"],
        "dId": ca["dId"],
        "vName": ca["vName"],
        "sign": sign,
    }
    if method.upper() == "POST":
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    body_bytes = body_str.encode("utf-8") if body_str else b""
    req_fn = requests.post if method.upper() == "POST" else requests.get
    kwargs = {"headers": headers, "timeout": TIMEOUT}
    if method.upper() == "POST":
        kwargs["data"] = body_bytes

    if "--debug" in sys.argv:
        safe_h = {k: (v[:6] + "..." + v[-3:] if k in ("cred", "sign") else v)
                  for k, v in headers.items()}
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] Method: {method}")
        print(f"[DEBUG] Headers: {json.dumps(safe_h, ensure_ascii=False)}")
        print(f"[DEBUG] Body: {body_str or '(empty)'}")
        sign_msg = path + body_str + ca["timestamp"] + json.dumps(ca, separators=(",", ":"))
        print(f"[DEBUG] Sign message: {sign_msg}")

    resp = req_fn(url, **kwargs)
    if "--debug" in sys.argv:
        print(f"[DEBUG] Status: {resp.status_code}")
        print(f"[DEBUG] Response: {resp.text[:600]}")
    return resp.json()


# ═══════════════════════════════════════════════════════════════
#  森空岛 API
# ═══════════════════════════════════════════════════════════════

def get_cred_and_sign_token(token):
    """OAuth2 两步认证: token → grant code → cred + sign_token"""
    auth_h = {"Content-Type": "application/json", "User-Agent": UA}

    # Step 1: 获取授权码
    r = requests.post(
        f"{AS_BASE}/user/oauth2/v2/grant",
        json={"token": token, "appCode": APP_CODE, "type": 0},
        headers=auth_h, timeout=TIMEOUT,
    ).json()
    if r.get("status") != 0:
        log(f"  获取授权码失败: {r.get('msg', '未知')}")
        return None, None
    code = r.get("data", {}).get("code", "")
    if not code:
        return None, None

    # Step 2: 授权码换取 cred
    r = requests.post(
        f"{SK_WEB}/user/auth/generate_cred_by_code",
        json={"kind": 1, "code": code},
        headers=auth_h, timeout=TIMEOUT,
    ).json()
    if r.get("code") != 0:
        log(f"  获取 cred 失败: {r.get('message', '未知')}")
        return None, None

    d = r.get("data", {})
    return d.get("cred", ""), d.get("token", "")


def get_bindings(cred, sign_token):
    """获取绑定的游戏和角色列表"""
    return signed_request(cred, sign_token, f"{SK_API}/game/player/binding", method="GET")


# ═══════════════════════════════════════════════════════════════
#  签到业务
# ═══════════════════════════════════════════════════════════════

def sign_attendance(cred, sign_token, uid, game_id):
    """明日方舟角色签到"""
    return signed_request(
        cred, sign_token, f"{SK_API}/game/attendance",
        body={"uid": str(uid), "gameId": str(game_id)},
    )


def sign_endfield(cred, sign_token, role_id, server_id):
    """终末地角色签到（专用端点 + sk-game-role header）"""
    return signed_request(
        cred, sign_token, f"{SK_API}/game/endfield/attendance",
        profile="endfield",
        extra_headers={"sk-game-role": f"3_{role_id}_{server_id}"},
    )


def sign_checkin(cred, sign_token, game_id):
    """登岛检票（森空岛平台积分签到）"""
    return signed_request(
        cred, sign_token, f"{SK_API}/score/checkin",
        body={"gameId": str(game_id)},
    )


def fmt_awards(awards):
    if not awards:
        return "无"
    return "，".join(
        f"{a.get('resource', {}).get('name', '?')}x{a.get('count', 0)}"
        for a in awards
    )


def handle_result(result, label, to_file=False):
    code = result.get("code", -1)
    msg = result.get("message", "")
    if code == 0:
        awards = fmt_awards(result.get("data", {}).get("awards", []))
        log(f"    {label}：签到成功！奖励: {awards}", to_file)
        return True
    if code == 10001:
        log(f"    {label}：今日已签到", to_file)
        return True
    log(f"    {label}：失败（{msg}，code={code}）", to_file)
    return False


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

def process_game(cred, st, game, to_file):
    """处理单个游戏的所有签到"""
    app_code = game.get("appCode", "")
    app_name = game.get("appName", "")
    log(f"  游戏: {app_name} ({app_code})", to_file)

    # 角色签到
    for binding in game.get("bindingList", []):
        uid = binding.get("uid", "")
        gid = binding.get("channelMasterId", "")
        nick = binding.get("nickName", uid)
        channel = binding.get("channelName", "")
        if not uid or not gid:
            continue

        if app_code == "endfield":
            # 终末地: 从 roles[] 取 roleId/serverId，走专用签到接口
            roles = binding.get("roles") or []
            default = binding.get("defaultRole") or {}
            if not roles and default:
                roles = [default]
            for role in roles:
                role_id = role.get("roleId", "")
                server_id = role.get("serverId", "")
                name = role.get("nickname", "") or nick or uid
                if role_id and server_id:
                    r = sign_endfield(cred, st, role_id, server_id)
                    handle_result(r, f"{name}[{channel}]", to_file)
        else:
            # 明日方舟等: 通用签到接口
            r = sign_attendance(cred, st, uid, gid)
            handle_result(r, f"{nick}[{channel}]", to_file)

    # 登岛检票
    if app_code in CHECKIN_MAP:
        r = sign_checkin(cred, st, CHECKIN_MAP[app_code])
        handle_result(r, f"{app_name}[登岛检票]", to_file)


def main():
    config = load_config()
    to_file = config.get("log_to_file", True) and "--nolog" not in sys.argv
    game_filter = set(config.get("games", []))  # 空=全部

    tokens = load_tokens()
    if not tokens:
        log("未找到 token，请在 creds.txt 填入", to_file)
        sys.exit(1)

    log(f"共 {len(tokens)} 个账号，开始签到...\n", to_file)
    sync_time_offset()

    for idx, token in enumerate(tokens, 1):
        mask = token[:8] + "****" + token[-4:] if len(token) > 12 else "****"
        log(f"--- 账号 {idx} ({mask}) ---", to_file)
        log("  获取 cred...", to_file)

        cred, st = get_cred_and_sign_token(token)
        if not cred or not st:
            log("  跳过（token 可能过期）\n", to_file)
            continue

        log(f"  cred 获取成功: {cred[:8]}****{cred[-4:]}", to_file)

        bd = get_bindings(cred, st)
        if bd.get("code") != 0:
            log(f"  获取绑定列表失败: {bd.get('message', '')}\n", to_file)
            continue

        games = bd.get("data", {}).get("list", [])
        if not games:
            log("  未绑定任何游戏\n", to_file)
            continue

        # 按 config.json 的 games 过滤
        if game_filter:
            games = [g for g in games if g.get("appCode", "") in game_filter]

        for game in games:
            process_game(cred, st, game, to_file)

        print()

    log("完成！", to_file)


if __name__ == "__main__":
    # 静默运行: 用 python.exe 启动时隐藏控制台窗口
    if os.path.basename(sys.executable).lower() == "python.exe":
        try:
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass
    main()

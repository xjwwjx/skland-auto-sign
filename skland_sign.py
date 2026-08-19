#!/usr/bin/env python3
"""
森空岛自动签到脚本
支持明日方舟（角色签到）+ 明日方舟：终末地（角色签到 + 登岛检票）

签名流程: path + body/query + timestamp + headerCA_json → HMAC-SHA256 → MD5
参考: https://github.com/bwmgd/skyland-auto-sign

跨平台支持: Windows / Android (Termux) / Linux / macOS
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
import platform
from urllib.parse import urlparse
from datetime import datetime
import gzip

# 数美(ShuMei)设备指纹的加密（DES/AES/RSA）全部使用内置纯 Python 实现，
# 见下方「纯 Python 密码学实现」区块。不再依赖 cryptography / pycryptodome，
# 可在 Termux 等无法编译 Rust 扩展的环境直接运行。

# 平台检测
IS_WINDOWS = os.name == "nt"
IS_ANDROID = "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ
IS_TERMUX = "TERMUX_VERSION" in os.environ


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
    "endfield": {"platform": "3", "vName": "1.0.0", "dId": None},   # 终末地
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
    """返回设备指纹 dId（数美真实指纹，进程内缓存）"""
    global _CACHED_DID
    if _CACHED_DID is None:
        _CACHED_DID = gen_sm_did()
    return _CACHED_DID


# ═══════════════════════════════════════════════════════════════
#  数美(ShuMei)设备指纹 — 用于 generate_cred_by_code 校验
#  鹰角自 2024-09 起对该接口启用数美 WAF，必须携带真实 dId 设备指纹，
#  否则返回 code=10001「设备信息无效」。下方为纯 Python 逆向实现，
#  每次运行实时向数美接口申请一个真实 dId（无需浏览器）。
#  参考: https://github.com/nuthx/auto-sign (SecuritySm.py)
# ═══════════════════════════════════════════════════════════════

SM_CONFIG = {
    "organization": "UWXspnCCJN4sfYlNfqps",
    "appId": "default",
    "publicKey": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCmxMNr7n8ZeT0tE1R9j/mPixoinPkeM+k4VGIn/s0k7N5rJAfnZ0eMER+QhwFvshzo0LNmeUkpR8uIlU/GEVr8mN28sKmwd2gpygqj0ePnBmOW4v0ZVwbSYK+izkhVFk2V/doLoMbWy6b+UnA8mkjvg0iYWRByfRsK2gdl7llqCwIDAQAB",
    "protocol": "https", "apiHost": "fp-it.portal101.cn",
}
DEVICE_URL = "https://fp-it.portal101.cn/deviceprofile/v4"

_SM_DES_RULE = {
    "appId": {"cipher": "DES", "is_encrypt": 1, "key": "uy7mzc4h", "obfuscated_name": "xx"},
    "box": {"is_encrypt": 0, "obfuscated_name": "jf"},
    "canvas": {"cipher": "DES", "is_encrypt": 1, "key": "snrn887t", "obfuscated_name": "yk"},
    "clientSize": {"cipher": "DES", "is_encrypt": 1, "key": "cpmjjgsu", "obfuscated_name": "zx"},
    "organization": {"cipher": "DES", "is_encrypt": 1, "key": "78moqjfc", "obfuscated_name": "dp"},
    "os": {"cipher": "DES", "is_encrypt": 1, "key": "je6vk6t4", "obfuscated_name": "pj"},
    "platform": {"cipher": "DES", "is_encrypt": 1, "key": "pakxhcd2", "obfuscated_name": "gm"},
    "plugins": {"cipher": "DES", "is_encrypt": 1, "key": "v51m3pzl", "obfuscated_name": "kq"},
    "pmf": {"cipher": "DES", "is_encrypt": 1, "key": "2mdeslu3", "obfuscated_name": "vw"},
    "protocol": {"is_encrypt": 0, "obfuscated_name": "protocol"},
    "referer": {"cipher": "DES", "is_encrypt": 1, "key": "y7bmrjlc", "obfuscated_name": "ab"},
    "res": {"cipher": "DES", "is_encrypt": 1, "key": "whxqm2a7", "obfuscated_name": "hf"},
    "rtype": {"cipher": "DES", "is_encrypt": 1, "key": "x8o2h2bl", "obfuscated_name": "lo"},
    "sdkver": {"cipher": "DES", "is_encrypt": 1, "key": "9q3dcxp2", "obfuscated_name": "sc"},
    "status": {"cipher": "DES", "is_encrypt": 1, "key": "2jbrxxw4", "obfuscated_name": "an"},
    "subVersion": {"cipher": "DES", "is_encrypt": 1, "key": "eo3i2puh", "obfuscated_name": "ns"},
    "svm": {"cipher": "DES", "is_encrypt": 1, "key": "fzj3kaeh", "obfuscated_name": "qr"},
    "time": {"cipher": "DES", "is_encrypt": 1, "key": "q2t3odsk", "obfuscated_name": "nb"},
    "timezone": {"cipher": "DES", "is_encrypt": 1, "key": "1uv05lj5", "obfuscated_name": "as"},
    "tn": {"cipher": "DES", "is_encrypt": 1, "key": "x9nzj1bp", "obfuscated_name": "py"},
    "trees": {"cipher": "DES", "is_encrypt": 1, "key": "acfs0xo4", "obfuscated_name": "pi"},
    "ua": {"cipher": "DES", "is_encrypt": 1, "key": "k92crp1t", "obfuscated_name": "bj"},
    "url": {"cipher": "DES", "is_encrypt": 1, "key": "y95hjkoo", "obfuscated_name": "cf"},
    "version": {"is_encrypt": 0, "obfuscated_name": "version"},
    "vpw": {"cipher": "DES", "is_encrypt": 1, "key": "r9924ab5", "obfuscated_name": "ca"},
}

_SM_BROWSER_ENV = {
    "plugins": "MicrosoftEdgePDFPluginPortableDocumentFormatinternal-pdf-viewer1,MicrosoftEdgePDFViewermhjfbmdgcfjbbpaeojofohoefgiehjai1",
    "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "canvas": "259ffe69", "timezone": -480, "platform": "Win32",
    "url": "https://www.skland.com/", "referer": "",
    "res": "1920_1080_24_1.25", "clientSize": "0_0_1080_1920_1920_1080_1920_1080", "status": "0011",
}


# ═══════════════════════════════════════════════════════════════
#  纯 Python 密码学实现（DES-ECB / AES-128-CBC / RSA-PKCS1v15）
#  无需任何第三方加密库；已与 pycryptodome 逐字节对拍验证。
# ═══════════════════════════════════════════════════════════════

# ---- DES 常量表 ----
_IP     = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7]
_IP_INV = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25]
_E      = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,12,13,14,15,16,17,16,17,18,19,20,21,20,21,22,23,24,25,24,25,26,27,28,29,28,29,30,31,32,1]
_P      = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25]
_PC1    = [57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35,27,19,11,3,60,52,44,36,63,55,47,39,31,23,15,7,62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,28,20,12,4]
_PC2    = [14,17,11,24,1,5,3,28,15,6,21,10,23,19,12,4,26,8,16,7,27,20,13,2,41,52,31,37,47,55,30,40,51,45,33,48,44,49,39,56,34,53,46,42,50,36,29,32]
_SBOX = [
 [[14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7],[0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8],[4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0],[15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13]],
 [[15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10],[3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5],[0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15],[13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9]],
 [[10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8],[13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1],[13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7],[1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12]],
 [[7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15],[13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9],[10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4],[3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14]],
 [[2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9],[14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6],[4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14],[11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3]],
 [[12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11],[10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8],[9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6],[4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13]],
 [[4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1],[13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6],[1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2],[6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12]],
 [[13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7],[1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2],[7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8],[2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11]],
]

def _bytes_to_bits(b):
    bits = []
    for byte in b:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def _bits_to_bytes(bits):
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        out.append(byte)
    return bytes(out)

def _des_subkeys(key):
    kb = _bytes_to_bits(key)
    c = [kb[_PC1[i] - 1] for i in range(28)]
    d = [kb[_PC1[i + 28] - 1] for i in range(28)]
    subs = []
    shifts = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]
    for s in shifts:
        c = c[s:] + c[:s]
        d = d[s:] + d[:s]
        cd = c + d
        subs.append([cd[_PC2[i] - 1] for i in range(48)])
    return subs

def _des_encrypt_block(block, subkeys):
    old = _bytes_to_bits(block)
    bits = [old[_IP[i] - 1] for i in range(64)]
    L = bits[:32]; R = bits[32:]
    for sk in subkeys:
        er = [R[_E[i] - 1] for i in range(48)]
        x = [er[j] ^ sk[j] for j in range(48)]
        b = []
        for j in range(8):
            s = x[j*6:(j+1)*6]
            row = (s[0] << 1) | s[5]
            col = (s[1] << 3) | (s[2] << 2) | (s[3] << 1) | s[4]
            v = _SBOX[j][row][col]
            b.extend([(v >> k) & 1 for k in (3, 2, 1, 0)])
        b = [b[_P[i] - 1] for i in range(32)]
        nR = [b[j] ^ L[j] for j in range(32)]
        L, R = R, nR
    bits = R + L
    bits = [bits[_IP_INV[i] - 1] for i in range(64)]
    return _bits_to_bytes(bits)

def pure_des_ecb(key8, data):
    """单 DES-ECB（数美各字段用 8 字节密钥，等价于原 cryptography TripleDES(8字节)）。"""
    subs = _des_subkeys(key8)
    pad = (8 - len(data) % 8) % 8
    data = data + b"\x00" * pad
    out = bytearray()
    for i in range(0, len(data), 8):
        out += _des_encrypt_block(data[i:i+8], subs)
    return bytes(out)

# ---- AES-128-CBC ----
_AES_S = [
 0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
 0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
 0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
 0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
 0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
 0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
 0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
 0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
 0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
 0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
 0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
 0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
 0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
 0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
 0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
 0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]

def _xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1)

def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p

def _key_expansion(key):
    w = [[key[4*i + j] for j in range(4)] for i in range(4)]
    rcon = 1
    for c in range(4, 44):
        t = w[c-1][:]
        if c % 4 == 0:
            t = t[1:] + t[:1]
            t = [_AES_S[b] for b in t]
            t[0] ^= rcon
            rcon = _xtime(rcon)
        w.append([w[c-4][j] ^ t[j] for j in range(4)])
    return [[[w[4*rnd + c][r] for c in range(4)] for r in range(4)] for rnd in range(11)]

def pure_aes_cbc(key16, iv, data):
    """AES-128-CBC，参数顺序 (密钥16字节, IV16字节, 明文)，返回 hex 字符串。"""
    rk = _key_expansion(key16)
    pad = (16 - len(data) % 16) % 16
    data = data + b"\x00" * pad
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = bytearray(data[i:i+16])
        for j in range(16):
            block[j] ^= prev[j]
        state = [[block[r + 4*c] for c in range(4)] for r in range(4)]
        for r in range(4):
            for c in range(4):
                state[r][c] ^= rk[0][r][c]
        for rnd in range(1, 11):
            for r in range(4):
                for c in range(4):
                    state[r][c] = _AES_S[state[r][c]]
            sr = [[0]*4 for _ in range(4)]
            for r in range(4):
                for c in range(4):
                    sr[r][c] = state[r][(c + r) % 4]
            state = sr
            if rnd < 10:
                for c in range(4):
                    col = [state[r][c] for r in range(4)]
                    state[0][c] = _gmul(col[0], 2) ^ _gmul(col[1], 3) ^ col[2] ^ col[3]
                    state[1][c] = col[0] ^ _gmul(col[1], 2) ^ _gmul(col[2], 3) ^ col[3]
                    state[2][c] = col[0] ^ col[1] ^ _gmul(col[2], 2) ^ _gmul(col[3], 3)
                    state[3][c] = _gmul(col[0], 3) ^ col[1] ^ col[2] ^ _gmul(col[3], 2)
            for r in range(4):
                for c in range(4):
                    state[r][c] ^= rk[rnd][r][c]
        enc = bytes(state[r][c] for c in range(4) for r in range(4))
        out += enc
        prev = enc
    return out.hex()

# ---- RSA PKCS1v15 公钥加密（从 DER 公钥解析 n/e） ----
def _der_nodes(data, start, end):
    pos = start
    while pos < end:
        tag = data[pos]; pos += 1
        ln = data[pos]; pos += 1
        if ln & 0x80:
            nb = ln & 0x7f
            ln = int.from_bytes(data[pos:pos+nb], "big"); pos += nb
        yield tag, pos, pos + ln
        pos += ln

def _parse_n_e(der_b64):
    data = base64.b64decode(der_b64)
    spki = list(_der_nodes(data, 0, len(data)))[0]
    kids = list(_der_nodes(data, spki[1], spki[2]))
    bitstring = kids[1]
    bs_start = bitstring[1] + 1
    rsa = list(_der_nodes(data, bs_start, bitstring[2]))[0]
    rkids = list(_der_nodes(data, rsa[1], rsa[2]))
    n = int.from_bytes(data[rkids[0][1]:rkids[0][2]], "big")
    e = int.from_bytes(data[rkids[1][1]:rkids[1][2]], "big")
    return n, e

def pure_rsa_pkcs1v15(pubkey_b64, msg):
    n, e = _parse_n_e(pubkey_b64)
    k = (n.bit_length() + 7) // 8
    ps_len = k - len(msg) - 3
    ps = b""
    while len(ps) < ps_len:
        b = os.urandom(1)[0]
        if b != 0:
            ps += bytes([b])
    em = b"\x00\x02" + ps + b"\x00" + msg
    c = pow(int.from_bytes(em, "big"), e, n)
    return c.to_bytes(k, "big")


def _sm_des(o):
    result = {}
    for i in o.keys():
        if i in _SM_DES_RULE:
            rule = _SM_DES_RULE[i]
            res = o[i]
            if rule["is_encrypt"] == 1:
                # 与原 cryptography TripleDES/ECB 行为一致: 补 8 字节 \x00 后只加密完整块
                data = str(res).encode() + b"\x00" * 8
                enc = pure_des_ecb(rule["key"].encode(), data)
                enc = enc[: (len(data) // 8) * 8]
                res = base64.b64encode(enc).decode()
            result[rule["obfuscated_name"]] = res
        else:
            result[i] = o[i]
    return result


def _sm_aes(v: bytes, k: bytes):
    iv = b"0102030405060708"
    # 与原 cryptography AES/CBC 行为一致: 至少补 1 字节, 再补到 16 字节整数倍
    v = v + b"\x00"
    while len(v) % 16 != 0:
        v += b"\x00"
    return pure_aes_cbc(k, iv, v)


def _sm_gzip(o):
    return base64.b64encode(gzip.compress(json.dumps(o, ensure_ascii=False).encode(), 2, mtime=0))


def _sm_get_tn(o):
    result_list = []
    for i in sorted(o.keys()):
        v = o[i]
        if isinstance(v, (int, float)):
            v = str(v * 10000)
        elif isinstance(v, dict):
            v = _sm_get_tn(v)
        result_list.append(v)
    return "".join(result_list)


def _sm_get_smid():
    t = time.localtime()
    _t = "{}{:0>2d}{:0>2d}{:0>2d}{:0>2d}{:0>2d}".format(
        t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
    uid = str(uuid.uuid4())
    v = _t + hashlib.md5(uid.encode()).hexdigest() + "00"
    smsk = hashlib.md5(("smsk_web_" + v).encode()).hexdigest()[0:14]
    return v + smsk + "0"


def gen_sm_did():
    """调用数美接口生成真实设备指纹 dId（返回 'B' + deviceId）"""
    uid = str(uuid.uuid4()).encode()
    priId = hashlib.md5(uid).hexdigest()[0:16]
    ep = base64.b64encode(pure_rsa_pkcs1v15(SM_CONFIG["publicKey"], uid)).decode()
    browser = _SM_BROWSER_ENV.copy()
    ct = int(time.time() * 1000)
    browser.update({"vpw": str(uuid.uuid4()), "svm": ct, "trees": str(uuid.uuid4()), "pmf": ct})
    des_target = {
        **browser, "protocol": 102, "organization": SM_CONFIG["organization"],
        "appId": SM_CONFIG["appId"], "os": "web", "version": "3.0.0", "sdkver": "3.0.0",
        "box": "", "rtype": "all", "smid": _sm_get_smid(), "subVersion": "1.0.0", "time": 0,
    }
    des_target["tn"] = hashlib.md5(_sm_get_tn(des_target).encode()).hexdigest()
    des_result = _sm_aes(_sm_gzip(_sm_des(des_target)), priId.encode())
    resp = requests.post(DEVICE_URL, json={
        "appId": "default", "compress": 2, "data": des_result, "encode": 5,
        "ep": ep, "organization": SM_CONFIG["organization"], "os": "web",
    }, timeout=TIMEOUT).json()
    if resp.get("code") != 1100:
        raise RuntimeError(f"数美接口返回异常: {resp.get('message', resp)}")
    return "B" + resp["detail"]["deviceId"]


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
        "X-Requested-With": "com.hypergryph.skland",
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
    """OAuth2 两步认证: token → grant code → cred + sign_token

    2024-09 起 generate_cred_by_code 接口新增数美设备指纹(dId)校验，
    必须在请求头带上 platform / timestamp / dId / vName，否则返回
    code=10001「设备信息无效」。这里复用 get_did() 生成 dId（与签到
    请求同一套格式，已被服务器接受）。
    """
    auth_h = {
        "Content-Type": "application/json",
        "User-Agent": UA,
        "X-Requested-With": "com.hypergryph.skland",
        "platform": "3",
        "timestamp": now_ts(),
        "dId": get_did(),
        "vName": "1.0.0",
    }

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

    # Step 2: 授权码换取 cred（需携带 dId 设备指纹，否则「设备信息无效」）
    r = requests.post(
        f"{SK_WEB}/user/auth/generate_cred_by_code",
        json={"kind": 1, "code": code},
        headers=auth_h, timeout=TIMEOUT,
    ).json()
    if r.get("code") != 0:
        msg = r.get("message", "未知")
        if r.get("code") == 10001:
            log(f"  获取 cred 失败: {msg}（请先 git pull 更新脚本，需携带 dId 设备指纹）")
        else:
            log(f"  获取 cred 失败: {msg}")
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

    # 显示运行平台信息
    if IS_TERMUX:
        log(f"运行环境: Android/Termux {os.environ.get('TERMUX_VERSION', '')}", to_file)
    elif IS_WINDOWS:
        log(f"运行环境: Windows {platform.release()}", to_file)
    else:
        log(f"运行环境: {platform.system()} {platform.release()}", to_file)

    tokens = load_tokens()
    if not tokens:
        log("未找到 token，请在 creds.txt 填入", to_file)
        sys.exit(1)

    log(f"共 {len(tokens)} 个账号，开始签到...\n", to_file)
    sync_time_offset()

    # 预生成数美设备指纹 dId（generate_cred_by_code 校验必需；失败则提前退出）
    try:
        get_did()
    except Exception as e:
        log(f"生成设备指纹(dId)失败: {e}", to_file)
        log("请检查网络能否访问 fp-it.portal101.cn（dId 由脚本内置纯 Python 实现生成，无需 cryptography 库）", to_file)
        sys.exit(1)

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
    # Windows 静默运行: 用 python.exe 启动时隐藏控制台窗口
    if IS_WINDOWS and os.path.basename(sys.executable).lower() == "python.exe":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass
    main()

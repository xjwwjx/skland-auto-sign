# 森空岛自动签到脚本

自动完成森空岛（Skland）平台的多游戏每日签到，支持：

- **明日方舟** — 角色签到 + 登岛检票
- **明日方舟：终末地** — 角色签到 + 登岛检票

> **关于本项目**：代码由 AI（WorkBuddy / CodeBuddy）编写，需求提出和测试由用户完成。
> 签名算法参考 [bwmgd/skyland-auto-sign](https://github.com/bwmgd/skyland-auto-sign)，终末地签到 API 参考 [sjtt2/endfield_auto_sign](https://github.com/sjtt2/endfield_auto_sign)。
> 本 README 同时记录了开发过程中踩过的所有坑，供后续 AI 或人类开发者参考，避免重复踩坑。

---

## 快速开始

### 1. 获取 Token

1. 手机打开森空岛 App → 我的 → 设置
2. 找到「鹰角通行证」相关页面，复制 Token

> **Token vs Cred**：本脚本使用的是**鹰角通行证 Token**（通过 OAuth2 自动换算为 Cred），不是浏览器抓到的 `cred` 字段。Token 更稳定，有效期更长。

### 2. 填入 Token

编辑 `creds.txt`：

```
# 每行一个 token，# 开头为注释
你的token值粘贴在这里
```

多账号就写多行。

### 3. 测试运行

```bat
python skland_sign.py
```

看到"签到成功"即正常。

### 4. 安装定时任务

**右键 → 以管理员身份运行** `install_task.bat`

安装后每天 **15:00** 自动签到。

```bat
REM 手动触发测试
schtasks /Run /TN SklandAutoSign

REM 卸载定时任务
schtasks /Delete /TN SklandAutoSign /F
```

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `skland_sign.py` | 主签到脚本（Python 3） |
| `creds.txt` | 存放鹰角通行证 token（敏感信息，勿泄露） |
| `config.json` | 运行配置（签到游戏过滤、日志开关等） |
| `install_task.bat` | 一键注册 Windows 定时任务（需管理员权限） |
| `sign_log.txt` | 运行日志（自动生成） |
| `NOTES.md` | 详细的开发经验笔记（本文档的扩展版） |

---

## 配置说明

编辑 `config.json`：

```json
{
  "games": [],
  "log_to_file": true
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `games` | 要签到的游戏列表，留空 = 全部 | `[]` |
| `log_to_file` | 是否写入日志文件 | `true` |

`games` 可选值：`"arknights"`（明日方舟）、`"endfield"`（终末地）。

---

## 技术文档（开发踩坑记录）

> 以下内容来自本项目的真实开发过程。如果你（人或 AI）要复刻、修改或扩展本脚本，这些信息可以直接帮你跳过我们踩过的坑。

### 认证流程

森空岛的认证不是直接用 Token 调 API，而是两步换算：

```
鹰角通行证 Token
  → POST as.hypergryph.com/user/oauth2/v2/grant  (body: {token, appCode, type:0})
  → 获得 code
  → POST zonai.skland.com/web/v1/user/auth/generate_cred_by_code  (body: {kind:1, code})
  → 获得 cred + sign_token
```

- `cred`：后续所有 API 请求的身份凭证（放在 Request Header 中）
- `sign_token`：签名密钥（用于计算请求签名）
- **建议存 Token 而非 cred**：Token 有效期更长，过期后重新获取更方便

### 签名算法

```
sign = MD5( HMAC-SHA256( sign_token, path + body + timestamp + headerCA_json ) )
```

| 字段 | 说明 |
|------|------|
| `path` | 请求 URL 的路径部分（不含域名和 query string） |
| `body` | 请求体的 JSON 字符串（`separators=(",",":")` 无空格），GET 请求为空字符串 `""` |
| `timestamp` | 当前 Unix 时间戳（建议减 2 秒防时钟偏移） |
| `headerCA` | `{"platform":"1","timestamp":"...","dId":"...","vName":"1.5.1"}` 格式的 JSON |

**最重要的坑**：发送请求时必须用 `requests.post(data=body_bytes)` 而不是 `requests.post(json=body)`。因为 `json=` 会让 requests 重新序列化 body，可能与签名时用的字符串不一致，导致签名验证失败。

```python
# 正确：签名和发送用同一份序列化结果
body_str = json.dumps(body, separators=(",", ":"))
sign = compute_sign(sign_token, path, body_str)
requests.post(url, data=body_str.encode("utf-8"), headers=headers)

# 错误：requests 会重新序列化，签名对不上
requests.post(url, json=body, headers=headers)
```

### 明日方舟 vs 终末地：完全不同的 API

这是本项目最大的坑。初版脚本只支持明日方舟的签到接口，终末地一直返回 `code=10001`，一度被误判为"今日已签到"——实际上是**接口用错了**。

| 参数 | 明日方舟 | 终末地 |
|------|---------|--------|
| 角色签到端点 | `/api/v1/game/attendance` | `/api/v1/game/endfield/attendance` |
| 请求体 | `{"uid":"...", "gameId":"..."}` | 空（无 body） |
| 额外 Header | 无 | `sk-game-role: 3_{roleId}_{serverId}` |
| 签名 platform | `"1"` | `"3"` |
| 签名 dId | 随机 UUID (base64) | `""`（空字符串） |
| 签名 vName | `"1.5.1"` | `"1.0.0"` |

**三个容易搞错的地方：**

1. **终末地的 roleId / serverId 来源**：不是绑定列表里的 `uid` / `channelMasterId`，而是 `bindingList[].roles[]` 数组中的 `roleId` 和 `serverId` 字段。嵌套层级深，容易取错。

2. **`sk-game-role` header 是必须的**：终末地签到必须携带此 header，格式为 `3_{roleId}_{serverId}`（gameId 固定为 3）。不携带则返回 code=10001。

3. **终末地签到的 body 必须为空**：签名计算中 body 部分为空字符串 `""`，不能传任何请求体。

> **教训**：森空岛是鹰角的统一平台，但不同游戏的签到接口、签名参数、请求格式完全不同。遇到未知的错误码，应该先调研该游戏是否有专用 API，不要假设平台内所有产品共用一套接口。

### 登岛检票

"登岛检票"是森空岛平台自身的积分签到，与具体游戏的角色签到是**独立的**两套机制。每个游戏各有一次登岛检票机会。

- 端点：`POST /api/v1/score/checkin`，body：`{"gameId": "..."}`
- 明日方舟 gameId = `"1"`，终末地 gameId = `"3"`

### API 响应码

| code | 含义 |
|------|------|
| `0` | 成功 |
| `10001` | 今日已签到（这是正常响应，不是错误） |
| 其他 | 需检查 `message` 字段 |

### Windows 定时任务注意事项

1. **路径问题**：定时任务的执行目录默认是 `C:\Windows\System32`，不是脚本所在目录。所有文件路径必须基于 `__file__` 构建绝对路径，不能用相对路径。

2. **静默运行**：`python.exe` 运行会弹控制台窗口，用 `pythonw.exe` 不会。脚本中额外用 `ctypes.windll.user32.ShowWindow` 隐藏窗口作为双保险——但注意不要忘记 `import ctypes`，否则报错会被 try/except 静默吞掉，排查困难。

3. **开发建议**：生产环境可以吞异常，但开发阶段尽量不要用宽泛的 try/except，否则出问题完全无迹可循。

### 扩展新游戏

如果鹰角未来推出新游戏需要签到，步骤：

1. 抓包分析新游戏的签到 API 端点和参数
2. 在 `SIGN_PROFILES` 字典中添加新游戏的签名参数
3. 如果 API 格式不同，新增对应的签到函数
4. 在 `process_game()` 中添加分支逻辑
5. 在 `CHECKIN_MAP` 中添加登岛检票的 gameId 映射

---

## 常见问题

**Q: Token 过期了怎么办？**
A: 重新获取并更新 `creds.txt` 即可。

**Q: 终末地签到返回 code=10001？**
A: code=10001 表示"今日已签到"，属于正常响应。如果确认今天还没签到过，检查 `sk-game-role` header 是否正确。

**Q: 签到失败怎么办？**
A: 手动运行脚本查看具体错误信息，检查网络和 Token 有效性。

**Q: 如果我想自己做一个类似的脚本，从哪里开始？**
A: 阅读 [NOTES.md](./NOTES.md) 获取完整的开发经验，或直接让 AI 助手阅读本仓库的代码和技术文档后帮你实现。

## 许可证

MIT License

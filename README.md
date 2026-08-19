# 森空岛自动签到脚本

自动完成森空岛（Skland）平台的多游戏每日签到，支持：

- **明日方舟** — 角色签到 + 登岛检票
- **明日方舟：终末地** — 角色签到 + 登岛检票

**跨平台支持**：Windows / Android (Termux) / Linux / macOS

> **关于本项目**：代码由 AI（WorkBuddy / CodeBuddy）编写，需求提出和测试由用户完成。
> 签名算法参考 [bwmgd/skyland-auto-sign](https://github.com/bwmgd/skyland-auto-sign)，终末地签到 API 参考 [sjtt2/endfield_auto_sign](https://github.com/sjtt2/endfield_auto_sign)。
> 本 README 同时记录了开发过程中踩过的所有坑，供后续 AI 或人类开发者参考，避免重复踩坑。

---

## 快速开始

### 1. 获取 Token

有两种方式获取鹰角通行证 Token：

#### 方式一：网页端获取（推荐）

1. 在浏览器中打开 [https://www.skland.com](https://www.skland.com)，用鹰角通行证账号登录
2. **登录后**，在同一个浏览器中访问以下链接：

   👉 [https://web-api.skland.com/account/info/hg](https://web-api.skland.com/account/info/hg)

3. 页面会返回一段 JSON，格式如下：

   ```json
   {
     "code": 0,
     "data": {
       "content": "这里就是你的Token"
     },
     "msg": "接口会返回您的鹰角网络通行证账号的登录凭证..."
   }
   ```

4. 复制 `data.content` 字段的值，即为你的 Token

> ⚠️ 必须先登录森空岛官网，再访问上述链接。未登录状态下会返回错误。

#### 方式二：手机 App 获取

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

### 3. Token 过期/更新（一键替换）

Token 有效期约 30 天，过期后脚本会提示"token 可能过期"并跳过。**注意：过期的是 Token，不是 cred** —— cred 由脚本用 Token 自动兑换，无需手动获取。

#### 方式一：使用 `set_token.sh` 助手脚本（推荐）

```bash
# 先更新仓库获取脚本（首次）
cd ~/skland-auto-sign && git pull

# 在浏览器复制好新 Token 后，运行：
bash set_token.sh
```

脚本会自动从**剪贴板**读取 Token（需 Termux:API），保留注释行，只替换 Token。也可直接传参：

```bash
bash set_token.sh 你的新Token值
```

#### 方式二：一行命令直接替换

从剪贴板读取（需 Termux:API）：

```bash
F=~/skland-auto-sign/creds.txt; TOK=$(termux-clipboard-get | tr -d '[:space:]'); [ -z "$TOK" ] && echo "剪贴板为空" || { grep '^#' "$F" > /tmp/c.txt 2>/dev/null; echo "$TOK" >> /tmp/c.txt; mv /tmp/c.txt "$F"; echo "✅ 已更新: ${TOK:0:8}****"; }
```

未装 Termux:API 时，手动替换占位符 `把新Token粘到这里`：

```bash
F=~/skland-auto-sign/creds.txt; TOK="把新Token粘到这里"; grep '^#' "$F" > /tmp/c.txt 2>/dev/null; echo "$TOK" >> /tmp/c.txt; mv /tmp/c.txt "$F"; echo "✅ 已更新"
```

### 4. 测试运行

```bash
python skland_sign.py
```

看到"签到成功"即正常。

### 4. 设置自动签到

根据你的平台选择：

#### Windows

**右键 → 以管理员身份运行** `install_task.bat`

安装后每天 **15:00** 自动签到。

```bat
REM 手动触发测试
schtasks /Run /TN SklandAutoSign

REM 卸载定时任务
schtasks /Delete /TN SklandAutoSign /F
```

#### Android (Termux)

> **安卓手机用户请按以下步骤操作**，从安装 Termux 到自动签到，完整流程如下。

##### 第 1 步：安装 Termux 及配套 APP

从 [F-Droid](https://f-droid.org/packages/com.termux/) 安装以下三个 APP（**不要用 Google Play 版，已过时**）：

| APP | 用途 | 下载地址 |
|-----|------|---------|
| **Termux** | 提供 Linux 终端环境，运行 Python 脚本 | [F-Droid](https://f-droid.org/packages/com.termux/) |
| **Termux:API** | 提供 termux-wake-lock 等系统接口 | [F-Droid](https://f-droid.org/packages/com.termux.api/) |
| **Termux:Boot** | 开机自启 cron 服务 | [F-Droid](https://f-droid.org/packages/com.termux.boot/) |

安装后，**打开 Termux:API 和 Termux:Boot 各一次**（打开即可关闭），让系统授予必要权限。

##### 第 2 步：在 Termux 中安装脚本

打开 Termux APP，依次输入以下命令：

```bash
# 1. 安装 git
pkg install git -y

# 2. 克隆仓库到手机
git clone https://github.com/xjwwjx/skland-auto-sign.git ~/skland-auto-sign

# 3. 进入项目目录
cd ~/skland-auto-sign

# 4. 运行一键安装脚本（自动安装 Python、依赖、cron 定时任务）
bash setup_android.sh
```

安装脚本会自动完成：
- ✅ 安装 Python、requests、cronie、termux-api
- ✅ 配置每天 **15:00** 的 cron 定时任务
- ✅ 设置 `termux-wake-lock` 防止手机休眠杀进程
- ✅ 配置 Termux:Boot 开机自启 cron 服务
- ✅ 创建 `creds.txt` 配置文件（如不存在）

看到 `安装完成！` 提示即表示环境配置成功。

##### 第 3 步：填入 Token

安装脚本会自动创建 `creds.txt` 文件，你需要编辑它填入自己的鹰角通行证 Token：

```bash
# 用 nano 编辑器打开配置文件
nano ~/skland-auto-sign/creds.txt
```

在文件中填入你的 Token（每行一个，`#` 开头为注释）：

```
# 森空岛自动签到 — Token 配置
你的token值粘贴在这里
```

编辑完成后按 `Ctrl+O` 保存，`Ctrl+X` 退出 nano。

> **Token 获取方式**：打开森空岛 App → 我的 → 设置 → 复制鹰角通行证 Token

##### 第 4 步：手动测试签到

确认 Token 填好后，先手动跑一次验证是否正常：

```bash
cd ~/skland-auto-sign && python skland_sign.py
```

看到 `签到成功` 即表示配置正确，可以进入下一步。如果报错，检查 Token 是否正确、网络是否通畅。

##### 第 5 步：设置系统后台保活

这一步非常关键，否则 Termux 会被安卓系统杀掉，定时任务无法执行：

1. **关闭电池优化**：系统设置 → 应用管理 → Termux → 电池/耗电管理 → 选择「不限制」或「无限制」
2. **锁定后台**：在最近任务列表中下拉锁定 Termux（或长按加锁图标）
3. **确认唤醒锁生效**：Termux 通知栏应显示 `ACQUIRE WAKELOCK`
4. **确认 cron 运行**：执行 `pgrep crond` 应输出进程号

##### 第 6 步：验证自动签到

等待到定时任务触发时间（默认 15:00），或手动验证 cron 是否正常：

```bash
# 查看 cron 定时任务是否已配置
crontab -l

# 查看 cron 服务是否在运行
pgrep crond

# 签到执行后查看日志
cat ~/skland-auto-sign/sign_log.txt
```

日志中出现签到记录即表示自动签到已正常运行。

##### Android 常用管理命令

```bash
# 手动触发签到
cd ~/skland-auto-sign && python skland_sign.py

# 查看签到日志
cat ~/skland-auto-sign/sign_log.txt

# 查看定时任务
crontab -l

# 修改签到时间（例如改为每天 8:00）
crontab -e
# 将 "0 15 * * *" 改为 "0 8 * * *"

# 重启 cron 服务
pkill crond && crond

# 重新设置唤醒锁
termux-wake-lock

# 删除定时任务（卸载用）
crontab -l | grep -v skland-auto-sign | crontab -
```

##### Android 常见问题

| 问题 | 解决方案 |
|------|---------|
| **Termux 总是被杀** | 关闭电池优化 → 锁定后台 → 确认 wake-lock 生效 → 安装 Termux:Boot 开机自启 |
| **cron 到时间没执行** | 检查 `pgrep crond` 是否有输出；检查 `crontab -l` 是否有任务；检查 `run_sign.sh` 是否存在 |
| **签到报网络错误** | 检查手机网络；Termux 内执行 `curl -sI https://zonai.skland.com` 测试连通性 |
| **时间偏差导致签名失败** | 脚本已内置时间校准，确保手机系统时间准确即可 |
| **Google Play 版 Termux 报错** | 卸载后从 F-Droid 重新安装，Google Play 版已停止更新 |

#### Linux / macOS

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 crontab 定时任务
crontab -e
# 添加以下行（每天 15:00 执行，替换实际路径）：
# 0 15 * * * cd /path/to/skland-auto-sign && python skland_sign.py >> sign_log.txt 2>&1
```

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `skland_sign.py` | 主签到脚本（Python 3，跨平台） |
| `creds.txt` | 存放鹰角通行证 token（敏感信息，勿泄露） |
| `config.json` | 运行配置（签到游戏过滤、日志开关等） |
| `requirements.txt` | Python 依赖列表 |
| `install_task.bat` | Windows 一键注册定时任务（需管理员权限） |
| `setup_android.sh` | Android (Termux) 一键安装脚本 |
| `run_sign.sh` | Android cron 执行入口（安装脚本自动生成） |
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
| `timestamp` | 当前 Unix 时间戳（自动校准服务器时间偏差） |
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

### 时间校准

森空岛服务器收紧了时间偏差校验，本地时钟偏差 >30s 时所有签名请求被拒绝（code=10003）。脚本启动时自动从响应头 `Date` 字段获取服务器时间并校准，偏差 >5s 时自动修正。这对 Android 设备尤为重要，因为手机时间可能不准确。

### Windows 定时任务注意事项

1. **路径问题**：定时任务的执行目录默认是 `C:\Windows\System32`，不是脚本所在目录。所有文件路径必须基于 `__file__` 构建绝对路径，不能用相对路径。

2. **静默运行**：`python.exe` 运行会弹控制台窗口，用 `pythonw.exe` 不会。脚本中额外用 `ctypes.windll.user32.ShowWindow` 隐藏窗口作为双保险（仅在 Windows 平台加载 ctypes）。

3. **跨平台适配**：`ctypes` 仅在 Windows 上导入，Android/Termux 和其他平台不会加载此模块，确保跨平台兼容。

### Android (Termux) 定时任务注意事项

1. **cron 服务**：Termux 使用 `cronie` 提供 cron 功能，需手动启动 `crond`。安装脚本已配置开机自启。

2. **唤醒锁**：Android 系统会在休眠时杀后台进程，需通过 `termux-wake-lock` 保持 Termux 运行。

3. **电池优化**：必须在系统设置中关闭 Termux 的电池优化，否则即使有唤醒锁也可能被杀。

4. **Termux:Boot**：安装 Termux:Boot APP 并打开一次，`~/.termux/boot/` 目录下的脚本会在开机时自动执行。

5. **F-Droid 版**：务必使用 F-Droid 版 Termux，Google Play 版已停止更新且权限受限。

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
A: 重新获取 Token 并更新 `creds.txt` 即可。注意过期的是 **Token** 不是 cred（cred 由脚本自动兑换）。一键更新：在浏览器复制新 Token 后运行 `bash set_token.sh`（自动读剪贴板），或参考上文「Token 过期/更新」章节的一行命令。

**Q: 提示「设备信息无效 / 获取 cred 失败」怎么办？**
A: 这是鹰角自 2024-09 起对「换 cred」接口（`generate_cred_by_code`）启用的数美(ShuMei)设备指纹校验。新版脚本已内置真实 dId 生成逻辑（每次运行实时向数美接口申请，无需浏览器），依赖 `cryptography` 库（安装脚本已自动安装）。若仍报此错，请确认：① 已 `git pull` 更新到含 dId 修复的版本（commit ≥ `8bd49df`）；② 手机能联网访问 `fp-it.portal101.cn`（生成 dId 需调用该接口，被墙或断网会失败）；③ 已安装依赖 `pip install -r requirements.txt`。手机端可重新运行 `bash setup_android.sh` 安装依赖。

**Q: 终末地签到返回 code=10001？**
A: code=10001 表示"今日已签到"，属于正常响应。如果确认今天还没签到过，检查 `sk-game-role` header 是否正确。

**Q: 签到失败怎么办？**
A: 手动运行脚本查看具体错误信息，检查网络和 Token 有效性。加 `--debug` 参数查看详细请求信息。

**Q: Android 上 Termux 总是被杀怎么办？**
A: 1) 关闭电池优化；2) 锁定 Termux 后台；3) 确认 termux-wake-lock 已生效；4) 安装 Termux:Boot 实现开机自启。

**Q: 如果我想自己做一个类似的脚本，从哪里开始？**
A: 阅读 [NOTES.md](./NOTES.md) 获取完整的开发经验，或直接让 AI 助手阅读本仓库的代码和技术文档后帮你实现。

## 许可证

MIT License

# 森空岛自动签到脚本

自动完成森空岛（Skland）平台的多游戏每日签到，支持：

- **明日方舟** — 角色签到 + 登岛检票
- **明日方舟：终末地** — 角色签到 + 登岛检票

## 这份代码是怎么来的

**整个项目从零开始，没有一行代码是手动写的。**

项目发起者不懂 Python，不会抓包，不了解 API 签名算法——他只是用自然语言告诉 AI（WorkBuddy / CodeBuddy）自己想要什么：

> "帮我做一个森空岛自动签到的脚本"

然后 AI 完成了全部工作：调研森空岛 API、逆向签名算法、编写代码、调试报错、解决终末地签到兼容性问题、重构代码结构、分离敏感信息……全程通过对话驱动，用户只需要**提需求、给反馈、测结果**。

**如果你也想复刻这个项目，你可以完全照做：**

1. 找一个支持代码执行的 AI 助手（如 [WorkBuddy](https://www.codebuddy.cn)、Cursor、GitHub Copilot 等）
2. 把你的需求用大白话告诉它，比如：
   - "帮我做一个自动签到的脚本"
   - "运行一下看看效果"
   - "报错了，帮我修一下"
   - "把这个功能加一下"
3. AI 会自动完成调研、编写、调试、部署——你不需要懂任何编程知识

这就是 2026 年的"编程"方式：**会说话就能做项目。**

当然，本仓库的代码是现成可用的，你也可以直接用。下面的教程会手把手带你跑起来。

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `skland_sign.py` | 主签到脚本（Python 3） |
| `creds.txt` | 存放鹰角通行证 token（敏感信息，勿泄露） |
| `config.json` | 运行配置（签到游戏过滤、日志开关等） |
| `install_task.bat` | 一键注册 Windows 定时任务（需管理员权限） |
| `sign_log.txt` | 运行日志（自动生成） |

## 快速开始

### 1. 获取 Token

1. 手机打开森空岛 App → 我的 → 设置
2. 找到「鹰角通行证」相关页面，复制 Token
3. 或通过抓包获取（见下方详细说明）

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

示例 — 只签到终末地：

```json
{
  "games": ["endfield"],
  "log_to_file": true
}
```

## 常见问题

**Q: Token 过期了怎么办？**
A: 重新获取并更新 `creds.txt` 即可。

**Q: 终末地签到返回 code=10001？**
A: code=10001 表示"今日已签到"，属于正常响应。

**Q: 签到失败怎么办？**
A: 手动运行脚本查看具体错误信息，检查网络和 Token 有效性。

## 致谢

- 签名算法参考 [bwmgd/skyland-auto-sign](https://github.com/bwmgd/skyland-auto-sign)
- 终末地签到 API 参考 [sjtt2/endfield_auto_sign](https://github.com/sjtt2/endfield_auto_sign)

## 许可证

MIT License

---

> **关于作者**：代码由 AI（WorkBuddy / CodeBuddy）编写，需求提出和测试由用户完成。

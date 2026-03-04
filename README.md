# 🗓️ 纪念日提醒系统

免费、无服务器的纪念日提醒工具。  
前端托管在 **GitHub Pages**，数据存储在仓库内，每天通过 **GitHub Actions + Apprise** 自动推送提醒。

---

## 目录结构

```
event/
├── index.html              # 入口（加密内容内嵌，单文件）
├── app.html                # 源文件（不提交）
├── encrypt.js              # 加密脚本（不提交，请本地保留以便重新生成）
├── events.json             # 纪念日数据
├── reminder.py             # 提醒检查 + Apprise 推送
├── .github/workflows/
│   └── daily.yml           # 每日定时任务（UTC 00:00）
└── README.md
```

### 🔐 页面加密（可选）

`index.html` 由加密脚本生成，应用内容以 AES-256-GCM 加密后内嵌，只有持有秘钥的人才能解密查看。

**加密流程：**
```bash
# 1. 修改 app.html 后，用你的秘钥生成 index.html
node encrypt.js "你的秘钥"

# 2. 提交生成的 index.html
git add index.html
git commit -m "update"
git push
```

**改进点：**
- **单文件**：加密内容内嵌，无需 app.enc，部署更简单
- **混淆**：解密逻辑已混淆，降低被分析难度
- **无外部依赖**：不请求其他文件，全部在 index.html 内

---

## 快速部署

### 1. Fork / 创建仓库

将本项目推送到你自己的 GitHub 仓库（建议仓库名 `event-reminder`）。

### 2. 启用 GitHub Pages

进入仓库 → **Settings → Pages**：
- Source：`Deploy from a branch`
- Branch：`main`，目录：`/ (root)`
- 保存后，几分钟内可通过 `https://<你的用户名>.github.io/event-reminder/` 访问。

### 3. 创建 Personal Access Token（PAT）

进入 GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**：
- 勾选 `repo` 权限
- 生成并复制 Token（`ghp_...`）

### 4. 配置推送渠道（Apprise URLs）

进入仓库 → **Settings → Secrets and variables → Actions → New repository secret**：

| Secret 名称 | 说明 |
|------------|------|
| `APPRISE_URLS` | Apprise 推送 URL，多个用换行分隔 |

常用 Apprise URL 格式：

| 渠道 | URL 格式 |
|------|---------|
| Telegram | `tgram://botToken/chatID` |
| QQ 邮箱 | `mailto://QQ号:授权码@qq.com` |
| 邮件（通用） | `mailtos://user:pass@smtp.example.com` |
| ntfy.sh | `ntfy://ntfy.sh/你的topic名` |
| Server 酱 | `sfk://SendKey` |
| PushPlus | `pplus://Token` |

> 更多渠道：https://github.com/caronc/apprise/wiki

### 5. 打开页面，开始使用

1. 打开 Pages 地址
2. 点击右上角 **⚙️ 配置**，填入：
   - GitHub 用户名
   - 仓库名
   - Personal Access Token
3. 点击 **＋ 添加** 录入纪念日
4. 点击 **☁️ 同步** 将数据保存到 GitHub

---

## events.json 数据格式

```json
{
  "remind_days": [7, 3, 1, 0],
  "items": [
    {
      "id": "唯一ID（UUID）",
      "name": "结婚纪念日",
      "date": "2020-06-01",
      "repeat": "yearly",
      "note": "备注（可选）"
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `remind_days` | 提前几天提醒，`0` 表示当天 |
| `repeat` | `yearly`（每年）/ `monthly`（每月）/ `once`（仅一次） |

---

## GitHub Actions

### 工作流说明

| 文件 | 说明 |
|------|------|
| `.github/workflows/daily.yml` | 每日纪念日检查与推送 |

### 触发方式

- **定时触发**：每天 **UTC 00:00**（北京时间 08:00）自动运行
- **手动触发**：仓库 → **Actions** → 选择「每日纪念日提醒」→ **Run workflow**

### 运行步骤

1. 检出仓库（含 `events.json`）
2. 设置 Python 3.11
3. 安装 Apprise
4. 执行 `reminder.py` 检查并推送提醒

### 必需配置

在 **Settings → Secrets and variables → Actions** 中配置：

| Secret | 必填 | 说明 |
|--------|------|------|
| `APPRISE_URLS` | ✅ | Apprise 推送 URL，多个用换行分隔 |

### 查看运行结果

进入 **Actions** 页面可查看每次运行的日志和状态。若推送失败，可检查 `APPRISE_URLS` 是否正确配置。

---

## 本地测试

```bash
pip install apprise
export APPRISE_URLS="ntfy://ntfy.sh/my-test-topic"
python reminder.py
```

**使用 QQ 邮箱推送：** 运行 `.\reminder_local.ps1` 检查纪念日并推送；运行 `.\test_notify_local.ps1` 发送测试邮件。（脚本含邮箱配置，已加入 .gitignore）

---

## 特点

- 🆓 **完全免费**：GitHub Pages、Actions、Telegram/邮件/ntfy 均免费
- 🚫 **无服务器**：不需要 VPS 或云函数
- 🔒 **数据私有**：数据存储在你自己的仓库，Token 仅存 localStorage
- 📬 **多渠道推送**：基于 Apprise，支持数十种通知渠道

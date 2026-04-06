# NexusPal

个人投研助手，通过 Discord Bot 接入，发送股票代码即可生成分析报告。

## 文件结构

```
nexuspal/
├── main.py              # 入口：python main.py
├── agent.py             # 投研 Agent（Gemini 2.5 Flash → Claude 3.5 Haiku 自动降级）
├── tools.py             # yfinance 行情 + DuckDuckGo 新闻
├── tracker.py           # Token 成本统计
├── reporter.py          # HTML 报告生成
├── channels/
│   ├── __init__.py
│   ├── discord.py       # Discord Bot
│   └── telegram.py      # Telegram Bot（备用，未启用）
├── .env.example         # 配置模板
├── requirements.txt
└── deploy.sh
```

## Discord Bot 配置

### 1. 创建 Bot

1. 打开 [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**
2. 左侧 **Bot** → **Add Bot**
3. 复制 **Token**，填入 `.env` 的 `DISCORD_BOT_TOKEN`

### 2. 开启 Message Content Intent

在 Bot 页面，**Privileged Gateway Intents** 一栏：

- ✅ **Message Content Intent**（必须开启，否则收不到消息内容）

### 3. 邀请 Bot 到服务器

左侧 **OAuth2 → URL Generator**：

- Scopes：勾选 `bot`
- Bot Permissions：勾选 `Send Messages` + `Read Message History`

复制生成的 URL，浏览器打开，选择你的服务器完成邀请。

### 4. 填写配置

```bash
cp .env.example .env
nano .env
```

```env
DISCORD_BOT_TOKEN=你的_bot_token

# 可选：只响应指定频道（留空则响应所有频道）
# DISCORD_CHANNEL_IDS=123456789,987654321
```

频道 ID 获取方式：Discord 设置 → 高级 → 开启**开发者模式**，右键频道 → **复制频道 ID**。

---

## 快速开始

```bash
# 1. 安装依赖
bash deploy.sh

# 2. 填写配置（见上方 Discord 配置）
cp .env.example .env && nano .env

# 3. 启动
python main.py
```

---

## 交互指令

在任意 Bot 可见的频道发送：

| 指令 | 说明 |
|------|------|
| `分析 NVDA` | 生成 NVDA 投研报告，返回 HTML 报告链接 |
| `!status` | 查看 Token 用量和累计成本 |

---

## 服务管理（systemd）

```bash
sudo systemctl start   nexuspal   # 启动
sudo systemctl stop    nexuspal   # 停止
sudo systemctl restart nexuspal   # 重启
sudo systemctl status  nexuspal   # 状态
sudo journalctl -u nexuspal -f    # 实时日志
```

---

*报告仅供参考，不构成投资建议。*

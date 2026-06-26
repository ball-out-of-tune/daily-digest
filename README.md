# 📋 Daily Digest — AI 策展的每日科技摘要

[English](#english) | [中文](#chinese)

---

<a id="english"></a>
## English

**Daily Digest** delivers a curated email every morning (8:00) and afternoon (17:00) covering what matters in AI today:

- **📄 arXiv Papers** — ~350 papers/day from 7 CS categories, AI picks the 25 best
- **🔥 GitHub Trending** — Hottest repos across all languages
- **💬 Reddit** — Top discussions from 10 tech subreddits
- **📰 Hacker News** — Front-page stories
- **📊 Trends & Opportunities** — AI synthesizes patterns and suggests what to build next

Each paper comes with team, problem, method, results, and a research lineage showing which prior work it builds on.

> "Not just what happened — but why it matters, and what to do about it."

### ⚡ Quick Start (5 minutes)

#### Step 1: Get your API keys

| Service | What | Where |
|---|---|---|
| **DeepSeek API** | AI curation | https://platform.deepseek.com → API Keys → Create → Copy `sk-...` |
| **Gmail SMTP** | Send emails | https://myaccount.google.com/apppasswords → Select "Mail" / "Other" → Copy 16-char password |

#### Step 2: Fork & configure

1. **Fork** this repo (top-right button on GitHub)
2. Go to your fork → **Settings** → **Secrets and variables** → **Actions**
   > URL: `https://github.com/YOUR_USERNAME/daily-digest/settings/secrets/actions`
3. Add these 6 secrets:

| Name | Value |
|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `EMAIL_USER` | yourname@gmail.com |
| `EMAIL_PASSWORD` | your Gmail app password (from Step 1) |
| `EMAIL_TO` | recipient@email.com |
| `DEEPSEEK_KEY` | your DeepSeek API key (from Step 1) |

#### Step 3: Done!

Emails arrive **every day at 8:00 and 17:00 (Beijing time / UTC+8)**.

To test: go to your fork → **Actions** → **Daily Digest Email** → **Run workflow**.

> 💡 **Too lazy to add secrets manually?** Use the auto-setup script below with a GitHub token.

#### 🤖 Automated Setup (with GitHub Token)

Instead of clicking through 6 secrets, run this once:

1. Get a GitHub token: https://github.com/settings/tokens → Generate new token (classic) → check `repo` → copy `ghp_...`
2. Send the token + your DeepSeek key + Gmail password to an AI agent (like Claude Code), and let it run:

```python
# The agent will call GitHub API to encrypt & upload all 6 secrets automatically
# Same as clicking through the UI but in seconds
```

#### 🖥️ Run Locally (for testing)

```bash
pip install -r requirements.txt
cp .env.example .env   # Edit with your keys
python src/main.py
```

### 🧠 How It Works

```
arXiv API (356 papers)  ─┐
GitHub Trending (15 repos) ─┤
Reddit (30 posts)          ─┼── DeepSeek AI ──→ Curated Email
Hacker News (15 stories)   ─┤       │
                             │       ├── Top 3 Must-Read
                             │       ├── 25 Papers (team • problem • method • results • lineage)
                             │       └── Trends & Opportunities
                             │
                    Paper references ──→ 2nd DeepSeek call ──→ Research lineage
```

### 🔧 Tech Stack

- **Python** — data fetching + email rendering
- **DeepSeek API** — paper curation, team identification, trend analysis
- **GitHub Actions** — scheduled delivery (free tier)
- **Gmail SMTP** — email sending (free)

### 📬 Email Preview

![Daily Digest Email Screenshot](assets/email-preview-top.png)

<details>
<summary>📜 查看完整邮件截图 (点击展开)</summary>

![Full Email Scroll](assets/email-preview.jpg)

</details>

---

<a id="chinese"></a>
## 中文

**每日科技摘要** 每天早上 8:00 和下午 17:00 发送一封 AI 策展的邮件，包含：

- **📄 arXiv 论文** — 每天 7 个 CS 分类约 350 篇，AI 精选 25 篇
- **🔥 GitHub Trending** — 全语言最热仓库
- **💬 Reddit 热门** — 10 个科技板块的讨论
- **📰 Hacker News 头条** — 技术社区头条
- **📊 趋势与机会** — AI 从今天内容中总结趋势，告诉你接下来可以做什么

每篇论文附带：**所属团队、解决的问题、核心方法、实验效果、发展历程**（引用哪些前人工作、解决了什么遗留问题）。

> 不只是推送——还告诉你为什么重要，以及接下来可以做什么。

### ⚡ 三步上手（5 分钟）

#### 第一步：准备两个 Key

| 服务 | 作用 | 获取地址 |
|---|---|---|
| **DeepSeek API** | AI 策展 | https://platform.deepseek.com → API Keys → 创建 → 复制 `sk-...` |
| **Gmail SMTP** | 发邮件 | https://myaccount.google.com/apppasswords → 选"邮件"/"其他" → 复制 16 位密码 |

#### 第二步：Fork 并配置

1. **Fork** 本仓库（GitHub 右上角按钮）
2. 进入你 Fork 的仓库 → **Settings** → **Secrets and variables** → **Actions**
   > 直达链接：`https://github.com/你的用户名/daily-digest/settings/secrets/actions`
3. 新建 6 个 Secrets：

| Name | Value |
|---|---|
| `SMTP_SERVER` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `EMAIL_USER` | yourname@gmail.com |
| `EMAIL_PASSWORD` | 第一步生成的 Gmail 应用专用密码 |
| `EMAIL_TO` | 接收邮件的邮箱 |
| `DEEPSEEK_KEY` | 第一步复制的 DeepSeek API Key |

#### 第三步：完成！

每天北京时间 **早上 8:00** 和**下午 17:00** 自动发送。

手动测试：进入你的仓库 → **Actions** → **Daily Digest Email** → **Run workflow**。

> 💡 **不想手动点 6 次？** 用 GitHub Token + AI Agent 自动配置（见下方）。

#### 🤖 自动配置（用 GitHub Token）

生成一个 GitHub Token（https://github.com/settings/tokens → Generate new token (classic) → 勾选 `repo`），发给 Claude Code 之类的 AI Agent，让它自动调用 API 完成配置——和手动点 6 次效果一样，但只需要几秒。

#### 🖥️ 本地测试

```bash
pip install -r requirements.txt
cp .env.example .env   # 编辑填入 Key
python src/main.py
```

### 📧 邮件截图

![每日科技摘要邮件截图](assets/email-preview-top.png)

<details>
<summary>📜 查看完整邮件截图 (点击展开)</summary>

![完整邮件](assets/email-preview.jpg)

</details>

---

## ⚙️ Configuration

| Env Variable | Description |
|---|---|
| `SMTP_SERVER` | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |
| `EMAIL_USER` | Your Gmail address |
| `EMAIL_PASSWORD` | Gmail app password |
| `EMAIL_TO` | Recipient email |
| `DEEPSEEK_KEY` | DeepSeek API key |

## 📄 License

MIT — see [LICENSE](LICENSE)

## 🙏 Acknowledgments

- [arXiv API](https://info.arxiv.org/help/api/index.html)
- [Hacker News Firebase API](https://github.com/HackerNews/API)
- [Reddit RSS](https://www.reddit.com/dev/api/)
- [DeepSeek](https://www.deepseek.com/)

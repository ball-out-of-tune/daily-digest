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

### ⚡ Quick Start

1. **Fork** this repo
2. Rename `.env.example` → `.env` and fill in your keys
3. Add the same keys as [GitHub Actions Secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
4. Done — emails arrive at 8:00 and 17:00 (Beijing time)

```bash
# Or run locally
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

> [Screenshot placeholder — add your screenshot here!]

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

### ⚡ 三步上手

1. **Fork** 本仓库
2. 把 `.env.example` 重命名为 `.env`，填入你的 Key
3. 在 GitHub Actions Secrets 里配置同样的 Key，定时发送自动开启

```bash
# 本地测试
pip install -r requirements.txt
cp .env.example .env   # 编辑填入你的 Key
python src/main.py
```

### 📧 邮件截图

> [在此处放一张邮件截图]

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

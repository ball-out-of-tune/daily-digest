# 📋 每日科技摘要 — 代码流程图

## 1. 整体架构流程（高层视角）

```mermaid
flowchart TD
    A["⏰ GitHub Actions 定时触发<br/>UTC 00:00 (北京 08:00) / UTC 09:00 (北京 17:00)"] --> B["🐍 python src/main.py"]
    B --> C["📅 get_target_date()<br/>确定查询日期（避开周末）"]
    C --> D["🌐 数据获取（并行独立）"]
    
    D --> D1["fetch_arxiv_papers()<br/>arXiv API → 7个CS分类"]
    D --> D2["fetch_github_trending()<br/>GitHub Trending 页面抓取"]
    D --> D3["fetch_reddit()<br/>Reddit RSS → 10个子版块"]
    D --> D4["fetch_hackernews()<br/>HN Firebase API"]
    
    D1 --> E["📊 数据聚合"]
    D2 --> E
    D3 --> E
    D4 --> E
    
    E --> F{"有数据?"}
    F -->|Yes| G["🤖 curate_with_deepseek()<br/>DeepSeek API 第1次调用<br/>精选 + 生成推荐理由 + 趋势分析"]
    F -->|No| X["❌ 无数据，终止"]
    
    G --> H["🏛️ enrich_paper_teams()<br/>爬 arXiv HTML 补充机构信息"]
    H --> I["📚 generate_context_with_deepseek()<br/>爬参考文献 + DeepSeek API 第2次调用<br/>生成每篇论文的发展历程"]
    
    I --> J["📧 render_email()<br/>生成 HTML 邮件（深色/浅色/移动端适配）"]
    J --> K["✉️ send_email()<br/>Gmail SMTP 发送"]
    K --> L["✅ 完成"]
```

## 2. 详细数据流

```mermaid
flowchart TD
    subgraph 调度层
        CRON["GitHub Actions Cron<br/>0 0 * * * (早8点)<br/>0 9 * * * (午5点)"]
    end

    subgraph 入口
        MAIN["main()"]
    end

    subgraph 日期模块
        DATE["get_target_date()<br/>→ 昨日起回溯4天<br/>→ 跳过周六日<br/>→ 返回 (YYYYMMDD, YYYY-MM-DD)"]
    end

    subgraph 数据获取层
        ARXIV["fetch_arxiv_papers(date, display)<br/>────────────────<br/>遍历 7 个分类<br/>→ arXiv API XML 查询<br/>→ 解析 Atom Feed<br/>→ 提取: 标题/摘要/作者/机构<br/>→ _check_known_team() 标记知名团队<br/>→ 按 arxiv_id 去重<br/>→ 最多回溯7天(无数据时)<br/>────────────────<br/>返回: list&#91;dict&#93;"]
        
        GITHUB["fetch_github_trending()<br/>────────────────<br/>→ 抓取 github.com/trending<br/>→ 正则提取仓库名+描述<br/>→ 去重, 最多15个<br/>────────────────<br/>返回: list&#91;dict&#93;"]
        
        REDDIT["fetch_reddit()<br/>────────────────<br/>→ Reddit RSS (10个子版块合并)<br/>→ 解析 Atom Feed<br/>→ 提取标题/链接/子版块/内容<br/>→ 最多30条<br/>────────────────<br/>返回: list&#91;dict&#93;"]
        
        HN["fetch_hackernews()<br/>────────────────<br/>→ Firebase API: topstories.json<br/>→ 取前15个ID<br/>→ 逐个获取 item/{id}.json<br/>→ 提取标题/URL/分数/评论数<br/>────────────────<br/>返回: list&#91;dict&#93;"]
    end

    subgraph AI策展层
        CURATE["curate_with_deepseek(papers, repos, reddit, hn)<br/>────────────────<br/>→ 构建多部分提示词<br/>&nbsp;&nbsp;· 所有论文(标题+作者+摘要前200字)<br/>&nbsp;&nbsp;· 所有GitHub仓库<br/>&nbsp;&nbsp;· 所有Reddit帖子<br/>&nbsp;&nbsp;· 所有HN故事<br/>&nbsp;&nbsp;· 精选标准指令<br/>&nbsp;&nbsp;· JSON输出格式要求<br/>→ DeepSeek API (OpenAI SDK)<br/>&nbsp;&nbsp;temperature=0.7, max_tokens=30000<br/>→ 解析JSON响应<br/>→ 返回精选结果 + token统计<br/>────────────────<br/>返回: dict{papers, repos, reddit, hn, highlights, trends, _usage}"]
    end

    subgraph 补充信息层
        ENRICH["enrich_paper_teams(papers, selected_ids)<br/>────────────────<br/>→ 对每篇精选论文<br/>→ 抓取 arxiv.org/abs/{id}<br/>→ 在 &lt;div class='authors'&gt; 中搜索<br/>→ 匹配知名机构列表<br/>→ 写入 paper&#91;'scraped_team'&#93;<br/>────────────────<br/>返回: papers (in-place修改)"]
        
        CONTEXT["generate_context_with_deepseek(papers, selected_ids)<br/>────────────────<br/>→ 对每篇精选论文<br/>&nbsp;&nbsp;fetch_paper_references(id)<br/>&nbsp;&nbsp;→ 抓取 arxiv.org/html/{id}<br/>&nbsp;&nbsp;→ 解析 &lt;section class='ltx_bibliography'&gt;<br/>&nbsp;&nbsp;→ 提取 bibitem 文本<br/>&nbsp;&nbsp;→ sleep(0.3s) 限速<br/>→ 构建参考文献提示词<br/>→ DeepSeek API 第2次调用<br/>&nbsp;&nbsp;temperature=0.5, max_tokens=4096<br/>→ 生成每篇论文的"发展历程"<br/>────────────────<br/>返回: dict{paper_id→context}, usage"]
    end

    subgraph 渲染与发送层
        RENDER["render_email(papers, repos, reddit, hn, curation, date, contexts)<br/>────────────────<br/>→ 确定时段标签(上午版/下午版)<br/>→ _resolve_team() 统一团队查找<br/>→ 生成HTML:<br/>&nbsp;&nbsp;1. 页眉(标题/日期/时段/token)<br/>&nbsp;&nbsp;2. 趋势与机会(3段中文)<br/>&nbsp;&nbsp;3. 三大看点(问题/方法/热议)<br/>&nbsp;&nbsp;4. arXiv论文精选(25篇)<br/>&nbsp;&nbsp;5. GitHub Trending<br/>&nbsp;&nbsp;6. Reddit热门讨论<br/>&nbsp;&nbsp;7. Hacker News头条<br/>&nbsp;&nbsp;8. 页脚(下次推送时间)<br/>→ 嵌入式CSS(深色/浅色/移动端)<br/>────────────────<br/>返回: (html_string, time_label)"]
        
        SEND["send_email(html, date, time_label)<br/>────────────────<br/>→ 构建 MIMEMultipart<br/>→ Gmail SMTP (587, STARTTLS)<br/>→ 发送至 EMAIL_TO<br/>────────────────<br/>返回: bool"]
    end

    CRON --> MAIN
    MAIN --> DATE
    DATE --> ARXIV
    MAIN --> GITHUB
    MAIN --> REDDIT
    MAIN --> HN
    
    ARXIV --> CURATE
    GITHUB --> CURATE
    REDDIT --> CURATE
    HN --> CURATE
    
    CURATE --> ENRICH
    ENRICH --> CONTEXT
    CONTEXT --> RENDER
    RENDER --> SEND
```

## 3. arXiv 论文获取子流程

```mermaid
flowchart TD
    START["fetch_arxiv_papers(date_str, date_display)"] --> LOOP{"遍历 7 个分类<br/>cs.AI, cs.LG, cs.CL,<br/>cs.CV, cs.DC, cs.OS, cs.SE"}
    
    LOOP --> QUERY["构造 arXiv API 查询<br/>cat:{cat}+AND+submittedDate:&#91;{date}..{next}&#93;<br/>max_results=500"]
    QUERY --> HTTP["GET export.arxiv.org/api/query"]
    HTTP --> PARSE["解析 Atom XML"]
    
    PARSE --> EXTRACT["提取每条 entry:<br/>· title (标题)<br/>· summary (摘要前500字)<br/>· id → arxiv_id<br/>· author name + affiliation<br/>· category terms"]
    
    EXTRACT --> CHECK["_check_known_team(affiliation)<br/>匹配知名机构列表<br/>(OpenAI, DeepMind, Stanford...)"]
    
    CHECK --> APPEND["添加到 all_papers list"]
    APPEND --> LOOP
    
    LOOP -->|遍历完成| DEDUP["按 arxiv_id 去重"]
    DEDUP --> RETURN["返回 unique papers"]
```

## 4. DeepSeek 双阶段调用流程

```mermaid
flowchart TD
    subgraph 第一阶段_初筛与策展
        A1["curate_with_deepseek()"] --> A2["组装提示词<br/>· 所有论文 (~350篇)<br/>· 所有GitHub仓库<br/>· 所有Reddit帖子<br/>· 所有HN故事<br/>· 策展标准指令"]
        A2 --> A3["DeepSeek API 调用<br/>model: deepseek-chat<br/>temperature: 0.7<br/>max_tokens: 30,000<br/>timeout: 180s"]
        A3 --> A4["解析 JSON 响应<br/>· papers: 25篇精选<br/>· repos: 全部保留<br/>· reddit: 10-15条<br/>· hn: 8-12条<br/>· highlights: 三大看点<br/>· trends: 趋势分析"]
    end

    subgraph 第二阶段_参考文献与发展历程
        B1["generate_context_with_deepseek()"] --> B2["对每篇精选论文:<br/>fetch_paper_references(arxiv_id)"]
        B2 --> B3["抓取 arXiv HTML 页面<br/>解析 ltx_bibliography<br/>提取 bibitem 文本<br/>间隔 0.3秒"]
        B3 --> B4["组装参考文献提示词<br/>· 论文标题+摘要<br/>· 参考文献列表"]
        B4 --> B5["DeepSeek API 调用<br/>temperature: 0.5<br/>max_tokens: 4,096<br/>timeout: 120s"]
        B5 --> B6["解析 JSON 响应<br/>· contexts: 每篇1-2句中文<br/>· 发展历程描述"]
    end

    A4 --> B1
    B6 --> MERGE["合并两次 token 统计<br/>curation['_usage'] += context_usage"]
    MERGE --> OUT["传入 render_email()"]
```

## 5. HTML 邮件渲染结构

```mermaid
flowchart TD
    RENDER["render_email()"] --> HEADER["📋 页眉<br/>· 标题: 每日科技摘要<br/>· 论文日期<br/>· 时段标签 (上午版/下午版)<br/>· Token消耗"]
    
    HEADER --> TRENDS["📊 趋势与机会<br/>(来自 DeepSeek 策展)<br/>· 🔍 重点关注的问题<br/>· 💡 出现的创新方法<br/>· 🚀 可探索的方向"]
    
    TRENDS --> HIGHLIGHTS["⭐ 今日三大看点<br/>每类Top 3, 带团队/来源标注<br/>· ❓ 最有吸引力的问题<br/>· 💡 最具创新的解决方法<br/>· 🔥 热度最高的讨论"]
    
    HIGHLIGHTS --> ARXIV_SECTION["📄 arXiv 论文精选<br/>25篇, 每篇展示:<br/>· 标题 + 知名团队徽章<br/>· 作者 + 分类<br/>· 🏛️ 团队 · ❓ 问题 · 💡 方法<br/>· 📊 效果 · 📚 发展历程<br/>· ⭐ AI推荐理由"]
    
    ARXIV_SECTION --> GITHUB_SECTION["🔥 GitHub Trending<br/>· 仓库名 + 描述<br/>· 📦 做什么<br/>· 🔥 为什么火"]
    
    GITHUB_SECTION --> REDDIT_SECTION["💬 Reddit 热门讨论<br/>· 标题 + 子版块<br/>· 💬 话题<br/>· 🔥 为什么热"]
    
    REDDIT_SECTION --> HN_SECTION["📰 Hacker News 头条<br/>· 标题 + 分数/评论<br/>· 📰 话题<br/>· 🔥 为什么热"]
    
    HN_SECTION --> FOOTER["📮 页脚<br/>· 下次推送时间<br/>· 数据来源说明<br/>· Token消耗明细"]
```

## 6. main() 函数完整执行流程

```mermaid
flowchart TD
    START(["main() 入口"]) --> BANNER["打印横幅"]
    BANNER --> DATE_FUNC["get_target_date()<br/>确定目标日期"]
    
    DATE_FUNC --> RETRY_LOOP{"arXiv 获取循环<br/>最多7次"}
    RETRY_LOOP -->|每次| FETCH_ARXIV["fetch_arxiv_papers()"]
    FETCH_ARXIV --> HAS_PAPERS{"有论文?"}
    HAS_PAPERS -->|Yes| PARALLEL_FETCH["并行获取其余数据源"]
    HAS_PAPERS -->|No| BACKOFF["回退1天<br/>跳过周末"]
    BACKOFF --> RETRY_LOOP
    
    PARALLEL_FETCH --> FETCH_GITHUB["fetch_github_trending()"]
    PARALLEL_FETCH --> FETCH_REDDIT["fetch_reddit()"]
    PARALLEL_FETCH --> FETCH_HN["fetch_hackernews()"]
    
    FETCH_GITHUB --> CHECK_DATA{"任一数据源<br/>有数据?"}
    FETCH_REDDIT --> CHECK_DATA
    FETCH_HN --> CHECK_DATA
    
    CHECK_DATA -->|Yes| CURATE["curate_with_deepseek()<br/>DeepSeek 第1次调用"]
    CHECK_DATA -->|No| DONE_FAIL["打印无数据, 退出"]
    
    CURATE --> HAS_CURATION{"策展成功?"}
    HAS_CURATION -->|Yes| GET_IDS["提取 selected_ids"]
    HAS_CURATION -->|No| RENDER_FALLBACK["降级渲染<br/>(原始数据, 无AI分析)"]
    
    GET_IDS --> ENRICH["enrich_paper_teams()<br/>补充团队信息"]
    ENRICH --> GEN_CTX["generate_context_with_deepseek()<br/>DeepSeek 第2次调用<br/>生成发展历程"]
    
    GEN_CTX --> MERGE_TOKENS["合并两次 token 统计"]
    MERGE_TOKENS --> RENDER["render_email()<br/>生成 HTML 邮件"]
    RENDER_FALLBACK --> RENDER
    
    RENDER --> SEND["send_email()<br/>通过 Gmail SMTP 发送"]
    SEND --> RESULT{"发送成功?"}
    RESULT -->|Yes| OK["🎉 打印成功消息"]
    RESULT -->|No| FAIL["❌ 打印失败消息"]
```

## 7. 外部服务依赖总览

```mermaid
flowchart LR
    subgraph 本项目
        MAIN_PY["src/main.py<br/>(1135行单文件)"]
    end

    subgraph 外部API
        ARXIV_API["export.arxiv.org<br/>论文查询API"]
        ARXIV_ABS["arxiv.org/abs/{id}<br/>论文摘要页HTML"]
        ARXIV_HTML["arxiv.org/html/{id}<br/>论文全文HTML"]
        GITHUB_WEB["github.com/trending<br/>热门仓库页面"]
        REDDIT_RSS["reddit.com/r/*/hot.rss<br/>热门帖子RSS"]
        HN_FB["hacker-news.firebaseio.com<br/>Firebase JSON API"]
        DEEPSEEK["api.deepseek.com<br/>OpenAI兼容API"]
        GMAIL["smtp.gmail.com:587<br/>邮件发送"]
    end

    MAIN_PY -->|"urllib GET"| ARXIV_API
    MAIN_PY -->|"urllib GET"| ARXIV_ABS
    MAIN_PY -->|"urllib GET"| ARXIV_HTML
    MAIN_PY -->|"urllib GET"| GITHUB_WEB
    MAIN_PY -->|"urllib GET"| REDDIT_RSS
    MAIN_PY -->|"urllib GET"| HN_FB
    MAIN_PY -->|"OpenAI SDK POST"| DEEPSEEK
    MAIN_PY -->|"smtplib STARTTLS"| GMAIL
```

## 8. 关键数据结构

```mermaid
flowchart TD
    subgraph 论文对象
        PAPER["paper dict<br/>· title: str<br/>· summary: str (前500字)<br/>· arxiv_id: str<br/>· authors: list&#91;str&#93; (最多6人)<br/>· has_known_team: bool<br/>· categories: list&#91;str&#93;<br/>· primary_cat: str<br/>· scraped_team: str (后续补充)"]
    end

    subgraph 策展结果
        CURATION["curation dict<br/>· papers: list&#91;dict&#93; (25篇)<br/>· repos: list&#91;dict&#93;<br/>· reddit: list&#91;dict&#93;<br/>· hn: list&#91;dict&#93;<br/>· highlights: {problems, methods, buzz}<br/>· trends: {problems, methods, opportunities}<br/>· _usage: {prompt_tokens, completion_tokens, total_tokens}"]
    end

    subgraph 上下文映射
        CTX["contexts dict<br/>· key: paper_id (如 'P0')<br/>· value: 发展历程描述 (中文1-2句)"]
    end

    subgraph 邮件产物
        EMAIL["(html_string, time_label)<br/>· html: 完整HTML文档<br/>· time_label: '上午版' | '下午版'"]
    end
```

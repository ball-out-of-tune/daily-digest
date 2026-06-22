"""
每日科技摘要
拉取 arXiv 某天全部论文 + GitHub Trending + Reddit + Hacker News，
用 DeepSeek 筛选最值得看的条目并生成推荐理由，发送邮件。
"""

import os
import sys
import json
import smtplib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, datetime, timedelta, timezone
from openai import OpenAI

# 修复 Windows 中文编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ============================================================
# 配置
# ============================================================

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "zycZYC030@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "zycZYC030@gmail.com")

DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY", "")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-chat"

ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.DC", "cs.OS", "cs.SE"]

REDDIT_SUBS = [
    "MachineLearning", "LocalLLaMA", "singularity", "OpenAI",
    "programming", "Python", "cpp", "linux", "netsec", "compsci"
]


# ============================================================
# 日期工具
# ============================================================

def get_target_date():
    """获取应该查询的 arXiv 日期（YYYYMMDD）
    规则：用昨天的日期；如果昨天是周末则用周五。
    但是 arXiv 实际只有周一到周四发布论文（周五也没有），
    所以可能需要回退 1-3 天才能找到有论文的日期。
    """
    today = date.today()
    # 尝试最近 4 天
    for delta in range(1, 5):
        target = today - timedelta(days=delta)
        w = target.weekday()
        if w == 5 or w == 6:  # 跳过周六日
            continue
        return target.strftime("%Y%m%d"), target.strftime("%Y-%m-%d")
    # 兜底
    target = today - timedelta(days=1)
    return target.strftime("%Y%m%d"), target.strftime("%Y-%m-%d")


# ============================================================
# 通用 HTTP
# ============================================================

def safe_request(url, timeout=30, headers=None):
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


# ============================================================
# arXiv
# ============================================================

def fetch_arxiv_papers(target_date_str, target_date_display):
    """拉取某一天所有 7 个分类的论文，去重"""
    print(f"[arXiv] 拉取 {target_date_display} 全部论文...")
    all_papers = []

    for cat in ARXIV_CATEGORIES:
        try:
            # 构造日期查询，不 encode 方括号
            next_day = (datetime.strptime(target_date_str, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            query = f"cat:{cat}+AND+submittedDate:[{target_date_str}000000+TO+{next_day}000000]"
            url = f"http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results=500"

            with safe_request(url, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                root = ET.fromstring(raw)

            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }

            count = 0
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                id_el = entry.find("atom:id", ns)

                if title_el is None or id_el is None:
                    continue

                # 提取作者和 affiliation
                authors = []
                has_known_team = False
                for a in entry.findall("atom:author", ns):
                    name_el = a.find("atom:name", ns)
                    aff_el = a.find("arxiv:affiliation", ns)
                    name = name_el.text.strip() if name_el is not None else ""
                    aff = aff_el.text.strip() if aff_el is not None else ""
                    authors.append(name)
                    # 检查是否知名团队
                    if _check_known_team(aff):
                        has_known_team = True

                arxiv_id = id_el.text.strip().split("/abs/")[-1]

                # 获取分类列表
                cats = []
                cat_els = entry.findall("atom:category", ns)
                for c in cat_els:
                    term = c.get("term", "")
                    if term:
                        cats.append(term)

                all_papers.append({
                    "title": title_el.text.strip().replace("\n", " "),
                    "summary": summary_el.text.strip()[:500] if summary_el is not None and summary_el.text else "",
                    "arxiv_id": arxiv_id,
                    "authors": authors[:6],
                    "has_known_team": has_known_team,
                    "categories": cats,
                    "primary_cat": cat,
                })
                count += 1

            print(f"  {cat}: {count} 篇")

        except Exception as e:
            print(f"  ⚠ arXiv {cat} 失败: {e}")

    # 去重
    seen = set()
    unique = []
    for p in all_papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    print(f"  ✅ 去重后 {len(unique)} 篇（原始 {len(all_papers)} 篇）")
    return unique


def _check_known_team(affiliation):
    """检查 affiliation 是否来自知名机构"""
    if not affiliation:
        return False
    aff_lower = affiliation.lower()
    known = [
        # 企业
        "openai", "deepmind", "google", "anthropic", "meta ai", "metaai",
        "microsoft research", "microsoft", "nvidia", "apple",
        "hugging face", "huggingface", "stability ai",
        "xai", "x.ai", "elon musk",
        "字节跳动", "bytedance", "tencent", "腾讯",
        "baidu", "百度", "alibaba", "阿里巴巴",
        "mistral", "cohere", "adept", "character.ai",
        # 高校
        "stanford", "massachusetts institute of technology", "mit",
        "carnegie mellon", "cmu", "uc berkeley", "berkeley",
        "oxford", "cambridge", "eth zurich", "eth zürich",
        "princeton", "harvard", "caltech", "yale",
        "university of washington", "uw seattle",
        "university of toronto", "vector institute",
        "nyu", "columbia university", "cornell",
        "uiuc", "ut austin", "gatech", "georgia tech",
        "tsinghua", "清华大学", "peking", "北京大学",
        "zhejiang", "浙江大学", "sjtu", "上海交通大学",
    ]
    return any(k in aff_lower for k in known)


# ============================================================
# GitHub Trending
# ============================================================

def fetch_github_trending():
    """拉取 GitHub Trending 全语言"""
    print("[GitHub] 拉取 Trending 全语言...")
    repos = []
    try:
        url = "https://github.com/trending?since=daily"
        with safe_request(url, timeout=30) as resp:
            html = resp.read().decode("utf-8")

        # 匹配仓库
        repo_matches = re.findall(
            r'<h2[^>]*>\s*<a[^>]*href="/([^/"]+/[^/"]+)"[^>]*>',
            html, re.DOTALL
        )
        # 匹配描述
        desc_matches = re.findall(
            r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>',
            html, re.DOTALL
        )

        seen = set()
        for i, repo_name in enumerate(repo_matches):
            repo_name = repo_name.strip()
            if not repo_name or repo_name in seen:
                continue
            seen.add(repo_name)

            desc = ""
            if i < len(desc_matches):
                desc = re.sub(r'<[^>]+>', '', desc_matches[i]).strip()

            repos.append({
                "repo": repo_name,
                "description": desc[:200],
                "url": f"https://github.com/{repo_name}",
            })
            if len(seen) >= 15:
                break

    except Exception as e:
        print(f"  ⚠ GitHub Trending 失败: {e}")

    print(f"  ✅ 获取 {len(repos)} 个仓库")
    return repos


# ============================================================
# Reddit
# ============================================================

def fetch_reddit():
    """拉取 Reddit 热门帖子（一次请求所有 subreddit）"""
    print("[Reddit] 拉取热门帖子...")
    posts = []

    sub_string = "+".join(REDDIT_SUBS)
    try:
        url = f"https://www.reddit.com/r/{sub_string}/hot.rss?limit=30"
        with safe_request(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            root = ET.fromstring(raw)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            content_el = entry.find("atom:content", ns)

            if title_el is None:
                continue

            href = link_el.get("href") if link_el is not None else ""
            sub_match = re.search(r'/r/(\w+)', href)
            sub_name = sub_match.group(1) if sub_match else "unknown"

            posts.append({
                "title": title_el.text.strip(),
                "subreddit": f"r/{sub_name}",
                "ups": 0,
                "num_comments": 0,
                "url": href,
                "selftext": content_el.text[:300] if content_el is not None and content_el.text else "",
            })
    except Exception as e:
        print(f"  ⚠ Reddit 失败: {e}")

    print(f"  ✅ 获取 {len(posts)} 条帖子")
    return posts[:30]


# ============================================================
# Hacker News
# ============================================================

def fetch_hackernews():
    """拉取 Hacker News 头条"""
    print("[HN] 拉取头条...")
    try:
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        with safe_request(url, timeout=30) as resp:
            ids = json.loads(resp.read().decode("utf-8"))[:15]

        stories = []
        for sid in ids:
            try:
                url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                with safe_request(url, timeout=10) as resp:
                    item = json.loads(resp.read().decode("utf-8"))
                if item and "title" in item:
                    stories.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "score": item.get("score", 0),
                        "descendants": item.get("descendants", 0),
                        "hn_url": f"https://news.ycombinator.com/item?id={sid}",
                    })
            except Exception:
                pass

        print(f"  ✅ 获取 {len(stories)} 条 HN 新闻")
        return stories
    except Exception as e:
        print(f"  ⚠ HN 失败: {e}")
        return []


# ============================================================
# DeepSeek AI 精选
# ============================================================

def curate_with_deepseek(papers, repos, reddit_posts, hn_stories):
    """用 DeepSeek 从全部候选中精选并生成推荐理由"""
    print("[DeepSeek] AI 筛选中...")

    client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE)

    # 构建论文列表
    papers_lines = []
    for i, p in enumerate(papers):
        team_tag = "🏢知名团队" if p["has_known_team"] else ""
        cats_str = ", ".join(p["categories"][:3])
        papers_lines.append(
            f"[P{i}] {team_tag} [{cats_str}] {p['title']}\n"
            f"    作者: {', '.join(p['authors'][:5])}\n"
            f"    摘要: {p['summary'][:300]}"
        )
    papers_text = "\n".join(papers_lines)

    # 构建 GitHub 列表
    repos_lines = []
    for i, r in enumerate(repos):
        repos_lines.append(f"[G{i}] {r['repo']}\n    {r['description']}")
    repos_text = "\n".join(repos_lines)

    # 构建 Reddit 列表（含 selftext 让 AI 看懂内容）
    reddit_lines = []
    for i, p in enumerate(reddit_posts):
        text_preview = p.get("selftext", "")[:200] if p.get("selftext") else ""
        reddit_lines.append(f"[R{i}] {p['subreddit']} | {p['title']}\n    内容: {text_preview}" if text_preview else f"[R{i}] {p['subreddit']} | {p['title']}")
    reddit_text = "\n".join(reddit_lines)

    # 构建 HN 列表
    hn_lines = []
    for i, s in enumerate(hn_stories):
        hn_lines.append(f"[H{i}] 👍{s['score']} 💬{s['descendants']} | {s['title']}")
    hn_text = "\n".join(hn_lines)

    prompt = f"""你是一位顶级科技内容策展人。请从以下候选中筛选出最值得关注的条目。

## 核心原则：选真正值得看的东西
你的首要任务是**选出好内容**。优先关注：
1. 知名团队的新工作（OpenAI、DeepMind、Google、Anthropic、Meta、Stanford、MIT 等）
2. 方法新颖、效果惊人、有实用价值的论文
3. 2026年热门方向：AI Agent、推理模型、多模态、代码/数学推理、对齐/安全、高效推理、RAG、世界模型、具身智能、AI4Science
4. 引发社区讨论的帖子/项目
5. 跳过纯理论水文、微小改进、只在玩具数据集上验证的

## 选好后，为每条写几句分析：
- 论文：team（机构）、problem（解决什么问题）、method（核心方法）、results（效果）、highlight（为什么值得看）
- GitHub：what（做什么的）、why（为什么火了）
- Reddit/HN：topic（讨论什么）、why（为什么热）

## 数量：
- 论文 25 篇 | GitHub 全部保留 | Reddit 10-15 条 | HN 8-12 条
- 额外1：**今日三大看点**（每类选 Top 3，可从论文/仓库/帖子中任意选取）：
  - top_problems: 今天最有吸引力的 3 个问题是什么？（值得所有人关注的问题）
  - top_methods: 今天最具创新性的 3 个解决方法是什么？（让人眼前一亮的新思路）
  - top_buzz: 今天热度最高、大家都在讨论的 3 个内容是什么？
- 额外2：**趋势与机会**：基于今天所有精选内容，总结以下三方面（每段 3-5 句中文）：
  - problems: 今天的内容反映了大家重点关注了哪些问题？有什么共识或争议？
  - methods: 都用了什么样的创新性解决方法？什么技术路线正在崛起？
  - opportunities: 基于这些趋势，我们可以做什么样的项目和科研？有什么被忽视但值得做的方向？

## 团队名要求：
- 团队请写**具体机构全名**，如"Stanford University"而非"多家学术机构"、如"Google Research"而非"科技巨头"、如"MIT CSAIL"而非"高校"。从作者名和摘要推断，无法确定的具体到哪个学校/公司也写"未知"。

## arXiv 论文（{len(papers)} 篇，🏢=知名团队）
{papers_text}

## GitHub Trending（{len(repos)} 个）
{repos_text}

## Reddit 热门（{len(reddit_posts)} 条，含帖子内容摘要）
{reddit_text}

## Hacker News 头条（{len(hn_stories)} 条）
{hn_text}

返回 JSON（不要 markdown 代码块）：
{{"highlights":{{"problems":[{{"id":"P0","desc":"为什么这个问题值得关注"}}],"methods":[{{"id":"G0","desc":"为什么这个方法眼前一亮"}}],"buzz":[{{"id":"R0","desc":"为什么大家都在讨论"}}]}},"papers":[{{"id":"P0","team":"机构","problem":"问题","method":"方法","results":"效果","highlight":"为什么值得看"}}],"repos":[{{"id":"G0","what":"做什么","why":"为什么火"}}],"reddit":[{{"id":"R0","topic":"话题","why":"为什么热"}}],"hn":[{{"id":"H0","topic":"话题","why":"为什么热"}}],"trends":{{"problems":"重点关注的问题","methods":"创新方法汇总","opportunities":"可探索的方向和项目"}}}}"""

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=14000,
        )
        content = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "total_tokens": resp.usage.total_tokens if resp.usage else 0,
        }
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:])
            if content.endswith("```"):
                content = content[:-3]
        content = content.strip()
        result = json.loads(content)
        result["_usage"] = usage
        print(f"  ✅ AI 筛选完成：论文 {len(result.get('papers',[]))} 篇, 仓库 {len(result.get('repos',[]))} 个, Reddit {len(result.get('reddit',[]))} 条, HN {len(result.get('hn',[]))} 条")
        print(f"  📊 Token: 输入 {usage['prompt_tokens']} + 输出 {usage['completion_tokens']} = {usage['total_tokens']}")
        return result
    except json.JSONDecodeError as e:
        print(f"  ⚠ DeepSeek 返回非 JSON")
        print(f"  返回内容: {content[:800] if 'content' in dir() else 'N/A'}")
        return None
    except Exception as e:
        print(f"  ⚠ DeepSeek 出错: {e}")
        return None


# ============================================================
# 团队信息补充（爬 arXiv HTML 页面）
# ============================================================

def enrich_paper_teams(papers, selected_ids):
    """对 DeepSeek 精选的论文，爬 arXiv abs 页面的 authors div 获取机构"""
    print("[Team] 补充团队信息...")

    KNOWN_INSTITUTIONS = [
        "OpenAI", "DeepMind", "Google", "Anthropic", "Meta AI", "Meta",
        "Microsoft Research", "Microsoft", "NVIDIA", "Apple",
        "Stability AI",
        "Stanford University", "Stanford", "MIT", "Massachusetts Institute of Technology",
        "Carnegie Mellon University", "CMU", "UC Berkeley", "Berkeley",
        "University of Oxford", "Oxford", "University of Cambridge", "Cambridge",
        "ETH Zurich", "ETH", "EPFL",
        "Princeton University", "Princeton", "Harvard University", "Harvard",
        "Caltech", "Yale University", "Yale",
        "University of Washington", "UW",
        "University of Toronto", "Vector Institute",
        "NYU", "New York University", "Columbia University", "Cornell University",
        "UIUC", "UT Austin", "Georgia Tech", "Georgia Institute of Technology",
        "University of Michigan", "UMD", "USC",
        "Tsinghua University", "Peking University",
        "Zhejiang University", "Shanghai Jiao Tong",
        "Bytedance", "Alibaba", "Tencent",
        "Baidu", "DeepSeek", "Moonshot", "Zhipu",
        "Allen Institute for AI", "AI2", "MBZUAI", "KAUST",
    ]

    enriched = 0
    for paper_id in selected_ids:
        idx = int(paper_id[1:])
        if idx >= len(papers):
            continue
        paper = papers[idx]
        if paper.get("has_known_team") or paper.get("scraped_team"):
            continue

        arxiv_id = paper.get("arxiv_id", "")
        if not arxiv_id:
            continue

        try:
            url = f"https://arxiv.org/abs/{arxiv_id}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DailyDigest/1.0)"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8")

            # 只在 authors div 中搜索（排除参考文献/页脚中的 HuggingFace 等误匹配）
            auth_div = re.search(r'<div class="authors">(.*?)</div>', html, re.DOTALL)
            if auth_div:
                search_text = re.sub(r'<[^>]+>', ' ', auth_div.group(1))
                search_text = re.sub(r'\s+', ' ', search_text)
            else:
                # 备选：页面纯文本前 3000 字符
                plain = re.sub(r'<[^>]+>', ' ', html)
                search_text = re.sub(r'\s+', ' ', plain)[:3000]

            found_teams = set()
            for inst in KNOWN_INSTITUTIONS:
                if inst.lower() in search_text.lower():
                    found_teams.add(inst)

            if found_teams:
                best = max(found_teams, key=len)
                paper["scraped_team"] = best
                paper["has_known_team"] = True
                enriched += 1

        except Exception:
            pass

    print(f"  ✅ 补充了 {enriched} 个团队信息")
    return papers


# ============================================================
# 参考文献与发展历程
# ============================================================

def fetch_paper_references(arxiv_id):
    """爬取 arXiv HTML 页面的参考文献列表"""
    refs = []
    html = None
    # 尝试多种 URL 格式
    for url in [
        f"https://arxiv.org/html/{arxiv_id}",       # 无版本后缀
        f"https://arxiv.org/html/{arxiv_id}v1",      # v1
    ]:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; DailyDigest/1.0)"
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8")
            break
        except Exception:
            continue

    if not html:
        return refs

    try:

        # 提取 bibliography section 中的 bibitem
        bib_match = re.search(
            r'<section[^>]*class="ltx_bibliography"[^>]*>(.*?)</section>',
            html, re.DOTALL
        )
        if not bib_match:
            return refs

        bibitems = re.findall(
            r'<li[^>]*class="ltx_bibitem"[^>]*>(.*?)</li>',
            bib_match.group(1), re.DOTALL
        )

        for item in bibitems:
            text = re.sub(r'<[^>]+>', ' ', item)
            text = re.sub(r'\s+', ' ', text).strip()
            # 提取年份
            year_match = re.search(r'\((\d{4})\)', text)
            year = year_match.group(1) if year_match else ""
            # 用年份分割，前面的为作者，后面的为标题+来源
            if year and f"({year})" in text:
                parts = text.split(f"({year})", 1)
                # 后面部分的前 200 字符作为标题+来源
                rest = parts[1].strip()[:200] if len(parts) > 1 else text[:200]
                refs.append(f"({year}) {rest}")
            else:
                refs.append(text[:200])

    except Exception:
        pass

    return refs


def generate_context_with_deepseek(papers, selected_ids):
    """二次 DeepSeek 调用：基于参考文献生成发展历程"""
    print("[Context] 爬参考文献 + 生成发展历程...")

    client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE)
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # 爬取所有精选论文的参考文献
    paper_contexts = []
    for paper_id in selected_ids:
        idx = int(paper_id[1:])
        if idx >= len(papers):
            continue
        paper = papers[idx]
        arxiv_id = paper.get("arxiv_id", "")
        if not arxiv_id:
            continue

        refs = fetch_paper_references(arxiv_id)
        time.sleep(0.3)  # 控制请求频率

        ref_text = "; ".join(refs[:20]) if refs else "无参考文献数据"

        paper_contexts.append({
            "id": paper_id,
            "title": paper["title"],
            "summary": paper["summary"][:400],
            "refs": ref_text,
        })

    if not paper_contexts:
        return {}, usage_total

    # 构建 prompt
    lines = []
    for pc in paper_contexts:
        lines.append(
            f"[{pc['id']}] 标题: {pc['title']}\n"
            f"    摘要: {pc['summary']}\n"
            f"    参考文献: {pc['refs']}"
        )
    data_text = "\n".join(lines)

    prompt = f"""以下是今天精选的论文，每篇附有摘要和参考文献列表。请为每篇论文总结"发展历程"（1-2句中文）：

发展历程 = 这篇论文引用了哪些前人的关键工作？前人方法有什么局限？这篇论文解决了什么前人没解决的问题？
注意：如果某篇论文的参考文献显示"无参考文献数据"，请根据摘要和你的知识来推断该论文的研究脉络和发展历程，不要写"无参考文献数据"。

## 论文列表
{data_text}

返回 JSON（不要 markdown）：
{{"contexts":[{{"id":"P0","context":"发展历程描述"}}]}}"""

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            lines_txt = content.split("\n")
            content = "\n".join(lines_txt[1:])
            if content.endswith("```"):
                content = content[:-3]
        content = content.strip()
        result = json.loads(content)

        if resp.usage:
            usage_total["prompt_tokens"] = resp.usage.prompt_tokens
            usage_total["completion_tokens"] = resp.usage.completion_tokens
            usage_total["total_tokens"] = resp.usage.total_tokens

        contexts = {c["id"]: c["context"] for c in result.get("contexts", [])}
        print(f"  ✅ 生成了 {len(contexts)} 个发展历程")
        return contexts, usage_total

    except Exception as e:
        print(f"  ⚠ Context 生成失败: {e}")
        return {}, usage_total


# ============================================================
# 邮件渲染
# ============================================================

def render_email(papers, repos, reddit_posts, hn_stories, curation, target_date_display, contexts=None):
    """生成 HTML 邮件"""
    if contexts is None:
        contexts = {}
    now = datetime.now()
    time_label = "上午版" if now.hour < 14 else "下午版"
    usage = curation.get("_usage", {}) if curation else {}

    # 建立索引
    paper_map = {f"P{i}": p for i, p in enumerate(papers)}
    repo_map = {f"G{i}": r for i, r in enumerate(repos)}
    reddit_map = {f"R{i}": p for i, p in enumerate(reddit_posts)}
    hn_map = {f"H{i}": s for i, s in enumerate(hn_stories)}

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<style>
  @media (prefers-color-scheme: dark) {{
    body, .card {{ background: #1a1a2e !important; }}
    .card {{ box-shadow: 0 2px 8px rgba(255,255,255,0.05) !important; }}
    h1 {{ color: #e0e0e0 !important; }}
    h2 {{ color: #ddd !important; }}
    .subtitle {{ color: #999 !important; }}
    .paper-bg {{ background: #2a1a1a !important; }}
    .repo-bg {{ background: #1a2a1a !important; }}
    .reddit-bg {{ background: #2a2018 !important; }}
    .hn-bg {{ background: #2a2418 !important; }}
    .trend-bg {{ background: #1e1a30 !important; }}
    .top3-bg {{ background: #2a2810 !important; }}
    .section-link {{ color: #8ab4f8 !important; }}
    .field-text {{ color: #bbb !important; }}
    .reason-text {{ color: #ccc !important; }}
    .footer-text {{ color: #777 !important; }}
    .border-divider {{ border-color: #333 !important; }}
  }}
  @media only screen and (max-width: 480px) {{
    body {{ padding: 8px !important; }}
    .card {{ padding: 16px !important; border-radius: 8px !important; }}
    .paper-item {{ padding: 10px !important; }}
    h1 {{ font-size: 20px !important; }}
    h2 {{ font-size: 16px !important; }}
    a {{ font-size: 14px !important; }}
  }}
</style>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
<div class="card" style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

<h1 style="color: #1a1a2e; margin: 0 0 4px 0;">📋 每日科技摘要</h1>
<p class="subtitle" style="color: #888; margin: 0 0 24px 0; font-size: 14px;">论文日期: {target_date_display} · {time_label} · AI 策展</p>

<!-- 趋势与机会（最前面）-->
"""

    # 趋势与机会（移到最前面）
    if curation and curation.get("trends"):
        trends = curation["trends"]
        problems_text = trends.get("problems", "")
        methods_text = trends.get("methods", "")
        opportunities_text = trends.get("opportunities", "")
        html += f"""
<h2 style="color: #6c5ce7; border-bottom: 2px solid #6c5ce7; padding-bottom: 6px;">📊 趋势与机会</h2>
<div style="background: #f8f7ff; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
  <div style="margin-bottom: 14px;">
    <div style="font-weight: 600; color: #6c5ce7; font-size: 14px; margin-bottom: 4px;">🔍 大家都在关注什么问题？</div>
    <div style="color: #444; font-size: 13px; line-height: 1.7;">{problems_text}</div>
  </div>
  <div style="margin-bottom: 14px;">
    <div style="font-weight: 600; color: #6c5ce7; font-size: 14px; margin-bottom: 4px;">💡 出现了哪些创新方法？</div>
    <div style="color: #444; font-size: 13px; line-height: 1.7;">{methods_text}</div>
  </div>
  <div>
    <div style="font-weight: 600; color: #6c5ce7; font-size: 14px; margin-bottom: 4px;">🚀 我们可以做什么？</div>
    <div style="color: #444; font-size: 13px; line-height: 1.7;">{opportunities_text}</div>
  </div>
</div>"""

    # Token 小标签
    token_info = f"{usage.get('total_tokens', '?')} tokens" if usage else ""
    html += f"""
<div style="text-align: right; color: #aaa; font-size: 11px; margin-bottom: 16px;">📊 本次消耗: {token_info}</div>

<!-- 今日三大看点 -->
"""

    def _render_highlight(tid, h_desc, color):
        """渲染单个看点条目"""
        prefix = tid[0] if tid else ""
        if prefix == "P":
            p = paper_map.get(tid)
            if p:
                return f"""
<div style="margin: 6px 0; padding: 10px; border-radius: 6px; border-left: 3px solid {color}; background: #fffdf5;">
  <span style="font-size:11px;color:#888;">📄 arXiv</span>
  <a href="https://arxiv.org/abs/{p['arxiv_id']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 13px; display: block; margin: 2px 0;">{p['title']}</a>
  <div style="color: #555; font-size: 12px; line-height: 1.5;">{h_desc}</div>
</div>"""
        elif prefix == "G":
            r = repo_map.get(tid)
            if r:
                return f"""
<div style="margin: 6px 0; padding: 10px; border-radius: 6px; border-left: 3px solid {color}; background: #fffdf5;">
  <span style="font-size:11px;color:#888;">📦 GitHub</span>
  <a href="{r['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 13px; display: block; margin: 2px 0;">{r['repo']}</a>
  <div style="color: #555; font-size: 12px; line-height: 1.5;">{h_desc}</div>
</div>"""
        elif prefix == "R":
            p = reddit_map.get(tid)
            if p:
                return f"""
<div style="margin: 6px 0; padding: 10px; border-radius: 6px; border-left: 3px solid {color}; background: #fffdf5;">
  <span style="font-size:11px;color:#888;">💬 {p['subreddit']}</span>
  <a href="{p['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 13px; display: block; margin: 2px 0;">{p['title'][:120]}</a>
  <div style="color: #555; font-size: 12px; line-height: 1.5;">{h_desc}</div>
</div>"""
        elif prefix == "H":
            s = hn_map.get(tid)
            if s:
                return f"""
<div style="margin: 6px 0; padding: 10px; border-radius: 6px; border-left: 3px solid {color}; background: #fffdf5;">
  <span style="font-size:11px;color:#888;">📰 HN · 👍{s['score']}</span>
  <a href="{s['hn_url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 13px; display: block; margin: 2px 0;">{s['title'][:120]}</a>
  <div style="color: #555; font-size: 12px; line-height: 1.5;">{h_desc}</div>
</div>"""
        return ""

    # 三大看点板块
    if curation and curation.get("highlights"):
        hl = curation["highlights"]
        html += '<h2 style="color: #e6b800; border-bottom: 2px solid #e6b800; padding-bottom: 6px;">⭐ 今日三大看点</h2>'

        for label, key, color, emoji in [
            ("最有吸引力的问题", "problems", "#d4a017", "❓"),
            ("最具创新的解决方法", "methods", "#1a7f37", "💡"),
            ("热度最高的讨论", "buzz", "#ff4500", "🔥"),
        ]:
            items = hl.get(key, [])[:3]
            if items:
                html += f'<div style="margin-bottom: 16px;"><div style="font-weight: 600; color: {color}; font-size: 14px; margin-bottom: 8px;">{emoji} {label}</div>'
                for item in items:
                    html += _render_highlight(item.get("id", ""), item.get("desc", ""), color)
                html += '</div>'

    html += """
<!-- arXiv -->
<h2 style="color: #b83b3b; border-bottom: 2px solid #b83b3b; padding-bottom: 6px;">📄 arXiv 论文精选（当日 """ + str(len(papers)) + """ 篇中精选）</h2>
"""

    # arXiv
    if curation and curation.get("papers"):
        for item in curation["papers"]:
            pid = item["id"]
            p = paper_map.get(pid)
            if not p:
                continue
            team_badge = ' <span style="background:#b83b3b;color:white;padding:1px 6px;border-radius:4px;font-size:10px;">知名团队</span>' if p["has_known_team"] else ""

            # 团队：优先用爬虫补上的，其次用 DeepSeek 识别的
            team_ds = item.get("team", "")
            team_scraped = p.get("scraped_team", "")
            if team_scraped and ("未知" in str(team_ds) or not team_ds):
                team = team_scraped
            else:
                team = team_ds if team_ds and "未知" not in str(team_ds) else team_scraped
            problem = item.get("problem", "")
            method = item.get("method", "")
            results = item.get("results", "")
            highlight = item.get("highlight", item.get("reason", ""))

            fields_html = ""
            if team:
                fields_html += f'<div style="font-size:12px;margin-top:4px;">🏛️ <b>团队:</b> {team}</div>'
            if problem:
                fields_html += f'<div style="font-size:12px;margin-top:2px;">❓ <b>问题:</b> {problem}</div>'
            if method:
                fields_html += f'<div style="font-size:12px;margin-top:2px;">💡 <b>方法:</b> {method}</div>'
            if results:
                fields_html += f'<div style="font-size:12px;margin-top:2px;">📊 <b>效果:</b> {results}</div>'
            # 发展历程（从二次 DeepSeek 调用生成）
            ctx = contexts.get(pid, "")
            if ctx:
                fields_html += f'<div style="font-size:12px;margin-top:2px;color:#6b4c9a;">📚 <b>发展历程:</b> {ctx}</div>'

            html += f"""
<div style="margin: 16px 0; padding: 14px; background: #fff5f5; border-radius: 8px; border-left: 3px solid #b83b3b;">
  <a href="https://arxiv.org/abs/{p['arxiv_id']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 15px;">{p['title']}</a>{team_badge}
  <div style="color: #666; font-size: 12px; margin: 4px 0;">{', '.join(p['authors'][:4])} · {p['primary_cat']}</div>
  {fields_html}
  <div style="color: #b83b3b; font-size: 13px; margin-top: 6px; font-weight: 500;">⭐ {highlight}</div>
</div>"""
    elif papers:
        for p in papers[:12]:
            team_badge = ' <span style="background:#b83b3b;color:white;padding:1px 6px;border-radius:4px;font-size:10px;">知名团队</span>' if p["has_known_team"] else ""
            html += f"""
<div style="margin: 12px 0; padding: 10px; background: #fff5f5; border-radius: 6px;">
  <a href="https://arxiv.org/abs/{p['arxiv_id']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">{p['title']}</a>{team_badge}
  <div style="color: #666; font-size: 12px; margin-top: 2px;">{', '.join(p['authors'][:4])} · {p['primary_cat']}</div>
</div>"""

    # GitHub
    html += '<h2 style="color: #1a7f37; border-bottom: 2px solid #1a7f37; padding-bottom: 6px; margin-top: 28px;">🔥 GitHub Trending</h2>'
    if curation and curation.get("repos"):
        for item in curation["repos"]:
            gid = item["id"]
            what = item.get("what", "")
            why = item.get("why", item.get("reason", ""))
            r = repo_map.get(gid)
            if not r:
                continue
            fields_html = ""
            if what:
                fields_html += f'<div style="font-size:12px;margin-top:4px;">📦 <b>{what}</b></div>'
            html += f"""
<div style="margin: 14px 0; padding: 12px; background: #f0fff4; border-radius: 8px; border-left: 3px solid #1a7f37;">
  <a href="{r['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 15px;">🔗 {r['repo']}</a>
  <div style="color: #666; font-size: 12px; margin: 2px 0;">{r['description'][:150]}</div>
  {fields_html}
  <div style="color: #1a7f37; font-size: 13px; margin-top: 4px;">🔥 {why}</div>
</div>"""
    elif repos:
        for r in repos:
            html += f"""
<div style="margin: 12px 0; padding: 10px; background: #f0fff4; border-radius: 6px;">
  <a href="{r['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">🔗 {r['repo']}</a>
  <div style="color: #666; font-size: 12px; margin-top: 2px;">{r['description'][:150]}</div>
</div>"""

    # Reddit
    html += '<h2 style="color: #ff4500; border-bottom: 2px solid #ff4500; padding-bottom: 6px; margin-top: 28px;">💬 Reddit 热门讨论</h2>'
    if curation and curation.get("reddit"):
        for item in curation["reddit"]:
            rid = item["id"]
            topic = item.get("topic", "")
            why = item.get("why", item.get("reason", ""))
            p = reddit_map.get(rid)
            if not p:
                continue
            fields_html = ""
            if topic:
                fields_html += f'<div style="font-size:12px;margin-top:4px;">💬 <b>{topic}</b></div>'
            html += f"""
<div style="margin: 12px 0; padding: 10px; background: #fff7f0; border-radius: 6px; border-left: 3px solid #ff4500;">
  <a href="{p['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">{p['title'][:120]}</a>
  <div style="color: #666; font-size: 12px; margin-top: 2px;">{p['subreddit']}</div>
  {fields_html}
  <div style="color: #ff4500; font-size: 13px; margin-top: 4px;">🔥 {why}</div>
</div>"""
    elif reddit_posts:
        for p in reddit_posts[:10]:
            html += f"""
<div style="margin: 10px 0; padding: 10px; background: #fff7f0; border-radius: 6px;">
  <a href="{p['url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">{p['title'][:120]}</a>
  <div style="color: #666; font-size: 12px; margin-top: 2px;">{p['subreddit']}</div>
</div>"""

    # HN
    html += '<h2 style="color: #ff6600; border-bottom: 2px solid #ff6600; padding-bottom: 6px; margin-top: 28px;">📰 Hacker News 头条</h2>'
    if curation and curation.get("hn"):
        for item in curation["hn"]:
            hid = item["id"]
            topic = item.get("topic", "")
            why = item.get("why", item.get("reason", ""))
            s = hn_map.get(hid)
            if not s:
                continue
            fields_html = ""
            if topic:
                fields_html += f'<div style="font-size:12px;margin-top:4px;">📰 <b>{topic}</b></div>'
            html += f"""
<div style="margin: 12px 0; padding: 10px; background: #fffaf0; border-radius: 6px; border-left: 3px solid #ff6600;">
  <a href="{s['hn_url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">{s['title'][:120]}</a>
  <div style="color: #666; font-size: 12px; margin-top: 2px;">👍 {s['score']} · 💬 {s['descendants']}</div>
  {fields_html}
  <div style="color: #ff6600; font-size: 13px; margin-top: 4px;">🔥 {why}</div>
</div>"""
    elif hn_stories:
        for s in hn_stories:
            html += f"""
<div style="margin: 10px 0; padding: 10px; background: #fffaf0; border-radius: 6px;">
  <a href="{s['hn_url']}" style="font-weight: 600; color: #1a0dab; text-decoration: none; font-size: 14px;">{s['title'][:120]}</a>
  <div style="color: #666; font-size: 12px; margin-top: 2px;">👍 {s['score']} · 💬 {s['descendants']}</div>
</div>"""

    next_time = "下午 17:00" if "上午" in time_label else "明早 08:00"
    token_detail = f"输入 {usage.get('prompt_tokens', '?')} + 输出 {usage.get('completion_tokens', '?')} = {usage.get('total_tokens', '?')} tokens" if usage else ""
    html += f"""
<div style="margin-top: 30px; padding-top: 16px; border-top: 1px solid #eee; color: #aaa; font-size: 11px; text-align: center;">
  📮 每日自动推送 · 下一封将在 {next_time} 送达<br>
  arXiv · GitHub Trending · Reddit · Hacker News · DeepSeek 策展<br>
  📊 本次消耗: {token_detail}（含初筛+发展历程两次调用）
</div>
</div></body></html>"""

    return html, time_label


# ============================================================
# 邮件发送
# ============================================================

def send_email(html, date_display, time_label):
    print("[Email] 发送邮件...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 每日科技摘要 | arXiv {date_display} {time_label}"
    msg["From"] = f"每日科技摘要 <{EMAIL_USER}>"
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())
        server.quit()
        print(f"  ✅ 邮件已发送到 {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"  ❌ 邮件发送失败: {e}")
        return False


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 60)
    print("📋 每日科技摘要")
    print("=" * 60)

    # 确定目标日期，如有必要回退到有论文的日期
    target_date_str, target_date_display = get_target_date()
    print(f"📅 目标日期: {target_date_display}")

    # 1. 拉取数据（arXiv 可能需回退到有论文的日期）
    papers = []
    for retry in range(3):
        papers = fetch_arxiv_papers(target_date_str, target_date_display)
        if papers:
            break
        # 回退一天再试
        t = datetime.strptime(target_date_str, "%Y%m%d") - timedelta(days=1)
        target_date_str = t.strftime("%Y%m%d")
        target_date_display = t.strftime("%Y-%m-%d")
        print(f"  🔄 无数据，回退到 {target_date_display}")

    repos = fetch_github_trending()
    reddit_posts = fetch_reddit()
    hn_stories = fetch_hackernews()

    # 2. DeepSeek 精选
    curation = None
    if papers or repos or reddit_posts or hn_stories:
        curation = curate_with_deepseek(papers, repos, reddit_posts, hn_stories)

    # 2.5 补充团队信息
    selected_ids = [item["id"] for item in curation["papers"]] if (curation and curation.get("papers")) else []
    if selected_ids and papers:
        papers = enrich_paper_teams(papers, selected_ids)

    # 2.6 爬参考文献 + 二次 DeepSeek 调用生成发展历程
    contexts = {}
    context_usage = {}
    if selected_ids and papers:
        contexts, context_usage = generate_context_with_deepseek(papers, selected_ids)

    # 合并两次 token 统计
    if curation and context_usage:
        u1 = curation.get("_usage", {})
        curation["_usage"] = {
            "prompt_tokens": u1.get("prompt_tokens", 0) + context_usage.get("prompt_tokens", 0),
            "completion_tokens": u1.get("completion_tokens", 0) + context_usage.get("completion_tokens", 0),
            "total_tokens": u1.get("total_tokens", 0) + context_usage.get("total_tokens", 0),
        }

    # 3. 渲染邮件
    html, time_label = render_email(papers, repos, reddit_posts, hn_stories, curation, target_date_display, contexts)

    # 4. 发送
    success = send_email(html, target_date_display, time_label)

    if success:
        print(f"\n🎉 完成！请检查 {EMAIL_TO}（也看看垃圾箱）")
    else:
        print("\n❌ 发送失败")

    print("=" * 60)


if __name__ == "__main__":
    main()
